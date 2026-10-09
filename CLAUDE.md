# neoori — Module Analyse CV (bêta)

## What this is
French-language CV analysis tool. Candidate uploads CV + 8 context fields → AI returns structured strategic analysis → one analysis object, read by the candidate or, through the advisor door, by their counselor (see Les quatre portes).

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
| — | Verdict (free only) | ✓ |
| 4 | Ce qui reste à renforcer | Paid only |
| 5 | Préconisations terrain | Paid only |
| 6 | Exemple de réécriture | Paid only |
| 7 | Synthèse | Paid only |
| 8 | Pistes d'évolution | Paid only |
| 9 | Proposition de CV retravaillé | Paid only |

## Les quatre portes

The parcours 1 form is open to everyone; « Générer mon analyse » leads to four
doors (three once signed in: « Sans compte » is hidden). `services/doors.py`
decides each door's tier and recipient — the browser never chooses a tier, and
`FORCE_ANALYSIS_TIER` is gone. Spec:
`docs/superpowers/specs/2026-10-08-four-doors-design.md`.

| Door | Account | Runs | The report goes to |
|---|---|---|---|
| `account` « Avec mon compte » | required | free (§1–3 + verdict) | the account; 9 € / 24 € unlock as before |
| `promo` « J'ai un code promo » | required | Complet (§1–9) | the account; once per account |
| `advisor` « J'ai un code conseiller » | never asked | Complet (§1–9) | **only** the counselor who owns the code, at `/conseiller/analyses/<id>` |
| `anonymous` « Sans compte » | none | free | a private link `/rapport#<token>`, 30 days |

- **A code's kind is its owner**: none = promo (admin-minted), one = conseiller.
  Uses count per kind — a single-use conseiller code opens one analysis and one
  voyage. The database holds the ceiling (`code_redemptions.slot` + unique
  keys); `code_service.redeem()` commits before the run starts.
- **Who may read an analysis** is `_may_access()` in `routes/analyses.py`:
  advisor rows never on candidate routes; token rows by the `X-Analysis-Token`
  header; owned rows by their owner; `legacy` rows (ownerless, from before
  accounts were required) by id; anything else closed.
- **The counselor's shared view is gone.** An advisor-door report is read on
  the counselor's own page, in full, with one private note per counselor and
  analysis (`GET` / `PUT /api/counselor/analyses/<id>/notes`). `/c/<token>` is
  a static « Ce lien n’est plus actif. » page, `/api/c/*` is deleted, and
  `analyses.share_token` stays as a column nothing mints. The voyage's own
  counselor link (`/voyage/c/…`) is untouched.
- **No token in a URL a server sees.** The report link carries its key in the
  fragment; a signed-out draft is held by the HttpOnly `neoori_hold` cookie.
  Password signup only marks a held row (`pending_user_id`), and only on the
  round trip that held it (`next` exactly
  `/analyse/nouveau?reprendre=compte|promo|brouillon` or `/espace?garder=1`,
  `held.ROUND_TRIPS`): a signup from anywhere else may be a stranger's on a
  shared computer. verify-email with the signup password attaches it; any
  other proof of the address (Google, Microsoft, email link, password reset)
  drops the mark.
- **Caps** read the append-only `run_log`, so deleting a report never lowers
  them: `ANONYMOUS_RUNS_PER_DAY`, `FREE_RUNS_PER_ACCOUNT_PER_DAY`. nginx limits
  the open POSTs per address (`analyses`, `codes` zones).
- **Retention** — `flask purge-expired`, host cron 03:30 (DOCKER.md « Purge »):
  held drafts 48 h, unclaimed no-login reports 30 days, advisor reports 12
  months, `run_log` 2 days.
- **Rolling back below the four-doors migration** needs a backup, then
  `flask purge-expired --before-rollback --apply`, then `flask db downgrade`:
  otherwise advisor reports, unclaimed no-login reports and held drafts become
  plain ownerless rows (belonging to no account) that the previous image
  serves by id. The commands, in order: DOCKER.md, « Rolling back below the
  four-doors migration ».
