# Autonomous session log — 2026-07-29

Ran Phases 0→4 of `plan.md` unattended. This is the catch-up: what I decided on
your behalf, what I found, what's left.

**Read "Needs you" first.** Everything else is FYI.

Everything is committed and pushed to `initial`, so Vercel and Render have
already redeployed. Backend **106 tests passing** (was 44). Frontend `tsc` and
`next build` both clean.

---

## Needs you

### 1. Set `FIELD_ENCRYPTION_KEYS` on Render — do this before real users

Bloc 5 and the OETH flag are encrypted at rest. Without that env var the key is
derived from `SECRET_KEY`, which works, but means **rotating `SECRET_KEY` makes
every encrypted profile permanently unreadable**.

```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Render → Environment → FIELD_ENCRYPTION_KEYS=<that value>
```

Rotation later: prepend a new key, comma-separated. First key encrypts, all keys
are tried on decrypt.

### 2. Two prices are now env vars — set them or accept the defaults

| Var | Default | Note |
|---|---|---|
| `PAID_PRICE_EUR_CENTS` | `900` | unchanged behaviour |
| `PREMIUM_PRICE_EUR_CENTS` | `2400` | **I picked this.** PM said "2–3× the paid tier, to calibrate on first buyers" — 24 € is the middle. Change it whenever; it's config, not a deploy. |

### 3. The three prompts are the last blocker for parcours 2 and 3

The admin editor now has three slots (`/admin/prompts`, P1/P2/P3). **Parcours 2
and 3 will error until their prompts exist** — there is no fallback, deliberately,
because every analysis stores its `prompt_version_id` for B2G traceability.

Parcours 1 keeps working on its existing prompt, but it should be updated too:
the free tier is now §1–§3 + verdict, and §10/§11 exist for Premium.

### 4. Still outstanding, unchanged

- **Anthropic DPA** — blocks real-user testing regardless of build state. I can't
  sign it; it needs an authorised person on your Anthropic account.
- **Unlock rate limit.** `POST /analyses/<id>/unlock` is ownership-gated now, but
  a counselor code is 8 chars of `[A-Z0-9]` with no attempt limit. Proper fix is
  `flask-limiter`; I did not add a dependency mid-schema-refactor unattended.
- **Carlito** (charter body font) is not on Google Fonts. Needs `next/font/local`
  and a self-hosted woff2 in `public/`. Everything else in the charter is applied.
- **Owner of the aménagements / dispositifs reference list.** Unowned, it will
  eventually cite a scheme that no longer exists.

### 5. Two things I'd flag to the PM when they next look

- **The free tier narrowed** (§4 moved to paid). Marketing copy *and the CGV* now
  say so. That's a contract change — worth them confirming.
- **Accounts are now effectively required** for the profile. Anonymous analysis
  still works, but a Profil de base needs a login. Neither doc says so explicitly;
  it follows from the persistent-profile decision.

---

## Decisions I made for you

| # | Decision | Why |
|---|---|---|
| 1 | Free = §1, §2, §3, verdict. Paid = §1–§9. Premium = +§10, §11 | Straight from CDC §4 |
| 2 | Parcours ids are `'1'/'2'/'3'` | `PromptVersion.path` is `String(1)` — single chars fit, so no width migration and no risky ALTER |
| 3 | Legacy `A`/`B` absorbed on read, not rewritten in the DB | `Analysis.inputs` is a JSON blob; rewriting `_path` per row needs a MySQL-only `JSON_SET` SQLite can't run |
| 4 | Tier vocabulary: model nicknames → plan names (`haiku`→`free`) | The nickname stopped meaning anything once a tier could change model |
| 5 | Premium `max_tokens` = 20000 | Opus 5 thinks by default and thinking counts against the cap; 8000 truncates an 11-section report |
| 6 | Sonnet billed at list `$3/$15`, not promo `$2/$10` | Promo ends 2026-08-31; list price means the dashboard never under-reports |
| 7 | Profile split across two tables, not nullable columns | A DB export or admin query over `profiles` then can't surface the sensitive half at all |
| 8 | `sensitive_profiles` row created even when OETH is false | Row presence alone would otherwise identify who ticked the box |
| 9 | OETH **is** returned — but only on the sensitive endpoint | See "changed my mind" below |
| 10 | Counselor sets for P2/P3 chosen by me (`A,B,F` / `I,III,V`) | Neither doc specifies them; P1's `1,4,5` is from the spec |
| 11 | P3 answer thresholds lower than P2's (10 vs 20 chars) | P3 exists for people without a CV; a long-answer requirement is the barrier it removes |
| 12 | `--orange` stays charter `#EA5624`, `--primary` is a darkened `#C9491E` | Charter orange is **3.59:1** on white — below AA for text and for white-on-orange buttons |
| 13 | Teal is an accent, not a text colour (4.17:1) | Same reason |
| 14 | Premium default 24 € | Middle of the PM's stated 2–3× range |

