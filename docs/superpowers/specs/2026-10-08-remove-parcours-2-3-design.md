# Retrait des parcours 2 et 3 — Design Spec
Date: 2026-10-08
Status: design approved in conversation 2026-10-08; written spec awaiting review

## Overview

The CV product has three parcours: 1 « J'ai une cible », 2 « Je cherche ma
direction », 3 « Je pars de zéro ». Parcours 2 and 3 leave the app entirely —
code, copy, prompts and data. Parcours 1 and le voyage stay as they are.

This is sub-project 1 of 3. The other two get their own specs:

2. A new submit flow for « J'ai une cible »: the form opens without an account,
   and « Générer l'analyse complète » offers four doors (sign in, conseiller
   code, promotion code, free version without login).
3. The split into two subdomains, `cv.<domain>` and `voyage.<domain>`, with the
   base domain a single setting.

This one ships alone, from `initial`. Its only overlap with the unmerged
`feat/social-sign-in` branch is `CLAUDE.md`, `DOCKER.md` and
`backend/app/config.py`, on different lines.

## Decisions

Developer rulings, 2026-10-08:

1. **P2 and P3 go entirely**: forms, validators, prompt builders, section
   lists, prompt slots, seed scripts, tests, copy. Parcours 1 and le voyage are
   untouched.
2. **Existing P2/P3 data is deleted, not archived** — whether or not real
   people used them. Deleted: every analysis whose `inputs._path` is "2", "3"
   or the legacy "B" (the old Chemin B, which became parcours 3), the counselor
   notes and price feedback attached to them, and every `PromptVersion` row of
   slots "2" and "3". Rejected: keeping them read-only (keeps P2/P3 rendering
   code alive, and keeps personal data with no purpose); mailing the owners
   with a 30-day grace period.
3. **A one-off script does the deletion**, dry-run by default, `--apply` to
   delete, run by hand on the VPS right after the code deploy, so the counts
   are seen before anything goes. Rejected: an Alembic data migration (deletes
   without anyone looking, and rolling the image back past a revision breaks
   `flask db upgrade` at container start, because the old image cannot find the
   revision); hand-typed SQL (no tests, and the foreign-key order is easy to get
   wrong).
4. **A fresh dump precedes `--apply`**: the nightly backup script, run by hand.
   It rotates out with the existing 7-day retention. No other copy is kept.
5. **Kept**: user accounts, including those whose only analyses were P2/P3; and
   `code_redemptions` rows pointing at a deleted analysis — a code already
   spent stays spent, and the conseiller's bénéficiaires history is unchanged.
6. **The prompt texts are not exported by code.** v1.1-P2 exists only in the
   production database (no seed script); v1.1-P3's live text has drifted from
   its seed. If the PM wants a copy, they copy it from `/admin/prompts` before
   the deploy — slots 2 and 3 disappear from the admin with it.
7. **`/analyse` stops being a chooser** and redirects to the parcours 1 form,
   `/analyse/nouveau`. Its voyage card goes; the voyage stays on the landing
   (`#voyage`), in `/espace` and in the account menu. `/analyse/direction` and
   `/analyse/depart` are deleted and answer 404 — no redirect.
8. **The server stamps every new analysis `_path: "1"`**, whatever the request
   body says.
9. **Copy: every P2/P3 mention leaves the current site**, with minimal
   rewrites in the existing tone — nothing else on it changes. The exact
   before/after is in « Copy » below. The site at the root domain stays as it
   is until the outcome of the split is known; each subdomain then gets its
   own landing, describing its product as a separate app (sub-project 3).
10. **The counselor view goes in sub-project 2, not here.** Ruling: the
    counselor sees the full report, on the counselor's page; `/c/<token>` with
    its §1/§4/§5 selection disappears. Until sub-project 2 ships, this
    sub-project only removes the view's P2/P3 branches.
11. **The legacy Vercel/Render/TiDB test environment no longer exists.** Its
    leftovers in the repo go too (« Legacy hosting leftovers » below).

## What stays of the parcours machinery

- `section_registry.PARCOURS` keeps its shape, with one entry: "1". The legacy
  "A" keeps mapping to "1" (rows written before the three-parcours migration),
  and an absent `_path` keeps meaning "1". Any other stored value falls back to
  "1", as unknown values already do today.
- `PromptVersion.path` keeps its column and slot lookup. Valid slots become
  "1", "voyage_micro", "voyage_portrait".
- **No schema migration.** No column, enum or constraint names P2/P3:
  `inputs._path` is a JSON key and `prompt_versions.path` is a `VARCHAR`. The
  two mid-chain migrations that mention P2/P3 (`c3d4e5f6a7b8`,
  `a7b8c9d0e1f2`) stay — deleting either breaks the chain.