- Access logs (nginx, gunicorn) record the path only — no query string, no
  Referer; nginx's line also carries the host.

## AI call spec

Two-tier model routing by user plan:

| Plan | Sections generated | Model | max_tokens |
|---|---|---|---|
| free | 1–3 + verdict | `claude-haiku-4-5-20251001` | 8000 |
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
- The tier is the door's (`services/doors.py`); nothing the browser sends selects a model. An unlock re-runs the same report on the tier it sold: Complet for a promo code or the 9 € payment, Premium for the 24 € one.

## Prompt management (hard requirement)
- Prompt stored in DB table `PromptVersion`, never in code
- Editable from admin dashboard without redeployment
- Full version history with author + timestamp
- Rollback to any prior version
- Every analysis row stores `prompt_version_id` (B2G traceability)

## Paywall
- Free: sections 1–3 + verdict (genuinely useful, do NOT aggressively blur)
- Paid: 9 € one-shot, no subscription
- Conseiller code → the advisor door: Complet, sent to the counselor, not the candidate. Promo code → Complet for a signed-in account, once.

## Data model (see README for full schema)
- `User` — id, email, role, plan, credits_remaining
- `Analysis` — id, user_id, prompt_version_id, status, inputs (8 fields), output (9 sections), tokens_in/out, share_token (retired, no longer minted)
- `CounselorNote` — analysis_id, counselor_id, body (private)
- `PromptVersion` — version_label, system_prompt_text, author_id, is_active

## UI copy rules (match the prompt tone)
No: boussole, copilote, miroir, révélation, épanouissement, alignement, excellence, talent unique, vous vous démarquez
Yes: factual, sober, professional, direct

## Live deployment (VPS)

Live at **https://neoori.tech** (the landing), **https://cv.neoori.tech** (« J'ai une cible ») and **https://voyage.neoori.tech** (le voyage); www redirects to the apex. The domain is one setting, `DOMAIN` (see « Sous-domaines »). Everything runs as Docker containers on one Hostinger VPS (KVM 2, Ubuntu 24.04, IP `186.240.157.26`). Full runbook: `DOCKER.md`.

| Container | Role | Image |
|---|---|---|
| nginx | TLS + routing — the only published ports (80/443) | `nginx:1.29-alpine` |
| frontend | Next.js standalone server (:3000) | `ghcr.io/alltoft/neoori-frontend` |
| backend | Flask / gunicorn gthread (:5000) | `ghcr.io/alltoft/neoori-backend` |
| db | MySQL 8.4, internal network only | `mysql:8.4` |

### Architecture
Browser → nginx (`/` → Next.js, `/api/*` → Flask) → MySQL (internal network)

nginx serves both apps on each host, so every page's API calls stay same-origin. The session cookies are `SameSite=Lax` and span the whole domain (`Domain=DOMAIN`): one sign-in for the landing, `cv.` and `voyage.` (« Sous-domaines »).

### Deploy workflow
```
# local change → live on the VPS
git add .
git commit -m "..."
git push        # GitHub Actions: build images → push GHCR → sync config + pull/up on the VPS
```
Rollback on the VPS: `IMAGE_TAG=<commit-sha> docker compose -f docker-compose.prod.yml up -d` — except below the four-doors migration, which needs the purge and a downgrade first (see Les quatre portes).

Local dev mirrors prod routing: `docker compose up -d` → http://neoori.localhost:8080 (the landing), http://cv.neoori.localhost:8080, http://voyage.neoori.localhost:8080 — in Chrome, which resolves `*.localhost` by itself.

