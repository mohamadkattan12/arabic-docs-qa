import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.db import migrate, open_pool
from api.embeddings import FastEmbedder
from api.ingest import ingest_corpus

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.embedder = FastEmbedder(settings.embedding_model)
    migrate(settings.database_url, app.state.embedder.dim)
    app.state.pool = open_pool(settings.database_url)
    with app.state.pool.connection() as conn:
        added = ingest_corpus(conn, Path(settings.corpus_dir), app.state.embedder)
    log.info("corpus documents added: %d", added)
    yield
    app.state.pool.close()


app = FastAPI(title="Arabic Docs Q&A", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
