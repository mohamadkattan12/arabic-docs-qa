# Review instructions

## Passes
Run three passes and tag each finding with its pass:
- Bugs: logic errors, broken edge cases (empty retrieval, NOT_FOUND streaming, refusals,
  max_tokens), Arabic/RTL handling, regressions in citation mapping
- Security: SQL built from strings, secrets or document text in logs, HTML rendered from model or
  document text, upload validation (type, size, filename), CORS, prompt-injection handling
- Compliance: the change matches docs/sdlc/<change>/spec.md and plan.md, and CLAUDE.md
  conventions; plan departures not recorded in plan.md are findings; eval metrics or the
  recommendation rule changed without a spec amendment is Important

## What Important means here
Important = would break behavior, leak data or secrets, spend API money unexpectedly, or make
an eval number wrong. Style and naming are nits.

## Cap the nits
Report at most five nits per review; summarize the rest as a count.

## Do not report
Lockfiles (`api/uv.lock`, `web/pnpm-lock.yaml`), `web/next-env.d.ts`, `web/AGENTS.md`,
`api/eval/results/*`, shadcn components in `web/src/components/ui/`, and anything CI enforces
(ruff, ruff format, mypy, ESLint, tsc).