### Known gotchas
- `NGINX_MODE` in `/srv/neoori/.env` selects the nginx template: `http` (pre-TLS / ACME / IP smoke tests) or `https`. Now `https` — login only works in that phase, JWT cookies are `Secure`-only in production.
- Flask `strict_slashes=False` stays global — the proxies strip trailing slashes before forwarding.
- The frontend reads `DOMAIN` at request time (`environment:` in both compose files): no site URL is baked into the image. `NEXT_PUBLIC_API_URL`, unset everywhere, is the one build-time value left, and like any `NEXT_PUBLIC_*` value it would need a rebuild.
- The four-doors caps and retentions are optional env settings read in `config.py` (defaults in parentheses): `ANONYMOUS_RUNS_PER_DAY` (200), `FREE_RUNS_PER_ACCOUNT_PER_DAY` (5), `CV_TEXT_MAX` (40000), `CIBLE_MAX` (10000), `ANONYMOUS_RETENTION_DAYS` (30), `ADVISOR_RETENTION_DAYS` (365), `HELD_DRAFT_RETENTION_HOURS` (48), `HELD_DRAFTS_MAX` (2000). `FORCE_ANALYSIS_TIER` no longer exists: a leftover line in `/srv/neoori/.env` does nothing.

## Sous-domaines

One Next.js app, one backend, one database and one sign-in, on three hosts
built from one setting, `DOMAIN` (`/srv/neoori/.env`, read when the containers
start: changing it needs no rebuild).

| Host | Serves |
|---|---|
| `DOMAIN` | today's landing at `/`, nothing else: every other path redirects (307) to the host that serves it |
| `cv.DOMAIN` | « J'ai une cible »: `/analyse/*`, `/rapport`, `/espace`; `/` → `/analyse/nouveau` until its landing exists |
| `voyage.DOMAIN` | le voyage: `/voyage/*`; `/` → `/voyage` |

Every other page — the sign-in pages, `/profil`, `/conseiller`, `/admin`, the
legal pages — is shared: served on cv and voyage, and sent from the root to
cv. The table lives in `frontend/src/lib/site.ts`: **a new page that belongs
to one app needs a row there**, or it is shared. A link that may cross hosts
uses `AppLink`, `useSite().href` or `go()` (`lib/site-context.tsx`).

- **One sign-in.** The session cookies are `neoori_access` / `neoori_refresh`
  with `Domain=DOMAIN` (`config.py`, `app/__init__.py`). The Google/Microsoft
  state, the signup ticket and `neoori_hold` stay on one host: each of their
  round trips starts and ends there.
- **Absolute URLs come from `DOMAIN`, never from the Host header**
  (`backend/app/utils/site.py`). An account mail links to the host it was
  asked from — cv when that is any other name — and every other mail to cv;
  the Google/Microsoft callback is on the host the sign-in started on (both
  are registered with each provider); Stripe returns to cv.
- **No subdomain of `DOMAIN` may be served by anything but this stack** — no
  blog, status page, click-tracking domain, staging copy or CNAME to an
  outside service. It would receive every session cookie, and `SameSite=Lax`
  does not stop a sibling subdomain from sending signed-in requests (CSRF
  protection is off). DOCKER.md, « No subdomain may point anywhere else ».
- `MAIL_FROM` is deliberately separate from `DOMAIN`: Resend silently refuses
  an unverified sender. The order for a domain swap is in DOCKER.md,
  « Swapping the domain later ».

Spec: `docs/superpowers/specs/2026-10-09-subdomain-split-design.md`

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
DOCKER.md's deploy runbook (`DOCKER.md:55-59`) runs the two seed scripts —
not the migration: the production container applies migrations on its own
at startup (`backend/entrypoint.sh:24`). This section is here so a local
database, or a fresh VPS one, is not the first place someone rediscovers
either half.

### What reaches an analysis

`routes/analyses._merge_voyage()` folds the voyage into **`account` and `promo`
runs** (the advisor and anonymous doors fold nothing), beside the Profil de
base fold and independent of it — session 0 requires no profile:

- `inputs["_voyage"]` — up to nine plain-French lines, a line omitted rather
  than left empty. No digit, no trait name, no framework name. Model-facing
  only: no page renders it.
- `inputs["_voyage_id"]` and `Analysis.voyage_id` — which voyage fed which
  analysis, recoverable afterwards. Same discipline as `prompt_version_id`.
- `anthropic_service._voyage_block()` wraps the lines under
  `--- CE QUE LE VOYAGE A RÉVÉLÉ ---` inside `_common_tail()`, which closes
  the analysis message.

Two rules hold this together, and both have tests in
`backend/tests/test_voyage_prompt_context.py`:

1. **Never required.** No voyage → no key, no block, no placeholder. An
   analysis runs identically without one.
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

### The Profil de base is asked inside the voyage

There is no form a person is sent to fill any more. Each block is asked at the
point where they are already engaged enough to answer it, and
`models/voyage.session_lock()` enforces the placement server-side — the same
gate that returns the locked card's French string.

| Where | Block | Enforced by |
|---|---|---|
| Signup | prénom, tranche d'âge | `LOCK_PROFILE` (S1) |
| Hub gate, before S0 | ville, nom, situation | the « Commencer » button |
| `/voyage/etape/parcours` | diplôme, type d'études, intitulé, appétence | `LOCK_PARCOURS` (S2–S5) |
| `/voyage/etape/conditions` | contraintes pratiques, bloc 5 + OETH | `LOCK_CONDITIONS` (S5) |

Each block is demanded by the session **after** the one it follows, so nobody
meets a form before they have played anything and S1 is never held by either.

`/profil` is « Mes informations »: unnumbered, reached from the app bar, and
the place an answer is *changed*, never given for the first time. It also holds
the erasure — `DELETE /api/profile` had existed since the profile shipped with
nothing in the app calling it, so a profile could be read and corrected but not
deleted (RGPD art. 17).

**Bloc 3 (`projet`) is retired.** The analysis form's « cible visée » asks the
same question with the same PDF drop zone, and the two were reaching the model
as two lines saying the same thing. Nothing asks for it now; `_profile_block()`
prints it only for rows that answered it while it was still asked, exactly like
`rayon`. Both columns stay — a populated column is not dropped on a plan's
say-so.

Three rules that are easy to undo by accident:

- **The conditions gate asks that the step was seen, not that anything was
  declared.** Bloc 5 is optional for everyone; `Profile.conditions_seen` is the
  one definition of "seen", and a row with answers but no consent record
  predates the second consent and is taken at its word.
- **Bloc 5 and OETH carry their own consent** (`consent_sensitive_at`), because
  they are GDPR Art. 9 data and the signup CGV does not reach them. The gate
  keys on the *presence* of `conditions` / `oeth` in the payload, never on
  their values — refusing `oeth: true` while accepting `oeth: false` would be
  a reaction to the flag, which is what the OETH invariant forbids. Any client
  that sends one must send both, or neither.
- **`GateProfile` names every field the client mirror reads.** A narrower type
  still compiles — the fields are all optional — and simply makes `sessionLock()`
  treat a block it never fetched as unanswered, locking a session the server
  opens. `frontend/src/app/voyage/session/[n]/page.tsx` shipped that bug once.

`rayon` is retired, not dropped: nothing asks for it, `_profile_block()` prints
it for rows that already carry one, and `/profil` shows it read-only. Age
brackets are seven (`14_17` … `55_plus`); `moins_25` is accepted on write and
never offered.

Spec: `docs/superpowers/plans/2026-09-18-profile-in-voyage.md`, with the open
questions beside it in `…-QUESTIONS.md`.

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

## Email verification

No session for an unproven address. `routes/auth._issue_session()` is the only
place a session (the refresh + access cookie pair) is opened, and it refuses
`email_verified_at IS NULL`; `/auth/refresh` re-mints only the access cookie,
after its own verified + `pwv` checks. Signup and the no-account conseiller
demande mail a link instead. Verifying takes the link **and** the password
chosen at signup — the link alone would let someone who signed up with your
address and their password share your account. « Mot de passe oublié » runs on
the same signed links (`utils/auth_links.py`, itsdangerous, no table); a reset
ends every older session at its next refresh, through the `pwv` claim on
refresh tokens (an access token already issued lives up to 1 h).

- Mail: Resend, From `MAIL_FROM`, links built from `DOMAIN` (`utils/site.py`):
  an account mail names the host it was asked from, every other mail cv. With
  no key in dev the link is printed in the backend log.
- One account mail a minute per address (`users.auth_mail_sent_at`), plus
  per-IP nginx `limit_req` on the auth endpoints.
