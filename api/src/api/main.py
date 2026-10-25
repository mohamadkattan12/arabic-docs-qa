import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.db import migrate, open_pool
from api.embeddings import FastEmbedder
from api.ingest import ingest_corpus
from api.routes import ask, documents, evaluation

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.embedder = FastEmbedder(settings.embedding_model)
    migrate(settings.database_url, app.state.embedder.dim)
    app.state.pool = open_pool(settings.database_url)
    with app.state.pool.connection() as conn:
        added = ingest_corpus(conn, Path(settings.corpus_dir), app.state.embedder)
    log.info("corpus documents added: %d", added)
    key = settings.anthropic_api_key
    app.state.claude = anthropic.AsyncAnthropic(api_key=key.get_secret_value()) if key else None
    if app.state.claude is None:
        log.warning("ANTHROPIC_API_KEY is not set; /ask will return an error until it is.")
    yield
    app.state.pool.close()


logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Arabic Docs Q&A", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


for module in (ask, documents, evaluation):
    app.include_router(module.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
