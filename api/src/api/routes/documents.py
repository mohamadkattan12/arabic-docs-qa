from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from api.ingest import SUPPORTED_EXTENSIONS, UnsupportedFile, ingest

router = APIRouter()
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class DocumentOut(BaseModel):
    id: UUID
    name: str
    lang: str
    chunks: int
    created_at: datetime


class UploadOut(BaseModel):
    id: UUID
    name: str
    created: bool


@router.post("/documents", status_code=201)
async def upload(file: UploadFile, request: Request, response: Response) -> UploadOut:
    name = Path(file.filename or "").name
    if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(415, "Only .pdf, .md and .txt files are supported.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Files must be 10 MB or smaller.")

    def store() -> tuple[UUID, bool]:
        with request.app.state.pool.connection() as conn:
            return ingest(conn, name, data, request.app.state.embedder)

    try:
        doc_id, created = await run_in_threadpool(store)
    except UnsupportedFile as e:
        raise HTTPException(422, str(e)) from e
    if not created:
        response.status_code = 200
    return UploadOut(id=doc_id, name=name, created=created)


@router.get("/documents")
def list_documents(request: Request) -> list[DocumentOut]:
    with request.app.state.pool.connection() as conn:
        rows = conn.execute(
            "SELECT d.id, d.name, d.lang, count(c.id), d.created_at FROM documents d "
            "LEFT JOIN chunks c ON c.document_id = d.id GROUP BY d.id ORDER BY d.name"
        ).fetchall()
    return [DocumentOut(id=r[0], name=r[1], lang=r[2], chunks=r[3], created_at=r[4]) for r in rows]


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: UUID, request: Request) -> None:
    with request.app.state.pool.connection() as conn:
        deleted = conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,)).rowcount
    if not deleted:
        raise HTTPException(404, "Document not found.")
