# Les quatre portes — Design Spec
Date: 2026-10-08
Status: written while the developer was away, on their instruction to take
every recommended option ("what you think is recommended is the best"). The
rulings they gave in person are marked **Ruling**; every other decision is
marked **Claude's call** and listed again in « Claude's calls » at the end, so
each can be overturned on review. An independent review against the code
found three blockers and ten should-fixes in the first draft; all are folded
in. Awaiting the developer's review.

## Overview

« J'ai une cible » (parcours 1) today needs a verified account before the form
even renders, and the browser decides which tier a run gets. This sub-project
opens the form to everyone and puts four doors behind its submit button:

| Door | UI name | Account | What runs | Who gets the report |
|---|---|---|---|---|
| `account` | « Avec mon compte » | required | free tier (§1–3 + verdict) | the account holder, who can unlock 9 € / 24 € as today |
| `advisor` | « J'ai un code conseiller » | never asked | Complet (§1–9) | **only** the counselor who owns the code |
| `promo` | « J'ai un code promo » | required | Complet (§1–9) | the account holder |
| `anonymous` | « Sans compte » | none | free tier (§1–3 + verdict) | whoever holds the private link, 30 days |

The server decides each door's tier and recipient. Nothing the browser sends
chooses a model any more.

This is sub-project 2 of 3 (2026-10-08 app split):

1. Retire parcours 2 and 3 — `docs/superpowers/specs/2026-10-08-remove-parcours-2-3-design.md`,
   branch `feat/remove-parcours-2-3`, being built in another session.
2. **This spec.**
3. Split into `cv.<domain>` and `voyage.<domain>`.

**Base.** The build starts from `initial` once sub-project 1 **and**
`feat/social-sign-in` are merged. Everything below is written against that
state: one parcours, `_path` stamped "1" by the server, the counselor view's
P2/P3 branches gone, and the sign-in round trip carrying a `redirect` / `next`
path through password signup, Google, Microsoft, the email link and the
verification mail (`utils/auth_links.safe_next` accepts a query string). Line
numbers are indicative; the plan re-reads them after both merges.

## What the code does today (2026-10-08, prod checked read-only)

- `FORCE_ANALYSIS_TIER=paid` is set in `/srv/neoori/.env`, and the code
  defaults to "paid" when it is unset (`routes/analyses.py:30`). **The free tier
  has never run in production.** `MODEL_FREE` there is
  `anthropic/claude-haiku-4-5-20251001` (valid); `MODEL_PREMIUM` is unset, so
  Premium runs on the code default `claude-opus-5`.
- With the switch off, `create_analysis` takes `data["tier"]` from the body
  (`analyses.py:85`): any signed-in client can post `"premium"` and get an
  Opus run for nothing. The frontend sends `"sonnet"` when
  `user.plan === "paid" || credits_remaining > 0` — and `credits_remaining`
  defaults to 1 and is never decremented.
- One code table, `counselor_codes`. `owner_id IS NULL` = admin-minted:
  unlimited, never expires, the admin can only deactivate it. Prod: 1 admin
  code (active), 5 conseiller codes, 1 redemption (a voyage), 3 counselors.
- One redemption consumes one use, voyage **or** analysis
  (`code_service.redemption_count`). The landing (`app/page.tsx:178, :528`) and
  CGV §6 promise both with one code. The use count is a plain read, so two
  overlapping requests can both pass the ceiling (`code_service.py:40-56`);
  the only database guard is the unique key on `(code_id, target_type,
  target_id)`.
- A conseiller code redeemed at `/debloquer` unlocks the candidate's own
  report to the paid tier. The counselor never sees content: conseiller spec
  decision 9, and `/beneficiaires` returns no id and no token.
- `/c/<share_token>` is public, unauthenticated, never expires, and shows
  §1/§4/§5 plus an input allow-list. Its notes endpoints accept any signed-in
  role. Prod: 0 counselor notes.
- No rate limit on analyses, drafts, uploads, code redemption or checkout —
  nginx limits only the auth endpoints (`nginx/templates-*/default.conf.template`).
  Each run is its own daemon thread, uncapped.
- CGV consent is recorded only on the profile, at signup
  (`profiles.consent_at`, `CONSENT_VERSION = "v1.2"`, recorded and never
  compared). Nothing checks consent before a run.
- `create_analysis`, `/draft`, `/api/upload/cv` and `/api/upload/projet` are
  `@jwt_required`; `proxy.ts` sends a signed-out visitor on `/analyse*` to
  `/inscription`. `inputs` is stored as whatever object the client posted
  (`utils/request_body.dict_field`), up to the 10 MB `MAX_CONTENT_LENGTH`.
- `_may_access` lets anyone read or modify an analysis with no owner: 17 such
  rows in prod (6 error, 11 success), created before accounts were required.
- The CV prompt's `_profile_block` reads prénom, nom, tranche d'âge, ville,
  situation, diplôme, études, contraintes and bloc 5 from the profile. A run
  with no account sends the CV and the target only.
- `payments.create_checkout` has no auth or ownership check, and refuses on
  `unlock_method` only, while `unlock_analysis` also refuses when §5 exists.
  The `/debloquer` page shows « déjà complète » whenever a paid section exists,
  so no person reaches that checkout through the UI; a direct API call could
  still pay for an unlock that then refuses. `/payments/verify` returns the
  full analysis to anyone holding a Stripe `session_id`.
- Secrets already travel in logged URLs: `/verifier-email?token=`,
  `/reinitialiser?token=`, `?redirect=` / `?next=` on every sign-in path, and
  the Stripe `?session_id=`. nginx logs the request line and the Referer
  (default `combined` format), gunicorn runs `--access-logfile -` with its
  default format (request line and Referer, `backend/entrypoint.sh:37`), and
  the prod `Referrer-Policy` is `strict-origin-when-cross-origin`, which sends
  the full URL on same-origin requests.
- `reap_stale_running` (every app boot) marks `running` rows older than 15
  minutes **by `created_at`** as error.

## Decisions

### Rulings (developer, 2026-10-08)

1. **The parcours 1 form opens without an account.** Its submit leads to four
   doors: sign in, advisor code, promo code, free version with no login.
2. **Advisor door: no login, only what the run needs. The full report goes
   only to the counselor's page; the candidate gets nothing.** This reverses
   decision 9 of the 2026-09-24 conseiller spec (the counselor never saw
   content).
3. **`/c/<token>` and its §1/§4/§5 selection are removed.** Counselors see the
   full report, on their own page.
4. **Promo codes are admin-minted and give the full report for free.**
5. **The sign-in door gives the free tier** (§1–3 + verdict), saved in the
   account; the 9 € / 24 € unlock stays on the report.
6. **The promo door requires signing in.** The full run starts directly (no
   free run first). One use per account.
7. **A promo code gives Complet (§1–9) only.** Premium stays a 24 € purchase.
8. **Existing admin codes become promo codes**, and the admin can now set
   their uses and expiry, or revoke them. Unlocking the voyage with one keeps
   working as today.
9. **The advisor door asks prénom and nom, both required.**
10. **One conseiller code use counts per kind**: a single-use code opens one
    advisor-door analysis **and** one voyage.
