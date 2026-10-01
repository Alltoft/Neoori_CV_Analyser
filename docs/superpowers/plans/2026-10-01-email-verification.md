# Email Verification + Password Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** No session for an unproven email address, a « mot de passe oublié » flow on the same plumbing, analyses closed to anonymous visitors, and per-IP limits on the auth endpoints.

**Architecture:** Stateless signed links (`itsdangerous`, salted per purpose) carry the proof; two nullable columns on `users` hold the verified state and a one-mail-a-minute clock. One helper, `routes/auth._issue_session()`, is the only place cookies are minted and it refuses an unverified account, so the gate holds by construction. Mail goes through the existing fail-soft Resend `email_service`. nginx `limit_req` throttles the public endpoints, and the deploy finally reloads nginx so template changes apply.

**Tech Stack:** Flask 3.1 + Flask-JWT-Extended 4.7.1 (cookies) + Flask-Bcrypt, itsdangerous 2.2.0 (ships with Flask — no new dependency), Alembic hand-written migrations, MySQL 8.4 prod / SQLite tests, pytest. Next.js 16 App Router + React 19, react-hook-form + zod, Base UI components, Tailwind. Resend. nginx 1.29-alpine.

**Spec:** `docs/superpowers/specs/2026-09-29-email-verification-design.md` (approved 2026-09-29, amended 2026-10-01). Decision numbers below ("decision 8") refer to its Decisions table.

## Global Constraints

- App UI strings: **French**. Code comments and commit messages: **English**.
- UI copy never uses: boussole, copilote, miroir, révélation, épanouissement, alignement, excellence, talent unique, vous vous démarquez. Sober and direct.
- No new Python or npm dependency. `itsdangerous` is already installed with Flask.
- Verification link lifetime **48 h**, reset link **1 h**, mail cooldown **60 s** per account, password minimum **8** characters.
- Mail sender comes from `MAIL_FROM`; every link is built from `APP_URL`. Email sending is fail-soft: never raises, returns a bool.
- Migration: revision `a9b0c1d2e3f4`, `down_revision = 'f8a9b0c1d2e3'`, idempotent per the repo's convention (`entrypoint.sh` runs `flask db upgrade` at every container start).
- Backend tests: `cd backend && venv/bin/pytest -q`. Baseline before this plan: **977 passed**.
- Frontend checks: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`.
- Work on branch `feat/email-verification`. Stage files by explicit path (the repo root holds an untracked `DOC-20260725-WA0000..pdf` that must never be committed).
- **Never `git push`** — a push to `initial` deploys to production. The developer pushes, or says so explicitly.
- Every commit message ends with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

1. **Mixed-case or padded email** at resend / forgot (« ␣Marie@Test.FR ») must reach the same account as the lowercase one stored at signup. Pinned in Task 5.
2. **A link mangled by a mail client** (trailing `.`, `)`, `%29` glued to the token) must answer 400 `link_invalid` with a way to ask for a new one — never a 500, never a silent success. Pinned in Task 5.
3. **A password with surrounding spaces** chosen at signup must work at the verify page and after a reset — `raw_text_field`, never `text_field`, for every password. Pinned in Task 5.
4. **A query string on a gated page** (`/analyse/nouveau?parcours=2`) must survive proxy → signup → mail → verify. `safe_next` keeps queries (Task 2 test) and the proxy forwards `search` (Task 10).
5. **An account an admin marked verified** must then log in and keep a working refresh token (`pwv` minted at login). Pinned in Task 8.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/migrations/versions/a9b0c1d2e3f4_email_verification.py` (new) | Two columns on `users` + backfill of existing rows |
| `backend/app/models/user.py` | `email_verified_at`, `auth_mail_sent_at`, `to_dict()["email_verified"]` |
| `backend/app/utils/auth_links.py` (new) | Sign / load the two link kinds, `safe_next`, `password_fingerprint` |
| `backend/app/services/email_service.py` | `send(text=)`, `APP_URL`, footer, the two new mails, dev log |
| `backend/app/services/auth_mail.py` (new) | Cooldown + "send if due" for both mails, shared by auth and conseiller routes |
| `backend/app/routes/auth.py` | `_issue_session`, register/login/refresh gate, the five new endpoints |
| `backend/app/routes/counselor_space.py` | `apply()` mails a link instead of opening a session |
| `backend/app/routes/analyses.py`, `upload.py` | `@jwt_required()` on create + uploads |
| `backend/app/routes/admin.py` | manual verify, queue filter, approve guard |
| `backend/app/config.py` | `APP_URL`, test bcrypt rounds |
| `nginx/templates-http/…`, `nginx/templates-https/…`, `nginx/dev.conf` | `limit_req` maps + zones |
| `.github/workflows/deploy.yml` | Re-render + reload nginx after `up -d` |
| `frontend/src/components/auth/VerificationPending.tsx` (new) | « Vérifiez votre boîte mail » + resend countdown |
| `frontend/src/app/(auth)/verifier-email`, `mot-de-passe-oublie`, `reinitialiser-mot-de-passe` (new) | The three link landing pages |
| `frontend/src/lib/auth.tsx`, `proxy.ts`, `types/index.ts`, `lib/counselor.ts` | Client contract changes |
| `frontend/src/app/(auth)/inscription`, `connexion`, `inscription-conseiller` | Pending screen, 403 handling, links |
| `frontend/src/app/admin/utilisateurs/page.tsx` | « Adresse » column + manual verify button |

---

### Task 1: Data layer — columns, backfill, test fixtures

**Files:**
- Create: `backend/migrations/versions/a9b0c1d2e3f4_email_verification.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/config.py` (TestingConfig)
- Modify: `backend/seed_dev.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_email_verification_model.py` (new)

**Interfaces:**
- Produces: `User.email_verified_at: datetime | None`, `User.auth_mail_sent_at: datetime | None`, `User.to_dict()["email_verified"]: bool`; migration module function `backfill(bind) -> None`; pytest fixture `make_user(email="marie@test.fr", password="motdepasse1", verified=True, role="candidate") -> User` (real bcrypt hash).

- [ ] **Step 0: Create the branch**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git switch -c feat/email-verification
```

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_email_verification_model.py`:

```python
"""users carries whether its address is proven (email verification spec,
decisions 2 and 14).

The migration is loaded straight from its file and its backfill run on the
test database's own connection — there is no Alembic in the test run — the
same pattern as test_migration_erase_billets.py.
"""
import importlib.util
from datetime import datetime
from pathlib import Path

from app.extensions import db
from app.models.user import User

MIGRATION = (
    Path(__file__).resolve().parents[1] / "migrations" / "versions"
    / "a9b0c1d2e3f4_email_verification.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("email_verification", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_new_user_is_unverified(app):
    user = User(email="new@test.fr", password_hash="x")
    db.session.add(user)
    db.session.commit()
    assert user.email_verified_at is None
    assert user.auth_mail_sent_at is None
    assert user.to_dict()["email_verified"] is False


def test_to_dict_reports_a_verified_user(app):
    user = User(email="v@test.fr", password_hash="x", email_verified_at=datetime.utcnow())
    db.session.add(user)
    db.session.commit()
    assert user.to_dict()["email_verified"] is True


def test_backfill_marks_existing_accounts_verified_at_their_signup(app):
    signed_up = datetime(2026, 9, 1, 12, 0, 0)
    already = datetime(2026, 9, 20, 8, 0, 0)
    old = User(email="old@test.fr", password_hash="x", created_at=signed_up)
    done = User(email="done@test.fr", password_hash="x", email_verified_at=already)
    db.session.add_all([old, done])
    db.session.commit()

    _migration().backfill(db.session.connection())
    db.session.commit()
    db.session.expire_all()

    assert db.session.get(User, old.id).email_verified_at == signed_up
    assert db.session.get(User, done.id).email_verified_at == already


def test_make_user_builds_a_login_ready_account(make_user):
    from app.extensions import bcrypt

    user = make_user(email="fixture@test.fr", password="motdepasse1", verified=False)
    assert bcrypt.check_password_hash(user.password_hash, "motdepasse1")
    assert user.email_verified_at is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && venv/bin/pytest tests/test_email_verification_model.py -v`
Expected: FAIL — `TypeError: 'email_verified_at' is an invalid keyword argument for User` and `fixture 'make_user' not found`.

- [ ] **Step 3: Add the columns to the model**

In `backend/app/models/user.py`, after `created_at = ...` add:

```python
    # NULL until the address is proven by its link, a reset link or an admin
    # (email verification spec, decision 2). No session is issued before that.
    email_verified_at = db.Column(db.DateTime, nullable=True)
    # When the last account mail (verification or reset) left. One clock for
    # both, so neither endpoint can be pointed at an inbox to flood it.
    auth_mail_sent_at = db.Column(db.DateTime, nullable=True)
```

and in `to_dict()` add the key after `"credits_remaining"`:

```python
            "email_verified": self.email_verified_at is not None,
```

- [ ] **Step 4: Write the migration**

Create `backend/migrations/versions/a9b0c1d2e3f4_email_verification.py`:

```python
"""Email verification: two columns on users, existing accounts backfilled

email_verified_at is NULL until an address is proven; no session is issued
before that. auth_mail_sent_at paces the verification and reset mails.

Every account that exists when this runs is a test account (developer,
2026-09-29), so all of them are marked verified at their signup time rather
than locked out until someone clicks a link nobody will send.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-10-01
"""
import sqlalchemy as sa
from alembic import op


revision = 'a9b0c1d2e3f4'
down_revision = 'f8a9b0c1d2e3'
branch_labels = None
depends_on = None


COLUMNS = (
    ("email_verified_at", sa.DateTime()),
    ("auth_mail_sent_at", sa.DateTime()),
)


def _columns(bind) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns("users")}


def backfill(bind) -> None:
    """Existing accounts count as verified, at their own signup time."""
    bind.execute(sa.text(
        "UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL"
    ))


def upgrade():
    # Idempotent per this repo's convention: entrypoint.sh runs `db upgrade` at
    # container start, and a half-applied revision must not wedge the backend.
    bind = op.get_bind()
    have = _columns(bind)
    for name, type_ in COLUMNS:
        if name not in have:
            op.add_column("users", sa.Column(name, type_, nullable=True))
    backfill(bind)


def downgrade():
    have = _columns(op.get_bind())
    for name, _ in reversed(COLUMNS):
        if name in have:
            op.drop_column("users", name)
```

- [ ] **Step 5: Add the `make_user` fixture and fast test hashing**

In `backend/app/config.py`, inside `class TestingConfig`, add:

```python
    # Real bcrypt hashes in tests (login and verify-email check them), at the
    # cheapest cost: the default 12 rounds would add seconds per test.
    BCRYPT_LOG_ROUNDS = 4
```

In `backend/tests/conftest.py`, after the `admin_headers` fixture, add:

```python
@pytest.fixture
def make_user(app):
    """A User with a real bcrypt hash, so /login, /verify-email and
    /reset-password can check its password. Verified unless told otherwise."""
    from datetime import datetime

    from app.extensions import bcrypt

    def _make(email="marie@test.fr", password="motdepasse1", verified=True, role="candidate"):
        user = User(
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
            role=role,
            email_verified_at=datetime.utcnow() if verified else None,
        )
        _db.session.add(user)
        _db.session.commit()
        return user

    return _make
```

- [ ] **Step 6: Keep the dev seed account usable**

In `backend/seed_dev.py`, add `from datetime import datetime` to the imports, and immediately before `db.session.commit()` at the end of the loop body's branches, make both branches verified — replace:

```python
            db.session.add(user)
            print(f"[create] {spec['email']}  →  {spec['password']}")
    db.session.commit()
```

with:

```python
            db.session.add(user)
            print(f"[create] {spec['email']}  →  {spec['password']}")
        # A seeded dev account has no inbox to click a link in.
        user.email_verified_at = user.email_verified_at or datetime.utcnow()
    db.session.commit()
```

- [ ] **Step 7: Run the tests to verify they pass, then the whole suite**

Run: `cd backend && venv/bin/pytest tests/test_email_verification_model.py tests/test_migration_chain.py -v`
Expected: all PASS (the chain test confirms `a9b0c1d2e3f4` is the single head).

Run: `cd backend && venv/bin/pytest -q`
Expected: `981 passed` (977 + 4).

- [ ] **Step 8: Commit**

```bash
git add backend/migrations/versions/a9b0c1d2e3f4_email_verification.py backend/app/models/user.py \
  backend/app/config.py backend/seed_dev.py backend/tests/conftest.py backend/tests/test_email_verification_model.py
git commit -m "$(cat <<'EOF'
feat(auth): record whether an address is proven

Two nullable columns on users: email_verified_at, and auth_mail_sent_at
to pace the account mails. Every existing account is a test account, so
the migration backfills them verified at their signup time.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Signed links — `auth_links`

**Files:**
- Create: `backend/app/utils/auth_links.py`
- Test: `backend/tests/test_auth_links.py` (new)

**Interfaces:**
- Consumes: `User.id`, `User.email`, `User.password_hash` (Task 1).
- Produces (module `app.utils.auth_links`):
  - `LinkResult(payload: dict | None, error: str | None)` — `error` is `None`, `"link_expired"` or `"link_invalid"`
  - `password_fingerprint(password_hash: str) -> str` (16 hex chars)
  - `safe_next(value) -> str | None`
  - `make_verify_token(user, next_path=None) -> str`; `load_verify_token(token) -> LinkResult` — payload `{"uid", "email", "next"}`
  - `make_reset_token(user) -> str`; `load_reset_token(token) -> LinkResult` — payload `{"uid", "pwv"}`
  - module constants `VERIFY_MAX_AGE = 172800`, `RESET_MAX_AGE = 3600` (read at call time, so tests can monkeypatch them)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_auth_links.py`:

```python
"""Signed links for the two account mails (email verification spec,
decisions 3–7)."""
import pytest

from app.models.user import User
from app.utils import auth_links


def _user(**overrides):
    fields = dict(id="u-1", email="marie@test.fr", password_hash="$2b$04$hash-one")
    fields.update(overrides)
    return User(**fields)


def _flip_last(token: str) -> str:
    return token[:-1] + ("A" if token[-1] != "A" else "B")


def test_a_verification_link_round_trips(app):
    token = auth_links.make_verify_token(_user(), "/analyse/nouveau")
    result = auth_links.load_verify_token(token)
    assert result.error is None
    assert result.payload == {"uid": "u-1", "email": "marie@test.fr", "next": "/analyse/nouveau"}


@pytest.mark.parametrize("bad", [
    "//evil.com", "/\\evil.com", "https://evil.com", "evil.com", "",
    "/ok\r\nSet-Cookie: x=1", "/" + "a" * 600, None, 42, ["/espace"],
])
def test_next_refuses_anything_but_a_local_path(bad):
    assert auth_links.safe_next(bad) is None


def test_next_keeps_a_local_path_and_its_query():
    # Review Focus 4: the query string of a gated page must survive the trip.
    assert auth_links.safe_next("/analyse/nouveau?parcours=2") == "/analyse/nouveau?parcours=2"


def test_an_unsafe_next_is_dropped_from_the_link(app):
    token = auth_links.make_verify_token(_user(), "//evil.com")
    assert auth_links.load_verify_token(token).payload["next"] is None


def test_a_verification_link_is_not_a_reset_link_and_back(app):
    user = _user()
    assert auth_links.load_reset_token(auth_links.make_verify_token(user)).error == "link_invalid"
    assert auth_links.load_verify_token(auth_links.make_reset_token(user)).error == "link_invalid"


def test_a_tampered_link_is_invalid(app):
    token = auth_links.make_verify_token(_user())
    assert auth_links.load_verify_token(_flip_last(token)).error == "link_invalid"


@pytest.mark.parametrize("junk", [None, 42, "", "not-a-token", "a.b.c", "\ud800"])
def test_junk_is_invalid_never_an_exception(app, junk):
    assert auth_links.load_verify_token(junk).error == "link_invalid"


def test_an_old_verification_link_is_expired(app, monkeypatch):
    token = auth_links.make_verify_token(_user())
    monkeypatch.setattr(auth_links, "VERIFY_MAX_AGE", -1)
    assert auth_links.load_verify_token(token).error == "link_expired"


def test_a_reset_link_expires_on_its_own_clock(app, monkeypatch):
    token = auth_links.make_reset_token(_user())
    monkeypatch.setattr(auth_links, "RESET_MAX_AGE", -1)
    assert auth_links.load_reset_token(token).error == "link_expired"


def test_a_reset_link_carries_the_password_fingerprint(app):
    user = _user()
    payload = auth_links.load_reset_token(auth_links.make_reset_token(user)).payload
    assert payload == {"uid": "u-1", "pwv": auth_links.password_fingerprint(user.password_hash)}


def test_the_fingerprint_moves_with_the_password():
    one = auth_links.password_fingerprint("$2b$04$hash-one")
    assert len(one) == 16
    int(one, 16)   # hex, or this raises
    assert one != auth_links.password_fingerprint("$2b$04$hash-two")


def test_a_new_secret_key_kills_old_links(app):
    token = auth_links.make_verify_token(_user())
    app.config["SECRET_KEY"] = "rotated"
    assert auth_links.load_verify_token(token).error == "link_invalid"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && venv/bin/pytest tests/test_auth_links.py -v`
Expected: FAIL — `ImportError: cannot import name 'auth_links' from 'app.utils'`.

- [ ] **Step 3: Implement**

Create `backend/app/utils/auth_links.py`:

```python
"""Signed, expiring links for the two mails that prove an inbox: confirming an
address, and resetting a password.

Stateless on purpose (email verification spec, decision 3): the link carries
its own proof, signed with SECRET_KEY, so there is no token table to store,
expire or clean up. One salt per purpose, so a link minted for one job is
refused by the other. Rotating SECRET_KEY kills every link in flight — the
person asks for a new one.
"""
import hashlib
from dataclasses import dataclass

from flask import current_app
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer

VERIFY_SALT = "email-verify"
RESET_SALT = "password-reset"
VERIFY_MAX_AGE = 48 * 3600   # seconds
RESET_MAX_AGE = 3600
NEXT_MAX_LENGTH = 512


@dataclass(frozen=True)
class LinkResult:
    payload: dict | None
    error: str | None   # None, "link_expired" or "link_invalid"


def password_fingerprint(password_hash: str) -> str:
    """16 hex chars of sha256(password_hash). It changes whenever the password
    does, which makes a reset link single-use and lets /refresh end every
    session minted under an old password."""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


def safe_next(value) -> str | None:
    """A local path (query string allowed), or None. Anything else would make
    the link an open redirect signed by neoori."""
    if not isinstance(value, str):
        return None
    if (
        not value.startswith("/")
        or value.startswith("//")
        or value.startswith("/\\")
        or len(value) > NEXT_MAX_LENGTH
        or any(ch in value for ch in "\r\n\t")
    ):
        return None
    return value


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)


def _load(salt: str, token, max_age: int) -> LinkResult:
    if not isinstance(token, str) or not token:
        return LinkResult(None, "link_invalid")
    try:
        data = _serializer(salt).loads(token, max_age=max_age)
    except SignatureExpired:          # subclass of BadData: must come first
        return LinkResult(None, "link_expired")
    except (BadData, UnicodeError):   # a lone surrogate cannot even be encoded
        return LinkResult(None, "link_invalid")
    if not isinstance(data, dict):
        return LinkResult(None, "link_invalid")
    return LinkResult(data, None)


def make_verify_token(user, next_path=None) -> str:
    return _serializer(VERIFY_SALT).dumps(
        {"uid": user.id, "email": user.email, "next": safe_next(next_path)}
    )


def load_verify_token(token) -> LinkResult:
    return _load(VERIFY_SALT, token, VERIFY_MAX_AGE)


def make_reset_token(user) -> str:
    return _serializer(RESET_SALT).dumps(
        {"uid": user.id, "pwv": password_fingerprint(user.password_hash)}
    )


def load_reset_token(token) -> LinkResult:
    return _load(RESET_SALT, token, RESET_MAX_AGE)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && venv/bin/pytest tests/test_auth_links.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/utils/auth_links.py backend/tests/test_auth_links.py
git commit -m "$(cat <<'EOF'
feat(auth): signed links for verification and reset

itsdangerous, one salt per purpose, no table. A reset link carries a
fingerprint of the password hash, so it dies once the password changes.
next is kept only as a local path, or the link is an open redirect.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: The two account mails and their cooldown

**Files:**
- Modify: `backend/app/config.py` (`APP_URL`)
- Modify: `backend/app/services/email_service.py`
- Create: `backend/app/services/auth_mail.py`
- Test: `backend/tests/test_auth_mail.py` (new)
- Test: `backend/tests/test_email_service.py` (one test added)

**Interfaces:**
- Consumes: `auth_links.make_verify_token`, `auth_links.make_reset_token` (Task 2); `make_user` fixture (Task 1).
- Produces:
  - config `APP_URL: str` (no trailing slash)
  - `email_service.send(to, subject, html, text=None) -> bool`
  - `email_service.send_verification(user, next_path=None) -> bool` — link `{APP_URL}/verifier-email?token=…`
  - `email_service.send_password_reset(user) -> bool` — link `{APP_URL}/reinitialiser-mot-de-passe?token=…`
  - `auth_mail.COOLDOWN = timedelta(seconds=60)`, `auth_mail.cooldown_passed(user, now=None) -> bool`
  - `auth_mail.verification_if_due(user, next_path=None) -> bool` — True when a link is on its way (sent now, or one left under a minute ago)
  - `auth_mail.reset_if_due(user) -> None`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_auth_mail.py`:

```python
"""The two account mails and their one-a-minute pace (email verification
spec, decisions 11 and 17–20)."""
import logging
import re
from datetime import datetime, timedelta
from unittest.mock import patch

from app.extensions import db
from app.models.profile import CONSENT_VERSION, Profile
from app.services import auth_mail, email_service
from app.utils import auth_links

SEND = "app.services.email_service.resend.Emails.send"
TOKEN = re.compile(r"token=([A-Za-z0-9_.\-]+)")


def _sent(mock_send) -> dict:
    return mock_send.call_args[0][0]


def test_the_verification_mail_links_to_the_app_with_a_live_token(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["APP_URL"] = "https://neoori.tech"
    user = make_user(verified=False)
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_verification(user, "/analyse/nouveau") is True
    mail = _sent(mock_send)
    assert mail["to"] == [user.email]
    assert mail["subject"] == "Confirmez votre adresse email"
    assert "https://neoori.tech/verifier-email?token=" in mail["html"]
    payload = auth_links.load_verify_token(TOKEN.search(mail["text"]).group(1)).payload
    assert payload["uid"] == user.id
    assert payload["next"] == "/analyse/nouveau"


def test_the_greeting_uses_the_prenom_escaped(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(verified=False)
    db.session.add(Profile(
        user_id=user.id, prenom="<b>Marie</b>",
        consent_at=datetime.utcnow(), consent_version=CONSENT_VERSION,
    ))
    db.session.commit()
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send_verification(user)
    html = _sent(mock_send)["html"]
    assert "Bonjour &lt;b&gt;Marie&lt;/b&gt;," in html
    assert "<b>Marie</b>" not in html


def test_without_a_key_the_mail_is_not_sent(app, make_user):
    app.debug = False   # FLASK_DEBUG in a developer's shell must not flip this
    assert email_service.send_verification(make_user(verified=False)) is False


def test_on_a_laptop_without_a_key_the_link_goes_to_the_log(app, make_user, caplog):
    app.debug = True
    user = make_user(verified=False)
    with caplog.at_level(logging.WARNING):
        assert email_service.send_verification(user) is True
    assert "/verifier-email?token=" in caplog.text


def test_the_reset_mail_carries_a_reset_token(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user()
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_password_reset(user) is True
    mail = _sent(mock_send)
    assert mail["subject"] == "Réinitialiser votre mot de passe"
    assert "/reinitialiser-mot-de-passe?token=" in mail["html"]
    token = TOKEN.search(mail["text"]).group(1)
    assert auth_links.load_reset_token(token).payload["uid"] == user.id


def test_send_passes_a_text_part_when_given(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send("a@b.fr", "Sujet", "<p>x</p>", text="x")
    assert _sent(mock_send)["text"] == "x"


def test_a_verification_mail_leaves_and_stamps_the_clock(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(verified=False)
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert auth_mail.verification_if_due(user) is True
    assert mock_send.call_count == 1
    assert user.auth_mail_sent_at is not None


def test_a_second_request_within_a_minute_sends_nothing(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(verified=False)
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        auth_mail.verification_if_due(user)
        assert auth_mail.verification_if_due(user) is True   # a link is on its way
        auth_mail.reset_if_due(user)                         # one clock for both mails
    assert mock_send.call_count == 1


def test_after_a_minute_the_next_mail_leaves(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user()
    user.auth_mail_sent_at = datetime.utcnow() - timedelta(seconds=61)
    db.session.commit()
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        auth_mail.reset_if_due(user)
    assert mock_send.call_count == 1


def test_a_failed_send_leaves_the_clock_alone(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(verified=False)
    with patch(SEND, side_effect=RuntimeError("down")):
        assert auth_mail.verification_if_due(user) is False
    assert user.auth_mail_sent_at is None
```

Append to `backend/tests/test_email_service.py`:

```python
def test_the_approval_link_follows_app_url(app):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["APP_URL"] = "http://localhost:8080"
    with patch("app.services.email_service.resend.Emails.send") as mock_send:
        email_service.send_counselor_approved(_profile())
    assert "http://localhost:8080/conseiller" in mock_send.call_args[0][0]["html"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && venv/bin/pytest tests/test_auth_mail.py tests/test_email_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'auth_mail'`, `AttributeError: ... has no attribute 'send_verification'`, `KeyError: 'APP_URL'`.

- [ ] **Step 3: Add `APP_URL` to config**

In `backend/app/config.py`, under `MAIL_FROM = ...` in `class Config`:

```python
    # Public origin every account mail links to (verification, reset,
    # conseiller). The dev compose file points it at http://localhost:8080.
    APP_URL = os.environ.get("APP_URL", "https://neoori.tech").rstrip("/")
```

- [ ] **Step 4: Rework `email_service.py`**

In `backend/app/services/email_service.py`:

1. Replace the imports and the `APP_URL = "https://neoori.tech"` constant with:

```python
import html as html_escape

import resend
from flask import current_app

from ..models.counselor_profile import CounselorProfile
from ..models.profile import Profile
from ..utils import auth_links

FOOTER = "neoori — pour nous écrire, répondez à ce message."


def _app_url() -> str:
    return current_app.config["APP_URL"]
```

2. Replace `send()` with:

```python
def send(to: str, subject: str, html: str, text: str | None = None) -> bool:
    key = current_app.config.get("RESEND_API_KEY")
    if not key:
        current_app.logger.warning("RESEND_API_KEY missing — mail to %s not sent.", to)
        return False
    try:
        resend.api_key = key
        params = {
            "from": current_app.config["MAIL_FROM"],
            "to": [to],
            "subject": subject,
            "html": html,
        }
        # A plain-text part: HTML-only mail scores worse with spam filters.
        if text is not None:
            params["text"] = text
        resend.Emails.send(params)
        return True
    except Exception:
        current_app.logger.exception("Mail to %s failed.", to)
        return False
```

3. In `_layout()`, replace the footer sentence `'neoori — ce message est automatique, il ne se répond pas.</p>'` with `f'{FOOTER}</p>'` (bonjour@neoori.tech is a live Hostinger mailbox since 2026-10-01).

4. In `send_counselor_approved`, replace `f'<p><a href="{APP_URL}/conseiller" '` with `f'<p><a href="{_app_url()}/conseiller" '`.

5. Append the two new mails:

```python
def _button(href: str, label: str) -> str:
    return (
        f'<p style="margin:24px 0"><a href="{href}" style="background:#c96442;'
        'color:#ffffff;padding:12px 20px;border-radius:8px;text-decoration:none;'
        f'display:inline-block">{label}</a></p>'
    )


def _prenom(user) -> str:
    profile = Profile.query.filter_by(user_id=user.id).first()
    return (profile.prenom or "").strip() if profile else ""


def _deliver_link(user, subject: str, html: str, text: str, link: str) -> bool:
    """send(), except on a laptop with no key: the link goes to the log, so the
    local flow can be walked end to end. Debug only — never in production,
    where a token in a log line is a session for whoever reads the log."""
    if not current_app.config.get("RESEND_API_KEY") and current_app.debug:
        current_app.logger.warning("DEV — no RESEND_API_KEY, link for %s: %s", user.email, link)
        return True
    return send(user.email, subject, html, text)


def send_verification(user, next_path=None) -> bool:
    """« Confirmez votre adresse ». Fail-soft like every mail here."""
    try:
        link = f"{_app_url()}/verifier-email?token={auth_links.make_verify_token(user, next_path)}"
        prenom = _prenom(user)
        hello = f"Bonjour {html_escape.escape(prenom)}," if prenom else "Bonjour,"
        body = (
            f"<p>{hello}</p>"
            "<p>Pour activer votre compte neoori, confirmez votre adresse : ouvrez le "
            "lien ci-dessous puis saisissez votre mot de passe. Il est valable 48 heures.</p>"
            + _button(link, "Confirmer mon adresse")
            + '<p style="font-size:13px">Si vous n\'avez pas créé de compte, ignorez ce message.</p>'
        )
        text = (
            f"{'Bonjour ' + prenom + ',' if prenom else 'Bonjour,'}\n\n"
            "Pour activer votre compte neoori, confirmez votre adresse : ouvrez le lien "
            f"ci-dessous puis saisissez votre mot de passe. Il est valable 48 heures.\n\n{link}\n\n"
            "Si vous n'avez pas créé de compte, ignorez ce message.\n\n"
            f"{FOOTER}\n"
        )
        return _deliver_link(
            user, "Confirmez votre adresse email",
            _layout("Confirmez votre adresse", body), text, link,
        )
    except Exception:
        current_app.logger.exception("Could not build/send the verification mail.")
        return False


def send_password_reset(user) -> bool:
    """« Réinitialiser votre mot de passe ». Fail-soft."""
    try:
        link = f"{_app_url()}/reinitialiser-mot-de-passe?token={auth_links.make_reset_token(user)}"
        body = (
            "<p>Une demande de réinitialisation a été faite pour votre compte. Le lien "
            "est valable 1 heure et ne sert qu'une fois.</p>"
            + _button(link, "Choisir un nouveau mot de passe")
            + '<p style="font-size:13px">Si vous n\'êtes pas à l\'origine de cette demande, '
            "ignorez ce message : votre mot de passe reste inchangé.</p>"
        )
        text = (
            "Une demande de réinitialisation a été faite pour votre compte. Le lien est "
            f"valable 1 heure et ne sert qu'une fois.\n\n{link}\n\n"
            "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : "
            "votre mot de passe reste inchangé.\n\n"
            f"{FOOTER}\n"
        )
        return _deliver_link(
            user, "Réinitialiser votre mot de passe",
            _layout("Nouveau mot de passe", body), text, link,
        )
    except Exception:
        current_app.logger.exception("Could not build/send the reset mail.")
        return False
```

- [ ] **Step 5: Create `auth_mail.py`**

Create `backend/app/services/auth_mail.py`:

```python
"""When the two account mails may leave, and the clock that says so.

Shared by routes/auth.py and the conseiller demande, which creates accounts
too. One column, users.auth_mail_sent_at, paces both mails: an inbox gets at
most one account mail a minute whatever the endpoint, so neither
/resend-verification nor /forgot-password can be aimed at someone's address
to flood it (email verification spec, decision 11). The clock is stamped only
when a mail actually left, so a provider outage never blocks the retry.
"""
from datetime import datetime, timedelta

from ..extensions import db
from . import email_service

COOLDOWN = timedelta(seconds=60)


def cooldown_passed(user, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return user.auth_mail_sent_at is None or now - user.auth_mail_sent_at >= COOLDOWN


def _stamp(user) -> None:
    user.auth_mail_sent_at = datetime.utcnow()
    db.session.commit()


def verification_if_due(user, next_path=None) -> bool:
    """True when a link is on its way: sent now, or sent under a minute ago."""
    if not cooldown_passed(user):
        return True
    if not email_service.send_verification(user, next_path):
        return False
    _stamp(user)
    return True


def reset_if_due(user) -> None:
    if cooldown_passed(user) and email_service.send_password_reset(user):
        _stamp(user)
```

- [ ] **Step 6: Run the tests to verify they pass, then the whole suite**

Run: `cd backend && venv/bin/pytest tests/test_auth_mail.py tests/test_email_service.py -v`
Expected: all PASS.

Run: `cd backend && venv/bin/pytest -q`
Expected: all pass, no failures.

- [ ] **Step 7: Commit**

```bash
git add backend/app/config.py backend/app/services/email_service.py backend/app/services/auth_mail.py \
  backend/tests/test_auth_mail.py backend/tests/test_email_service.py
git commit -m "$(cat <<'EOF'
feat(auth): the verification and reset mails, paced to one a minute

Both mails send HTML and plain text, link through APP_URL, and stay
fail-soft. On a laptop without a key the link is logged instead. The
footer now invites replies: bonjour@neoori.tech is a live mailbox.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: The session gate — register, login, refresh

**Files:**
- Modify: `backend/app/routes/auth.py`
- Modify: `backend/tests/test_counselor_review.py` (`_demande` + one refresh test)
- Test: `backend/tests/test_auth_gate.py` (new)

**Interfaces:**
- Consumes: `auth_links.password_fingerprint` (Task 2), `auth_mail.verification_if_due` (Task 3), `make_user` (Task 1).
- Produces:
  - `routes.auth._issue_session(response, user) -> None` — raises `ValueError` for an unverified user; refresh token carries claim `pwv`
  - `POST /api/auth/register` → 201 `{user, mail_sent: bool}`, **no cookies**; accepts optional `next`
  - `POST /api/auth/login` → 403 `{error, code: "email_unverified"}` for a right password on an unverified account
  - `POST /api/auth/refresh` → 401 when unverified or `pwv` missing/stale

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_auth_gate.py`:

```python
"""No session for an unproven address (email verification spec, decisions
2, 6, 9 and 10)."""
import re
from unittest.mock import patch

import pytest
from flask import jsonify
from flask_jwt_extended import create_refresh_token

from app.extensions import bcrypt, db
from app.models.user import User
from app.routes.auth import _issue_session
from app.utils import auth_links

SEND = "app.services.email_service.resend.Emails.send"
TOKEN = re.compile(r"token=([A-Za-z0-9_.\-]+)")


def _cookies(res) -> str:
    return " ".join(res.headers.getlist("Set-Cookie"))


def _register(client, email="nouveau@test.fr", password="motdepasse1", **extra):
    return client.post("/api/auth/register", json={"email": email, "password": password, **extra})


def _login(client, email, password="motdepasse1"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _refresh(client, token):
    return client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {token}"})


def _refresh_token(user):
    return create_refresh_token(
        identity=user.id,
        additional_claims={"pwv": auth_links.password_fingerprint(user.password_hash)},
    )


def test_register_opens_no_session(client, app):
    res = _register(client)
    assert res.status_code == 201
    assert "access_token_cookie" not in _cookies(res)
    assert res.get_json()["user"]["email_verified"] is False
    assert res.get_json()["mail_sent"] is False      # no key in tests


def test_register_mails_a_link_that_keeps_the_destination(client, app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        res = _register(client, next="/analyse/nouveau")
    assert res.get_json()["mail_sent"] is True
    token = TOKEN.search(mock_send.call_args[0][0]["text"]).group(1)
    assert auth_links.load_verify_token(token).payload["next"] == "/analyse/nouveau"


@pytest.mark.parametrize("verified", [True, False])
def test_register_never_overwrites_an_existing_account(client, make_user, verified):
    user = make_user(email="pris@test.fr", verified=verified)
    before = user.password_hash
    res = _register(client, email="pris@test.fr", password="autrechose9")
    assert res.status_code == 409
    db.session.expire_all()
    assert db.session.get(User, user.id).password_hash == before


def test_login_of_an_unverified_account_says_so_only_with_the_right_password(client, make_user):
    make_user(email="attente@test.fr", verified=False)
    wrong = _login(client, "attente@test.fr", "pasLeBon123")
    assert wrong.status_code == 401
    assert wrong.get_json()["error"] == "Identifiants incorrects."
    right = _login(client, "attente@test.fr")
    assert right.status_code == 403
    assert right.get_json()["code"] == "email_unverified"
    assert "access_token_cookie" not in _cookies(right)


def test_login_of_a_verified_account_opens_a_session(client, make_user):
    make_user(email="ok@test.fr")
    res = _login(client, "ok@test.fr")
    assert res.status_code == 200
    assert "access_token_cookie" in _cookies(res)
    assert "refresh_token_cookie" in _cookies(res)


def test_issue_session_refuses_an_unverified_account(app, make_user):
    with pytest.raises(ValueError):
        _issue_session(jsonify({}), make_user(verified=False))


def test_refresh_works_under_the_password_it_was_minted_with(client, make_user):
    assert _refresh(client, _refresh_token(make_user())).status_code == 200


def test_refresh_without_pwv_is_refused(client, make_user):
    user = make_user()
    assert _refresh(client, create_refresh_token(identity=user.id)).status_code == 401


def test_refresh_after_a_password_change_is_refused(client, make_user):
    user = make_user()
    token = _refresh_token(user)
    user.password_hash = bcrypt.generate_password_hash("nouveau-mdp1").decode("utf-8")
    db.session.commit()
    assert _refresh(client, token).status_code == 401


def test_refresh_of_an_unverified_account_is_refused(client, make_user):
    assert _refresh(client, _refresh_token(make_user(verified=False))).status_code == 401
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && venv/bin/pytest tests/test_auth_gate.py -v`
Expected: FAIL — `ImportError: cannot import name '_issue_session'`.

- [ ] **Step 3: Implement the gate in `routes/auth.py`**

1. Add to the imports:

```python
from ..services import auth_mail
from ..utils import auth_links
```

2. In `register()`, replace the tail:

```python
    db.session.commit()

    response = jsonify({"user": user.to_dict()})
    _set_tokens(response, user)
    return response, 201
```

with:

```python
    db.session.commit()

    # No session: the account opens once its address is proven (spec decision
    # 2). `next` rides in the link, so the email round-trip lands them back
    # where they were heading.
    mail_sent = auth_mail.verification_if_due(user, text_field(data, "next") or None)
    return jsonify({"user": user.to_dict(), "mail_sent": mail_sent}), 201
```

3. In `login()`, replace:

```python
    response = jsonify({"user": user.to_dict()})
    _set_tokens(response, user)
    return response, 200
```

with:

```python
    # 403, not 401: api.ts sends every 401 back to /connexion, which would
    # swallow this. Reached only with the right password, so it tells the
    # account's state to its owner and nobody else (spec decision 9).
    if user.email_verified_at is None:
        return jsonify({
            "error": "Confirmez votre adresse email pour activer votre compte.",
            "code": "email_unverified",
        }), 403

    response = jsonify({"user": user.to_dict()})
    _issue_session(response, user)
    return response, 200
```

4. Replace the whole `refresh()` function with:

```python
@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur introuvable."}), 404

    # A refresh token outlives a password change by up to 30 days. pwv pins it
    # to the password it was minted under, so a reset ends every other session
    # (spec decision 6). Tokens minted before pwv existed carry none and end
    # too, once.
    if (
        user.email_verified_at is None
        or get_jwt().get("pwv") != auth_links.password_fingerprint(user.password_hash)
    ):
        response = jsonify({"error": "Session expirée."})
        unset_jwt_cookies(response)
        return response, 401

    access_token = create_access_token(
        identity=user.id,
        additional_claims={"role": user.role},
    )
    response = jsonify({"user": user.to_dict()})
    set_access_cookies(response, access_token)
    return response, 200
```

5. Replace the `_set_tokens` helper at the bottom with:

```python
def _issue_session(response, user: User):
    """The only place a session is minted. It refuses an unverified account, so
    a route added later cannot hand one out by forgetting a check (spec
    decision 2)."""
    if user.email_verified_at is None:
        raise ValueError("refusing to open a session for an unverified account")
    access_token = create_access_token(
        identity=user.id,
        additional_claims={"role": user.role},
    )
    refresh_token = create_refresh_token(
        identity=user.id,
        additional_claims={"pwv": auth_links.password_fingerprint(user.password_hash)},
    )
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)
```

6. Confirm nothing else calls the old helper:

Run: `grep -rn "_set_tokens" backend/app`
Expected: no output.

- [ ] **Step 4: Update the conseiller review tests**

In `backend/tests/test_counselor_review.py`:

- add imports `from datetime import datetime` and `from app.utils.auth_links import password_fingerprint`
- in `_demande`, make the user verified — the queue and approval now require it (spec decision 16):

```python
def _demande(email="conseiller@test.com", status="pending"):
    # Verified: a demande reaches the queue only once its address is proven.
    u = User(email=email, password_hash="x", role="candidate", email_verified_at=datetime.utcnow())
```

- in `test_refresh_mints_the_counselor_claim_after_approval`, mint the refresh token the way `_issue_session` now does:

```python
    refresh_headers = {
        "Authorization": "Bearer " + create_refresh_token(
            identity=str(user.id),
            additional_claims={"pwv": password_fingerprint(user.password_hash)},
        )
    }
```

- [ ] **Step 5: Run the tests to verify they pass, then the whole suite**

Run: `cd backend && venv/bin/pytest tests/test_auth_gate.py tests/test_counselor_review.py tests/test_signup_profile_seed.py -v`
Expected: all PASS.

Run: `cd backend && venv/bin/pytest -q`
Expected: all pass. If a test elsewhere fails because it expected `register` or `login` to set cookies, update it to the new contract in this task, not by weakening the gate.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/auth.py backend/tests/test_auth_gate.py backend/tests/test_counselor_review.py
git commit -m "$(cat <<'EOF'
feat(auth): no session until the address is proven

