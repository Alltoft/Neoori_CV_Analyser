# neoori — frontend

Next.js 16 (App Router, TypeScript, Tailwind 4). French-only UI — see the root
`CLAUDE.md` for copy rules and `AGENTS.md` here before writing any Next.js code.

## Run

```bash
# full stack (recommended): from the repo root
docker compose up -d          # http://neoori.localhost:8080 (+ cv. and voyage.)

# frontend alone (needs the backend running on :5001), then open
# http://cv.localhost:3001 (or voyage.localhost:3001) in Chrome
DOMAIN=localhost PUBLIC_SCHEME=http PUBLIC_PORT=3001 npm run dev
```

Production image: `frontend/Dockerfile` (standalone output), built by CI —
deployment runbook in the root `DOCKER.md`.
