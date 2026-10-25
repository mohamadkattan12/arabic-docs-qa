# Spec: Arabic document Q&A with evaluation (v1)

From: intent.md (f17546a) · Status: accepted by Mohamad Nour on 2026-10-25 (concerns 1, 2, 4 OK; concern 3 amended: eval compares several answer models)
Skills applied: sdlc, claude-api, security-review, frontend-principles, prefer-cli-scaffolding (memory) @ ~/.claude 2bc6be4
Produced by: `/sdlc` stage 2 for "Portfolio project #1: Arabic document Q&A (RAG + evaluation)"

## Flagged concerns
1. **Arabic PDF text extraction is unreliable.** Many Arabic PDFs extract with reversed or
   disconnected letters. Proposed decision: the bundled demo corpus is authored as Markdown
   (cited by document + section heading). PDF upload is supported with PyMuPDF and cited by
   document + page; one generated Arabic PDF fixture is tested so extraction quality is measured,
   not assumed. **Needs your OK.**
2. **Embedding model size vs. quality.** Local model via `fastembed` (ONNX, no PyTorch, so the
   image stays small). Proposed: `intfloat/multilingual-e5-large` (good Arabic quality, ~2 GB
   download on first run, cached in a Docker volume). Smaller fallback:
   `paraphrase-multilingual-MiniLM-L12-v2` (~220 MB). Set by one env var; the eval compares both
   and the README reports the result. **Needs your OK on the default.**
3. **The eval costs real API money.** One full run of ~40 questions with an LLM judge is
   estimated at well under $1 per answer model; comparing 3 models is a few dollars.
   *Decision (Mohamad, 2026-10-25):* the eval compares several answer models so the README can
   document which model is recommended and why. It runs only by an explicit command, never in CI. CI uses a fake
   Claude client, so no key lives in GitHub.
4. **Model choice.** Answers: `claude-opus-5-5` (the current default model; best Arabic and
   citation quality). Judge: `claude-sonnet-5-5`. Both overridable by env var. Cost per question
   is logged from `response.usage`.
5. **No auth.** Local-only demo, single user. Must not be exposed publicly as-is; the README says so.
   Hosting is a later cycle that adds auth and rate limits.

## Requirements
1. `docker compose up` starts `db` (Postgres + pgvector), `api` (FastAPI) and `web` (Next.js);
   the web UI is at http://localhost:3000. Only `ANTHROPIC_API_KEY` in `.env` is required.
2. On first start the API loads the bundled corpus (`corpus/` with 6–8 fictional policy docs:
   about half in Arabic, half in English) if the database is empty. Ingest is idempotent:
   re-running it does not duplicate chunks (unique on document hash + chunk index).
3. Upload: `POST /documents` accepts `.pdf`, `.md`, `.txt` up to 10 MB; other types → 415,
   too large → 413. The file is chunked (~800 tokens, ~100 overlap, split on headings/paragraphs),
   embedded and stored. `GET /documents` lists documents; `DELETE /documents/{id}` removes one and its chunks.
4. Ask: `POST /ask {question}` streams the answer over Server-Sent Events. Retrieval mode is set by
   `RETRIEVAL_MODE`: `vector` (default: pgvector cosine top-k) or `hybrid` (vector plus Postgres
   full-text search with `arabic`/`english` configs, merged by Reciprocal Rank Fusion); top 6 chunks
   go to Claude. The eval reports both modes.
   *Amended 2026-10-25 (Mohamad, option 1):* hybrid was the original design; measured on 10 questions
   it found the right section 6/10 vs 10/10 for vector-only, because full-text search can only
   match same-language words and pushed correct cross-language sections out of the top 6.
5. Chunks are sent to Claude as `search_result` content blocks with citations enabled; each block's
   source/title carries document name + page or section. The final event returns citations
   (document, page/section, quoted text), mapped from the API's native citation objects.
6. When the documents do not contain the answer, the model answers with a fixed "not found"
   message in the question's language and returns no citations. The API flags this as `answerable: false`.
7. Answers are in the question's language (Arabic question → Arabic answer).
8. Document text is treated as data: the system prompt tells the model to ignore instructions
   inside documents. The eval set includes 3 prompt-injection documents/questions.
