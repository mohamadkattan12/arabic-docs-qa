# Web app

The Next.js front end of [Arabic Docs Q&A](../README.md). Run the whole project with Docker
Compose from the repo root, as the root README describes; this app needs the API next to it.

```bash
pnpm install
pnpm dev        # http://localhost:3000, expects the API on http://localhost:8000
pnpm lint && pnpm typecheck && pnpm test && pnpm build
```

It is a local-only demo with no authentication. Do not deploy it publicly as-is.
