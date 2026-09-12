# Le voyage — phase 3 handoff

Phase 3 (the candidate UI) is complete and merged into `initial` **locally**. 25 commits (`7dfee96..` this handoff),
**764 backend tests**, 0 failures. `npm run build` passes; `npm run lint` is exactly the
pre-existing `✖ 10 problems (5 errors, 5 warnings)`. Nothing is pushed; nothing is deployed.

**Spec:** `docs/superpowers/specs/2026-09-09-voyage-design.md`
**Contract:** `docs/superpowers/plans/2026-09-09-voyage-contracts.md`
**Plan:** `docs/superpowers/plans/2026-09-09-voyage-phase-3-candidate-ui.md` — **read with the rulings**:
the plan was audited before execution (4 lenses, ~70 findings) and ~35 rulings overrode it. The
full ledger — every ruling, its cost-if-wrong, every review and mutation scoreboard — is in the
git-ignored `.superpowers/sdd/2026-09-09-voyage-phase-3-candidate-ui/progress.md` (with
`rulings-preflight.md` beside it); the decisions a later reader needs are below.

## ⚠️ Push gate

**Do not deploy phase 3 without phase 5.** The chrome says the voyage « enrichit toutes vos
analyses »; the injection that makes that true is phase 5. Pushing `initial` deploys production.

## Before the voyage works on any database

The voyage needs its schema and its two prompts. Neither is automatic:

```bash
# local stack
docker compose exec backend flask db upgrade          # b8c9d0e1f2a3 -> a3b4c5d6e7f8 (5 migrations)
docker compose exec backend python seed_prompt_v10_voyage_micro.py
docker compose exec backend python seed_prompt_v10_voyage_portrait.py
# VPS: same two steps with -f docker-compose.prod.yml (DOCKER.md's seed loop)
```

Symptom when the migrations are missing: **every** `/api/voyage` call AND `/api/analyses/`
answer 500 — `Table 'neoori.voyages' doesn't exist` and `Unknown column 'analyses.voyage_id'`,
because `Analysis` selects the new column. The hub then shows its load-error screen, which is
correct behaviour, not a UI bug. Symptom when the seeds are missing: session 0 completes but the
phrase fails with « Aucun prompt actif pour le slot voyage_micro » (now retryable).

## What exists

| File | Contents |
|---|---|
| `frontend/src/types/voyage.ts` | Contract § I types, `PORTRAIT_SECTIONS`, `LOCK_*`, `sessionLock()` (trims like Python), `CounselorPortrait.error?` |
| `frontend/src/lib/voyage.ts` | Typed wrappers incl. `retryMicro()`, `missingItems()`, `errorStatus()` |
| `frontend/src/lib/api.ts` | `ApiError.body`; message = `error ?? errors[0] ?? message ?? fallback` (app-wide) |
| `frontend/src/components/voyage/*` | `SessionProgress`, `MicroReveal` (spinner / stalled / success / error + « Réessayer »), `ChecklistRow`, `OptionCard`, `SceneCard`, `BilletForm` (1000-char cap) |
| `frontend/src/app/voyage/page.tsx` | Hub: consent gate, stamps, code entry, phrase polling with a 3-min ceiling, retry, **counselor share-link card**, portrait status, erasure |
| `frontend/src/app/voyage/session/[n]/page.tsx` | Player: resume, save on « Suivant », S0 per-row saves, read-only finished sessions, lock remedies |
| `frontend/src/app/voyage/portrait/page.tsx` | Validated portrait on `.report-shell`, printable |
| `AppBar`, `/analyse`, `/espace`, landing `page.tsx` | The four entry points |
| `frontend/src/proxy.ts`, `globals.css` | `/voyage` protected; `.voyage-rule` |
| `backend/tests/test_voyage_parity.py` | Python ↔ TS, exact equality: lock strings, portrait sections, `BILLET_MAX_CHARS`, and `MICRO_RETRY_STALE_MINUTES` vs the hub's `POLL_MAX_MS` |
| `backend/app/services/voyage/generation.py` | Phrase leak check + one corrective retry |
| `backend/app/routes/voyage.py` | `POST /micro/retry`; regenerate accepts a stale portrait; billet cap; finished sessions read-only; no-op PUT writes nothing |
| `TEST-PLAN.md` | « § 12 · Le voyage » — the PM's manual pass |

