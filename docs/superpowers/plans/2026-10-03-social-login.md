# Connexion Google / Microsoft / lien — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add « Continuer avec Google », « Continuer avec Microsoft » and « Recevoir un lien de connexion », so a job seeker can sign up or sign in without a password or a verification mail.

**Architecture:**
- **OAuth.** Flask runs the authorization-code flow with Authlib: state + PKCE + nonce, and the ID token's claims are checked.
- **Email link.** A single-use link built on itsdangerous, with a `login_links` table holding its single use and its pacing clock.
- **One session door.** Both paths end in `routes/auth._issue_session()`, like the password login.
- **No account before consent.** Someone with no account gets a signed `signup_ticket` cookie and finishes on `/inscription/finaliser`. The account, its provider identity and its CGV consent are created there, in one commit.
- **Frontend.** Next.js only links to the server (no provider JavaScript), calls a few JSON endpoints, and gains two pages.

**Tech Stack:**
- Backend: Flask 3.1, Flask-SQLAlchemy / Alembic, Flask-JWT-Extended (cookies), Authlib 1.8.0 (+ joserfc), itsdangerous, Resend.
- Frontend: Next.js 16.2 App Router, React 19, react-hook-form + zod 4, shadcn on base-ui.
- nginx `limit_req`.

**Spec:** `docs/superpowers/specs/2026-10-03-social-login-design.md`. The decision numbers below ("decision 9") are the spec's.

## Before you start

- **Branch.** `git switch -c feat/social-sign-in` from `initial` (the spec is commit `cef2dec`).
- **Never push.** Deploying is pushing `initial`, and the developer decides when.
- **Backend tests**, from `backend/`: `venv/bin/pytest -q -p no:cacheprovider`. Baseline on 2026-10-03: `1201 passed` in about 20 s.
- **Frontend checks**, from `frontend/`:
  - `npx tsc --noEmit` is clean today.
  - `npx eslint <files you touched>`. The repo has 13 lint problems today, none in a file this plan touches; leave them alone.
  - `npm run build`.
  - There is no frontend test runner. Pages are verified by type check, lint, build and Task 14's walk-through.
- **Next.js 16.** `frontend/AGENTS.md` says APIs differ from older versions. Before writing a page, read `frontend/node_modules/next/dist/docs/01-app/03-api-reference/04-functions/use-search-params.md` and `use-router.md`.
- **Local stack.** `docker compose up -d` → http://localhost:8080. There is no Resend key locally, so links are printed in `docker compose logs backend`.

## Deviations from the spec's file list

Implementation detail only; the behaviour is the spec's.

1. **cryptography 43.0.3 → 50.0.2.** Authlib 1.8.0 requires `cryptography>=45.0.1`; a dry-run resolve was checked on 2026-10-03. The only users are Fernet and HKDF in `utils/crypto.py`.
2. **One Authlib registry per app**, created in `services/oauth_clients.init_app`, not an `extensions.oauth` singleton. Authlib's `OAuth` holds one `app` and caches its clients, and the test suite builds a new app for every test.
3. **`_home_path`** lives in `routes/auth_oauth.py`, beside its only caller.
4. **`email_service.send_login_link(to, prenom, token)`** takes the token and builds the URL from `APP_URL`, like the other mails. The caller needs the `jti` before sending.
5. **The unusable hash** hashes `secrets.token_urlsafe(32)` (256 bits). bcrypt refuses a NUL byte, which `token_bytes` can produce.
6. **Two guards found while planning:**
   - a prénom longer than `profiles.prenom` (120) or not encodable is a 400 in the seed helper `register` and `signup` share. It was a MySQL "Data too long" 500 waiting to happen at `register` too.
   - an address carrying a lone surrogate fails `email_shape_ok`.
7. **`default_timeout=10`** on every Authlib HTTP call, so a hung provider cannot hold a gunicorn thread.

## Global Constraints

- **Copy.** UI copy in French, sober. Banned words (CLAUDE.md): boussole, copilote, miroir, révélation, épanouissement, alignement, excellence, talent unique, vous vous démarquez.
- **Comments and commits** in English. Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Auth lives in Flask** (`routes/auth.py`, JWT cookies), not NextAuth. Every session opens through `routes/auth._issue_session()`, which refuses an unverified account.
- **No provider JavaScript on our pages.** A provider button is a plain `<a href="/api/auth/<provider>/start?next=…">`.
- **Pins:** `Authlib==1.8.0`, `cryptography==50.0.2`, `requests==2.33.1`.
- **Scopes:** exactly `openid email profile`. No provider access or refresh token is stored; only `provider` + `sub`.
- **Microsoft:** tenant `common`. Personal-account tenant id `9188040d-6c67-4c5b-b112-36a304b66dad`. `response_mode=query`.
- **Both providers:** `prompt=select_account`.
- **Email link:** itsdangerous salt `email-login`, valid 15 min, single use, lands on `/connexion/lien?token=…`.
- **Signup ticket:** salt `signup-ticket`, valid 30 min. Cookie `signup_ticket`, `Path=/api/auth`, HttpOnly, SameSite=Lax, Secure in production.
- **Pacing:** one account mail a minute per address (`auth_mail.COOLDOWN`). A `login_links` row or an `auth_mail_sent_at` stamp is written only after Resend accepted the mail.
- **`next`** passes only through `auth_links.safe_next` (server) or `safeRedirect` (client), then travels verbatim: never decoded or rebuilt.
- **SQLite vs MySQL.** Tests run on SQLite, production on MySQL 8.4: tests enforce neither column lengths nor collations, so lengths are validated in code.
- **Never push.**

## Review Focus

1. **A provider address in capitals** (`Marie.Dupont@Outlook.fr`) for an account stored lowercase must enter that account, never start a second signup.
   → Task 4: `test_a_provider_address_in_capitals_enters_the_lowercase_account`.
2. **No live OAuth state.** A callback reached without one (Back after signing in, a refresh, a second tab, a bookmarked callback URL, a lost session cookie), or a `/start` while the provider's discovery document is unreachable, must end on `/connexion?erreur=echec`, never a 500 page.
   → Task 8: `test_a_callback_without_a_live_state_is_a_failure_not_a_500`, `test_a_callback_replayed_with_back_is_a_failure`, `test_an_unreachable_provider_is_a_failure_not_a_500`.
3. **« Créer mon compte » sent twice** (double click, two tabs) must leave exactly one account, and both requests end signed in.
   → Task 7: `test_a_second_submit_enters_the_first_one_s_account`, `test_a_submit_that_loses_the_race_enters_the_winner_s_account`.
4. **A prénom longer than the column (120)**, from a provider's `given_name` or typed, must neither prefill a form that can never be sent nor reach MySQL.
   → Task 4: `test_the_prenom_hint_is_trimmed_to_what_the_profile_holds`.
   → Task 7: `test_a_prenom_longer_than_the_column_is_refused_not_a_500`, `test_register_refuses_it_too`.
5. **A destination with a query string** (`/analyse/nouveau?parcours=2&x=a%20b`) must survive the provider round trip byte for byte.
   → Task 8: `test_the_destination_survives_the_round_trip_byte_for_byte`.

---

### Task 1: Dependencies — Authlib 1.8 and the cryptography it needs

**Files:**
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: nothing.
- Produces: `authlib`, `joserfc` and `requests` importable in the backend venv and in the dev image.

- [ ] **Step 1: Edit the pins**

In `backend/requirements.txt`, replace the line `cryptography==43.0.3` with `cryptography==50.0.2`. Add these two lines right after `resend==2.30.0`:

```
Authlib==1.8.0
requests==2.33.1
```

- [ ] **Step 2: Install**

Run: `cd backend && venv/bin/pip install -r requirements.txt`
Expected: ends with `Successfully installed Authlib-1.8.0 cryptography-50.0.2 joserfc-1.7.5`. `requests` is already 2.33.1.

- [ ] **Step 3: Check the versions**

Run: `venv/bin/python -c "import authlib, cryptography, joserfc; print(authlib.__version__, cryptography.__version__)"`
Expected: `1.8.0 50.0.2`

- [ ] **Step 4: Run the whole suite on the new cryptography**

Run: `venv/bin/pytest -q -p no:cacheprovider`
Expected: `1201 passed`. `tests/test_migration_erase_billets.py` exercises Fernet encrypt and decrypt.

- [ ] **Step 5: Rebuild the dev image so the container has Authlib**

Run: `docker compose build backend && docker compose run --rm --no-deps backend python -c "import authlib; print(authlib.__version__)"`
Expected: `1.8.0`. If Docker is not running, note it in your report and go on; Task 9 needs the image.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt
git commit -m "build(backend): Authlib 1.8 and the cryptography it needs

Authlib 1.8.0 requires cryptography>=45.0.1, so 43.0.3 becomes 50.0.2.
Its only users here are Fernet and HKDF (utils/crypto.py), unchanged
across those versions.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `auth_identities` and `login_links` — models and migration

**Files:**
- Create: `backend/app/models/auth_identity.py`
- Create: `backend/app/models/login_link.py`
- Create: `backend/migrations/versions/b0c1d2e3f4a5_social_sign_in.py`
- Modify: `backend/app/__init__.py:151-154` (the models import tuple)
- Test: `backend/tests/test_social_sign_in_models.py`

**Interfaces:**
- Consumes: `users.id`.
- Produces:
  - `app.models.auth_identity.PROVIDERS = ("google", "microsoft")`
  - `AuthIdentity(id: str, user_id: str, provider: str, subject: str, created_at: datetime)` on table `auth_identities`, with `UNIQUE (provider, subject)`
  - `app.models.login_link.LoginLink(id: str, email_hash: str, created_at: datetime, used_at: datetime | None)` on table `login_links`. Its `id` is the link's `jti`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_social_sign_in_models.py`:

```python
"""The two tables social sign-in adds (social sign-in spec, decisions 2
and 4)."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.auth_identity import AuthIdentity
from app.models.login_link import LoginLink


def test_one_provider_account_opens_one_neoori_account(app, make_user):
    marie = make_user(email="marie@test.fr")
    paul = make_user(email="paul@test.fr")
    db.session.add(AuthIdentity(user_id=marie.id, provider="google", subject="1234"))
    db.session.commit()
    db.session.add(AuthIdentity(user_id=paul.id, provider="google", subject="1234"))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_the_same_subject_at_another_provider_is_another_identity(app, make_user):
    marie = make_user()
    db.session.add_all([
        AuthIdentity(user_id=marie.id, provider="google", subject="1234"),
        AuthIdentity(user_id=marie.id, provider="microsoft", subject="1234"),
    ])
    db.session.commit()
    assert AuthIdentity.query.filter_by(user_id=marie.id).count() == 2


def test_erasing_an_account_erases_its_identities(app, make_user):
    marie = make_user()
    db.session.add(AuthIdentity(user_id=marie.id, provider="google", subject="1234"))
    db.session.commit()
    db.session.delete(marie)
    db.session.commit()
    assert AuthIdentity.query.count() == 0


def test_a_login_link_row_keeps_no_address(app):
    columns = {c.name for c in LoginLink.__table__.columns}
    assert columns == {"id", "email_hash", "created_at", "used_at"}
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd backend && venv/bin/pytest -q -p no:cacheprovider tests/test_social_sign_in_models.py`
Expected: collection error `ModuleNotFoundError: No module named 'app.models.auth_identity'`.

- [ ] **Step 3: Write the models**

Create `backend/app/models/auth_identity.py`:

```python
"""A Google or Microsoft account that opens a neoori account (social sign-in
spec, decision 2).

One row per (provider, subject): `subject` is the ID token's `sub`, stable for
the life of the provider account. No provider token and no provider address
is kept — users.email stays the one address (decision 25). Apple or
FranceConnect would be a new `provider` value, not a new column.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy.dialects import mysql

from ..extensions import db

PROVIDERS = ("google", "microsoft")

# Case matters: Microsoft subjects are base64url, and two that differ only by
# case belong to two different people. MySQL's default collations compare
# case-insensitively, so the column takes the binary one there.
SUBJECT_TYPE = db.String(255).with_variant(
    mysql.VARCHAR(255, collation="utf8mb4_bin"), "mysql"
)


class AuthIdentity(db.Model):
    __tablename__ = "auth_identities"
    __table_args__ = (
        db.UniqueConstraint("provider", "subject", name="uq_auth_identities_provider_subject"),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider = db.Column(db.String(16), nullable=False)
    subject = db.Column(SUBJECT_TYPE, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
```

Create `backend/app/models/login_link.py`:

```python
"""The email sign-in link's single use and its pacing clock (social sign-in
spec, decisions 4, 14 and 17).

A table rather than a column on users: the link also reaches addresses that
have no account yet. It keeps an HMAC of the address
(utils/auth_links.email_hash), never the address itself. Rows older than a
day are purged on every insert (services/auth_mail.login_link_if_due).
"""
from datetime import datetime

from ..extensions import db


class LoginLink(db.Model):
    __tablename__ = "login_links"
    __table_args__ = (
        db.Index("ix_login_links_email_hash_created_at", "email_hash", "created_at"),
    )

    id = db.Column(db.String(36), primary_key=True)   # the token's jti
    email_hash = db.Column(db.CHAR(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    used_at = db.Column(db.DateTime, nullable=True)
```

In `backend/app/__init__.py`, replace:

```python
    from .models import (  # noqa: F401
        user, analysis, prompt_version, counselor_note, counselor_code,
        counselor_profile, code_redemption, profile, price_feedback, voyage,
    )
```

with:

```python
    from .models import (  # noqa: F401
        user, analysis, prompt_version, counselor_note, counselor_code,
        counselor_profile, code_redemption, profile, price_feedback, voyage,
        auth_identity, login_link,
    )
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_social_sign_in_models.py`
Expected: `4 passed`.

- [ ] **Step 5: Write the migration**

Create `backend/migrations/versions/b0c1d2e3f4a5_social_sign_in.py`:

```python
"""Social sign-in: auth_identities and login_links

auth_identities ties a Google or Microsoft account (provider + the ID token's
sub) to a users row; subject compares case-sensitively (utf8mb4_bin).
login_links is the email sign-in link's single-use record and pacing clock;
it holds an HMAC of the address, never the address.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-10-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = 'b0c1d2e3f4a5'
down_revision = 'a9b0c1d2e3f4'
branch_labels = None
depends_on = None


def _tables(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _indexes(bind, table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(table)}


def upgrade():
    # Idempotent per this repo's convention: entrypoint.sh runs `db upgrade`
    # at container start, and MySQL DDL is not transactional — each guard
    # checks the very object it is about to create, so a crash between two
    # statements resumes at the one that did not happen.
    bind = op.get_bind()

    if "auth_identities" not in _tables(bind):
        op.create_table(
            "auth_identities",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "user_id", sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("provider", sa.String(16), nullable=False),
            sa.Column(
                "subject",
                sa.String(255).with_variant(mysql.VARCHAR(255, collation="utf8mb4_bin"), "mysql"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("provider", "subject", name="uq_auth_identities_provider_subject"),
        )
    if "ix_auth_identities_user_id" not in _indexes(bind, "auth_identities"):
        op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])

    if "login_links" not in _tables(bind):
        op.create_table(
            "login_links",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email_hash", sa.CHAR(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
        )
    if "ix_login_links_email_hash_created_at" not in _indexes(bind, "login_links"):
        op.create_index(
            "ix_login_links_email_hash_created_at", "login_links", ["email_hash", "created_at"]
        )


def downgrade():
    tables = _tables(op.get_bind())
    if "login_links" in tables:
        op.drop_table("login_links")
    if "auth_identities" in tables:
        op.drop_table("auth_identities")
```

- [ ] **Step 6: The revision graph still has one head**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_migration_chain.py`
Expected: `2 passed`.

- [ ] **Step 7: Apply it to the dev MySQL, check the collation, round-trip it**

From the repo root:

```bash
docker compose up -d db backend
docker compose exec backend flask db upgrade
docker compose exec db mysql -uneoori -pneoori_dev neoori -e "SHOW FULL COLUMNS FROM auth_identities LIKE 'subject'; SHOW INDEX FROM auth_identities; SHOW INDEX FROM login_links;"
docker compose exec backend flask db downgrade a9b0c1d2e3f4
docker compose exec backend flask db upgrade
```

Expected:
- The `subject` row shows `Collation: utf8mb4_bin`.
- The indexes listed are `uq_auth_identities_provider_subject`, `ix_auth_identities_user_id` and `ix_login_links_email_hash_created_at`.
- The downgrade and upgrade run without error.

If Docker is unavailable, say so in your report. Task 14 runs on this stack.

- [ ] **Step 8: Full suite**

Run: `cd backend && venv/bin/pytest -q -p no:cacheprovider`
Expected: `1205 passed`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/auth_identity.py backend/app/models/login_link.py \
        backend/app/__init__.py backend/migrations/versions/b0c1d2e3f4a5_social_sign_in.py \
        backend/tests/test_social_sign_in_models.py
git commit -m "feat(auth): auth_identities and login_links tables

A provider identity is (provider, sub) -> user, unique, case-sensitive
on MySQL. login_links holds the email link's single use and pacing clock
under an HMAC of the address, never the address.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Signed tokens — the sign-in link, the signup ticket, the address helpers

**Files:**
- Modify: `backend/app/utils/auth_links.py`
- Test: `backend/tests/test_sign_in_links.py`

**Interfaces:**
- Consumes: the existing `_serializer`, `_load`, `safe_next`, `LinkResult` in the same module.
- Produces, all in `app.utils.auth_links`:
  - `LOGIN_SALT = "email-login"`, `SIGNUP_SALT = "signup-ticket"`
  - `LOGIN_MAX_AGE = 900`, `SIGNUP_MAX_AGE = 1800`, `EMAIL_MAX_LENGTH = 255`
  - `normalise_email(raw) -> str`
  - `email_shape_ok(email) -> bool`
  - `email_hash(email: str) -> str` (64 hex)
  - `make_login_token(jti: str, email: str, next_path=None) -> str`; `load_login_token(token) -> LinkResult`. The payload is `{"jti", "email", "next"}`.
  - `make_signup_ticket(*, method: str, sub: str | None, email: str, prenom_hint: str = "", next_path=None) -> str`; `load_signup_ticket(token) -> LinkResult`. The payload is `{"method", "sub", "email", "prenom_hint", "next"}`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_sign_in_links.py`:

```python
"""The sign-in link, the signup ticket and the address helpers (social
sign-in spec, decisions 4, 15 and 18)."""
import pytest

from app.utils import auth_links


@pytest.mark.parametrize("raw, expected", [
    ("  Marie@Test.FR ", "marie@test.fr"),
    ("marie@test.fr", "marie@test.fr"),
    (None, ""), (42, ""), (["marie@test.fr"], ""),
])
def test_an_address_has_one_stored_form(raw, expected):
    assert auth_links.normalise_email(raw) == expected


@pytest.mark.parametrize("email", ["marie@test.fr", "marie.dupont+cv@sub.example.org"])
def test_a_plain_address_passes_the_shape_check(email):
    assert auth_links.email_shape_ok(email)


@pytest.mark.parametrize("email", [
    "", "marie", "marie@", "@test.fr", "marie@test", "ma rie@test.fr", "marie@@test.fr",
    "marie@test.fr\n", "ma\x00rie@test.fr", "\ud800@test.fr", "a" * 250 + "@test.fr",
    None, 42,
])
def test_anything_else_fails_it(email):
    assert not auth_links.email_shape_ok(email)


def test_the_hash_hides_the_address_and_ignores_its_case(app):
    digest = auth_links.email_hash("Marie@Test.fr")
    assert digest == auth_links.email_hash("marie@test.fr")
    assert len(digest) == 64 and "marie" not in digest


def test_the_hash_is_keyed_on_the_secret(app):
    before = auth_links.email_hash("marie@test.fr")
    app.config["SECRET_KEY"] = "another-key"
    assert auth_links.email_hash("marie@test.fr") != before


def test_a_login_link_round_trips(app):
    token = auth_links.make_login_token("j-1", "marie@test.fr", "/analyse/nouveau")
    result = auth_links.load_login_token(token)
    assert result.error is None
    assert result.payload == {"jti": "j-1", "email": "marie@test.fr", "next": "/analyse/nouveau"}


def test_a_login_link_drops_an_unsafe_destination(app):
    token = auth_links.make_login_token("j-1", "marie@test.fr", "//evil.com")
    assert auth_links.load_login_token(token).payload["next"] is None


def test_a_login_link_expires(app, monkeypatch):
    token = auth_links.make_login_token("j-1", "marie@test.fr")
    monkeypatch.setattr(auth_links, "LOGIN_MAX_AGE", -1)
    assert auth_links.load_login_token(token).error == "link_expired"


def test_a_link_lives_fifteen_minutes_and_a_ticket_thirty():
    assert auth_links.LOGIN_MAX_AGE == 15 * 60
    assert auth_links.SIGNUP_MAX_AGE == 30 * 60


def test_each_purpose_refuses_the_others_tokens(app):
    login = auth_links.make_login_token("j-1", "marie@test.fr")
    ticket = auth_links.make_signup_ticket(method="email", sub=None, email="marie@test.fr")
    assert auth_links.load_signup_ticket(login).error == "link_invalid"
    assert auth_links.load_login_token(ticket).error == "link_invalid"
    assert auth_links.load_verify_token(login).error == "link_invalid"


def test_a_ticket_round_trips(app):
    ticket = auth_links.make_signup_ticket(
        method="google", sub="1234", email="marie@gmail.com",
        prenom_hint="Marie", next_path="/espace",
    )
    assert auth_links.load_signup_ticket(ticket).payload == {
        "method": "google", "sub": "1234", "email": "marie@gmail.com",
        "prenom_hint": "Marie", "next": "/espace",
    }


def test_a_ticket_expires(app, monkeypatch):
    ticket = auth_links.make_signup_ticket(method="email", sub=None, email="marie@test.fr")
    monkeypatch.setattr(auth_links, "SIGNUP_MAX_AGE", -1)
    assert auth_links.load_signup_ticket(ticket).error == "link_expired"
```

- [ ] **Step 2: Run them to see them fail**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_sign_in_links.py`
Expected: FAIL with `AttributeError: module 'app.utils.auth_links' has no attribute 'normalise_email'`.

- [ ] **Step 3: Implement**

In `backend/app/utils/auth_links.py`, replace the first paragraph of the module docstring:

```python
"""Signed, expiring links for the two mails that prove an inbox: confirming an
address, and resetting a password.
```

with:

```python
"""Signed, expiring tokens for everything that proves an inbox: the links that
confirm an address, reset a password or sign in, and the signup ticket a
proven address carries to « Finaliser votre inscription ».
```

Replace `import hashlib` with:

```python
import hashlib
import hmac
```

After `NEXT_MAX_LENGTH = 512`, add:

```python
LOGIN_SALT = "email-login"
SIGNUP_SALT = "signup-ticket"
LOGIN_MAX_AGE = 15 * 60      # social sign-in spec, decision 15
SIGNUP_MAX_AGE = 30 * 60     # decision 18
EMAIL_MAX_LENGTH = 255       # users.email
# One @, a dot after it, no whitespace or control character anywhere.
_EMAIL_SHAPE = re.compile(
    r"[^@\s\x00-\x1f\x7f]+@[^@\s\x00-\x1f\x7f]+\.[^@\s\x00-\x1f\x7f]+"
)
```

At the end of the file, add:

```python
def normalise_email(raw) -> str:
    """The one form an address is stored and looked up under — the one
    register stores: stripped, lowercased. Anything but a string is ""."""
    return raw.strip().lower() if isinstance(raw, str) else ""


def email_shape_ok(email) -> bool:
    """A light check before an address is mailed or stored: the right shape,
    fits users.email, and encodable — a lone surrogate, which JSON can carry,
    is not."""
    if not isinstance(email, str) or not 0 < len(email) <= EMAIL_MAX_LENGTH:
        return False
    try:
        email.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return _EMAIL_SHAPE.fullmatch(email) is not None


def email_hash(email: str) -> str:
    """What login_links keeps instead of the address (social sign-in spec,
    decision 4): an HMAC of the normalised address keyed on SECRET_KEY, so a
    table dump does not tell which known addresses asked for a link. Call it
    on a shape-checked address."""
    key = current_app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(key, normalise_email(email).encode("utf-8"), hashlib.sha256).hexdigest()


def make_login_token(jti: str, email: str, next_path=None) -> str:
    return _serializer(LOGIN_SALT).dumps(
        {"jti": jti, "email": email, "next": safe_next(next_path)}
    )


def load_login_token(token) -> LinkResult:
    return _load(LOGIN_SALT, token, LOGIN_MAX_AGE)


def make_signup_ticket(*, method: str, sub, email: str, prenom_hint: str = "",
                       next_path=None) -> str:
    return _serializer(SIGNUP_SALT).dumps({
        "method": method, "sub": sub, "email": email,
        "prenom_hint": prenom_hint, "next": safe_next(next_path),
    })


def load_signup_ticket(token) -> LinkResult:
    return _load(SIGNUP_SALT, token, SIGNUP_MAX_AGE)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_sign_in_links.py tests/test_auth_links.py`
Expected: all pass.

- [ ] **Step 5: Full suite**

Run: `venv/bin/pytest -q -p no:cacheprovider`
Expected: no failures.

- [ ] **Step 6: Commit**

```bash
git add backend/app/utils/auth_links.py backend/tests/test_sign_in_links.py
git commit -m "feat(auth): sign-in link and signup ticket tokens

Two more itsdangerous purposes (email-login, 15 min; signup-ticket,
30 min), plus the address helpers they need: one normal form, a shape
check that refuses unencodable input, and the keyed hash login_links
stores instead of the address.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `services/sign_in.py` — trust, resolution, ruling 4, the ticket cookie

**Files:**
- Modify: `backend/app/models/profile.py` (a `PRENOM_MAX_LENGTH` constant; the `prenom` column uses it)
- Create: `backend/app/services/sign_in.py`
- Test: `backend/tests/test_sign_in.py`

**Interfaces:**
- Consumes:
  - `PROVIDERS` and `AuthIdentity` (Task 2)
  - `auth_links.normalise_email`, `email_shape_ok`, `make_signup_ticket`, `load_signup_ticket`, `SIGNUP_MAX_AGE` (Task 3)
  - `demande_mail.notify_if_visible(user)`
- Produces:
  - `app.models.profile.PRENOM_MAX_LENGTH = 120`
  - In `app.services.sign_in`:
    - `MSA_TENANT_ID: str`, `SIGNUP_COOKIE = "signup_ticket"`, `SIGNUP_COOKIE_PATH = "/api/auth"`, `TICKET_METHODS = ("google", "microsoft", "email")`
    - `Outcome(kind: str, user: User | None = None, email: str | None = None)`, a frozen dataclass. `kind` is one of `"user"`, `"signup"`, `"refused"`.
    - `unusable_password_hash() -> str`
    - `trusted_email(provider: str, claims) -> str | None`
    - `microsoft_issuer_ok(claims) -> bool`
    - `enter(user, provider: str | None = None, sub: str | None = None) -> None`
    - `existing_account(provider: str | None, sub: str | None, email: str | None) -> User | None`
    - `resolve_oauth(provider: str, claims) -> Outcome`. The caller guarantees `claims["sub"]` is a non-empty str.
    - `set_signup_ticket(response, *, method: str, sub: str | None, email: str, prenom_hint=None, next_path=None) -> None`
    - `clear_signup_ticket(response) -> None`
    - `live_signup_ticket() -> tuple[dict | None, str | None]`. Returns `(ticket, None)`, or `(None, "link_expired" | "link_invalid")`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_sign_in.py`:

```python
"""Who a sign-in is and which account it enters (social sign-in spec,
decisions 3, 7–9 and 18)."""
from datetime import datetime
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.auth_identity import AuthIdentity
from app.models.profile import CONSENT_VERSION, Profile
from app.models.user import User
from app.routes.auth import password_matches
from app.services import sign_in
from app.utils import auth_links

NOTIFY = "app.services.demande_mail.notify_if_visible"
WORK_TENANT = "72f988bf-86f1-41af-91ab-2d7cd011db47"

GOOGLE = {"sub": "g-1", "email": "marie@gmail.com", "email_verified": True}
MS_PERSONAL = {"sub": "m-1", "email": "marie@outlook.fr", "tid": sign_in.MSA_TENANT_ID}
MS_WORK = {"sub": "m-2", "email": "marie@entreprise.fr", "tid": WORK_TENANT}


def _fresh(user):
    db.session.expire_all()
    return db.session.get(User, user.id)


def _ticket_in(response) -> dict:
    header = next(h for h in response.headers.getlist("Set-Cookie")
                  if h.startswith("signup_ticket="))
    return auth_links.load_signup_ticket(header.split(";", 1)[0].split("=", 1)[1]).payload


# ── the unusable hash (decision 3) ────────────────────────────────────────────

def test_no_password_opens_a_password_less_account(app):
    user = User(email="sans@test.fr", password_hash=sign_in.unusable_password_hash())
    for guess in ("", "motdepasse1", "None", user.password_hash):
        assert password_matches(user, guess) is False


def test_each_unusable_hash_is_new(app):
    assert sign_in.unusable_password_hash() != sign_in.unusable_password_hash()


# ── trust (decision 7) ────────────────────────────────────────────────────────

def test_google_vouches_only_for_a_verified_address():
    assert sign_in.trusted_email("google", GOOGLE) == "marie@gmail.com"
    for flag in (False, None, "true", 1):
        assert sign_in.trusted_email("google", {**GOOGLE, "email_verified": flag}) is None


def test_a_personal_microsoft_account_is_trusted():
    assert sign_in.trusted_email("microsoft", MS_PERSONAL) == "marie@outlook.fr"


def test_a_work_account_needs_its_domain_proven():
    """nOAuth: a tenant admin can write any address into `email`."""
    assert sign_in.trusted_email("microsoft", MS_WORK) is None


@pytest.mark.parametrize("flag", [True, "1", "true", "TRUE"])
def test_xms_edov_proves_a_work_address_in_every_form_microsoft_sends(flag):
    claims = {**MS_WORK, "xms_edov": flag}
    assert sign_in.trusted_email("microsoft", claims) == "marie@entreprise.fr"


@pytest.mark.parametrize("flag", [False, "0", "false", None, 1, ""])
def test_anything_else_is_no_proof(flag):
    assert sign_in.trusted_email("microsoft", {**MS_WORK, "xms_edov": flag}) is None


@pytest.mark.parametrize("email", [None, "", "pas-une-adresse", "\ud800@outlook.fr"])
def test_no_usable_address_is_no_trusted_address(email):
    assert sign_in.trusted_email("microsoft", {**MS_PERSONAL, "email": email}) is None


def test_a_phone_only_microsoft_account_has_no_address():
    claims = {k: v for k, v in MS_PERSONAL.items() if k != "email"}
    assert sign_in.trusted_email("microsoft", claims) is None


def test_a_trusted_address_comes_back_in_its_stored_form():
    claims = {**MS_PERSONAL, "email": " Marie.Dupont@Outlook.FR "}
    assert sign_in.trusted_email("microsoft", claims) == "marie.dupont@outlook.fr"


def test_an_unknown_provider_vouches_for_nothing():
    assert sign_in.trusted_email("apple", GOOGLE) is None


# ── the Microsoft issuer (decision 6) ─────────────────────────────────────────

def test_the_issuer_must_name_the_token_s_own_tenant():
    tid = WORK_TENANT
    assert sign_in.microsoft_issuer_ok(
        {"tid": tid, "iss": f"https://login.microsoftonline.com/{tid}/v2.0"})
    assert not sign_in.microsoft_issuer_ok(
        {"tid": tid, "iss": f"https://login.microsoftonline.com/{sign_in.MSA_TENANT_ID}/v2.0"})
    assert not sign_in.microsoft_issuer_ok(
        {"tid": tid, "iss": "https://login.microsoftonline.com/{tenantid}/v2.0"})
    assert not sign_in.microsoft_issuer_ok({"iss": "https://login.microsoftonline.com//v2.0"})
    assert not sign_in.microsoft_issuer_ok({"tid": 5, "iss": "https://login.microsoftonline.com/5/v2.0"})


# ── entering an account (decision 9) ──────────────────────────────────────────

def test_entering_a_verified_account_keeps_its_password(app, make_user):
    user = make_user(email="marie@gmail.com")
    with patch(NOTIFY) as told:
        sign_in.enter(user, "google", "g-1")
    assert password_matches(_fresh(user), "motdepasse1")
    assert AuthIdentity.query.filter_by(user_id=user.id, provider="google", subject="g-1").count() == 1
    told.assert_not_called()


def test_entering_twice_links_once(app, make_user):
    user = make_user()
    sign_in.enter(user, "google", "g-1")
    sign_in.enter(user, "google", "g-1")
    assert AuthIdentity.query.count() == 1


def test_entering_an_unverified_account_wipes_the_password_a_stranger_set(app, make_user):
    user = make_user(verified=False)
    reset_token = auth_links.make_reset_token(user)
    with patch(NOTIFY) as told:
        sign_in.enter(user, "google", "g-1")
    fresh = _fresh(user)
    assert fresh.email_verified_at is not None
    assert not password_matches(fresh, "motdepasse1")
    # pwv moved with the hash: the stranger's reset link died too.
    assert (auth_links.load_reset_token(reset_token).payload["pwv"]
            != auth_links.password_fingerprint(fresh.password_hash))
    told.assert_called_once()


def test_the_profile_seed_survives_the_wipe(app, make_user):
    user = make_user(verified=False)
    db.session.add(Profile(user_id=user.id, prenom="Marie", tranche_age="25_34",
                           consent_at=datetime.utcnow(), consent_version=CONSENT_VERSION))
    db.session.commit()
    with patch(NOTIFY):
        sign_in.enter(user)
    assert Profile.query.filter_by(user_id=user.id).one().prenom == "Marie"


# ── resolution (decision 8) ───────────────────────────────────────────────────

def test_a_known_identity_wins_over_a_changed_address(app, make_user):
    user = make_user(email="ancienne@gmail.com")
    db.session.add(AuthIdentity(user_id=user.id, provider="google", subject="g-1"))
    db.session.commit()
    outcome = sign_in.resolve_oauth("google", {**GOOGLE, "email": "nouvelle@gmail.com"})
    assert outcome.kind == "user" and outcome.user.id == user.id


def test_a_known_identity_enters_without_a_trusted_address(app, make_user):
    user = make_user(email="marie@entreprise.fr")
    db.session.add(AuthIdentity(user_id=user.id, provider="microsoft", subject="m-2"))
    db.session.commit()
    outcome = sign_in.resolve_oauth("microsoft", MS_WORK)
    assert outcome.kind == "user" and outcome.user.id == user.id


def test_a_trusted_address_enters_its_account_and_links_it(app, make_user):
    user = make_user(email="marie@gmail.com")
    outcome = sign_in.resolve_oauth("google", GOOGLE)
    assert outcome.kind == "user" and outcome.user.id == user.id
    assert AuthIdentity.query.filter_by(provider="google", subject="g-1").one().user_id == user.id


def test_a_trusted_address_without_an_account_is_a_signup(app):
    outcome = sign_in.resolve_oauth("google", GOOGLE)
    assert outcome == sign_in.Outcome("signup", email="marie@gmail.com")
    assert User.query.count() == 0 and AuthIdentity.query.count() == 0


def test_an_untrusted_address_is_refused_and_links_nothing(app, make_user):
    make_user(email="marie@entreprise.fr")
    assert sign_in.resolve_oauth("microsoft", MS_WORK).kind == "refused"
    assert AuthIdentity.query.count() == 0


def test_a_provider_address_in_capitals_enters_the_lowercase_account(app, make_user):
    # Review Focus 1.
    user = make_user(email="marie.dupont@outlook.fr")
    outcome = sign_in.resolve_oauth("microsoft", {**MS_PERSONAL, "email": "Marie.Dupont@Outlook.fr"})
    assert outcome.kind == "user" and outcome.user.id == user.id
    assert User.query.count() == 1


def test_an_address_alone_enters_without_linking_anything(app, make_user):
    user = make_user(email="marie@test.fr")
    assert sign_in.existing_account(None, None, "marie@test.fr").id == user.id
    assert AuthIdentity.query.count() == 0


# ── the signup ticket (decision 18) ───────────────────────────────────────────

def test_the_ticket_cookie_is_scoped_and_hidden_from_scripts(app):
    response = app.response_class()
    sign_in.set_signup_ticket(response, method="google", sub="g-1",
                              email="marie@gmail.com", prenom_hint="Marie")
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "Path=/api/auth" in cookie
    assert "SameSite=Lax" in cookie and "Max-Age=1800" in cookie
    assert _ticket_in(response)["prenom_hint"] == "Marie"


def test_the_prenom_hint_is_trimmed_to_what_the_profile_holds(app):
    # Review Focus 4: a longer name would prefill a form that can never be sent.
    response = app.response_class()
    sign_in.set_signup_ticket(response, method="google", sub="g-1",
                              email="m@gmail.com", prenom_hint="  " + "M" * 300)
    assert _ticket_in(response)["prenom_hint"] == "M" * 120


def test_a_missing_hint_is_an_empty_prenom(app):
    response = app.response_class()
    sign_in.set_signup_ticket(response, method="microsoft", sub="m-1",
                              email="m@outlook.fr", prenom_hint=None)
    assert _ticket_in(response)["prenom_hint"] == ""


def test_clearing_the_ticket_expires_the_cookie(app):
    response = app.response_class()
    sign_in.clear_signup_ticket(response)
    cookie = response.headers["Set-Cookie"]
    assert cookie.startswith("signup_ticket=;") and "Path=/api/auth" in cookie


def test_a_live_ticket_is_read_from_the_request(app):
    token = auth_links.make_signup_ticket(method="email", sub=None, email="m@test.fr")
    with app.test_request_context("/", headers={"Cookie": f"signup_ticket={token}"}):
        ticket, code = sign_in.live_signup_ticket()
    assert code is None and ticket["email"] == "m@test.fr"


