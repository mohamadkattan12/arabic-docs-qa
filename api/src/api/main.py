from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings

app = FastAPI(title="Arabic Docs Q&A")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
