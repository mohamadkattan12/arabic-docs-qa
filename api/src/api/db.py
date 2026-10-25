from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

MIGRATION = Path(__file__).parent / "migrations" / "001_init.sql"


def migrate(database_url: str, dim: int) -> None:
    """Create the schema (idempotent) and fail loudly if the stored embedding size differs."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(MIGRATION.read_text().replace("{dim}", str(int(dim))).encode())
        row = conn.execute(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
        ).fetchone()
        if row is None or row[0] != dim:
            raise RuntimeError(
                f"chunks.embedding has dimension {row and row[0]}, but the embedding model "
                f"needs {dim}. Reset the database (docker compose down -v) after changing models."
            )


def open_pool(database_url: str) -> ConnectionPool[psycopg.Connection]:
    pool: ConnectionPool[psycopg.Connection] = ConnectionPool(
        database_url, configure=register_vector, open=False
    )
    pool.open(wait=True)
    return pool