## Backend

| File | Change |
|---|---|
| `services/section_registry.py` | Delete `_P2`, `_P3` and their `PARCOURS` entries. `normalize()` keeps only the legacy `"A" → "1"` map. Docstrings and the counselor-set comment. |
| `services/anthropic_service.py` | Delete `_format_user_message_p2`, `_format_user_message_p3` and their `_FORMATTERS` entries. The tier line drops its `path == "3"` branch and reads `inputs._tier`. Comments. **Keep** `_profile_block`, `_conditions_block`, `_rights_block`, `_voyage_block`, `_common_tail`, and the longest-first heading regexes (`_md_section_re`, `_section_open_re`) — parcours 1 needs them to tell "1" from "10" and "11". |
| `routes/analyses.py` | Delete `_missing`, `_validate_inputs_p2`, `_validate_inputs_p3`, their `VALIDATORS` entries, and the parcours 3 tier branch. `create_analysis` sets `inputs["_path"] = "1"` unconditionally and normalises `_chemin` unconditionally (it was parcours-1-only). Comments. |
| `services/unlock_service.py` | Delete the parcours 3 refusal. |
| `routes/payments.py` | Delete the parcours 3 checkout refusal. |
| `services/prompt_slots.py` | `LABELS` loses "2" and "3" (`valid()` derives from the registry). Docstrings. |
| `routes/prompts.py` | `_read_path` keeps `"A" → "1"` and drops `"B"`: "B", "2" and "3" now get the existing 400 for an unknown slot. Without this, "B" would fall through `normalize()` to slot "1" — a silent overwrite of the live parcours 1 prompt, the exact case `_read_path` exists to prevent. |
| `models/analysis.py` | `COUNSELOR_VISIBLE_INPUT_KEYS` loses `_sub_profile`, `aime`, `refuse`, `accompagnement` (parcours 3 key facts only) and `_path` (no counselor surface forks on it any more). Comments. |
| `models/prompt_version.py`, `models/profile.py`, `routes/profile.py` | Comments only. |
| `routes/admin.py` | No change: `active_prompts` is data-driven. |
| `seed_prompt_v10_p2.py`, `seed_prompt_v11_p3.py` | Deleted. |

## Data purge

`backend/purge_retired_parcours.py` — temporary. A follow-up commit removes it,
with its tests, once the developer confirms the production purge (runbook
step 6 at zero).

**Selection.** Every analysis whose raw `inputs._path`, read as a string,
stripped and upper-cased, is "2", "3" or "B" — the values the old `normalize()`
sent to parcours 2 and 3. The filter runs in Python, not in SQL: the test
database is SQLite, and the table is small.

**Dry-run (default) changes nothing and prints:**
- analyses to delete, by parcours × status;
- how many of them carry `unlock_method` (paid or code-unlocked);
- counselor notes and price feedback rows to delete;
- `code_redemptions` pointing at them — kept, shown for information;
- prompt versions to delete: path, label, `is_active`, `created_at`.

**`--apply`** runs one transaction, in foreign-key order:
1. `counselor_notes` of the selected analyses (their FK has no `ON DELETE`, so
   it would block step 3);
2. `price_feedback` of the selected analyses (the DB cascade would do it; the
   script does not rely on that);
3. the selected `analyses`;
4. `prompt_versions` with path "2", "3" or "B" ("B" defensively: the
   migrations already moved the legacy "B" prompts to "3"). Before this step
   the script checks that no remaining analysis references one of them; if one
   does, it aborts and rolls back — nothing is deleted.

It prints the counts after, and exits non-zero on any error. A second run finds
nothing and deletes nothing.

**Runbook** — each step on the developer's go:
1. *(PM, optional)* copy the P2/P3 prompt texts from `/admin/prompts`.
2. Merge to `initial`, push: the deploy builds and starts the new images.
3. On the VPS, dry-run, and read the counts:
   ```bash
   ssh neoori
   cd /srv/neoori
   docker compose -f docker-compose.prod.yml exec -T backend python purge_retired_parcours.py
   ```
4. Fresh dump: `/usr/local/bin/neoori-backup.sh` (replaces the day's
   `/backups/neoori-<date>.sql.gz`; 7-day rotation).
5. `docker compose -f docker-compose.prod.yml exec -T backend python purge_retired_parcours.py --apply`
6. Dry-run again: everything at zero.

The local dev database gets the same treatment first, as a rehearsal.

## Frontend