Signup mails a link instead of signing in. Login answers 403
email_unverified, and only to someone with the right password. Refresh
tokens carry a password fingerprint, so a password change ends them.
_issue_session is the one place cookies are minted and it refuses an
unverified account.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Verify, resend, forgot, reset endpoints

**Files:**
- Modify: `backend/app/routes/auth.py`
- Test: `backend/tests/test_auth_link_routes.py` (new)

**Interfaces:**
- Consumes: `auth_links` (Task 2), `auth_mail` (Task 3), `_issue_session` (Task 4), `make_user` (Task 1).
- Produces:
  - `POST /api/auth/verify-email/check {token}` → 200 `{email}` | 400 `{error, code}`
  - `POST /api/auth/verify-email {token, password}` → 200 `{user, next: str | null}` + cookies | 401 `{error, code: "wrong_password"}` | 400 `{error, code: "link_expired" | "link_invalid"}`
  - `POST /api/auth/resend-verification {email, next?}` → always 200 `{message}`
  - `POST /api/auth/forgot-password {email}` → always 200 `{message}`
  - `POST /api/auth/reset-password {token, password}` → 200 `{user}` + cookies | 400

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_auth_link_routes.py`:

```python
"""Verify, resend, forgot, reset (email verification spec, decisions 4–12
and 23)."""
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_refresh_token

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User
from app.utils import auth_links

SEND = "app.services.email_service.resend.Emails.send"


def _cookies(res) -> str:
    return " ".join(res.headers.getlist("Set-Cookie"))


def _fresh(user):
    db.session.expire_all()
    return db.session.get(User, user.id)


def _verify(client, token, password="motdepasse1"):
    return client.post("/api/auth/verify-email", json={"token": token, "password": password})


def _reset(client, token, password="nouveau-mdp1"):
    return client.post("/api/auth/reset-password", json={"token": token, "password": password})


def _post_counting_mails(client, path, email, **extra):
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        res = client.post(path, json={"email": email, **extra})
    return res, mock_send.call_count


# ── verify-email/check ────────────────────────────────────────────────────────

def test_check_names_the_address_of_a_live_link(client, make_user):
    user = make_user(verified=False)
    res = client.post("/api/auth/verify-email/check",
                      json={"token": auth_links.make_verify_token(user)})
    assert res.status_code == 200
    assert res.get_json() == {"email": user.email}


def test_check_says_expired(client, make_user, monkeypatch):
    token = auth_links.make_verify_token(make_user(verified=False))
    monkeypatch.setattr(auth_links, "VERIFY_MAX_AGE", -1)
    res = client.post("/api/auth/verify-email/check", json={"token": token})
    assert res.status_code == 400
    assert res.get_json()["code"] == "link_expired"


# ── verify-email ──────────────────────────────────────────────────────────────

def test_link_and_password_verify_and_sign_in(client, make_user):
    user = make_user(verified=False)
    res = _verify(client, auth_links.make_verify_token(user, "/analyse/nouveau"))
    assert res.status_code == 200
    assert res.get_json()["next"] == "/analyse/nouveau"
    assert res.get_json()["user"]["email_verified"] is True
    assert "access_token_cookie" in _cookies(res)
    assert _fresh(user).email_verified_at is not None


def test_the_wrong_password_changes_nothing(client, make_user):
    user = make_user(verified=False)
    res = _verify(client, auth_links.make_verify_token(user), "pasLeBon123")
    assert res.status_code == 401
    assert res.get_json()["code"] == "wrong_password"
    assert "access_token_cookie" not in _cookies(res)
    assert _fresh(user).email_verified_at is None


def test_a_second_use_is_a_login(client, make_user):
    token = auth_links.make_verify_token(make_user(verified=False))
    assert _verify(client, token).status_code == 200
    again = _verify(client, token)
    assert again.status_code == 200
    assert "access_token_cookie" in _cookies(again)


def test_a_link_for_an_address_the_account_no_longer_holds_is_invalid(client, make_user):
    user = make_user(verified=False)
    token = auth_links.make_verify_token(user)
    user.email = "autre@test.fr"
    db.session.commit()
    assert _verify(client, token).get_json()["code"] == "link_invalid"


def test_a_link_for_a_deleted_account_is_invalid(client, make_user):
    user = make_user(verified=False)
    token = auth_links.make_verify_token(user)
    db.session.delete(user)
    db.session.commit()
    res = _verify(client, token)
    assert res.status_code == 400
    assert res.get_json()["code"] == "link_invalid"


def test_a_conseiller_without_next_lands_on_the_demande(client, make_user):
    user = make_user(verified=False)
    db.session.add(CounselorProfile(
        user_id=user.id, structure="Cap Emploi 31", fonction="Conseillère", telephone="0561000000",
    ))
    db.session.commit()
    assert _verify(client, auth_links.make_verify_token(user)).get_json()["next"] == "/conseiller"


@pytest.mark.parametrize("suffix", [".", ")", "%29"])
def test_a_link_mangled_by_a_mail_client_is_invalid_not_a_crash(client, make_user, suffix):
    # Review Focus 2.
    res = _verify(client, auth_links.make_verify_token(make_user(verified=False)) + suffix)
    assert res.status_code == 400
    assert res.get_json()["code"] == "link_invalid"


def test_a_password_with_surrounding_spaces_is_taken_verbatim(client, app):
    # Review Focus 3.
    password = "  espace devant et derrière  "
    assert client.post("/api/auth/register",
                       json={"email": "espaces@test.fr", "password": password}).status_code == 201
    user = User.query.filter_by(email="espaces@test.fr").one()
    token = auth_links.make_verify_token(user)
    assert _verify(client, token, password.strip()).status_code == 401
    assert _verify(client, token, password).status_code == 200


@pytest.mark.parametrize("body", [{"token": ["x"]}, {"token": {"a": 1}}, {"password": 42}, {}])
def test_hostile_verify_bodies_answer_400(client, body):
    res = client.post("/api/auth/verify-email", json=body)
    assert res.status_code == 400
    assert res.get_json()["code"] == "link_invalid"


# ── resend-verification ───────────────────────────────────────────────────────

