# neoori — CDC v1.2 / Parcours implementation plan

## Context

Two spec documents landed on 2026-07-26: `neoori_cahier_des_charges_v1_2.pdf` (product spec) and `Parcours_neoori-1.pdf` (user journey). On 2026-07-29 the PM resolved the five blocking questions, and the developer decided to implement the whole delta rather than piecemeal.

The shipped app is a **2-path** analyzer: Chemin A (`/analyse/nouveau`, CV + target, sections §1–§9, free = §1–4) and Chemin B (`/analyse/orientation`, chip-select questionnaire with `b1/b2/b3` sub-profiles, sections §1,2,3,8,9). Two tiers, Stripe 9 € unlock, counselor codes, DB-backed prompt versioning, print-CSS PDF.

The specs replace this with a **3-parcours** model on top of a shared 6-block persistent profile, add a third paid tier, and add OETH/RGPD handling with a two-speed storage model. Nothing is in production — the Vercel + Render URLs are the PM's test environment, so each phase deploys as it lands.

### Decisions locked (do not re-litigate)

| # | Decision | Source |
|---|---|---|
| 1 | `Parcours_neoori-1.pdf` is authoritative; the CDC's common form is a historical subset | PM |
| 2 | Persistent account + profile. **Two-speed storage:** profile erasable under consent; bloc 5 + OETH stored separately, encrypted, excluded from logs and PDFs | PM (B2G: Appuis Spécifiques, Aide 18, Emploi Accompagné) |
| 3 | Type de mobilité merges into "Situation actuelle"; tranche d'âge returns in bloc 1 as brackets (routes Académie des Ori + P3 youth schemes) | PM |
| 4 | P2 questionnaire = **3** questions, not 4 | Parcours doc simplification |
| 5 | Chemin B = framing note only, **no web search** at launch | PM |
| 6 | Bloc 5 offered to everyone, optional to fill | Parcours §11 recommendation |
| 7 | Model routing: free→`claude-haiku-4-5`, paid→`claude-sonnet-5`, premium→`claude-opus-5` | developer |
| 8 | Incremental pushes to `initial`; PM validates each phase on the live URL | developer |
| 9 | Premium price configurable (env + admin), not hardcoded — PM calibrates on first buyers at 2–3× the 9 € tier | PM |

### Assumption requiring a flag, not a blocker

**Anonymous analyses end.** Today `Analysis.user_id` is nullable, `POST /analyses/` needs no auth, and the whole flow works logged-out. A reusable Profil de base is meaningless without an account, so Phase 1 makes registration a precondition. The alternative — guest analysis that upgrades into an account — is more work and neither doc asks for it. Building the required-account model; will flag to the PM when Phase 1 deploys.

---

## Phase 0 — data foundation

Nothing user-visible. Everything downstream sits on this.

### 0.1 Section registry (kills the hardcoded `"1".."9"` model)

The single highest-risk item. `frontend/src/app/analyse/[id]/rapport/page.tsx:62` sorts with `Number(a) - Number(b)`; for `"A"` or `"IV"` that is `NaN - NaN`, the comparator never orders anything, and V8 silently falls back to insertion order. And `backend/app/services/anthropic_service.py` `_parse_output` gates JSON validity on `any(k.isdigit() for k in result)` — letter-keyed output fails the check and collapses into the single-section last-resort shape. Both fail quietly.

New `backend/app/services/section_registry.py` — one authoritative structure:

```python
PARCOURS = {
  "1": {"label": "J'ai une cible",
        "sections": [{"key": "1", "title": "...", "render": "markdown", "tiers": ("free","paid","premium")}, ...],
        "counselor": ("1", "4", "5")},
  "2": {... keys "A".."G" ...},
  "3": {... keys "I".."VI" ...},
}
```