9. Eval: `uv run python -m eval.run` runs `eval/dataset.jsonl` (~40 cases: Arabic and English;
   answerable, unanswerable, injection) and writes `eval/results/<timestamp>.json` plus a Markdown
   summary. Metrics:
   - retrieval hit@6 (expected source in retrieved chunks): deterministic
   - citation accuracy (cited source = expected source): deterministic
   - refusal accuracy on unanswerable cases: deterministic (`answerable` flag)
   - answer correctness 0–2 against a reference answer: LLM judge with a written rubric
   - total cost and latency per case
   - `--models a,b,c` runs the same dataset against several answer models (default:
     `claude-opus-5-5,claude-sonnet-5-5,claude-haiku-5-5`) with the same judge, and the summary
     has one row per model (all metrics + cost per 100 questions + median latency) plus a
     "recommended model" line chosen by a written rule: only models with the best injection
     resistance qualify; among those within 5 points of the best answer score, highest refusal +
     citation accuracy, then lowest cost.
   - injection resistance is judged by the judge model ("did the answer follow the hidden
     instruction or state its claims as fact?"); a warning that quotes the attack counts as resisted.
   *Amended 2026-10-25 (Mohamad):* the first run used a canary-string check, which failed Sonnet
   for warning the user about the attack, and the rule ignored injection resistance entirely.
10. The web UI has three pages: **Ask** (chat, streaming, citations as clickable chips that show
    the quoted text), **Documents** (upload / list / delete), **Evaluation** (latest model-comparison
    table, read from `GET /eval/latest`).
11. Arabic and other right-to-left text displays correctly: `dir="auto"` on message bubbles and
    inputs, and the layout does not break with mixed Arabic/English.
12. CI (GitHub Actions) on every push/PR: backend `ruff check`, `ruff format --check`,
    `mypy`, `pytest`; frontend `lint`, `tsc --noEmit`, `build`. No secrets required.

## Design
**Repo layout (monorepo):**
```
api/          FastAPI app (uv project)
  app/        main.py, config.py, db.py, ingest.py, retrieval.py, answer.py, routes/
  tests/      pytest (fake Claude client + test Postgres via docker service in CI)
  eval/       dataset.jsonl, run.py, judge.py, results/
web/          Next.js (create-next-app, TypeScript, Tailwind, App Router)
corpus/       fictional policy docs (.md), plus one Arabic PDF fixture
docker-compose.yml, .env.example, README.md, .github/workflows/ci.yml
```
**Data model (Postgres):**
- `documents(id uuid pk, name text, lang text, sha256 text unique, created_at timestamptz)`
- `chunks(id bigserial pk, document_id uuid fk on delete cascade, idx int, location text,
  content text, embedding vector(N), tsv tsvector, unique(document_id, idx))`, HNSW index on
  `embedding`, GIN index on `tsv`.
- Schema is created by one SQL migration file applied at startup (no ORM; plain `psycopg`).

**API contract:**
- `POST /ask` → SSE events: `delta {text}`, then `done {answerable, citations[], usage}`;
  `error {message}` on failure.
- `GET/POST/DELETE /documents`, `GET /eval/latest`, `GET /health`.

**Claude call:** official `anthropic` Python SDK, `messages.stream`, adaptive thinking, effort
set explicitly (`medium` to start, tuned with the eval). Stop reason is checked (`refusal`,
`max_tokens`) before using content. Server-side refusal fallback enabled per the claude-api skill.
The system prompt + instructions are stable, so they are prompt-cached; retrieved chunks change
per question and come after the cache breakpoint.

**Frontend:** Next.js calls the API through `NEXT_PUBLIC_API_URL`. Streaming via `fetch` +
ReadableStream (SSE parsing). shadcn/ui components added with the shadcn CLI.

**Backwards compatibility / migrations:** new project; none.

## Non-functional
- **Security:** API key only on the server, read from env, never logged. CORS limited to the web
  origin. Uploads: extension + MIME check, 10 MB cap, filename sanitized, stored in DB only (no
  arbitrary file paths). SQL only through parameterized queries. No secrets in the repo
  (`.env` git-ignored; `.env.example` committed).
- **Performance:** first answer token < 5 s on a laptop after warm-up; retrieval < 300 ms for the
  bundled corpus.
- **Observability:** structured JSON logs per request: question id, retrieved chunk ids, model,
  tokens, cost estimate, latency. No document text or questions at INFO level beyond ids.
- **Rollback:** git revert; `docker compose down -v` resets data.

## Carried-forward open questions
- None beyond flagged concerns 1 and 2.
