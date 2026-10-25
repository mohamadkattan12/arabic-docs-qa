import psycopg
import pytest

from api.db import migrate

DIM = 8


def test_migrate_is_idempotent(database_url: str) -> None:
    migrate(database_url, DIM)
    migrate(database_url, DIM)
    with psycopg.connect(database_url) as conn:
        tables = {
            r[0]
            for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        }
        indexes = {
            r[0]
            for r in conn.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'chunks'")
        }
    assert {"documents", "chunks"} <= tables
    assert {"chunks_embedding_idx", "chunks_tsv_idx"} <= indexes


def test_migrate_rejects_dimension_change(database_url: str) -> None:
    migrate(database_url, DIM)
    with pytest.raises(RuntimeError, match="dimension"):
        migrate(database_url, DIM * 2)
