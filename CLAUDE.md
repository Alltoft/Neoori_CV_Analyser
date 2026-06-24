# neoori — Module Analyse CV (bêta)

## What this is
French-language CV analysis tool. Candidate uploads CV + 8 context fields → AI returns structured strategic analysis → two exports from one analysis object (candidate full report, counselor synthesis).

## Language rule
- App UI: **French** (all strings, labels, copy)
- Code comments / commit messages: English
- Communication with developer: English

## Stack
- **Next.js 15** (App Router, TypeScript)
- **Tailwind CSS** + design tokens (see below)
- **shadcn/ui** for base components
- **Prisma** + **MySQL** (Aiven for prod / Railway for dev)
- **NextAuth.js v5** — roles: `candidate | counselor | admin`
- **Anthropic SDK** — model `claude-sonnet-4-20250514`, max_tokens ≥ 4000
- **React Hook Form + Zod** for form validation
- **Resend** for email (FR templates)
- PDF export via `@media print` (browser print, not Puppeteer)

## Design tokens (non-final, placeholder)
```css
--accent:   #c96442   /* terracotta */
--ink:      #1d1a17
--ink-2:    rgba(29,26,23,0.55)
--ink-3:    rgba(29,26,23,0.32)
--paper:    #faf7f0
--paper-2:  #f3eee2
--radius-sm: 4px
--radius-md: 8px
--radius-lg: 12px
--font-sans: Inter, system-ui, sans-serif
--font-mono: 'JetBrains Mono', monospace
```
Do NOT use handwritten fonts (Caveat, Patrick Hand, etc.) — wireframes only.

## Selected variants (final)
- Form: **variant A** (single page, FrameFormA)
- Deliverable: **variant C** (A4 report, FrameDeliverableC)

## The 8 form fields (all required)
1. CV — PDF upload (≤10MB) OR pasted text (>200 chars)
2. Cible visée — long text (>50 chars)
3. Prénom — short text
4. Tranche d'âge — select: `< 25` | `25–34` | `35–44` | `45–54` | `55+`
5. Localisation — short text
6. Situation actuelle — select: `en poste` | `en recherche` | `en formation` | `en pause`
7. Type de mobilité — chip select: `évolution` | `reconversion proche` | `reconversion forte` | `première insertion` | `retour à l'emploi`
8. Notes spécifiques — long text (required but can be empty string)

## The 9 analysis sections
| § | Title | Free plan |
|---|---|---|
| 1 | Lecture stratégique du parcours | ✓ |
| 2 | Forces du profil pour la cible | ✓ |
| 3 | Compétences transférables (tag cloud) | ✓ |
| 4 | Ce qui reste à renforcer | ✓ |
| 5 | Préconisations terrain | Paid only |
| 6 | Exemple de réécriture | Paid only |
| 7 | Synthèse | Paid only |
| 8 | Pistes d'évolution | Paid only |
| 9 | Proposition de CV retravaillé | Paid only |

## Counselor view — sections 1, 4, 5 only
- Same analysis object, no regeneration
- Header badge: `VERSION CONSEILLER`
- Key facts strip: Cible visée, Mobilité, Posture actuelle, Points sensibles
- Private counselor notes field (not shared with candidate)
- Public share URL: `/c/[share_token]`

## AI call spec

Two-tier model routing by user plan:

| Plan | Sections generated | Model | max_tokens |
|---|---|---|---|
| free | 1–4 only | `claude-haiku-4-5-20251001` | 8000 |
| paid | 1–9 (full) | `claude-sonnet-4-6` | 8000 |

```
POST https://api.anthropic.com/v1/messages
model: <see table above>
max_tokens: <see table above>
system: <PromptVersion.system_prompt_text>   ← from DB, never hardcoded
user: <concatenation of 8 fields per format in prompt v1.3>
```
- `ANTHROPIC_API_KEY` in env
- Stream the response
- Persist raw response + parsed output
- Counselor code grants paid-tier model access (free for Cap Emploi / France Travail beneficiaries)

## Prompt management (hard requirement)
- Prompt stored in DB table `PromptVersion`, never in code
- Editable from admin dashboard without redeployment
- Full version history with author + timestamp
- Rollback to any prior version
- Every analysis row stores `prompt_version_id` (B2G traceability)

## Paywall
- Free: sections 1–4 (genuinely useful, do NOT aggressively blur)
- Paid: 9 € one-shot, no subscription
- Counselor code → free access (Cap Emploi / France Travail beneficiaries)

## Data model (see README for full schema)
- `User` — id, email, role, plan, credits_remaining
- `Analysis` — id, user_id, prompt_version_id, status, inputs (8 fields), output (9 sections), tokens_in/out, share_token
- `CounselorNote` — analysis_id, counselor_id, body (private)
- `PromptVersion` — version_label, system_prompt_text, author_id, is_active

## UI copy rules (match the prompt tone)
No: boussole, copilote, miroir, révélation, épanouissement, alignement, excellence, talent unique, vous vous démarquez
Yes: factual, sober, professional, direct

## Live deployment (test environment)

All work is developed locally and tested live on the internet. Every push deploys automatically — no manual deploy step needed.

| Service  | URL | Host | Auto-deploy branch |
|---|---|---|---|
| Frontend | https://frontend-seven-fawn-59.vercel.app | Vercel | `initial` (set as production branch in Vercel dashboard) |
| Backend  | https://neoori-cv-analyser.onrender.com | Render | `initial` |
| Database | TiDB Cloud — project `neoori` | TiDB Cloud | — |

### Architecture
Browser → Vercel (Next.js proxy `/api/*`) → Render (Flask/gunicorn) → TiDB Cloud

The Next.js rewrite in `frontend/next.config.ts` proxies all `/api/*` requests to Render. The browser never calls Render directly — all requests are same-origin from the browser's perspective. JWT cookies are `SameSite=Lax` because of this proxy.

### Deploy workflow
```
# local change → live on both services
git add .
git commit -m "..."
git push        # triggers Vercel (frontend) + Render (backend) redeploys simultaneously
```

### Known gotchas
- `BACKEND_URL` on Vercel must be `https://neoori-cv-analyser.onrender.com` (HTTPS, no trailing slash) — baked into Next.js build at compile time, so env changes require a redeploy
- `FRONTEND_URL` on Render must be `https://frontend-seven-fawn-59.vercel.app` (with `https://`) — used by Flask-CORS; missing scheme breaks CORS header matching
- Flask `strict_slashes=False` is set globally — required because Next.js proxy strips trailing slashes before forwarding, and Flask's default 308 redirect to an absolute Render URL leaks through the proxy to the browser

## Out of scope
- Portrait module
- CV-per-job adaptation
- Guided application / personal assistant
