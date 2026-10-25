import hashlib
import re
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import numpy as np
from anthropic.types import Message

DIM = 64


class HashEmbedder:
    """Deterministic bag-of-words embedder: texts sharing words get similar vectors. No download."""

    dim = DIM

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(DIM, dtype=np.float32)
        for word in re.findall(r"\w+", text.lower()):
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1  # noqa: S324
        norm = np.linalg.norm(v)
        return v / norm if norm else v + 1 / np.sqrt(DIM)

    def embed_passages(self, texts: list[str]) -> list[np.ndarray]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)


class FakeStream:
    def __init__(self, deltas: list[str], message: Message) -> None:
        self._deltas, self._message = deltas, message

    async def __aenter__(self) -> "FakeStream":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    @property
    async def text_stream(self) -> AsyncIterator[str]:  # type: ignore[misc]
        for d in self._deltas:
            yield d

    async def get_final_message(self) -> Message:
        return self._message


class FakeMessages:
    def __init__(self, client: "FakeClaude", beta: bool) -> None:
        self._client, self._beta = client, beta

    def stream(self, **params: Any) -> FakeStream:
        self._client.calls.append({"beta": self._beta, **params})
        return FakeStream(self._client.deltas, self._client.message)


class FakeClaude:
    """Stands in for anthropic.AsyncAnthropic; records every request."""

    def __init__(self, deltas: list[str], message: Message) -> None:
        self.deltas, self.message = deltas, message
        self.calls: list[dict[str, Any]] = []
        self.messages = FakeMessages(self, beta=False)
        self.beta = SimpleNamespace(messages=FakeMessages(self, beta=True))


def claude_message(
    content: list[dict[str, Any]], stop_reason: str = "end_turn", model: str = "claude-opus-5-5"
) -> Message:
    """A real SDK Message object built from API-shaped JSON."""
    return Message.model_validate(
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": model,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 1000, "output_tokens": 100},
            "content": content,
        }
    )


def cite(index: int, quote: str) -> dict[str, Any]:
    return {
        "type": "search_result_location",
        "cited_text": quote,
        "source": "s",
        "title": "t",
        "search_result_index": index,
        "start_block_index": 0,
        "end_block_index": 1,
    }
