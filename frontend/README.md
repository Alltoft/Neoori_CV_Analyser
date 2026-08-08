# neoori — frontend

Next.js 16 (App Router, TypeScript, Tailwind 4). French-only UI — see the root
`CLAUDE.md` for copy rules and `AGENTS.md` here before writing any Next.js code.

## Run

```bash
# full stack (recommended): from the repo root
docker compose up -d          # http://localhost:8080

# frontend alone (needs the backend running on :5001)
npm run dev                   # http://localhost:3001
```

Production image: `frontend/Dockerfile` (standalone output), built by CI —
deployment runbook in the root `DOCKER.md`.
