from dataclasses import dataclass
from typing import Literal

import psycopg

from api.embeddings import Embedder

RRF_K = 60  # standard Reciprocal Rank Fusion constant
CANDIDATES = 20

# Questions are matched with OR (any meaningful word), using both Arabic and English stemming.
FTS_SQL = """
SELECT id FROM chunks,
    CAST(replace(CAST(plainto_tsquery('arabic', %(q)s) AS text), '&', '|') AS tsquery) qa,
    CAST(replace(CAST(plainto_tsquery('english', %(q)s) AS text), '&', '|') AS tsquery) qe
WHERE tsv @@ (qa || qe)
ORDER BY ts_rank(tsv, qa || qe) DESC
LIMIT %(n)s
"""


@dataclass(frozen=True)
class Hit:
    chunk_id: int
    document: str
    location: str
    content: str
    score: float


def retrieve(
    conn: psycopg.Connection,
    question: str,
    embedder: Embedder,
    k: int = 6,
    mode: Literal["vector", "hybrid"] = "vector",
) -> list[Hit]:
    """Vector search; "hybrid" also merges full-text top-N by Reciprocal Rank Fusion."""
    vector_ids = [
        r[0]
        for r in conn.execute(
            "SELECT id FROM chunks ORDER BY embedding <=> %s LIMIT %s",
            (embedder.embed_query(question), CANDIDATES),
        )
    ]
    text_ids = (
        [r[0] for r in conn.execute(FTS_SQL, {"q": question, "n": CANDIDATES})]
        if mode == "hybrid"
        else []
    )

    scores: dict[int, float] = {}
    for ranked in (vector_ids, text_ids):
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (RRF_K + rank)
    top = sorted(scores, key=lambda i: scores[i], reverse=True)[:k]
    if not top:
        return []

    rows = {
        r[0]: r
        for r in conn.execute(
            "SELECT c.id, d.name, c.location, c.content FROM chunks c "
            "JOIN documents d ON d.id = c.document_id WHERE c.id = ANY(%s)",
            (top,),
        )
    }
    return [Hit(i, rows[i][1], rows[i][2], rows[i][3], scores[i]) for i in top]