## Backend added in this phase (not in the plan — PM decisions + audit)

- **The phrase is leak-checked (PM-Q1).** Same 17-pattern `leak_check()` as the portrait; one
  corrective retry; still leaking or retry failed → `micro_status="error"` and **the text is never
  stored** (no human gate on the phrase, unlike the portrait). Invariant: `micro_phrase` is non-None
  only on a `success` row (`_fail_micro` drops `phrase`) — except a transient twin-run window, below.
- **`POST /api/voyage/micro/retry` (PM-Q2)** → `202 {voyage}`. Accepts `error`, or `generating` whose
  `updated_at` is older than `MICRO_RETRY_STALE_MINUTES = 3` (the hub's poll ceiling). 409 otherwise;
  404 no voyage; 409 before S0 is complete. Stamps `updated_at` on accept so a double click cannot
  spawn twice. Not a contract route — contract § E has no E17; treat this handoff as the amendment.
- **Counselor regenerate also accepts a stale `generating` portrait** (`PORTRAIT_RETRY_STALE_MINUTES
  = 10`). Without it the hub's "prend plus de temps" message would point at a counselor who cannot act.
- **Billets are capped:** 1000 characters per field, plus a backstop when the ciphertext would exceed
  MySQL `TEXT` (65535) — strict mode raises error 1406, which SQLite never reproduces.
- **A completed session is read-only on the server** (409), checked before the locks.
- **A PUT that changes nothing writes nothing** (contract § E5's "no-op 200" made literal) — it no
  longer re-encrypts, commits and moves `updated_at`.

## Decisions a future reader will otherwise trip over

- **The share link is the only way a counselor reaches a voyage** (spec "For the PM" #7). The hub shows
  `${origin}/voyage/c/${share_token}` once the voyage is `termine`. The link alone opens nothing —
  the counselor route needs role **and** token. Remove the card and no portrait is ever validated.
- **A failed read never looks like "no voyage".** A missing voyage is `200 {voyage: null}` and a
  missing profile `200 {profile: null}`, so the pages treat every rejection as a load error. The hub's
  first version cleared its error before refetching and showed the consent form mid-retry; on a
  finished voyage that is a 201 retake that hides the validated portrait. Never clear a load error
  before the reload succeeds.
- **The hub stops polling after 3 minutes** of continuous `generating` (backoff 4 s on a failed read)
  and restarts the streak whenever the status pair changes.
- **Loaders wait for auth** (`!authLoading && user`), so an expired session takes the page's own
  `/connexion?redirect=…` guard rather than `api.ts`'s bare redirect.
- **A finished session opens at step 0, read-only**, never on a lock screen, and « Suivant » never saves.
- **Inputs freeze while « Suivant » saves** (the scene, and the S0 rows during their reconcile save):
  otherwise the answer scored can differ from the last one shown.
- **`/espace` shows the phrase teaser only when `micro_status == "success"`.** The backend invariant
  "a phrase only on a success row" has two known holes (twin-run window, reaper); the UI does not rely on it.
- **The hub's poll ceiling must stay ≥ the server's retry threshold** (3 min both) or « Réessayer »
  409s after the spinner gives up; the parity test pins the pair.
- **« Ce qu'il révèle » was removed** from the `/analyse` card although the spec prescribes it: the
  contract reads the copy ban by root. Chrome is gender-neutral (« en autonomie », not « seul »).
- **No retake button.** `GET /api/voyage/portrait` resolves to the newest open voyage, so a retake
  would hide a validated portrait. PM item below.

## What phase 4 must know

- The candidate hands the counselor `/voyage/c/<share_token>`; phase 4 builds that page.
- `CounselorPortrait` carries `error` on error rows (shipped in phase 2, typed here).
- Regenerate accepts `draft`, `error`, or `generating` older than 10 minutes.
- **The shared `updated_at` clock:** a candidate's phrase retry and `_run_micro`'s commits defer a
  stalled portrait's 10-minute relaunch; counselor regenerate/edit/validate and `_run_portrait` defer
  the phrase's 3-minute retry. Documented in `reap_stale_generating`'s docstring. The durable fix is
  per-run timestamps (`micro_started_at` / `portrait_started_at`) with the next migration.

## What phase 5 must know

- The push gate above.
- A phrase refused for vocabulary is never stored, so `Voyage.for_prompt()` cannot select it.

## TEST-PLAN § 12 recipes that need the local stack

- Forcing a phrase failure (to test « Réessayer ») is **local only**: an invalid `ANTHROPIC_API_KEY`,
  finish S0, restore the key, restart, retry. `/admin/prompts` cannot deactivate a prompt — never
  tamper with the production prompt to test this.
- The load-error screen is reached by stopping the backend and navigating from the account menu
  **without reloading** — a reload fails `/auth/me` first and redirects to `/connexion`.

## Open, needing the PM

1. **Add `RÈGLE DÉFICIT` to the active `voyage_micro` prompt in `/admin/prompts`** (PM-Q1). The seed
   script was deliberately not edited.
2. **Retake:** no CTA; decide whether v1 offers one, and if so `GET /portrait` must serve the latest
   *validated* portrait.
3. **`DELETE /api/voyage` erases only the current voyage**; an older finished one resurfaces on the hub
   afterwards (phase-1 open item 5, now visible).
4. **Phase-0 intro inconsistency** is now on screen: sessions 0–2 end their intro with an instruction
   line, 3–5 do not.
5. Carried: `Besoin dominant : competence` unaccented; the cahier-vs-ban-list question.

## Known, accepted, not done

- **No live browser walk was done.** Completing S0 bills a real Anthropic call on the app's key.
  The pages were proven by execution harnesses instead; TEST-PLAN § 12 is the manual pass.
- `npm run lint` still reports the pre-existing 10 problems; one sits in `espace/page.tsx`, a file this
  phase edited, and was deliberately left alone.
- Transient twin-run window: if a stale phrase retry races a slow original run, the twin's pre-stream
  write can carry the first run's phrase onto a `generating` row for one stream. Fixing it in
  `Voyage.micro_phrase` touches the model contract (§ C.4).
- A first phrase call raising with an empty message records `""` as the reason (status is correctly
  `error`); the same `str(exc) or type(exc).__name__` fallback as the corrective call would fix it.
- « Le portrait ne peut plus être régénéré. » reads oddly for a fresh `generating` portrait
  (counselor-facing; phase 4 may reword).
- The parity test's regex expects double-quoted single-line declarations (a reformat fails as "could not
  find declaration", still loud); a duplicate same-named declaration is caught by `tsc`, not the regex.
- A later successful save clears an earlier failure's message (the S0 « Suivant » resend covers the data);
  signing up from `/connexion?redirect=…` drops the redirect; `/profil` does not honour `?redirect=`.
- The `ApiError` change surfaces a pre-existing snake_case server message on `/profil`
  (« reconversion_scope ne s'applique… »).
- `_run_micro` / `_run_portrait` duplication (phase 2) grew with the phrase retry helper.
- Test warnings grew with the suite (the pre-existing `datetime.utcnow` deprecation class).

## Process notes worth keeping

- **The audit paid for itself.** Four lenses found the plan's only red→green test did not exist, a
  manual row that would have invited weakening the order lock, an invisible landing logo, and — most
  expensive — that no screen gave the counselor the link, so every portrait would have stayed `draft`
  forever.
- **Execution harnesses replace the missing frontend runner.** Reviewers compiled the real pages with
  the repo's TypeScript and ran them in React 19.2 in node with a fake DOM (stubbed API/auth/router).
  That is how the consent-form-during-retry hole and the answer-changed-while-saving race were found.
- **A harness that crashes is not a harness that fails.** One "caught" mutation was a TypeError from
  clicking a button that no longer existed; another mutation tested a different defect from the one
  it named. Both were rebuilt to fail by assertion.
- **Empty exception messages are falsy.** `TimeoutError()` has `str(exc) == ""`; branching on the
  error string committed an empty phrase as `success`. Branch on the result, not on the message.
