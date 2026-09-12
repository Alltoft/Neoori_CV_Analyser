# Le voyage — phase 4 handoff (counselor UI)

Phase 4 is complete and merged into `initial` **locally**. 13 commits (`d81096a..f8855eb`),
**781 backend tests**, 0 failures. `npm run build` passes; `npm run lint` is exactly the pre-existing
`✖ 10 problems (5 errors, 5 warnings)`. Nothing pushed.

**Plan:** `docs/superpowers/plans/2026-09-09-voyage-phase-4-counselor-ui.md` — **read it with**
`.superpowers/sdd/2026-09-09-voyage-phase-4-counselor-ui/rulings-preflight.md`, which overrides it.
Ledger (every ruling, review and mutation scoreboard): `progress.md` beside it.

## What exists

| File | Contents |
|---|---|
| `frontend/src/app/voyage/c/[token]/page.tsx` | The counselor surface: role gate, key facts, sheet, portrait editor, private note, restitution guide, print |
| `frontend/src/components/voyage/SynthesisSheet.tsx` | The manual's page-18 sheet + the AI legend, the phrase block and the staleness warning |
| `frontend/src/components/voyage/RiasecBars.tsx` | Six bars off the **computed** maxima (R12 I11 A10 S10 E11 C9) |
| `frontend/src/components/voyage/RestitutionGuide.tsx` | The five-phase guide, verbatim manual text, plus `NOTE_PROMPTS` |
| `frontend/src/lib/voyage-labels.ts` | The accented French for the scoring vocabulary — counselor surface only |
| `frontend/src/lib/voyage.ts` | Gained the six counselor wrappers |
| `frontend/src/app/globals.css` | `.ai-block` — the peach rule + tint that marks AI-written text |
| `frontend/src/app/admin/utilisateurs/page.tsx` · `admin/page.tsx` | Role select; the four voyage KPIs |
| `backend/app/routes/voyage.py` | `counselor_sheet` gained the row's `scoring_version` (ten keys) |
| `backend/tests/test_voyage_counselor_labels.py` | Python ↔ TS parity for the vocabulary, and the import boundary |
| `TEST-PLAN.md` | « § 13 · Le voyage — vue conseiller », 27 rows |

## Decisions a future reader will otherwise trip over

- **The boundary is enforced in code, not by convention.** `voyage-labels.ts`, `SynthesisSheet` and
  `RiasecBars` may be imported by exactly three files, asserted with `==` (not `⊆`, which passes when
  nothing imports them at all). Planting an import in a candidate page fails the suite.
- **Peach means "an AI wrote this".** `.ai-block` marks the session-0 phrase and the six portrait
  sections; the legend says so once, at the top. It reads « bordés de pêche », not « teintés »,
  because three non-AI blocks share the same tint — the border is what distinguishes them.
- **The phrase block carries « Déjà affichée à la personne ».** That is the distinction that matters:
  the candidate has already read it, unreviewed. A non-`success` status says so rather than showing an
  empty block.
- **« Valider et transmettre » saves first.** It used to post validate while edits sat unsaved: the
  server validated the *stored* text and the seed effect then overwrote the fields, so the counselor's
  corrections vanished and the candidate received the un-edited draft. The textareas are also frozen
  while a save, validate or regenerate is in flight, and the seed no longer re-runs on draft→validated.
- **« Régénérer » follows the backend**, which accepts `draft`, `error`, or a `generating` row older
  than ten minutes. An `error` portrait keeps its button — that state is what a counselor is there to
  rescue — and the stored failure reason is shown.
- **The editor does not render for `portrait_status == "none"`**; the page says the portrait has not
  been drafted yet rather than offering six boxes the API will refuse.
- **A stale `scoring_version` is surfaced.** `synthesis.scoring_version` is always the bank's current
  value, so the payload carries the row's own; when they differ the sheet says the answers predate the
  questionnaire, instead of silently showing « Session 1 non terminée. ».
- **Mutating actions are guarded by refs, not state.** A `if (saving) return` still sent two PUTs on a
  double click (stale closure); `loadingRef`-style refs are the pattern here.

## What phase 5 must know
- Nothing in phase 4 blocks it; the two phases touch different files.
- `Analysis.to_dict(audience="counselor")` filters `inputs` to an allow-list (phase 3) — phase 5's
  `_voyage` must stay out of it, and `voyage_id` was removed from that payload in phase 5.

## Open, needing the PM
1. Three commits (`3ffc4b8`, `7482710`, `564f9cc`) carry a `Claude Sonnet 5` co-author trailer instead
   of the project's. The PM ruled on 2026-09-12: leave them.
2. The counselor sheet shows the phrase but there is still no way for a counselor to *correct* it —
   they can only mention it in the restitution. A « réécrire la phrase » control is a phase-6 question.
3. Carried: `RÈGLE DÉFICIT` still missing from the active `voyage_micro` prompt (PM action, /admin/prompts).

## Known, accepted, not done
- `Voyage.counselor_code_id` still has no `ondelete`.
- The sheet's fixture-shape test compares only top-level synthesis keys, so a nested rename drifts.
- A poll failure after data exists is surfaced only as a small inline line; a persistent outage is
  otherwise quiet until the three-minute stall message.
- `npm run lint` still reports the pre-existing 10 problems; none are in phase-4 files.

## Process notes
- **Two independent auditors and my own read all found the same top defect**: the AI-marking rule was
  written into the plan's Task 5 as prose, with no code behind it. A requirement added to a plan after
  its code block was written is invisible to anyone executing the code block.
- **The plan's last step was `git push` to production**, and the one before it `git add -A`. Both were
  struck before any agent saw them.
- **An auditor proved a test could not fail** by swapping two French labels and watching the suite stay
  green — `bank.py` holds no French for five of the seven groups, so the test compared keys only.
- **A harness that calls `onChange` directly cannot see `disabled`.** The fix wave's implementer
  discovered its prescribed fix did not satisfy its own proof, fixed the root cause instead, and said so.
