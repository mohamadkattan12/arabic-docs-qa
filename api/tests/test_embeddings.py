from typing import Any

import numpy as np
import pytest

import api.embeddings as embeddings


class RecordingModel:
    """Stands in for fastembed's TextEmbedding (an external library); records how it is called."""

    embedding_size = 4

    def __init__(self, model: str) -> None:
        self.batch_sizes: list[int] = []
        self.inputs: list[str] = []

    def embed(self, texts: list[str], batch_size: int = 256, **_: Any) -> Any:
        self.batch_sizes.append(batch_size)
        self.inputs += texts
        return (np.zeros(4) for _ in texts)


def test_passages_are_embedded_in_small_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: fastembed's default batch of 256 chunks needs more memory than the Docker VM
    # has with multilingual-e5-large (API OOM-killed on a 10 MB upload). Batch 8 peaks ~2.2 GB.
    monkeypatch.setattr(embeddings, "TextEmbedding", RecordingModel)
    embedder = embeddings.FastEmbedder("intfloat/multilingual-e5-large")
    embedder.embed_passages(["a"] * 100)
    model: RecordingModel = embedder._model  # type: ignore[assignment]
    assert model.batch_sizes and all(b <= 8 for b in model.batch_sizes)
    assert model.inputs[0] == "passage: a"
