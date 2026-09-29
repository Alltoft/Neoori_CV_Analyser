# Vérification d'email + mot de passe oublié — Design Spec
Date: 2026-09-29
Status: approved in conversation, section by section — awaiting review of this written spec

## Overview

Today an account is an email string nobody has checked. `POST /api/auth/register`
signs the person in on the spot (`routes/auth.py:63`), `POST /api/counselor/apply`
does the same for a conseiller demande (`routes/counselor_space.py`), and
`users` has no column that could say whether the address is real. There is no
« mot de passe oublié » either: a forgotten password is a lost account.

This spec adds:

1. **Email verification as a hard gate.** No session is ever issued to an
   unverified account. The link in the email verifies the address *and* signs
   the person in.
2. **Password reset**, built on the same plumbing (signed link + mail + page).
3. **Analyses require an account.** The anonymous path is closed, because it
   made the gate pointless: nobody needs a throwaway account when no account is
   needed at all.
4. **Per-IP rate limiting** on the endpoints that send mail, and on login.

Developer rulings in this conversation (2026-09-29):

- Purpose is all four at once: stop throwaway accounts, guarantee every account
  is reachable, trust conseiller demandes, compliance / hygiene.
- Gate: **no session until verified** (not "signed in but locked", not
  "gate some actions", not a grace period).
- Anonymous analyses: **closed**. Account + verified email required.
- Existing accounts are test accounts: **backfilled as verified**, no clicks.
  An admin button « Marquer comme vérifié » covers new test accounts and, after
  testing, the real user whose mail landed in spam.
- Password reset: **same batch**.
- Conseiller trust: **account email only**. `email_pro` stays a declared,
  unchecked field.
- Mechanism: **signed stateless links** (`itsdangerous`), no token table.
- Transport: **stay on Resend**, not Flask-Mail (decision 1).
- Sender: `neoori <bonjour@neoori.tech>`, and `bonjour@neoori.tech` becomes a
  real mailbox on **Hostinger Email** — replies land there, no Reply-To trick.

