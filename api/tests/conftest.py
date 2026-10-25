import os
from collections.abc import Iterator

import psycopg
import pytest

ADMIN_URL = os.environ.get(
    "TEST_ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5434/postgres"
)
TEST_DB = "docsqa_test"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """A fresh, empty test database for the whole test session."""
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {TEST_DB}")
    yield ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB}"
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