- The auth rate limits key on the client address, and IPv6 clients reach nginx
  through docker-proxy as one shared address: never publish an AAAA record for
  `neoori.tech`. See `DOCKER.md` (« Do not publish an AAAA record (rate
  limits) »).
- The deploy re-renders and reloads nginx (`deploy.yml`): `up -d` alone never
  applied a template change.
- The analysis form and the CV upload are open (Les quatre portes): `proxy.ts`
  leaves `/analyse`, `/analyse/nouveau` and `/analyse/envoyee` public. The rest
  of `/analyse/` — the report (`/analyse/<id>/rapport`), its unlock page
  (`/analyse/<id>/debloquer`) and the waiting page (`/analyse/en-cours/<id>`) —
  needs the owner, and sends a signed-out visitor to `/inscription`.
- `/admin/utilisateurs` « Marquer comme vérifié » is the way in for a test
  account or a link lost to spam.

Spec: `docs/superpowers/specs/2026-09-29-email-verification-design.md`

## Connexion Google / Microsoft / lien

Three password-less ways in, beside the password signup: « Continuer avec
Google », « Continuer avec Microsoft » and « Recevoir un lien de connexion ».
All three end in `routes/auth._issue_session()`.

- **No provider script on our pages.** A provider button is a plain link to
  `/api/auth/<provider>/start`. Flask runs the authorization-code round trip
  with Authlib (`services/oauth_clients.py`, `routes/auth_oauth.py`). The
  checks are state + PKCE + nonce, and on the ID token `iss`, `aud` and `exp`.
  One Tap or a hosted widget would bring a CNIL consent banner with it.
- **No `users` row before the CGV consent.** An unknown identity, or a link
  for an address with no account, gets a signed `signup_ticket` cookie (30
  min, `Path=/api/auth`) and lands on `/inscription/finaliser`. The account,
  its identity and its consent are created there in one commit. Nothing needs
  a consent gate because nothing exists before it.
- **An address is believed only when the provider proves it**
  (`services/sign_in.trusted_email`). Google: `email_verified`. Microsoft: the
  personal-account tenant, or `xms_edov`. A work tenant's `email` claim can be
  any address its admin types (nOAuth). Without that proof, and with no
  identity already linked, a sign-in enters nothing and creates nothing.
  `xms_edov` is added in the Entra app's manifest; the portal no longer lists
  it.
- **Addresses are ASCII, and an account is entered only under its own
  address.** `email_shape_ok` refuses non-ASCII addresses, and
  `sign_in.account_of` compares the stored address after normalising it.
  MySQL's `utf8mb4_unicode_ci` treats « gmaïl » as « gmail », and the email
  link is mailed to the address as typed. Without those two checks a
  lookalike registration could catch the real owner's sign-in. An address
  the database files only under a lookalike account is refused: the
  callback redirects with `email_non_verifie`, and the link consume and the
  finalise step answer 409 `address_unavailable`.
- **The ID token's `sub` is screened before anything is written.** It must
  be ASCII, non-empty and at most 255 characters, because `resolve_oauth`
  commits identity links. The callback also checks `aud` and the issuer
  itself. Authlib checks `aud` only when told to, and Microsoft's `iss`
  must name the token's own `tid`.
- **Entering an unverified account replaces its password** with an unusable
  hash, since a stranger may have set it. Password-less accounts carry such a
  hash too: every typed password fails like a wrong one, and « Mot de passe
  oublié » sets a real one.
- **The email link is spent by a click, never by opening the page.** Mail
  scanners open links. `/connexion/lien` checks the token on load and consumes
  it only on « Continuer ». `login_links` makes it single-use and keeps an
  HMAC of the address, never the address.
- **Keys.** `GOOGLE_CLIENT_ID/SECRET` and `MICROSOFT_CLIENT_ID/SECRET` live in
  `/srv/neoori/.env`. A provider's button shows only once both its keys are
  set (`GET /api/auth/providers`). The Microsoft secret expires: see DOCKER.md,
  « Google / Microsoft sign-in keys ».

Spec: `docs/superpowers/specs/2026-10-03-social-login-design.md`

