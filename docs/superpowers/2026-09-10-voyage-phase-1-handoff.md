# Le voyage — phase 1 handoff

Phase 1 (models, migrations, encryption, routes) is complete and merged into `initial` locally.
23 commits, 374 tests, 0 failures, 0 errors, 0 deselected. **Nothing is pushed; nothing is deployed.**

**Spec:** `docs/superpowers/specs/2026-09-09-voyage-design.md`
**Contract:** `docs/superpowers/plans/2026-09-09-voyage-contracts.md`
**Phase-0 handoff:** `docs/superpowers/2026-09-10-voyage-phase-0-handoff.md`
**Plans for phases 2–5:** `docs/superpowers/plans/2026-09-09-voyage-phase-{2..5}-*.md`

Suite went 232 → 374. Phase 0's 87 tests plus 142 added here.

## What exists now

| File | Contents |
|---|---|
| `backend/app/models/voyage.py` | `Voyage`, `VoyageNote`, `session_lock()`, status constants, `to_dict()` (exactly 12 keys), `synthesis()` |
| `backend/app/routes/voyage.py` | 16 handlers — candidate surface (bank, read, create, erase, responses, complete, unlock, portrait) and counselor surface (sheet, notes, portrait edit/validate) |
| `backend/app/services/prompt_slots.py` | The five prompt slots, French labels, `normalize()` |
| `backend/migrations/versions/` | `c9d0e1f2a3b4`, `d0e1f2a3b4c5`, `e1f2a3b4c5d6`, `f2a3b4c5d6e7` — head is `f2a3b4c5d6e7` |
| `backend/app/routes/admin.py` | Role endpoint + four voyage KPIs (`started`, `s0_done`, `completed`, `validated`) |

Encryption follows the `SensitiveProfile` precedent exactly: Fernet tokens in `db.Text` columns named `<thing>_encrypted`, exposed through property/setter pairs. `crypto.DecryptionError` propagates.

## Verified, not assumed

Every claim below was produced by running code, not reading it.