def test_resend_answers_the_same_whatever_the_account(client, app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    make_user(email="attente@test.fr", verified=False)
    make_user(email="actif@test.fr")
    bodies, sent = set(), {}
    for email in ("attente@test.fr", "actif@test.fr", "inconnu@test.fr"):
        res, count = _post_counting_mails(client, "/api/auth/resend-verification", email)
        assert res.status_code == 200
        bodies.add(res.get_data())
        sent[email] = count
    assert len(bodies) == 1
    assert sent == {"attente@test.fr": 1, "actif@test.fr": 0, "inconnu@test.fr": 0}


def test_resend_finds_the_account_whatever_the_case_and_padding(client, app, make_user):
    # Review Focus 1.
    app.config["RESEND_API_KEY"] = "re_test"
    make_user(email="marie@test.fr", verified=False)
    _res, count = _post_counting_mails(client, "/api/auth/resend-verification", "  Marie@Test.FR ")
    assert count == 1


# ── forgot-password ───────────────────────────────────────────────────────────

def test_forgot_answers_the_same_whatever_the_account(client, app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    make_user(email="actif@test.fr")
    known, sent_known = _post_counting_mails(client, "/api/auth/forgot-password", "actif@test.fr")
    unknown, sent_unknown = _post_counting_mails(client, "/api/auth/forgot-password", "inconnu@test.fr")
    assert known.status_code == unknown.status_code == 200
    assert known.get_data() == unknown.get_data()
    assert (sent_known, sent_unknown) == (1, 0)


def test_forgot_finds_the_account_whatever_the_case_and_padding(client, app, make_user):
    # Review Focus 1.
    app.config["RESEND_API_KEY"] = "re_test"
    make_user(email="marie@test.fr")
    _res, count = _post_counting_mails(client, "/api/auth/forgot-password", " MARIE@test.fr")
    assert count == 1


# ── reset-password ────────────────────────────────────────────────────────────

def test_reset_sets_the_password_and_signs_in(client, make_user):
    user = make_user(email="reset@test.fr")
    res = _reset(client, auth_links.make_reset_token(user))
    assert res.status_code == 200
    assert "access_token_cookie" in _cookies(res)
    login = client.post("/api/auth/login", json={"email": "reset@test.fr", "password": "nouveau-mdp1"})
    assert login.status_code == 200


def test_a_reset_link_works_once(client, make_user):
    token = auth_links.make_reset_token(make_user())
    assert _reset(client, token).status_code == 200
    second = _reset(client, token, "encore-autre1")
    assert second.status_code == 400
    assert second.get_json()["code"] == "link_invalid"


def test_a_short_password_does_not_spend_the_link(client, make_user):
    token = auth_links.make_reset_token(make_user())
    assert _reset(client, token, "court").status_code == 400
    assert _reset(client, token).status_code == 200


def test_a_reset_proves_the_inbox(client, make_user):
    user = make_user(verified=False)
    assert _reset(client, auth_links.make_reset_token(user)).status_code == 200
    assert _fresh(user).email_verified_at is not None


def test_a_reset_ends_sessions_opened_under_the_old_password(client, make_user):
    user = make_user()
    old = create_refresh_token(
        identity=user.id,
        additional_claims={"pwv": auth_links.password_fingerprint(user.password_hash)},
    )
    assert _reset(client, auth_links.make_reset_token(user)).status_code == 200
    res = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {old}"})
    assert res.status_code == 401


def test_an_expired_reset_link_says_so(client, make_user, monkeypatch):
    token = auth_links.make_reset_token(make_user())
    monkeypatch.setattr(auth_links, "RESET_MAX_AGE", -1)
    assert _reset(client, token).get_json()["code"] == "link_expired"


def test_a_reset_keeps_surrounding_spaces(client, make_user):
    # Review Focus 3.
    user = make_user(email="sp@test.fr")
    assert _reset(client, auth_links.make_reset_token(user), "  avec espaces  ").status_code == 200
    login = client.post("/api/auth/login", json={"email": "sp@test.fr", "password": "  avec espaces  "})
    assert login.status_code == 200
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && venv/bin/pytest tests/test_auth_link_routes.py -v`
Expected: FAIL — 404/405 on every new endpoint.

- [ ] **Step 3: Implement the endpoints**

In `backend/app/routes/auth.py`:

1. Add the import `from ..models.counselor_profile import CounselorProfile`.

2. Above the `# ── helpers ──` line, add:

```python
LINK_ERRORS = {
    "link_expired": "Ce lien a expiré. Demandez-en un nouveau.",
    "link_invalid": "Ce lien n'est pas valide. Demandez-en un nouveau.",
}
# One sentence whatever the account's state: these two must not tell a
# stranger whether an address has an account (spec decision 11).
RESEND_MESSAGE = "Si cette adresse attend une confirmation, un nouveau lien vient d'être envoyé."
FORGOT_MESSAGE = "Si un compte existe pour cette adresse, un email vient d'être envoyé."


@auth_bp.post("/verify-email/check")
def verify_email_check():
    """Is this link alive, and for which address? Lets the page say « expiré »
    before anyone types a password, and fill the email for password managers."""
    user, _payload, code = _user_from_verify_token(text_field(json_object(), "token"))
    if code:
        return _link_error(code)
    return jsonify({"email": user.email}), 200


@auth_bp.post("/verify-email")
def verify_email():
    """Link + password → verified and signed in (spec decision 8).

    The password is what closes pre-account hijacking: someone who signed up
    with your address and their password cannot have you verify an account
    they can also log into. Without it the victim uses « mot de passe
    oublié », which sets their own password and ends the other sessions.
    A second use is simply a login.
    """
    data = json_object()
    user, payload, code = _user_from_verify_token(text_field(data, "token"))
    if code:
        return _link_error(code)

    password = raw_text_field(data, "password")
    if not password or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({"error": "Mot de passe incorrect.", "code": "wrong_password"}), 401

    if user.email_verified_at is None:
        user.email_verified_at = datetime.utcnow()
        db.session.commit()

    response = jsonify({"user": user.to_dict(), "next": _landing(user, payload)})
    _issue_session(response, user)
    return response, 200


@auth_bp.post("/resend-verification")
def resend_verification():
    data = json_object()
    email = text_field(data, "email").lower()
    user = User.query.filter_by(email=email).first() if email else None
    if user is not None and user.email_verified_at is None:
        auth_mail.verification_if_due(user, text_field(data, "next") or None)
    return jsonify({"message": RESEND_MESSAGE}), 200


@auth_bp.post("/forgot-password")
def forgot_password():
    email = text_field(json_object(), "email").lower()
    user = User.query.filter_by(email=email).first() if email else None
    if user is not None:
        auth_mail.reset_if_due(user)
    return jsonify({"message": FORGOT_MESSAGE}), 200


@auth_bp.post("/reset-password")
def reset_password():
    data = json_object()
    result = auth_links.load_reset_token(text_field(data, "token"))
    if result.error:
        return _link_error(result.error)
    uid = result.payload.get("uid")
    user = db.session.get(User, uid) if isinstance(uid, str) else None
    # pwv dies with the password it was minted under: a used link is dead.
    if user is None or result.payload.get("pwv") != auth_links.password_fingerprint(user.password_hash):
        return _link_error("link_invalid")

    # Checked before anything is written, so a refused password leaves the
    # link usable for the next attempt.
    password = raw_text_field(data, "password")
    if len(password) < 8:
        return jsonify({"error": "Le mot de passe doit contenir au moins 8 caractères."}), 400

    user.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    # Opening the link proved the inbox, exactly as the verification link
    # does (spec decision 12).
    if user.email_verified_at is None:
        user.email_verified_at = datetime.utcnow()
    db.session.commit()

    response = jsonify({"user": user.to_dict()})
    _issue_session(response, user)
    return response, 200
```

3. Below `_issue_session` in the helpers section, add:

```python
def _link_error(code: str):
    return jsonify({"error": LINK_ERRORS[code], "code": code}), 400


def _user_from_verify_token(token: str):
    """(user, payload, None) for a live verification link, else (None, None, code)."""
    result = auth_links.load_verify_token(token)
    if result.error:
        return None, None, result.error
    uid = result.payload.get("uid")
    user = db.session.get(User, uid) if isinstance(uid, str) else None
    # The address is in the signed payload: a link mailed to an address the
    # account no longer holds proves nothing about the current one.
    if user is None or user.email != result.payload.get("email"):
        return None, None, "link_invalid"
    return user, result.payload, None


def _landing(user: User, payload: dict) -> str | None:
    """Where the verified person goes. A conseiller who asked for a fresh link
    from /connexion carries no next; their screen is the demande, not the
    candidate espace (spec decision 23)."""
    if payload.get("next"):
        return payload["next"]
    if CounselorProfile.query.filter_by(user_id=user.id).first():
        return "/conseiller"
    return None
```

- [ ] **Step 4: Run the tests to verify they pass, then the whole suite**

Run: `cd backend && venv/bin/pytest tests/test_auth_link_routes.py -v`
Expected: all PASS.

Run: `cd backend && venv/bin/pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/auth.py backend/tests/test_auth_link_routes.py
git commit -m "$(cat <<'EOF'
feat(auth): verify with link and password, resend, forgot, reset

Verifying takes the link and the password chosen at signup, which closes
pre-account hijacking. Resend and forgot answer the same sentence for
every address. A reset link works once, proves the inbox, and ends the
sessions opened under the old password.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: The conseiller demande mails a link instead of signing in

**Files:**
- Modify: `backend/app/routes/counselor_space.py`
- Test: `backend/tests/test_counselor_apply.py` (three tests added)

**Interfaces:**
- Consumes: `auth_mail.verification_if_due` (Task 3).
- Produces: `POST /api/counselor/apply` without a JWT → 201 `{user, profile, mail_sent}`, no cookies, link `next = "/conseiller"`. With a JWT: unchanged (no `mail_sent` key).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_counselor_apply.py`:

```python
def test_a_new_account_demande_opens_no_session(client, app):
    r = client.post("/api/counselor/apply", json=PAYLOAD)
    assert r.status_code == 201
    assert "access_token_cookie" not in " ".join(r.headers.getlist("Set-Cookie"))
    assert r.get_json()["mail_sent"] is False      # no key in tests
    assert r.get_json()["user"]["email_verified"] is False


def test_the_demande_link_lands_on_the_conseiller_screen(client, app):
    import re
    from unittest.mock import patch

    from app.utils import auth_links

    app.config["RESEND_API_KEY"] = "re_test"
    with patch("app.services.email_service.resend.Emails.send", return_value={"id": "1"}) as mock_send:
        r = client.post("/api/counselor/apply", json=PAYLOAD)
    assert r.get_json()["mail_sent"] is True
    token = re.search(r"token=([A-Za-z0-9_.\-]+)", mock_send.call_args[0][0]["text"]).group(1)
    assert auth_links.load_verify_token(token).payload["next"] == "/conseiller"


def test_reapplying_with_an_unverified_accounts_email_is_refused(client, app):
    assert client.post("/api/counselor/apply", json=PAYLOAD).status_code == 201
    again = client.post("/api/counselor/apply", json={**PAYLOAD, "password": "autrechose9"})
    assert again.status_code == 409
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && venv/bin/pytest tests/test_counselor_apply.py -v`
Expected: the first two FAIL (`access_token_cookie` present, `KeyError: 'mail_sent'`); the third already passes (the unique-email 409 is unchanged — it pins that it stays).

- [ ] **Step 3: Implement**

In `backend/app/routes/counselor_space.py`:

1. Add the import `from ..services import auth_mail` beside `from ..services import code_service`.

2. Replace the end of `apply()`:

```python
    response = jsonify({"user": user.to_dict(), "profile": profile.to_dict()})
    if created:
        access_token = create_access_token(
            identity=user.id, additional_claims={"role": user.role}
        )
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, create_refresh_token(identity=user.id))
    return response, 201
```

with:

```python
    body = {"user": user.to_dict(), "profile": profile.to_dict()}
    if created:
        # A new account opens only once its address is proven (email
        # verification spec, decision 2): no session here, a link instead,
        # landing on the « demande en attente » screen. The demande waits for
        # the same proof before the admin queue shows it (decision 16).
        body["mail_sent"] = auth_mail.verification_if_due(user, "/conseiller")
    return jsonify(body), 201
```

3. Remove the imports this left unused:

Run: `grep -n "create_access_token\|create_refresh_token\|set_access_cookies\|set_refresh_cookies" backend/app/routes/counselor_space.py`
Expected: only the import lines. Delete those four names from the `from flask_jwt_extended import (...)` block, keeping `get_jwt_identity`, `jwt_required`, `verify_jwt_in_request`.

- [ ] **Step 4: Run the tests to verify they pass, then the whole suite**

Run: `cd backend && venv/bin/pytest tests/test_counselor_apply.py -v` → all PASS.
Run: `cd backend && venv/bin/pytest -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/counselor_space.py backend/tests/test_counselor_apply.py
git commit -m "$(cat <<'EOF'
feat(conseiller): a new demande mails a link instead of signing in

The no-account path creates the account unverified and sends the
confirmation link, landing on /conseiller. A demande from a signed-in
account is unchanged.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Close anonymous analyses and uploads

**Files:**
- Modify: `backend/app/routes/analyses.py` (`create_analysis`)
- Modify: `backend/app/routes/upload.py`
- Modify: `backend/tests/conftest.py` (`candidate_headers` fixture)
- Modify: `backend/tests/test_parcours_inputs.py`, `backend/tests/test_malformed_bodies.py`, `backend/tests/test_voyage_prompt_context.py`, `backend/tests/test_no_500_on_hostile_input.py`
- Test: `backend/tests/test_anonymous_closed.py` (new)

**Interfaces:**
- Consumes: `make_user` (Task 1).
- Produces: fixture `candidate_headers -> dict` (verified candidate bearer header); `POST /api/analyses/`, `/api/upload/cv`, `/api/upload/projet` → 401 without a JWT.

- [ ] **Step 1: Add the fixture and write the failing tests**

In `backend/tests/conftest.py`, after `make_user`, add:

```python
@pytest.fixture
def candidate_headers(make_user):
    """A verified candidate's bearer header — what every gated route needs now
    that analyses and uploads require an account."""
    user = make_user(email="candidat@test.fr")
    token = create_access_token(identity=str(user.id), additional_claims={"role": "candidate"})
    return {"Authorization": f"Bearer {token}"}
```

Create `backend/tests/test_anonymous_closed.py`:

```python
"""No analysis and no upload without an account (email verification spec,
decision 13). The anonymous path is what made throwaway accounts
unnecessary: nobody needs a fake account when no account is needed."""
import io
from unittest.mock import patch

import pytest

P1 = {"inputs": {"_path": "1", "cv_text": "c" * 300, "cible_visee": "Chauffeur livreur PL"}}


@pytest.mark.parametrize("path", ["/api/upload/cv", "/api/upload/projet"])
def test_an_upload_needs_an_account(client, path):
    data = {"file": (io.BytesIO(b"%PDF-1.4"), "cv.pdf", "application/pdf")}
    res = client.post(path, data=data, content_type="multipart/form-data")
    assert res.status_code == 401


def test_an_analysis_needs_an_account(client):
    assert client.post("/api/analyses/", json=P1).status_code == 401


@patch("app.routes.analyses.start_analysis")
def test_a_signed_in_candidate_still_creates_one(_start, client, candidate_headers):
    res = client.post("/api/analyses/", json=P1, headers=candidate_headers)
    assert res.status_code == 201, res.data
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && venv/bin/pytest tests/test_anonymous_closed.py -v`
Expected: the three 401 tests FAIL (the routes answer 400/415/201 today).

- [ ] **Step 3: Gate the routes**

In `backend/app/routes/analyses.py`, change `create_analysis`'s head to:

```python
@analyses_bp.post("/")
@jwt_required()
def create_analysis():
    # An account with a proven address is required (email verification spec,
    # decision 13): the anonymous path made throwaway accounts unnecessary.
    user_id = get_jwt_identity()
```

(`_optional_user_id()` stays — the read routes still use it.)

In `backend/app/routes/upload.py`, add `from flask_jwt_extended import jwt_required` to the imports and `@jwt_required()` under both route decorators:

```python
@upload_bp.post("/cv")
@jwt_required()
def upload_cv():
```

```python
@upload_bp.post("/projet")
@jwt_required()
def upload_projet():
```

- [ ] **Step 4: Move the existing anonymous tests onto an account**

- `backend/tests/test_parcours_inputs.py`: add `candidate_headers` to the signatures of `test_create_persists_the_chemin_so_the_framing_note_can_fire` and `test_create_leaves_parcours_2_and_3_without_a_chemin`, and pass `headers=candidate_headers` to both `client.post("/api/analyses/", ...)` calls.
- `backend/tests/test_malformed_bodies.py`: change `test_create_analysis_survives_malformed_body(client, body)` to `(client, body, candidate_headers)` and post with `headers=candidate_headers`.
- `backend/tests/test_no_500_on_hostile_input.py`: in the `create_analysis` entry of `ROUTES`, change `headers=lambda rig: {}` to `headers=lambda rig: rig["candidate_headers"]`.
- `backend/tests/test_voyage_prompt_context.py`: replace `test_an_anonymous_analysis_carries_no_voyage` (and its `@patch` decorator) with:

```python
def test_there_is_no_anonymous_analysis_any_more(client, app):
    """An account with a proven address is required (email verification spec,
    decision 13), so the anonymous path this test used to cover is closed."""
    res = client.post("/api/analyses/", json={"inputs": dict(P1_FULL)})
    assert res.status_code == 401
```

- [ ] **Step 5: Run the tests to verify they pass, then the whole suite**

Run: `cd backend && venv/bin/pytest tests/test_anonymous_closed.py tests/test_parcours_inputs.py tests/test_malformed_bodies.py tests/test_voyage_prompt_context.py tests/test_no_500_on_hostile_input.py -v`
Expected: all PASS.

Run: `cd backend && venv/bin/pytest -q` → all pass. Any other test posting anonymously to these three routes gets `candidate_headers` the same way.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/analyses.py backend/app/routes/upload.py backend/tests/conftest.py \
  backend/tests/test_anonymous_closed.py backend/tests/test_parcours_inputs.py backend/tests/test_malformed_bodies.py \
  backend/tests/test_voyage_prompt_context.py backend/tests/test_no_500_on_hostile_input.py
git commit -m "$(cat <<'EOF'
feat(analyses): an analysis and an upload need an account

Anonymous analyses made the verification gate pointless: nobody needs a
throwaway account when no account is needed. Creating an analysis and
both PDF uploads now require a JWT, which only a verified account gets.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Admin — manual verify, queue filter, approve guard

**Files:**
- Modify: `backend/app/routes/admin.py`
- Test: `backend/tests/test_admin_email_verification.py` (new)

**Interfaces:**
- Consumes: `make_user`, `admin_headers` fixtures; `User.email_verified_at` (Task 1).
- Produces: `POST /api/admin/users/<id>/verify-email` → 200 `{user}` (admin only); `GET /api/admin/counselor-applications` omits unverified accounts; `POST .../approve` → 409 for an unverified account.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_admin_email_verification.py`:

```python
"""The admin's side of email verification (spec decisions 15 and 16)."""
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User


def _demande(make_user, email, verified):
    user = make_user(email=email, verified=verified)
    profile = CounselorProfile(
        user_id=user.id, structure="Cap Emploi 31", fonction="Conseillère", telephone="0561000000",
    )
    db.session.add(profile)
    db.session.commit()
    return user, profile


def _verify_by_admin(client, admin_headers, user):
    return client.post(f"/api/admin/users/{user.id}/verify-email", headers=admin_headers)


def test_the_admin_marks_an_address_verified(client, admin_headers, make_user):
    user = make_user(email="test@test.fr", verified=False)
    res = _verify_by_admin(client, admin_headers, user)
    assert res.status_code == 200
    assert res.get_json()["user"]["email_verified"] is True


def test_marking_twice_keeps_the_first_timestamp(client, admin_headers, make_user):
    user = make_user(email="twice@test.fr", verified=False)
    _verify_by_admin(client, admin_headers, user)
    db.session.expire_all()
    first = db.session.get(User, user.id).email_verified_at
    _verify_by_admin(client, admin_headers, user)
    db.session.expire_all()
    assert db.session.get(User, user.id).email_verified_at == first


def test_a_candidate_cannot_mark_an_address(client, make_user):
    target = make_user(email="cible@test.fr", verified=False)
    candidate = make_user(email="curieux@test.fr")
    token = create_access_token(identity=str(candidate.id), additional_claims={"role": "candidate"})
    res = client.post(f"/api/admin/users/{target.id}/verify-email",
                      headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_a_manually_verified_account_logs_in_with_a_working_refresh(client, admin_headers, make_user):
    # Review Focus 5.
    user = make_user(email="manuel@test.fr", verified=False)
    creds = {"email": "manuel@test.fr", "password": "motdepasse1"}
    assert client.post("/api/auth/login", json=creds).status_code == 403
    _verify_by_admin(client, admin_headers, user)
    login = client.post("/api/auth/login", json=creds)
    assert login.status_code == 200
    assert "refresh_token_cookie" in " ".join(login.headers.getlist("Set-Cookie"))


def test_the_users_list_carries_the_flag(client, admin_headers, make_user):
    make_user(email="flag@test.fr", verified=False)
    users = client.get("/api/admin/users", headers=admin_headers).get_json()["users"]
    assert {u["email"]: u["email_verified"] for u in users}["flag@test.fr"] is False


def test_unverified_demandes_stay_out_of_the_queue(client, admin_headers, make_user):
    _demande(make_user, "vu@test.fr", verified=True)
    _demande(make_user, "pasvu@test.fr", verified=False)
    rows = client.get("/api/admin/counselor-applications", headers=admin_headers).get_json()["applications"]
    emails = {row["user"]["email"] for row in rows}
    assert emails == {"vu@test.fr"}


def test_an_unverified_demande_cannot_be_approved(client, admin_headers, make_user):
    _user, profile = _demande(make_user, "pasvu@test.fr", verified=False)
    res = client.post(f"/api/admin/counselor-applications/{profile.id}/approve",
                      json={}, headers=admin_headers)
    assert res.status_code == 409
    db.session.expire_all()
    assert db.session.get(CounselorProfile, profile.id).status == "pending"
```

(`CounselorProfile.to_dict(with_user=True)` nests `user.to_dict()` under `"user"` — `models/counselor_profile.py:134-135` — hence `row["user"]["email"]`.)

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && venv/bin/pytest tests/test_admin_email_verification.py -v`
Expected: FAIL — 404/405 on `verify-email`, unverified demande listed, approve answers 200.

- [ ] **Step 3: Implement**

In `backend/app/routes/admin.py`:

1. After `set_user_role`, add:

```python
@admin_bp.post("/users/<user_id>/verify-email")
@admin_required
def verify_user_email(user_id):
    """Mark an address verified by hand: a test account with no inbox, or a
    real person whose link landed in spam (email verification spec, decision
    15). Idempotent; there is no undo, by design."""
    user = User.query.get_or_404(user_id)
    if user.email_verified_at is None:
        user.email_verified_at = datetime.utcnow()
        db.session.commit()
    return jsonify({"user": user.to_dict()}), 200
```

2. In `list_counselor_applications`, replace `query = CounselorProfile.query` with:

```python
    # A demande from an address nobody has proven is not admin work yet
    # (email verification spec, decision 16): it shows once its link is
    # opened. Two FKs point at users, so the join names its column.
    query = (
        CounselorProfile.query
        .join(User, CounselorProfile.user_id == User.id)
        .filter(User.email_verified_at.isnot(None))
    )
```

3. In `approve_counselor_application`, right after the `if profile.status != "pending":` block, add:

```python
    # Defence in depth beside the queue filter: the id can be posted without
    # the list.
    if profile.user.email_verified_at is None:
        return jsonify({"error": "L'adresse email de ce compte n'est pas encore vérifiée."}), 409
```

- [ ] **Step 4: Run the tests to verify they pass, then the whole suite**

Run: `cd backend && venv/bin/pytest tests/test_admin_email_verification.py tests/test_counselor_review.py -v` → all PASS.
Run: `cd backend && venv/bin/pytest -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/admin.py backend/tests/test_admin_email_verification.py
git commit -m "$(cat <<'EOF'
feat(admin): verify an address by hand, keep unproven demandes out

« Marquer comme vérifiée » covers test accounts and mail lost to spam.
A demande from an unverified account never reaches the queue, and
approving one by id is refused.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: nginx limits, nginx reload on deploy, environment

**Files:**
- Modify: `nginx/templates-http/default.conf.template`
- Modify: `nginx/templates-https/default.conf.template`
- Modify: `nginx/dev.conf`
- Modify: `.github/workflows/deploy.yml`
- Modify: `docker-compose.yml`, `.env.example`, `backend/.env.example`

**Interfaces:**
- Produces: HTTP 429 after ~4 rapid calls per IP to `register` / `resend-verification` / `forgot-password` / `counselor/apply`, after ~6 to `login` / `verify-email` / `reset-password`; `APP_URL` set in every environment.

- [ ] **Step 1: Add the limits to all three nginx configs**

At the **top** of `nginx/templates-http/default.conf.template` and `nginx/templates-https/default.conf.template` (after their leading comment lines, before the first `server {`), and in `nginx/dev.conf` right after the existing `map $http_upgrade ... { ... }` block, insert:

```nginx
# Per-IP limits on the auth endpoints (email verification spec, decision 21).
# Each map turns every other URI into an empty key, which limit_req does not
# count, so the rest of /api/ is untouched. envsubst leaves $uri and
# $binary_remote_addr alone: it only replaces names set in the environment.
map $uri $auth_mail_key {
    ~^/api/(auth/(register|resend-verification|forgot-password)|counselor/apply)/?$  $binary_remote_addr;
    default "";
}
map $uri $auth_login_key {
    ~^/api/auth/(login|verify-email|reset-password)/?$  $binary_remote_addr;
    default "";
}
limit_req_zone $auth_mail_key  zone=auth_mail:10m  rate=5r/m;
limit_req_zone $auth_login_key zone=auth_login:10m rate=10r/m;
limit_req_status 429;
```

Then inside each file's `location /api/ {` block (in the https template it is the one in the apex `server` on 443 — the only `/api/` location in that file), add as the first two lines:

```nginx
        limit_req zone=auth_mail  burst=3 nodelay;
        limit_req zone=auth_login burst=5 nodelay;
```

- [ ] **Step 2: Validate both production templates**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
docker run --rm -e DOMAIN=localhost --add-host backend:127.0.0.1 --add-host frontend:127.0.0.1 \
  -v "$PWD/nginx/templates-http:/etc/nginx/templates:ro" nginx:1.29-alpine nginx -t

CERTS=$(mktemp -d) && mkdir -p "$CERTS/live/localhost" && \
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=localhost" \
  -keyout "$CERTS/live/localhost/privkey.pem" -out "$CERTS/live/localhost/fullchain.pem" 2>/dev/null && \
docker run --rm -e DOMAIN=localhost --add-host backend:127.0.0.1 --add-host frontend:127.0.0.1 \
  -v "$PWD/nginx/templates-https:/etc/nginx/templates:ro" -v "$CERTS:/etc/letsencrypt:ro" \
  nginx:1.29-alpine nginx -t; rm -rf "$CERTS"
```

Expected, twice: `nginx: configuration file /etc/nginx/nginx.conf test is successful`.

- [ ] **Step 3: Reload nginx on deploy**

In `.github/workflows/deploy.yml`, in the « Pull images & restart stack » script, replace:

```yaml
            docker compose -f docker-compose.prod.yml up -d
            docker image prune -f
```

with:

```yaml
            docker compose -f docker-compose.prod.yml up -d
            # Templates render only at container start, and `up -d` leaves an
            # unchanged nginx service running — so a template change never
            # applied. Re-render and reload in place; nginx -t guards the
            # reload, so a bad config keeps the old one serving and fails the
            # job (set -e) instead of taking the site down.
            docker compose -f docker-compose.prod.yml exec -T nginx sh -c \
              '/docker-entrypoint.d/20-envsubst-on-templates.sh >/dev/null && nginx -t && nginx -s reload'
            docker image prune -f
```

- [ ] **Step 4: Set `APP_URL` everywhere**

- `docker-compose.yml`, in the `backend` service's `environment:` block, add `APP_URL: http://localhost:8080` under `FRONTEND_URL`.
- `backend/.env.example`: add `APP_URL=http://localhost:8080` on the line after `MAIL_FROM=...`.
- `.env.example` (root, production): replace the `# ---- Email ----` section with:

```
# ---- Email ----
RESEND_API_KEY=re_...
# Sender shown to recipients. The domain must be verified in Resend.
MAIL_FROM=neoori <bonjour@neoori.tech>
# Public origin the account mails link to (verification, reset, conseiller).
APP_URL=https://app.example.fr
```

(The production `.env` on the VPS already holds `RESEND_API_KEY`, `MAIL_FROM` and `APP_URL=https://neoori.tech` since 2026-10-01.)

- [ ] **Step 5: See the limits work on the dev stack**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
docker compose up -d
docker compose restart nginx      # dev.conf is bind-mounted: a running nginx keeps the old one
docker compose exec nginx nginx -t
for i in $(seq 1 7); do curl -s -o /dev/null -w "%{http_code} " -X POST http://localhost:8080/api/auth/forgot-password \
  -H 'Content-Type: application/json' -d '{"email":"personne@test.fr"}'; done; echo
```

Expected: `nginx -t` successful, then `200 200 200 200 429 429 429` (1 + burst 3).

- [ ] **Step 6: Commit**

```bash
git add nginx/templates-http/default.conf.template nginx/templates-https/default.conf.template nginx/dev.conf \
  .github/workflows/deploy.yml docker-compose.yml .env.example backend/.env.example
git commit -m "$(cat <<'EOF'
feat(infra): per-IP limits on the auth endpoints, reload nginx on deploy

Signup, resend, forgot and the conseiller demande send mail from a
public endpoint; Resend's free plan is 100 a day, so one script could
lock every real signup out. Login, verify and reset check a secret.

The deploy copied nginx templates but never re-rendered them: up -d
leaves an unchanged nginx running. It now re-renders and reloads,
guarded by nginx -t.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Frontend foundations — types, auth client, proxy, pending component

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/auth.tsx`
- Modify: `frontend/src/lib/counselor.ts`
- Modify: `frontend/src/proxy.ts`
- Create: `frontend/src/components/auth/VerificationPending.tsx`

**Interfaces:**
- Consumes: the endpoints of Tasks 4–6.
- Produces:
  - `User.email_verified: boolean`
  - `useAuth().register(email, password, seed?, next?) => Promise<{ mail_sent: boolean }>` (no session)
  - `useAuth().login` throws `ApiError` (status 403, `body.code === "email_unverified"`) instead of reloading the page on 401
  - `counselor.apply(...)` resolves `{ user, profile, mail_sent?: boolean }`
  - `<VerificationPending email next? variant? mailSent? onRestart? restartLabel? />`

- [ ] **Step 1: Types and API clients**

In `frontend/src/types/index.ts`, add to `interface User` after `credits_remaining`:

```ts
  /** False until the address is proven; no session exists before that. */
  email_verified: boolean
```

In `frontend/src/lib/counselor.ts`, change the `apply` return type to:

```ts
  apply: (payload: ApplyPayload) =>
    api.post<{ user: User; profile: CounselorProfile; mail_sent?: boolean }>("/counselor/apply", payload),
```

In `frontend/src/lib/auth.tsx`:

1. Change the `register` line of `AuthContextValue` to:

```ts
  /** Creates the account and mails the confirmation link. No session: the
   *  person signs in from the link, with their password. */
  register: (email: string, password: string, seed?: ProfileSeed, next?: string | null) => Promise<{ mail_sent: boolean }>
```

2. Replace the `login` and `register` implementations with:

```ts
  const login = async (email: string, password: string) => {
    // skipRedirect: a 401 here is « Identifiants incorrects. » and a 403 is an
    // unconfirmed address — both for the page to show. Without it api.ts
    // reloaded /connexion on a wrong password and the message was lost.
    const data = await api.post<{ user: User }>("/auth/login", { email, password }, { skipRedirect: true })
    setUser(data.user)
    return data.user
  }

  const register = async (email: string, password: string, seed?: ProfileSeed, next?: string | null) => {
    const data = await api.post<{ user: User; mail_sent: boolean }>(
      "/auth/register",
      { email, password, ...seed, next: next ?? undefined },
      { skipRedirect: true },
    )
    return { mail_sent: data.mail_sent }
  }
```

- [ ] **Step 2: The proxy**

Replace `frontend/src/proxy.ts` with:

```ts
import { NextRequest, NextResponse } from "next/server"

/** Routes that need an account. Gated at the edge so no page ever renders a
 *  form the user can fill and then lose at submit. */
const PROTECTED = ["/admin", "/conseiller", "/profil", "/voyage", "/espace", "/analyse"]

/** Where a signed-out visitor on these lands instead of /connexion. The
 *  analysis form is where new people arrive from the landing page, so it opens
 *  on signup — and the redirect survives the confirmation email, because it
 *  travels inside the link. */
const SIGNUP_FIRST = ["/analyse"]

export function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl

  if (!PROTECTED.some((p) => pathname.startsWith(p))) return NextResponse.next()

  // Presence only — the signature and the role are enforced server-side.
  const hasToken = req.cookies.has("access_token_cookie")
  if (!hasToken) {
    const url = req.nextUrl.clone()
    url.pathname = SIGNUP_FIRST.some((p) => pathname.startsWith(p)) ? "/inscription" : "/connexion"
    url.search = ""
    url.searchParams.set("redirect", pathname + search)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

// Next 16 reads `config`, not `proxyConfig` — under the old name this matcher
// was ignored, so the proxy ran on every request including static assets.
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.png$).*)"],
}
```

- [ ] **Step 3: The pending component**

Create `frontend/src/components/auth/VerificationPending.tsx`:

```tsx
"use client"

