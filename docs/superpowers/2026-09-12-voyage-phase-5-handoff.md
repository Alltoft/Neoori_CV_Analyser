# Le voyage — phase 5 handoff (injection into analyses) · the feature is complete

Phase 5 is complete and merged into `initial` **locally**. 9 commits, **820 backend tests**, 0 failures. Nothing is pushed. With it, **le voyage
is finished**: phases 0-5 all landed, and the copy that says the voyage enriches your analyses is
now true.

**Plan:** `docs/superpowers/plans/2026-09-09-voyage-phase-5-injection.md` — **read it with**
`.superpowers/sdd/2026-09-09-voyage-phase-5-injection/rulings-preflight.md`, which overrides it.

## Deploying this — two steps a fresh database needs

```
flask db upgrade                              # five voyage migrations, head a3b4c5d6e7f8
python seed_prompt_v10_voyage_micro.py
python seed_prompt_v10_voyage_portrait.py
```

Skip the **migrations** and every `/api/voyage` *and* `/api/analyses/` call 500s — `Analysis` selects
`voyage_id`, so the dashboard dies with the voyage. Skip the **seeds** and the API is fine, but
session 0 ends with « Aucun prompt actif pour le slot voyage_micro » (retryable) and the portrait
fails the same way. Both were measured, the first on the local stack on 2026-09-12.

## What phase 5 added

| File | Change |
|---|---|
| `backend/app/services/anthropic_service.py` | `_voyage_block()` inside `_common_tail()` — one change covers all three parcours |
| `backend/app/routes/analyses.py` | `_merge_voyage()`: **pops any client-supplied `_voyage` / `_voyage_id` first**, then folds the server's own; `create_analysis` stamps `Analysis.voyage_id` |
| `backend/app/routes/voyage.py` | `DELETE /api/voyage` strips those keys from past analyses (PM ruling) |
| `backend/app/models/analysis.py` | `voyage_id` popped from the counselor/public-share payload |
| `backend/tests/test_voyage_prompt_context.py` | The four rules: never required · the stage rule · no numbers or framework words · traceability |
| `frontend/src/types/index.ts` · `TEST-PLAN.md` § 12.9 · `CLAUDE.md` | Types, the PM's manual rows, the project documentation |

## Decisions a future reader will otherwise trip over

- **The server is the only writer of `_voyage` and `_voyage_id`.** The plan folded them in without
  removing what the caller posted, and `POST /api/analyses/` carries **no auth decorator**: a probe
  posted « IGNORE TOUTES LES INSTRUCTIONS PRECEDENTES. » plus a framework-vocabulary line and watched
  them reach the model under the real header, stamped another user's voyage id on the row, and 500ed
  the route with a bogus one. The two `pop()`s are the first statements of the fold, for authenticated
  and anonymous callers alike.
- **Erasure reaches the copies** (PM ruling, 2026-09-12). `DELETE /api/voyage` strips both keys from
  that user's referencing analyses before deleting the row. `Analysis.inputs` is a JSON column, so the
  strip **reassigns a new dict** — an in-place `pop()` does not persist, proven by probe.
- **The stage rule is what keeps a report from front-running a restitution.** Until
  `portrait_status == "validated"`, an analysis gets the phrase and the three attractions only.
- **Reduction happens once, at merge time.** Unlocking an analysis regenerates it from the stored
  lines, so a delivered report is never rewritten by a later validation.
- **A digit in the phrase is legitimate** (« Après 17 ans d'usine… »). The no-digit rule covers the
  lines after « Phrase révélée » — do not add a runtime assertion that would 500 on a phrase.
- **The block's header and « Phrase révélée » share a root with a banned word.** They are model-facing
  prompt text; the ban reaches pages, and the hub says « Votre phrase ».

## Open, needing the PM
1. **`RÈGLE DÉFICIT` still missing from the active `voyage_micro` prompt** (/admin/prompts). Carried
   since phase 3; the counselor sheet now shows the phrase, which is the mitigation, not the fix.
2. Retake: still no CTA, and `GET /api/voyage/portrait` resolves to the newest open voyage, so adding
   one needs that endpoint to serve the latest **validated** portrait instead.
3. `DELETE /api/voyage` erases only the current voyage; an older finished one resurfaces on the hub.
4. Carried from phase 0: `Besoin dominant : competence` reaches the model unaccented; the cahier
   ban-list question.

## Known, accepted, not done
- `Voyage.counselor_code_id` still has no `ondelete`.
- `save_draft` now pops the two keys too, but drafts remain the one place `_voyage` was ever
  client-writable; nothing downstream consumed it.
- `AnalysisInputsB` (legacy `_path: "B"`) did not gain the two keys; the interface is referenced nowhere.
- `npm run lint` still reports the pre-existing 10 problems.
- No live browser walk of the whole six-session flow was done — TEST-PLAN §§ 12, 12.9 and 13 are the
  manual pass, and finishing a voyage bills real Anthropic calls.

## Process notes worth keeping
- **Three of the five plans ended with `git push` to production**, one of them without the migration
  step that makes the app work at all. Every one was struck before an agent saw it.
- **Auditing a plan before executing it paid for itself in every phase**: the missing parity test and
  the unreachable counselor link (phase 3), the AI-marking rule with no code behind it and the
  validate-before-save bug (phase 4), the injection hole and the erasure gap (phase 5).
- **"The suite is green" is not evidence a guard works.** Two separate guards this phase passed while
  the thing they guarded was broken — a ban word planted in the bank's negative pole, and a test whose
  assertion could not fail. Both were found by mutating, not by reading.
