from pathlib import Path
from typing import Literal

import psycopg
import pytest

from api.ingest import ingest_corpus
from api.retrieval import FTS_SQL, retrieve
from tests.fakes import HashEmbedder

CORPUS = Path(__file__).parents[2] / "corpus"


@pytest.fixture
def corpus_conn(conn: psycopg.Connection) -> psycopg.Connection:
    ingest_corpus(conn, CORPUS, HashEmbedder())
    return conn


@pytest.mark.parametrize("mode", ["vector", "hybrid"])
@pytest.mark.parametrize(
    ("question", "document", "location"),
    [
        ("كم عدد أيام الإجازة السنوية؟", "leave-policy-ar.md", "الإجازة السنوية"),
        ("ما هي ساعات العمل في رمضان؟", "working-hours-ar.md", "شهر رمضان"),
        ("What is the hotel limit per night abroad?", "travel-policy-en.md", "Hotels"),
        ("How many days can I work remotely per week?", "remote-work-policy-en.md", "Allowance"),
    ],
)
def test_expected_section_is_in_top_6(
    corpus_conn: psycopg.Connection,
    question: str,
    document: str,
    location: str,
    mode: Literal["vector", "hybrid"],
) -> None:
    hits = retrieve(corpus_conn, question, HashEmbedder(), mode=mode)
    assert len(hits) == 6
    assert (document, location) in [(h.document, h.location) for h in hits]
    assert hits == sorted(hits, key=lambda h: h.score, reverse=True)


def test_question_without_searchable_words_still_returns_vector_hits(
    corpus_conn: psycopg.Connection,
) -> None:
    assert len(retrieve(corpus_conn, "؟", HashEmbedder())) == 6


def test_empty_database_returns_nothing(conn: psycopg.Connection) -> None:
    assert retrieve(conn, "annual leave", HashEmbedder()) == []


def test_hybrid_includes_full_text_and_vector_matches(corpus_conn: psycopg.Connection) -> None:
    # HNSW search is approximate (randomized graph), so compare sets that hold for any index
    # build: every full-text match and every vector candidate appears in the fused results.
    question = "إجازة"  # full-text stemming matches "الإجازة"; the hash embedder does not
    text_ids = {r[0] for r in corpus_conn.execute(FTS_SQL, {"q": question, "n": 20})}
    vector = {h.chunk_id for h in retrieve(corpus_conn, question, HashEmbedder(), k=20)}
    hybrid = {
        h.chunk_id for h in retrieve(corpus_conn, question, HashEmbedder(), k=40, mode="hybrid")
    }
    assert text_ids and text_ids <= hybrid
    assert vector <= hybrid