@pytest.mark.parametrize("payload", [
    dict(method="apple", sub="a-1", email="m@icloud.com"),
    dict(method="google", sub=None, email="m@gmail.com"),
    dict(method="google", sub="", email="m@gmail.com"),
    dict(method="email", sub=None, email=""),
])
def test_a_signed_but_malformed_ticket_is_invalid(app, payload):
    token = auth_links.make_signup_ticket(**payload)
    with app.test_request_context("/", headers={"Cookie": f"signup_ticket={token}"}):
        assert sign_in.live_signup_ticket() == (None, "link_invalid")


def test_no_ticket_is_an_invalid_one(app):
    with app.test_request_context("/"):
        assert sign_in.live_signup_ticket() == (None, "link_invalid")
```

- [ ] **Step 2: Run them to see them fail**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_sign_in.py`
Expected: collection error `ImportError: cannot import name 'sign_in' from 'app.services'`.

- [ ] **Step 3: Add the prénom width to the profile model**

In `backend/app/models/profile.py`, after the line `CONSENT_SENSITIVE_VERSION = "v1"`, add:

```python

# profiles.prenom's width. MySQL refuses a longer value with an error, which
# SQLite (the tests) never does, so the signup doors check it themselves
# (routes/auth._seed_problem) and the signup ticket trims its hint to it.
PRENOM_MAX_LENGTH = 120
```

In the same file, replace `    prenom = db.Column(db.String(120), nullable=True)` with:

```python
    prenom = db.Column(db.String(PRENOM_MAX_LENGTH), nullable=True)
```

- [ ] **Step 4: Write the service**

Create `backend/app/services/sign_in.py`:

```python
"""Who a Google, Microsoft or email-link sign-in is, and which account it
enters (social sign-in spec, decisions 1, 3, 7–9, 18 and 19).

Every new door ends in routes/auth._issue_session(), like the password one.
This module decides what comes before it:

  * whether a provider's address can be believed (trusted_email);
  * which existing account a sign-in enters, if any (existing_account),
    applying ruling 4 on the way in (enter);
  * or, for someone with no account yet, the signup ticket that carries them
    to « Finaliser votre inscription » — no users row exists before the CGV
    consent is given there.
"""
import secrets
from dataclasses import dataclass
from datetime import datetime

from flask import current_app, request

from ..extensions import bcrypt, db
from ..models.auth_identity import PROVIDERS, AuthIdentity
from ..models.profile import PRENOM_MAX_LENGTH
from ..models.user import User
from ..utils import auth_links
from . import demande_mail

# The tenant every personal Microsoft account (Outlook, Hotmail, Live) signs
# in under. Microsoft vouches for those addresses; in a work or school tenant
# only xms_edov does (decision 7).
MSA_TENANT_ID = "9188040d-6c67-4c5b-b112-36a304b66dad"

SIGNUP_COOKIE = "signup_ticket"
SIGNUP_COOKIE_PATH = "/api/auth"
TICKET_METHODS = PROVIDERS + ("email",)


@dataclass(frozen=True)
class Outcome:
    """Where a provider sign-in goes: "user" (an account, already entered),
    "signup" (a trusted address with no account) or "refused"."""
    kind: str
    user: User | None = None
    email: str | None = None


def unusable_password_hash() -> str:
    """A real bcrypt hash of a secret nobody holds (decision 3): every
    password typed against it fails like a wrong one, while pwv, the refresh
    check and the reset link work on it unchanged. token_urlsafe rather than
    raw bytes: bcrypt refuses a NUL byte."""
    return bcrypt.generate_password_hash(secrets.token_urlsafe(32)).decode("utf-8")


def trusted_email(provider: str, claims) -> str | None:
    """The address this ID token proves, in its stored form, or None."""
    email = auth_links.normalise_email(claims.get("email"))
    if not auth_links.email_shape_ok(email):
        return None
    if provider == "google":
        return email if claims.get("email_verified") is True else None
    if provider == "microsoft":
        if claims.get("tid") == MSA_TENANT_ID or _xms_edov(claims.get("xms_edov")):
            return email
    return None


def _xms_edov(value) -> bool:
    """Microsoft sends the flag as a boolean or, in some forms, a string."""
    return value is True or (isinstance(value, str) and value.strip().lower() in ("1", "true"))


def microsoft_issuer_ok(claims) -> bool:
    """`iss` names the token's own tenant (decision 6). The /common metadata
    publishes a template issuer, so Authlib's default check can never pass."""
    tid = claims.get("tid")
    return (
        isinstance(tid, str) and bool(tid)
        and claims.get("iss") == f"https://login.microsoftonline.com/{tid}/v2.0"
    )


def enter(user: User, provider: str | None = None, sub: str | None = None) -> None:
    """Let a proven sign-in into `user` (decision 9): link the provider
    identity if one is given, and apply ruling 4 to an account nobody had
    verified — the password a stranger may have set is replaced, the address
    counts as proven, and a demande waiting on that proof joins the queue."""
    if provider and not AuthIdentity.query.filter_by(provider=provider, subject=sub).first():
        db.session.add(AuthIdentity(user_id=user.id, provider=provider, subject=sub))
    newly_verified = user.email_verified_at is None
    if newly_verified:
        user.password_hash = unusable_password_hash()
        user.email_verified_at = datetime.utcnow()
    db.session.commit()
    if newly_verified:
        demande_mail.notify_if_visible(user)


def existing_account(provider: str | None, sub: str | None, email: str | None) -> User | None:
    """The account this sign-in enters, already entered, or None (decision 8,
    branches 1 and 2). A known identity wins even when the provider's address
    changed; an address is matched only when the caller has proven it."""
    if provider and sub:
        identity = AuthIdentity.query.filter_by(provider=provider, subject=sub).first()
        if identity is not None:
            user = db.session.get(User, identity.user_id)
            enter(user)
            return user
    if email:
        user = User.query.filter_by(email=email).first()
        if user is not None:
            enter(user, provider, sub)
            return user
    return None


def resolve_oauth(provider: str, claims) -> Outcome:
    """Decision 8 in order: known identity, trusted address of an account,
    trusted address without one (signup), anything else refused."""
    email = trusted_email(provider, claims)
    user = existing_account(provider, claims["sub"], email)
    if user is not None:
        return Outcome("user", user=user)
    if email is None:
        return Outcome("refused")
    return Outcome("signup", email=email)


def set_signup_ticket(response, *, method: str, sub: str | None, email: str,
                      prenom_hint=None, next_path=None) -> None:
    """Carry someone with no account to « Finaliser votre inscription »
    (decision 18). A cookie, not a URL parameter: the provider subject and the
    address stay out of browser history and the nginx log. The hint is cut to
    what profiles.prenom holds, so the form it prefills can always be sent."""
    hint = prenom_hint.strip()[:PRENOM_MAX_LENGTH] if isinstance(prenom_hint, str) else ""
    token = auth_links.make_signup_ticket(
        method=method, sub=sub, email=email, prenom_hint=hint, next_path=next_path,
    )
    response.set_cookie(
        SIGNUP_COOKIE, token,
        max_age=auth_links.SIGNUP_MAX_AGE,
        path=SIGNUP_COOKIE_PATH,
        httponly=True,
        samesite="Lax",
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
    )


def clear_signup_ticket(response) -> None:
    response.delete_cookie(
        SIGNUP_COOKIE,
        path=SIGNUP_COOKIE_PATH,
        httponly=True,
        samesite="Lax",
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
    )


def live_signup_ticket() -> tuple[dict | None, str | None]:
    """(ticket, None) for this request's live, well-formed signup ticket;
    else (None, "link_expired" | "link_invalid")."""
    result = auth_links.load_signup_ticket(request.cookies.get(SIGNUP_COOKIE))
    if result.error:
        return None, result.error
    ticket = result.payload
    method, sub, email = ticket.get("method"), ticket.get("sub"), ticket.get("email")
    if method not in TICKET_METHODS or not (isinstance(email, str) and email):
        return None, "link_invalid"
    if method != "email" and not (isinstance(sub, str) and sub):
        return None, "link_invalid"
    return ticket, None
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_sign_in.py`
Expected: all pass.

- [ ] **Step 6: Full suite**

Run: `venv/bin/pytest -q -p no:cacheprovider`
Expected: no failures.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/profile.py backend/app/services/sign_in.py backend/tests/test_sign_in.py
git commit -m "feat(auth): sign_in service — trust, resolution, ruling 4

Google is believed on email_verified, Microsoft on the personal-account
tenant or xms_edov (nOAuth). A known identity wins; a trusted address
enters its account; an unverified account loses the password a stranger
may have set. Someone with no account gets a signup ticket cookie.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The link mail and its one-a-minute pace

**Files:**
- Modify: `backend/app/services/email_service.py` (`_deliver_link` takes an address; its two callers; new `send_login_link`)
- Modify: `backend/app/services/auth_mail.py` (new `login_link_if_due`)
- Test: `backend/tests/test_login_link_mail.py`

**Interfaces:**
- Consumes: `LoginLink` (Task 2); `auth_links.email_hash`, `make_login_token` (Task 3); `email_service.prenom_of(user)`.
- Produces:
  - `email_service.send_login_link(to: str, prenom: str, token: str) -> bool`. Fail-soft; the link is `{APP_URL}/connexion/lien?token=…`.
  - `email_service._deliver_link(to: str, subject, html, text, link) -> bool`. Its first argument is now an address, not a user.
  - `auth_mail.login_link_if_due(email: str, user: User | None, next_path=None) -> bool`. True when a link is on its way.
  - `auth_mail.LINK_ROWS_KEPT = timedelta(hours=24)`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_login_link_mail.py`:

```python
"""The email sign-in link: its mail and its one-a-minute pace (social
sign-in spec, decisions 4, 14 and 15)."""
import logging
import re
from datetime import datetime, timedelta
from unittest.mock import patch

from app.extensions import db
from app.models.login_link import LoginLink
from app.services import auth_mail, email_service
from app.utils import auth_links

SEND = "app.services.email_service.resend.Emails.send"
TOKEN = re.compile(r"token=([A-Za-z0-9_.\-]+)")


def _sent(mock_send) -> dict:
    return mock_send.call_args[0][0]


def _link_mail(app, email="marie@test.fr", user=None, next_path=None):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        sent = auth_mail.login_link_if_due(email, user, next_path)
    return sent, mock_send


# ── the mail ──────────────────────────────────────────────────────────────────

def test_the_mail_links_to_the_landing_page(app):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["APP_URL"] = "https://neoori.tech"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_login_link("marie@test.fr", "", "tok.en") is True
    mail = _sent(mock_send)
    assert mail["to"] == ["marie@test.fr"]
    assert mail["subject"] == "Votre lien de connexion"
    assert "https://neoori.tech/connexion/lien?token=tok.en" in mail["html"]
    assert "valable 15 minutes" in mail["text"] and "ne sert qu'une fois" in mail["text"]
    assert mail["text"].startswith("Bonjour,")


def test_the_greeting_uses_the_prenom(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send_login_link("marie@test.fr", "Marie", "t")
    assert _sent(mock_send)["text"].startswith("Bonjour Marie,")


def test_on_a_laptop_without_a_key_the_link_goes_to_the_log(app, caplog):
    app.debug = True
    with caplog.at_level(logging.WARNING):
        assert email_service.send_login_link("marie@test.fr", "", "t") is True
    assert "/connexion/lien?token=t" in caplog.text


# ── the pace ──────────────────────────────────────────────────────────────────

def test_a_link_reaches_an_address_with_no_account(app):
    sent, mock_send = _link_mail(app, next_path="/analyse/nouveau")
    assert sent is True and mock_send.call_count == 1
    payload = auth_links.load_login_token(TOKEN.search(_sent(mock_send)["text"]).group(1)).payload
    assert payload["email"] == "marie@test.fr" and payload["next"] == "/analyse/nouveau"
    row = db.session.get(LoginLink, payload["jti"])
    assert row.email_hash == auth_links.email_hash("marie@test.fr") and row.used_at is None


def test_an_address_without_an_account_gets_one_link_a_minute(app):
    _link_mail(app)
    sent, again = _link_mail(app)
    assert sent is True               # on its way: one left under a minute ago
    assert again.call_count == 0
    assert LoginLink.query.count() == 1


def test_after_a_minute_it_gets_another(app):
    _link_mail(app)
    LoginLink.query.update({"created_at": datetime.utcnow() - timedelta(seconds=61)})
    db.session.commit()
    _, again = _link_mail(app)
    assert again.call_count == 1
    assert LoginLink.query.count() == 2


def test_an_account_shares_the_clock_of_its_other_mails(app, make_user):
    user = make_user()
    user.auth_mail_sent_at = datetime.utcnow()     # a reset mail just left
    db.session.commit()
    sent, mock_send = _link_mail(app, email=user.email, user=user)
    assert sent is True and mock_send.call_count == 0


def test_a_link_to_an_account_stamps_its_clock(app, make_user):
    user = make_user()
    _link_mail(app, email=user.email, user=user)
    assert user.auth_mail_sent_at is not None


def test_a_failed_send_writes_nothing_and_blocks_no_retry(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, side_effect=RuntimeError("provider down")):
        assert auth_mail.login_link_if_due("marie@test.fr", None) is False
    assert LoginLink.query.count() == 0
    _, retry = _link_mail(app)
    assert retry.call_count == 1


def test_a_failed_send_to_an_account_leaves_its_clock_alone(app, make_user):
    user = make_user()
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, side_effect=RuntimeError("provider down")):
        auth_mail.login_link_if_due(user.email, user)
    assert user.auth_mail_sent_at is None


def test_rows_older_than_a_day_are_purged(app):
    db.session.add(LoginLink(id="old", email_hash="0" * 64,
                             created_at=datetime.utcnow() - timedelta(hours=25)))
    db.session.commit()
    _link_mail(app)
    assert db.session.get(LoginLink, "old") is None
```

- [ ] **Step 2: Run them to see them fail**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_login_link_mail.py`
Expected: FAIL with `AttributeError: module 'app.services.email_service' has no attribute 'send_login_link'`.

- [ ] **Step 3: `email_service` — `_deliver_link` takes an address; add `send_login_link`**

In `backend/app/services/email_service.py`, replace the whole `_deliver_link` function with:

```python
def _deliver_link(to: str, subject: str, html: str, text: str, link: str) -> bool:
    """send(), except on a laptop with no key: the link goes to the log, so the
    local flow can be walked end to end. Debug only — never in production,
    where a token in a log line is a session for whoever reads the log."""
    if not current_app.config.get("RESEND_API_KEY") and current_app.debug:
        current_app.logger.warning("DEV — no RESEND_API_KEY, link for %s: %s", to, link)
        return True
    return send(to, subject, html, text)
```

In `send_verification`, replace:

```python
        return _deliver_link(
            user, "Confirmez votre adresse email",
```

with:

```python
        return _deliver_link(
            user.email, "Confirmez votre adresse email",
```

In `send_password_reset`, replace:

```python
        return _deliver_link(
            user, "Réinitialiser votre mot de passe",
```

with:

```python
        return _deliver_link(
            user.email, "Réinitialiser votre mot de passe",
```

Right after the end of `send_password_reset` (before the `# ── Lot 2` comment), add:

```python
def send_login_link(to: str, prenom: str, token: str) -> bool:
    """« Votre lien de connexion ». One wording whatever the address's account
    state (social sign-in spec, decision 15): it goes to the inbox owner, and
    an address with no account gets the same link, which signs it up. Fail-soft."""
    try:
        link = f"{_app_url()}/connexion/lien?token={token}"
        body, text = _mail(
            [
                _greeting(prenom),
                "Voici votre lien pour accéder à neoori. Il est valable 15 minutes "
                "et ne sert qu'une fois.",
            ],
            button=("Accéder à neoori", link),
            small="Si vous n'avez pas demandé ce lien, ignorez ce message.",
        )
        return _deliver_link(
            to, "Votre lien de connexion",
            _layout("Votre lien de connexion", body), text, link,
        )
    except Exception:
        current_app.logger.exception("Could not build/send the sign-in link mail.")
        return False
```

- [ ] **Step 4: `auth_mail` — `login_link_if_due`**

In `backend/app/services/auth_mail.py`, replace the module docstring's first line:

```python
"""When the two account mails may leave, and the clock that says so.
```

with:

```python
"""When the account mails may leave, and the clocks that say so.
```

Then add this paragraph at the end of the docstring, before its closing `"""`:

```python

The sign-in link (social sign-in spec, decision 14) also reaches addresses
with no account: those are paced by their latest login_links row instead.
```

Replace:

```python
from datetime import datetime, timedelta

from ..extensions import db
from . import email_service

COOLDOWN = timedelta(seconds=60)
```

with:

```python
from datetime import datetime, timedelta
from uuid import uuid4

from ..extensions import db
from ..models.login_link import LoginLink
from ..utils import auth_links
from . import email_service

COOLDOWN = timedelta(seconds=60)
# A link lives 15 minutes and its pacing clock one: a day of rows is ample.
LINK_ROWS_KEPT = timedelta(hours=24)
```

At the end of the file, add:

```python
def login_link_if_due(email: str, user, next_path=None) -> bool:
    """« Recevoir un lien de connexion ». True when a link is on its way: sent
    now, or sent under a minute ago.

    Paced per address whether or not it has an account: an account by the
    clock its other mails share, an address without one by its latest
    login_links row. Both are written only once Resend accepted the mail, so
    an outage never blocks the retry."""
    digest = auth_links.email_hash(email)
    now = datetime.utcnow()
    if not _link_cooldown_passed(digest, user, now):
        return True
    jti = str(uuid4())
    prenom = email_service.prenom_of(user) if user is not None else ""
    if not email_service.send_login_link(email, prenom, auth_links.make_login_token(jti, email, next_path)):
        return False
    LoginLink.query.filter(LoginLink.created_at < now - LINK_ROWS_KEPT).delete(
        synchronize_session=False
    )
    db.session.add(LoginLink(id=jti, email_hash=digest, created_at=now))
    if user is not None:
        user.auth_mail_sent_at = now
    db.session.commit()
    return True


def _link_cooldown_passed(digest: str, user, now: datetime) -> bool:
    if user is not None:
        return cooldown_passed(user, now)
    last = (
        LoginLink.query.filter_by(email_hash=digest)
        .order_by(LoginLink.created_at.desc())
        .first()
    )
    return last is None or now - last.created_at >= COOLDOWN
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_login_link_mail.py tests/test_auth_mail.py tests/test_email_service.py`
Expected: all pass. The existing dev-log test for the verification mail still passes after the `_deliver_link` change.

- [ ] **Step 6: Full suite**

Run: `venv/bin/pytest -q -p no:cacheprovider`
Expected: no failures.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/email_service.py backend/app/services/auth_mail.py \
        backend/tests/test_login_link_mail.py
git commit -m "feat(mail): « Votre lien de connexion » and its pace

One wording for every address. One link a minute per address: an
account shares auth_mail_sent_at with its other mails, an address
without one is paced by its latest login_links row. Nothing is
written unless Resend accepted the mail.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The email-link endpoints — send, check, consume

**Files:**
- Create: `backend/app/routes/auth_link.py`
- Modify: `backend/app/__init__.py` (import and register the blueprint)
- Modify: `backend/tests/test_no_500_on_hostile_input.py` (three `ROUTES` rows)
- Test: `backend/tests/test_email_link_routes.py`

