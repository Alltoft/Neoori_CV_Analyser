# Connexion Google / Microsoft / lien par email — Design Spec
Date: 2026-10-03
Status: approved 2026-10-03 (design section by section, then this spec). Plan: `docs/superpowers/plans/2026-10-03-social-login.md`

## Overview

Job seekers quit signup at « mot de passe + email de vérification ». This spec
adds three ways in that need neither:

1. **« Continuer avec Google »**
2. **« Continuer avec Microsoft »**
3. **« Recevoir un lien de connexion »**: an email link that both signs up and
   signs in.

Signup with a password, its verification mail, login, « mot de passe oublié »
and the conseiller demande all stay as they are
(`2026-09-29-email-verification-design.md`). Every new path ends in the same
place: `routes/auth._issue_session()`, the same JWT cookie pair, refused for an
unverified account.

Developer rulings (2026-10-03, carried from the first brainstorm session):

1. Goal: fewer signup drop-offs.
2. Round 1 scope: Google, Microsoft, the email link. Not now: Apple (later, if
   iPhone users ask); FranceConnect / ProConnect (possible B2G phase 2).
3. The email link both signs up and signs in. Clicking it proves the address,
   so there is no separate verification mail. New accounts give prénom +
   tranche d'âge + CGV consent. A password is optional (set later through
   « Mot de passe oublié »).
4. Linking: signing in with Google, Microsoft or the link, using the address of
   an existing account, enters that account, and its password keeps working.
   If that account was never verified, its password is wiped, so a stranger who
   signed up with that address keeps no way in.
