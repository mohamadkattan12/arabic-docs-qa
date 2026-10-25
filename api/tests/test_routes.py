import json
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from api.config import settings
from api.db import open_pool
from api.ingest import ingest_corpus
from api.main import app
from tests.fakes import FakeClaude, HashEmbedder, cite, claude_message

CORPUS = Path(__file__).parents[2] / "corpus"


@pytest.fixture
def client(conn: psycopg.Connection, database_url: str) -> Iterator[TestClient]:
    """The real app with test state; the lifespan (model download, real Claude) is not run."""
    ingest_corpus(conn, CORPUS, HashEmbedder())
    pool = open_pool(database_url)
    app.state.pool, app.state.embedder = pool, HashEmbedder()
    app.state.claude = FakeClaude(
        ["سبعة وعشرون", " يوماً."],
        claude_message(
            [{"type": "text", "text": "سبعة وعشرون يوماً.", "citations": [cite(0, "27 يوم")]}]
        ),
    )
    yield TestClient(app, headers={"X-Requested-By": "arabic-docs-qa"})
    pool.close()


def sse(text: str) -> list[tuple[str, dict[str, object]]]:
    events = []
    for block in text.replace("\r\n", "\n").strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def test_ask_streams_deltas_then_done_with_citations(client: TestClient) -> None:
    response = client.post("/ask", json={"question": "كم يوم إجازة سنوية؟"})
    assert response.status_code == 200
    assert "\r" not in response.text  # plain "\n" separators (see routes/ask.py)
    events = sse(response.text)
    assert [e for e, _ in events] == ["delta", "delta", "done"]
    done = events[-1][1]
    assert done["answerable"] is True
    citations = done["citations"]
    assert isinstance(citations, list) and citations[0]["quote"] == "27 يوم"
    # the fake client recorded the real request: retrieved chunks + question
    (call,) = app.state.claude.calls
    content = call["messages"][0]["content"]
    assert content[-1] == {"type": "text", "text": "كم يوم إجازة سنوية؟"}
    assert sum(b["type"] == "search_result" for b in content) == 6


def test_ask_without_api_key_returns_error_event(client: TestClient) -> None:
    app.state.claude = None
    assert sse(client.post("/ask", json={"question": "q"}).text)[0][0] == "error"


@pytest.mark.parametrize("question", ["", "x" * 1001])
def test_ask_validates_question(client: TestClient, question: str) -> None:
    assert client.post("/ask", json={"question": question}).status_code == 422


def test_upload_list_delete(client: TestClient) -> None:
    files = {"file": ("notes.md", b"# Parking\n\nParking is on level B2.", "text/markdown")}
    created = client.post("/documents", files=files)
    assert created.status_code == 201 and created.json()["created"] is True
    again = client.post("/documents", files=files)
    assert again.status_code == 200 and again.json() == {**created.json(), "created": False}

    docs = {d["name"]: d for d in client.get("/documents").json()}
    assert len(docs) == 9 and docs["notes.md"]["chunks"] == 1

    doc_id = created.json()["id"]
    assert client.delete(f"/documents/{doc_id}").status_code == 204
    assert client.delete(f"/documents/{doc_id}").status_code == 404
    assert len(client.get("/documents").json()) == 8


@pytest.mark.parametrize(
    ("name", "data", "status"),
    [
        ("virus.exe", b"MZ", 415),
        ("big.txt", b"a" * (10 * 1024 * 1024 + 1), 413),
        ("broken.pdf", b"not a pdf", 422),
        ("../../etc/passwd.md", b"# Hi\n\nok", 201),  # path is stripped to the base name
    ],
)
def test_upload_rejects_bad_files(client: TestClient, name: str, data: bytes, status: int) -> None:
    response = client.post("/documents", files={"file": (name, data)})
    assert response.status_code == status
    if status == 201:
        assert response.json()["name"] == "passwd.md"


def test_eval_latest(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "eval_results_dir", str(tmp_path))
    assert client.get("/eval/latest").status_code == 404
    (tmp_path / "2026-10-25T10-00-00.json").write_text('{"run": "old"}')
    (tmp_path / "2026-10-25T11-00-00.json").write_text('{"run": "new"}')
    assert client.get("/eval/latest").json() == {"run": "new"}


def test_cors_allows_only_the_web_origin(client: TestClient) -> None:
    def preflight(origin: str) -> str | None:
        response = client.options(
            "/ask", headers={"Origin": origin, "Access-Control-Request-Method": "POST"}
        )
        return response.headers.get("access-control-allow-origin")

    assert preflight("http://localhost:3000") == "http://localhost:3000"
    assert preflight("https://evil.example") is None


def test_upload_rejects_documents_longer_than_the_chunk_limit(client: TestClient) -> None:
    # Regression: a 10 MB text (~4,400 chunks) takes over an hour to embed on CPU and exhausted
    # memory; documents are capped by chunk count instead.
    from api.chunking import MAX_CHARS
    from api.ingest import MAX_CHUNKS

    sentence = "Employees may work remotely two days per week. "
    # one chunk each: under MAX_CHARS, and too long for two to merge
    paragraph = sentence * ((MAX_CHARS - 100) // len(sentence))
    too_long = "\n\n".join([paragraph] * (MAX_CHUNKS + 1)).encode()
    response = client.post("/documents", files={"file": ("handbook.txt", too_long)})
    assert response.status_code == 413
    assert str(MAX_CHUNKS) in response.json()["detail"]
    assert len(client.get("/documents").json()) == 8  # nothing stored

    at_limit = "\n\n".join([paragraph] * MAX_CHUNKS).encode()
    assert client.post("/documents", files={"file": ("ok.txt", at_limit)}).status_code == 201


def test_document_changes_require_the_app_header(client: TestClient) -> None:
    files = {"file": ("x.md", b"# X\n\nplanted")}
    assert client.post("/documents", files=files, headers={"X-Requested-By": ""}).status_code == 403
    doc_id = client.get("/documents").json()[0]["id"]
    bad = client.delete(f"/documents/{doc_id}", headers={"X-Requested-By": "other"})
    assert bad.status_code == 403
    assert len(client.get("/documents").json()) == 8