**Interfaces:**
- Consumes:
  - `auth_mail.login_link_if_due` (Task 5)
  - `auth_links.normalise_email`, `email_shape_ok`, `load_login_token` (Task 3)
  - `sign_in.existing_account`, `set_signup_ticket` (Task 4)
  - `routes.auth._issue_session`, `_landing`, `_link_error`
- Produces:
  - `POST /api/auth/email-link {email, next}` → 200 `{mail_sent: bool}`; 400 `{error: "Email invalide."}`
  - `POST /api/auth/email-link/check {token}` → 200 `{email}`; 400 `{code: link_expired | link_invalid, error}`
  - `POST /api/auth/email-link/consume {token}` → 200 `{user, next}` + session cookies, or 200 `{signup: true}` + the `signup_ticket` cookie; 400 as `check`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_email_link_routes.py`:

```python
"""« Recevoir un lien de connexion » end to end (social sign-in spec,
decisions 14–17)."""
import re
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.login_link import LoginLink
from app.models.user import User
from app.routes.auth import password_matches
from app.utils import auth_links

SEND = "app.services.email_service.resend.Emails.send"
TOKEN = re.compile(r"token=([A-Za-z0-9_.\-]+)")


def _cookies(res) -> str:
    return " ".join(res.headers.getlist("Set-Cookie"))


def _request_link(client, app, email="marie@test.fr", **extra):
    """POST /email-link with a working mail provider: (response, token or None)."""
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        res = client.post("/api/auth/email-link", json={"email": email, **extra})
    token = TOKEN.search(mock_send.call_args[0][0]["text"]).group(1) if mock_send.called else None
    return res, token


def _check(client, token):
    return client.post("/api/auth/email-link/check", json={"token": token})


def _consume(client, token):
    return client.post("/api/auth/email-link/consume", json={"token": token})


# ── send ──────────────────────────────────────────────────────────────────────

def test_the_answer_does_not_say_whether_an_account_exists(client, app, make_user):
    make_user(email="compte@test.fr")
    with_account, _ = _request_link(client, app, "compte@test.fr")
    without, _ = _request_link(client, app, "personne@test.fr")
    assert with_account.status_code == without.status_code == 200
    assert with_account.get_json() == without.get_json() == {"mail_sent": True}


@pytest.mark.parametrize("email", ["", "pas-une-adresse", None, 42, "a@b"])
def test_a_malformed_address_is_refused(client, email):
    res = client.post("/api/auth/email-link", json={"email": email})
    assert res.status_code == 400
    assert res.get_json()["error"] == "Email invalide."


def test_an_address_typed_with_capitals_and_spaces_is_paced_as_one(client, app):
    _request_link(client, app, "marie@test.fr")
    _, token = _request_link(client, app, "  Marie@Test.FR ")
    assert token is None                 # inside the minute: no second mail
    assert LoginLink.query.count() == 1


def test_the_destination_rides_in_the_link(client, app):
    _, token = _request_link(client, app, next="/analyse/nouveau")
    assert auth_links.load_login_token(token).payload["next"] == "/analyse/nouveau"


# ── check ─────────────────────────────────────────────────────────────────────

def test_check_names_the_address_and_spends_nothing(client, app):
    _, token = _request_link(client, app)
    for _ in range(2):
        res = _check(client, token)
        assert res.status_code == 200 and res.get_json() == {"email": "marie@test.fr"}
    assert LoginLink.query.one().used_at is None


def test_check_says_expired(client, app, monkeypatch):
    _, token = _request_link(client, app)
    monkeypatch.setattr(auth_links, "LOGIN_MAX_AGE", -1)
    res = _check(client, token)
    assert res.status_code == 400 and res.get_json()["code"] == "link_expired"


# ── consume ───────────────────────────────────────────────────────────────────

def test_a_link_for_an_account_signs_it_in(client, app, make_user):
    make_user(email="marie@test.fr")
    _, token = _request_link(client, app, next="/analyse/nouveau")
    res = _consume(client, token)
    assert res.status_code == 200
    assert res.get_json()["next"] == "/analyse/nouveau"
    assert res.get_json()["user"]["email"] == "marie@test.fr"
    assert "access_token_cookie" in _cookies(res)


def test_a_link_is_single_use(client, app, make_user):
    make_user(email="marie@test.fr")
    _, token = _request_link(client, app)
    assert _consume(client, token).status_code == 200
    again = _consume(client, token)
    assert again.status_code == 400 and again.get_json()["code"] == "link_invalid"
    assert _check(client, token).get_json()["code"] == "link_invalid"


def test_a_tampered_link_is_invalid(client, app):
    _, token = _request_link(client, app)
    res = _consume(client, token + "x")
    assert res.status_code == 400 and res.get_json()["code"] == "link_invalid"


def test_a_signed_link_without_its_row_is_invalid(client, app):
    # e.g. a link minted while the mail failed: no row was ever written.
    token = auth_links.make_login_token("never-written", "marie@test.fr")
    assert _consume(client, token).get_json()["code"] == "link_invalid"


def test_an_address_without_an_account_goes_on_to_finalise(client, app):
    _, token = _request_link(client, app, next="/analyse/nouveau")
    res = _consume(client, token)
    assert res.status_code == 200 and res.get_json() == {"signup": True}
    assert "access_token_cookie" not in _cookies(res)
    assert User.query.count() == 0      # decision 1: no account before consent
    ticket = auth_links.load_signup_ticket(
        client.get_cookie("signup_ticket", path="/api/auth").value
    ).payload
    assert ticket == {"method": "email", "sub": None, "email": "marie@test.fr",
                      "prenom_hint": "", "next": "/analyse/nouveau"}


def test_a_link_to_an_unverified_account_applies_ruling_4(client, app, make_user):
    user = make_user(email="marie@test.fr", verified=False)
    _, token = _request_link(client, app)
    assert _consume(client, token).status_code == 200
    db.session.expire_all()
    fresh = db.session.get(User, user.id)
    assert fresh.email_verified_at is not None
    assert not password_matches(fresh, "motdepasse1")


def test_a_conseiller_without_next_lands_on_the_demande(client, app, make_user):
    user = make_user(email="claire@capemploi.fr")
    db.session.add(CounselorProfile(user_id=user.id, structure="Cap Emploi 31",
                                    fonction="Conseillère", telephone="0561000000"))
    db.session.commit()
    _, token = _request_link(client, app, "claire@capemploi.fr")
    assert _consume(client, token).get_json()["next"] == "/conseiller"
```

- [ ] **Step 2: Run them to see them fail**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_email_link_routes.py`
Expected: FAIL, with 404s on `/api/auth/email-link`.

- [ ] **Step 3: Write the blueprint**

Create `backend/app/routes/auth_link.py`:

```python
"""« Recevoir un lien de connexion »: one link that signs up and signs in
(social sign-in spec, decisions 14–17)."""
from datetime import datetime

from flask import Blueprint, jsonify

from ..extensions import db
from ..models.login_link import LoginLink
from ..models.user import User
from ..services import auth_mail, sign_in
from ..utils import auth_links
from ..utils.request_body import json_object, text_field
# The one place a session opens, where a signed-in person lands, and the
# answer every dead link gets.
from .auth import _issue_session, _landing, _link_error

auth_link_bp = Blueprint("auth_link", __name__)


@auth_link_bp.post("/email-link")
def send_email_link():
    """The same answer for an address with or without an account: the link
    leaves either way, so it says nothing about who has one."""
    data = json_object()
    email = auth_links.normalise_email(data.get("email"))
    if not auth_links.email_shape_ok(email):
        return jsonify({"error": "Email invalide."}), 400
    user = User.query.filter_by(email=email).first()
    sent = auth_mail.login_link_if_due(email, user, text_field(data, "next") or None)
    return jsonify({"mail_sent": sent}), 200


@auth_link_bp.post("/email-link/check")
def check_email_link():
    """Is this link alive, and for which address? Never spends it: mail
    scanners open links, and some run the page's scripts (decision 16)."""
    payload, code = _live_link(text_field(json_object(), "token"))
    if code:
        return _link_error(code)
    return jsonify({"email": payload["email"]}), 200


@auth_link_bp.post("/email-link/consume")
def consume_email_link():
    payload, code = _live_link(text_field(json_object(), "token"))
    if code:
        return _link_error(code)
    # Atomic: of two clicks racing, one updates the row and the other finds
    # it used (decision 17).
    claimed = (
        LoginLink.query
        .filter(LoginLink.id == payload["jti"], LoginLink.used_at.is_(None))
        .update({"used_at": datetime.utcnow()}, synchronize_session=False)
    )
    db.session.commit()
    if claimed != 1:
        return _link_error("link_invalid")

    user = sign_in.existing_account(None, None, payload["email"])
    if user is None:
        response = jsonify({"signup": True})
        sign_in.set_signup_ticket(
            response, method="email", sub=None, email=payload["email"],
            next_path=payload.get("next"),
        )
        return response, 200
    response = jsonify({"user": user.to_dict(), "next": _landing(user, payload)})
    _issue_session(response, user)
    return response, 200


def _live_link(token):
    """(payload, None) for a signed, unexpired, unused link; else (None, code)."""
    result = auth_links.load_login_token(token)
    if result.error:
        return None, result.error
    payload = result.payload
    if not isinstance(payload.get("jti"), str) or not isinstance(payload.get("email"), str):
        return None, "link_invalid"
    row = db.session.get(LoginLink, payload["jti"])
    if row is None or row.used_at is not None:
        return None, "link_invalid"
    return payload, None
```

In `backend/app/__init__.py`, after `    from .routes.counselor_space import counselor_space_bp`, add:

```python
    from .routes.auth_link import auth_link_bp
```

After `    app.register_blueprint(counselor_space_bp, url_prefix="/api/counselor")`, add:

```python
    app.register_blueprint(auth_link_bp, url_prefix="/api/auth")
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_email_link_routes.py`
Expected: all pass.

- [ ] **Step 5: Add the three routes to the hostile-input fuzz**

In `backend/tests/test_no_500_on_hostile_input.py`, the `ROUTES` table ends with the `upsert_counselor_notes` row. Replace:

```python
        base=lambda rig: {"body": "note de test"},
        fields=["body"],
    ),
]
```

with:

```python
        base=lambda rig: {"body": "note de test"},
        fields=["body"],
    ),
    dict(
        name="email_link",
        method="post",
        path=lambda rig: "/api/auth/email-link",
        headers=lambda rig: {},
        base=lambda rig: {"email": "fuzz-link@test.fr", "next": "/espace"},
        fields=["email", "next"],
    ),
    dict(
        name="email_link_check",
        method="post",
        path=lambda rig: "/api/auth/email-link/check",
        headers=lambda rig: {},
        base=lambda rig: {"token": "not-a-token"},
        fields=["token"],
    ),
    dict(
        name="email_link_consume",
        method="post",
        path=lambda rig: "/api/auth/email-link/consume",
        headers=lambda rig: {},
        base=lambda rig: {"token": "not-a-token"},
        fields=["token"],
    ),
]
```

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_no_500_on_hostile_input.py`
Expected: all pass.

- [ ] **Step 6: Full suite**

Run: `venv/bin/pytest -q -p no:cacheprovider`
Expected: no failures.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/auth_link.py backend/app/__init__.py \
        backend/tests/test_email_link_routes.py backend/tests/test_no_500_on_hostile_input.py
git commit -m "feat(auth): email-link send, check and consume

Send answers the same for every address. Check names the address and
spends nothing (mail scanners). Consume is an atomic single use, then
signs the account in, or hands someone with no account a signup ticket.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: « Finaliser votre inscription » — `GET`/`POST /api/auth/signup`, the shared seed helper

**Files:**
- Modify: `backend/app/routes/auth.py`
- Modify: `backend/tests/test_no_500_on_hostile_input.py` (`rig` sets a ticket cookie; one `ROUTES` row)
- Test: `backend/tests/test_signup_ticket_routes.py`

**Interfaces:**
- Consumes:
  - `sign_in.live_signup_ticket`, `existing_account`, `unusable_password_hash`, `clear_signup_ticket` (Task 4)
  - `AuthIdentity` (Task 2); `PRENOM_MAX_LENGTH` (Task 4)
- Produces:
  - `GET /api/auth/signup` (cookie) → 200 `{email, prenom, method}`; 400 `{code: link_expired | link_invalid}`
  - `POST /api/auth/signup {prenom, tranche_age, consent}` (cookie) → 200 `{user, next}` + session cookies, ticket cookie cleared; 400 `{error}` or `{code}`
  - In `routes.auth`: `_seed_problem(seed: dict, consent, brackets=ACCEPTED_AGE_BRACKETS) -> str | None` and `_add_seeded_profile(user, seed) -> None`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_signup_ticket_routes.py`:

```python
"""« Finaliser votre inscription »: the account a signup ticket was waiting
for (social sign-in spec, decisions 1 and 18–22)."""
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.auth_identity import AuthIdentity
from app.models.profile import CONSENT_VERSION, Profile
from app.models.user import User
from app.routes.auth import password_matches
from app.services import sign_in
from app.utils import auth_links

SEND = "app.services.email_service.resend.Emails.send"
FORM = {"prenom": "Marie", "tranche_age": "25_34", "consent": True}


def _cookies(res) -> str:
    return " ".join(res.headers.getlist("Set-Cookie"))


def _give_ticket(client, method="google", sub="g-1", email="marie@gmail.com",
                 prenom_hint="Marie", next_path=None):
    client.set_cookie(
        "signup_ticket",
        auth_links.make_signup_ticket(method=method, sub=sub, email=email,
                                      prenom_hint=prenom_hint, next_path=next_path),
        path="/api/auth",
    )


def _signup(client, **form):
    return client.post("/api/auth/signup", json={**FORM, **form})


# ── GET ───────────────────────────────────────────────────────────────────────

def test_the_page_learns_the_address_and_the_prenom_to_prefill(client):
    _give_ticket(client)
    res = client.get("/api/auth/signup")
    assert res.status_code == 200
    assert res.get_json() == {"email": "marie@gmail.com", "prenom": "Marie", "method": "google"}


def test_without_a_ticket_there_is_nothing_to_finalise(client):
    res = client.get("/api/auth/signup")
    assert res.status_code == 400 and res.get_json()["code"] == "link_invalid"


def test_an_expired_ticket_says_so(client, monkeypatch):
    _give_ticket(client)
    monkeypatch.setattr(auth_links, "SIGNUP_MAX_AGE", -1)
    assert client.get("/api/auth/signup").get_json()["code"] == "link_expired"


# ── POST ──────────────────────────────────────────────────────────────────────

def test_finalising_creates_the_account_its_identity_and_its_consent_at_once(client):
    _give_ticket(client, next_path="/analyse/nouveau")
    res = _signup(client)
    assert res.status_code == 200
    assert res.get_json()["next"] == "/analyse/nouveau"
    assert "access_token_cookie" in _cookies(res)
    user = User.query.one()
    assert user.email == "marie@gmail.com" and user.email_verified_at is not None
    assert AuthIdentity.query.one().subject == "g-1"
    profile = Profile.query.one()
    assert (profile.prenom, profile.tranche_age) == ("Marie", "25_34")
    assert profile.consent_at is not None and profile.consent_version == CONSENT_VERSION


def test_finalising_spends_the_ticket(client):
    _give_ticket(client)
    _signup(client)
    assert client.get_cookie("signup_ticket", path="/api/auth") is None


def test_an_email_ticket_makes_an_account_with_no_identity(client):
    _give_ticket(client, method="email", sub=None, email="marie@test.fr", prenom_hint="")
    assert _signup(client).status_code == 200
    assert User.query.one().email == "marie@test.fr"
    assert AuthIdentity.query.count() == 0


def test_the_new_account_has_no_password_until_one_is_set(client):
    _give_ticket(client)
    _signup(client)
    assert not password_matches(User.query.one(), "motdepasse1")
    login = client.post("/api/auth/login",
                        json={"email": "marie@gmail.com", "password": "n'importe"})
    assert login.status_code == 401


def test_no_mail_leaves_when_the_account_is_created(client, app):
    app.config["RESEND_API_KEY"] = "re_test"
    _give_ticket(client)
    with patch(SEND) as mock_send:
        _signup(client)
    mock_send.assert_not_called()


@pytest.mark.parametrize("form, message", [
    ({"prenom": ""}, "Prénom requis."),
    ({"prenom": "   "}, "Prénom requis."),
    ({"tranche_age": ""}, "Tranche d'âge requise."),
    ({"consent": False}, "Le consentement est requis."),
    ({"consent": "true"}, "Le consentement est requis."),
    ({"tranche_age": "moins_25"}, "Valeur invalide pour tranche_age."),
    ({"tranche_age": "14_99"}, "Valeur invalide pour tranche_age."),
])
def test_a_refused_form_creates_nothing_and_keeps_the_ticket(client, form, message):
    _give_ticket(client)
    res = _signup(client, **form)
    assert res.status_code == 400 and res.get_json()["error"] == message
    assert User.query.count() == 0
    assert client.get_cookie("signup_ticket", path="/api/auth") is not None


def test_without_a_ticket_nothing_is_created(client):
    res = _signup(client)
    assert res.status_code == 400 and res.get_json()["code"] == "link_invalid"
    assert User.query.count() == 0


def test_an_address_claimed_meanwhile_is_entered_not_duplicated(client, make_user):
    existing = make_user(email="marie@gmail.com")
    _give_ticket(client)
    res = _signup(client, prenom="Autre")
    assert res.status_code == 200
    assert res.get_json()["user"]["id"] == existing.id
    assert User.query.count() == 1
    assert Profile.query.count() == 0          # the form never overwrites an account
    assert password_matches(db.session.get(User, existing.id), "motdepasse1")


def test_a_second_submit_enters_the_first_one_s_account(client):
    # Review Focus 3: the double click left before the first answer cleared the cookie.
    _give_ticket(client)
    first = _signup(client)
    _give_ticket(client)
    second = _signup(client)
    assert second.status_code == 200
    assert second.get_json()["user"]["id"] == first.get_json()["user"]["id"]
    assert User.query.count() == 1
    assert AuthIdentity.query.count() == 1 and Profile.query.count() == 1


def test_a_submit_that_loses_the_race_enters_the_winner_s_account(client, monkeypatch):
    # Review Focus 3: both submits looked before either committed.
    _give_ticket(client)
    winner = _signup(client).get_json()["user"]["id"]
    _give_ticket(client)
    real = sign_in.existing_account
    looks = []

    def blind_at_first(*args):
        looks.append(args)
        return None if len(looks) == 1 else real(*args)

    monkeypatch.setattr(sign_in, "existing_account", blind_at_first)
    res = _signup(client, prenom="Perdant")
    assert res.status_code == 200
    assert res.get_json()["user"]["id"] == winner
    assert User.query.count() == 1
    assert Profile.query.one().prenom == "Marie"


def test_a_prenom_longer_than_the_column_is_refused_not_a_500(client):
    # Review Focus 4: SQLite stores it; MySQL raises "Data too long".
    _give_ticket(client)
    res = _signup(client, prenom="M" * 121)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Le prénom est trop long : 120 caractères maximum."
    assert User.query.count() == 0


def test_register_refuses_it_too(client):
    # Review Focus 4: the shared seed helper guards the password signup as well.
    res = client.post("/api/auth/register", json={
        "email": "long@test.fr", "password": "motdepasse1",
        "prenom": "M" * 121, "tranche_age": "25_34", "consent": True,
    })
    assert res.status_code == 400
    assert User.query.count() == 0


def test_a_prenom_that_cannot_be_stored_is_refused(client):
    _give_ticket(client)
    res = _signup(client, prenom="Ma\ud800rie")
    assert res.status_code == 400
    assert User.query.count() == 0
```