- List position **is** the order — no sorting anywhere, ever again.
- `render: "markdown" | "tags"` replaces the literal `n === "3"` branch in `components/report/ReportSection.tsx:82`.
- `tiers` replaces `FREE_SECTIONS` / `PAID_SECTIONS` and the `_HAIKU_SECTION_NOTE` French prose glued onto the user turn (`anthropic_service.py:16-19`) — the JSON schema alone enforces the tier's section set.
- Rewrite `_section_keys`, `_build_output_schema`, `_SECTION_TITLES_A/_B` against it. Keep `_build_output_schema`'s `additionalProperties: False` and the `extra_body` structured-output shim (it exists because `anthropic` is pinned as `>=0.40.0`).
- `_MD_SECTION_RE` (`:200-203`) capture group `(\d)` → `([0-9A-G]|[IVX]+)`; the markdown fallback currently titles path-B sections from `_SECTION_TITLES_A` (`:225`) — resolve titles through the registry instead.
- `_parse_output`'s digit test (`:240`) → membership in the parcours' key set.

`Analysis.to_dict()` gains `sections_meta: [{key, title, render, tier}]` in registry order. The report page maps that array directly — the backend owns ordering, and the long-standing bug where B reports render A-path titles disappears with it.

**Consolidate the dead constants.** `FREE_SECTIONS`, `COUNSELOR_SECTIONS`, `COUNSELOR_SECTIONS_B` in `frontend/src/types/index.ts:101-117` are exported but never imported — the real values are copy-pasted inline in `rapport/page.tsx:61,64`, `debloquer/page.tsx:18-19`, and `c/[token]/page.tsx:59`. All four call sites consume `sections_meta`.

### 0.2 Parcours identity replaces the A/B duality

`PromptVersion.path` is `db.String(1)` — `'1'`, `'2'`, `'3'` fit, so **no width migration**, only a data migration (`A→1`, `B→3`). Then:

- `backend/app/routes/prompts.py:23,46` — two separate `path not in ("A","B")` checks.
- `prompts.py:54` — duplicate `version_label` check is **global, not path-scoped**, so `v1.7` can only ever exist for one parcours. Scope it to `(version_label, path)`.
- `backend/app/routes/admin.py:33` — `filter_by(is_active=True).first()` with no path filter returns whichever row comes first. Existing bug; fix while here.
- `admin/prompts/page.tsx` — `type Path = "A"|"B"` (`:23`), `PATH_HELP` (`:25-28`), the two-element `.map` (`:182`), the label-suffix logic (`:75-82`, `-B` suffix + `/-[AB]$/` regex — note A is asymmetric with no suffix), and the two-path prose callout (`:200-208`). Give all three parcours an explicit suffix and migrate legacy labels, rather than keeping the asymmetry.
- Retire `SubProfile = "b1"|"b2"|"b3"` and both `_format_user_message_b` sub-branches. B3 becomes a declarative flag, orthogonal to parcours — never a routing choice, per CDC §3.3.

### 0.3 Persistent profile + two-speed encrypted storage

`cryptography==43.0.3` is already installed (a PyMySQL dependency), so `Fernet`/`MultiFernet` costs **zero new dependencies**. There is no crypto helper in the codebase today — a grep for `fernet|encrypt|kms|nacl` returns nothing outside bcrypt and `secrets.choice`.

- `app/utils/crypto.py` — `MultiFernet` over `FIELD_ENCRYPTION_KEYS` (comma-separated, first key encrypts) so rotation is possible from day one. Add to `Config`.
- New `Profile` table — the 6 blocks minus the sensitive ones, plaintext, one row per user, erasable under consent.
- New `SensitiveProfile` table — **separate table, ciphertext columns**, holding bloc 5 and the OETH flag. This is what "stockés à part, chiffrés, hors des logs" means structurally. Never enters `to_dict()`, never enters `Analysis.inputs`, never reaches a PDF. Decrypted in-process only to compose the AI prompt.
- `Analysis.inputs` keeps a **reference** to the profile, not a copy of it. Today every client-supplied key lands in that JSON blob verbatim and is echoed back by `to_dict()`.

### 0.4 Third tier