### One decision I reversed mid-build

I first made the OETH flag write-only — never returned by any endpoint, so no
response anywhere could differ based on it. That was wrong: re-saving a profile
would silently clear a status that governs the person's rights.

The rule in the Parcours doc is *"elle ne déclenche rien de visible"* — no
**reaction**. Handing someone their own stored answer back so the checkbox
renders as they left it is persistence, not a reaction. It now travels only on
`/profile/conditions`, never on the ordinary profile payload, and a test pins
that.

---

## What shipped

| Phase | Commit |
|---|---|
| 0.1 Section registry | `19fdcb3` |
| — free-tier copy + CGV | `a2acea2` |
| 0.2 A/B → 3 parcours | `b7c8b58` |
| 0.4 Premium tier + model routing | `4a723bc` |
| 0.3 Profile + field encryption | `8829d14` |
| 0.5 Analysis IDOR | `bda975e` |
| 1 Profil de base (6 blocks, matrix, live synthesis) | `a1054fc` |
| 2.1 Parcours 2/3 backend | `ec6dd21` |
| 2.2–2.3 Chooser + both forms | `103646d` |
| 4.1 Graphic charter + print fixes | `ce84613` |
| 3 Willingness-to-pay probe | `03589bd` |
| 3 Premium checkout | `883a6af` |

### Not done

- **§10 / §11 content** — they're in the section registry and the schema, so they
  generate as soon as the Premium prompt exists. Nothing further to build.
- **Counselor referral 48h button** — one line in the CDC, no spec behind it. I
  didn't invent a workflow.
- **Two PDFs on P1 paid** — the counselor view is still component state rather
  than a URL param, so `?print=1` can only produce the candidate report. Needs a
  small routing change.
- **Voyage / portrait / Conseiller chat / groupes** — separate programme.

---

## Findings worth knowing

**Three silent failures fixed in 0.1.** All would have produced wrong output with
no error:
- `rapport/page.tsx` sorted keys with `Number(a) - Number(b)`. For `"A"` or `"IV"`
  that's `NaN`, so the comparator ordered nothing and V8 left insertion order.
- `_parse_output` gated validity on `any(k.isdigit())` — letter-keyed output
  failed and collapsed the whole report into one section.
- The heading regex captured a single digit, so §10, §A and §VI never matched.

**Three live bugs found and fixed.**
- Counselor filter hardcoded to `("1","4","5")` for every path while the frontend
  asked for `["1","2","8"]` on path B — Chemin B share links have been rendering
  three empty skeletons.
- Admin stats did `filter_by(is_active=True).first()` with no path filter, so the
  "prompt actif" KPI showed whichever row the DB returned first.
- `GET /api/analyses/<id>` had no auth and returned the raw inputs blob. Any
  caller with an id could read any analysis; delete and code-unlock had the same
  gap.

**`/analyse/orientation` had never been linked from anywhere.** Every CTA pointed
at `/analyse/nouveau`. The second parcours was unreachable before a third existed.
The chooser at `/analyse` is now the conversion target (12 CTAs repointed).

**The palette had drifted from the repo's own design spec.**
`docs/superpowers/specs/2026-06-14-neoori-brand-redesign-design.md` already
specified `#ea5624` / `#1c3561`; the shipped CSS had `#ff7a39` / `#0f1e34` and no
teal. Charter values are applied now, including the literals that bypass the token
system (mesh, shadows, Logo.tsx, favicon, PWA theme colour).

**`.report-shell` was 600×900** — a 2:3 ratio, not A4's 1:1.414 — with
`overflow:hidden` clipping anything flowing to page 2. Both fixed.

**Migrations.** Five new ones, all round-tripped up and down on SQLite. The full
chain can't run locally (`fd6e96d0d77c` is MySQL-only raw SQL), so the enum
widening in `d4e5f6a7b8c9` is the one step only production exercises — it's a
standard Alembic `alter_column` on a native MySQL ENUM.

**Pre-existing issues left alone** (documented in `plan.md`): the daemon-thread
runner whose boot sweep kills the other gunicorn worker's in-flight generations;
`proxy.ts` exporting `proxyConfig` where Next 16 expects `config`; `litellm` and
`resend` installed but imported nowhere.