- [ ] **Step 2: Run them to see them fail**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_signup_ticket_routes.py`
Expected: FAIL. `/api/auth/signup` answers 405 or 404, and the register test answers 201.

- [ ] **Step 3: Imports**

In `backend/app/routes/auth.py`, replace:

```python
from datetime import datetime

from ..extensions import db, bcrypt
from ..models.counselor_profile import CounselorProfile
from ..models.profile import ACCEPTED_AGE_BRACKETS, CONSENT_VERSION, Profile
from ..models.user import User
from ..services import auth_mail, demande_mail, email_service
```

with:

```python
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from ..extensions import db, bcrypt
from ..models.auth_identity import AuthIdentity
from ..models.counselor_profile import CounselorProfile
from ..models.profile import (
    ACCEPTED_AGE_BRACKETS, AGE_BRACKETS, CONSENT_VERSION, PRENOM_MAX_LENGTH, Profile,
)
from ..models.user import User
from ..services import auth_mail, demande_mail, email_service, sign_in
```

- [ ] **Step 4: `register` uses the shared seed helper**

Replace:

```python
    if seed:
        if data.get("consent") is not True:
            return jsonify({"error": "Le consentement est requis."}), 400
        bracket = seed.get("tranche_age")
        if bracket and bracket not in ACCEPTED_AGE_BRACKETS:
            return jsonify({"error": "Valeur invalide pour tranche_age."}), 400
```

with:

```python
    if seed:
        problem = _seed_problem(seed, data.get("consent"))
        if problem:
            return jsonify({"error": problem}), 400
```

Replace:

```python
    if seed:
        db.session.add(Profile(
            user_id=user.id,
            consent_at=datetime.utcnow(),
            consent_version=CONSENT_VERSION,
            **seed,
        ))
```

with:

```python
    if seed:
        _add_seeded_profile(user, seed)
```

- [ ] **Step 5: The two signup routes**

Immediately before `@auth_bp.post("/login")`, add:

```python
@auth_bp.get("/signup")
def signup_details():
    """What « Finaliser votre inscription » shows: the address the ticket
    proves, and the prénom the provider gave, to prefill."""
    ticket, code = sign_in.live_signup_ticket()
    if code:
        return _link_error(code)
    return jsonify({
        "email": ticket["email"],
        "prenom": ticket.get("prenom_hint") or "",
        "method": ticket["method"],
    }), 200


@auth_bp.post("/signup")
def signup():
    """The account a signup ticket was waiting for, created with its consent
    in one commit (social sign-in spec, decisions 1 and 19). Nothing exists
    before this: no users row, no session."""
    ticket, code = sign_in.live_signup_ticket()
    if code:
        return _link_error(code)

    data = json_object()
    seed = {field: text_field(data, field) for field in SEED_FIELDS}
    if not seed["prenom"]:
        return jsonify({"error": "Prénom requis."}), 400
    if not seed["tranche_age"]:
        return jsonify({"error": "Tranche d'âge requise."}), 400
    # The seven brackets the form offers: the legacy one is never asked again.
    problem = _seed_problem(seed, data.get("consent"), AGE_BRACKETS)
    if problem:
        return jsonify({"error": problem}), 400

    provider = None if ticket["method"] == "email" else ticket["method"]
    sub = ticket.get("sub")
    email = ticket["email"]
    # Another tab, or a double click, may have finished first: what it made
    # is entered, and this form overwrites nothing (decision 19).
    user = sign_in.existing_account(provider, sub, email)
    if user is None:
        user = User(
            email=email,
            password_hash=sign_in.unusable_password_hash(),
            email_verified_at=datetime.utcnow(),   # the ticket is the proof
        )
        db.session.add(user)
        try:
            db.session.flush()   # user.id, for the identity and the profile
            if provider:
                db.session.add(AuthIdentity(user_id=user.id, provider=provider, subject=sub))
            _add_seeded_profile(user, seed)
            db.session.commit()
        except IntegrityError:
            # A concurrent submit committed the same address first.
            db.session.rollback()
            user = sign_in.existing_account(provider, sub, email)
            if user is None:
                raise

    response = jsonify({"user": user.to_dict(), "next": _landing(user, ticket)})
    sign_in.clear_signup_ticket(response)
    _issue_session(response, user)
    return response, 200


```

- [ ] **Step 6: The shared seed helper**

Immediately before `def _link_error(code: str):`, add:

```python
def _seed_problem(seed: dict, consent, brackets=ACCEPTED_AGE_BRACKETS) -> str | None:
    """Why a signup's profile seed cannot be stored, as the sentence to show,
    or None. register and signup share it: they are the two doors that write
    a first consent (social sign-in spec, decision 20). The length check is
    the one SQLite never makes and MySQL answers with an error."""
    if consent is not True:
        return "Le consentement est requis."
    bracket = seed.get("tranche_age")
    if bracket and bracket not in brackets:
        return "Valeur invalide pour tranche_age."
    prenom = seed.get("prenom", "")
    if len(prenom) > PRENOM_MAX_LENGTH:
        return f"Le prénom est trop long : {PRENOM_MAX_LENGTH} caractères maximum."
    try:
        prenom.encode("utf-8")
    except UnicodeEncodeError:
        return "Le prénom contient un caractère non pris en charge."
    return None


def _add_seeded_profile(user: User, seed: dict) -> None:
    """The Profil de base row a signup opens, with the consent just given."""
    db.session.add(Profile(
        user_id=user.id,
        consent_at=datetime.utcnow(),
        consent_version=CONSENT_VERSION,
        **seed,
    ))


```

- [ ] **Step 7: Run the tests to see them pass**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_signup_ticket_routes.py tests/test_signup_profile_seed.py tests/test_auth_gate.py`
Expected: all pass. The existing seed tests keep their messages.

- [ ] **Step 8: Add the route to the hostile-input fuzz**

In `backend/tests/test_no_500_on_hostile_input.py`, below the existing imports (after `from app.models.user import User`), add:

```python
from app.utils import auth_links
```

In the `rig` fixture, replace:

```python
    analysis = _analysis(share_token="fuzz-share-token")

    return {
```

with:

```python
    analysis = _analysis(share_token="fuzz-share-token")

    # POST /api/auth/signup reads its body only behind a live ticket. Every
    # fuzzed call leaves at least one field invalid but one (consent=True),
    # so the ticket survives until that last call.
    client.set_cookie(
        "signup_ticket",
        auth_links.make_signup_ticket(method="email", sub=None, email="fuzz-signup@test.fr"),
        path="/api/auth",
    )

    return {
```

In `ROUTES`, replace:

```python
        base=lambda rig: {"token": "not-a-token"},
        fields=["token"],
    ),
]
```

with:

```python
        base=lambda rig: {"token": "not-a-token"},
        fields=["token"],
    ),
    dict(
        name="signup",
        method="post",
        path=lambda rig: "/api/auth/signup",
        headers=lambda rig: {},
        base=lambda rig: {"prenom": "Rig", "tranche_age": "25_34", "consent": True},
        fields=["prenom", "tranche_age", "consent"],
    ),
]
```

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_no_500_on_hostile_input.py`
Expected: all pass.

- [ ] **Step 9: Full suite**

Run: `venv/bin/pytest -q -p no:cacheprovider`
Expected: no failures.

- [ ] **Step 10: Commit**

```bash
git add backend/app/routes/auth.py backend/tests/test_signup_ticket_routes.py \
        backend/tests/test_no_500_on_hostile_input.py
git commit -m "feat(auth): finalise a signup from its ticket

GET /signup prefills the page; POST /signup creates the verified,
password-less account, its provider identity and its consent in one
commit, or enters the account a racing submit made. register and
signup share one seed check, which now refuses a prénom MySQL would.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: « Continuer avec Google / Microsoft » — the OAuth round trip

**Files:**
- Modify: `backend/app/config.py` (four keys; session cookie settings)
- Create: `backend/app/services/oauth_clients.py`
- Create: `backend/app/routes/auth_oauth.py`
- Modify: `backend/app/__init__.py` (`oauth_clients.init_app(app)`; register the blueprint)
- Modify: `backend/tests/conftest.py` (blank the provider keys)
- Modify: `backend/.env.example`, `.env.example`
- Test: `backend/tests/test_oauth_routes.py`

**Interfaces:**
- Consumes:
  - `sign_in.resolve_oauth`, `set_signup_ticket`, `microsoft_issuer_ok` (Task 4)
  - `auth_links.safe_next`; `PROVIDERS` (Task 2)
  - `routes.auth._issue_session`, `_landing`
- Produces:
  - In `app.services.oauth_clients`:
    - `init_app(app)`
    - `client(name) -> FlaskOAuth2App | None`
    - `configured() -> dict[str, bool]`
    - `claims_options(name, client_id) -> dict`
    - `AUTHORIZE_PARAMS: dict`, `GOOGLE_ISSUERS: tuple`
  - Endpoints:
    - `GET /api/auth/providers` → `{google: bool, microsoft: bool}`
    - `GET /api/auth/<provider>/start?next=` → 302 to the provider, or 302 `/connexion?erreur=indisponible | echec`. An unknown provider is a 404.
    - `GET /api/auth/<provider>/callback` → 302 to the landing + session cookies, or 302 `/inscription/finaliser` + `signup_ticket`, or 302 `/connexion?erreur=annule | echec | indisponible | email_non_verifie`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_oauth_routes.py`:

```python
"""« Continuer avec Google / Microsoft », walked from /start to the landing
with the provider faked at the network boundary only (social sign-in spec,
decisions 5–13). Signature verification is the one step skipped; state,
PKCE, nonce, issuer, audience and expiry all run for real."""
import time
from unittest.mock import patch
from urllib.parse import parse_qs, quote, urlsplit

import pytest
import requests
from authlib.integrations.flask_client import FlaskOAuth2App
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from authlib.oidc.core import CodeIDToken, UserInfo

from app.extensions import db
from app.models.auth_identity import AuthIdentity
from app.models.counselor_profile import CounselorProfile
from app.models.user import User
from app.services import oauth_clients, sign_in
from app.utils import auth_links

CLIENT_ID = {"google": "google-client", "microsoft": "microsoft-client"}
WORK_TENANT = "72f988bf-86f1-41af-91ab-2d7cd011db47"

METADATA = {
    "google": {
        "issuer": "https://accounts.google.com",
        "authorization_endpoint": "https://accounts.google.test/o/oauth2/v2/auth",
        "token_endpoint": "https://oauth2.google.test/token",
        "jwks_uri": "https://www.google.test/oauth2/v3/certs",
    },
    "microsoft": {
        "issuer": "https://login.microsoftonline.com/{tenantid}/v2.0",
        "authorization_endpoint": "https://login.microsoft.test/common/oauth2/v2.0/authorize",
        "token_endpoint": "https://login.microsoft.test/common/oauth2/v2.0/token",
        "jwks_uri": "https://login.microsoft.test/common/discovery/v2.0/keys",
    },
}


@pytest.fixture
def providers(app, monkeypatch):
    """Both providers configured, their discovery documents served locally."""
    app.config.update(
        GOOGLE_CLIENT_ID=CLIENT_ID["google"], GOOGLE_CLIENT_SECRET="google-secret",
        MICROSOFT_CLIENT_ID=CLIENT_ID["microsoft"], MICROSOFT_CLIENT_SECRET="microsoft-secret",
    )
    monkeypatch.setattr(FlaskOAuth2App, "load_server_metadata",
                        lambda self: dict(METADATA[self.name]))


def _cookies(res) -> str:
    return " ".join(res.headers.getlist("Set-Cookie"))


def _start(client, provider, next_path=None):
    path = f"/api/auth/{provider}/start"
    if next_path is not None:
        path += "?next=" + quote(next_path, safe="")
    return client.get(path)


def _query(res) -> dict:
    return {k: v[0] for k, v in parse_qs(urlsplit(res.headers["Location"]).query).items()}


def _id_claims(provider, nonce, **claims):
    now = int(time.time())
    base = {"aud": CLIENT_ID[provider], "iat": now, "exp": now + 600, "nonce": nonce}
    if provider == "google":
        base["iss"] = "https://accounts.google.com"
    else:
        base["iss"] = f"https://login.microsoftonline.com/{claims.get('tid', WORK_TENANT)}/v2.0"
    return {**base, **claims}


def _callback(client, provider, claims, *, state, seen=None):
    """The provider's answer: its token endpoint returns an ID token carrying
    `claims`, which Authlib's claim checks then judge with the options the
    route passed."""
    seen = seen if seen is not None else {}

    def fetch_access_token(self, **params):
        seen["token_request"] = params
        return {"access_token": "at", "token_type": "Bearer", "id_token": "unchecked"}

    def parse_id_token(self, token, nonce, claims_options=None, claims_cls=None, leeway=120):
        CodeIDToken(dict(claims), {"alg": "RS256"}, claims_options,
                    {"nonce": nonce, "client_id": self.client_id}).validate(leeway=leeway)
        return UserInfo(claims)

    with patch.object(FlaskOAuth2App, "fetch_access_token", fetch_access_token), \
            patch.object(FlaskOAuth2App, "parse_id_token", parse_id_token):
        return client.get(f"/api/auth/{provider}/callback?code=the-code&state={state}")


def _sign_in(client, provider, next_path=None, **claims):
    q = _query(_start(client, provider, next_path))
    return _callback(client, provider, _id_claims(provider, q["nonce"], **claims), state=q["state"])


# ── configuration (decision 13) ───────────────────────────────────────────────

def test_no_keys_no_buttons(client):
    assert client.get("/api/auth/providers").get_json() == {"google": False, "microsoft": False}


def test_keys_bring_the_buttons(client, providers):
    assert client.get("/api/auth/providers").get_json() == {"google": True, "microsoft": True}


def test_one_key_is_not_enough(client, app):
    app.config["GOOGLE_CLIENT_ID"] = "google-client"
    assert client.get("/api/auth/providers").get_json()["google"] is False


def test_production_sends_the_state_cookie_over_https_only():
    from app.config import Config, ProductionConfig
    assert ProductionConfig.SESSION_COOKIE_SECURE is True
    assert Config.SESSION_COOKIE_SAMESITE == "Lax"


def test_a_hung_provider_cannot_hold_a_thread(app, providers):
    assert oauth_clients.client("google").client_kwargs["default_timeout"] == 10


def test_claims_options_are_built_fresh_each_time():
    first = oauth_clients.claims_options("microsoft", "c")
    first["iss"].pop("validate")
    assert "validate" in oauth_clients.claims_options("microsoft", "c")["iss"]


# ── start (decision 5) ────────────────────────────────────────────────────────

def test_an_unconfigured_provider_is_unavailable(client):
    res = _start(client, "google")
    assert res.status_code == 302
    assert res.headers["Location"] == "/connexion?erreur=indisponible"


def test_an_unknown_provider_is_a_404(client, providers):
    assert client.get("/api/auth/apple/start").status_code == 404
    assert client.get("/api/auth/apple/callback").status_code == 404


def test_google_start_asks_for_an_account_with_pkce_and_a_nonce(client, app, providers):
    app.config["APP_URL"] = "https://neoori.tech"
    res = _start(client, "google")
    assert res.status_code == 302
    assert res.headers["Location"].startswith(METADATA["google"]["authorization_endpoint"])
    q = _query(res)
    assert q["client_id"] == "google-client"
    assert q["redirect_uri"] == "https://neoori.tech/api/auth/google/callback"
    assert q["scope"] == "openid email profile"
    assert q["prompt"] == "select_account"
    assert q["code_challenge_method"] == "S256" and q["code_challenge"]
    assert q["nonce"] and q["state"]
    assert "response_mode" not in q


def test_microsoft_answers_in_the_query_string(client, providers):
    q = _query(_start(client, "microsoft"))
    assert q["response_mode"] == "query" and q["prompt"] == "select_account"


def test_an_unreachable_provider_is_a_failure_not_a_500(client, providers, monkeypatch):
    # Review Focus 2.
    def unreachable(self):
        raise requests.ConnectionError("discovery document unreachable")
    monkeypatch.setattr(FlaskOAuth2App, "load_server_metadata", unreachable)
    res = _start(client, "google")
    assert res.status_code == 302 and res.headers["Location"] == "/connexion?erreur=echec"


# ── callback: who gets in (decisions 7–11) ────────────────────────────────────

def test_a_new_google_address_goes_on_to_finalise(client, providers):
    res = _sign_in(client, "google", sub="g-1", email="marie@gmail.com",
                   email_verified=True, given_name="Marie")
    assert res.status_code == 302 and res.headers["Location"] == "/inscription/finaliser"
    assert "access_token_cookie" not in _cookies(res)
    assert User.query.count() == 0
    ticket = auth_links.load_signup_ticket(
        client.get_cookie("signup_ticket", path="/api/auth").value).payload
    assert ticket == {"method": "google", "sub": "g-1", "email": "marie@gmail.com",
                      "prenom_hint": "Marie", "next": None}


def test_a_known_account_is_signed_in_and_sent_home(client, providers, make_user):
    make_user(email="marie@gmail.com")
    res = _sign_in(client, "google", sub="g-1", email="marie@gmail.com", email_verified=True)
    assert res.headers["Location"] == "/espace"
    assert "access_token_cookie" in _cookies(res)
    assert AuthIdentity.query.one().subject == "g-1"


@pytest.mark.parametrize("role, home", [
    ("admin", "/admin"), ("counselor", "/conseiller"), ("candidate", "/espace"),
])
def test_each_role_lands_on_its_own_home(client, providers, make_user, role, home):
    make_user(email="marie@gmail.com", role=role)
    res = _sign_in(client, "google", sub="g-1", email="marie@gmail.com", email_verified=True)
    assert res.headers["Location"] == home


def test_a_conseiller_with_a_demande_lands_on_it(client, providers, make_user):
    user = make_user(email="claire@capemploi.fr")
    db.session.add(CounselorProfile(user_id=user.id, structure="Cap Emploi 31",
                                    fonction="Conseillère", telephone="0561000000"))
    db.session.commit()
    res = _sign_in(client, "google", sub="g-1", email="claire@capemploi.fr", email_verified=True)
    assert res.headers["Location"] == "/conseiller"


def test_an_unverified_google_address_is_refused(client, providers):
    res = _sign_in(client, "google", sub="g-1", email="marie@gmail.com", email_verified=False)
    assert res.headers["Location"] == "/connexion?erreur=email_non_verifie"