- `User.plan` enum `free|paid` → `+premium`. Native MySQL ENUM, so an explicit `ALTER TABLE ... MODIFY COLUMN` migration.
- `_select_model_by_tier` (`anthropic_service.py:30-33`) is a two-branch string test returning a vestigial fixed `8000`. Rewrite as a `{tier: (model, max_tokens)}` map. **Opus 5 needs `max_tokens` ≥ 16000** — thinking is on by default and counts against the cap, so 8000 truncates mid-report.
- The tier discriminator lives in `Analysis.inputs["_tier"]` as an untyped JSON key with no constraint. `admin.py:203` aggregates all cost/timeseries data through `Analysis.inputs["_tier"].as_string()`. Promote `_tier` to a real indexed column and update both aggregation queries plus `tests/test_admin.py`.
- `admin.py:194-203` hardcodes two price pairs and `_USD_TO_EUR = 0.92`. Make it a three-entry table; the FX rate stays a constant but moves next to it.
- `frontend/src/app/admin/couts/page.tsx:27-29,84-103,155-166` mirrors the two-model split throughout.

### 0.5 Security fixes that Phase 0 makes mandatory

`GET /api/analyses/<id>` has **no auth** and returns the raw `inputs` blob — CV text, name, location, and today the B3 health context. Once bloc 5 and OETH exist, leaving it open is indefensible. Require JWT + ownership (clean, once accounts are required). Same file: `DELETE /analyses/<id>` currently allows anyone to delete any analysis whose `user_id` is null.

Also worth doing while the file is open: `POST /analyses/<id>/unlock` is unauthenticated with no rate limit and no per-code usage cap, against an 8-char `[A-Z0-9]` code space.

### 0.6 Migration conventions

Chain head is `b2c3d4e5f6a7`. Recent migrations use hand-written sequential revision ids (`a1b2c3d4e5f6` → `b2c3d4e5f6a7`), so continue with `c3d4e5f6a7b8`. Adding a NOT NULL column to a populated table follows `a1b2c3d4e5f6`: explicit `server_default`, mirrored in the model. Every migration implements a real `downgrade()`. `Procfile` runs `flask db upgrade` before gunicorn, so migrations auto-apply on push.

**Tests never run migrations** — `conftest.py` uses `db.create_all()`, so model/migration drift is invisible to CI. Worth a smoke test that runs the chain against SQLite, except `fd6e96d0d77c` is MySQL-specific raw SQL. Note it; don't solve it in this plan.

**Files:** `backend/app/services/section_registry.py` (new), `app/services/anthropic_service.py`, `app/models/{analysis,user,prompt_version,profile}.py`, `app/routes/{analyses,prompts,admin}.py`, `app/utils/crypto.py` (new), `migrations/versions/c3d4e5f6a7b8_*.py`, `frontend/src/types/index.ts`, `frontend/src/app/admin/{prompts,couts}/page.tsx`.

---

## Phase 1 — Profil de base (6 blocks)

Follow the `analyse/nouveau/page.tsx` pattern (React Hook Form + Zod, module-scope schema, `useForm({resolver: zodResolver(schema)})`), **not** `orientation/page.tsx` (plain `useState`). Promote the file-private `SectionCard({n, title, hint, children})` at `nouveau/page.tsx:46` to `components/ui/section-card.tsx` — six blocks need it and it is currently duplicated in spirit across both forms.

| Block | Content | Notes |
|---|---|---|
| 1 · Vous | Prénom + NOM (uppercased) · ville + **rayon** (ma ville / 30 km / région / toute la France) · **tranche d'âge** | Radius is new; age returns per PM |
| 2 · Situation | 5 options with **mobilité merged in**; if *reconversion* → sub-question (rester dans mon domaine / changer de métier / changer de secteur) | The 5-chip `type_mobilite` field is retired |
| 3 · Projet | Free text + optional upload of a job ad / fiche de poste / fiche métier | `POST /upload/projet` already exists |
| 4 · Contraintes pratiques | Free text + warning: no health info, no diagnosis, no treatment — describe the effect on work only | Free-text mention of an adaptation need triggers the B3 *functional* level (CDC §3.3 level 2) |
| 5 · Conditions de travail | 8 families × 3 states + separate "C'est un point fort" checkbox | **Encrypted, separate table.** Optional per decision 6 |
| 6 · Droits et accord | OETH checkbox + explainer · mandatory RGPD consent, submit disabled until checked | **OETH must trigger nothing visible.** See below |

