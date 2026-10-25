from typing import Protocol

import numpy as np
from fastembed import TextEmbedding

# fastembed's default (256) exceeds the Docker VM's memory with e5-large; 8 peaks at ~2.2 GB.
BATCH_SIZE = 8


class Embedder(Protocol):
    dim: int

    def embed_passages(self, texts: list[str]) -> list[np.ndarray]: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class FastEmbedder:
    def __init__(self, model: str) -> None:
        self._model = TextEmbedding(model)
        self.dim = self._model.embedding_size
        # e5 models are trained with these prefixes; fastembed does not add them.
        self._e5 = "e5" in model
        self._passage = "passage: " if self._e5 else ""
        self._query = "query: " if self._e5 else ""

    def embed_passages(self, texts: list[str]) -> list[np.ndarray]:
        return list(self._model.embed([self._passage + t for t in texts], batch_size=BATCH_SIZE))

    def embed_query(self, text: str) -> np.ndarray:
        return next(iter(self._model.embed([self._query + text])))