def test_a_work_account_without_proof_cannot_enter_the_account_of_its_address(
        client, providers, make_user):
    """nOAuth: a tenant admin can write any address into `email`."""
    make_user(email="marie@entreprise.fr")
    res = _sign_in(client, "microsoft", sub="m-2", email="marie@entreprise.fr", tid=WORK_TENANT)
    assert res.headers["Location"] == "/connexion?erreur=email_non_verifie"
    assert AuthIdentity.query.count() == 0
    assert "access_token_cookie" not in _cookies(res)


def test_a_proven_work_address_enters(client, providers, make_user):
    make_user(email="marie@entreprise.fr")
    res = _sign_in(client, "microsoft", sub="m-2", email="marie@entreprise.fr",
                   tid=WORK_TENANT, xms_edov=True)
    assert res.headers["Location"] == "/espace"


def test_a_personal_microsoft_account_enters(client, providers, make_user):
    make_user(email="marie@outlook.fr")
    res = _sign_in(client, "microsoft", sub="m-1", email="marie@outlook.fr",
                   tid=sign_in.MSA_TENANT_ID)
    assert res.headers["Location"] == "/espace"


# ── callback: the token checks (decision 6) ───────────────────────────────────

def test_a_token_naming_another_tenant_s_issuer_is_refused(client, providers, make_user):
    make_user(email="marie@outlook.fr")
    q = _query(_start(client, "microsoft"))
    claims = _id_claims("microsoft", q["nonce"], sub="m-1", email="marie@outlook.fr",
                        tid=sign_in.MSA_TENANT_ID)
    claims["iss"] = f"https://login.microsoftonline.com/{WORK_TENANT}/v2.0"
    res = _callback(client, "microsoft", claims, state=q["state"])
    assert res.headers["Location"] == "/connexion?erreur=echec"


def test_a_token_issued_to_another_app_is_refused(client, providers, make_user):
    make_user(email="marie@gmail.com")
    q = _query(_start(client, "google"))
    claims = _id_claims("google", q["nonce"], sub="g-1", email="marie@gmail.com",
                        email_verified=True, aud="someone-else")
    assert _callback(client, "google", claims, state=q["state"]).headers["Location"] \
        == "/connexion?erreur=echec"


def test_a_token_for_another_sign_in_is_refused(client, providers, make_user):
    make_user(email="marie@gmail.com")
    q = _query(_start(client, "google"))
    claims = _id_claims("google", "another-nonce", sub="g-1", email="marie@gmail.com",
                        email_verified=True)
    assert _callback(client, "google", claims, state=q["state"]).headers["Location"] \
        == "/connexion?erreur=echec"


def test_an_expired_token_is_refused(client, providers, make_user):
    make_user(email="marie@gmail.com")
    q = _query(_start(client, "google"))
    now = int(time.time())
    claims = _id_claims("google", q["nonce"], sub="g-1", email="marie@gmail.com",
                        email_verified=True, iat=now - 4000, exp=now - 3600)
    assert _callback(client, "google", claims, state=q["state"]).headers["Location"] \
        == "/connexion?erreur=echec"


def test_the_code_exchange_carries_the_pkce_verifier(client, providers):
    q = _query(_start(client, "google"))
    seen = {}
    _callback(client, "google",
              _id_claims("google", q["nonce"], sub="g-1", email="m@gmail.com", email_verified=True),
              state=q["state"], seen=seen)
    assert create_s256_code_challenge(seen["token_request"]["code_verifier"]) == q["code_challenge"]


# ── callback: every failure is a redirect (decision 12) ───────────────────────

def test_cancelling_at_the_provider_says_so(client, providers):
    state = _query(_start(client, "google"))["state"]
    res = client.get(f"/api/auth/google/callback?error=access_denied&state={state}")
    assert res.headers["Location"] == "/connexion?erreur=annule"


def test_any_other_provider_error_is_a_failure(client, providers):
    res = client.get("/api/auth/google/callback?error=server_error")
    assert res.headers["Location"] == "/connexion?erreur=echec"


@pytest.mark.parametrize("query", ["?code=c&state=never-issued", "?code=c", ""])
def test_a_callback_without_a_live_state_is_a_failure_not_a_500(client, providers, query):
    # Review Focus 2: a bookmark, a second tab, a lost session cookie.
    res = client.get(f"/api/auth/google/callback{query}")
    assert res.status_code == 302 and res.headers["Location"] == "/connexion?erreur=echec"


def test_a_callback_replayed_with_back_is_a_failure(client, providers, make_user):
    # Review Focus 2.
    make_user(email="marie@gmail.com")
    q = _query(_start(client, "google"))
    claims = _id_claims("google", q["nonce"], sub="g-1", email="marie@gmail.com",
                        email_verified=True)
    assert _callback(client, "google", claims, state=q["state"]).headers["Location"] == "/espace"
    assert _callback(client, "google", claims, state=q["state"]).headers["Location"] \
        == "/connexion?erreur=echec"


def test_a_failure_while_resolving_is_a_failure_not_a_500(client, providers, monkeypatch):
    def broken(*args):
        raise RuntimeError("database unavailable")
    monkeypatch.setattr(sign_in, "resolve_oauth", broken)
    res = _sign_in(client, "google", sub="g-1", email="m@gmail.com", email_verified=True)
    assert res.headers["Location"] == "/connexion?erreur=echec"


# ── next (decision 5) ─────────────────────────────────────────────────────────

def test_the_destination_survives_the_round_trip_byte_for_byte(client, providers, make_user):
    # Review Focus 5.
    make_user(email="marie@gmail.com")
    destination = "/analyse/nouveau?parcours=2&x=a%20b"
    res = _sign_in(client, "google", next_path=destination, sub="g-1",
                   email="marie@gmail.com", email_verified=True)
    assert res.headers["Location"] == destination


def test_an_unsafe_destination_is_dropped_at_start(client, providers, make_user):
    make_user(email="marie@gmail.com")
    res = _sign_in(client, "google", next_path="//evil.com", sub="g-1",
                   email="marie@gmail.com", email_verified=True)
    assert res.headers["Location"] == "/espace"


def test_the_destination_reaches_the_ticket(client, providers):
    _sign_in(client, "google", next_path="/analyse/nouveau", sub="g-1",
             email="marie@gmail.com", email_verified=True)
    ticket = auth_links.load_signup_ticket(
        client.get_cookie("signup_ticket", path="/api/auth").value).payload
    assert ticket["next"] == "/analyse/nouveau"
```

- [ ] **Step 2: Run them to see them fail**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_oauth_routes.py`
Expected: FAIL. The collection error is `ImportError: cannot import name 'oauth_clients'`.

- [ ] **Step 3: Config**

In `backend/app/config.py`, after the line `    ADMIN_NOTIFY_EMAILS = _addresses(os.environ.get("ADMIN_NOTIFY_EMAIL", ""))`, add:

```python
    # « Continuer avec Google / Microsoft » (social sign-in spec, decision 13):
    # a provider's button shows only once both its keys are set.
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    MICROSOFT_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID")
    MICROSOFT_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET")
    # Authlib keeps the OAuth state, PKCE verifier and nonce in Flask's
    # session cookie between /start and /callback. Lax: the provider sends
    # the browser back with a top-level GET, which carries it.
    SESSION_COOKIE_SAMESITE = "Lax"
```

Replace:

```python
class ProductionConfig(Config):
    DEBUG = False
    JWT_COOKIE_SECURE = True   # required for SameSite=None
```

with:

```python
class ProductionConfig(Config):
    DEBUG = False
    JWT_COOKIE_SECURE = True   # required for SameSite=None
    SESSION_COOKIE_SECURE = True   # the OAuth state cookie, and the signup ticket
```

- [ ] **Step 4: Keep a developer's real keys out of the tests**

In `backend/tests/conftest.py`, replace:

```python
    application.config["ADMIN_NOTIFY_EMAILS"] = []
    with application.app_context():
```

with:

```python
    application.config["ADMIN_NOTIFY_EMAILS"] = []
    # And the sign-in providers: a developer's backend/.env carrying real
    # Google or Microsoft keys must not switch the buttons on in the tests.
    application.config.update(
        GOOGLE_CLIENT_ID=None, GOOGLE_CLIENT_SECRET=None,
        MICROSOFT_CLIENT_ID=None, MICROSOFT_CLIENT_SECRET=None,
    )
    with application.app_context():
```

- [ ] **Step 5: The provider clients**

Create `backend/app/services/oauth_clients.py`:

```python
"""Google and Microsoft as OpenID Connect providers (social sign-in spec,
decisions 5, 6, 13 and 25).

A client exists only once both its keys are in the config: until then the
provider is "not configured", its button stays hidden and /start answers
« indisponible ». Clients are registered on first use, in a registry that
belongs to the app: the factory — and the test suite — build many apps, and
Authlib's registry holds one app and caches its clients.

Scopes are openid email profile and nothing else: neoori never calls a
provider API, so no provider token is kept.
"""
from authlib.integrations.flask_client import OAuth
from flask import current_app

from ..models.auth_identity import PROVIDERS
from . import sign_in

_EXTENSION = "authlib.integrations.flask_client"

_DISCOVERY = {
    "google": "https://accounts.google.com/.well-known/openid-configuration",
    "microsoft": "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
}

# Google writes its issuer both ways, and its documentation says so.
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

# Asked on every sign-in. select_account: job seekers often use shared
# computers (agencies, libraries), and without it the next person is signed
# in silently as the last one. Microsoft answers in the query string: a
# form_post is a cross-site POST, which does not carry the Lax session cookie
# that holds the state.
AUTHORIZE_PARAMS = {
    "google": {"prompt": "select_account"},
    "microsoft": {"prompt": "select_account", "response_mode": "query"},
}


def init_app(app) -> None:
    OAuth(app)


def client(name: str):
    """The provider's Authlib client, or None when the name is unknown or a
    key is missing (decision 13)."""
    if name not in PROVIDERS:
        return None
    client_id = current_app.config.get(f"{name.upper()}_CLIENT_ID")
    client_secret = current_app.config.get(f"{name.upper()}_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    oauth = current_app.extensions[_EXTENSION]
    return oauth.create_client(name) or oauth.register(
        name,
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=_DISCOVERY[name],
        client_kwargs={
            "scope": "openid email profile",
            "code_challenge_method": "S256",
            # Discovery, JWKS and the code exchange: a hung provider must not
            # hold a gunicorn thread.
            "default_timeout": 10,
        },
    )


def configured() -> dict[str, bool]:
    return {name: client(name) is not None for name in PROVIDERS}


def claims_options(name: str, client_id: str) -> dict:
    """What the ID token must say beyond its signature, expiry and nonce,
    which Authlib checks itself: who issued it, and that it was issued to us
    (decision 6). Built fresh on every call: Authlib pops the "validate" hook
    out of the dict it is handed."""
    audience = {"essential": True, "value": client_id}
    if name == "google":
        return {"iss": {"essential": True, "values": list(GOOGLE_ISSUERS)}, "aud": audience}
    return {
        "iss": {
            "essential": True,
            "validate": lambda claims, _value: sign_in.microsoft_issuer_ok(claims),
        },
        "aud": audience,
    }
```

- [ ] **Step 6: The blueprint**

Create `backend/app/routes/auth_oauth.py`:

```python
"""« Continuer avec Google / Microsoft »: the server-side authorization-code
flow (social sign-in spec, decisions 5–13).

No provider JavaScript runs on our pages: the button is a link to /start,
the provider sends the browser back to /callback, and every way out of
/callback is a redirect — into a session, to « Finaliser votre inscription »,
or to /connexion with an error code the page turns into a French sentence.
"""
import secrets

from flask import Blueprint, abort, current_app, jsonify, redirect, request, session

from ..extensions import db
from ..models.auth_identity import PROVIDERS
from ..services import oauth_clients, sign_in
from ..utils import auth_links
# The one place a session opens, and where a signed-in person lands.
from .auth import _issue_session, _landing

auth_oauth_bp = Blueprint("auth_oauth", __name__)

# Where /start keeps `next` for its callback, tied to the state it belongs
# to. One slot: of two sign-ins started in parallel, the earlier lands on its
# home rather than on a destination meant for the other.
_NEXT_SLOT = "oauth_next"


@auth_oauth_bp.get("/providers")
def providers():
    """Which buttons the sign-in pages show (decision 13)."""
    return jsonify(oauth_clients.configured()), 200


@auth_oauth_bp.get("/<provider>/start")
def start(provider):
    if provider not in PROVIDERS:
        abort(404)
    client = oauth_clients.client(provider)
    if client is None:
        return _to_connexion("indisponible")
    state = secrets.token_urlsafe(32)
    session[_NEXT_SLOT] = {"state": state, "next": auth_links.safe_next(request.args.get("next"))}
    try:
        return client.authorize_redirect(
            _redirect_uri(provider), state=state, **oauth_clients.AUTHORIZE_PARAMS[provider]
        )
    except Exception:
        # Most often the provider's discovery document is unreachable.
        current_app.logger.exception("OAuth start failed for %s.", provider)
        session.pop(_NEXT_SLOT, None)
        return _to_connexion("echec")


@auth_oauth_bp.get("/<provider>/callback")
def callback(provider):
    if provider not in PROVIDERS:
        abort(404)
    client = oauth_clients.client(provider)
    if client is None:
        return _to_connexion("indisponible")

    slot = session.pop(_NEXT_SLOT, None) or {}
    next_path = (
        auth_links.safe_next(slot.get("next"))
        if slot.get("state") == request.args.get("state") else None
    )

    error = request.args.get("error")
    if error:
        return _to_connexion("annule" if error == "access_denied" else "echec")

    try:
        token = client.authorize_access_token(
            claims_options=oauth_clients.claims_options(provider, client.client_id)
        )
        claims = token.get("userinfo") or {}
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise ValueError("the provider sent no ID token subject")
        outcome = sign_in.resolve_oauth(provider, claims)
    except Exception:
        # A dead or replayed state, a refused token, the provider or the
        # database failing: the person is on a browser navigation, and a
        # 500 page there is a dead end.
        db.session.rollback()
        current_app.logger.exception("OAuth callback failed for %s.", provider)
        return _to_connexion("echec")

    if outcome.kind == "refused":
        return _to_connexion("email_non_verifie")
    if outcome.kind == "signup":
        response = redirect("/inscription/finaliser")
        sign_in.set_signup_ticket(
            response, method=provider, sub=claims["sub"], email=outcome.email,
            prenom_hint=claims.get("given_name"), next_path=next_path,
        )
        return response
    response = redirect(_landing(outcome.user, {"next": next_path}) or _home_path(outcome.user.role))
    _issue_session(response, outcome.user)
    return response


def _redirect_uri(provider: str) -> str:
    """From APP_URL, never the request: behind nginx, Flask sees backend:5000."""
    return f"{current_app.config['APP_URL']}/api/auth/{provider}/callback"


def _to_connexion(code: str):
    return redirect(f"/connexion?erreur={code}")


def _home_path(role: str) -> str:
    """The role's home. frontend/src/lib/home.ts homeFor says the same:
    keep the two in step."""
    if role == "admin":
        return "/admin"
    if role == "counselor":
        return "/conseiller"
    return "/espace"
```

In `backend/app/__init__.py`, after the line `    bcrypt.init_app(app)`, add:

```python
    from .services import oauth_clients
    oauth_clients.init_app(app)
```

After `    from .routes.auth_link import auth_link_bp`, add:

```python
    from .routes.auth_oauth import auth_oauth_bp
```

After `    app.register_blueprint(auth_link_bp, url_prefix="/api/auth")`, add:

```python
    app.register_blueprint(auth_oauth_bp, url_prefix="/api/auth")
```

- [ ] **Step 7: Run the tests to see them pass**

Run: `venv/bin/pytest -q -p no:cacheprovider tests/test_oauth_routes.py`
Expected: all pass.

- [ ] **Step 8: Document the keys in both env examples**

In `backend/.env.example`, after the line `APP_URL=http://localhost:8080`, add:

```
# « Continuer avec Google / Microsoft »: a button shows only once both of its
# provider's keys are set. How to create them:
# docs/superpowers/specs/2026-10-03-social-login-design.md, appendices A and B.
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
```

In the root `.env.example`, after the `ADMIN_NOTIFY_EMAIL=` line, add:

```

# ---- Sign-in with Google / Microsoft (optional) ----
# A provider's button shows only once both its keys are set. How to create
# them: docs/superpowers/specs/2026-10-03-social-login-design.md, appendices
# A and B. After an edit: docker compose -f docker-compose.prod.yml up -d --force-recreate backend
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
MICROSOFT_CLIENT_ID=
# Microsoft secrets expire (24 months at most). Write the expiry date on this
# line when you paste one; renew a month before (DOCKER.md, "Google /
# Microsoft sign-in keys").
MICROSOFT_CLIENT_SECRET=
```

- [ ] **Step 9: Full suite**

Run: `venv/bin/pytest -q -p no:cacheprovider`
Expected: no failures.

- [ ] **Step 10: Commit**

```bash
git add backend/app/config.py backend/app/services/oauth_clients.py backend/app/routes/auth_oauth.py \
        backend/app/__init__.py backend/tests/conftest.py backend/tests/test_oauth_routes.py \
        backend/.env.example .env.example
git commit -m "feat(auth): « Continuer avec Google / Microsoft »

Server-side authorization code with Authlib: state + PKCE + nonce,
prompt=select_account, Microsoft on the common tenant with its issuer
checked against the token's own tid and the audience checked for both.
Every way out of the callback is a redirect. A provider stays hidden
until both its keys are set.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: nginx — the new endpoints under the auth rate limits

**Files:**
- Modify: `nginx/dev.conf`
- Modify: `nginx/templates-http/default.conf.template`
- Modify: `nginx/templates-https/default.conf.template`

**Interfaces:**
- Consumes: the endpoint paths from Tasks 6–8.
- Produces:
  - `auth_mail` (5 r/m, burst 3) also covers `auth/email-link`.
  - `auth_login` (10 r/m, burst 5) also covers `auth/email-link/(check|consume)` and `auth/signup`.
  - A new `auth_oauth` zone (30 r/m, burst 10) covers `auth/(google|microsoft)/(start|callback)`.

Make the same four edits in each of the three files. The anchors below are identical in all three.

- [ ] **Step 1: The comment**

Replace:

```
# Per-IP limits on the auth endpoints (email verification spec, decision 21).
```

with:

```
# Per-IP limits on the auth endpoints (email verification spec, decision 21;
# social sign-in spec, decision 23).
```

- [ ] **Step 2: Widen the two maps**

Replace:

```
    ~^/api/(auth/(register|resend-verification|forgot-password)|counselor/apply)/?$  $binary_remote_addr;
```

with:

```
    ~^/api/(auth/(register|resend-verification|forgot-password|email-link)|counselor/apply)/?$  $binary_remote_addr;
```

Replace:

```
    ~^/api/auth/(login|verify-email|reset-password)/?$  $binary_remote_addr;
```

with:

```
    ~^/api/auth/(login|verify-email|reset-password|email-link/(check|consume)|signup)/?$  $binary_remote_addr;