| File | Change |
|---|---|
| `app/analyse/direction/page.tsx`, `app/analyse/depart/page.tsx` | Deleted. |
| `app/analyse/page.tsx` | Becomes a redirect to `/analyse/nouveau` (temporary redirect: sub-project 2 changes this flow again). |
| `types/index.ts` | `Parcours`, `AnalysisPath`, `PromptSlot` and `normalizeParcours` shrink to parcours 1 and the voyage slots. Dead code goes: `AnalysisInputsB`, `PAID_SECTIONS`, the legacy Chemin B input fields (`nom` stays — the report header uses it). |
| `app/analyse/[id]/rapport/page.tsx` | Drop the parcours 3 header (« Portrait de potentiel ») and the parcours 3 key-facts branch. The unlock CTA no longer tests `path === "1"`. |
| `app/c/[token]/page.tsx` | Drop the parcours fork in the key-facts strip. |
| `app/analyse/[id]/debloquer/page.tsx` | Drop the `path === "3"` « déjà complète » case. |
| `app/espace/page.tsx` | Drop the « Portrait de potentiel » card title; copy below. |
| `app/admin/prompts/page.tsx` | `SLOTS`, `SLOT_LABEL` (byte-locked to the backend `LABELS` by a test), `SLOT_HELP` and `SLOT_SUFFIX` lose "2" and "3"; `SUFFIX_RE` loses `P2`, `P3` and `B`. `toSlot()` stops mapping unknown paths to "1": an unknown row is left out, never shown in parcours 1's history or as its « actif ». |
| `app/globals.css` | `--teal` / `--color-teal` go: only the parcours 3 surfaces used them. `--success` is its own literal and stays. Comment on the three hues. |
| `components/report/ReportSection.tsx` | Comment only. The chip logic stays: parcours 1 needs it for "verdict", "10" and "11". |
| Landing, `SiteNav`, `SiteFooter`, `AuthLayout`, `app/layout.tsx`, legal pages | See « Copy ». |

## Copy

Every sentence of the current site that names P2/P3, or promises an analysis
without a CV. Left as is, the site would advertise what no longer exists and
link to pages that answer 404. The wording is approved with this spec.

