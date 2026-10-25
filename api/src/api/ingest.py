import hashlib
from pathlib import Path
from uuid import UUID

import psycopg

from api.chunking import Chunk, chunk_markdown, chunk_pdf, chunk_plain, detect_lang
from api.embeddings import Embedder

FTS_CONFIG = {"ar": "arabic", "en": "english"}
SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}
# Embedding runs ~1 s per chunk on CPU, inside the upload request: 150 chunks (~350k characters)
# keeps an upload to a few minutes.
MAX_CHUNKS = 150


class UnsupportedFile(ValueError):
    pass


class DocumentTooLong(UnsupportedFile):
    pass


def parse(name: str, data: bytes) -> list[Chunk]:
    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        try:
            chunks = chunk_pdf(data)
        except Exception as e:  # PyMuPDF raises several types for broken files
            raise UnsupportedFile("could not read PDF") from e
    elif ext in (".md", ".txt"):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise UnsupportedFile("text files must be UTF-8") from e
        chunks = chunk_markdown(text, Path(name).stem) if ext == ".md" else chunk_plain(text)
    else:
        raise UnsupportedFile("only .pdf, .md and .txt are supported")
    if not chunks:
        raise UnsupportedFile("no text found (scanned PDFs are not supported)")
    return chunks


def ingest(
    conn: psycopg.Connection, name: str, data: bytes, embedder: Embedder
) -> tuple[UUID, bool]:
    """Store a document and its chunks. Returns (document id, created); same bytes = no-op."""
    name = Path(name).name[:200]
    sha = hashlib.sha256(data).hexdigest()
    existing = conn.execute("SELECT id FROM documents WHERE sha256 = %s", (sha,)).fetchone()
    if existing:
        return existing[0], False

    chunks = parse(name, data)
    if len(chunks) > MAX_CHUNKS:
        raise DocumentTooLong(
            f"This document has {len(chunks)} sections; the limit is {MAX_CHUNKS} "
            "(about 350,000 characters). Split it into smaller files."
        )
    vectors = embedder.embed_passages([c.content for c in chunks])
    lang = detect_lang(" ".join(c.content for c in chunks))
    with conn.transaction():
        row = conn.execute(
            "INSERT INTO documents (name, lang, sha256) VALUES (%s, %s, %s) "
            "ON CONFLICT (sha256) DO NOTHING RETURNING id",
            (name, lang, sha),
        ).fetchone()
        if row is None:  # a concurrent upload of the same file won
            again = conn.execute("SELECT id FROM documents WHERE sha256 = %s", (sha,)).fetchone()
            assert again is not None
            return again[0], False
        conn.cursor().executemany(
            "INSERT INTO chunks (document_id, idx, location, content, fts_config, embedding) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            [
                (row[0], i, c.location, c.content, FTS_CONFIG[detect_lang(c.content)], v)
                for i, (c, v) in enumerate(zip(chunks, vectors, strict=True))
            ],
        )
    return row[0], True


def ingest_corpus(conn: psycopg.Connection, corpus_dir: Path, embedder: Embedder) -> int:
    """Load the bundled demo documents into an empty database. Returns how many were added."""
    if conn.execute("SELECT 1 FROM documents LIMIT 1").fetchone():
        return 0
    paths = sorted(corpus_dir.glob("*.md"))
    return sum(ingest(conn, p.name, p.read_bytes(), embedder)[1] for p in paths)