---

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | **Resend stays the transport.** Flask-Mail is not added. | Flask-Mail is an SMTP client only — it still needs an SMTP server (Gmail app password ≈500/day with a From mismatch that lands in spam; Proton SMTP only on business plans; a raw VPS sender has port 25 blocked and zero IP reputation). Every option needs the same SPF/DKIM DNS work, which is the real work. Resend is already coded, fail-soft and fenced off in tests (`email_service.py`, `conftest.py`); a second transport buys nothing. |
| 2 | **No session until verified**, enforced by one helper `_issue_session(response, user)` that refuses an unverified user. Every path that sets cookies goes through it. | No JWT means no `jwt_required` route is reachable — every existing and future route is gated by construction, not by a check someone can forget on route 41. |
| 3 | **Signed stateless links** via `itsdangerous.URLSafeTimedSerializer` (ships with Flask), keyed on `SECRET_KEY`, one salt per purpose. No token table. | Verification is idempotent, so replay is harmless; reset gets single-use for free from the password fingerprint (decision 5). A table would add revocation and an audit trail nothing here needs, plus an expiry cleanup job. Cost accepted: rotating `SECRET_KEY` kills links in flight — the person asks for a new one. |
| 4 | Verification link: salt `email-verify`, **48 h**, payload `{uid, email, next}`. | `email` in the payload kills the link if the address ever changes. `next` carries the destination across the email round-trip (e.g. `/analyse/nouveau`). |
| 5 | Reset link: salt `password-reset`, **1 h**, payload `{uid, pwv}` where `pwv` = first 16 hex chars of `sha256(password_hash)`. | Once the password changes, `pwv` no longer matches: the link is single-use without storing anything. |
| 6 | The refresh token carries the same `pwv` claim; `/auth/refresh` refuses a token whose `pwv` is missing or stale. | A reset must end sessions opened elsewhere — the usual reason to reset is "someone else is in my account". Access tokens stay 1 h, so a stolen session dies within the hour. Refresh tokens minted before this ships carry no `pwv`: everyone is logged out once at deploy. They are test accounts. |
| 7 | `next` is accepted only if it starts with `/` and not `//` (nor `/\`). Anything else becomes `null`. | Otherwise the verification link is an open redirect signed by neoori. |
| 8 | The verification link signs in **only on the first verification**. The UPDATE is conditional (`WHERE email_verified_at IS NULL`); only the request whose rowcount is 1 gets a session. A later click answers `{already: true}`, no cookies. | An old email must not work as a 48 h login link, and two simultaneous clicks must not both mint a session. |
| 9 | Login with the right password on an unverified account → **403** `{code: "email_unverified"}`. Wrong password → the usual 401 « Identifiants incorrects. », whether or not the account is verified. | 403 not 401: `api.ts:39` redirects every 401 to `/connexion`, which would swallow the message. The unverified state is revealed only to someone who knows the password — no enumeration. |
| 10 | Re-signup on an **unverified** email updates the account **in place** (new password, seed replaced, pending demande fields replaced) and sends a fresh link. Same 201 response as a new account. On a verified email → 409 as today. | Otherwise anyone can squat an address by registering it first, and a person who mistyped their password before verifying is stuck forever. In place, not delete-and-recreate: `profiles.user_id` and `counselor_profiles.user_id` carry no `ondelete` cascade. |
| 11 | `resend-verification` and `forgot-password` always answer **200 with the same body**, whatever the account state. They send only when the account exists (and, for resend, is unverified) and `auth_mail_sent_at` is older than **60 s**. | No enumeration through these two endpoints. The cooldown stops one account from being used to mail-bomb its owner. |
| 12 | Clicking a reset link also sets `email_verified_at` if it was NULL. | It proves inbox ownership exactly as the verification link does. |
| 13 | `POST /api/analyses/`, `POST /api/analyses/draft`, `POST /api/upload/cv`, `POST /api/upload/projet` become `@jwt_required()`. `proxy.ts` `PROTECTED` gains `/analyse` and `/espace`. A logged-out visitor on `/analyse/*` is sent to **`/inscription?redirect=…`**, not `/connexion`. | The anonymous path is what made throwaway accounts unnecessary (`create_analysis` reads `_optional_user_id()`; `/analyse` was never gated). Visitors on the analysis form are most likely new, so signup is the right door. `/espace` had no edge guard at all. |
| 14 | Existing rows are backfilled `email_verified_at = created_at` in the migration. | Every current account is a test account (developer, 2026-09-29). |
| 15 | Admin gets `POST /api/admin/users/<id>/verify-email` and a « Marquer comme vérifié » button. It is **kept after testing**. | New test accounts need no inbox, and a real person whose mail landed in spam has a way in. There is no "unverify". |
| 16 | `GET /api/admin/counselor-applications` **leaves out** demandes whose account is unverified. | A throwaway demande never becomes admin work. Resolves most of open question 6 of the conseiller spec (spam on `/apply`). |
| 17 | Sending stays **fail-soft** (`send()` never raises). `register` / `apply` still return 201 when the mail fails, with `mail_sent: false`, and the screen says so. | An account row that committed must not become a 500 the person retries into a 409. The pending screen offers « Renvoyer ». |
| 18 | `send()` gains an optional `text` part; both new mails send HTML + plain text. | HTML-only mail scores worse with spam filters. |
| 19 | New config `APP_URL` (default `https://neoori.tech`; dev compose `http://localhost:8080`) replaces the hardcoded `APP_URL` constant in `email_service.py`. | Links must point at the local stack in dev. The conseiller approval mail moves to it too. |
| 20 | Dev only: when `RESEND_API_KEY` is missing **and** `app.debug`, the verification / reset link is written to the backend log. Never in production. | Local end-to-end testing without a real mailbox. Tokens never reach production logs. |
| 21 | Per-IP rate limiting in **nginx** (`limit_req`), keyed through a `map` on `$uri` so the existing `/api/` location stays one block. ~5 req/min (small burst) on `register`, `resend-verification`, `forgot-password`, `counselor/apply`; ~10 req/min on `login`. Status 429. | These endpoints are public and send mail; Resend's free plan is **100 mails/day** (3,000/month). One script can burn the day's quota and leave every real signup stuck — the per-account cooldown does not stop many accounts. Login is one extra line and blocks password guessing. `api.ts:46` already renders 429 as « Trop de requêtes — patientez une minute puis réessayez. » |

---

## User flows

### Candidate signup
1. `/inscription` as today (prénom, tranche d'âge, email, mot de passe, CGV).
   `?redirect=` is read and sent as `next`.
2. On submit the account is created, **no session**. The page swaps to
   `<VerificationPending email>`: « Un lien de confirmation a été envoyé à
   marie@… », « Renvoyer » (60 s countdown), « Mauvaise adresse ? Recommencer ».
   If `mail_sent` is false: « L'envoi a échoué. Réessayez dans un instant. »
3. The link opens `/verifier-email?token=…` → verified + signed in →
   `next ?? homeFor(role)`.
4. A second click → « Adresse déjà confirmée » + « Se connecter ».
5. Expired / invalid → message + email field + « Recevoir un nouveau lien ».

### Unverified login
Right password → `<VerificationPending email>` on `/connexion`. Wrong password →
« Identifiants incorrects. »

### Analyses
Logged-out visitor on any `/analyse/*` → `/inscription?redirect=<path>` → after
verification lands back on the form. Landing CTAs are unchanged; the proxy does
the redirect.

### Mot de passe oublié
`/connexion` gains « Mot de passe oublié ? » → `/mot-de-passe-oublie` → always
« Si un compte existe pour cette adresse, un email vient d'être envoyé. » → link
(1 h, single-use) → `/reinitialiser-mot-de-passe?token=…` → new password +
confirmation → signed in → `homeFor(role)`. Invalid link → « Demander un
nouveau lien ».

### Conseiller demande without an account
Same as signup: `<VerificationPending>` after submit, `next = /conseiller`. The
demande enters the admin queue only once the email is verified. After the click
they land on their « demande en attente » screen. A demande from a signed-in
account is unchanged.

### Admin
`/admin/utilisateurs`: « Vérifié » column (✓ / « Non vérifié ») and « Marquer
comme vérifié » on unverified rows.

---

## Data model

One migration, `down_revision = 'e7f8a9b0c1d2'` (counselor_accounts, current head).

`users` gains:

| Column | Type | Meaning |
|---|---|---|
| `email_verified_at` | `DATETIME NULL` | NULL = unverified. Backfilled to `created_at` for every existing row. |
| `auth_mail_sent_at` | `DATETIME NULL` | Cooldown clock shared by verification and reset mails. |

`User.to_dict()` gains `email_verified: bool`. No new table.

---

## Backend

### `app/utils/auth_links.py` (new)
- `password_fingerprint(user) -> str` — 16 hex of `sha256(password_hash)`.
- `make_verify_token(user, next_path) / load_verify_token(token)` — decision 4.
- `make_reset_token(user) / load_reset_token(token)` — decision 5.
- `safe_next(value) -> str | None` — decision 7.
- Loaders return a small result distinguishing `expired` from `invalid`
  (`SignatureExpired` vs `BadSignature`), so the page can say which.

### `routes/auth.py`
- `_issue_session(response, user)` replaces `_set_tokens`; raises if
  `user.email_verified_at is None`; adds `pwv` to the refresh token.
- `register` — no session; decision 10 for an unverified email; sends the mail;
  201 `{user, mail_sent}`.
- `login` — decision 9.
- `refresh` — refuses unverified, and missing / stale `pwv` (decision 6).
- `POST /verify-email {token}` — decisions 4, 8. Success
  `{user, next}` + cookies; `{already: true}`; 400 `{code: "link_expired" | "link_invalid"}`
  (bad signature, unknown user, email mismatch).
- `POST /resend-verification {email}` — decision 11.
- `POST /forgot-password {email}` — decision 11.
- `POST /reset-password {token, password}` — `len >= 8`, stale `pwv` →
  `link_invalid`; sets hash; decision 12; session.

### `routes/counselor_space.py` — `apply()`
Without a JWT: no session (the `created` branch stops setting cookies);
decision 10 for an unverified email — the password is replaced in place and
the demande is created, or its fields replaced if one is already pending; sends the verification mail with `next = /conseiller`. With a JWT:
unchanged.

### `routes/analyses.py`, `routes/upload.py`
Decision 13. `_optional_user_id()` stays for the read paths that use it.

### `routes/admin.py`
- `POST /users/<id>/verify-email` (admin only) — decision 15.
- `GET /users` — rows carry `email_verified`.
- `GET /counselor-applications` — decision 16.

### `services/email_service.py`
- `send(to, subject, html, text=None)` — decision 18.
- `send_verification(user, next_path) -> bool` and
  `send_password_reset(user) -> bool`, same fail-soft wrapper shape as the
  conseiller mails. They stamp `auth_mail_sent_at` at the call site.
- Links from `current_app.config["APP_URL"]` (decision 19); dev log (decision 20).

Mail copy (French, sober, `_layout()` frame):

**Confirmez votre adresse email**
> Bonjour {prénom},   ← « Bonjour, » when the account has no Profile prénom
> Pour activer votre compte neoori, confirmez votre adresse. Le lien est valable
> 48 heures.
> [Confirmer mon adresse]
> Si vous n'avez pas créé de compte, ignorez ce message.

**Réinitialiser votre mot de passe**
> Une demande de réinitialisation a été faite pour votre compte. Le lien est
> valable 1 heure et ne sert qu'une fois.
> [Choisir un nouveau mot de passe]
> Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : votre
> mot de passe reste inchangé.

Footer (in `_layout()`, so the conseiller mails change too): « Pour nous
écrire, répondez à ce message. » The `bonjour@neoori.tech` mailbox is step 2 of
the mandatory deploy order below, so it exists before the first mail carries
this line.

### `config.py`
`APP_URL` (decision 19). `MAIL_FROM` unchanged.

---

## Frontend

### New pages — `app/(auth)/`, `AuthLayout`
- `verifier-email/page.tsx` — calls `verify-email` on mount (once, guarded
  against the React strict-mode double effect), then `refresh()` and routes.
- `mot-de-passe-oublie/page.tsx`
- `reinitialiser-mot-de-passe/page.tsx` — same zod password rules as
  `/inscription`.

### New component
`components/auth/VerificationPending.tsx` — used by `/inscription`,
`/inscription-conseiller` (no-account path) and `/connexion` (403
`email_unverified`). « Recommencer » resets the form it sits in.

### Changes
- `lib/auth.tsx` — `register()` no longer sets the user, returns `{mail_sent}`;
  `login()` lets the 403 through as an `ApiError` carrying `body.code`.
- `(auth)/connexion` — « Mot de passe oublié ? », `VerificationPending` on 403,
  « Créer un compte » forwards `?redirect=`.
- `(auth)/inscription` — reads `?redirect=`, `VerificationPending` after submit
  instead of `router.push("/espace")`.
- `(auth)/inscription-conseiller` — `VerificationPending` on the no-account path.
- `proxy.ts` — decision 13; `/analyse*` redirects to `/inscription`.
- `admin/utilisateurs` — column + button.
- `types` — `User.email_verified: boolean`.

---

## Nginx (decision 21)

In both `templates-http` / `templates-https` and `nginx/dev.conf`, at file top
(the templates render into `conf.d/`, which sits in the `http {}` context):

```nginx
map $uri $auth_mail_key {
    ~^/api/(auth/(register|resend-verification|forgot-password)|counselor/apply)/?$  $binary_remote_addr;
    default "";
}
map $uri $auth_login_key {
    ~^/api/auth/login/?$  $binary_remote_addr;
    default "";
}
limit_req_zone $auth_mail_key  zone=auth_mail:10m  rate=5r/m;
limit_req_zone $auth_login_key zone=auth_login:10m rate=10r/m;
limit_req_status 429;
```

and inside the existing `location /api/`:

```nginx
limit_req zone=auth_mail  burst=3 nodelay;
limit_req zone=auth_login burst=5 nodelay;
```

An empty key is not counted, so every other `/api/` call is untouched. nginx is
the edge (no CDN in front), so `$binary_remote_addr` is the client.

---

## Ops — prerequisites and deploy order

The code **must not** ship before mail works: every new signup would stop at
« vérifiez votre boîte » with the admin button as the only way in.

As of 2026-09-29, `neoori.tech` has **no TXT and no MX record at all**
(checked with `dig` against 1.1.1.1): the domain is not verified in Resend, so
no mail leaves production today — the conseiller approval mails are already
being skipped silently.

1. **Resend** → Domains → add `neoori.tech`, region **EU (Ireland)**. Copy the
   records it shows into Hostinger DNS: DKIM TXT `resend._domainkey`, MX + SPF
   TXT on `send`. Wait for « Verified ».
2. **Hostinger Email** → create `bonjour@neoori.tech`. Its MX, SPF (apex) and
   DKIM records go into the same DNS zone. They do not collide with Resend's:
   receiving is MX on the apex, Resend uses the `send` subdomain.
3. **DMARC** → TXT `_dmarc` = `v=DMARC1; p=none; rua=mailto:bonjour@neoori.tech`.
4. **VPS `.env`** → `RESEND_API_KEY`, `MAIL_FROM=neoori <bonjour@neoori.tech>`,
   `APP_URL=https://neoori.tech`. The laptop SSH key is refused since
   2026-09-12 — use the Hostinger hPanel browser terminal or a dispatch
   workflow (`.github/workflows/seed.yml` is the pattern), then restart the
   backend container.
5. **Test** a real send to `nneoori+test@proton.me`, and score one on
   mail-tester.com.
6. **Only then** `git push` (deploy). The migration runs at container start
   (`backend/entrypoint.sh`).

Quota: 100 mails/day on the free plan. Move to Pro (50k/month, no daily cap)
before any launch push.

## Legal

`/confidentialite` §5 « Destinataires et sous-traitants » gains:
« Resend (envoi des emails transactionnels, États-Unis — clauses contractuelles
types) ». Hostinger is already listed; its mail service is the same processor.
Legal text — the PM sees the line before it ships.

---

## Testing

Backend, pytest, TDD. `conftest.py` already blanks `RESEND_API_KEY`.

- **Links**: round-trip; expired; tampered; wrong salt (a verify token refused
  as a reset token and back); `next` = `//evil.com`, `/\evil.com`,
  `https://evil.com` → `None`.
- **register**: no `Set-Cookie`; verified email → 409; unverified email →
  password and seed replaced in place, 201, same body shape as a new account;
  `mail_sent` false when the key is missing.
- **login**: unverified + right password → 403 `email_unverified`; unverified +
  wrong password → 401; verified → cookies.
- **refresh**: unverified → refused; no `pwv` → refused; stale `pwv` after a
  reset → refused.
- **verify-email**: first click → session + `next`; second → `{already: true}`,
  no cookies; expired; email mismatch; unknown user.
- **resend / forgot**: byte-identical response for existing, unverified,
  verified and unknown emails; second call inside 60 s sends nothing.
- **reset**: sets the hash; second use of the same link → `link_invalid`; marks
  an unverified email verified; short password → 400.
- **apply**: no-account path sets no cookies; unverified re-apply replaces the
  demande in place.
- **gate**: anonymous `POST /analyses/`, `/analyses/draft`, `/upload/cv`,
  `/upload/projet` → 401.
- **admin**: `verify-email` admin-only (candidate → 403); `/users` carries the
  flag; `/counselor-applications` omits unverified accounts.
- **migration**: existing rows come out verified (`test_migration_chain.py`).
- **Existing tests** that expect `register` / `apply` to set cookies
  (`test_signup_profile_seed.py`, `test_counselor_apply.py`) are updated, not
  deleted.

Frontend: `tsc`, lint, `next build`. Then end to end on the local stack
(`docker compose up -d` → http://localhost:8080) using the link from the backend
log: signup → pending → link → `/analyse/nouveau`; login unverified; forgot →
reset → old session refused at refresh; admin button; 429 on the sixth rapid
signup.

---

## Out of scope

- Verifying `email_pro` on conseiller demandes (developer ruling).
- Changing one's email address — no such feature exists; decision 4 keeps the
  link safe if one is ever added.
- Cleaning up unverified accounts that are never confirmed.
- Resend bounce / complaint webhooks.
- Per-account login lockout, CAPTCHA.

## Open questions for the PM

1. **Funnel change**: an analysis now requires a verified account. No landing
   copy promises otherwise (checked), but it is a conversion decision.
2. The `/confidentialite` line naming Resend.
3. The mail footer now invites replies (« Pour nous écrire, répondez à ce
   message. ») — wording is the PM's to adjust.