- **No scoring key reaches a candidate.** `GET /api/voyage/bank` serves `bank.public()`; a recursive walk of 1113 nodes found zero weight keys. A planted `snapshot: {"riasec": "SECRET"}` survives in ciphertext and appears in no response.
- **The counselor gate needs role AND token.** Both halves are pinned by mutation: replacing `Voyage.by_token(token)` with `Voyage.query.first()` at all 6 sites fails 2 tests; stripping `role_required` fails 3.
- **Every candidate handler is owner-scoped, and each is pinned.** Mutating `_current()` to an unscoped query, one site at a time, fails a test for all 7 handlers.
- **`bank.py` imports nothing; `scoring.py` imports only `bank`** — verified with `ast.parse`, not grep (bank.py's docstring has import-lookalike lines).
- **Migrations round-trip** 16 up / 16 down / 16 up on SQLite, exactly one head.
- **"Never required" holds.** The non-voyage suites pass alone (246), and no existing `to_dict()` caller branches on `voyage_id`.

## Decisions a future reader will otherwise re-litigate

- **`has_code` is `bool(counselor_code_id)`; unlock is permanent.** Contract § C.5:919 pins it, and § E7 refuses an inactive code at *unlock* time. A Cap Emploi beneficiary must not lose a half-finished voyage to a rotated code. Do not add a continuous `is_active` check.
- **Unknown item ids on `PUT /responses` are dropped silently** (§ E5:1119), while a *known* id with an invalid value is a 400. A bank edit un-scores old items, so a stale client would otherwise lose a whole session's work.
- **A coercer is not a validator.** `prompt_slots.normalize()` defaults unknown input to parcours `'1'` — right for rendering an old stored row, catastrophic for client input. Using it to validate made the 400 branch unreachable and let a typo silently overwrite the live parcours-1 prompt. `routes/prompts.py:_read_path` now validates before defaulting; the comment says why.
- **`oui`/`non`/`resultant` are forwarded raw and do not sum.** § B.5's own example is non-summing. Presentation is phase 4's problem.
- **Non-scalar values are refused, not coerced**, in billets, notes and portrait sections. Stringifying them puts `"{'nested': 'x'}"` into the portrait a person reads and into the prompt as their own words.

## What phase 2 must know

- `_spawn_micro` / `_spawn_portrait` fire strictly **after** `db.session.commit()` (`voyage.py:298-305`), so no request-thread connection is held across them. Keep it that way: never hold a DB connection across an Anthropic stream (`anthropic_service.py:463-472` is the pattern).
- The seam takes the `ImportError` branch today because `services/voyage/generation.py` does not exist. It is monkeypatchable by name, which is how the tests pin it.
- `synthesis()` and `crypto` need no Flask app context — phase 2 calls them from a background thread.
- **Phase 2's plan Tasks 1–2 are verification, not creation.** Phase 1 already owns `prompt_slots.py` and the prompts route. Both tasks carry an inline warning; the Task 2 block still contains the defective `_read_path`. Do not re-apply it.

## Open, needing a decision

1. **`analyses.voyage_id` has no `ondelete`, and erase hard-deletes.** Unreachable in phase 1 (nothing writes the column), live the moment phase 5 does. With `PRAGMA foreign_keys=ON` and a populated `voyage_id`, `DELETE /api/voyage` raises an **uncaught `IntegrityError`** — a 500 on the user's right-to-erasure path, leaving a failed transaction. SQLite has FK enforcement off, so no local test can catch it; MySQL will. Phase 5 needs `ondelete="SET NULL"` or must null the column first, plus a `try/except` at `voyage.py:128`.
2. **Add `PRAGMA foreign_keys=ON` to `tests/conftest.py`** at the start of phase 5 — three lines, pins every FK in the repo, and the suite already passes with it.
3. **`request.get_json(silent=True) or {}` at 12 pre-existing non-voyage sites** (auth ×2, payments ×2, analyses ×4, admin, profile, counselor, prompts). A JSON array or bare string is valid JSON and truthy, so the next `.get()` raises `AttributeError`. Verified live: `POST /api/auth/login` with `[1,2,3]` is an unhandled 500 today on neoori.tech. Not introduced here — the voyage code is the only part now free of it. Options: fix the 12 sites, or register a global error handler.
4. **Two pre-existing model/migration FK gaps** — `price_feedback` and `sensitive_profiles` declare `ondelete='CASCADE'` in the migration but not on the model.
5. **`DELETE /api/voyage` erases only the *current* voyage** (contract-compliant, § E9:1175). An earlier retake survives and its share token still serves the full synthesis to a counselor. "Erase all and revoke tokens" is a PM question.
6. Carried from phase 0 and still open: `Besoin dominant : competence` reaches the model unaccented (needs a § H amendment before phase 5); the cahier's six ban-list words; `scoring_version` staleness has no surface on the sheet (§ E10 caps it at seven keys).

## Process notes worth keeping

- **Reviewers must exercise HTTP endpoints, not just read diffs.** Every one of the three production defects found in this phase — the silent prompt overwrite, the JSON-body 500, the note wipe — was invisible to reading and found in minutes by sending hostile input. Five reading-based audit lenses missed the first one.
- **A green suite can conceal an untested security property.** Mutating `by_token` left 97/97 green because every test ran in a single-voyage database. Ask of each access-control test: would it fail if the check were removed? Then check by mutating.
- **Only one implementer may hold the working tree at a time.** Two concurrent implementers caused one agent's commit to absorb another's uncommitted work. Reviewers may overlap — they never commit, and carry a read-only-git ban.

---

## Addendum — the two open items, closed (2026-09-10)

Both items the phase-1 review left open have been fixed and verified. Suite 374 → **591 passed**.

### 1. `analyses.voyage_id` FK and the erasure 500

- `ondelete="SET NULL"` on the model, migration `a3b4c5d6e7f8` (head).
- `delete_voyage` guards `IntegrityError` → French 409 with a rollback, so a database-level
  failure can never leave a failed transaction on the session.
- `tests/conftest.py` now enables SQLite foreign keys via a connect listener. **This was not
  free**: it exposed six tests asserting behaviour against a `Voyage` row whose
  `counselor_code_id` pointed at a code that never existed — a row MySQL would reject. Fixed to
  create real codes.
- Verified by mutation: reverting `ondelete` makes
  `test_deleting_a_voyage_still_referenced_by_an_analysis_sets_it_null` fail.

Still open, same shape, no delete path touches it today: `Voyage.counselor_code_id`.

### 2. The unhandled-500 class — nine vectors, not one

The 12 `get_json(...) or {}` sites were the visible part. Fuzzing every body-reading route with
hostile field values found the class was wider:

| Site | Vector |
|---|---|
| `auth` register/login | non-string `password` — a list reached **bcrypt** before failing |
| `analyses` | non-dict `inputs` (`dict(5)`); hostile values inside `inputs.*`; `draft_id` into a raw `filter_by()`; hostile `tier` into `tiers.normalize`; unhashable `_path` into `section_registry.normalize` |
| `profile` | non-string fields into `.strip()` |
| `payments` | non-scalar `analysis_id` into `get_or_404()` — **masked in tests** by the 503 that fires when `STRIPE_SECRET_KEY` is unset |
| `prompts` | non-bool `activate` into a strict Boolean column |
| `counselor` | a malformed PUT wiped a private note behind a 200 (data loss, not a 500) |

`backend/app/utils/request_body.py` holds `json_object()`, `text_field()` (trimmed),
`raw_text_field()` (verbatim — passwords, where whitespace is significant) and `dict_field()`.

**`backend/tests/test_no_500_on_hostile_input.py` is the durable part**: a table-driven fuzz over
every body-reading route asserting no 5xx and no escaped exception. Adding a route means adding a
row. It fails on 33 cases against the pre-fix code.

Verified independently of the implementer: 215 probes, 0 crashes; valid flows unchanged; and a
password of `"  motdepasse  "` still authenticates while `"motdepasse"` does not, proving
`raw_text_field` does not strip.

One vector on my list was **wrong** and the implementer corrected it: `verify`'s `session_id`
never crashed, because `payments.py` already wraps `Session.retrieve()` in `try/except Exception`.
Guarded anyway for symmetry with `checkout`.

### Found while fuzzing — relevant to phase 2, not fixed

`anthropic_service._run_analysis` builds its prompt message **outside** its `try/except`. A hostile
profile-merged field could therefore kill the background generation thread silently — the request
already returned 201, so nothing surfaces as an HTTP error and the analysis just never completes.
Different bug class from the above, and that file's connection-lifecycle code is delicate, so it
was deliberately left alone. **Phase 2 adds two more background generation threads on this exact
pattern — fix it there.**
