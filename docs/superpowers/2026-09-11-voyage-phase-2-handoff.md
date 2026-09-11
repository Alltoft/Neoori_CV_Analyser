# Le voyage — phase 2 handoff

Phase 2 (prompt slots, the two AI calls, the seeds, the admin selector) is complete and
merged into `initial` **locally**. 19 commits, **701 tests**, 0 failures. Nothing is pushed;
nothing is deployed.

**Spec:** `docs/superpowers/specs/2026-09-09-voyage-design.md`
**Contract:** `docs/superpowers/plans/2026-09-09-voyage-contracts.md` (§ F prompts, § G generation)
**Plan:** `docs/superpowers/plans/2026-09-09-voyage-phase-2-generation.md`
**Phase 0 / 1 handoffs:** `docs/superpowers/2026-09-10-voyage-phase-{0,1}-handoff.md`

## What exists

| File | Contents |
|---|---|
| `backend/app/services/voyage/generation.py` | Both AI calls: slots, budgets, the six-key `_portrait_schema()`, `LEAK_PATTERNS` + `leak_check()`, `_micro_user_message`, `_portrait_user_message` and helpers, `_stream_text`, `_run_micro`/`start_micro`, `_run_portrait`/`start_portrait`, the leak retry |
| `backend/seed_prompt_v10_voyage_micro.py` · `_portrait.py` | The two system prompts, seeded **active**, idempotently |
| `backend/app/__init__.py` | `reap_stale_generating()` — sweeps voyages orphaned mid-generation at startup |
| `backend/tests/test_voyage_generation.py` (84) · `test_voyage_reaper.py` (14) · `test_no_live_api_key.py` (2) | |
| `frontend/src/app/admin/prompts/page.tsx` · `types/index.ts` | The selector's five slots |

Phase 1 had already shipped `prompt_slots.py`, the fixed `/api/prompts` route and its 20
tests, so phase-2 Tasks 1 and 2 were closed by verification with no code written.

## Decisions a future reader will otherwise trip over

- **`PromptVersion.path` is a slot, not a parcours.** `'1' | '2' | '3' | 'voyage_micro' |
  'voyage_portrait'`. `prompt_slots.normalize()` coerces *stored* values and defaults the
  unknown to parcours 1; it must **never** validate client input, or an admin typo silently
  overwrites the live parcours-1 prompt. The contract's own § F snippet contains that bug —
  phase 1's shipped `_read_path` is right and the contract is wrong.
- **Structure is a JSON schema, never prompt prose.** `_portrait_schema()` goes through
  `extra_body`; a `BadRequestError` degrades to a plain call **only when there was an
  `extra_body` to drop** — retrying a schema-less 400 bills twice for the same failure.
- **`leak_check()` matches word-boundary, diacritic-folded, with an optional trailing `s`
  and `[\s-]+` between words** — so « traits », « scores » and « Big-Five » are caught.
  All 467 French strings the bank emits were scanned: zero false positives.
- **A still-leaking draft is kept and flagged, never discarded** — including when the retry
  *call itself* fails. A flagged draft is more useful than none; that is what the flag is for.
- **The portrait stores a `snapshot` of the synthesis it was written from**, captured before
  the stream, so a later scoring correction can never make an existing portrait a lie.
- **Scene titles may contain digits.** S2-7 is « Dans 20 ans », cahier verbatim. The
  no-digit rule covers the person's own words, not the cahier's titles.
- **`HEADER_SESSION_0 = "--- SESSION 0 ---"` is a contract with the prompt text**, which the
  PM edits from `/admin/prompts` without touching code. Do not rename it for tidiness.
- **The reaper sweeps both statuses in ONE statement with per-column `case()` guards.**
  Two successive UPDATEs are broken twice over: `updated_at`'s `onupdate` fires on a bulk
  UPDATE, so the second pass matches nothing and strands the very row it was meant to
  clear; and an unconditional `"error"` would flip an already-validated portrait. Both
  measured, both pinned.

## What phase 3 must know

- **`micro_status` / `portrait_status` are the whole signal**: `none | generating | success |
  error` for the phrase, `none | generating | draft | validated | error` for the portrait.
  The hub polls `GET /api/voyage` while either reads `generating`.
- **`"error"` is recoverable for the portrait only** — `POST /c/<token>/portrait/regenerate`
  accepts `draft` or `error`. The failure reason is returned in the counselor payload, and
  **only on an error row** (the healthy shape stays five keys). There is **no equivalent for
  the phrase**: a `micro_status = "error"` cannot be retried through any route today. See
  open items.