```

- [ ] **Step 3: The OAuth zone**

Replace:

```
limit_req_zone $auth_login_key zone=auth_login:10m rate=10r/m;
```

with:

```
limit_req_zone $auth_login_key zone=auth_login:10m rate=10r/m;
# Looser for the OAuth round trip: each provider sign-in costs two requests
# (start, callback), a France Travail workshop puts a whole room behind one
# address, and neither endpoint checks a secret anyone could guess.
map $uri $auth_oauth_key {
    ~^/api/auth/(google|microsoft)/(start|callback)/?$  $binary_remote_addr;
    default "";
}
limit_req_zone $auth_oauth_key zone=auth_oauth:10m rate=30r/m;
```

- [ ] **Step 4: Apply the zone in `location /api/`**

Replace:

```
        limit_req zone=auth_login burst=5 nodelay;
```

with:

```
        limit_req zone=auth_login burst=5 nodelay;
        limit_req zone=auth_oauth burst=10 nodelay;
```

- [ ] **Step 5: Check that the three files agree**

Run: `grep -c "auth_oauth" nginx/dev.conf nginx/templates-http/default.conf.template nginx/templates-https/default.conf.template`
Expected: `3` for each file (the map, the zone, the `limit_req` line).

- [ ] **Step 6: Both production templates pass `nginx -t`**

From the repo root:

```bash
S=$(mktemp -d)
openssl req -x509 -nodes -newkey rsa:2048 -days 1 -subj "/CN=neoori.test" \
  -keyout "$S/privkey.pem" -out "$S/fullchain.pem" 2>/dev/null
for mode in http https; do
  docker run --rm -e DOMAIN=neoori.test \
    --add-host backend:127.0.0.1 --add-host frontend:127.0.0.1 \
    -v "$PWD/nginx/templates-$mode:/etc/nginx/templates:ro" \
    -v "$S:/etc/letsencrypt/live/neoori.test:ro" \
    nginx:1.29-alpine sh -c '/docker-entrypoint.d/20-envsubst-on-templates.sh >/dev/null && nginx -t'
done
```

Expected: twice, `nginx: the configuration file /etc/nginx/nginx.conf syntax is ok` and `nginx: configuration file /etc/nginx/nginx.conf test is successful`.

- [ ] **Step 7: The dev stack applies it and limits each zone**

Run these from the repo root. If anything hit these endpoints in the last minute, wait a minute first.

```bash
docker compose up -d
docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload
for i in $(seq 1 13); do curl -s -o /dev/null -w "%{http_code} " http://localhost:8080/api/auth/google/start; done; echo
for i in $(seq 1 6); do curl -s -o /dev/null -w "%{http_code} " -H 'Content-Type: application/json' -d '{"email":"x"}' http://localhost:8080/api/auth/email-link; done; echo
for i in $(seq 1 8); do curl -s -o /dev/null -w "%{http_code} " -H 'Content-Type: application/json' -d '{"token":"x"}' http://localhost:8080/api/auth/email-link/consume; done; echo
for i in $(seq 1 20); do curl -s -o /dev/null -w "%{http_code} " http://localhost:8080/api/auth/providers; done; echo
```

Expected:
- `/start`: eleven `302` (a redirect to `/connexion?erreur=indisponible`, since there are no keys locally), then `429 429`.
- `email-link`: four `400`, then `429 429`.
- `consume`: six `400`, then `429 429`.
- `providers`: twenty `200`. It is not limited.

- [ ] **Step 8: Commit**

```bash
git add nginx/dev.conf nginx/templates-http/default.conf.template nginx/templates-https/default.conf.template
git commit -m "feat(nginx): rate-limit the social sign-in endpoints

The link request joins auth_mail; link check/consume and signup join
auth_login. A looser auth_oauth zone (30 r/m, burst 10) covers start
and callback, so a workshop behind one address is not turned away.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Frontend — the sign-in options on `/connexion` and `/inscription`

**Files:**
- Modify: `frontend/src/lib/api.ts` (add `apiHref`)
- Create: `frontend/src/lib/useCooldown.ts`
- Modify: `frontend/src/components/auth/VerificationPending.tsx` (uses `useCooldown`)
- Create: `frontend/src/components/auth/ProviderLogos.tsx`
- Create: `frontend/src/components/auth/EmailLinkForm.tsx`
- Create: `frontend/src/components/auth/SocialSignIn.tsx`
- Modify: `frontend/src/app/(auth)/connexion/page.tsx`
- Modify: `frontend/src/app/(auth)/inscription/page.tsx`

**Interfaces:**
- Consumes: `GET /api/auth/providers`, `POST /api/auth/email-link`, `GET /api/auth/<provider>/start` (Tasks 6 and 8).
- Produces:
  - `apiHref(path: string): string`
  - `useCooldown(running: boolean): { wait: number; restart: () => void }`, `COOLDOWN_S = 60`
  - `<EmailLinkForm next? submitLabel? />`
  - `<SocialSignIn next: string | null separator: string />`
  - `GoogleLogo`, `MicrosoftLogo`

Before writing: read `frontend/node_modules/next/dist/docs/01-app/03-api-reference/04-functions/use-search-params.md`.

- [ ] **Step 1: `apiHref`**

In `frontend/src/lib/api.ts`, after the line `type ApiOptions = RequestInit & { skipRedirect?: boolean }`, add:

```ts
/** A same-origin URL for a full-page navigation to the API — the OAuth start,
 *  which must leave the app for the provider's page, as fetch() cannot. */
export function apiHref(path: string): string {
  return `${BASE}/api${path}`
}
```

- [ ] **Step 2: `useCooldown`**

Create `frontend/src/lib/useCooldown.ts`:

```ts
"use client"

import { useEffect, useState } from "react"

/** Mirrors auth_mail.COOLDOWN on the server: one account mail a minute. */
export const COOLDOWN_S = 60

/** The « Renvoyer » countdown every account-mail screen shows: seconds left
 *  before another mail may be asked for. restart() starts a new minute. */
export function useCooldown(running: boolean) {
  const [wait, setWait] = useState(running ? COOLDOWN_S : 0)

  useEffect(() => {
    if (wait <= 0) return
    const t = setTimeout(() => setWait((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [wait])

  return { wait, restart: () => setWait(COOLDOWN_S) }
}
```

- [ ] **Step 3: `VerificationPending` uses it**

In `frontend/src/components/auth/VerificationPending.tsx`, replace:

```tsx
import { useEffect, useState } from "react"
import { api, ApiError } from "@/lib/api"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

/** Mirrors auth_mail.COOLDOWN on the server: one account mail a minute. */
const COOLDOWN_S = 60
```

with:

```tsx
import { useState } from "react"
import { api, ApiError } from "@/lib/api"
import { useCooldown } from "@/lib/useCooldown"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
```

Replace:

```tsx
  const [wait, setWait] = useState(justSent ? COOLDOWN_S : 0)
```

with:

```tsx
  const { wait, restart } = useCooldown(justSent)
```

Delete this block and the blank line after it:

```tsx
  useEffect(() => {
    if (wait <= 0) return
    const t = setTimeout(() => setWait((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [wait])
```

Replace `      setWait(COOLDOWN_S)` with `      restart()`.

- [ ] **Step 4: The provider marks**

Create `frontend/src/components/auth/ProviderLogos.tsx`:

```tsx
/** Each provider's mark as its brand guidelines draw it: the four-colour G,
 *  the four squares. Inline SVG, so nothing is fetched from a provider's
 *  server before the person clicks. */
export function GoogleLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className={className}>
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  )
}

export function MicrosoftLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 21 21" aria-hidden="true" className={className}>
      <rect x="1" y="1" width="9" height="9" fill="#F25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
      <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
      <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
    </svg>
  )
}
```

- [ ] **Step 5: The email-link form**

Create `frontend/src/components/auth/EmailLinkForm.tsx`:

```tsx
"use client"

import { useState, type FormEvent } from "react"
import { api, ApiError } from "@/lib/api"
import { useCooldown } from "@/lib/useCooldown"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"

interface Props {
  /** Where the link should land, when the page knows. Sent as given. */
  next?: string | null
  submitLabel?: string
}

/** « Recevoir un lien de connexion »: an address, then the sent state with
 *  « Renvoyer » on the server's one-a-minute clock (social sign-in spec,
 *  decision 14). The server sends whether or not the address has an
 *  account, so this screen can say plainly that a link left. */
export function EmailLinkForm({ next = null, submitLabel = "Envoyer le lien" }: Props) {
  const [email, setEmail] = useState("")
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const { wait, restart } = useCooldown(false)

  const send = async (to: string) => {
    setError(null)
    setSending(true)
    try {
      const res = await api.post<{ mail_sent: boolean }>(
        "/auth/email-link", { email: to, next: next ?? undefined }, { skipRedirect: true },
      )
      setSentTo(to)
      setFailed(!res.mail_sent)
      if (res.mail_sent) restart()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur lors de l’envoi.")
    } finally {
      setSending(false)
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    send(email.trim())
  }

  if (sentTo) {
    return (
      <div className="space-y-4">
        {failed ? (
          <Alert variant="destructive">
            <AlertDescription>L’envoi a échoué. Réessayez dans un instant.</AlertDescription>
          </Alert>
        ) : (
          <p className="text-sm text-muted-foreground">
            Un lien de connexion a été envoyé à <strong className="text-navy">{sentTo}</strong>.
            Il est valable 15 minutes. Pensez à regarder dans les courriers indésirables.
          </p>
        )}
        {error && (
          <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
        )}
        <Button
          type="button"
          variant="outline"
          className="h-11 w-full"
          disabled={wait > 0 || sending}
          onClick={() => send(sentTo)}
        >
          {sending ? "Envoi…" : wait > 0 ? `Renvoyer le lien (${wait} s)` : "Renvoyer le lien"}
        </Button>
        <button
          type="button"
          onClick={() => { setSentTo(null); setFailed(false); setError(null) }}
          className="link-underline block w-full text-center text-sm font-medium text-orange-dark"
        >
          Changer d’adresse
        </button>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      {error && (
        <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="link-email">Email</Label>
        <Input
          id="link-email" type="email" autoComplete="email" className="h-10"
          placeholder="vous@exemple.fr" required
          value={email} onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <Button type="submit" size="lg" className="h-11 w-full" disabled={sending}>
        {sending ? "Envoi…" : submitLabel}
      </Button>
    </form>
  )
}
```

- [ ] **Step 6: The block both pages show**

Create `frontend/src/components/auth/SocialSignIn.tsx`:

```tsx
"use client"

import { useEffect, useState } from "react"
import { Mail } from "lucide-react"
import { api, apiHref } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Button, buttonVariants } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { EmailLinkForm } from "@/components/auth/EmailLinkForm"
import { GoogleLogo, MicrosoftLogo } from "@/components/auth/ProviderLogos"

type Providers = { google: boolean; microsoft: boolean }

const PROVIDERS = [
  { id: "google", label: "Continuer avec Google", Logo: GoogleLogo },
  { id: "microsoft", label: "Continuer avec Microsoft", Logo: MicrosoftLogo },
] as const

interface Props {
  /** The page's ?redirect=, already checked by safeRedirect. */
  next: string | null
  /** Under the options: « ou » on /connexion, « ou avec un mot de passe » on /inscription. */
  separator: string
}

/** The password-less ways in (social sign-in spec). A provider button is a
 *  plain link to the server, which runs the whole OAuth round trip — no
 *  provider script ever loads here. It shows only once the server says
 *  that provider's keys are set. */
export function SocialSignIn({ next, separator }: Props) {
  const [providers, setProviders] = useState<Providers>({ google: false, microsoft: false })
  const [linkOpen, setLinkOpen] = useState(false)

  useEffect(() => {
    let live = true
    api.get<Providers>("/auth/providers", { skipRedirect: true })
      .then((p) => { if (live) setProviders(p) })
      // No provider buttons then: the email link and the password still work.
      .catch(() => {})
    return () => { live = false }
  }, [])

  const startHref = (id: string) =>
    apiHref(`/auth/${id}/start${next ? `?next=${encodeURIComponent(next)}` : ""}`)

  return (
    <div className="mt-7">
      <div className="space-y-2.5">
        {PROVIDERS.filter((p) => providers[p.id]).map(({ id, label, Logo }) => (
          <a
            key={id}
            href={startHref(id)}
            className={cn(buttonVariants({ variant: "outline" }), "h-11 w-full gap-2.5 text-[0.95rem]")}
          >
            <Logo className="size-5" /> {label}
          </a>
        ))}
        {linkOpen ? (
          <EmailLinkForm next={next} />
        ) : (
          <Button
            type="button"
            variant="outline"
            className="h-11 w-full gap-2.5 text-[0.95rem]"
            onClick={() => setLinkOpen(true)}
          >
            <Mail className="size-5" /> Recevoir un lien de connexion
          </Button>
        )}
      </div>
      <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground">
        <Separator className="flex-1" />
        <span>{separator}</span>
        <Separator className="flex-1" />
      </div>
    </div>
  )
}
```

- [ ] **Step 7: `/connexion` shows it and turns `?erreur=` into a sentence**

In `frontend/src/app/(auth)/connexion/page.tsx`, after the line `import { VerificationPending } from "@/components/auth/VerificationPending"`, add:

```tsx
import { SocialSignIn } from "@/components/auth/SocialSignIn"
```

After the line `type Fields = z.infer<typeof schema>`, add:

```tsx

/** What /api/auth/<provider>/callback reports when it sends someone back
 *  here (social sign-in spec, decision 12). A Map, not an object literal:
 *  "?erreur=constructor" must find nothing. */
const OAUTH_ERRORS = new Map([
  ["annule", "Connexion annulée."],
  ["echec", "La connexion n’a pas abouti. Réessayez, ou utilisez « Recevoir un lien de connexion »."],
  ["indisponible", "Ce mode de connexion n’est pas disponible pour le moment."],
  ["email_non_verifie", "Ce compte ne confirme pas votre adresse email. Utilisez « Recevoir un lien de connexion »."],
])
```

After the line `  const redirect = safeRedirect(params.get("redirect"))`, add:

```tsx
  const oauthError = OAUTH_ERRORS.get(params.get("erreur") ?? "") ?? null
```

Replace:

```tsx
      <p className="mt-1.5 text-sm text-muted-foreground">Retrouvez vos analyses, votre profil et votre voyage.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
```

with:

```tsx
      <p className="mt-1.5 text-sm text-muted-foreground">Retrouvez vos analyses, votre profil et votre voyage.</p>

      {oauthError && (
        <Alert variant="destructive" className="mt-6">
          <AlertDescription>{oauthError}</AlertDescription>
        </Alert>
      )}

      <SocialSignIn next={redirect} separator="ou" />

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
```

- [ ] **Step 8: `/inscription` shows it**

In `frontend/src/app/(auth)/inscription/page.tsx`, after the line `import { VerificationPending } from "@/components/auth/VerificationPending"`, add:

```tsx
import { SocialSignIn } from "@/components/auth/SocialSignIn"
```

Replace:

```tsx
      <p className="mt-1.5 text-sm text-muted-foreground">Gratuit · 1 analyse offerte.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
```

with:

```tsx
      <p className="mt-1.5 text-sm text-muted-foreground">Gratuit · 1 analyse offerte.</p>

      <SocialSignIn next={next} separator="ou avec un mot de passe" />

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
```

- [ ] **Step 9: Type check, lint, build**

From `frontend/`:

```bash
npx tsc --noEmit
npx eslint src/lib/api.ts src/lib/useCooldown.ts src/components/auth \
  "src/app/(auth)/connexion/page.tsx" "src/app/(auth)/inscription/page.tsx"
npm run build
```

Expected: `tsc` prints nothing; ESLint reports no problems; the build succeeds and lists `/connexion` and `/inscription`.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/useCooldown.ts frontend/src/components/auth \
        "frontend/src/app/(auth)/connexion/page.tsx" "frontend/src/app/(auth)/inscription/page.tsx"
git commit -m "feat(frontend): sign-in options on /connexion and /inscription

Provider buttons are plain links to the server and appear only when it
says their keys are set; « Recevoir un lien de connexion » opens an
inline form on the server's one-a-minute clock. /connexion turns the
callback's ?erreur= into a French sentence.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Frontend — `/connexion/lien`, where the link lands

**Files:**
- Create: `frontend/src/app/(auth)/connexion/lien/page.tsx`

**Interfaces:**
- Consumes: `POST /api/auth/email-link/check`, `POST /api/auth/email-link/consume` (Task 6); `<EmailLinkForm>` (Task 10); `useAuth().refresh`, `homeFor`.
- Produces: the page at `/connexion/lien?token=…`.

- [ ] **Step 1: Write the page**

Create `frontend/src/app/(auth)/connexion/lien/page.tsx`:

```tsx
"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { useAuth } from "@/lib/auth"
import { homeFor } from "@/lib/home"
import { api, ApiError } from "@/lib/api"
import type { User } from "@/types"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"
import { EmailLinkForm } from "@/components/auth/EmailLinkForm"

const INVALID = "Ce lien n’est pas valide. Demandez-en un nouveau."

type LinkState =
  | { kind: "checking" }
  | { kind: "ready"; email: string }
  | { kind: "dead"; message: string }
  /** The check itself failed (429, a 5xx, the network): nothing is known
   *  about the link, so it is not called dead. */
  | { kind: "unchecked"; message: string }

type Consumed = { user: User; next: string | null } | { signup: true }

/** Where « Recevoir un lien de connexion » lands. Opening the page spends
 *  nothing — mail scanners open links, and some run scripts. Only the click
 *  on « Continuer » uses the link (social sign-in spec, decision 16), and the
 *  address shown says whose account it opens. */
function ConnexionLien() {
  const params = useSearchParams()
  const router = useRouter()
  const { refresh } = useAuth()
  const token = params.get("token") ?? ""
  const [state, setState] = useState<LinkState>(() =>
    token ? { kind: "checking" } : { kind: "dead", message: INVALID },
  )
  const [attempt, setAttempt] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!token) return
    let live = true
    api.post<{ email: string }>("/auth/email-link/check", { token }, { skipRedirect: true })
      .then((r) => { if (live) setState({ kind: "ready", email: r.email }) })
      .catch((e) => {
        if (!live) return
        const code = e instanceof ApiError ? e.body?.code : undefined
        if (e instanceof ApiError && e.status === 400 && typeof code === "string" && code.startsWith("link_")) {
          setState({ kind: "dead", message: e.message })
        } else {
          setState({
            kind: "unchecked",
            message: e instanceof ApiError ? e.message : "Vérification du lien impossible pour le moment.",
          })
        }
      })
    return () => { live = false }
  }, [token, attempt])

  const recheck = () => {
    setState({ kind: "checking" })
    setAttempt((n) => n + 1)
  }

  const proceed = async () => {
    setError(null)
    setSubmitting(true)
    try {
      const res = await api.post<Consumed>("/auth/email-link/consume", { token }, { skipRedirect: true })
      // replace, not push: Back must not reopen the spent link.
      if ("signup" in res) {
        router.replace("/inscription/finaliser")
        return
      }
      await refresh()
      router.replace(res.next ?? homeFor(res.user.role))
    } catch (err) {
      const code = err instanceof ApiError ? err.body?.code : undefined
      if (code === "link_expired" || code === "link_invalid") {
        setState({ kind: "dead", message: (err as ApiError).message })
      } else {
        setError(err instanceof ApiError ? err.message : "Erreur inattendue.")
      }
      setSubmitting(false)
    }
  }

  if (state.kind === "checking") {
    return <p className="text-sm text-muted-foreground">Vérification du lien…</p>
  }

  if (state.kind === "unchecked") {
    return (
      <>
        <h1 className="font-display text-2xl font-bold text-navy">Connexion</h1>
        <Alert variant="destructive" className="mt-6"><AlertDescription>{state.message}</AlertDescription></Alert>
        <Button type="button" size="lg" className="mt-6 h-11 w-full" onClick={recheck}>
          Réessayer
        </Button>
      </>
    )
  }

  if (state.kind === "dead") {
    return (
      <>
        <h1 className="font-display text-2xl font-bold text-navy">Lien expiré ou invalide</h1>
        <Alert variant="destructive" className="mt-6"><AlertDescription>{state.message}</AlertDescription></Alert>
        <div className="mt-6">
          <EmailLinkForm submitLabel="Recevoir un nouveau lien" />
        </div>
        <p className="mt-5 text-center text-sm text-muted-foreground">
          <Link href="/connexion" className="link-underline font-medium text-orange-dark">Retour à la connexion</Link>
        </p>
      </>
    )
  }

  return (
    <>
      <h1 className="font-display text-2xl font-bold text-navy">Connexion</h1>
      <p className="mt-3 text-sm text-muted-foreground">
        Connexion avec <strong className="text-navy">{state.email}</strong>.
      </p>
      {error && (
        <Alert variant="destructive" className="mt-6"><AlertDescription>{error}</AlertDescription></Alert>
      )}
      <Button type="button" size="lg" className="mt-6 h-11 w-full" disabled={submitting} onClick={proceed}>
        {submitting ? "Connexion…" : "Continuer"}
      </Button>
      <p className="mt-4 text-center text-xs text-muted-foreground">
        Ce n’est pas votre adresse ? Fermez cette page.
      </p>
    </>
  )
}

export default function ConnexionLienPage() {
  return (
    <AuthLayout>
      <Suspense>
        <ConnexionLien />
      </Suspense>
    </AuthLayout>
  )
}
```

