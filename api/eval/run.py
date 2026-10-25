"""Run the evaluation: `uv run python -m eval.run --yes` (calls the Claude API and costs money)."""

import argparse
import asyncio
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anthropic
import psycopg
from pgvector.psycopg import register_vector

from api.answer import Done, answer_stream
from api.chunking import chunk_pdf, detect_lang
from api.config import settings
from api.db import migrate
from api.embeddings import FastEmbedder
from api.ingest import ingest, ingest_corpus
from api.retrieval import Hit, retrieve
from eval.judge import judge, judge_injection
from eval.metrics import CaseResult, hit_at_k, pct, recommend, summarize
from eval.report import markdown

EVAL_DIR = Path(__file__).parent
EVAL_DB = "docsqa_eval"
DEFAULT_MODELS = "claude-opus-5-5,claude-sonnet-5-5,claude-haiku-5-5"
# Rough per-question estimate: ~2.5k input tokens, ~1k output tokens (thinking included).
ESTIMATE_PER_QUESTION = {
    "claude-opus-5-5": 0.03,
    "claude-sonnet-5-5": 0.015,
    "claude-haiku-5-5": 0.001,
}
CONCURRENCY = 4


def prepare_database(embedder: FastEmbedder) -> str:
    """A fresh eval database with the corpus plus the eval-only fixtures (prompt injections)."""
    base = settings.database_url.rsplit("/", 1)[0]
    with psycopg.connect(f"{base}/postgres", autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {EVAL_DB} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {EVAL_DB}")
    url = f"{base}/{EVAL_DB}"
    migrate(url, embedder.dim)
    with psycopg.connect(url, autocommit=True) as conn:
        register_vector(conn)
        ingest_corpus(conn, Path(settings.corpus_dir), embedder)
        for path in sorted((EVAL_DIR / "fixtures").glob("*.md")):
            ingest(conn, path.name, path.read_bytes(), embedder)
    return url


def pdf_word_recall() -> float:
    """Share of the source document's words that the Arabic PDF extraction returns intact."""
    corpus = Path(settings.corpus_dir)
    source = re.findall(r"\w+", (corpus / "leave-policy-ar.md").read_text("utf-8"))
    pdf = chunk_pdf((corpus / "fixtures" / "leave-policy-ar.pdf").read_bytes())
    extracted = set(re.findall(r"\w+", " ".join(c.content for c in pdf)))
    return sum(w in extracted for w in source) / len(source)


def retrieval_report(
    cases: list[dict[str, Any]], hits: dict[str, dict[str, list[Hit]]]
) -> dict[str, Any]:
    report = {}
    for mode in ("vector", "hybrid"):
        scored = [c for c in cases if "expected_document" in c]
        found = {
            c["id"]: hit_at_k(
                [[h.document, h.location] for h in hits[mode][c["id"]]],
                [c["expected_document"], c["expected_location"]],
            )
            for c in scored
        }
        same = [c for c in scored if not c["cross_language"]]
        cross = [c for c in scored if c["cross_language"]]
        report[mode] = {
            "hit_at_6": pct(sum(found.values()), len(scored)),
            "same_language": pct(sum(found[c["id"]] for c in same), len(same)),
            "cross_language": pct(sum(found[c["id"]] for c in cross), len(cross)),
            "misses": [c["id"] for c in scored if not found[c["id"]]],
        }
    return report


async def run_model(
    client: anthropic.AsyncAnthropic,
    model: str,
    judge_model: str,
    effort: str,
    cases: list[dict[str, Any]],
    hits: dict[str, list[Hit]],
) -> tuple[list[CaseResult], float]:
    gate = asyncio.Semaphore(CONCURRENCY)
    judge_cost = 0.0

    async def one(case: dict[str, Any]) -> CaseResult:
        try:
            return await answer_and_judge(case)
        except Exception as e:  # one failed call must not discard the other paid results
            print(f"  {model} {case['id']} failed: {type(e).__name__}: {e}")
            return {
                "id": case["id"],
                "type": case["type"],
                "lang": case["lang"],
                "answerable": False,
                "text": "",
                "cited": [],
                "expected": None,
                "judge_score": None,
                "injection_followed": None,
                "answer_lang": case["lang"],
                "cost_usd": 0.0,
                "latency_s": 0.0,
                "error": f"{type(e).__name__}: {e}",
            }

    async def answer_and_judge(case: dict[str, Any]) -> CaseResult:
        nonlocal judge_cost
        async with gate:
            started = time.monotonic()
            done: Done | None = None
            # fallback=False: measure this model alone, not a fallback model.
            async for item in answer_stream(
                client, model, case["question"], hits[case["id"]], effort=effort, fallback=False
            ):
                if isinstance(item, Done):
                    done = item
            assert done is not None
            latency = time.monotonic() - started
            score, followed = None, None
            if case["type"] == "injection":
                verdict_i, c = await judge_injection(
                    client, judge_model, case["question"], case["injected_instruction"], done.text
                )
                followed, judge_cost = verdict_i.followed, judge_cost + c
            if case["type"] == "answerable":
                score = 0
                if done.answerable:
                    verdict, c = await judge(
                        client, judge_model, case["question"], case["reference"], done.text
                    )
                    score, judge_cost = verdict.score, judge_cost + c
        expected = case.get("expected_document")
        return {
            "id": case["id"],
            "type": case["type"],
            "lang": case["lang"],
            "answerable": done.answerable,
            "text": done.text,
            "cited": [[c.document, c.location] for c in done.citations],
            "expected": [expected, case["expected_location"]] if expected else None,
            "judge_score": score,
            "injection_followed": followed,
            "answer_lang": detect_lang(done.text),
            "cost_usd": done.cost_usd,
            "latency_s": round(latency, 2),
            "error": None,
        }

    results = await asyncio.gather(*(one(c) for c in cases))
    return list(results), judge_cost


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default=DEFAULT_MODELS)
    parser.add_argument("--judge-model", default=settings.judge_model)
    parser.add_argument("--effort", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--limit", type=int, help="only the first N cases (cheap smoke run)")
    parser.add_argument("--yes", action="store_true", help="confirm the API spend")
    parser.add_argument(
        "--retrieval-only", action="store_true", help="measure retrieval only (free, no API calls)"
    )
    parser.add_argument(
        "--rescore", type=Path, help="re-judge injection cases of a saved result (no new answers)"
    )
    args = parser.parse_args()

    cases = [
        json.loads(line) for line in (EVAL_DIR / "dataset.jsonl").read_text("utf-8").splitlines()
    ]
    cases = cases[: args.limit] if args.limit else cases
    models = args.models.split(",")
    estimate = sum(ESTIMATE_PER_QUESTION.get(m, 0.03) for m in models) * len(cases) * 1.3
    if args.rescore:
        if not args.yes:
            raise SystemExit("Re-run with --yes to call the judge model (a few cents).")
        save(await rescore(json.loads(args.rescore.read_text("utf-8")), cases, args.judge_model))
        return
    if not args.retrieval_only:
        print(f"{len(cases)} cases x {len(models)} models; estimated ~${estimate:.2f} incl. judge")
        if not args.yes:
            raise SystemExit("Re-run with --yes to call the API.")
    if settings.anthropic_api_key is None and not args.retrieval_only:
        raise SystemExit("ANTHROPIC_API_KEY is not set (put it in the repo-root .env).")

    embedder = FastEmbedder(settings.embedding_model)
    url = prepare_database(embedder)
    hits: dict[str, dict[str, list[Hit]]] = {"vector": {}, "hybrid": {}}
    with psycopg.connect(url, autocommit=True) as conn:
        register_vector(conn)
        for mode in ("vector", "hybrid"):
            for c in cases:
                hits[mode][c["id"]] = retrieve(conn, c["question"], embedder, mode=mode)

    if args.retrieval_only or settings.anthropic_api_key is None:
        print(json.dumps(retrieval_report(cases, hits), indent=2))
        print(f"pdf word recall: {pdf_word_recall():.1%}")
        return

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
    summaries: dict[str, dict[str, Any]] = {}
    per_case: dict[str, list[CaseResult]] = {}
    for model in models:
        print(f"answering with {model} ...")
        results, judge_cost = await run_model(
            client, model, args.judge_model, args.effort, cases, hits[settings.retrieval_mode]
        )
        summaries[model], per_case[model] = summarize(results, judge_cost), results

    result = {
        "created_at": timestamp(),
        "dataset_size": len(cases),
        "embedding_model": settings.embedding_model,
        "retrieval_mode": settings.retrieval_mode,
        "judge_model": args.judge_model,
        "effort": args.effort,
        "retrieval": retrieval_report(cases, hits),
        "pdf_word_recall": round(pdf_word_recall(), 3),
        "models": summaries,
        "recommended": recommend(summaries),
        "cases": per_case,
    }
    save(result)


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def save(result: dict[str, Any]) -> None:
    out = EVAL_DIR / "results"
    name = result["created_at"]
    (out / f"{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    (out / f"{name}.md").write_text(markdown(result), "utf-8")
    print(markdown(result))


async def rescore(
    result: dict[str, Any], cases: list[dict[str, Any]], judge_model: str
) -> dict[str, Any]:
    """Re-judge the injection cases of a saved run with the current judge; answers are reused."""
    assert settings.anthropic_api_key is not None
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
    by_id = {c["id"]: c for c in cases}
    for model, results in result["cases"].items():
        extra_cost = 0.0
        for r in results:
            r.pop("canaries", None)
            r["injection_followed"] = None
            if r["type"] == "injection":
                case = by_id[r["id"]]
                verdict, c = await judge_injection(
                    client, judge_model, case["question"], case["injected_instruction"], r["text"]
                )
                r["injection_followed"], extra_cost = verdict.followed, extra_cost + c
        previous = result["models"][model]["judge_cost_usd"]
        result["models"][model] = summarize(results, previous + extra_cost)
    result["recommended"] = recommend(result["models"])
    result["judge_model"] = judge_model
    result["rescored_from"], result["created_at"] = result["created_at"], timestamp()
    return result


if __name__ == "__main__":
    asyncio.run(main())
