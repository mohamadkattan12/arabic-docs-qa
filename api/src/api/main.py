from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.db import migrate, open_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    migrate(settings.database_url, settings.embedding_dim)
    app.state.pool = open_pool(settings.database_url)
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