| # | Where | Before | After |
|---|---|---|---|
| 1 | Landing, hero subtitle | « Vous visez un poste, vous cherchez votre direction ou vous repartez de zéro : neoori lit votre parcours — avec ou sans CV — et vous dit ce qui fait votre force, ce qui freine, et par où avancer. » | « Vous visez un poste : neoori lit votre parcours et votre CV face à cette cible, et vous dit ce qui fait votre force, ce qui freine, et par où avancer. Pas encore de cible ? Le voyage vous aide à faire le point. » |
| 2 | Landing, hero floating chip | « 3 · parcours » | removed |
| 3 | Landing, « Comment ça marche », step 02 | « Votre point de départ » — « Une cible précise, une direction à trouver, ou un départ de zéro. Votre CV si vous en avez un — sinon, quelques questions suffisent. » | « Votre cible » — « Une offre d’emploi en main, ou le poste que vous visez décrit avec vos mots. Et votre CV, en PDF ou copié-collé. » |
| 4 | Landing, step 03 | « neoori lit votre parcours du point de vue des recruteurs — et votre CV, si vous en avez un, en tenant compte des ATS. » | « neoori lit votre parcours et votre CV du point de vue des recruteurs, en tenant compte des ATS. » |
| 5 | Landing, section `#parcours` | « Par où commencer — Trois situations, trois lectures », its three cards | removed, with the nav link « Parcours » and the footer link « Les parcours » |
| 6 | Landing, `#rapport` intro | « … Ci-dessous, celui du parcours « J’ai une cible ». » | « … Ci-dessous, un exemple. » |
| 7 | Landing, free offer | « Vous découvrez ce que votre parcours montre déjà — face au poste que vous visez, ou pour trouver votre direction. » | « Vous découvrez ce que votre parcours montre déjà face au poste que vous visez. » |
| 8 | Landing, paid offer | « Pour le parcours « J’ai une cible », en plus des 3 premières sections, vous accédez à : » | « En plus des 3 premières sections, vous accédez à : » |
| 9 | FAQ « Combien ça coûte ? » | « Le rapport complet est à 9 € — pour le parcours « J’ai une cible », neuf sections, dont la proposition de CV retravaillé. » | « Le rapport complet est à 9 € : neuf sections, dont la proposition de CV retravaillé. » (rest unchanged) |
| 10 | FAQ « Combien de temps pour avoir mon rapport ? » | « Quelques minutes. Le temps de répondre aux questions de votre parcours, l’analyse est déjà en cours. » | « Quelques minutes après l’envoi de votre CV et de votre cible. » |
| 11 | FAQ « Quels formats de CV sont acceptés ? » | « … Pas de CV ? Le parcours « Je pars de zéro » s’en passe : cinq questions suffisent. » | last two sentences removed |
| 12 | Footer tagline | « Une lecture de votre parcours, avec ou sans CV, au service de votre projet professionnel. » | « Une lecture de votre parcours, au service de votre projet professionnel. » |
| 13 | Auth side panel, bullet | « Trois parcours d’analyse et le voyage » | « L’analyse de votre CV et le voyage » |
| 14 | Auth side panel, line | « Une lecture claire de votre parcours, avec ou sans CV. » | « Une lecture claire de votre parcours. » |
| 15 | Site description (meta) | « Faites le point sur votre parcours, avec ou sans CV : trois parcours d'analyse et le voyage, six sessions pour poser ce que vous savez déjà de vous. Conçu pour … » | « Faites le point sur votre parcours : l'analyse de votre CV face au poste que vous visez, et le voyage, six sessions pour poser ce que vous savez déjà de vous. Conçu pour … » |
| 16 | OpenGraph description | « Trois parcours d'analyse, avec ou sans CV, et le voyage en six sessions. Pour … » | « L'analyse de votre CV face à votre cible, et le voyage en six sessions. Pour … » |
| 17 | Twitter description | « Trois parcours d'analyse, avec ou sans CV, et le voyage en six sessions pour faire le point sur votre parcours. » | « L'analyse de votre CV face à votre cible, et le voyage en six sessions pour faire le point sur votre parcours. » |
| 18 | `/espace`, empty state | « ~2 min · avec ou sans CV » | « ~2 min » |
| 19 | CGV §2 | « L'offre payante débloque le rapport complet du parcours choisi, ainsi que l'export conseiller. Pour le parcours « J'ai une cible », il compte 9 sections, incluant … » | « L'offre payante débloque le rapport complet, ainsi que l'export conseiller. Il compte 9 sections, incluant … » |
| 20 | Confidentialité, « Analyses » | « selon le parcours choisi, le contenu de votre CV, la cible visée (offre d'emploi ou description) et vos réponses aux questions du parcours (pouvant inclure des informations sensibles que vous choisissez de communiquer). » | « le contenu de votre CV et la cible visée (offre d'emploi ou description), pouvant inclure des informations sensibles que vous choisissez de communiquer. » |
| 21 | Admin, prompt slots | « Parcours 2 · Je cherche ma direction », « Parcours 3 · Je pars de zéro » and their help lines | removed |

Removed with the pages and code that carry them: the `/analyse` chooser (« Par
où commencer ? », its cards and footnote), the two forms, the parcours 3 report
header « Portrait de potentiel », the P2/P3 validation messages, and the
parcours 3 refusals at unlock and checkout (« Le portrait de potentiel est déjà
complet »).

The H1 « Où que vous en soyez, faites ressortir votre vrai potentiel. » stays:
with row 1's last sentence pointing to le voyage, it remains true for someone
without a target.

## Legacy hosting leftovers

The Vercel/Render/TiDB environment is gone; nothing in the repo may describe it
as current.

| Where | Change |
|---|---|
| `CLAUDE.md` | Delete the line « The legacy Vercel/Render/TiDB test env keeps serving its last deploy until cutover… ». |
| `DOCKER.md` | Delete the section « Data migration (TiDB Cloud → VPS MySQL, at cutover) ». |
| `frontend/vercel.json` | Deleted. |
| `.gitignore`, `frontend/.gitignore`, `frontend/.dockerignore` | Drop the `.vercel` entries. |
| `backend/app/config.py` | Reword the pre-ping comment, which names TiDB Cloud. **Keep `pool_pre_ping`**: MySQL also closes connections idle past `wait_timeout`. |
| `backend/app/routes/analyses.py`, `TEST-PLAN.md` | « FORCE_ANALYSIS_TIER="" on Render » → in `/srv/neoori/.env`. |
| `.github/workflows/deploy.yml` | Header comment no longer refers to the Vercel/Render auto-deploys. |

Migrations and dated docs keep their mentions: they record their time.

## Errors and edge cases

- **`POST /api/analyses/` with `_path` "2", "3", "B" or garbage**: stamped "1",
  then parcours 1 validation runs (`cv_text` ≥ 200, `cible_visee` ≥ `CIBLE_MIN`)
  — a stale P2/P3 page gets the parcours 1 errors, never a P2/P3 run.
