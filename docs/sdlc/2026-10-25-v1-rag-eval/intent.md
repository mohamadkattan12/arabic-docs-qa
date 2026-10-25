# Intent: Arabic document Q&A with evaluation (portfolio project #1)

Author: Mohamad Nour · Source: conversation (LinkedIn KSA job-market research) · Date: 2026-10-25
Status: accepted by Mohamad Nour on 2026-10-25 (open questions resolved: local multilingual embeddings; repo name arabic-docs-qa; Next.js + FastAPI)

## Problem
Mohamad is applying for AI / software engineering jobs in Saudi Arabia. Employers ask for a GitHub
profile, and it has no public project showing the skills the KSA job posts ask for most: LLM apps,
RAG (retrieval-augmented generation), evaluation of AI output, Arabic support, and production-style
engineering. Evidence: of 25 KSA "AI engineer" posts read on 2026-10-25, Python appeared in 19, LLM in 17,
evaluation in 15, agents in 14, RAG in 13 and Arabic in 9.

## Proposed outcome
A public GitHub repo (account `mohamadkattan12`) where a reviewer can:
1. Run `docker compose up` and open a web UI.
2. Ask questions in Arabic or English about a bundled set of fake company policy documents
   (HR, IT, leave, expenses), or upload their own PDFs.
3. Get an answer that cites the exact document and page it came from, or says
   "not found in the documents" instead of making something up.
4. Open an evaluation page / run one command that scores the system on a fixed test set
   (answer correctness, citation correctness, refusal when the answer is not in the documents).
5. Read a README that explains the architecture, design decisions, and evaluation results in about 2 minutes.

## Affected users and systems
- Recruiters and hiring engineers at KSA companies (readers of the repo).
- Mohamad (owner, maintainer).
- New standalone repo: `~/dev/projects/portfolio/arabic-docs-qa`. No existing systems touched.

## Constraints
- LLM: Claude API. API key only via `.env`; never committed. `.env.example` provided.
- Demo documents are generated, fictional company policies. No real company, client or personal data.
  Nothing from Mohamad's employer work (CXOne, WhatsApp, commerce platform) goes in this repo.
- Runs locally with Docker only; no hosted deployment in this cycle.
- Real engineering signals: tests, CI (GitHub Actions), lint, typed code, small meaningful commits.
- Arabic text must display correctly (right-to-left) in the UI.

## Out of scope
- Live hosting / public demo URL (separate later cycle).
- User accounts, multi-tenant, auth.
- Agents / tool calling (that is portfolio project #2).
- Fine-tuning or training models.
- Other LLM providers.

## Success measure
- A fresh clone + `.env` with an API key + `docker compose up` works end to end on a clean machine.
- The evaluation run produces a scored report, and its numbers are in the README.
- CI is green on the main branch.
- Questions whose answer is not in the documents are refused in at least 90% of the out-of-scope test cases.

## Open questions
1. Embeddings: Claude has no embeddings API. Options: a local multilingual model (no key, larger
   Docker image) or Voyage AI (Anthropic's recommended embeddings partner, needs a second key). Decide in spec.
2. Repo name: proposed `arabic-docs-qa`.
3. UI stack: proposed Next.js frontend + Python FastAPI backend (matches the job posts), vs. one simpler Python UI.

## Bug found in verification (2026-10-25)
- **Symptom:** a 10 MB `.txt` upload OOM-killed the API container (exit 137, `OOMKilled=true`).
- **Origin:** `api/src/api/embeddings.py` `embed_passages` used fastembed's default `batch_size=256`.
- **Proof:** batch 256 of chunk-sized passages was OOM-killed; batch 32 peaked at 4.1 GB; batch 8 at 2.2 GB
  (Docker VM 8.3 GB). Embedding runs ~1 s/chunk on CPU, so a 10 MB text (4,459 chunks) could not be
  ingested in one request even without the memory spike.
- **Fix:** batch size 8; documents capped at 150 chunks (413 with a clear message). Regression
  tests: `api/tests/test_embeddings.py`, `test_upload_rejects_documents_longer_than_the_chunk_limit`.