5. Approach A: server-side OAuth redirect in Flask with Authlib. No provider
   JavaScript on our pages, so no CNIL consent banner. Rejected: Google One Tap
   (loads Google's tracking script), hosted auth (Clerk / Auth0).
6. Email link: built on `utils/auth_links` (itsdangerous) + Resend;
   single-use; valid 15 min; paced by `users.auth_mail_sent_at` plus the nginx
   per-IP `limit_req`.
7. The conseiller demande form stays as is. A conseiller signs in with a
   provider, then applies from their espace (that path exists).

Rulings made while presenting the design (2026-10-03):

- An untrusted Microsoft address is **refused** and pointed at the email link
  (decision 10). No unlinked account is offered.
- Ruling 4's wipe gets **no extra notice** (decision 9).
- The completion page is kept and titled **« Finaliser votre inscription »**.
  Prénom is prefilled from the provider. The age bracket and consent cannot come
  from a provider (decision 22).
- OAuth endpoints get their **own, looser nginx zone** (decision 23).

---

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | **No account before consent.** An unknown provider identity, or a link for an address with no account, creates **no `users` row**. It gets a signed, short-lived **signup ticket**. The account (verified, profile seed, CGV consent) is created in one commit when « Finaliser votre inscription » is submitted. | Gated by construction, like `_issue_session`: no row → no session → no route needs a consent check. Someone who abandons leaves nothing behind. |
| 2 | New table **`auth_identities`** `(provider, subject) → user_id`, not `users.google_sub` / `microsoft_sub`. | Apple or FranceConnect become a new `provider` value, not a migration per provider. |
| 3 | A password-less account stores an **unusable hash**: bcrypt of 32 random bytes (`secrets.token_bytes`). `password_hash` stays `NOT NULL`. | `password_fingerprint`, the refresh `pwv` and the reset link's single use all keep working unchanged. Any password typed at login fails → « Identifiants incorrects. ». Setting a password later is the existing reset flow. Rejected alternative: a nullable column, which would give every reader of `password_hash` a None branch. |
| 4 | New table **`login_links`** `(id, email_hash, created_at, used_at)`. `email_hash` = HMAC-SHA256 of the normalised address, keyed on `SECRET_KEY`. Rows older than 24 h are purged on every insert. | The link also serves addresses with **no account yet**, so `users` has no row to hold a nonce or a pacing clock. The table provides both. HMAC rather than the address: we keep nothing readable about people who never signed up, and a table dump does not reveal which known addresses asked for a link. |
| 5 | OAuth start: Authlib `authorize_redirect` with **state + PKCE (S256) + nonce**, all held by Authlib in Flask's signed `session` cookie. `next` (through `safe_next`) is stored beside the state. **`prompt=select_account`** on both providers. `redirect_uri` is built from `APP_URL`. Microsoft: tenant `common`, **`response_mode=query`**. | `select_account`: job seekers use shared computers (agencies, libraries); without it the next person is signed in silently as the last one. `APP_URL`: Flask sits behind nginx and sees `backend:5000`. `query`: `form_post` is a cross-site POST, which does not carry a Lax cookie, so the state would be lost. |
| 6 | Callback: Authlib checks the state, exchanges the code with the PKCE verifier, and validates the ID token (JWKS signature, `aud`, `exp`, `nonce`). **Microsoft `iss` gets a custom check**: it must equal `https://login.microsoftonline.com/{tid}/v2.0`, with `tid` taken from the token. | The `/common` metadata publishes a template issuer (`…/{tenantid}/v2.0`), so the default issuer check fails for every Microsoft token. |
| 7 | **Trusted email.** Google: `email_verified is True`. Microsoft: `tid == 9188040d-6c67-4c5b-b112-36a304b66dad` (personal accounts), **or** `xms_edov` truthy (`True`, `"1"` or `"true"`). Anything else is untrusted, including an absent `email` claim (a phone-only Microsoft account). A trusted address is normalised exactly as `register` stores it (strip, lower) before any lookup. | Microsoft's `email` claim on work / school accounts can be set by a tenant admin to any address ("nOAuth" account takeover). `xms_edov` says the tenant has proven ownership of the email's domain. Microsoft emits it as a string in some forms. |
| 8 | **Resolution order** at the callback: (1) `(provider, sub)` known → that account; (2) trusted email matching an account → add the identity, enter (decision 9); (3) trusted email, no account → signup ticket; (4) otherwise → refused (decision 10). | A known identity wins even if the provider address changed. The address is only used to *create* a link, and only when it is trusted. |
| 9 | Entering an **unverified** account by any new door (provider or link): the password is replaced with a new unusable hash, `email_verified_at` is set to now, and `demande_mail.notify_if_visible()` runs. The profile seed stays. **No notice** is shown about the wipe. | Ruling 4. The same precedent as a reset link proving an inbox (email verification spec, decision 12), including keeping the seed. The new hash also changes `pwv`, killing any reset link the stranger had. Accepted consequence: a person who signed up with a password and never confirmed it finds that password gone; « Mot de passe oublié » restores it. |
| 10 | An **untrusted** address with no known identity creates and links nothing. → `/connexion?erreur=email_non_verifie`. | Safer than an unlinked account the person would then have to merge. The email link is always available and proves the address directly. |
| 11 | Landing after the callback: `next`, else `_landing()` (a conseiller with a demande → `/conseiller`), else the role's home. A 3-line Python `_home_path(role)` mirrors `frontend/src/lib/home.ts` `homeFor`, with a comment naming it. The JSON endpoints (link consume, signup) return `{user, next}` like `verify-email`, and the page applies `next ?? homeFor(role)`. | A redirect can't ask the frontend where home is. The alternative, an extra client-side hop page, costs a round trip on every provider login. |
| 12 | Callback failures **never show JSON**. All go to `/connexion?erreur=<code>`: `annule` (provider `error=access_denied`), `echec` (any other provider error, state / exchange / token failure — logged), `indisponible` (provider not configured), `email_non_verifie` (decision 10). | The browser is on a top-level navigation; a JSON body would be a dead end. |
| 13 | `GET /api/auth/providers` → `{google: bool, microsoft: bool}`, true when both keys are set. Buttons show only for configured providers. An unconfigured `/start` → `?erreur=indisponible`. | Code deploys before the keys reach `.env`; the buttons appear on the restart that brings them. |
| 14 | `POST /api/auth/email-link {email, next}`: always 200 `{mail_sent}`, same body for every address. Pacing: an existing account → `auth_mail.cooldown_passed(user)` (the clock shared with verification and reset); no account → the latest `login_links` row for the hash. Inside the cooldown → `mail_sent: true` (on its way). The row and the `auth_mail_sent_at` stamp are written **only after Resend accepts the mail**. | No enumeration: it sends whether or not an account exists. One mail a minute per address whatever the endpoint. A provider outage never blocks the retry (the existing `auth_mail` rule). |
| 15 | Link token: itsdangerous salt `email-login`, payload `{jti, email, next}`, `max_age` 15 min. Mail « Votre lien de connexion », one wording for every case, built with `_mail`. `email_service._deliver_link` takes the recipient **address** instead of a user. | The link must reach addresses with no account. One wording: the mail goes to the inbox owner, and nothing in it varies by account state except the greeting's prénom. |
| 16 | The link lands on **`/connexion/lien?token=…`**. On load, `POST /email-link/check` (does not consume) → `{email}` or `link_expired` / `link_invalid`. The page shows the address and a **« Continuer »** button that calls `POST /email-link/consume`. | Mail security scanners (Outlook Safe Links, corporate gateways) open links, and some run JS. Consuming on load would burn the single use before the person arrives. Showing the address also defeats a login-CSRF link to someone else's account: the person sees an address that is not theirs. |
| 17 | Consume is atomic: `UPDATE login_links SET used_at = now WHERE id = :jti AND used_at IS NULL`. A rowcount other than 1 → `link_invalid`. Then: account exists → decision 9 if unverified, `_issue_session`, `{user, next}`; no account → signup ticket, `{signup: true}`. | A double click cannot use the link twice. Also covers the row missing (mail never accepted, or purged). |
| 18 | Signup ticket: itsdangerous salt `signup-ticket`, payload `{method, sub, email, prenom_hint, next}`, `max_age` 30 min. Carried in an HttpOnly cookie **`signup_ticket`**, `Path=/api/auth`, SameSite=Lax, Secure in production. `method` is `google`, `microsoft` or `email`; `sub` is null for `email`; `prenom_hint` is the provider's `given_name` when sent. | The cookie keeps `sub` and the address out of URLs, browser history and nginx logs. It is a strictly necessary cookie (no banner). |
| 19 | `POST /api/auth/signup {prenom, tranche_age, consent}` validates (prénom required, `tranche_age` in `AGE_BRACKETS` — legacy `moins_25` refused, `consent is True`), then resolves again: the identity now exists → enter it; the address now has an account → decision 9 path (the ticket proves the address); otherwise one commit of `User` (unusable hash, `email_verified_at` = now) + `AuthIdentity` (provider methods) + `Profile` (prénom, tranche_age, `consent_at`, `CONSENT_VERSION`). An `IntegrityError` → rollback and fall back to the first two branches. The cookie is cleared; `_issue_session`; `{user, next}`. | Another tab, or the same person on another device, may finish first. The unique constraints settle the race. An existing account's profile is never overwritten by this form. |
| 20 | `register`'s seed validation and `Profile` creation move into one helper used by both `register` and `signup`. | Two consent paths written twice would drift apart. |
| 21 | **No mail** when an account is created through a ticket. | The address is already proven, and the 100-mails-a-day Resend quota is shared by every mail. |
| 22 | Page **`/inscription/finaliser`**, title « Finaliser votre inscription ». Prénom prefilled from the ticket. Age bracket and consent asked on the page. Not « Complétez votre profil ». | No provider gives an age bracket with basic scopes. Google's `user.birthday.read` is a sensitive scope (weeks of verification) and returns a date of birth, which the profile deliberately never stores. Consent must be a click on our site. « Complétez votre profil » is already `LOCK_PROFILE`, the voyage's locked-session card. |
| 23 | nginx: `auth_mail` gains `auth/email-link`; `auth_login` gains `auth/email-link/(check\|consume)` and `auth/signup`; a **new `auth_oauth` zone, 30 r/m burst 10**, covers `auth/(google\|microsoft)/(start\|callback)`. | A France Travail workshop puts a room behind one IP, and each provider sign-in costs two requests; `auth_login`'s 10 r/m would 429 the room. These endpoints check no guessable secret; the limit only caps outbound calls to the providers. |
| 24 | `ProductionConfig`: `SESSION_COOKIE_SECURE = True`, `SESSION_COOKIE_SAMESITE = "Lax"`. | Authlib's state lives in Flask's session cookie, which is not used anywhere else today and has no production settings. |
| 25 | Scopes `openid email profile` only. **No provider token is kept** (no access or refresh token stored). Only `provider` + `sub` are stored. | We never call a provider API; a stored token would only be a liability. |
| 26 | `/inscription-conseiller` and `/profil` are unchanged. No « comptes connectés » management in round 1. | Ruling 7; YAGNI. |

---

## User flows

### « Continuer avec Google / Microsoft »
1. `/connexion` or `/inscription` → the button, a plain link to
   `/api/auth/<provider>/start?next=<redirect>`.
2. Provider account picker → consent → back to `/api/auth/<provider>/callback`.
3. Known identity, or trusted address of an existing account → signed in →
   `next` / `/conseiller` / role home.
4. Trusted address, no account → `/inscription/finaliser` (prénom prefilled,
   tranche d'âge, CGV) → « Créer mon compte » → signed in → `next ?? homeFor`.
5. Untrusted Microsoft address → `/connexion` with « Ce compte ne confirme pas
   votre adresse email. Utilisez « Recevoir un lien de connexion ». »
6. Cancelled at the provider → `/connexion` with « Connexion annulée. »

### « Recevoir un lien de connexion »
1. The button reveals an email field → « Envoyer le lien ».
2. « Un lien de connexion a été envoyé à marie@… Il est valable 15 minutes. »,
   « Renvoyer » after a 60 s countdown, « Pensez à regarder dans les courriers
   indésirables. » If `mail_sent` is false: « L'envoi a échoué. Réessayez dans
   un instant. »
3. The link opens `/connexion/lien?token=…` → « Connexion avec marie@… » →
   « Continuer ».
4. Existing account → signed in. No account → `/inscription/finaliser`.
5. Expired / used / invalid → the message + an email field + « Recevoir un
   nouveau lien ».

### Finalising after the ticket expired
« Cette étape a expiré. Recommencez depuis la page d'inscription. » + link to
`/inscription`.

### Setting a password later
A password-less account uses « Mot de passe oublié » as today: link → new
password → signed in. Nothing new.

---

## Data model

One migration, `down_revision = 'a9b0c1d2e3f4'` (email_verification, the
current head). No change to `users`.

**`auth_identities`** — `models/auth_identity.py`

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36)` PK | uuid4 |
| `user_id` | `VARCHAR(36)` NOT NULL | FK `users.id` `ON DELETE CASCADE`, indexed |
| `provider` | `VARCHAR(16)` NOT NULL | `google` \| `microsoft` |
| `subject` | `VARCHAR(255)` NOT NULL | the ID token's `sub` |
| `created_at` | `DATETIME` NOT NULL | |

`UNIQUE (provider, subject)` named `uq_auth_identities_provider_subject`.

**`login_links`** — `models/login_link.py`

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36)` PK | uuid4, the token's `jti` |
| `email_hash` | `CHAR(64)` NOT NULL | HMAC-SHA256 hex (decision 4) |
| `created_at` | `DATETIME` NOT NULL | the pacing clock for addresses without an account |
| `used_at` | `DATETIME` NULL | set once, atomically (decision 17) |

Index `(email_hash, created_at)`.

---

## Backend

### Endpoints

| Method + path | Body / query | Success | Errors |
|---|---|---|---|
| `GET /api/auth/providers` | — | `{google, microsoft}` | — |
| `GET /api/auth/<provider>/start` | `?next=` | 302 to the provider | 302 `/connexion?erreur=indisponible`; unknown provider → 404 |
| `GET /api/auth/<provider>/callback` | provider query | 302 to the landing (decision 11) + session cookies, or 302 `/inscription/finaliser` + `signup_ticket` cookie | 302 `/connexion?erreur=…` (decision 12) |
| `POST /api/auth/email-link` | `{email, next}` | 200 `{mail_sent}` | 400 « Email invalide. » |
| `POST /api/auth/email-link/check` | `{token}` | 200 `{email}` | 400 `{code: link_expired \| link_invalid}` |
| `POST /api/auth/email-link/consume` | `{token}` | 200 `{user, next}` + cookies, or 200 `{signup: true}` + `signup_ticket` | 400 `{code: link_expired \| link_invalid}` |
| `GET /api/auth/signup` | cookie | 200 `{email, prenom, method}` | 400 `{code: link_expired \| link_invalid}` |
| `POST /api/auth/signup` | `{prenom, tranche_age, consent}` + cookie | 200 `{user, next}` + cookies, cookie cleared | 400 validation sentence; 400 `{code: link_expired \| link_invalid}` |

The link error sentences are `LINK_ERRORS`, as for the verification and reset
links.

### Files

- **`extensions.py`** — `oauth = OAuth()` (Authlib Flask client), initialised
  in the app factory.
- **`services/oauth_clients.py`** (new) — registers `google` (metadata
  `https://accounts.google.com/.well-known/openid-configuration`) and
  `microsoft` (`https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration`)
  only when their two keys are set. Scope `openid email profile`,
  `code_challenge_method: S256`. `configured() -> dict[str, bool]`.
- **`services/sign_in.py`** (new) — the logic, testable without HTTP:
  - `trusted_email(provider, claims) -> str | None` (decision 7)
  - `microsoft_issuer_ok(claims) -> bool` (decision 6)
  - `resolve(provider, sub, email) -> Outcome`: existing user / signup / refused (decision 8)
  - `enter(user, provider=None, sub=None)`: adds the identity if given; applies decision 9
  - `unusable_password_hash() -> str` (decision 3)
- **`routes/auth_oauth.py`** (new blueprint, prefix `/api/auth`) —
  `providers`, `start`, `callback`.
- **`routes/auth_link.py`** (new blueprint, prefix `/api/auth`) —
  `email-link`, `email-link/check`, `email-link/consume`.
- **`routes/auth.py`** — `GET` / `POST /signup`; the shared seed helper
  (decision 20); `_home_path(role)` (decision 11). Splitting the new routes out
  keeps this file from doubling.
- **`utils/auth_links.py`** — `make_login_token(jti, email, next)` /
  `load_login_token`, `LOGIN_MAX_AGE = 15 * 60`; `make_signup_ticket(...)` /
  `load_signup_ticket`, `SIGNUP_MAX_AGE = 30 * 60`; `email_hash(email)`.
- **`services/auth_mail.py`** — `login_link_if_due(email, user | None, next)
  -> bool` with both pacing branches (decision 14).
- **`services/email_service.py`** — `send_login_link(to, prenom, link) ->
  bool`; `_deliver_link(to, …)` takes the address (decision 15); the dev log
  path (no `RESEND_API_KEY` + debug) applies to this link too.
- **`config.py`** — `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
  `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`; decision 24.
- **`requirements.txt`** — `Authlib` and `requests`, pinned.
- **`backend/.env.example`** — the four keys, empty.

### Mail copy

**Votre lien de connexion**
> Bonjour {prénom}, ← « Bonjour, » without an account or a prénom
> Voici votre lien pour accéder à neoori. Il est valable 15 minutes et ne sert
> qu'une fois.
> [Accéder à neoori]
> Si vous n'avez pas demandé ce lien, ignorez ce message.

CLAUDE.md's « Mails transactionnels » table gains this row once it ships.

---

## Frontend

Read `node_modules/next/dist/docs` before writing (`frontend/AGENTS.md`:
Next.js 16).

- **`components/auth/SocialSignIn.tsx`** (new) — at the top of `/connexion`
  and `/inscription`:
  - « Continuer avec Google » and « Continuer avec Microsoft »: plain `<a>` to
    `${BASE}/api/auth/<provider>/start?next=…`, shown per `GET
    /api/auth/providers`. Inline SVG logos following each provider's branding
    guidelines.
  - « Recevoir un lien de connexion »: reveals the email form and the pending
    state (flows above).
  - Then a separator: « ou » on `/connexion`, « ou avec un mot de passe » on
    `/inscription`. The existing forms are unchanged below it.
- **`lib/useCooldown.ts`** (new) — the 60 s countdown pulled out of
  `VerificationPending`, used by both.
- **`/connexion`** — reads `?erreur=` and shows an `Alert`:
  - `annule` — « Connexion annulée. »
  - `echec` — « La connexion n'a pas abouti. Réessayez, ou utilisez « Recevoir
    un lien de connexion ». »
  - `indisponible` — « Ce mode de connexion n'est pas disponible pour le
    moment. »
  - `email_non_verifie` — « Ce compte ne confirme pas votre adresse email.
    Utilisez « Recevoir un lien de connexion ». »
- **`app/(auth)/connexion/lien/page.tsx`** (new) — decision 16.
- **`app/(auth)/inscription/finaliser/page.tsx`** (new) — decision 22:
  - Header: `AuthLayout`, the title, sub « Dernière étape : ces informations
    servent à personnaliser vos analyses. »
  - Fields: email read-only, prénom, tranche d'âge (`TRANCHES_AGE`), and the
    same CGV + confidentialité checkbox as `/inscription`.
  - Button: « Créer mon compte ».
  - Not in `proxy.ts PROTECTED`: there is no session yet.
- `api.ts` calls to the new endpoints use `skipRedirect`.

---

## nginx

In `nginx/dev.conf`, `nginx/templates-http/default.conf.template` and
`nginx/templates-https/default.conf.template`:

```nginx
map $uri $auth_mail_key {
    ~^/api/(auth/(register|resend-verification|forgot-password|email-link)|counselor/apply)/?$  $binary_remote_addr;
}
map $uri $auth_login_key {
    ~^/api/auth/(login|verify-email|reset-password|email-link/(check|consume)|signup)/?$  $binary_remote_addr;
}
map $uri $auth_oauth_key {
    ~^/api/auth/(google|microsoft)/(start|callback)/?$  $binary_remote_addr;
}
limit_req_zone $auth_oauth_key zone=auth_oauth:10m rate=30r/m;
# in the /api/ location, beside the two existing lines:
limit_req zone=auth_oauth burst=10 nodelay;
```

The deploy already re-renders and reloads nginx (`deploy.yml`, email
verification spec decision 22).

---

## Privacy

`/confidentialite` gains this line. **The PM approves the wording before the
provider keys go live.**

> **Connexion avec Google ou Microsoft.** Si vous choisissez ce mode de
> connexion, Google ou Microsoft nous transmet votre adresse email, votre
> prénom et un identifiant de compte. Nous conservons l'adresse et
> l'identifiant, et le prénom seulement si vous le gardez à l'inscription. Nous
> ne recevons ni votre mot de passe, ni l'accès à vos emails, contacts ou
> fichiers. Ces données servent uniquement à vous connecter.

---

## Testing

Backend (pytest). Resend is already fenced off in `conftest.py`. Authlib's
`authorize_access_token` is mocked to return chosen ID token claims.

- **Resolution:** each branch of decision 8.
- **Trust:**
  - Google `email_verified: false` → refused.
  - Microsoft: personal-account tenant → trusted; work tenant without
    `xms_edov` → refused; `xms_edov` as `True`, `"1"`, `"true"` → trusted.
- **Issuer:** `microsoft_issuer_ok` rejects a `tid` / `iss` mismatch.
- **Linking an unverified account:**
  - hash replaced and `pwv` changed (an old reset link → `link_invalid`)
  - `email_verified_at` set
  - demande mail sent
  - profile seed kept
- **Start / callback:** an unsafe `next` is dropped. Each `?erreur=` code is
  reached. An unconfigured provider → `indisponible`, and `/providers` says
  false.
- **Email link:**
  - Send: identical 200 for an address with and without an account; the
    cooldown on both branches; no row and no stamp when the send fails.
  - Consume: second consume → `link_invalid`; expired and tampered tokens;
    `check` never consumes.
  - Outcomes: unknown address → ticket; unverified account → decision 9.
- **Ticket:**
  - missing or expired → link error
  - consent false and `moins_25` → refused
  - success → user + identity + profile in one commit, cookie cleared, session
    opened, `next` carried
  - race (account created meanwhile) → enters it, profile untouched
- **Regression:** the existing `_issue_session` refusal tests stay green.

Frontend: typecheck + build. Local end-to-end on `http://localhost:8080` with
the localhost redirect URIs; link mails read from `docker compose logs
backend`. nginx: a curl burst per zone shows the 429.

---

## Rollout

1. **Code ships** (push `initial` only with the developer's go-ahead). The
   migration runs at container start (`backend/entrypoint.sh`). The email link
   works at once. The provider buttons stay hidden: `/providers` says false.
2. **The PM approves the `/confidentialite` line** and it ships. This happens
   before step 3, so the page is accurate the day the buttons appear.
3. **Keys:** the developer creates both apps (appendices A and B), pastes the
   four keys into `/srv/neoori/.env`, then on the VPS runs
   `docker compose -f docker-compose.prod.yml up -d --force-recreate backend`.
   The buttons appear.
4. **CLAUDE.md** gains a « Connexion Google / Microsoft / lien » section (the
   rules a later change could undo: decisions 1, 7, 9, 16, 17), and the link
   mail joins the « Mails transactionnels » table.

### Known limitation

Some organisations only let staff consent to apps from a Microsoft-verified
publisher. Their work accounts see « Approbation de l'administrateur requise »
until neoori is a verified publisher, which needs a Microsoft AI Cloud Partner
Program account. Personal accounts (Outlook, Hotmail, Live) are not affected.
Not addressed in round 1.

---

## Appendix A — Google OAuth client

At <https://console.cloud.google.com>:

1. Project picker (top bar) → **New project** → name `neoori` → **Create**, then
   select it.
2. ☰ menu → **Google Auth Platform**.
   - First visit only: **Get started**.
   - App name `neoori`; support email: an address you read
     (`bonjour@neoori.tech`).
   - **Audience: External**.
   - Contact email: yours.
   - Accept the policy → **Create**.
3. **Branding**:
   - Home page `https://neoori.tech`
   - Privacy policy `https://neoori.tech/confidentialite`
   - Terms of service `https://neoori.tech/cgv`
   - Authorised domain `neoori.tech`
   - **Leave the logo empty**: uploading one triggers brand verification
     (days).
   - **Save**.
4. **Data Access** → **Add or remove scopes** → tick `openid`,
   `…/auth/userinfo.email`, `…/auth/userinfo.profile` → **Update** → **Save**.
5. **Clients** → **Create client**:
   - Application type **Web application**, name `neoori web`.
   - Authorised JavaScript origins: none.
   - Authorised redirect URIs:
     - `https://neoori.tech/api/auth/google/callback`
     - `http://localhost:8080/api/auth/google/callback`
   - **Create**. **Copy the client secret now**: Google shows it in full only
     at creation (download the JSON if offered).
6. **Audience** → **Publish app** → confirm. The status becomes « In
   production ». With only these three basic scopes there is no review, and
   users see no « unverified app » warning.
7. Paste into `/srv/neoori/.env` and `backend/.env`:
   `GOOGLE_CLIENT_ID=…`, `GOOGLE_CLIENT_SECRET=…`.

## Appendix B — Microsoft Entra app registration

At <https://entra.microsoft.com>, signed in with the Microsoft account that
will own the app. If the portal says the account has no directory, create a
free Azure account first; it creates one.

1. **Identity → Applications → App registrations → New registration**:
   - Name `neoori`.
   - Supported account types: **Accounts in any organizational directory (Any
     Microsoft Entra ID tenant — Multitenant) and personal Microsoft accounts**.
   - Redirect URI: platform **Web**,
     `https://neoori.tech/api/auth/microsoft/callback`.
   - **Register**.
2. **Overview**: copy the **Application (client) ID**.
3. **Authentication**:
   - **Add URI** (Web) `http://localhost:8080/api/auth/microsoft/callback`.
   - Leave « Access tokens » and « ID tokens » (implicit / hybrid) **unticked**:
     the flow is authorization code.
   - **Save**.
4. **Certificates & secrets → Client secrets → New client secret**:
   - Description `neoori prod 2026-10`; expires **24 months**.
   - **Add**, then **copy the Value** now (not the Secret ID).
   - **Write the expiry date down** (appendix C).
5. **Token configuration → Add optional claim** → token type **ID** → tick
   `email` and `given_name` → **Add**. Accept the prompt that adds the Microsoft
   Graph `email` / `profile` permissions.
6. **Manifest**: in `optionalClaims.idToken`, add
   `{"name": "xms_edov", "source": null, "essential": false, "additionalProperties": []}`
   → **Save**. The optional-claims UI no longer lists `xms_edov`; the manifest
   is the only place to add it. Without it, every work / school account is
   refused (decision 7).
7. **API permissions**: Microsoft Graph delegated `openid`, `email`, `profile`
   are enough. `User.Read` can be removed (neoori never calls Graph), which
   shortens the consent screen.
8. **Branding & properties**:
   - Home page `https://neoori.tech`
   - Terms of service `https://neoori.tech/cgv`
   - Privacy statement `https://neoori.tech/confidentialite`
   - **Save**.
9. Paste into `/srv/neoori/.env` and `backend/.env`:
   `MICROSOFT_CLIENT_ID=…`, `MICROSOFT_CLIENT_SECRET=…`.

## Appendix C — Microsoft secret renewal

The secret dies on its expiry date, and Microsoft sign-in breaks with it
(`?erreur=echec`).

- The expiry date is written in `DOCKER.md` and as a comment beside
  `MICROSOFT_CLIENT_SECRET` in `/srv/neoori/.env`.
- **A month before expiry:**
  1. Create a second secret; the two live side by side.
  2. Paste it in.
  3. Recreate the backend (rollout step 3's command).
  4. Check one Microsoft sign-in.
  5. Delete the old secret.
- Claude schedules a reminder for that date once the developer gives the date
  the secret was created.
