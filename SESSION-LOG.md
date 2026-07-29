# Autonomous session log — 2026-07-29

Running Phases 0→4 of `plan.md` unattended. This file is the catch-up: what I
decided on your behalf, what I found, and anything you need to act on.

**Read "Needs you" first.** Everything else is FYI.

---

## Needs you

### 1. Set `FIELD_ENCRYPTION_KEYS` on Render before real users exist

Bloc 5 and the OETH flag are encrypted at rest. Without that env var the key is
derived from `SECRET_KEY` via HKDF — which works, but means **rotating
`SECRET_KEY` makes every encrypted profile unreadable**. Generate and set it:

```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Render → Environment → FIELD_ENCRYPTION_KEYS=<that value>
```

Rotation later: prepend a new key, comma-separated. The first key encrypts, all
keys are tried on decrypt.

### 2. Unlock endpoint still has no rate limit

`POST /analyses/<id>/unlock` is now ownership-gated, but a counselor code is 8
chars of `[A-Z0-9]` and there is no attempt limit. Proper fix is `flask-limiter`
(a new dependency). I did **not** add it mid-schema-refactor — that's a deploy
risk I didn't want to take unattended. Worth doing before the codes go to real
Cap Emploi counselors.

### 3. Still outstanding from the PM (unchanged)

- The 3 prompt texts (P1 v1.8, P2 v1.0, P3 v1.0). Admin UI is ready and now has
  three slots; admins paste. **Parcours 2 and 3 will error until their prompts
  exist** — there is no fallback, by design (B2G traceability).
- Anthropic DPA signature — blocks real-user testing regardless of build state.
- Premium price. Built configurable so it isn't blocking.
- Owner of the aménagements / dispositifs reference list.

---

## Decisions I made for you

| # | Decision | Why |
|---|---|---|
| 1 | §4 moved to paid; marketing copy + CGV updated | CDC §4 defines free as §1–§3 + verdict. You confirmed. `a2acea2` |
| 2 | Free tier = §1, §2, §3, verdict. Paid = §1–§9. Premium = +§10, §11 | Straight from CDC §4 |
| 3 | Parcours ids are `'1'/'2'/'3'`, not `'P1'` etc. | `PromptVersion.path` is `String(1)` — single chars fit, so no width migration and no risk on an ALTER |
| 4 | Legacy `A`/`B` absorbed on read, not rewritten in the DB | `Analysis.inputs` is a JSON blob; rewriting `_path` per row needs a MySQL-only `JSON_SET` that SQLite can't run. `normalize()` on both sides costs nothing |
| 5 | Tier vocabulary moved from model nicknames to plan names (`haiku`→`free`, `sonnet`→`paid`) | The nickname stopped meaning anything once a tier could change model. Old values still resolve |
| 6 | Premium `max_tokens` = 20000, not 8000 | Opus 5 thinks by default and thinking counts against the cap; 8000 truncates an 11-section report |
| 7 | Sonnet billed at list `$3/$15`, not the promo `$2/$10` | Promo ends 2026-08-31; list price means the dashboard never under-reports a month |
| 8 | Profile split into two tables, not nullable columns on one | A DB export or admin query over `profiles` then cannot surface the sensitive half at all |
| 9 | The `sensitive_profiles` row is created even when OETH is false | If it only existed for people who ticked the box, row presence alone identifies them |
| 10 | No endpoint returns the OETH flag — not even to its owner | Nothing anywhere differs based on it; that's what makes the promise testable |
| 11 | Ownerless analyses stay readable by id | The anonymous flow polls before an account exists. Phase 1 kills this branch |
| 12 | Counselor sets for parcours 2 and 3 chosen by me (`A,B,F` / `I,III,V`) | Neither doc specifies them. Parcours 1's `1,4,5` is from the spec |

---

## Progress

| Phase | Status | Commit |
|---|---|---|
| 0.1 Section registry | done | `19fdcb3` |
| — free-tier copy realignment | done | `a2acea2` |
| 0.2 A/B → 3 parcours | done | `b7c8b58` |
| 0.4 Third tier + model routing | done | `4a723bc` |
| 0.3 Profile + encryption | done | `8829d14` |
| 0.5 Analysis IDOR | done | `bda975e` |
| 0.6 Migration verification | done | — |
| 1 Profil de base (UI) | in progress | |
| 2 Three parcours | pending | |
| 3 Tiers + monetization | pending | |
| 4 Output + compliance | pending | |

Backend: 82 tests passing (was 44). Frontend: `tsc` clean, `next build` clean.

---

## Findings worth knowing

**Three silent failures fixed in 0.1.** All would have produced wrong output
with no error:
- `rapport/page.tsx` sorted section keys with `Number(a) - Number(b)`. For `"A"`
  or `"IV"` that's `NaN`, so the comparator ordered nothing and V8 left the array
  in insertion order.
- `_parse_output` gated JSON validity on `any(k.isdigit())` — letter-keyed output
  failed the check and collapsed the whole report into one section.
- The heading regex captured a single digit, so §10, §A and §VI never matched.

**Two live bugs found and fixed.**
- The counselor filter was hardcoded to `("1","4","5")` for every path while the
  frontend asked for `["1","2","8"]` on path B — Chemin B share links have been
  rendering three empty skeletons.
- Admin stats did `filter_by(is_active=True).first()` with no path filter, so the
  "prompt actif" KPI showed whichever row the DB happened to return first.

**`/analyse/orientation` has never been linked from anywhere.** Every CTA on the
landing, nav, footer, AppBar and espace points at `/analyse/nouveau`. The second
parcours was already unreachable before a third existed. Phase 2 adds the chooser.

**Migrations verified.** All three new ones round-trip up and down on SQLite. The
full chain can't be exercised locally — `fd6e96d0d77c` is MySQL-only raw SQL —
so the enum widening (`d4e5f6a7b8c9`) is the one step only production will run.
It's a standard Alembic `alter_column` on a native MySQL ENUM.

**Pre-existing issues left alone** (documented in `plan.md`): the daemon-thread
analysis runner whose boot sweep kills the other gunicorn worker's in-flight
generations; `proxy.ts` exporting `proxyConfig` where Next 16 expects `config`;
`litellm` and `resend` installed but imported nowhere.