### The 8 × 3 matrix

`components/ui` has **no** `checkbox.tsx`, `radio-group.tsx`, or `form.tsx`. The codebase currently does radios/checkboxes three different ways: native `<input className="accent-orange">`, a `role="checkbox"` `Chip` button (orientation), and `<button aria-pressed>` pills (nouveau). `@base-ui/react@1.4.1` is already installed and ships `radio-group`, `checkbox`, and `field`; `components.json` is configured (`style: base-nova`). Add the shadcn components rather than hand-rolling a fourth variant.

Shape: one `<Controller>` holding `Record<familyKey, "convient" | "adaptation" | "eviter">` plus a parallel `Record<familyKey, boolean>` for *point fort*. Desktop uses the existing `components/ui/table.tsx` primitives; collapse to stacked cards on mobile (the repo's idiom is `grid-cols-1 sm:grid-cols-[1.2fr_1fr]`).

Encode the report rule in the registry, not the UI: *"me convient" is never a strength.* Only a **point fort on a painful requirement** (noise, outdoors, night, load, seasonality) is a differentiator worth valorizing.

### OETH — the rule that constrains the implementation

Ticking the box must change **nothing observable**: no new field, no re-layout, no extra request, no altered validation, no visible latency. If the interface reacts, the person learns they just flagged themselves and the equal-treatment promise collapses. Practically: the checkbox writes to form state only; the effect appears solely in the generated report (institutional insert, §11 sub-module B). Worth an explicit test.

### Live synthesis

A panel that builds under the user's eyes as they fill: *vos points forts / ce qui vous convient / possible avec adaptation / à éviter*. Pure client-side derivation from `watch()` — no API call, no server round-trip. The Parcours doc calls this the tipping point toward paying.

### Zod / Flask duplication

The Zod schema and `_validate_inputs` in `backend/app/routes/analyses.py:159-208` are duplicated by hand today, with no schema library on the backend (no marshmallow, no pydantic). Six blocks make that worse. Keep the hand-rolled validators to match the existing style, but derive both from one field list so they can't drift silently.

**Files:** `frontend/src/app/profil/page.tsx` (new), `components/ui/{section-card,radio-group,checkbox}.tsx`, `components/profil/{ConditionsMatrix,LiveSynthesis}.tsx` (new), `frontend/src/types/index.ts`, `backend/app/routes/profile.py` (new), `backend/app/models/profile.py`.

---

## Phase 2 — the three parcours

### 2.1 Entry

`/analyse/orientation` has **zero inbound links** — every CTA on the landing, nav, footer, AppBar, and espace points at `/analyse/nouveau`. The second parcours is already orphaned before a third exists.

Add a 3-card chooser as a new landing section between the hero and `#module`, reusing the `PERSONAS` grid structure at `page.tsx:277-308` (3-column, `<Reveal delayMs={i*90}>`, photo + icon chip + title + arrow). Route each card to `/analyse/[parcours]`. Keep `/analyse/nouveau` as a redirect to the chooser so the ~15 existing CTAs (`page.tsx` ×5, `SiteNav:45,79`, `SiteFooter:12`, `AppBar:32`, `espace` ×5) keep working without a mass rewrite.

### 2.2 The three forms

| Parcours | Input | Report | Paid extra |
|---|---|---|---|
| **1 · J'ai une cible** | CV mandatory (PDF ≤5 MB or paste) + Chemin A (paste the job ad) or Chemin B (describe, min 20 chars) | §1–§9 | 2 PDFs, counselor-referral button |
| **2 · Je cherche ma direction** | CV (PDF / text / raw experience list) + **3** free-text questions | §A–§G | Generic proto-CV, no job title |
| **3 · Je pars de zéro** | No CV; **5** life questions | §I–§VI | CV draft from declared life experience |

Chemin B adds a framing note at the top of the report — *"analyse fondée sur le métier X d'après votre description"* — and no lookup.

Retire `b1/b2/b3` entirely. The multi-step machinery in `orientation/page.tsx:160-182` (`step`/`totalSteps`/`canNext()`, all steps mounted as sibling `{step === N && ...}` blocks) is sound and worth lifting for P2/P3.

### 2.3 Counselor view

`backend/app/models/analysis.py:62-64` filters to `("1","4","5")` **regardless of path**, while `c/[token]/page.tsx:59` asks for `["1","2","8"]` on path B. The B counselor view therefore renders three empty skeletons today — a live bug. Drive the filter from `registry[parcours]["counselor"]`.

### 2.4 Paywall sentinel

`"5" in output` is the canonical "is unlocked" test in three places (`unlock_service.py:24`, `payments.py:60`, `rapport/page.tsx:58`). Meaningless for §A–§G and §I–§VI. Replace with `analysis.unlock_method is not None` — a real column that already exists.

Note that unlocking is a **full regeneration**, not a reveal: `unlock_service` flips `_tier`, requeues, and overwrites `output`/`raw_output`. That behavior is intentional and stays.

---

## Phase 3 — tiers and monetization

- **Premium tier** — Stripe price from config (decision 9), `plan` enum extended in Phase 0. `payments.py` currently hardcodes `PRICE_EUR_CENTS = 900` and builds an inline `price_data` Checkout Session with no Stripe Price object; extend to a per-tier lookup. Preserve the two stripe-v15 workarounds (bracket access, `.to_dict()`) — `tests/test_unlock.py::test_webhook_unlocks_on_real_stripe_object` guards them.
- **§10 interview prep** — 5 likely questions with answers + CV/offer correspondence table.
- **§11 difficult questions** — sub-module A (CV gaps by nature: health / financial / parenting / sabbatical, each with the probable recruiter question, what labor law says, recommended phrasing, phrasing to avoid), B (RQTH/disability framing + the timing rule: never in a first interview if the disability isn't visible; raise at offer stage), C (negotiation: anchor / floor / BATNA, part-time, adaptation needs).
- **Free-tier "verdict de diagnostic"** — quantifies the frictions without naming them.
- **Willingness-to-pay probe** after the free report — *"Ce diagnostic vous a-t-il été utile ? … moins de 5 € · 5 à 10 € · 10 à 20 € · plus de 20 € · je ne paierais pas."* New table, admin readout. Treat as a hierarchy signal, not a price.
- **Counselor referral within 48 h** button on the paid tier.

---

## Phase 4 — output and compliance

### 4.1 PDF charter

The charter values are `#EA5624` / `#1C3561` / `#2E8B6E` / `#F0F7F4`, Carlito 9.5 pt body / 11 pt titles. Current `globals.css` ships `--orange: #ff7a39`, `--navy: #0f1e34`, `--paper: #f1f5fb` (blue-tinted vs the charter's green-tinted), and **no teal token at all** (nearest is `--success: #1f8a5b`).

The repo's own design spec — `docs/superpowers/specs/2026-06-14-neoori-brand-redesign-design.md:10-31` — already specifies `#ea5624` / `#1c3561`. The shipped CSS drifted from it during the PM feedback round (`52b75f9` → `dc944e5`). So this is bringing the code back into line with a spec it already had, not a new direction.

Three complications:
- **Hardcoded hexes bypass the token system** and won't follow a `:root` edit: `globals.css:117-154` (`.bg-mesh`, `.bg-mesh-navy`, `.bg-dots`), `:126-133,209,222` (every shadow utility), and `components/brand/Logo.tsx:73,89,123,127-129` — deliberately un-var'd in `a91f335`.
- **The logo is a raster PNG** (`/public/neoori-logo.png`, commented *"used verbatim, never recolored"*). A CSS recolor cannot touch it; the charter's double-infinity mark needs a new asset.
- **Carlito is not on Google Fonts** → `next/font/local` + a self-hosted woff2. Current stack is Plus Jakarta Sans / Inter / JetBrains Mono.

Also dead: the `--n-*` report tokens at `globals.css:86-93` have zero consumers.

### 4.2 Print

There is one stylesheet, no PDF library, and export is `window.print()`. Two real problems for the "2 PDFs on P1 paid" requirement:

- `.report-shell` is `600 × 900` — a 2:3 ratio, not A4's 1:1.414 — with `overflow: hidden`, which is hostile to multi-page print.
- The counselor view is **component state, not a URL param**, so `?print=1` can only ever produce the candidate report. Move the view into the URL to get two deterministic documents.

`.opacity-60 { opacity: 1 !important }` in the print block un-dims locked sections, printing a full-opacity lock message. Revisit alongside the sentinel change.

### 4.3 RGPD / retention

- Rewrite the CDC line and `app/(legal)/confidentialite` from *"nothing is kept"* to *"you control what we keep"* (decision 2). `cgv/page.tsx:19-20` also states section counts that change with the 3-parcours model.
- Consent-withdrawal / erasure flow for the profile.
- Counselor return-to-file access — the B2G requirement that forced the retention decision.
- **Anthropic DPA** is PM/legal, blocks real-user testing, and I cannot do it.

---

## Verification

Per phase, before pushing to `initial`:

1. `cd backend && venv/bin/python -m pytest tests/ -q` — expect `test_anthropic_service.py:100-118` to fail by design in Phase 0 (it asserts `_section_keys("A","haiku") == ["1","2","3","4"]` and the literal `_SECTION_TITLES_B` descriptions); rewrite against the registry. Add cases for letter and Roman keys through `_parse_output`, `_MD_SECTION_RE`, and `_build_output_schema`.
2. `cd frontend && npm run build` — the type changes ripple through `types/index.ts` into ~12 files.
3. Migration up **and** down against a scratch DB before pushing (`Procfile` auto-runs `flask db upgrade`, so a broken migration takes the backend down on deploy).
4. End-to-end per parcours on the live URL after the push: create → poll `/analyse/en-cours/[id]` → report renders in registry order with correct titles → counselor view at `/c/[token]` shows the right section set → print produces a sane A4.
5. Encryption: confirm bloc 5 and OETH are ciphertext at rest, absent from `GET /api/analyses/<id>`, absent from the admin analyses log, and absent from both PDFs.
6. OETH invariant: fill the form twice, identical except the checkbox — the two sessions must be indistinguishable in the UI (same fields, same layout, same requests).
7. Premium: Stripe test-mode checkout → webhook → regeneration at `claude-opus-5` with `max_tokens ≥ 16000` → §10 and §11 present and complete (not truncated).

## Known pre-existing issues, noted but not in scope

- `start_analysis` spawns a bare `threading.Thread(daemon=True)` with no pool or backpressure; `app/__init__.py:79-87` sweeps `running` → `error` at boot, and with `--workers 2` each worker's boot kills the other's in-flight generations.
- `frontend/src/proxy.ts` exports `proxyConfig`, but Next 16 expects `export const config` — the matcher is ignored. Benign today thanks to an early return.
- `litellm==1.83.7` and `resend==2.30.0` are installed and imported nowhere; `backend/.env.example` still advertises a Gemini model id that would break the Anthropic SDK call.
- `User.credits_remaining` is written nowhere; `User.plan` is read only for the admin conversion KPI. The paywall is entirely per-analysis.
- `anthropic`, `json-repair`, and `stripe` are unpinned lower bounds — a fresh deploy can pull a new major.
- `db.session.remove()` before the Anthropic stream (`anthropic_service.py:292`, commit `a3925e9`) is a deliberate fix for TiDB reaping idle connections across multi-minute streams. **Preserve it through every refactor.**

## Still outstanding from the PM

- The 3 prompt texts (P1 v1.8, P2 v1.0, P3 v1.0) — the specs give structure, not text. Admin UI will be ready; admins paste.
- Anthropic DPA signature.
- Premium price (built configurable so it doesn't block).
- Owner of the aménagements / dispositifs reference list — unowned, it will eventually cite a scheme that no longer exists.

## Out of scope

Le voyage (6 sessions S0–S5, 17 questions, Roue du Sens, Académie des Ori), le portrait, le Conseiller chat, les groupes d'échange. Separate program.