- **`/api/prompts` with path "2", "3" or "B"**: 400, « path doit être l'un de
  '1', 'voyage_micro', 'voyage_portrait'. »
- **`/analyse/direction`, `/analyse/depart`**: the Next.js 404 page.
- **Between the deploy and `--apply`** (minutes): leftover P2/P3 rows are read
  as parcours 1. They show their old output under parcours 1 titles, or
  nothing; a paid unlock in that window would regenerate them with the
  parcours 1 prompt. Accepted — they are about to be deleted, and step 3 of the
  runbook follows the deploy directly.
- **Purge failure**: one transaction, rolled back, non-zero exit; nothing is
  deleted.
- **Image rollback**: no schema change, so the previous image runs with or
  without the rows. Rolled back after the purge, it shows the P2/P3 forms again
  with an empty history. Deleted data comes back only from the pre-purge dump
  (restore procedure: `DOCKER.md` « Backups »), within its 7 days.
- **A pre-purge backup restored later** brings P2/P3 rows back. They read as
  parcours 1, as above; re-run the purge.

## Testing

**Delete** — the 19 tests that only cover P2/P3: 8 in `test_parcours_inputs.py`
(the file stays: 16 of its 25 tests are parcours 1), 7 in
`test_anthropic_service.py`, 3 in `test_analysis_model.py`, 1 in
`test_unlock.py`.

**Edit**
- Parcours 1 tests carrying P2/P3 or legacy "B" cases:
  `test_parcours_inputs.py`, `test_anthropic_service.py`,
  `test_analysis_model.py` (with `_RENDERED_INPUT_KEYS` and `_full_inputs` in
  step with `COUNSELOR_VISIBLE_INPUT_KEYS`), `test_prompt_slots.py`,
  `test_seed_scripts.py`.
- `test_voyage_prompt_context.py` imports `_format_user_message_p2` / `_p3` at
  module level: without the edit, the whole module (about 40 tests, mostly
  parcours 1 and voyage) fails to import. Its P2/P3 fixtures and parametrize
  cases go too.
- Lockstep tests pass when both sides change together:
  `test_admin_selector_labels.py` (backend `LABELS` = frontend `SLOT_LABEL`),
  `test_prompt_section_keys.py` (seed scripts × registry),
  `test_migration_chain.py`.

**Add**
- Parcours 1 heading match, longest first: "1" is not read inside "10" or "11"
  (the deleted roman-numeral test gave this coverage).
- `create_analysis` stamps `_path: "1"` for a body carrying "2", "3", "B", a
  list or nothing.
- The prompts API refuses "2", "3" and "B" with 400, and still takes "A" as "1".
- Purge script:
  - the dry-run changes nothing;
  - `--apply` deletes exactly the "2" / "3" / "B" analyses, their notes and
    feedback, and the "2" / "3" prompts;
  - parcours 1 rows — `_path` "1", legacy "A", or absent — the voyage prompts,
    users and code redemptions are intact;
  - it aborts and rolls back when a kept analysis references a prompt marked
    for deletion;
  - a second run deletes nothing.

**Run**: the full backend suite; `tsc --noEmit` and `next build`; a local
Docker walkthrough — landing, `/analyse` → form, the two 404s, a parcours 1
report, the counselor view `/c/<token>`, `/admin/prompts` showing three slots.

## Docs

- **Updated**: `CLAUDE.md` ("all three parcours carry it", "Every parcours
  runs identically"), `TEST-PLAN.md` (§2 chooser, §5 P2, §6 P3, "five
  prompts"), the `DOCKER.md` seed loop, and the lines of the voyage spec and
  contracts that `CLAUDE.md` links to.
- **Workflow**: the `all` set of `.github/workflows/seed.yml` drops the two
  deleted seed scripts.
- **Left as they are**: `plan.md`, `SESSION-LOG.md`, `handoff.md`, past plans
  and PM messages — snapshots of their date.

## Out of scope

- Sub-projects 2 and 3, and the landing redesign.
- Removing the parcours abstraction itself (registry, slot lookup): it stays,
  with one entry.
- The counselor view `/c/<token>`: replaced in sub-project 2 (decision 10).
- `video/` (the motion ad, outside git): its card scene shows the three
  parcours. Untouched here; it needs a re-render before any use.
- Issues found during exploration, not fixed here: the frontend never refreshes
  the access token; `/api/prompts/active` is public; counselor notes on
  `/c/<token>` accept any signed-in role; a profile deletion leaves the bloc 5
  summary and the OETH flag in plaintext inside past analyses.
