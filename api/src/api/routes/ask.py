import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse, ServerSentEvent
from starlette.concurrency import run_in_threadpool

from api.answer import Done, answer_stream
from api.config import settings
from api.retrieval import Hit, retrieve

router = APIRouter()
log = logging.getLogger("api.ask")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


def _event(name: str, data: object) -> ServerSentEvent:
    return ServerSentEvent(event=name, data=json.dumps(data, ensure_ascii=False))


@router.post("/ask")
async def ask(body: AskRequest, request: Request) -> EventSourceResponse:
    state = request.app.state

    def search() -> list[Hit]:
        with state.pool.connection() as conn:
            return retrieve(conn, body.question, state.embedder, mode=settings.retrieval_mode)

    async def events() -> AsyncIterator[ServerSentEvent]:
        question_id = uuid.uuid4().hex[:12]
        started = time.monotonic()
        if state.claude is None:
            yield _event("error", {"message": "ANTHROPIC_API_KEY is not set on the server."})
            return
        try:
            hits = await run_in_threadpool(search)
            async for item in answer_stream(
                state.claude, settings.answer_model, body.question, hits
            ):
                if isinstance(item, Done):
                    log.info(
                        json.dumps(
                            {
                                "question_id": question_id,
                                "chunk_ids": [h.chunk_id for h in hits],
                                "model": item.model,
                                "answerable": item.answerable,
                                "input_tokens": item.input_tokens,
                                "output_tokens": item.output_tokens,
                                "cost_usd": round(item.cost_usd, 6),
                                "latency_s": round(time.monotonic() - started, 2),
                            }
                        )
                    )
                    yield _event("done", asdict(item))
                else:
                    yield _event("delta", {"text": item})
        except Exception:
            log.exception("ask failed (question_id=%s)", question_id)
            yield _event("error", {"message": "Something went wrong while answering."})

    return EventSourceResponse(events())
