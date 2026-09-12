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
- **Flask-SQLAlchemy** + **MySQL 8.4** (Docker container on the VPS)
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

## Live deployment (VPS)

Live at **https://neoori.tech** (www redirects to the apex). Everything runs as Docker containers on one Hostinger VPS (KVM 2, Ubuntu 24.04, IP `186.240.157.26`). Full runbook: `DOCKER.md`.

| Container | Role | Image |
|---|---|---|
| nginx | TLS + routing — the only published ports (80/443) | `nginx:1.29-alpine` |
| frontend | Next.js standalone server (:3000) | `ghcr.io/alltoft/neoori-frontend` |
| backend | Flask / gunicorn gthread (:5000) | `ghcr.io/alltoft/neoori-backend` |
| db | MySQL 8.4, internal network only | `mysql:8.4` |

### Architecture
Browser → nginx (`/` → Next.js, `/api/*` → Flask) → MySQL (internal network)

nginx serves both apps from one origin, so everything stays same-origin from the browser's perspective. JWT cookies are `SameSite=Lax` because of this.

### Deploy workflow
```
# local change → live on the VPS
git add .
git commit -m "..."
git push        # GitHub Actions: build images → push GHCR → sync config + pull/up on the VPS
```
Rollback on the VPS: `IMAGE_TAG=<commit-sha> docker compose -f docker-compose.prod.yml up -d`

Local dev mirrors prod routing: `docker compose up -d` → http://localhost:8080

### Known gotchas
- `NGINX_MODE` in `/srv/neoori/.env` selects the nginx template: `http` (pre-TLS / ACME / IP smoke tests) or `https`. Now `https` — login only works in that phase, JWT cookies are `Secure`-only in production.
- Flask `strict_slashes=False` stays global — the proxies strip trailing slashes before forwarding.
- Frontend `NEXT_PUBLIC_*` values are baked at image build time (CI build-args), not read from VPS runtime env.
- The legacy Vercel/Render/TiDB test env keeps serving its last deploy until cutover — data migration steps in `DOCKER.md`.

## Le voyage

Six sessions (S0–S5) digitised from the PM's paper cahier and its counselor
scoring manual. Session 0 is five minutes and self-serve; sessions 1–5 need a
counselor code. Scoring is arithmetic in Python — no model call — and **the
candidate never sees a score or a trait name**. The one surface that may show
that vocabulary is the counselor's own, `/voyage/c/<token>`, gated to the
counselor (and admin) role.

- Route `/voyage`, API `/api/voyage`, tables `voyages` / `voyage_notes`
- Answers, phrase and portrait are Fernet-encrypted at rest, same util as bloc 5
- Two prompt slots in `PromptVersion.path`: `voyage_micro`, `voyage_portrait`
- Spec: `docs/superpowers/specs/2026-09-09-voyage-design.md`
- Contracts (names, types, shapes): `docs/superpowers/plans/2026-09-09-voyage-contracts.md`

### A fresh database needs the migration *and* two seed scripts

Skipping either half fails differently, and the two are easy to mix up when
debugging under pressure:

- **Missing migrations** — every `/api/voyage` and `/api/analyses/` call
  500s: `Unknown column 'analyses.voyage_id'`, `Table 'neoori.voyages'
  doesn't exist`. Neither surface can run at all without the schema.
- **Missing seeds** — the schema is fine, so session 0 completes, but the
  phrase fails with « Aucun prompt actif pour le slot voyage_micro » (now
  retryable), because neither prompt slot above has a row until it is
  seeded. The portrait fails the same way, for the same reason.

This bit us on 2026-09-12, probing a migrated-but-unseeded database. Both
steps stay mandatory. From `backend/`:

```
flask db upgrade
python seed_prompt_v10_voyage_micro.py
python seed_prompt_v10_voyage_portrait.py
```

Both scripts are idempotent — re-running does not duplicate a version.
DOCKER.md's deploy runbook (`DOCKER.md:55-60`) runs the two seed scripts —
not the migration: the production container applies migrations on its own
at startup (`backend/entrypoint.sh:24`). This section is here so a local
database, or a fresh VPS one, is not the first place someone rediscovers
either half.

### What reaches an analysis

`routes/analyses._merge_voyage()` folds the voyage into every new analysis,
beside the Profil de base fold and independent of it — session 0 requires no
profile:

- `inputs["_voyage"]` — up to nine plain-French lines, a line omitted rather
  than left empty. No digit, no trait name, no framework name. Model-facing
  only: no page renders it.
- `inputs["_voyage_id"]` and `Analysis.voyage_id` — which voyage fed which
  analysis, recoverable afterwards. Same discipline as `prompt_version_id`.
- `anthropic_service._voyage_block()` wraps the lines under
  `--- CE QUE LE VOYAGE A RÉVÉLÉ ---` inside `_common_tail()`, so all three
  parcours carry it from one place.

Two rules hold this together, and both have tests in
`backend/tests/test_voyage_prompt_context.py`:

1. **Never required.** No voyage → no key, no block, no placeholder. Every
   parcours runs identically without one.
2. **The stage rule.** Until `portrait_status == "validated"`, an analysis
   receives only session 0's phrase and its three attractions. The full
   reduction travels only after a counselor validates — an analysis must never
   perform a restitution the counselor has not given yet.

The reduction is computed once, at merge time, and stored on the row. Unlocking
an analysis regenerates it from the same lines the first run sent, so a report
already delivered is never rewritten by a later validation.

`--- CE QUE LE VOYAGE A RÉVÉLÉ ---` and « Phrase révélée » share a root with the
banned « révélation ». They are model-facing prompt text, not UI chrome, and the
ban list does not reach them. It does reach every page: the hub says « Votre
phrase », never « Votre révélation ».

### Erasing a voyage erases what it copied, too

`DELETE /api/voyage` (RGPD erasure) does not stop at the voyage row. Before
deleting it, the route strips `_voyage` and `_voyage_id` out of `inputs` on
every past analysis that carried them. PM ruling, 2026-09-12: a person
erasing their voyage must not leave its reduced lines sitting in plaintext on
old reports, pointing at an id that no longer resolves to anything. The
analysis text already delivered (`Analysis.output`) is untouched — only the
copied voyage inputs go.

### Le voyage is not le portrait

**Do not touch these four lines.** Le portrait (Parcours doc §8) is the paid
synthesis of CV + form + voyage. It is still unbuilt, so it stays out of scope:

- `README.md:7` — the "second module (Portrait …) is out of scope" paragraph
- `README.md:43` — `| Portrait module | Out of scope |`
- `plan.md:248` — the out-of-scope paragraph of the CDC v1.2 build. It also
  names « Le voyage », because that was true of *that* build; it is a snapshot
  of a finished scope, not a live statement about this one.
- `CLAUDE.md`'s own `## Out of scope` below — `- Portrait module` stays

The six-section text a counselor validates *inside* a voyage is also called a
portrait (`portrait_status`, `/voyage/portrait`). Same French word, different
object. Deleting an out-of-scope line because "the portrait is built now" would
be deleting the wrong one.

## Out of scope
- Portrait module
- CV-per-job adaptation
- Guided application / personal assistant