- [ ] **Step 2: Type check, lint, build**

From `frontend/`:

```bash
npx tsc --noEmit
npx eslint "src/app/(auth)/connexion/lien/page.tsx"
npm run build
```

Expected: no type errors; no lint problems; the build lists `/connexion/lien`.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(auth)/connexion/lien/page.tsx"
git commit -m "feat(frontend): /connexion/lien, where the sign-in link lands

Checks the link on load, spends it only on « Continuer » (mail
scanners), and goes on to the account or to « Finaliser votre
inscription ». A dead link offers a new one in place.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Frontend — `/inscription/finaliser`

**Files:**
- Create: `frontend/src/app/(auth)/inscription/finaliser/page.tsx`

**Interfaces:**
- Consumes: `GET /api/auth/signup`, `POST /api/auth/signup` (Task 7); `TRANCHES_AGE`; `useAuth().refresh`, `homeFor`.
- Produces: the page at `/inscription/finaliser`.

- [ ] **Step 1: Write the page**

Create `frontend/src/app/(auth)/inscription/finaliser/page.tsx`:

```tsx
"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Controller, useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useAuth } from "@/lib/auth"
import { homeFor } from "@/lib/home"
import { api, ApiError } from "@/lib/api"
import { TRANCHES_AGE } from "@/lib/profile-options"
import type { User } from "@/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"

/** profiles.prenom's width (PRENOM_MAX_LENGTH on the server). */
const PRENOM_MAX = 120

const schema = z.object({
  prenom: z.string().trim().min(1, "Prénom requis.").max(PRENOM_MAX, `${PRENOM_MAX} caractères maximum.`),
  tranche_age: z.string().min(1, "Tranche d'âge requise."),
  consent: z.boolean().refine((v) => v === true, {
    message: "Veuillez accepter les CGV et la politique de confidentialité.",
  }),
})
type Fields = z.infer<typeof schema>

type Ticket =
  | { kind: "loading" }
  | { kind: "ready"; email: string }
  | { kind: "expired" }
  | { kind: "unchecked"; message: string }

/** The last step of a signup by Google, Microsoft or the email link. The
 *  address is already proven, so only the prénom, the age bracket and the
 *  consent are asked; the account is created on submit, not before (social
 *  sign-in spec, decisions 1 and 22). */
export default function FinaliserPage() {
  const router = useRouter()
  const { refresh } = useAuth()
  const [ticket, setTicket] = useState<Ticket>({ kind: "loading" })
  const [attempt, setAttempt] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const { register, control, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { prenom: "", tranche_age: "", consent: false },
  })

  useEffect(() => {
    let live = true
    api.get<{ email: string; prenom: string }>("/auth/signup", { skipRedirect: true })
      .then((t) => {
        if (!live) return
        reset({ prenom: t.prenom, tranche_age: "", consent: false })
        setTicket({ kind: "ready", email: t.email })
      })
      .catch((e) => {
        if (!live) return
        const code = e instanceof ApiError ? e.body?.code : undefined
        if (typeof code === "string" && code.startsWith("link_")) setTicket({ kind: "expired" })
        else setTicket({ kind: "unchecked", message: e instanceof ApiError ? e.message : "Chargement impossible pour le moment." })
      })
    return () => { live = false }
  }, [attempt, reset])

  const onSubmit = async (fields: Fields) => {
    setError(null)
    try {
      const res = await api.post<{ user: User; next: string | null }>("/auth/signup", fields, { skipRedirect: true })
      await refresh()
      router.replace(res.next ?? homeFor(res.user.role))
    } catch (e) {
      const code = e instanceof ApiError ? e.body?.code : undefined
      if (typeof code === "string" && code.startsWith("link_")) setTicket({ kind: "expired" })
      else setError(e instanceof ApiError ? e.message : "Erreur lors de la création du compte.")
    }
  }

  if (ticket.kind === "loading") {
    return <AuthLayout><p className="text-sm text-muted-foreground">Chargement…</p></AuthLayout>
  }

  if (ticket.kind === "unchecked") {
    return (
      <AuthLayout>
        <h1 className="font-display text-2xl font-bold text-navy">Finaliser votre inscription</h1>
        <Alert variant="destructive" className="mt-6"><AlertDescription>{ticket.message}</AlertDescription></Alert>
        <Button type="button" size="lg" className="mt-6 h-11 w-full"
          onClick={() => { setTicket({ kind: "loading" }); setAttempt((n) => n + 1) }}>
          Réessayer
        </Button>
      </AuthLayout>
    )
  }

  if (ticket.kind === "expired") {
    return (
      <AuthLayout>
        <h1 className="font-display text-2xl font-bold text-navy">Finaliser votre inscription</h1>
        <Alert variant="destructive" className="mt-6">
          <AlertDescription>Cette étape a expiré. Recommencez depuis la page d’inscription.</AlertDescription>
        </Alert>
        <p className="mt-5 text-center text-sm text-muted-foreground">
          <Link href="/inscription" className="link-underline font-medium text-orange-dark">Retour à l’inscription</Link>
        </p>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-bold text-navy">Finaliser votre inscription</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Dernière étape : ces informations servent à personnaliser vos analyses.
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
        {error && (
          <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="username" className="h-10" value={ticket.email} readOnly />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="prenom">Prénom</Label>
            <Input id="prenom" autoComplete="given-name" className="h-10" placeholder="Marie" {...register("prenom")} />
            {errors.prenom && <p className="text-xs text-destructive">{errors.prenom.message}</p>}
          </div>

          <div className="space-y-1.5">
            <Label>Tranche d&apos;âge</Label>
            <Controller
              name="tranche_age"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger className="h-10 w-full"><SelectValue placeholder="Choisir…" /></SelectTrigger>
                  <SelectContent>
                    {TRANCHES_AGE.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.tranche_age && <p className="text-xs text-destructive">{errors.tranche_age.message}</p>}
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="flex items-start gap-2.5 text-xs leading-relaxed text-muted-foreground">
            <input
              type="checkbox"
              className="mt-0.5 size-4 shrink-0 rounded border-input accent-[var(--primary)]"
              {...register("consent")}
            />
            <span>
              J’accepte les{" "}
              <Link href="/cgv" target="_blank" className="text-navy underline underline-offset-2">CGV</Link>{" "}
              et la{" "}
              <Link href="/confidentialite" target="_blank" className="text-navy underline underline-offset-2">politique de confidentialité</Link>.
            </span>
          </label>
          {errors.consent && <p className="text-xs text-destructive">{errors.consent.message}</p>}
        </div>

        <Button type="submit" size="lg" className="h-11 w-full" disabled={isSubmitting}>
          {isSubmitting ? "Création…" : "Créer mon compte"}
        </Button>
      </form>
    </AuthLayout>
  )
}
```

- [ ] **Step 2: Type check, lint, build**

From `frontend/`:

```bash
npx tsc --noEmit
npx eslint "src/app/(auth)/inscription/finaliser/page.tsx"
npm run build
```

Expected: no type errors; no lint problems; the build lists `/inscription/finaliser`.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(auth)/inscription/finaliser/page.tsx"
git commit -m "feat(frontend): « Finaliser votre inscription »

Prénom prefilled from the provider, the age bracket and the CGV
consent: the account is created on submit, not before. An expired
ticket sends the person back to /inscription.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Docs — CLAUDE.md and DOCKER.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `DOCKER.md`

**Interfaces:**
- Consumes: the behaviour of Tasks 2–12.
- Produces: the rules a later change could undo, written where the next session reads them.

- [ ] **Step 1: CLAUDE.md — the new section**

In `CLAUDE.md`, immediately before the line `## Mails transactionnels`, add:

```markdown
## Connexion Google / Microsoft / lien

Three password-less ways in, beside the password signup: « Continuer avec
Google », « Continuer avec Microsoft » and « Recevoir un lien de connexion ».
All three end in `routes/auth._issue_session()`.

- **No provider script on our pages.** A provider button is a plain link to
  `/api/auth/<provider>/start`. Flask runs the authorization-code round trip
  with Authlib (`services/oauth_clients.py`, `routes/auth_oauth.py`). The
  checks are state + PKCE + nonce, and on the ID token `iss`, `aud` and `exp`.
  One Tap or a hosted widget would bring a CNIL consent banner with it.
- **No `users` row before the CGV consent.** An unknown identity, or a link
  for an address with no account, gets a signed `signup_ticket` cookie (30
  min, `Path=/api/auth`) and lands on `/inscription/finaliser`. The account,
  its identity and its consent are created there in one commit. Nothing needs
  a consent gate because nothing exists before it.
- **An address is believed only when the provider proves it**
  (`services/sign_in.trusted_email`). Google: `email_verified`. Microsoft: the
  personal-account tenant, or `xms_edov`. A work tenant's `email` claim can be
  any address its admin types (nOAuth). Without proof a sign-in enters nothing
  and creates nothing. `xms_edov` is added in the Entra app's manifest; the
  portal no longer lists it.
- **Entering an unverified account replaces its password** with an unusable
  hash, since a stranger may have set it. Password-less accounts carry such a
  hash too: every typed password fails like a wrong one, and « Mot de passe
  oublié » sets a real one.
- **The email link is spent by a click, never by opening the page.** Mail
  scanners open links. `/connexion/lien` checks the token on load and consumes
  it only on « Continuer ». `login_links` makes it single-use and keeps an
  HMAC of the address, never the address.
- **Keys.** `GOOGLE_CLIENT_ID/SECRET` and `MICROSOFT_CLIENT_ID/SECRET` live in
  `/srv/neoori/.env`. A provider's button shows only once both its keys are
  set (`GET /api/auth/providers`). The Microsoft secret expires: see DOCKER.md,
  « Google / Microsoft sign-in keys ».

Spec: `docs/superpowers/specs/2026-10-03-social-login-design.md`

```

- [ ] **Step 2: CLAUDE.md — the mails table**

In the « Mails transactionnels » table, after the row starting `| Réinitialiser votre mot de passe |`, add:

```markdown
| Votre lien de connexion | the address typed, account or not | « Recevoir un lien de connexion » — `services/auth_mail.login_link_if_due` |
```

- [ ] **Step 3: DOCKER.md — keys and renewal**

In `DOCKER.md`, immediately before the line `## Data migration (TiDB Cloud → VPS MySQL, at cutover)`, add:

````markdown
## Google / Microsoft sign-in keys

Four keys in `/srv/neoori/.env` (and `backend/.env` locally) configure the
two providers: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
`MICROSOFT_CLIENT_ID` and `MICROSOFT_CLIENT_SECRET`. Creating the two apps,
click by click, is in
`docs/superpowers/specs/2026-10-03-social-login-design.md`, appendices A and
B. A provider's button appears only once both its keys are set. After
editing `.env`:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate backend
```

### Microsoft secret renewal

A Microsoft client secret lives 24 months at most. The day it expires,
« Continuer avec Microsoft » answers « La connexion n'a pas abouti ». Its
expiry date is the comment beside `MICROSOFT_CLIENT_SECRET` in
`/srv/neoori/.env`. A month before it:

1. In Entra, open the `neoori` app → Certificates & secrets → New client
   secret (24 months). The old one keeps working meanwhile.
2. Paste the new **Value** into `/srv/neoori/.env` and update the expiry
   comment.
3. Recreate the backend (command above), then sign in once with Microsoft.
4. Delete the old secret in Entra.

````

- [ ] **Step 4: Check nothing else in CLAUDE.md contradicts it**

Run: `grep -n "_issue_session\|account mails\|NextAuth" CLAUDE.md`
Expected:
- `_issue_session` is still described as the only place a session opens. That remains true.
- The NextAuth stack line is unchanged. Out of scope here; the brief says not to touch it.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md DOCKER.md
git commit -m "docs: social sign-in rules and the Microsoft secret runbook

CLAUDE.md records what a later change could undo (no account before
consent, trust rules, click-to-consume). DOCKER.md says where the keys
live and how to renew the expiring Microsoft secret.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: End to end on the local stack

**Files:** none changed; verification only. Fix anything it finds in the owning task's files, with a test, and its own commit.

**Interfaces:**
- Consumes: everything above.
- Produces: evidence that the flows work through nginx, Flask, MySQL and the pages.

- [ ] **Step 1: Stack up, health, providers**

```bash
docker compose build backend && docker compose up -d
curl -s http://localhost:8080/api/health
curl -s http://localhost:8080/api/auth/providers
```

Expected:
- `{"status":"ok"}`
- `{"google":false,"microsoft":false}`, unless `backend/.env` already carries keys.

- [ ] **Step 2: The email-link signup, through nginx, with curl**

```bash
J=$(mktemp); E="e2e-$(date +%s)@test.fr"; H='Content-Type: application/json'
curl -s -c $J -b $J -H "$H" -d "{\"email\":\"$E\",\"next\":\"/analyse/nouveau\"}" http://localhost:8080/api/auth/email-link; echo
T=$(docker compose logs backend --since 2m | grep -o 'connexion/lien?token=[A-Za-z0-9_.-]*' | tail -1 | cut -d= -f2)
curl -s -H "$H" -d "{\"token\":\"$T\"}" http://localhost:8080/api/auth/email-link/check; echo
curl -s -c $J -b $J -H "$H" -d "{\"token\":\"$T\"}" http://localhost:8080/api/auth/email-link/consume; echo
curl -s -c $J -b $J http://localhost:8080/api/auth/signup; echo
curl -s -c $J -b $J -H "$H" -d '{"prenom":"Test","tranche_age":"25_34","consent":true}' http://localhost:8080/api/auth/signup; echo
curl -s -b $J http://localhost:8080/api/auth/me; echo
curl -s -H "$H" -d "{\"token\":\"$T\"}" http://localhost:8080/api/auth/email-link/consume; echo
docker compose exec db mysql -uneoori -pneoori_dev neoori -e "SELECT email_hash, used_at FROM login_links ORDER BY created_at DESC LIMIT 1;"
```

Expected, line by line:
1. `{"mail_sent":true}`
2. `{"email":"e2e-…@test.fr"}`
3. `{"signup":true}`
4. `{"email":"e2e-…@test.fr","method":"email","prenom":""}`
5. `{"next":"/analyse/nouveau","user":{…,"email_verified":true,…}}`
6. The same user from `/me`.
7. `{"code":"link_invalid","error":"Ce lien n'est pas valide. Demandez-en un nouveau."}`
8. A 64-hex `email_hash`, and a `used_at`. No address in the table.

- [ ] **Step 3: The pages, in a browser**

Use the claude-in-chrome tools, or ask the developer to click through. Record what you saw.
1. **http://localhost:8080/connexion**: no provider buttons (no keys). « Recevoir un lien de connexion » opens the email field. Send to a new address; the sent state shows the address and « Renvoyer le lien (60 s) ».
2. **The link** from `docker compose logs backend`: the page shows « Connexion avec <address>. » and « Continuer ». Click it: `/inscription/finaliser` shows the address read-only. Fill the form and submit: you land on `/espace`, signed in.
3. **The same link again**: « Lien expiré ou invalide », with the form « Recevoir un nouveau lien ».
4. **A second link to the same address**: « Continuer » signs straight in, with no finalise step.
5. **Error codes**: `/connexion?erreur=email_non_verifie` shows « Ce compte ne confirme pas votre adresse email. Utilisez « Recevoir un lien de connexion ». » `/connexion?erreur=constructor` shows no alert.
6. **/inscription** shows the same block, with « ou avec un mot de passe » above the password form.
7. **With provider keys.** If `backend/.env` carries Google or Microsoft dev keys (localhost redirect URIs registered), run `docker compose up -d --force-recreate backend`. Check the buttons appear, sign in with each, and check that a second sign-in goes straight in. If there are no keys yet, write "provider walk-through pending keys" in your report.

- [ ] **Step 4: Final checks**

```bash
cd backend && venv/bin/pytest -q -p no:cacheprovider && cd ../frontend && npx tsc --noEmit && npm run build
```

Expected: the backend suite has no failures, `tsc` is clean, and the build succeeds.

---

## After the implementation — developer and PM, not part of the run

1. **Privacy line.** It ships only after the PM approves the wording, and before step 2. The spec's draft: once approved, add to `frontend/src/app/(legal)/confidentialite/page.tsx`, in « 2. Données collectées », right after the `<li><strong>Compte</strong> : …</li>` item:

   ```tsx
           <li>
             <strong>Connexion avec Google ou Microsoft</strong> : si vous choisissez ce mode de
             connexion, Google ou Microsoft nous transmet votre adresse email, votre prénom et un
             identifiant de compte. Nous conservons l&apos;adresse et l&apos;identifiant, et le
             prénom seulement si vous le gardez à l&apos;inscription. Nous ne recevons ni votre
             mot de passe, ni l&apos;accès à vos emails, contacts ou fichiers. Ces données servent
             uniquement à vous connecter.
           </li>
   ```

2. **Keys.** The developer creates the Google client and the Entra app (spec appendices A and B), pastes the four keys into `/srv/neoori/.env` (with the Microsoft expiry comment) and `backend/.env`, then recreates the backend.
3. **Reminder.** With the Microsoft secret's creation date, Claude schedules a renewal reminder for a month before expiry.
4. **Push.** Only on the developer's word: pushing `initial` deploys.
