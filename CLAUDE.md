# Arabic Docs Q&A

Public portfolio project: Arabic/English document Q&A (RAG) with Claude citations and an
evaluation harness. Single-user local demo; no auth, no tenancy. Owner: mohamadkattan12.

## Commands
- Run: `docker compose up --build` → web http://localhost:3000, API http://localhost:8000/health → `{"status":"ok"}`
- API tests: `cd api && uv run pytest -q` → healthy: `58 passed` (needs `docker compose up -d db`; Postgres on 127.0.0.1:5434)
- API lint/types: `uv run ruff check . && uv run ruff format --check . && uv run mypy` → `All checks passed!` / `Success: no issues found in 21 source files`
- Web: `cd web && pnpm lint && pnpm typecheck && pnpm build` → exit 0, build lists routes `/`, `/documents`, `/eval`
- Eval (costs money): `docker compose run --rm eval --yes`; free: `docker compose run --rm eval --retrieval-only`

## Verifying your work
Run tests, lint and types before reporting done and paste the output tails. If a test fails,
fix the code, not the test. UI changes: check the page in Chrome. Never spend API money (eval,
live `/ask`) without the owner's OK in chat.

## Conventions
- Scaffold and add dependencies with commands (`uv add`, `pnpm add`, `pnpm dlx shadcn add`), not by editing manifests.
- Commits are authored by the owner only: no `Claude-Session` or `Co-Authored-By` trailers.
- Python 3.12, strict mypy, plain psycopg (no ORM), parameterized SQL only.
- Claude calls use the `anthropic` SDK; current models only (`claude-sonnet-5-5` default, see eval).
- Next.js 16 differs from older versions: read `web/node_modules/next/dist/docs/` before writing web code.
- Server data in the web app goes through TanStack Query; text from documents is never rendered as HTML.
- Changes follow the `sdlc` skill: intent, spec, plan in `docs/sdlc/<date>-<slug>/`, one commit per plan step, departures recorded in plan.md.

## Architecture
- `api/src/api/`: FastAPI app: `chunking`, `embeddings` (fastembed e5), `ingest`, `retrieval`, `answer` (Claude), `routes/`
- `api/eval/`: dataset, runner, judge, metrics; results in `api/eval/results/` (served by `/eval/latest`)
- `web/src/app/`: Ask, Documents, Evaluation pages; `web/src/lib/api.ts` is the only API client
- `corpus/`: fictional demo documents, loaded into an empty database on API start
- Generated: `web/next-env.d.ts`, `web/AGENTS.md` (written by `next dev`), lockfiles

## Deploy
None: local Docker only (see `docs/sdlc/2026-10-25-v1-rag-eval/intent.md`). Reset data: `docker compose down -v`.

## Things Claude gets wrong
- Stopping the stack (`docker compose down`) after a check, then running tests without the db. Start it with `docker compose up -d db`.
- Running two `uv add` commands at once: the failed one reverts `pyproject.toml`. Run them one after another.
- Text replacements written before `ruff format` silently miss reformatted lines: check that each edit applied.
