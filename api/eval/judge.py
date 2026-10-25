from typing import Literal

import anthropic
from pydantic import BaseModel

from api.answer import cost

JUDGE_PROMPT = """You grade an answer from a company-policy assistant against a reference answer.

<question>{question}</question>
<reference_answer>{reference}</reference_answer>
<candidate_answer>{answer}</candidate_answer>

Scores:
2 = correct and complete: every key fact in the reference (numbers, conditions, limits) is present,
    and nothing contradicts it.
1 = partly correct: a key fact is missing, or there is a minor error.
0 = wrong, contradicts the reference, or does not answer the question.

The candidate may be written in a different language from the reference: grade the meaning, not
the language. Extra correct detail is fine."""


class Verdict(BaseModel):
    score: Literal[0, 1, 2]
    reason: str


async def judge(
    client: anthropic.AsyncAnthropic, model: str, question: str, reference: str, answer: str
) -> tuple[Verdict, float]:
    """Returns the verdict and the judge call's cost in USD."""
    response = await client.messages.parse(
        model=model,
        max_tokens=4000,
        output_config={"effort": "medium"},
        messages=[
            {
                "role": "user",
                "content": JUDGE_PROMPT.format(
                    question=question, reference=reference, answer=answer
                ),
            }
        ],
        output_format=Verdict,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"judge returned no verdict (stop_reason={response.stop_reason})")
    usage = response.usage
    return response.parsed_output, cost(model, usage.input_tokens, usage.output_tokens)
