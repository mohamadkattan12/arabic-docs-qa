from typing import Any

COLUMNS = [
    ("answer_score", "Answer score"),
    ("citation_accuracy", "Citations"),
    ("refusal_accuracy", "Refuses when not in docs"),
    ("false_refusal_rate", "False refusals"),
    ("injection_resisted", "Injection resisted"),
    ("language_match", "Answer language"),
    ("cost_per_100_usd", "Cost / 100 Q (USD)"),
    ("median_latency_s", "Median latency (s)"),
]


def fmt(value: Any, key: str) -> str:
    if value is None:
        return "n/a"
    if key == "cost_per_100_usd":
        return f"${value:.2f}"
    if key == "median_latency_s":
        return f"{value:.1f}"
    return f"{value:.0f}%"


def markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# Evaluation {result['created_at']}",
        "",
        f"{result['dataset_size']} cases · embeddings `{result['embedding_model']}` · "
        f"answer retrieval `{result['retrieval_mode']}` · judge `{result['judge_model']}` · "
        f"effort `{result['effort']}`",
        "",
        "## Answer models",
        "",
        "| Model | " + " | ".join(label for _, label in COLUMNS) + " |",
        "|---|" + "---|" * len(COLUMNS),
    ]
    for model, s in result["models"].items():
        lines.append(f"| `{model}` | " + " | ".join(fmt(s[k], k) for k, _ in COLUMNS) + " |")
    lines += ["", f"**Recommended model:** `{result['recommended']}`", ""]
    failed = {m: s["errors"] for m, s in result["models"].items() if s.get("errors")}
    if failed:
        lines += [f"Failed cases (API errors, excluded from the metrics): {failed}", ""]
    lines += ["## Retrieval (expected section in top 6)", ""]
    lines += ["| Mode | All | Same language | Cross-language |", "|---|---|---|---|"]
    for mode, r in result["retrieval"].items():
        lines.append(
            f"| `{mode}` | {fmt(r['hit_at_6'], '')} | {fmt(r['same_language'], '')} | "
            f"{fmt(r['cross_language'], '')} |"
        )
    lines += [
        "",
        f"Arabic PDF extraction: {result['pdf_word_recall']:.0%} of the source document's words "
        "come out of the PDF intact.",
        "",
    ]
    return "\n".join(lines)
