from typing import Any

import pytest

from api.answer import NOT_FOUND_MESSAGE, Citation, Done, answer_stream, build_content, cost
from api.retrieval import Hit
from tests.fakes import FakeClaude, cite, claude_message

HITS = [
    Hit(
        1,
        "leave-policy-ar.md",
        "الإجازة السنوية",
        "الإجازة السنوية\n\nيستحق الموظف 27 يوم عمل.",
        0.03,
    ),
    Hit(2, "travel-policy-en.md", "Hotels", "Hotels\n\nHotel limit: SAR 900 per night.", 0.02),
]


async def run(client: FakeClaude, question: str, **kw: Any) -> tuple[str, Done]:
    parts: list[str] = []
    done = None
    async for item in answer_stream(
        client, kw.pop("model", "claude-opus-5-5"), question, HITS, **kw
    ):  # type: ignore[arg-type]
        if isinstance(item, Done):
            done = item
        else:
            parts.append(item)
    assert done is not None
    return "".join(parts), done


def test_build_content_sends_citable_search_results_then_question() -> None:
    content = build_content("question?", HITS)
    assert [b["type"] for b in content] == ["search_result", "search_result", "text"]
    assert content[0]["source"] == "leave-policy-ar.md#الإجازة السنوية"
    assert content[0]["content"] == [
        {"type": "text", "text": "الإجازة السنوية"},
        {"type": "text", "text": "يستحق الموظف 27 يوم عمل."},
    ]
    assert content[0]["citations"] == {"enabled": True}
    assert content[-1] == {"type": "text", "text": "question?"}


async def test_citations_map_back_to_retrieved_chunks() -> None:
    message = claude_message(
        [
            {"type": "text", "text": "You get 27 days"},
            {
                "type": "text",
                "text": " and SAR 900 hotels.",
                "citations": [cite(1, "SAR 900"), cite(1, "SAR 900")],
            },
            {"type": "text", "text": "", "citations": [cite(0, "27 يوم")]},
        ]
    )
    streamed, done = await run(
        FakeClaude(["You get 27 days", " and SAR 900 hotels."], message), "q"
    )
    assert streamed == done.text == "You get 27 days and SAR 900 hotels."
    assert done.answerable and not done.refused
    assert done.citations == [
        Citation("travel-policy-en.md", "Hotels", "SAR 900"),
        Citation("leave-policy-ar.md", "الإجازة السنوية", "27 يوم"),
    ]
    assert (done.input_tokens, done.output_tokens) == (1000, 100)
    assert (
        done.cost_usd == pytest.approx(cost("claude-opus-5-5", 1000, 100)) == pytest.approx(0.006)
    )


async def test_not_found_sentinel_is_never_streamed() -> None:
    client = FakeClaude(["NOT_", "FOUND"], claude_message([{"type": "text", "text": "NOT_FOUND"}]))
    streamed, done = await run(client, "ما هو راتب المدير؟")
    assert streamed == ""
    assert not done.answerable and done.citations == []
    assert done.text == NOT_FOUND_MESSAGE["ar"]


async def test_refusal_is_reported_without_content() -> None:
    client = FakeClaude([], claude_message([], stop_reason="refusal"))
    _, done = await run(client, "question")
    assert done.refused and not done.answerable and done.citations == []


async def test_max_tokens_marks_answer_truncated() -> None:
    client = FakeClaude(["long"], claude_message([{"type": "text", "text": "long"}], "max_tokens"))
    _, done = await run(client, "question")
    assert done.truncated and done.answerable


@pytest.mark.parametrize(
    ("model", "fallback", "beta"),
    [
        ("claude-opus-5-5", True, True),
        ("claude-sonnet-5-5", True, True),
        ("claude-haiku-5-5", True, False),  # no server-side fallback for Haiku
        ("claude-opus-5-5", False, False),  # eval measures the model alone
    ],
)
async def test_fallback_request_shape(model: str, fallback: bool, beta: bool) -> None:
    client = FakeClaude(["ok"], claude_message([{"type": "text", "text": "ok"}], model=model))
    await run(client, "question", model=model, fallback=fallback)
    (call,) = client.calls
    assert call["beta"] is beta
    assert ("fallbacks" in call) is beta
    if beta:
        assert call["fallbacks"] == "default"
        assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "medium"}
    assert "temperature" not in call  # rejected by current models


async def test_no_hits_skips_the_api_call() -> None:
    client = FakeClaude([], claude_message([]))
    parts = [x async for x in answer_stream(client, "claude-opus-5-5", "question", [])]  # type: ignore[arg-type]
    assert client.calls == []
    assert parts == [Done(answerable=False, model="claude-opus-5-5", text=NOT_FOUND_MESSAGE["en"])]
