import hashlib
import re

import numpy as np

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
