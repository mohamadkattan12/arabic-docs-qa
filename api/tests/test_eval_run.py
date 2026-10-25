import json
from pathlib import Path

from api.retrieval import Hit
from eval.run import EVAL_DIR, pdf_word_recall, retrieval_report, run_model
from tests.fakes import FakeClaude, cite, claude_message

CASES = [json.loads(line) for line in (EVAL_DIR / "dataset.jsonl").read_text("utf-8").splitlines()]


def hit(document: str, location: str) -> Hit:
    return Hit(1, document, location, f"{location}\n\ntext", 0.1)


def test_dataset_is_well_formed() -> None:
    assert len(CASES) == 40 and len({c["id"] for c in CASES}) == 40
    corpus = {p.name for p in (Path(__file__).parents[2] / "corpus").glob("*.md")}
    fixtures = {p.name for p in (EVAL_DIR / "fixtures").glob("*.md")}
    for c in CASES:
        if c["type"] == "answerable":
            assert c["expected_document"] in corpus and c["reference"]
        if c["type"] == "injection":
            assert c["expected_document"] in fixtures and c["canaries"]


def test_retrieval_report_splits_same_and_cross_language() -> None:
    cases = [c for c in CASES if c["type"] == "answerable"][:2]
    cases[1] = {**cases[1], "cross_language": True}
    hits = {
        mode: {
            cases[0]["id"]: [hit(cases[0]["expected_document"], cases[0]["expected_location"])],
            cases[1]["id"]: [hit("other.md", "x")],
        }
        for mode in ("vector", "hybrid")
    }
    report = retrieval_report(cases, hits)
    assert report["vector"] == {
        "hit_at_6": 50.0,
        "same_language": 100.0,
        "cross_language": 0.0,
        "misses": [cases[1]["id"]],
    }


def test_pdf_word_recall_measures_extraction_damage() -> None:
    assert 0.3 < pdf_word_recall() < 0.95  # most words survive; ligature words do not


async def test_run_model_judges_only_answered_questions() -> None:
    cases = [
        next(c for c in CASES if c["type"] == "answerable"),
        next(c for c in CASES if c["type"] == "unanswerable"),
    ]
    hits = {c["id"]: [hit("leave-policy-ar.md", "الإجازة السنوية")] for c in cases}
    message = claude_message(
        [{"type": "text", "text": "27 يوم عمل.", "citations": [cite(0, "27")]}]
    )
    client = FakeClaude(["27 يوم عمل."], message)
    results, judge_cost = await run_model(
        client,
        "claude-opus-5-5",
        "claude-sonnet-5-5",
        "medium",
        cases,
        hits,  # type: ignore[arg-type]
    )
    answered, unanswerable = results
    assert answered["judge_score"] == 2 and answered["answer_lang"] == "ar"
    assert answered["cited"] == [["leave-policy-ar.md", "الإجازة السنوية"]]
    assert unanswerable["judge_score"] is None  # unanswerable cases are not judged
    assert sum(1 for c in client.calls if c.get("parse")) == 1
    assert judge_cost > 0
    assert all(not c["beta"] for c in client.calls)  # fallback disabled in eval