## Mails transactionnels

Every mail is built in `services/email_service.py`, leaves after the commit
that decided it, and is fail-soft: a Resend failure logs and returns False —
never a 500, never a rolled-back write. A mail says that something happened,
never what a report or a voyage contains, and nothing about a conseiller
applicant. The one free text a mail carries is an admin's reason, on the
rejection and revocation mails — already shown to the conseiller on
`/conseiller`. The analysis, demande and approval mails link to a page behind
a login; the account mails link to their `(auth)` pages; the unlock-failure,
rejection and revocation mails carry no link. HTML and plain text come from
one paragraph list (`_mail`), so a wording edit reaches both — except the
approval and rejection mails, which predate it and are HTML-only.

| Mail | To | Sent by |
|---|---|---|
| Confirmez votre adresse | the account | signup, conseiller demande, resend — `services/auth_mail.py` |
| Réinitialiser votre mot de passe | the account | « mot de passe oublié » — `services/auth_mail.py` |
| Votre lien de connexion | the address typed, account or not | « Recevoir un lien de connexion » — `services/auth_mail.login_link_if_due` |
| Votre mot de passe a été modifié | the account | `auth.reset_password`, after its commit |
| Votre analyse est prête / n'a pas abouti | the analysis owner, verified only | `anthropic_service._notify_outcome`, at every final status `_run_analysis` writes |
| Une analyse est prête / n’a pas abouti (conseiller) | the counselor who owns the code, verified only | `anthropic_service._notify_outcome`, advisor-door runs |
| Nouvelle demande de compte conseiller | the addresses in `ADMIN_NOTIFY_EMAIL`; every verified admin when it is unset | `services/demande_mail.notify_if_visible` |
| Compte activé / demande non retenue / accès retiré | the conseiller | `admin` approve / reject / revoke |

- **The analysis mail goes out on every run `_run_analysis` finishes, watched
  or not.** That is what lets the waiting page say « vous pouvez fermer cette
  page », and why its 10-minute give-up reads « C’est plus long que prévu »,
  not an error. A no-login report has no address to mail, so its waiting page
  promises none (« Gardez ce lien : le rapport s’affichera ici dès qu’il sera
  prêt. »). A run orphaned by a restart is not one of them:
  `reap_stale_running` (`app/__init__.py`) marks it `error` at startup and
  sends nothing — but it only takes runs older than `STALE_RUN_CUTOFF_MINUTES`
  (15), and a run a deploy orphans is a minute or two old when the new
  container boots. So `reap_if_orphaned()` (same module, same cutoff, same
  `started_at` clock) applies the rule to the one row a read is about to
  serve — `GET /api/analyses/<id>`, `GET /api/analyses/by-token`,
  `GET /api/counselor/analyses/<id>` — once it passes the cutoff: `running`
  rows only, never `queued`; it sets `error` and sends no mail. The list
  endpoints still show such a run as `running` until its row is opened.
- **The run an unlock starts (`unlock_method` set) has its own wording.** When
  it fails, the unlock is still a dead end — a second unlock is a 409 — so the
  mail asks the candidate to reply, with the analysis id. Relaunching it is
  manual.
- **The admin mail fires when a demande enters the queue**: a signed-in
  applicant applies, or an applicant's address is proven for the first time,
  by its verification link, by a reset link, or by a Google / Microsoft /
  email-link sign-in (`sign_in.enter`). Admin « Marquer comme vérifié »
  does not send it. Production sets `ADMIN_NOTIFY_EMAIL` in
  `/srv/neoori/.env` (comma-separated; today `ouakouriimran@gmail.com`): the
  shared admin login, `admin@neoori.dev`, has no mailbox — neoori.dev has no
  MX record — so every copy sent there would bounce. A new recipient is an
  `.env` edit plus a redeploy, not a new admin account.
- Resend's free plan is 100 mails a day, shared by every mail above.

Spec: `docs/superpowers/specs/2026-10-02-transactional-mails-design.md`

## Out of scope
- Portrait module
- CV-per-job adaptation
- Guided application / personal assistant