import { useEffect, useState } from "react"
import { api, ApiError } from "@/lib/api"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

/** Mirrors auth_mail.COOLDOWN on the server: one account mail a minute. */
const COOLDOWN_S = 60

interface Props {
  email: string
  /** Where the link should land once confirmed, when the page knows. */
  next?: string | null
  /** "sent": a link just left (signup, demande). "login": the account exists
   *  unconfirmed and nothing was sent this time. */
  variant?: "sent" | "login"
  /** False when the server could not hand the first mail to the provider. */
  mailSent?: boolean
  onRestart?: () => void
  restartLabel?: string
}

export function VerificationPending({
  email,
  next,
  variant = "sent",
  mailSent = true,
  onRestart,
  restartLabel = "Mauvaise adresse ? Recommencer",
}: Props) {
  const justSent = variant === "sent" && mailSent
  const [wait, setWait] = useState(justSent ? COOLDOWN_S : 0)
  const [failed, setFailed] = useState(variant === "sent" && !mailSent)
  const [notice, setNotice] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (wait <= 0) return
    const t = setTimeout(() => setWait((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [wait])

  const resend = async () => {
    setSending(true)
    setNotice(null)
    try {
      await api.post("/auth/resend-verification", { email, next: next ?? undefined }, { skipRedirect: true })
      setFailed(false)
      setNotice("Un nouveau lien vient d’être envoyé. Pensez à regarder dans les courriers indésirables.")
      setWait(COOLDOWN_S)
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : "Erreur lors de l’envoi.")
    } finally {
      setSending(false)
    }
  }

  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-navy">
        {variant === "sent" ? "Vérifiez votre boîte mail" : "Confirmez votre adresse"}
      </h1>
      {variant === "sent" ? (
        <p className="mt-3 text-sm text-muted-foreground">
          Un lien de confirmation a été envoyé à <strong className="text-navy">{email}</strong>.
          Ouvrez-le dans les 48 heures et saisissez votre mot de passe : votre compte sera activé.
        </p>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          Votre compte n’est pas encore activé. Ouvrez le lien envoyé à{" "}
          <strong className="text-navy">{email}</strong> lors de l’inscription, ou demandez-en un nouveau.
        </p>
      )}

      {failed && (
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>L’envoi a échoué. Réessayez dans un instant.</AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert className="mt-4">
          <AlertDescription className="text-sm text-foreground">{notice}</AlertDescription>
        </Alert>
      )}

      <Button
        type="button"
        variant="outline"
        className="mt-6 h-11 w-full"
        disabled={wait > 0 || sending}
        onClick={resend}
      >
        {sending ? "Envoi…" : wait > 0 ? `Renvoyer le lien (${wait} s)` : "Renvoyer le lien"}
      </Button>

      {onRestart && (
        <button
          type="button"
          onClick={onRestart}
          className="link-underline mt-4 block w-full text-center text-sm font-medium text-orange-dark"
        >
          {restartLabel}
        </button>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Type-check and lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: clean. (`/inscription` still ignores `register()`'s new return value and pushes to `/espace` until Task 11 — that compiles, it is just the old behaviour.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/auth.tsx frontend/src/lib/counselor.ts \
  frontend/src/proxy.ts frontend/src/components/auth/VerificationPending.tsx
git commit -m "$(cat <<'EOF'
feat(auth): client contract for the verification gate

register no longer signs in; login surfaces 401 and 403 to the page
instead of reloading /connexion. The proxy gates /analyse and /espace,
sends /analyse visitors to signup, and keeps the query string. A shared
« Vérifiez votre boîte mail » screen with a paced resend.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Signup, login and conseiller pages

**Files:**
- Modify: `frontend/src/app/(auth)/inscription/page.tsx`
- Modify: `frontend/src/app/(auth)/connexion/page.tsx`
- Modify: `frontend/src/app/(auth)/inscription-conseiller/page.tsx`

**Interfaces:**
- Consumes: `useAuth().register/login` and `VerificationPending` (Task 10).

- [ ] **Step 1: `/inscription`**

Replace `frontend/src/app/(auth)/inscription/page.tsx` with (schema and fields unchanged; what changes is the `Suspense` wrapper, `redirect` handling, the pending screen and the 409 links):

```tsx
"use client"

import { Suspense, useState } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { Controller, useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useAuth } from "@/lib/auth"
import { ApiError } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"
import { VerificationPending } from "@/components/auth/VerificationPending"
import { TRANCHES_AGE } from "@/lib/profile-options"

// Prénom and tranche d'âge are asked here because session_lock has demanded
// them before session 1 since the voyage shipped. Asking mid-journey means
// bouncing someone out of the sessions and into a form; this is the one moment
// they are already filling one.
const schema = z
  .object({
    prenom: z.string().min(1, "Prénom requis."),
    tranche_age: z.string().min(1, "Tranche d'âge requise."),
    email: z.string().email("Email invalide."),
    password: z.string().min(8, "8 caractères minimum."),
    confirm: z.string(),
    consent: z.boolean().refine((v) => v === true, {
      message: "Veuillez accepter les CGV et la politique de confidentialité.",
    }),
  })
  .refine((d) => d.password === d.confirm, {
    message: "Les mots de passe ne correspondent pas.",
    path: ["confirm"],
  })
type Fields = z.infer<typeof schema>

function InscriptionForm() {
  const { register: registerUser } = useAuth()
  const params = useSearchParams()
  // Where they were heading (the proxy sends /analyse/* here). It travels in
  // the confirmation link, so the email round-trip lands them back on it.
  const next = params.get("redirect")
  const [error, setError] = useState<string | null>(null)
  const [taken, setTaken] = useState(false)
  const [pending, setPending] = useState<{ email: string; mailSent: boolean } | null>(null)

  const { register, control, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { consent: false, prenom: "", tranche_age: "" },
  })

  const onSubmit = async ({ email, password, prenom, tranche_age, consent }: Fields) => {
    setError(null)
    setTaken(false)
    try {
      const { mail_sent } = await registerUser(email, password, { prenom, tranche_age, consent }, next)
      setPending({ email, mailSent: mail_sent })
    } catch (e) {
      // 409: the address already has an account, confirmed or not. Signing in
      // or resetting the password is the way back — never a second account.
      setTaken(e instanceof ApiError && e.status === 409)
      setError(e instanceof ApiError ? e.message : "Erreur lors de la création du compte.")
    }
  }

  const connexionHref = next ? `/connexion?redirect=${encodeURIComponent(next)}` : "/connexion"

  if (pending) {
    return (
      <AuthLayout>
        <VerificationPending
          email={pending.email}
          next={next}
          mailSent={pending.mailSent}
          onRestart={() => { reset(); setPending(null) }}
        />
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-bold text-navy">Créer un compte</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">Gratuit · 1 analyse offerte.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>
              {error}
              {taken && (
                <span className="mt-1.5 block">
                  <Link href={connexionHref} className="underline underline-offset-2">Se connecter</Link>
                  {" · "}
                  <Link href="/mot-de-passe-oublie" className="underline underline-offset-2">Mot de passe oublié ?</Link>
                </span>
              )}
            </AlertDescription>
          </Alert>
        )}

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
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" className="h-10" placeholder="vous@exemple.fr" {...register("email")} />
          {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password">Mot de passe</Label>
          <Input id="password" type="password" autoComplete="new-password" className="h-10" placeholder="8 caractères minimum" {...register("password")} />
          {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="confirm">Confirmer le mot de passe</Label>
          <Input id="confirm" type="password" autoComplete="new-password" className="h-10" placeholder="••••••••" {...register("confirm")} />
          {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
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

      <p className="mt-5 text-center text-sm text-muted-foreground">
        Déjà un compte ?{" "}
        <Link href={connexionHref} className="link-underline font-medium text-orange-dark">
          Se connecter
        </Link>
      </p>

      <p className="mt-2 text-center text-sm text-muted-foreground">
        Vous accompagnez des demandeurs d&apos;emploi ?{" "}
        <Link href="/inscription-conseiller" className="link-underline font-medium text-orange-dark">
          Demander un compte conseiller
        </Link>
      </p>
    </AuthLayout>
  )
}

export default function InscriptionPage() {
  return (
    <Suspense>
      <InscriptionForm />
    </Suspense>
  )
}
```

- [ ] **Step 2: `/connexion`**

In `frontend/src/app/(auth)/connexion/page.tsx`:

1. Add the import `import { VerificationPending } from "@/components/auth/VerificationPending"`.
2. Inside `ConnexionForm`, after `const [error, setError] = ...`, add:

```tsx
  const redirect = params.get("redirect")
  // Right password, unconfirmed address: the server says so only to someone
  // who knows the password (spec decision 9). Holds the address to resend to.
  const [unverified, setUnverified] = useState<string | null>(null)
```

3. Replace `onSubmit` with:

```tsx
  const onSubmit = async ({ email, password }: Fields) => {
    setError(null)
    try {
      const signedIn = await login(email, password)
      // A ?redirect= still wins — it is the page they were turned away from.
      // Otherwise each role lands on its own home rather than the candidate
      // espace: an admin in Administration, an approved conseiller in their
      // espace conseiller.
      router.push(redirect ?? homeFor(signedIn.role))
    } catch (e) {
      if (e instanceof ApiError && e.body?.code === "email_unverified") {
        setUnverified(email)
        return
      }
      setError(e instanceof ApiError ? e.message : "Erreur de connexion.")
    }
  }

  const inscriptionHref = redirect ? `/inscription?redirect=${encodeURIComponent(redirect)}` : "/inscription"

  if (unverified) {
    return (
      <AuthLayout>
        <VerificationPending
          variant="login"
          email={unverified}
          next={redirect}
          onRestart={() => setUnverified(null)}
          restartLabel="Retour à la connexion"
        />
      </AuthLayout>
    )
  }
```

4. Replace the password field block with one that carries the reset link:

```tsx
        <div className="space-y-1.5">
          <div className="flex items-baseline justify-between">
            <Label htmlFor="password">Mot de passe</Label>
            <Link href="/mot-de-passe-oublie" className="text-xs text-muted-foreground underline underline-offset-2">
              Mot de passe oublié ?
            </Link>
          </div>
          <Input id="password" type="password" autoComplete="current-password" className="h-10" placeholder="••••••••" {...register("password")} />
          {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
        </div>
```

5. Change the « Créer un compte » link's `href="/inscription"` to `href={inscriptionHref}`.

- [ ] **Step 3: `/inscription-conseiller`**

In `frontend/src/app/(auth)/inscription-conseiller/page.tsx`:

1. Add the import `import { VerificationPending } from "@/components/auth/VerificationPending"`.
2. After `const [showPassword, setShowPassword] = useState(false)`, add:

```tsx
  // Set when the demande created a new account: it opens once its address is
  // confirmed, so the person is sent to their inbox, not to /conseiller.
  const [pending, setPending] = useState<{ email: string; mailSent: boolean } | null>(null)
```

3. In `onSubmit`, replace from `await counselor.apply({` through `setTimeout(() => router.push("/conseiller"), 3000)` so that the result is kept and the no-account path stops before `refresh()`:

```tsx
      const res = await counselor.apply({
        structure: values.structure,
        type_structure: values.type_structure as TypeStructure,
        type_structure_autre: values.type_structure === "autre" ? values.type_structure_autre : undefined,
        siret: values.siret ? values.siret.replace(/\s+/g, "") : undefined,
        adresse_rue: values.adresse_rue,
        adresse_code_postal: values.adresse_code_postal,
        adresse_ville: values.adresse_ville,
        domaines: values.domaines as DomaineActivite[],
        nom_complet: values.nom_complet,
        fonction: values.fonction,
        telephone: values.telephone,
        consent: values.consent,
        consent_donnees: values.consent_donnees,
        email: values.email,
        password: values.password,
      })
      if (!user) {
        // No session before the submit: the account was created just now and
        // opens once its address is confirmed. The link lands on /conseiller.
        setPending({ email: values.email, mailSent: res.mail_sent ?? false })
        return
      }
      // A signed-in candidate keeps their session; refresh() puts the demande's
      // user in context before the /conseiller page reads it. The panel below
      // shows for a moment first so the 48h-delay message cannot be missed.
      await refresh()
      setSubmitted(true)
      setTimeout(() => router.push("/conseiller"), 3000)
```

4. Immediately before `if (submitted) {`, add:

```tsx
  if (pending) {
    return (
      <AuthLayout>
        <VerificationPending
          email={pending.email}
          next="/conseiller"
          mailSent={pending.mailSent}
          onRestart={() => setPending(null)}
        />
        <p className="mt-6 text-sm text-muted-foreground">
          Votre demande est enregistrée. Elle sera examinée dès votre adresse confirmée, sous 48 h ouvrées.
        </p>
      </AuthLayout>
    )
  }
```

- [ ] **Step 4: Type-check, lint, build**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected: no type errors, no lint errors, build succeeds (the three pages using `useSearchParams` are inside `Suspense`).

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(auth)/inscription/page.tsx" "frontend/src/app/(auth)/connexion/page.tsx" \
  "frontend/src/app/(auth)/inscription-conseiller/page.tsx"
git commit -m "$(cat <<'EOF'
feat(auth): signup, login and demande pages wait for the confirmed address

Signup and a no-account demande end on « Vérifiez votre boîte mail ».
Login of an unconfirmed account offers a new link; a taken address
offers sign-in or reset. The redirect travels through all of it.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: The three link pages

**Files:**
- Create: `frontend/src/app/(auth)/verifier-email/page.tsx`
- Create: `frontend/src/app/(auth)/mot-de-passe-oublie/page.tsx`
- Create: `frontend/src/app/(auth)/reinitialiser-mot-de-passe/page.tsx`

**Interfaces:**
- Consumes: `POST /auth/verify-email/check`, `/auth/verify-email`, `/auth/resend-verification`, `/auth/forgot-password`, `/auth/reset-password` (Task 5); `useAuth().refresh`; `homeFor`.

- [ ] **Step 1: `/verifier-email`**

Create `frontend/src/app/(auth)/verifier-email/page.tsx`:

```tsx
"use client"

import { Suspense, useEffect, useState, type FormEvent } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { useAuth } from "@/lib/auth"
import { homeFor } from "@/lib/home"
import { api, ApiError } from "@/lib/api"
import type { User } from "@/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"

const INVALID = "Ce lien n’est pas valide. Demandez-en un nouveau."

type LinkState =
  | { kind: "checking" }
  | { kind: "ready"; email: string }
  | { kind: "dead"; message: string }

/** The link plus the password chosen at signup: that pair, not the link
 *  alone, opens the account (spec decision 8 — pre-account hijacking). */
function VerifierEmail() {
  const params = useSearchParams()
  const router = useRouter()
  const { refresh } = useAuth()
  const token = params.get("token") ?? ""
  const [state, setState] = useState<LinkState>(() =>
    token ? { kind: "checking" } : { kind: "dead", message: INVALID },
  )
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [resendEmail, setResendEmail] = useState("")
  const [resent, setResent] = useState(false)

  useEffect(() => {
    if (!token) return
    let live = true
    api.post<{ email: string }>("/auth/verify-email/check", { token }, { skipRedirect: true })
      .then((r) => { if (live) setState({ kind: "ready", email: r.email }) })
      .catch((e) => { if (live) setState({ kind: "dead", message: e instanceof ApiError ? e.message : INVALID }) })
    return () => { live = false }
  }, [token])

  const confirm = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const res = await api.post<{ user: User; next: string | null }>(
        "/auth/verify-email", { token, password }, { skipRedirect: true },
      )
      await refresh()
      router.push(res.next ?? homeFor(res.user.role))
    } catch (err) {
      const code = err instanceof ApiError ? err.body?.code : undefined
      if (code === "wrong_password") setError("Mot de passe incorrect.")
      else if (code === "link_expired" || code === "link_invalid") setState({ kind: "dead", message: (err as ApiError).message })
      else setError(err instanceof ApiError ? err.message : "Erreur inattendue.")
    } finally {
      setSubmitting(false)
    }
  }

  const resend = async (e: FormEvent) => {
    e.preventDefault()
    await api.post("/auth/resend-verification", { email: resendEmail }, { skipRedirect: true }).catch(() => {})
    setResent(true)
  }

  if (state.kind === "checking") {
    return <p className="text-sm text-muted-foreground">Vérification du lien…</p>
  }

  if (state.kind === "dead") {
    return (
      <>
        <h1 className="font-display text-2xl font-bold text-navy">Lien expiré ou invalide</h1>
        <Alert variant="destructive" className="mt-6"><AlertDescription>{state.message}</AlertDescription></Alert>
        {resent ? (
          <Alert className="mt-6">
            <AlertDescription className="text-sm text-foreground">
              Si cette adresse attend une confirmation, un nouveau lien vient d’être envoyé.
            </AlertDescription>
          </Alert>
        ) : (
          <form onSubmit={resend} className="mt-6 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="resend-email">Email du compte</Label>
              <Input id="resend-email" type="email" autoComplete="email" className="h-10" required
                value={resendEmail} onChange={(e) => setResendEmail(e.target.value)} />
            </div>
            <Button type="submit" size="lg" className="h-11 w-full">Recevoir un nouveau lien</Button>
          </form>
        )}
        <p className="mt-5 text-center text-sm text-muted-foreground">
          <Link href="/connexion" className="link-underline font-medium text-orange-dark">Retour à la connexion</Link>
        </p>
      </>
    )
  }

  return (
    <>
      <h1 className="font-display text-2xl font-bold text-navy">Confirmez votre adresse</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Saisissez le mot de passe choisi à l’inscription pour activer votre compte.
      </p>
      <form onSubmit={confirm} className="mt-7 space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>
              {error}{" "}
              <Link href="/mot-de-passe-oublie" className="underline underline-offset-2">Mot de passe oublié ?</Link>
            </AlertDescription>
          </Alert>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="username" className="h-10" value={state.email} readOnly />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Mot de passe</Label>
          <Input id="password" type="password" autoComplete="current-password" className="h-10" required
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <Button type="submit" size="lg" className="h-11 w-full" disabled={submitting || !password}>
          {submitting ? "Activation…" : "Activer mon compte"}
        </Button>
      </form>
    </>
  )
}

export default function VerifierEmailPage() {
  return (
    <AuthLayout>
      <Suspense>
        <VerifierEmail />
      </Suspense>
    </AuthLayout>
  )
}
```

- [ ] **Step 2: `/mot-de-passe-oublie`**

Create `frontend/src/app/(auth)/mot-de-passe-oublie/page.tsx`:

```tsx
"use client"

import { useState } from "react"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { api, ApiError } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"

const schema = z.object({ email: z.string().email("Email invalide.") })
type Fields = z.infer<typeof schema>

export default function MotDePasseOubliePage() {
  const [done, setDone] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async ({ email }: Fields) => {
    setError(null)
    try {
      // The same sentence comes back whether or not the address has an
      // account (spec decision 11) — it is shown as is.
      const res = await api.post<{ message: string }>("/auth/forgot-password", { email }, { skipRedirect: true })
      setDone(res.message)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
    }
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-bold text-navy">Mot de passe oublié</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Indiquez l’adresse de votre compte : vous recevrez un lien pour choisir un nouveau mot de passe, valable 1 heure.
      </p>

      {done ? (
        <Alert className="mt-7">
          <AlertDescription className="text-sm text-foreground">
            {done} Pensez à regarder dans les courriers indésirables.
          </AlertDescription>
        </Alert>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
          {error && (
            <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" className="h-10" placeholder="vous@exemple.fr" {...register("email")} />
            {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
          </div>
          <Button type="submit" size="lg" className="h-11 w-full" disabled={isSubmitting}>
            {isSubmitting ? "Envoi…" : "Recevoir le lien"}
          </Button>
        </form>
      )}

      <p className="mt-5 text-center text-sm text-muted-foreground">
        <Link href="/connexion" className="link-underline font-medium text-orange-dark">Retour à la connexion</Link>
      </p>
    </AuthLayout>
  )
}
```

- [ ] **Step 3: `/reinitialiser-mot-de-passe`**

Create `frontend/src/app/(auth)/reinitialiser-mot-de-passe/page.tsx`:

```tsx
"use client"

import { Suspense, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useAuth } from "@/lib/auth"
import { homeFor } from "@/lib/home"
import { api, ApiError } from "@/lib/api"
import type { User } from "@/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"

const INVALID = "Ce lien n’est pas valide. Demandez-en un nouveau."

const schema = z
  .object({
    password: z.string().min(8, "8 caractères minimum."),
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, {
    message: "Les mots de passe ne correspondent pas.",
    path: ["confirm"],
  })
type Fields = z.infer<typeof schema>

function Reinitialiser() {
  const params = useSearchParams()
  const router = useRouter()
  const { refresh } = useAuth()
  const token = params.get("token") ?? ""
  const [dead, setDead] = useState<string | null>(token ? null : INVALID)
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async ({ password }: Fields) => {
    setError(null)
    try {
      const res = await api.post<{ user: User }>("/auth/reset-password", { token, password }, { skipRedirect: true })
      await refresh()
      router.push(homeFor(res.user.role))
    } catch (e) {
      const code = e instanceof ApiError ? e.body?.code : undefined
      if (code === "link_expired" || code === "link_invalid") setDead((e as ApiError).message)
      else setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
    }
  }

  return (
    <>
      <h1 className="font-display text-2xl font-bold text-navy">Nouveau mot de passe</h1>
      {dead ? (
        <>
          <Alert variant="destructive" className="mt-6"><AlertDescription>{dead}</AlertDescription></Alert>
          <p className="mt-5 text-center text-sm">
            <Link href="/mot-de-passe-oublie" className="link-underline font-medium text-orange-dark">
              Demander un nouveau lien
            </Link>
          </p>
        </>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
          {error && (
            <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="password">Nouveau mot de passe</Label>
            <Input id="password" type="password" autoComplete="new-password" className="h-10" placeholder="8 caractères minimum" {...register("password")} />
            {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="confirm">Confirmer le mot de passe</Label>
            <Input id="confirm" type="password" autoComplete="new-password" className="h-10" placeholder="••••••••" {...register("confirm")} />
            {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
          </div>
          <Button type="submit" size="lg" className="h-11 w-full" disabled={isSubmitting}>
            {isSubmitting ? "Enregistrement…" : "Enregistrer et me connecter"}
          </Button>
        </form>
      )}
    </>
  )
}

export default function ReinitialiserMotDePassePage() {
  return (
    <AuthLayout>
      <Suspense>
        <Reinitialiser />
      </Suspense>
    </AuthLayout>
  )
}
```

- [ ] **Step 4: Type-check, lint, build**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected: clean; the build lists `/verifier-email`, `/mot-de-passe-oublie`, `/reinitialiser-mot-de-passe`.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(auth)/verifier-email/page.tsx" "frontend/src/app/(auth)/mot-de-passe-oublie/page.tsx" \
  "frontend/src/app/(auth)/reinitialiser-mot-de-passe/page.tsx"
git commit -m "$(cat <<'EOF'
feat(auth): the verify, forgot and reset pages

The verify page checks the link first, then asks for the password chosen
at signup. A dead link offers a new one. The reset page signs in on
success and points to a new link when this one is spent.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: Admin users column and the privacy page

**Files:**
- Modify: `frontend/src/app/admin/utilisateurs/page.tsx`
- Modify: `frontend/src/app/(legal)/confidentialite/page.tsx`

**Interfaces:**
- Consumes: `POST /api/admin/users/<id>/verify-email` (Task 8), `User.email_verified` (Task 10).

- [ ] **Step 1: The « Adresse » column**

In `frontend/src/app/admin/utilisateurs/page.tsx`:

1. Add the import `import { Button } from "@/components/ui/button"`.
2. After the `rowError` state, add:

```tsx
  const [verifyingId, setVerifyingId] = useState<string | null>(null)

  // For a test account with no inbox, or a real person whose link landed in
  // spam (spec decision 15). There is no undo.
  const markVerified = async (id: string) => {
    setVerifyingId(id)
    setRowError((current) => ({ ...current, [id]: "" }))
    try {
      const res = await api.post<{ user: User }>(`/admin/users/${id}/verify-email`)
      setUsers((list) => list.map((u) => (u.id === res.user.id ? res.user : u)))
    } catch (err) {
      setRowError((current) => ({
        ...current,
        [id]: err instanceof ApiError ? err.message : "Échec de la vérification.",
      }))
    } finally {
      setVerifyingId(null)
    }
  }
```

3. In the header row, after `<TableHead className="eyebrow text-navy-500">E-mail</TableHead>`, add:

```tsx
                <TableHead className="eyebrow text-navy-500">Adresse</TableHead>
```

4. Change both `colSpan={5}` to `colSpan={6}`.
5. In the body row, after the e-mail `<TableCell>`, add:

```tsx
                    <TableCell>
                      {u.email_verified ? (
                        <Badge variant="success">Vérifiée</Badge>
                      ) : (
                        <div className="flex items-center gap-2">
                          <Badge variant="warning">Non vérifiée</Badge>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={verifyingId === u.id}
                            onClick={() => void markVerified(u.id)}
                          >
                            Marquer comme vérifiée
                          </Button>
                        </div>
                      )}
                    </TableCell>
```

- [ ] **Step 2: Name Resend as a processor**

In `frontend/src/app/(legal)/confidentialite/page.tsx`, in the list under `<h2>5. Destinataires et sous-traitants</h2>`, after `<li>Stripe (paiement)</li>` add:

```tsx
        <li>Resend (envoi des emails de confirmation et de réinitialisation, États-Unis — clauses contractuelles types)</li>
```

This is legal text: list it for the PM in the hand-off (spec, open question 2).

- [ ] **Step 3: Type-check, lint, build**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build` → clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/admin/utilisateurs/page.tsx "frontend/src/app/(legal)/confidentialite/page.tsx"
git commit -m "$(cat <<'EOF'
feat(admin): show each address's state, mark one verified by hand

The users table gains an « Adresse » column with « Marquer comme
vérifiée ». The privacy page names Resend among the processors.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: End-to-end on the local stack, docs, hand-off

**Files:**
- Modify: `CLAUDE.md` (new section)

- [ ] **Step 1: Full checks**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && venv/bin/pytest -q
cd ../frontend && npx tsc --noEmit && npm run lint && npm run build
```

Expected: every backend test passes (977 baseline + this plan's additions); frontend clean.

- [ ] **Step 2: Walk the flows on http://localhost:8080**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
docker compose up -d --build
grep -c '^RESEND_API_KEY=re_' backend/.env || true
```

If the count is `0`, the link of every mail is printed by `docker compose logs -f backend` (`DEV — no RESEND_API_KEY, link for …`). If it is `1`, real mail leaves: sign up with `nneoori+e2e1@proton.me`, `+e2e2`, … and take the links from that inbox.

Check each, and note the result:

1. Signed out, open `/analyse/nouveau?parcours=2` → lands on `/inscription?redirect=%2Fanalyse%2Fnouveau%3Fparcours%3D2`.
2. Sign up → « Vérifiez votre boîte mail », « Renvoyer le lien (60 s) » counting down.
3. Open the link → email shown, password asked. Wrong password → « Mot de passe incorrect. ». Right one → back on `/analyse/nouveau?parcours=2`, signed in.
4. Sign out, sign in again → works.
5. A second unconfirmed account: sign in → « Confirmez votre adresse » + resend.
6. Sign up again with an existing address → « Un compte existe déjà… » with « Se connecter » · « Mot de passe oublié ? ».
7. `/mot-de-passe-oublie` → same sentence for a known and an unknown address. Reset link → new password → signed in. Open the same reset link again → « Ce lien n'est pas valide ».
8. Conseiller demande while signed out → pending screen; the demande is absent from `/admin/conseillers` until the link is used; after it, the person lands on `/conseiller`.
9. `/admin/utilisateurs` (as `admin@neoori.dev` after `docker compose exec backend python seed_dev.py`) → « Non vérifiée » rows; « Marquer comme vérifiée » flips one; that account can then sign in.
10. Seven rapid `forgot-password` calls (Task 9 Step 5) → `429` from the fifth.

Fix anything that fails in the task that owns it, re-run its tests, and commit there.

- [ ] **Step 3: Document it in CLAUDE.md**

Append to `CLAUDE.md`, before `## Out of scope`:

```markdown
## Email verification

No session for an unproven address. `routes/auth._issue_session()` is the only
place cookies are minted, and it refuses `email_verified_at IS NULL`; signup and
the no-account conseiller demande mail a link instead. Verifying takes the link
**and** the password chosen at signup — the link alone would let someone who
signed up with your address and their password share your account. « Mot de
passe oublié » runs on the same signed links (`utils/auth_links.py`,
itsdangerous, no table); a reset ends every older session through the `pwv`
claim on refresh tokens.

- Mail: Resend, From `MAIL_FROM`, links from `APP_URL`. With no key in dev the
  link is printed in the backend log.
- One account mail a minute per address (`users.auth_mail_sent_at`), plus
  per-IP nginx `limit_req` on the auth endpoints.
- The deploy re-renders and reloads nginx (`deploy.yml`): `up -d` alone never
  applied a template change.
- Analyses and CV uploads require an account; `/analyse/*` sends a signed-out
  visitor to `/inscription`.
- `/admin/utilisateurs` « Marquer comme vérifiée » is the way in for a test
  account or a link lost to spam.

Spec: `docs/superpowers/specs/2026-09-29-email-verification-design.md`
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: how email verification holds together

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Hand off — do not push**

Report to the developer: the branch `feat/email-verification`, the test count, the E2E checklist results, and these points for the PM (spec, open questions): analyses now require an account; the `/confidentialite` line naming Resend; the mail footer now invites replies. Merging to `initial` and pushing deploys — that is the developer's call. Production prerequisites are already in place (DNS verified, `RESEND_API_KEY` / `MAIL_FROM` / `APP_URL` in the VPS `.env`, test sends accepted on 2026-10-01).
