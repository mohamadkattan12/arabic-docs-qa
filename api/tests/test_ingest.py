import psycopg
import pytest

from api.ingest import UnsupportedFile, ingest
from tests.fakes import HashEmbedder

AR_DOC = "# سياسة الإجازات\n\nيحق للموظف الحصول على إجازة سنوية مدتها ثلاثون يوماً.\n".encode()


def test_ingest_stores_chunks_with_language(conn: psycopg.Connection) -> None:
    doc_id, created = ingest(conn, "../../leave-ar.md", AR_DOC, HashEmbedder())
    assert created
    assert conn.execute("SELECT name, lang FROM documents").fetchone() == ("leave-ar.md", "ar")
    rows = conn.execute(
        "SELECT location, fts_config::text FROM chunks WHERE document_id = %s ORDER BY idx",
        (doc_id,),
    ).fetchall()
    assert rows == [("سياسة الإجازات", "arabic")]


def test_reingest_same_bytes_is_noop(conn: psycopg.Connection) -> None:
    first, _ = ingest(conn, "a.md", AR_DOC, HashEmbedder())
    second, created = ingest(conn, "renamed.md", AR_DOC, HashEmbedder())
    assert (second, created) == (first, False)
    assert conn.execute("SELECT count(*) FROM chunks").fetchone() == (1,)


def test_arabic_full_text_search_matches_stemmed_word(conn: psycopg.Connection) -> None:
    ingest(conn, "a.md", AR_DOC, HashEmbedder())
    hit = conn.execute(
        "SELECT count(*) FROM chunks WHERE tsv @@ websearch_to_tsquery('arabic', 'الإجازة')"
    ).fetchone()
    assert hit == (1,)


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("a.exe", b"MZ", "only .pdf"),
        ("a.txt", b"\xff\xfe\x00", "UTF-8"),
        ("a.txt", b"   \n\n  ", "no text"),
        ("a.pdf", b"not a pdf", "could not read PDF"),
    ],
)
def test_rejects_bad_files(conn: psycopg.Connection, name: str, data: bytes, message: str) -> None:
    with pytest.raises(UnsupportedFile, match=message):
        ingest(conn, name, data, HashEmbedder())
    assert conn.execute("SELECT count(*) FROM documents").fetchone() == (0,)