11. **No-login reports live at a private link** with a « Créer un compte pour
    le garder » button that attaches the report to an account. No email is
    stored, no mail is sent.
12. **An unclaimed no-login report is deleted after 30 days.**
13. **Everything else: Claude's recommended option** — the developer's
    instruction while away. Those choices follow, each marked.

### The tier is the server's

14. *Claude's call.* **`services/doors.py` maps a door to a tier and a
    recipient; nothing else decides.** `FORCE_ANALYSIS_TIER` is deleted from
    the code, `.env.example` and the VPS `.env`; `data["tier"]` is no longer
    read. The PM's content review, which the switch existed for, uses promo
    codes instead (one per review run, minted by the admin). An unknown `door`
    is a 400.
15. *Claude's call.* **A signed-in visitor sees three doors**: the no-login
    door is hidden, since « Avec mon compte » gives the same tier and keeps the
    report.
16. *Claude's call.* **The submit button reads « Générer mon analyse »** for
    everyone, and the footer line « 3 sections gratuites — les 6 suivantes
    après déblocage… » goes. The ruling named the button « Générer l'analyse
    complète », but two of the four doors behind it give the free tier;
    a button promising the complete analysis would be wrong for half of them.

### Codes

17. *Claude's call.* **A code's kind is derived, not stored**: `owner_id IS NULL`
    → promo, otherwise conseiller. No new column. An advisor-door report needs
    an owner to go to, so an ownerless code cannot be a conseiller code.
18. *Claude's call.* **Admin promo codes get the same controls as conseiller
    codes**: `max_uses` (default 1) and an expiry (default 90 days), both
    editable later, both allowing « illimité ». Revoke sets `revoked_at`. The
    one existing admin code keeps NULL / NULL until the admin edits it.
19. **Counting per kind** (ruling 10). *Claude's call*: it applies to promo
    codes too, so `max_uses` caps analyses and voyages separately for every
    code, and a promo code's voyage use (ruling 8) counts as a voyage use.
20. *Claude's call.* **A conseiller code works only while its owner is an
    approved counselor** (not pending, rejected or revoked) — everywhere one is
    checked or redeemed: the advisor door, `/api/codes/check` and the voyage
    unlock — answered with the generic « Code invalide ou désactivé. » At the
    advisor door the report would otherwise go to a page nobody can open; at
    the voyage, a revoked counselor's code would keep opening sessions in their
    name.
21. *Claude's call.* **A code typed at the wrong door is answered with the right
    one**: the server refuses with the door the code belongs to, and the panel
    switches to it, keeping what was typed.
22. *Claude's call.* **`/debloquer` accepts promo codes only.** A conseiller code
    there is refused: « Ce code est un code conseiller : avec lui, le rapport
    complet est envoyé à votre conseiller. Lancez une nouvelle analyse et
    choisissez « J'ai un code conseiller ». » Otherwise a conseiller code would
    still hand the candidate the report ruling 2 sends to the counselor.
23. *Claude's call.* **The database enforces a code's limits, not a count.**
    With no account at the advisor door, N overlapping requests with one
    single-use code would otherwise buy N Complet runs; the old judgment
    ("bounded, non-revenue", `code_service.py:50`) assumed unlocks of distinct
    owned analyses. `code_redemptions` gains:
    - `slot` (INT NULL) and a unique key on `(code_id, target_type, slot)`.
      For a code with `max_uses`, the redemption is written with
      `slot = count + 1`, refused when that exceeds `max_uses`, and inserted
      **and committed before the run starts**. A unique violation means another
      request took that slot: recount once in a fresh transaction, then answer
      `EXHAUSTED`. Unlimited codes write `slot = NULL`, which never collides.
    - A unique key on `(code_id, target_type, user_id)`: one promo use per
      account is atomic. Advisor redemptions carry `user_id = NULL`, which
      never collides.

### The advisor door

24. *Claude's call.* **An advisor-door run never reads a profile or a voyage**,
    even when the person happens to be signed in. Its inputs are the CV, the
    target, the chemin, and prénom and nom — stored as the `prenom` / `nom`
    inputs, which `_profile_block` already prints. The row has no `user_id`, so
    no candidate surface can ever list or open it; folding a voyage in would
    also bypass the voyage's own stage rule on a page the counselor sees. The
    door always writes a **new** row and deletes any draft the person had:
    promoting a draft would give the counselor's report an id the candidate
    already holds.
25. *Claude's call.* **Notice and consent before submit.** The door shows the
    notice « Le rapport complet sera envoyé à votre conseiller, pas à vous :
    vous n'en recevrez pas de copie. Votre conseiller pourra vous le présenter
    ou vous le transmettre. » and a checkbox « J'accepte les CGV et la politique
    de confidentialité. », recorded on the row.
26. *Claude's call.* **After submit the candidate sees a confirmation page,
    `/analyse/envoyee`**, with no link, no id and no content.
27. *Claude's call.* **The counselor's page**: « Mes bénéficiaires » links each
    advisor-door analysis to `/conseiller/analyses/<id>` — the full report,
    print-to-PDF, private notes, delete, and « Relancer » when the run failed
    (same row, no new code use; the candidate is gone and cannot retry).
28. *Claude's call.* **The counselor is mailed when the run ends** — ready or
    failed — with no name and no content: « Une analyse est prête dans votre
    espace conseiller. » Fail-soft, like every other mail.
29. *Claude's call.* **Advisor-door reports are deleted 12 months after
    creation**, or earlier when the counselor deletes them; notes go with them.
    Twelve months covers a typical Cap Emploi / France Travail accompaniment.
    The candidate's rights of access and erasure go through the RGPD contact in
    `/confidentialite`.

### The no-login door

30. *Claude's call.* **The report's key is a random token that never reaches a
    server log.** 32 bytes from `secrets.token_urlsafe`, stored only as its
    SHA-256 hex in `analyses.access_token_hash`. The link is
    **`/rapport#<token>`**: a URL fragment is never sent to a server and never
    appears in a Referer. The page reads it from `location.hash` and sends it to
    the API in an `X-Analysis-Token` header. Headers are not in any access log.
    A fresh token is minted at submit, so a draft's token never opens a
    report; claiming clears the hash, so the old link stops working.
31. *Claude's call.* **Consent is the same checkbox as at the advisor door**,
    recorded on the row.
32. *Claude's call.* **The report page says how long it lives**: « Ce rapport
    n'est accessible que par ce lien, jusqu'au <date>. » with « Copier le lien »,
    « Créer un compte pour le garder » and « Supprimer ce rapport ». The unlock
    offer reads « Créez un compte pour débloquer le rapport complet » — the
    9 € unlock needs an owner (decision 41). « Garder » hands the report to the
    hold cookie (decision 34) and runs the sign-in round trip with
    `redirect=/espace?garder=1`; `/espace` then claims it.
