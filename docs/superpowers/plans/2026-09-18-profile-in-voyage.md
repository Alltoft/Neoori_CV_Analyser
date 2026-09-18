# Profil dans le voyage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the Profil de base as a form you go and fill, and ask its questions at
the four points of the voyage where the person is already engaged enough to answer them.

**Architecture:** One `Profile` table, unchanged in spirit — four new columns for the
« Ton parcours » block, two for the sensitive consent. The questions move, the storage
does not. Placement is enforced server-side by extending `voyage.session_lock`, the gate
that already returns the exact French string the locked card renders: S2 needs the
parcours block, S5 needs bloc 5. The frontend gains two interstitial steps under
`/voyage/etape/<bloc>` and captures identity at signup. `/profil` survives as the edit
surface — nobody is ever *sent* there to fill it in the first place.

**Tech Stack:** Flask-SQLAlchemy / Alembic / pytest · Next.js 15 App Router / React Hook
Form + Zod / Tailwind · French UI, English comments.

**Spec:** the two PM PDFs at the repo root — `1_neoori_questionnaire_adapte.pdf`
(« Carte d'intégration des nouvelles questions », p.1) and `2_neoori_spec_syntheses.pdf`.
Open questions raised against them: `2026-09-18-profile-in-voyage-QUESTIONS.md`.

## Global Constraints

- UI strings **French**; code comments and commit messages **English**.
- Banned UI vocabulary (CLAUDE.md): boussole, copilote, miroir, révélation,
  épanouissement, alignement, excellence, talent unique, vous vous démarquez.
- The candidate never sees a score or a trait name. These steps ask, they never restitute.
- Bloc 5 and the OETH flag stay in `SensitiveProfile`, Fernet-encrypted, never in
  `to_dict()`, never in a log, never in a PDF.
- **The OETH invariant:** ticking the box changes nothing observable — same response
  shape, same status code, same rows touched.
- Age brackets are the seven of `AGE_BRACKETS`; `moins_25` is accepted on write and
  never offered.
- No migration may drop a column that holds data. Retirement = stop asking, keep reading.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/models/profile.py` | +4 parcours columns, +2 sensitive-consent columns, their enums |
| `backend/app/routes/profile.py` | validation + upsert for the new fields, sensitive-consent gate |
| `backend/app/models/voyage.py` | `session_lock` gains the two placement gates |
| `backend/app/services/anthropic_service.py` | `_profile_block` carries the parcours lines; `rayon` printed only when present |
| `backend/migrations/versions/<rev>_profile_parcours_block.py` | the six new columns |
| `frontend/src/app/(auth)/inscription/page.tsx` | prénom + tranche d'âge at signup |
| `frontend/src/lib/auth.tsx` | `register()` carries the profile seed |
| `frontend/src/app/voyage/page.tsx` | entry block before the voyage exists; step nudges |
| `frontend/src/app/voyage/etape/[bloc]/page.tsx` | the two interstitials |
| `frontend/src/lib/profile-steps.ts` | one declaration of what each step asks — shared by the step page and the hub |
| `frontend/src/app/profil/page.tsx` | keeps every field, gains the parcours block |

---

### Task 1: The parcours block — storage

**Files:** `backend/app/models/profile.py`, `backend/app/routes/profile.py`,
`backend/migrations/versions/*`, `backend/tests/test_profile.py`

**Produces:** `DIPLOMES`, `TYPES_ETUDES`, `APPETENCE_ETUDES` tuples;
`Profile.diplome / type_etudes / intitule_etudes / appetence_etudes`.

- [ ] Write failing tests: each enum accepted, a bogus value rejected 400, values read back
- [ ] Run, confirm red
- [ ] Add columns + enums; wire `_ENUMS` and `_TEXT_FIELDS`
- [ ] Alembic revision, `flask db upgrade`
- [ ] Run, confirm green; commit

### Task 2: The sensitive consent

**Files:** `backend/app/models/profile.py`, `backend/app/routes/profile.py`,
`backend/tests/test_profile.py`

Bloc 5 and OETH are GDPR Art. 9 territory; the signup CGV does not cover them.

**Produces:** `Profile.consent_sensitive_at / consent_sensitive_version`,
`CONSENT_SENSITIVE_VERSION`.

- [ ] Write failing tests: writing non-empty conditions with no consent on record → 400;
      with `consent_sensitive: true` → stored, and the timestamp recorded once;
      clearing to empty needs no consent; the OETH invariant still holds
- [ ] Run, confirm red
- [ ] Add columns + gate in `_upsert_sensitive`
- [ ] Run, confirm green; commit

### Task 3: Placement — the two new gates

**Files:** `backend/app/models/voyage.py`, `frontend/src/types/voyage.ts`,
`backend/tests/test_voyage_routes.py`

`session_lock` already returns the locked card's exact French string. Two more rules,
after the existing prénom/tranche d'âge one:

- S2..S5 and the profile lacks the parcours block → `LOCK_PARCOURS`
- S5 and bloc 5 was never answered → `LOCK_CONDITIONS`

**Produces:** `LOCK_PARCOURS`, `LOCK_CONDITIONS`, mirrored in `types/voyage.ts`.

- [ ] Write failing tests: S2 locked without the block, open with it; S5 locked without
      bloc 5; S1 unaffected; order still wins where it should
- [ ] Run, confirm red
- [ ] Extend `session_lock` + the TS mirror
- [ ] Run, confirm green; commit

### Task 4: The prompt carries the parcours block

**Files:** `backend/app/services/anthropic_service.py`, `backend/tests/test_prompt_*.py`

- [ ] Write failing test: the three parcours lines appear; absent fields say « Non renseigné. »;
      `rayon` prints only when the row has one
- [ ] Run, confirm red
- [ ] Edit `_profile_block`
- [ ] Run, confirm green; commit

### Task 5: Identity at signup

**Files:** `frontend/src/app/(auth)/inscription/page.tsx`, `frontend/src/lib/auth.tsx`,
`backend/app/routes/auth.py`, `backend/tests/test_auth.py`

Prénom + tranche d'âge move here. They are what `session_lock` has always demanded
before S1, and demanding them mid-voyage is the bounce this whole plan removes.
`POST /auth/register` accepts them and seeds the `Profile` with the CGV consent it
already collects.

- [ ] Write failing tests: register with prénom + bracket creates a Profile carrying both
      and a `consent_at`; register without them creates no Profile (the old shape still works);
      a bogus bracket is refused
- [ ] Run, confirm red
- [ ] Backend seed, then the form fields
- [ ] Run, confirm green; `npx tsc --noEmit`; commit

### Task 6: The entry step — ville, nom, situation

**Files:** `frontend/src/app/voyage/page.tsx`, `frontend/src/lib/profile-steps.ts`

Asked on the hub before the voyage exists, under the PM's « Ce n'est pas un test »
framing. Ville is what makes « demande locale » readable; without it that line stays
« à vérifier », so the step states the consequence rather than forcing the field.

- [ ] Declare the step in `profile-steps.ts`
- [ ] Render it on the hub when no voyage exists yet
- [ ] `npx tsc --noEmit`; commit

### Task 7: The interstitials

**Files:** `frontend/src/app/voyage/etape/[bloc]/page.tsx`, `frontend/src/lib/profile-steps.ts`,
`frontend/src/app/voyage/page.tsx`

One route, two blocs — `parcours` after S1, `conditions` after S4. Styled as part of the
journey, not as a settings page: that is the whole point of moving them.

- [ ] Build the step page off the shared declaration
- [ ] The hub's locked cards link to the step that unlocks them
- [ ] `npx tsc --noEmit`; commit

### Task 8: `/profil` keeps up

**Files:** `frontend/src/app/profil/page.tsx`

Still the edit surface. It gains the parcours block, sends the sensitive consent with
bloc 5, and stops asking `rayon`.

- [ ] Add the block, wire the consent, retire the rayon field
- [ ] `npx tsc --noEmit`; commit

### Task 9: Verification

- [ ] `./venv/bin/python -m pytest tests/ -q` — all green
- [ ] `npx tsc --noEmit` — clean
- [ ] `npx next lint` if configured
- [ ] Update `CLAUDE.md` with where the profile is now asked
- [ ] Commit

---

## Self-review notes

- `rayon` is retired, not dropped: Task 4 keeps printing it for rows that already hold
  one, and no migration touches the column. Reversible if the PM wants it back.
- The three S4-derivable condition families are **not** derived — see the questions doc.
  All eight are asked, on one screen.
- Module Pont (FP-1…FP-14) is out of this plan. It is post-portrait and optional, so it
  is not on the path of any analysis, and PM's format for it differs from bloc 5's shape.