- **A reaped row carries no error text.** Nothing was alive to observe the failure; the
  status is the signal. Do not render an empty reason as "unknown error" — say the run was
  interrupted.
- **The reaper's clock has a documented blind spot.** `Voyage.updated_at` is a *last-write*
  clock, not a *run-start* clock, so any write to the row pushes it out of the sweep's
  reach. A finished voyage is still writable (session 0 has no code gate and no order lock),
  so this affects the portrait as well as the phrase. Pinned by
  `test_a_finished_voyage_can_still_refresh_its_own_clock` — when per-run timestamps land,
  that test starts failing, which is the signal to delete it.
- **The admin labels are duplicated into TypeScript** and held only by a text-matching
  parity test. `prompt_slots.choices()` still has no consumer; serving it and deleting the
  second copy is the durable fix.
- **The test suite can no longer bill the real Anthropic account** — an autouse fixture
  blanks `ANTHROPIC_API_KEY`, guarded by `tests/test_no_live_api_key.py`. Keep every
  Anthropic call in tests behind the mocked client.

## Open, needing the PM

1. **The micro phrase reaches a candidate with no human gate and no leak check.** Spec and
   contract both scope `leak_check()` to the portrait, so that is what shipped. The
   defence-in-depth is inverted: the *only* ungated candidate-facing text has the weaker
   guard-rail set, and the seeded micro prompt lacks the `RÈGLE DÉFICIT` its counselor-gated
   sibling carries. Both are prompt edits in `/admin/prompts` needing no redeploy. Decide
   before phase 3 renders the phrase.
2. **The phrase is copied verbatim into every later parcours analysis prompt** via
   `prompt_context()` (phase 5 wiring). Whatever the model wrote once travels everywhere;
   the no-digit invariant is only tested against a clean literal.
3. **Admin selector copy.** The labels now read « Parcours 1 · J'ai une cible », « Voyage ·
   phrase (S0) », « Voyage · portrait », taken byte-for-byte from `prompt_slots.LABELS`. If
   shorter chips were wanted, shorten the five values in `prompt_slots.py` — the TS side
   must follow, not diverge.
4. **Phase 0's two open copy items are still open:** `Besoin dominant : competence` reaches
   the model unaccented, and the cahier-vs-ban-list question.

## Known, accepted, not done

- **`npm run lint` fails on `initial` with `✖ 10 problems (5 errors, 5 warnings)`, and did
  so before this phase.** `npm run build` passes. One of those errors is inside
  `admin/prompts/page.tsx` and was deliberately left alone — a drive-by fix to an effect,
  inside a task about a selector, is how an unrelated regression ships under a green review.
- **`_run_micro` / `_run_portrait` are ~90% duplicated**, as are `_fail_micro` /
  `_fail_portrait`. The whole-branch review confirmed they have **not** drifted — a
  normalised diff shows only intended deltas — but it is a standing drift surface.
- **No `micro_started_at` / `portrait_started_at`.** This phase adds no migration by design.
- **`_parse_sections`' `repair_json` rung** is the only thing that rescues a payload
  truncated at `max_tokens`, which is the realistic failure for six prose sections at 3000
  tokens. It is now tested; do not remove it as redundant.

## Process notes worth keeping

Five defect classes recurred, and the same technique caught all of them: **demand a proof,
not an opinion.**

1. **Tests that cannot fail.** Two fix fixtures the controller wrote were non-discriminating
   — three leak words whose declaration order equals their alphabetical order, and `""`
   where only whitespace is truthy. Both were caught by an implementer told to prove the
   test fails when its subject breaks.
2. **Guards nothing asserts.** The API-key fixture shipped with a commit message saying
   "verified, not assumed" — verified by a throwaway probe that was then deleted. Removing
   the fixture left the suite green.
3. **Substring containment.** `"Voyage · portrait"` is a substring of « … complet »; `trait`
   is not a substring match for « traits ». Containment checks pass on the wrong thing in
   both directions.
4. **Negative claims.** "Nothing writes this row after S5" was false, and no passing suite
   can contradict a negative claim — only a probe against the live route found it.
5. **False greens.** A "no FAILED lines" filter scored a `SyntaxError` as a pass. Every
   later dispatch had to assert on the presence of an `N passed` / `N failed` summary line.

The most expensive single lesson: **a ruling that creates a new state must ship the way out
of it in the same breath.** R22 added the reaper and manufactured `"error"` rows without
checking that anything could leave `"error"`.