33. *Claude's call.* **Claiming keeps the inputs as they were**: no profile or
    voyage is folded in. An unlock later regenerates from those stored inputs,
    the same rule the voyage already follows ("a report already delivered is
    never rewritten").

### Signing in mid-flow

34. *Claude's call.* **A signed-out draft is held by a cookie, never by a URL.**
    The draft is saved only when a door needs a sign-in round trip — « Avec mon
    compte » or « J'ai un code promo » while signed out — because only those
    doors leave the page; the others leave no ownerless draft behind.
    - It is an `Analysis` row with `status="draft"`, no owner and a token
      hash. The raw token goes into an HttpOnly cookie `neoori_hold`
      (`Path=/api`, `SameSite=Lax`, `Secure` in production, 48 h) — never into
      the JSON, a URL, a mail or a log. The same cookie holds a no-login report
      handed over by « Garder » (decision 32); one held row at a time.
    - The round trip's `redirect` is `/analyse/nouveau?reprendre=compte` or
      `?reprendre=promo` — no secret in it.
    - Back on the form with a session, `POST /api/analyses/claim` attaches the
      held row to the account, clears the hash and the cookie, and returns the
      draft. The form refills and reopens the panel at that door. The person
      confirms; nothing starts on its own. A promo code is retyped (pre-filled
      from `sessionStorage` in the same browser) — it never rides in a URL.
    - **Password signup marks; the signup password attaches.**
      `POST /api/auth/register`, when it creates a new user row and the request
      carries the cookie, writes that account's id into the held row's
      `pending_user_id`. The row stays ownerless and held. `POST
      /api/auth/verify-email` — the link **and** the signup password, so the
      registrant — attaches every row pending for that account. So the
      verification link opened on a phone finds the draft as that account's
      most recent draft. Google, Microsoft and password login stay in the
      same browser, so the claim at the form does it.
    - **The one case that loses the thread**: an email sign-in link (« Recevoir
      un lien de connexion ») opened on another device. That device finds no
      draft and says « Votre formulaire est resté sur l’appareil où vous l’avez
      rempli : connectez-vous depuis celui-ci pour le retrouver. » A token in
      the URL would fix it, at the price of putting a CV's key in a mail and in
      logs.
    - Promoting a draft — at any door — sets `created_at` to the submit time,
      so retention and the report's date count from the run.
35. *Claude's call.* **A held draft not claimed within 48 hours is deleted** —
    the life of the verification link (`VERIFY_MAX_AGE`). The form then opens
    empty with « Votre brouillon a expiré. »
36. *Claude's call.* **Nothing is attached to an account before the signup
    password proves its address.** Otherwise someone registering another
    person's address could leave a draft in that account. If the address is
    proven another way first — `sign_in.enter` (Google, Microsoft, email link),
    which already replaces the password « since a stranger may have set it »,
    or `auth.reset_password` — the `pending_user_id` mark is dropped. The row
    is not deleted: it stays held by the browser that made it, so a registrant
    who switches to Google in that same browser still claims it at the form,
    and it expires with its cookie.

### Inputs and sessions

37. *Claude's call.* **The client's `inputs` are an allow-list with length
    caps**, at every door and for every draft: `cv_text` (≤ 40 000 characters),
    `cible_visee` (≤ 10 000), `_chemin`. Every other posted key is dropped,
    including the server-owned ones (`_voyage`, `_voyage_id`, `_conditions`,
    `_oeth`, `_tier`; `_path` is stamped). The advisor door adds `prenom` and
    `nom` (≤ 80 each) from its own top-level fields. Over a cap: 400 « CV trop
    long (40 000 caractères maximum). » / « Cible visée trop longue (10 000
    caractères maximum). » This also closes today's gap where a client-posted
    `_conditions` / `_oeth` survives `_merge_profile` for an account with no
    sensitive row.
38. *Claude's call.* **"Signed in" means a valid, unexpired access token.** The
    open endpoints (submit, `/draft`, `/claim`'s caller check, `/codes/check`,
    uploads) read the identity with `_optional_user_id()` (try/except, as
    `routes/counselor_space.py:121-131` does), never with
    `@jwt_required(optional=True)`, which still answers 401 / 422 on an expired
    or malformed token. A lapsed session is therefore a signed-out visitor
    everywhere: the doors, the held draft and the anonymous door all work, and
    a 401 at the `account` / `promo` doors restarts the round trip once instead
    of looping.

### Abuse limits

39. *Claude's call.* **nginx, per IP**, on what this opens up, sized for a
    workshop room behind one address (15 people, each about four requests
    within minutes):
    - `analyses` zone, 10 r/min, `burst=40 nodelay`, `POST` only:
      `/api/analyses/`, `/api/analyses/draft`, `/api/upload/(cv|projet)`;
    - `codes` zone, 10 r/min, `burst=20 nodelay`: `/api/codes/check`,
      `/api/analyses/<id>/unlock`, `/api/voyage/unlock`;
    - keyed with `map "$request_method:$uri"`, so the polling `GET`s are never
      limited.
40. *Claude's call.* **Two daily caps in the app, counted from an append-only
    `run_log` table** — one row per submitted run: `door`, `user_id`,
    `created_at`. Nothing deletes from it but the purge, after 2 days; deleting
    a report (which candidates and anonymous holders may do) never lowers a
    count. Values from env:
    - `ANONYMOUS_RUNS_PER_DAY` (default 200), all no-login runs together.
      With the input caps, a Haiku run costs about 0.06 $, so the door is
      bounded near 12 $ a day. Over it: 429 « La version sans compte est très
      demandée aujourd'hui. Créez un compte, ou revenez demain. »
    - `FREE_RUNS_PER_ACCOUNT_PER_DAY` (default 5), `account`-door runs per
      user. Over it: 429 « Vous avez lancé {n} analyses gratuites aujourd'hui.
      Revenez demain, ou débloquez une analyse existante. »
    - Promo and advisor runs are bounded by their codes (decision 23); unlock
      regenerations by payment or code; a counselor's relaunch writes no row.
    - A per-IP daily cap is left out: it would mean storing addresses. If one
      address drains the anonymous budget, the other doors still work.

### Payment

41. *Claude's call.* **Checkout and verify require the owner, and checkout
    refuses exactly when the unlock would.**
    - `/payments/checkout` and `/payments/verify` are `@jwt_required`, caller ==
      `analysis.user_id`.
    - `unlock_service.refusal(analysis)` is the one rule both checkout and
      `unlock_analysis` call. It refuses unless `status == "success"` (today
      an errored row could be unlocked), when a run is in flight, and when the
      row is already unlocked or already has §5.
    - So Premium (24 €) is bought from a free report only, as today: a promo,
      advisor or already-Complet report cannot be upgraded. That keeps ruling 7
      literal.
    - The webhook is unchanged.

### Logs

42. *Claude's call.* **Access logs record the path, never the query string or
    the Referer.** nginx gets a `log_format` of address, time, method, `$uri`,
    status, bytes and duration. gunicorn gets `--access-logformat '%(h)s %(t)s
    "%(m)s %(U)s" %(s)s %(b)s %(L)s'`. This feature's own tokens never reach a
    URL (decisions 30, 34). The fix is still made here because the sign-in round
    trip it routes people through already logs verification and reset tokens,
    `next` paths and Stripe session ids (see « What the code does today »).

### What goes, what stays

43. *Claude's call.* **`/c/<token>` becomes a static page**: « Ce lien n'est plus
    actif. » with a link to the landing — counselors hold old links, so a 404
    would look like a bug. `/api/c/*` is deleted. `share_token` stays as a
    column (a populated column is not dropped) and is no longer minted. The
    report's « Vue conseiller » tab, « Partager au conseiller » and the
    `/espace` analysis share link go. The voyage's own counselor link
    (`/voyage/c/…`) is untouched.
44. *Claude's call.* **The 17 old ownerless analyses are marked, not inferred.**
    The migration sets `door = 'legacy'` on every row with no owner. Only a
    `legacy` row keeps its old by-id access. Any future row that ends up with no
    owner, no token and no counselor is closed to everyone, rather than
    silently readable. They are not purged here (open item 1).
45. *Claude's call.* **No new form fields for the thin context** of no-profile
    runs: the advisor door adds prénom + nom (ruling 9), the no-login door adds
    nothing. The PM judges sample reports from a CV-only run before launch;
    optional tranche d'âge and situation selects are the follow-up if they read
    thin (open item 3).
46. *Claude's call.* **The purge is a CLI command run daily by host cron**,
    exactly like the backups: `flask purge-expired` (`--dry-run` to count only),
    from a wrapper script in `scripts/` and a cron line on the VPS. It has a
    second mode for rollback (« Errors and edge cases »).
47. *Claude's call.* **The reaper keys on `started_at`**, a new column set when
    a row goes `running`. Two things this adds would otherwise trip the
    `created_at` rule: the nightly purge boots the app, and a counselor's
    « Relancer » re-runs a row that may be days old. Both would mark a live run
    as error, mid-stream, and invite a second paid run on the same row. Rows
    with no `started_at` fall back to `created_at`.
48. *Claude's call.* **`CONSENT_VERSION` becomes "v1.3"**, because CGV §2 and §6
    change (copy rows 8–9). It is recorded, never compared, so no existing
    account is asked again (open item 7).

## Data model

One Alembic migration.

`analyses` gains:

| Column | Type | Meaning |
|---|---|---|
| `door` | `VARCHAR(16)` NULL; index `(door, created_at)` | `account` / `promo` / `advisor` / `anonymous`, set at submit; `legacy` set by the migration on rows with no owner (decision 44). NULL for drafts and pre-existing owned rows. |
| `access_token_hash` | `CHAR(64)` NULL, unique | SHA-256 of the token: held drafts and `anonymous` reports, until claimed. |
| `counselor_id` | `VARCHAR(36)` NULL, FK `users.id` `ON DELETE SET NULL`, indexed | The counselor an `advisor` report belongs to. |
| `consent_at` | `DATETIME` NULL | The checkbox at the `advisor` / `anonymous` doors. |
| `consent_version` | `VARCHAR(16)` NULL | `CONSENT_VERSION` at that moment. |
| `started_at` | `DATETIME` NULL | Set when the row goes `running`; the reaper's clock (decision 47). |
| `pending_user_id` | `VARCHAR(36)` NULL, FK `users.id` `ON DELETE SET NULL`, indexed | The account a held row waits for, set by password signup, attached at verify-email (decisions 34, 36). |

`code_redemptions` gains `slot` (`INT` NULL) and two unique keys,
`(code_id, target_type, slot)` and `(code_id, target_type, user_id)`
(decision 23). The migration back-fills `slot` for rows of codes that have a
`max_uses`, in `redeemed_at` order (prod: one row).

`counselor_notes` gains a unique key `(analysis_id, counselor_id)` (prod: zero
rows).

New table `run_log` (decision 40): `id`, `door` `VARCHAR(16)`, `user_id`
`VARCHAR(36)` NULL (no FK: it outlives nothing and is purged after 2 days),
`created_at` indexed.

No change to `counselor_codes`: the kind is derived (decision 17).

**Who may read an analysis** — `_may_access(analysis)`, used by the
candidate-facing routes (`GET /<id>`, `GET /by-token`, `DELETE`,
`price-feedback`), in this order:

1. `door == "advisor"` or `counselor_id` set → **no**. Counselor routes are
   separate (below). Testing `door` keeps a report closed even after a
   counselor's account is erased (`SET NULL`).
2. `access_token_hash` set → yes iff the `X-Analysis-Token` header hashes to it
   (`hmac.compare_digest`).
3. `user_id` set → yes iff it is the caller.
4. `door == "legacy"` → yes, as today.
5. Anything else → **no**.

`unlock` and `checkout` are narrower: owner only (decision 41 and the
`unlock_with_code` row below).

## Backend

| File | Change |
|---|---|
| `services/doors.py` (new) | `DOORS`; `decide(door, *, user_id) -> Plan` or a refusal. `Plan` holds the tier, the row's `user_id` / `counselor_id`, whether to fold profile + voyage, whether consent is required, which cap applies, and the response shape. Every door rule in one table the tests can read. |
| `routes/analyses.py` | `create_analysis` becomes the submit, with the identity read by `_optional_user_id()` (decision 38). Body `{inputs, door, draft_id?, code?, prenom?, nom?, consent?}`. Steps: allow-list + caps on inputs (decision 37) → validate parcours 1 inputs → `doors.decide` → cap check on `run_log` → resolve the code for the door → write and commit the redemption (decision 23) → promote the draft row or create one → write `run_log` → start the run. A signed-in body with no `door` means `account`, so a stale tab still works and gets the free tier. Delete `_FORCE_TIER` and every `data.get("tier")`. `share_token` is no longer minted. `save_draft`: identity via `_optional_user_id()`; signed out, it creates or updates the held draft and sets the `neoori_hold` cookie (decision 34); the JSON never carries the token. New: `GET /held`, `POST /hold` (header token → cookie), `POST /claim` (valid session + cookie → attach, clear hash and cookie), `GET /by-token`. `_may_access` as in « Who may read ». `unlock_with_code`: `@jwt_required`, owner only, promo codes only (decision 22), one use per account. |
| `routes/codes.py` (new) | `POST /api/codes/check {code}` → `{kind: "promo" \| "conseiller"}`, or 400 with the `code_service` refusal (decision 20 applied). The panel uses it to show the advisor notice or the sign-in step before submit. It redeems nothing. |
| `services/code_service.py` | `resolve(code_str, target_type)` counts per kind. `kind(code)` from `owner_id`. `resolve_for_door(code_str, door, user_id)`: the right kind; an approved owner for a conseiller code; for promo, no earlier analysis use by this account (`ALREADY_USED = "Vous avez déjà utilisé ce code."`). The wrong-door refusal carries `door`. `record()` writes `slot` and is committed by the caller **before** the run starts; a unique violation is retried once, then `EXHAUSTED` / `ALREADY_USED`. The docstring's race paragraph is rewritten to match. |
| `services/unlock_service.py` | Extract `refusal(analysis) -> str \| None` (decision 41); `unlock_analysis` calls it. |
| `routes/payments.py` | `create_checkout` and `verify_session`: `@jwt_required`, owner only; checkout uses `unlock_service.refusal()`. |
| `routes/upload.py` | `/cv` and `/projet` drop `@jwt_required`. Otherwise unchanged: PDF only, 10 MB, nothing stored. |
| `routes/auth.py` | `register`: when it creates a new user and the request carries `neoori_hold`, set the held row's `pending_user_id` (decision 34) — never for an address that already has an account. `verify_email`: on success, attach every row pending for that user. `reset_password`: on an unverified account, drop the marks (decision 36). |
| `services/sign_in.py` | `enter` on an unverified account drops its `pending_user_id` marks (decision 36). |
| `routes/counselor.py` | Deleted (`/api/c/<token>` and its notes). Blueprint unregistered. |
| `routes/counselor_space.py` (exists) | Add, under `@approved_counselor_required`, with `analysis.counselor_id == me` or 404: `GET /analyses` (id, prénom, nom, code label, status, created_at); `GET /analyses/<id>` (full `to_dict()`); `DELETE /analyses/<id>` (notes deleted explicitly first: their FK has no cascade); `POST /analyses/<id>/relaunch` (error / timeout only, no redemption, no `run_log` row); `GET` / `PUT /analyses/<id>/notes`. `/beneficiaires` adds `nom` and `analysis_id` for the caller's advisor-door rows; its docstring stops citing decision 9. `/codes` and the stats count uses per kind. |
| `routes/admin.py` | `POST /counselor-codes` takes `max_uses` and `expires_in_days` (defaults 1 and 90; `null` = illimité). New `PATCH /counselor-codes/<id>` for the two limits. `DELETE` also sets `revoked_at`. The list shows each code's kind and per-kind uses. |
| `models/analysis.py` | The seven columns. Delete `COUNSELOR_VISIBLE_INPUT_KEYS`, the `audience="counselor"` branch, `counselor_keys` and `share_token` in `to_dict()`. Add `door` and `access_expires_at` (unclaimed `anonymous` rows only: `created_at` + `ANONYMOUS_RETENTION_DAYS`). |
| `models/code_redemption.py`, `models/counselor_note.py`, `models/run_log.py` (new) | Columns and keys from « Data model ». |
| `models/profile.py` | `CONSENT_VERSION = "v1.3"` (decision 48). |
| `services/section_registry.py` | Drop the `"counselor"` key and `counselor_keys()`. |
| `services/anthropic_service.py` | Set `started_at` with `running`. `_notify_outcome`: an `advisor` row mails its counselor (verified address only); an ownerless row mails nobody. |
| `app/__init__.py` | `reap_stale_running` keys on `started_at`, falling back to `created_at` (decision 47). |
| `services/email_service.py` | `send_counselor_analysis_ready` / `send_counselor_analysis_failed`, through `_mail`, no name, link to `/conseiller`. |
| `services/purge.py` + `cli.py` (new) | `flask purge-expired [--dry-run]`: in one transaction and FK order (notes, price feedback, then rows), deletes held drafts unclaimed after 48 h, unclaimed `anonymous` reports after 30 days, `advisor` reports after 365 days, and `run_log` rows after 2 days. Prints counts per kind. Never selects `legacy`, owned or claimed rows. `flask purge-expired --before-rollback [--apply]` deletes **every** `advisor` and `anonymous` row and every held draft, whatever its age (« Errors and edge cases »). |
| `config.py` | `ANONYMOUS_RUNS_PER_DAY` (200), `FREE_RUNS_PER_ACCOUNT_PER_DAY` (5), `ANONYMOUS_RETENTION_DAYS` (30), `ADVISOR_RETENTION_DAYS` (365), `HELD_DRAFT_RETENTION_HOURS` (48), `CV_TEXT_MAX` (40 000), `CIBLE_MAX` (10 000). |
| `nginx/templates-http`, `templates-https`, `dev.conf` | The `analyses` and `codes` zones (decision 39). The path-only `log_format` (decision 42). |
| `backend/entrypoint.sh` | gunicorn `--access-logformat` (decision 42). |
| `scripts/neoori-purge.sh` (new) | `cd /srv/neoori` then `docker compose -f docker-compose.prod.yml exec -T backend flask purge-expired`, logging to `/var/log/neoori-purge.log` — the shape of `scripts/neoori-backup.sh`. |
| `.env.example` | Delete `FORCE_ANALYSIS_TIER`. `MODEL_FREE` becomes `anthropic/claude-haiku-4-5-20251001` (the `gemini/…` value would fail the Anthropic call). Add the caps. |
| Migration | Everything in « Data model », including `door = 'legacy'` on ownerless rows and the `slot` back-fill. The downgrade drops it all; it is only safe after `--before-rollback`. |

**Submit, per door** (after parcours 1 validation, which stays as is):

| | `account` | `promo` | `advisor` | `anonymous` |
|---|---|---|---|---|
| Session (decision 38) | required, else 401 | required, else 401 | ignored | must be absent, else 400 « Vous êtes connecté : choisissez « Avec mon compte ». » |
| Code | — | promo, one per account | conseiller, approved owner | — |
| Extra fields | — | — | `prenom`, `nom` required | — |
| Consent checkbox | — (signup) | — (signup) | required | required |
| Cap (`run_log`) | 5 / account / day | — | — | 200 / day, all together |
| `_tier` | `free` | `paid` | `paid` | `free` |
| Profile + voyage folded | yes | yes | **no** | no |
| Row | promoted draft or new; `user_id` = caller | promoted draft or new; `user_id` = caller | always new, any draft deleted; `user_id` NULL, `counselor_id` = code owner, no token | promoted held draft or new; `user_id` NULL, fresh token |
| Response | `{analysis}` | `{analysis}` | `{}` | `{analysis, access_token}` |

## Frontend

| File | Change |
|---|---|
| `proxy.ts` | `/analyse` stays protected except `/analyse`, `/analyse/nouveau` and `/analyse/envoyee` (exact paths). `/rapport` is outside every protected prefix. |
| `app/analyse/nouveau/page.tsx` | No `useRequireSession`. The paragraph « Le reste de l’analyse s’appuie sur ce que vous avez déjà donné… » shows to signed-in visitors only — a signed-out run has no profile. The shield line keeps « Données chiffrées, supprimables à tout moment. » for everyone. Submit opens the doors panel instead of posting. With `?reprendre=compte\|promo`: signed in → `POST /claim`, else the account's latest draft, else the decision 34 message; signed out → `GET /held`. Then refill and open the panel at that door. « Enregistrer le brouillon » stays for signed-in users. No `tier`, no `canPremium`. Label and footer per decision 16. |
| `components/analyse/DoorsPanel.tsx` (new) | The four doors (three when signed in), one open at a time, each with its fields, notice, checkbox and error. It saves the held draft and builds the sign-in redirect. « Avec mon compte » signed out goes to `/inscription` (signup first, as `proxy.ts` does), whose page links to `/connexion` with the same redirect. Wrong-door switch (decision 21). A 401 at `account` / `promo` restarts the round trip once. |
| `app/analyse/envoyee/page.tsx` (new) | The advisor-door confirmation. |
| `app/rapport/page.tsx` (new) | One page, token from `location.hash`: waiting state plus report for a no-login run, polling `GET /analyses/by-token`. Banner, copy link (the full URL with its `#`), « garder » (`POST /hold`, then the round trip to `/espace?garder=1`), delete (decision 32). The 10-minute give-up reads « C’est plus long que prévu. Gardez ce lien : le rapport s’affichera ici dès qu’il sera prêt. » — no mail promise. `metadata.referrer = "no-referrer"`. |
| `app/espace/page.tsx` | With `?garder=1`: `POST /claim`, then show the claimed report on top. Delete the analysis share link and « Partagez avec votre conseiller ». The voyage's « Lien pour mon conseiller » stays. |
| `app/conseiller/analyses/[id]/page.tsx` (new) | Header « Prénom NOM · code « label » · date ». Status, polling while queued or running, the full report (the shared report components, without unlock CTA or price probe), print, notes, delete (in-page confirm, never a browser dialog), « Relancer ». |
| `app/conseiller/page.tsx` | « Mes bénéficiaires »: prénom + nom from the analysis, and « Voir l’analyse » on advisor-door rows. The codes table and the « Places » hint show uses per kind (« 1 analyse et 1 voyage par place »). |
| `app/analyse/[id]/rapport/page.tsx` | Delete the « Vue conseiller » tab, `VERSION CONSEILLER`, the counselor key-facts strip and « Partager au conseiller ». |
| `app/analyse/[id]/debloquer/page.tsx` | The code field becomes « Déjà un code promo ? », error « Saisissez votre code promo. »; the conseiller-code refusal is shown as returned. Copy per « Copy ». |
| `app/c/[token]/page.tsx` | Static notice (decision 43); no API call. |
| `app/admin/…` codes screen | « Codes promo »: mint with label, uses, expiry; edit limits; revoke; kind column. |
| `lib/api.ts` | A token-header option for `/by-token`, `/hold` and the token-holder's `DELETE` / `price-feedback`. A 401 on a public page (`/analyse/nouveau`, `/analyse/envoyee`, `/rapport`) never hard-navigates to `/connexion`. |
| `types/index.ts` | `Door`; `Analysis` gains `door` and `access_expires_at`, and loses `share_token` and `counselor_keys`. |
| `components/report/ReportSection.tsx` | Drop the `counselor` prop. |

## Copy

Provisional, in the existing tone; the PM approves before launch. None of the
new strings uses a word from CLAUDE.md's banned list. "After sub-project 1"
means the text as that spec leaves it.

**New strings**

| Where | Text |
|---|---|
| Panel title | « Comment voulez-vous continuer ? » |
| « Avec mon compte » | « Version gratuite : les trois premières sections et le verdict, gardés dans votre espace. Le rapport complet reste disponible à 9 €. » Button « Créer un compte ou me connecter » (signed out) / « Lancer la version gratuite » (signed in). |
| « J'ai un code conseiller » | Prénom, Nom, Code. Notice (decision 25). Checkbox. Button « Envoyer à mon conseiller ». |
| « J'ai un code promo » | « Le rapport complet, offert. Un compte est nécessaire pour le recevoir. » Code. Button « Continuer » (signed out: to sign-in) / « Lancer l’analyse complète » (signed in). |
| « Sans compte » | « Version gratuite, accessible par un lien privé pendant 30 jours. Sans compte, nous ne pourrons pas vous renvoyer ce lien. » Checkbox. Button « Lancer sans compte ». |
| `/analyse/envoyee` | « C’est envoyé. » — « Votre conseiller recevra votre analyse d’ici quelques minutes, dans son espace. Il pourra vous la présenter lors de votre prochain échange. » |
| `/rapport` banner | Decision 32. |
| `/c/<token>` | « Ce lien n’est plus actif. » — « Les conseillers reçoivent désormais l’analyse complète dans leur espace, lorsque leur code est utilisé. » |
| Form after the round trip | « Votre brouillon a expiré. » / the decision 34 cross-device message. |
| Refusals | Decisions 22, 37, 40, the submit table, `ALREADY_USED`; « Merci d’accepter les CGV et la politique de confidentialité. »; nginx 429 in the panel: « Trop de tentatives — réessayez dans une minute. » |
| Counselor mails | Subject « Une analyse est prête » / « Une analyse n’a pas abouti ». Body « Un bénéficiaire a utilisé votre code : son analyse est prête dans votre espace conseiller. » / « … n’a pas abouti. Vous pouvez la relancer depuis votre espace conseiller. » |

**Changed strings**

| # | Where | Before | After |
|---|---|---|---|
| 1 | Landing, counselor card (`page.tsx:158`) | « Vos bénéficiaires arrivent en entretien avec un rapport déjà structuré : leurs forces, leurs fragilités, vos préconisations. Vous travaillez ensemble, à partir d’une même base. Vous gagnez du temps. Eux, de la confiance. Avec votre code conseiller, ils accèdent aussi aux sessions du voyage — et vous relisez leur portrait avec eux avant qu’ils ne le reçoivent. » | « Avec votre code, vos bénéficiaires lancent l’analyse de leur CV, et le rapport complet arrive dans votre espace conseiller : leurs forces, leurs fragilités, vos préconisations. Vous le reprenez ensemble en entretien, à partir d’une même base. Vous gagnez du temps. Eux, de la confiance. Le même code leur ouvre les sessions du voyage — et vous relisez leur portrait avec eux avant qu’ils ne le reçoivent. » |
| 2 | FAQ « Combien ça coûte ? » (after sub-project 1) | « Chaque analyse commence gratuitement, sans carte bancaire : … Si votre conseiller vous a remis un code, le rapport complet et les sessions 1 à 5 du voyage sont offerts. » | « Chaque analyse commence gratuitement, sans carte bancaire et sans compte obligatoire : … Si votre conseiller vous a remis un code, les sessions 1 à 5 du voyage vous sont offertes, ainsi que votre analyse : son rapport complet est envoyé à votre conseiller, qui le reprend avec vous. » (middle unchanged) |
| 3 | Landing, report section (`page.tsx:411`) | « Si vous êtes accompagné par un conseiller, il a peut-être un code qui vous donne accès à tout — gratuitement. Ça vaut la peine de lui demander. » | « Si vous êtes accompagné par un conseiller, il a peut-être un code : votre analyse complète lui est alors envoyée, gratuitement, pour qu’il la reprenne avec vous. Ça vaut la peine de lui demander. » |
| 4 | Pricing, free card small print | « Trois premières sections et verdict de diagnostic inclus, plus la première session du voyage. Aucune carte bancaire demandée. » | « … Aucune carte bancaire demandée, et pas de compte obligatoire pour l’analyse. » |
| 5 | Pricing, « Code conseiller » card (`page.tsx:528`) | « Vous êtes accompagné par un conseiller ? Il a peut-être un code qui vous ouvre le rapport complet et les sessions 1 à 5 du voyage — gratuitement. Ça vaut la peine de lui demander. » | « Vous êtes accompagné par un conseiller ? Avec son code, votre analyse complète lui est envoyée pour qu’il la reprenne avec vous, et les sessions 1 à 5 du voyage vous sont ouvertes — gratuitement. Ça vaut la peine de lui demander. » |
| 6 | Form button / footer | « Générer l'analyse complète » or « Générer mon analyse »; « 3 sections gratuites — les 6 suivantes après déblocage (9 € ou code conseiller) » | « Générer mon analyse »; footer removed (decision 16) |
| 7 | `/debloquer` | « Déjà un code conseiller ? »; « Saisissez votre code conseiller. »; « Paiement sécurisé par Stripe · gratuit pour les bénéficiaires Cap Emploi / France Travail (code conseiller) »; « Livrable 9 sections + CV retravaillé + export conseiller » | « Déjà un code promo ? »; « Saisissez votre code promo. »; « Paiement sécurisé par Stripe »; « Livrable 9 sections + CV retravaillé » |
| 8 | CGV §2 (after sub-project 1) | « … L'offre payante débloque le rapport complet, ainsi que l'export conseiller. Il compte 9 sections, … » | « … ainsi qu'un verdict de diagnostic. Elle est accessible avec ou sans compte ; sans compte, le rapport n'est accessible que par un lien privé, pendant 30 jours, sauf si l'utilisateur crée un compte pour le conserver. L'offre payante débloque le rapport complet. Il compte 9 sections, … » |
| 9 | CGV §6 | Title « Bénéficiaires accompagnés (code conseiller) »; « Les bénéficiaires d'un accompagnement Cap Emploi, France Travail, Mission Locale ou CEP peuvent obtenir le rapport complet gratuitement, et accéder aux sessions 1 à 5 du voyage, au moyen d'un code fourni par leur conseiller. Ce code est strictement personnel à la structure qui le délivre. » | Title « Codes conseiller et codes promotionnels ». « Les bénéficiaires d'un accompagnement Cap Emploi, France Travail, Mission Locale ou CEP peuvent, au moyen d'un code fourni par leur conseiller, faire réaliser gratuitement une analyse complète et accéder aux sessions 1 à 5 du voyage. Le rapport de cette analyse est transmis au seul conseiller titulaire du code, et non au bénéficiaire ; il est conservé 12 mois dans l'espace de ce conseiller. Ce code est strictement personnel à la structure qui le délivre. » + « neoori peut remettre des codes promotionnels. Un code promotionnel donne accès gratuitement, une fois par compte, au rapport complet d'une analyse ; il nécessite un compte. Il peut être limité en nombre d'utilisations et dans le temps, et neoori peut le désactiver à tout moment. » |
| 10 | Confidentialité §2, « Notes du conseiller » | « … les notes qu'un conseiller prend sur votre analyse ou votre voyage pour préparer l'entretien. » | « … les notes qu'un conseiller prend sur votre voyage, ou sur une analyse lancée avec son code, pour préparer l'entretien. » |
| 11 | Confidentialité §2, new bullet after « Analyses » | — | « <strong>Analyse sans compte</strong> : le contenu de votre CV et la cible visée, conservés 30 jours puis supprimés, sauf si vous créez un compte pour garder le rapport. Le lien privé du rapport en est la seule clé : nous ne pouvons pas le retrouver pour vous. » |
| 12 | Confidentialité §3, new bullet | — | « Analyse sans compte, ou avec le code de votre conseiller — exécution du contrat (CGV acceptées à l'envoi). » |
| 13 | Confidentialité §5, the « /c/… » paragraph | « Le lien de partage conseiller (« /c/… ») donne accès à une synthèse de votre analyse à toute personne disposant du lien : ne le transmettez qu'à votre conseiller. » | « Si vous lancez une analyse avec le code de votre conseiller, le rapport complet, votre prénom, votre nom, votre CV et la cible visée sont transmis à ce conseiller, dans son espace, et à lui seul ; vous n'en recevez pas de copie. Ce rapport est supprimé 12 mois après sa création, ou plus tôt si le conseiller le supprime. Pour en obtenir une copie ou sa suppression, adressez-vous à votre conseiller ou écrivez-nous. Lorsque vous utilisez son code pour le voyage, le conseiller voit votre prénom, votre email et la date d'utilisation. » |

The last sentence of row 13 is the line the conseiller spec promised for
`/confidentialite` (its « RGPD » section) and never added.

## Errors and edge cases

- **Code at the wrong door**: 409 `{error, door}`; the panel switches.
- **Conseiller code, owner not approved**: « Code invalide ou désactivé. »
- **Promo already used by this account**, at the door or on `/debloquer`:
  `ALREADY_USED`, 409.
- **Code exhausted or expired**: the existing `code_service` messages, per
  kind. Two overlapping requests for the last slot: one runs, the other gets
  `EXHAUSTED` (decision 23).
- **Caps**: 429 with the decision 40 messages. The no-login cap message points
  to the account door, which still works.
- **nginx limits**: 429; the panel shows « Trop de tentatives… ».
- **Expired session**: treated as signed out (decision 38). At `account` /
  `promo` the 401 restarts the round trip once.
- **Held row gone** (expired, already claimed, or another browser): `/held` and
  `/claim` answer 404; the form says « Votre brouillon a expiré. », or the
  cross-device message when the account has no draft either.
- **Claim from a different account than the one that started**: the cookie is
  the capability, and the row moves to the account present — the same as
  handing the link to someone.
- **Advisor run fails**: the candidate is not told (they left with
  `/analyse/envoyee`); the counselor is mailed and relaunches. A relaunch
  records no redemption and no `run_log` row.
- **No-login run fails**: the report page shows the failure and « Nouvelle
  analyse »; the person resubmits, which counts against the daily cap again.
- **Counselor revoked** after a report arrived: role back to `candidate`, so
  `@approved_counselor_required` refuses; the report waits for its 12 months or
  an admin. Their codes then fail everywhere (decision 20).
- **Stale form tab** posting `{inputs, tier}` while signed in: treated as
  `account`, free tier; `tier` ignored; inputs allow-listed.
- **Old `/c/<token>` links**: static page; `/api/c/*` answers 404.
- **Image rollback.** `flask db upgrade` runs at container start under
  `set -e` (`backend/entrypoint.sh:24`), so the previous image cannot start
  against a database that carries this revision — the trap sub-project 1's
  decision 3 describes. Rolling back takes three steps, in order, with the
  new image still running:
  1. `flask purge-expired --before-rollback` (dry-run), then `--apply`. Without
     it, the downgrade would leave `advisor` rows as plain ownerless rows,
     which the old `_may_access` serves to anyone with the id.
  2. `flask db downgrade <previous revision>`.
  3. `IMAGE_TAG=<sha> docker compose -f docker-compose.prod.yml up -d`.

## Testing

**Backend (pytest), new**

- `doors.decide`: the submit table, every cell — session valid, expired or
  absent; code kinds; missing prénom/nom; missing consent; unknown door → 400.
- Submit:
  - per door, the stored `_tier`, `user_id`, `counselor_id`, `door`, consent
    columns, token hash and `run_log` row, and the response shape;
  - `advisor` and `anonymous` rows carry no profile, voyage, `_conditions` or
    `_oeth` key even when the caller is signed in with all of them;
  - the allow-list drops every other key at every door and on drafts; the
    length caps answer 400;
  - a body `tier: "premium"` never yields premium; `FORCE_ANALYSIS_TIER` in
    env changes nothing;
  - the advisor door writes a new row and deletes the caller's draft.
- Caps: the 6th `account` run of the day → 429, and still 429 after deleting
  the first five; the 201st `anonymous` → 429; unlocks, relaunches and other
  doors do not count.
- Codes:
  - single-use conseiller code: one advisor analysis plus one voyage, then
    exhausted for each;
  - two threads racing for the last slot: exactly one redemption row (run on
    MySQL in the local Docker stack; SQLite does not reproduce the snapshot);
  - promo once per account, enforced by the unique key; wrong-door refusal
    carries `door`;
  - conseiller code with a pending / rejected / revoked owner refused at the
    door and at `/codes/check`;
  - `/debloquer` refuses a conseiller code;
  - admin mint defaults (1 use, 90 days), `PATCH`, revoke.
- `_may_access`, the full matrix: owner / other user / signed out × owned row /
  `legacy` row / token row with right, wrong and no header / advisor row with
  and without `counselor_id` / a row with nothing set (closed).
- Hold and claim:
  - the token is only ever in the cookie and the hash, never in a response
    body;
  - `register` marks only when it creates the user; `verify-email` attaches
    the marked rows; a held row never becomes owned before that;
  - claim clears hash and cookie; the old `/rapport#…` token then 404s;
  - a draft's token does not open the report;
  - entering an unverified account, or resetting its password, drops the
    marks without deleting the rows; the same browser can still claim.
- Counselor routes:
  - another counselor → 404; a candidate → 403;
  - relaunch only on error / timeout; delete removes notes first;
  - one note per counselor per analysis.
- `_notify_outcome`: an advisor row mails the counselor and only them; an
  anonymous row mails nobody.
- Checkout and verify: anonymous caller → 401; non-owner → 403. Checkout
  refuses whenever `refusal()` does: §5 present, an error row, a run in flight.
- Uploads accept a signed-out request. `/api/c/<token>` → 404.
- Reaper: a relaunched row with a fresh `started_at` and an old `created_at`
  survives a boot.
- `purge-expired`:
  - it selects exactly the expired kinds, with their notes, feedback and
    `run_log` rows;
  - it never selects a `legacy`, owned, claimed or fresh row;
  - `--dry-run` changes nothing; a second run deletes nothing;
  - `--before-rollback` takes every `advisor` and `anonymous` row and every
    held draft.
- Migration: chain test; the upgrade marks ownerless rows `legacy` and
  back-fills `slot`; the downgrade runs.

**Backend, existing tests that change** (they assert what this spec removes):
- `test_anonymous_closed.py` — 401 on uploads, create and draft;
- `test_unlock.py` and `test_code_redemption_routes.py` — code redemption on
  ownerless rows without auth;
- the `/api/c` notes rigs in `test_malformed_bodies.py` and
  `test_no_500_on_hostile_input.py`;
- the counselor-view cases in `test_analysis_model.py`;
- `test_checkout_503_without_key` — now gets 401 before the 503 unless it
  signs in.

**Frontend**: `tsc --noEmit`, `next build`.

**Local walkthrough through nginx (`localhost:8080`)**:
- each door, signed out and signed in, plus with an expired access cookie;
- password signup with the verification link opened in a second browser
  profile (the phone case) — the draft is there;
- an email-link sign-in opened in that second profile — the cross-device
  message;
- a Google round trip if the keys are set locally;
- a counselor receiving, printing, annotating and relaunching an advisor-door
  report;
- `/rapport#…` → « garder » → `/espace`;
- a burst of submits reaching the nginx 429;
- the access logs show paths only;
- the old `/c/<token>` notice.

## Rollout

On the developer's go, each step:

1. Sub-project 1 and `feat/social-sign-in` merged to `initial`; this branch
   rebased; the plan's line numbers re-checked.
2. PM approves the copy (new strings + rows 1–13).
3. Merge and push. The deploy builds the images, applies the migration at
   container start, and re-renders nginx (`deploy.yml` reloads it).
4. On the VPS: delete the `FORCE_ANALYSIS_TIER=paid` line from
   `/srv/neoori/.env` (inert after the deploy; removed so nobody believes it).
   Optionally set the caps there.
5. Install the purge: `scp scripts/neoori-purge.sh neoori:/usr/local/bin/`,
   `chmod +x`, cron `30 3 * * *` (after the 03:00 backup). Run it once by hand
   with `--dry-run`.
6. Smoke test in prod, in order:
   - a free run through « Avec mon compte » — **the first free-tier run
     production has ever made**;
   - a no-login run;
   - an advisor run with a test conseiller code, to a test counselor account;
   - a promo run with a single-use admin code.
7. The PM reads the free-tier and CV-only sample reports (decision 45, open
   item 3).

## Docs

- `CLAUDE.md`:
  - replace « Counselor view — sections 1, 4, 5 only » with a « Les quatre
    portes » section: the door table, the access rule, the hold cookie, the
    three retentions, the purge cron, the rollback order;
  - « Paywall » and « AI call spec »: the counselor code no longer grants the
    candidate the paid tier;
  - « Analyses and CV uploads require an account » becomes « The analysis form
    and CV upload are open; `/analyse/<id>/*` needs the owner »;
  - « What reaches an analysis »: `_merge_voyage()` folds the voyage into
    `account` and `promo` runs only;
  - the counselor mails join the « Mails transactionnels » table;
  - the new env settings join the gotchas.
- `DOCKER.md`: a « Purge » section beside « Backups »; the rollback order; the
  two new nginx zones beside the auth ones; the access-log format.
- `TEST-PLAN.md`: the four doors replace the counselor-view checks.
- The conseiller spec gets a dated note under decision 9: reversed on
  2026-10-08 by this spec. The note is added; the decision text stays as it
  was.

## Out of scope

- Sub-project 3 (subdomains, per-app landings). Nothing here hardcodes a
  domain: links are built from `APP_URL` as today.
- The voyage — its unlock, its `/voyage/c/` page (open to any approved
  counselor holding the token, as today), its prompts — except counting code
  uses per kind and refusing a code whose counselor is no longer approved
  (decision 20).
- Premium as a promo option or as an upgrade from Complet, Stripe promotion
  codes, account deletion, a per-IP daily cap, a cap on concurrent run threads.
- Cleaning up unverified accounts that never verify (and the drafts signup
  attached to them).
- Issues seen during exploration, not fixed here:
  - the frontend never refreshes the access token (decision 38 makes the open
    pages tolerate that; the rest of the app still lapses after an hour);
  - `DELETE /api/profile` leaves copied profile fields and `_conditions` /
    `_oeth` inside past analyses.

## Open items

1. **The 17 legacy ownerless analyses** stay readable by anyone with their id.
   Purge them, or close their by-id access? Not decided here.
2. **Copy**: every string above is provisional (PM).
3. **Thin context for CV-only runs**: PM verdict on samples; optional selects
   are the follow-up.
4. **RGPD contact**: `/confidentialite` still carries `[À COMPLÉTER]`. Row 13
   sends advisor-door candidates there for access and erasure, so it becomes
   blocking for the advisor door.
5. **Retention values** (48 hours, 30 days, 12 months) and the **caps**
   (200 / day, 5 / account / day, 40 000 / 10 000 characters) are Claude's
   numbers, all in config.
6. **Revoked counselor's reports**: kept until 12 months, admin-only. Delete
   them at revocation instead?
7. **CGV change for existing accounts**: v1.3 is recorded for new consents
   only. Whether existing account holders must be told of the change (mail,
   banner) is a PM / legal call.

## Claude's calls

Made on the developer's standing instruction (2026-10-08) to take the
recommended option; each is open to reversal on review:

- Decisions 14–48 above (for 19, only its extension to promo codes).
- The door names in code (`account`, `promo`, `advisor`, `anonymous`, `legacy`)
  and their UI names.
- The order in which the panel shows the doors: the ruling's order — sign in,
  advisor code, promo code, no login.
