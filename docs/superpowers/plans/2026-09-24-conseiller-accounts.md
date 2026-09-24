# Comptes conseiller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A conseiller signs up, an admin approves or rejects the demande, and an approved conseiller mints their own single-use codes and sees a dashboard of their bénéficiaires and accompagnements.

**Architecture:** One new 1-1 table (`counselor_profiles`) carries the demande and the two admin dials; `counselor_codes` gains an owner and per-code limits; a new `code_redemptions` table logs who redeemed what and when, which `uses_count` never could. One service (`code_service`) owns the redemption path both existing call sites share. One new Flask blueprint at `/api/counselor`, guarded by a decorator that checks the DB and not just the JWT claim. Frontend adds two pages and one admin panel.

**Tech Stack:** Flask 3 + Flask-SQLAlchemy + Flask-JWT-Extended (cookies), Alembic (hand-written migrations), MySQL 8.4 in prod / SQLite in tests, pytest. Next.js 16.2.6 App Router + React 19.2.4, Base UI components, react-hook-form + zod, Tailwind. Resend for email.

**Spec:** `docs/superpowers/specs/2026-09-24-conseiller-accounts-design.md` — read it first; this plan argues from it and every decision number below refers to it.

---

## Global Constraints

- **UI strings are French. Code comments and commit messages are English.** (CLAUDE.md)
- **Banned UI words** — never in French copy: boussole, copilote, miroir, révélation, épanouissement, alignement, excellence, talent unique, vous vous démarquez. Tone: factual, sober, professional, direct.
- **Backend tests run from `backend/`**: `venv/bin/pytest tests/<file>.py -v`. `pytest.ini` sets `testpaths = tests`, `pythonpath = .`.
- **Migrations are hand-written and idempotent** — `backend/entrypoint.sh:24` runs `flask db upgrade` at container start, so a half-applied revision must not wedge the backend. Follow `d6e7f8a9b0c1_profile_sensitive_consent.py`. `tests/test_migration_chain.py` asserts exactly one head: the new revision's `down_revision` is `d6e7f8a9b0c1` and nothing else may claim that parent.
- **Never trust a JSON body's shape.** Use `app/utils/request_body.py` (`json_object`, `text_field`, `raw_text_field`). A bare array or a non-string field reaching `.strip()` is an unhandled 500 — this codebase has fixed that defect three times.
- **Role claims live in the JWT, not the DB.** `role_required` (`app/utils/decorators.py:13`) reads `get_jwt()["role"]`. Access TTL is 1 h (`config.py:23`). Any check that must bite immediately reads the DB.
- **Frontend:** read `frontend/AGENTS.md` before writing components — this is Next.js 16.2.6 and the bundled docs in `frontend/node_modules/next/dist/docs/` are authoritative over memory. Every pattern this plan uses is copied from a file already working in this repo; copy the idiom rather than inventing one.
- **Base UI convention:** `render={<Link href="…" />}`, **not** `asChild`.
- **⚠ Another session holds uncommitted edits** in: `frontend/src/app/page.tsx`, `layout.tsx`, `(auth)/connexion/page.tsx`, `(legal)/cgv/page.tsx`, `(legal)/confidentialite/page.tsx`, `espace/page.tsx`, `analyse/en-cours/[id]/page.tsx`, `components/layout/AuthLayout.tsx`, `SiteNav.tsx`, `SiteFooter.tsx`, `backend/app/routes/payments.py`. **Task 14 touches two of them.** Always `git add` by explicit path — never `git add -A`, never `git commit -a`.
- Port 3001 may be occupied by another session's `next dev`.

---

## File Structure

**Backend — create**

| File | Responsibility |
|---|---|
| `app/models/counselor_profile.py` | the demande: fields, status, the two admin dials |
| `app/models/code_redemption.py` | one row per redemption — who, what, when |
| `app/services/code_service.py` | normalise, resolve (3 refusals), record. The only redemption path |
| `app/services/email_service.py` | Resend transport + the two FR templates. Fail-soft |
| `app/routes/counselor_space.py` | `/api/counselor/*` — the conseiller's own surface |
| `migrations/versions/e7f8a9b0c1d2_counselor_accounts.py` | the one schema revision |

**Backend — modify**

| File | Change |
|---|---|
| `app/models/counselor_code.py` | `owner_id`, `max_uses`, `expires_at`, `revoked_at` |
| `app/utils/decorators.py` | `approved_counselor_required` |
| `app/routes/analyses.py:190-215` | redeem through `code_service` |
| `app/routes/voyage.py:441-484` | redeem through `code_service` |
| `app/routes/admin.py` | the five `/counselor-applications` routes |
| `app/config.py` | `MAIL_FROM` |
| `app/__init__.py:151,159-172` | import the new models, register the new blueprint |

**Frontend — create**

| File | Responsibility |
|---|---|
| `src/lib/counselor.ts` | typed client for `/api/counselor/*` |
| `src/app/(auth)/inscription-conseiller/page.tsx` | the demande form |
| `src/app/conseiller/page.tsx` | the four-state dashboard |

**Frontend — modify**: `src/types/index.ts`, `src/app/admin/conseillers/page.tsx`, `src/app/admin/layout.tsx`, `src/components/layout/AppBar.tsx`, `src/proxy.ts`, `src/app/(legal)/confidentialite/page.tsx`, `src/app/(legal)/cgv/page.tsx`.

---

## Task 1: Schema — profile, code columns, redemption log

**Files:**
- Create: `backend/app/models/counselor_profile.py`
- Create: `backend/app/models/code_redemption.py`
- Modify: `backend/app/models/counselor_code.py`
- Modify: `backend/app/__init__.py:151`
- Create: `backend/migrations/versions/e7f8a9b0c1d2_counselor_accounts.py`
- Test: `backend/tests/test_counselor_models.py`

**Interfaces:**
- Produces: `CounselorProfile` (`.status` in `pending|approved|rejected|revoked`, `.max_codes`, `.max_uses_per_code`, `.to_dict(with_user=False)`), `CodeRedemption` (`.code_id`, `.user_id`, `.target_type` in `analysis|voyage`, `.target_id`, `.redeemed_at`), `CounselorCode.owner_id / .max_uses / .expires_at / .revoked_at`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_counselor_models.py`:

```python
"""The three schema changes, pinned at the model level.

Two of these tests are about what must NOT change: an existing counselor code
keeps working untouched, and a redemption outlives the person it belonged to.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.code_redemption import CodeRedemption
from app.models.counselor_code import CounselorCode
from app.models.counselor_profile import CounselorProfile
from app.models.user import User


def _user(email="conseiller@test.com", role="candidate"):
    u = User(email=email, password_hash="x", role=role)
    db.session.add(u)
    db.session.commit()
    return u


def _code(**kwargs):
    c = CounselorCode(label=kwargs.pop("label", "Cap Emploi test"), **kwargs)
    db.session.add(c)
    db.session.commit()
    return c


def test_profile_starts_pending_with_no_limits(app):
    u = _user()
    p = CounselorProfile(
        user_id=u.id,
        structure="Cap Emploi 31",
        fonction="Conseillère en insertion",
        telephone="0561000000",
    )
    db.session.add(p)
    db.session.commit()

    assert p.status == "pending"
    assert p.max_codes is None            # NULL = illimité, decision 4
    assert p.max_uses_per_code is None
    assert p.reviewed_at is None
    assert p.decision_reason is None


def test_one_demande_per_account(app):
    u = _user()
    db.session.add(CounselorProfile(user_id=u.id, structure="a", fonction="b", telephone="c"))
    db.session.commit()

    db.session.add(CounselorProfile(user_id=u.id, structure="d", fonction="e", telephone="f"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_an_existing_code_is_unowned_and_unlimited(app):
    """Decision 13: every row that exists today keeps behaving exactly as it did."""
    c = _code()
    assert c.owner_id is None
    assert c.max_uses is None
    assert c.expires_at is None
    assert c.revoked_at is None


def test_a_redemption_is_unique_per_target(app):
    c = _code()
    db.session.add(CodeRedemption(code_id=c.id, target_type="analysis", target_id="a-1"))
    db.session.commit()

    db.session.add(CodeRedemption(code_id=c.id, target_type="analysis", target_id="a-1"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_a_redemption_outlives_the_person(app):
    """RGPD: erasing an account anonymises the row, it does not delete the count."""
    u = _user("beneficiaire@test.com")
    c = _code()
    r = CodeRedemption(code_id=c.id, user_id=u.id, target_type="voyage", target_id="v-1")
    db.session.add(r)
    db.session.commit()

    db.session.delete(u)
    db.session.commit()
    db.session.refresh(r)
    assert r.user_id is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_counselor_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.counselor_profile'`

- [ ] **Step 3: Create `backend/app/models/counselor_profile.py`**

```python
from uuid import uuid4
from datetime import datetime
from ..extensions import db


# pending  — submitted, not yet reviewed
# approved — user.role is 'counselor' for exactly this status
# rejected — the demande failed review, terminal
# revoked  — was approved, access withdrawn afterwards. Kept apart from
#            'rejected' because they are not the same fact: different message
#            on screen, different line in any report.
STATUSES = ("pending", "approved", "rejected", "revoked")


class CounselorProfile(db.Model):
    """One demande per account. Nothing counselor-shaped lives on `users`:
    to_dict() there is returned on every /auth/me, to every candidate."""

    __tablename__ = "counselor_profiles"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id"), unique=True, nullable=False, index=True
    )

    structure = db.Column(db.String(255), nullable=False)
    fonction = db.Column(db.String(255), nullable=False)
    telephone = db.Column(db.String(32), nullable=False)
    email_pro = db.Column(db.String(255), nullable=True)
    message = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.Enum(*STATUSES, name="counselor_status"),
        nullable=False,
        default="pending",
        index=True,
    )

    # Both NULL = illimité. The admin's two dials: how many codes, and how many
    # uses any one of them may carry. An account-wide redemption quota would be
    # meaningless once a code is multi-use — spec decision 4.
    max_codes = db.Column(db.Integer, nullable=True)
    max_uses_per_code = db.Column(db.Integer, nullable=True)

    decision_reason = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Two FKs to the same table, so both relationships must name their column.
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("counselor_profile", uselist=False),
    )
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    def to_dict(self, *, with_user: bool = False) -> dict:
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "structure": self.structure,
            "fonction": self.fonction,
            "telephone": self.telephone,
            "email_pro": self.email_pro,
            "message": self.message,
            "status": self.status,
            "max_codes": self.max_codes,
            "max_uses_per_code": self.max_uses_per_code,
            "decision_reason": self.decision_reason,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "created_at": self.created_at.isoformat(),
        }
        if with_user:
            data["user"] = self.user.to_dict()
        return data
```

- [ ] **Step 4: Create `backend/app/models/code_redemption.py`**

```python
from uuid import uuid4
from datetime import datetime
from ..extensions import db


class CodeRedemption(db.Model):
    """Who redeemed which code, on what, when.

    CounselorCode.uses_count is an integer and answers none of that; an analysis
    unlock records *that* a code was used (Analysis.unlock_method) but never
    which one. The conseiller dashboard is not derivable without this table.
    """

    __tablename__ = "code_redemptions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    code_id = db.Column(
        db.String(36), db.ForeignKey("counselor_codes.id"), nullable=False, index=True
    )
    # Nullable on purpose: POST /api/analyses/<id>/unlock carries no auth
    # decorator, so the anonymous flow redeems codes too. ON DELETE SET NULL
    # keeps the count when the person is erased — the row survives, they do not.
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_type = db.Column(
        db.Enum("analysis", "voyage", name="redemption_target"), nullable=False
    )
    target_id = db.Column(db.String(36), nullable=False)
    redeemed_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    __table_args__ = (
        # A retried unlock must not double-count.
        db.UniqueConstraint(
            "code_id", "target_type", "target_id", name="uq_code_redemptions_target"
        ),
    )

    code = db.relationship("CounselorCode", foreign_keys=[code_id])
    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code_id": self.code_id,
            "user_id": self.user_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "redeemed_at": self.redeemed_at.isoformat(),
        }
```

- [ ] **Step 5: Add the four columns to `backend/app/models/counselor_code.py`**

Replace lines 19-35 (from `created_by_id` through the end of `to_dict`) with:

```python
    created_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    # Whose budget and dashboard this code belongs to. NULL = admin-minted,
    # which every row that predates comptes conseiller is. created_by_id stays
    # "who pressed the button"; for a conseiller-minted code they are the same.
    owner_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    uses_count = db.Column(db.Integer, nullable=False, default=0)
    # NULL = illimité, on all three. Codes minted by a conseiller default to
    # max_uses=1 and a 90-day expiry at the route; codes that already exist
    # keep NULL and behave exactly as they did.
    max_uses = db.Column(db.Integer, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    owner = db.relationship("User", foreign_keys=[owner_id])

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "label": self.label,
            "is_active": self.is_active,
            "uses_count": self.uses_count,
            "created_by_id": self.created_by_id,
            "owner_id": self.owner_id,
            "max_uses": self.max_uses,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "created_at": self.created_at.isoformat(),
        }
```

- [ ] **Step 6: Register the models in `backend/app/__init__.py:151`**

```python
    from .models import (  # noqa: F401
        user, analysis, prompt_version, counselor_note, counselor_code,
        counselor_profile, code_redemption, profile, price_feedback, voyage,
    )
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_counselor_models.py -v`
Expected: 5 passed

- [ ] **Step 8: Write the migration**

Create `backend/migrations/versions/e7f8a9b0c1d2_counselor_accounts.py`:

```python
"""Comptes conseiller: demandes, code ownership, redemption log

Three changes, one revision:

  * counselor_profiles — one demande per account, carrying the two admin dials
    (max_codes, max_uses_per_code). Nothing is added to `users`.
  * counselor_codes — owner_id, max_uses, expires_at, revoked_at, every one
    nullable so the rows that exist keep behaving exactly as they did: unowned,
    unlimited, unexpiring.
  * code_redemptions — who redeemed what, when. uses_count is an integer and
    answers none of that.

code_redemptions.user_id is ON DELETE SET NULL: erasing an account must leave
the conseiller's count intact and the person gone.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-24
"""
import sqlalchemy as sa
from alembic import op


revision = 'e7f8a9b0c1d2'
down_revision = 'd6e7f8a9b0c1'
branch_labels = None
depends_on = None


CODE_COLUMNS = (
    ("owner_id", sa.String(36)),
    ("max_uses", sa.Integer()),
    ("expires_at", sa.DateTime()),
    ("revoked_at", sa.DateTime()),
)


def _tables(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _columns(bind, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade():
    # Idempotent: entrypoint.sh runs `db upgrade` at container start, and a
    # half-applied revision must not wedge the backend down.
    bind = op.get_bind()
    tables = _tables(bind)

    if "counselor_profiles" not in tables:
        op.create_table(
            "counselor_profiles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("structure", sa.String(255), nullable=False),
            sa.Column("fonction", sa.String(255), nullable=False),
            sa.Column("telephone", sa.String(32), nullable=False),
            sa.Column("email_pro", sa.String(255), nullable=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column(
                "status",
                sa.Enum("pending", "approved", "rejected", "revoked", name="counselor_status"),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("max_codes", sa.Integer(), nullable=True),
            sa.Column("max_uses_per_code", sa.Integer(), nullable=True),
            sa.Column("decision_reason", sa.Text(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_id", name="uq_counselor_profiles_user"),
        )
        op.create_index("ix_counselor_profiles_status", "counselor_profiles", ["status"])

    have = _columns(bind, "counselor_codes")
    for name, type_ in CODE_COLUMNS:
        if name not in have:
            op.add_column("counselor_codes", sa.Column(name, type_, nullable=True))
    if "owner_id" not in have:
        op.create_index("ix_counselor_codes_owner_id", "counselor_codes", ["owner_id"])
        op.create_foreign_key(
            "fk_counselor_codes_owner_id", "counselor_codes", "users", ["owner_id"], ["id"]
        )

    if "code_redemptions" not in tables:
        op.create_table(
            "code_redemptions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code_id", sa.String(36), sa.ForeignKey("counselor_codes.id"), nullable=False),
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "target_type",
                sa.Enum("analysis", "voyage", name="redemption_target"),
                nullable=False,
            ),
            sa.Column("target_id", sa.String(36), nullable=False),
            sa.Column("redeemed_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "code_id", "target_type", "target_id", name="uq_code_redemptions_target"
            ),
        )
        op.create_index("ix_code_redemptions_code_id", "code_redemptions", ["code_id"])
        op.create_index("ix_code_redemptions_user_id", "code_redemptions", ["user_id"])
        op.create_index("ix_code_redemptions_redeemed_at", "code_redemptions", ["redeemed_at"])


def downgrade():
    bind = op.get_bind()
    tables = _tables(bind)

    if "code_redemptions" in tables:
        op.drop_table("code_redemptions")

    have = _columns(bind, "counselor_codes")
    if "owner_id" in have:
        op.drop_constraint("fk_counselor_codes_owner_id", "counselor_codes", type_="foreignkey")
        op.drop_index("ix_counselor_codes_owner_id", table_name="counselor_codes")
    for name, _ in reversed(CODE_COLUMNS):
        if name in have:
            op.drop_column("counselor_codes", name)

    if "counselor_profiles" in tables:
        op.drop_table("counselor_profiles")
```

- [ ] **Step 9: Verify the revision graph still has one head**

Run: `cd backend && venv/bin/pytest tests/test_migration_chain.py -v`
Expected: 2 passed

- [ ] **Step 10: Run the whole suite — nothing may regress**

Run: `cd backend && venv/bin/pytest -q`
Expected: all pass. `tests/test_unlock.py` in particular must still be green: the code model changed, its behaviour has not.

- [ ] **Step 11: Commit**

```bash
git add backend/app/models/counselor_profile.py backend/app/models/code_redemption.py \
        backend/app/models/counselor_code.py backend/app/__init__.py \
        backend/migrations/versions/e7f8a9b0c1d2_counselor_accounts.py \
        backend/tests/test_counselor_models.py
git commit -m "feat(conseiller): schema for demandes, code ownership and a redemption log"
```

---

## Task 2: `code_service` — one redemption path

**Files:**
- Create: `backend/app/services/code_service.py`
- Test: `backend/tests/test_code_service.py`

**Interfaces:**
- Consumes: `CounselorCode`, `CodeRedemption` (Task 1).
- Produces: `normalize(raw) -> str`, `redemption_count(code_id) -> int`, `resolve(code_str) -> tuple[CounselorCode | None, str | None]`, `record(code, *, user_id, target_type, target_id) -> None`, and the three constants `INVALID`, `EXPIRED`, `EXHAUSTED`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_code_service.py`:

```python
"""The three refusals and the log, tested away from any route.

Both call sites redeem through this module, so a rule proved once here holds
for an analysis unlock and a voyage unlock alike.
"""
from datetime import datetime, timedelta

from app.extensions import db
from app.models.code_redemption import CodeRedemption
from app.models.counselor_code import CounselorCode
from app.services import code_service


def _code(**kwargs):
    c = CounselorCode(label=kwargs.pop("label", "Cap Emploi test"), **kwargs)
    db.session.add(c)
    db.session.commit()
    return c


def test_normalize_accepts_spacing_and_case(app):
    assert code_service.normalize(" ab12-cd34 ") == "AB12CD34"
    assert code_service.normalize(None) == ""
    assert code_service.normalize(["nope"]) == ""


def test_resolve_returns_an_active_code(app):
    c = _code()
    found, refusal = code_service.resolve(c.code)
    assert refusal is None
    assert found.id == c.id


def test_resolve_refuses_an_inactive_code(app):
    c = _code(is_active=False)
    found, refusal = code_service.resolve(c.code)
    assert found is None
    assert refusal == code_service.INVALID


def test_resolve_refuses_a_revoked_code(app):
    c = _code(revoked_at=datetime.utcnow())
    found, refusal = code_service.resolve(c.code)
    assert found is None
    assert refusal == code_service.INVALID


def test_resolve_refuses_an_expired_code(app):
    c = _code(expires_at=datetime.utcnow() - timedelta(days=1))
    found, refusal = code_service.resolve(c.code)
    assert found is None
    assert refusal == code_service.EXPIRED


def test_resolve_refuses_an_exhausted_code(app):
    c = _code(max_uses=1)
    db.session.add(CodeRedemption(code_id=c.id, target_type="analysis", target_id="a-1"))
    db.session.commit()

    found, refusal = code_service.resolve(c.code)
    assert found is None
    assert refusal == code_service.EXHAUSTED


def test_a_legacy_code_is_never_exhausted(app):
    """max_uses NULL = illimité. Rows written before this feature carry a
    uses_count with no redemption rows behind it; the count check never runs
    on them, so that history cannot lock anybody out."""
    c = _code(uses_count=97)
    found, refusal = code_service.resolve(c.code)
    assert refusal is None
    assert found.id == c.id


def test_record_writes_the_row_and_bumps_the_counter(app):
    c = _code()
    code_service.record(c, user_id=None, target_type="analysis", target_id="a-1")
    db.session.commit()

    row = CodeRedemption.query.filter_by(code_id=c.id).one()
    assert row.user_id is None
    assert row.target_type == "analysis"
    assert row.target_id == "a-1"
    assert c.uses_count == 1
    assert code_service.redemption_count(c.id) == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_code_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'code_service' from 'app.services'`

- [ ] **Step 3: Create `backend/app/services/code_service.py`**

```python
"""One redemption path, shared by the two call sites that redeem a code.

POST /api/analyses/<id>/unlock and POST /api/voyage/unlock each did their own
lookup and their own `uses_count += 1`. They now agree on three refusals —
inactive, expired, exhausted — and on writing the row that says who redeemed
what, when.
"""
import re
from datetime import datetime

from ..extensions import db
from ..models.code_redemption import CodeRedemption
from ..models.counselor_code import CounselorCode

INVALID = "Code invalide ou désactivé."
EXPIRED = "Ce code a expiré."
EXHAUSTED = "Ce code a atteint sa limite d'utilisation."


def normalize(raw) -> str:
    """Accept "ABCD1234", "abcd 1234", "ABCD-1234"… — codes are 8 alnum chars.

    A non-string value yields "", so the route answers its own « Code requis. »
    instead of raising AttributeError on .strip() -> an unhandled 500.
    """
    return re.sub(r"[^A-Za-z0-9]", "", raw if isinstance(raw, str) else "").upper()


def redemption_count(code_id: str) -> int:
    return CodeRedemption.query.filter_by(code_id=code_id).count()


def resolve(code_str: str) -> tuple[CounselorCode | None, str | None]:
    """The code, or the French refusal to hand back verbatim.

    Counted, not read off uses_count: that column is an increment which can
    drift, and rows that predate this feature carry one with no redemption
    behind it. Their max_uses is NULL, so the check below never reaches them.

    with_for_update locks the row for the rest of the transaction on MySQL, so
    two simultaneous redemptions of a code's last use cannot both pass. SQLite
    (tests) omits the clause; the check itself still runs.
    """
    code = CounselorCode.query.filter_by(code=code_str).with_for_update().first()
    if code is None or not code.is_active or code.revoked_at is not None:
        return None, INVALID
    if code.expires_at is not None and code.expires_at <= datetime.utcnow():
        return None, EXPIRED
    if code.max_uses is not None and redemption_count(code.id) >= code.max_uses:
        return None, EXHAUSTED
    return code, None


def record(code: CounselorCode, *, user_id: str | None, target_type: str, target_id: str) -> None:
    """Log the redemption and bump the legacy counter.

    Deliberately does not commit: the caller owns the transaction this belongs
    to, and the unlock it accompanies must land or not land with it.
    """
    db.session.add(CodeRedemption(
        code_id=code.id,
        user_id=user_id,
        target_type=target_type,
        target_id=target_id,
    ))
    code.uses_count += 1
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_code_service.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/code_service.py backend/tests/test_code_service.py
git commit -m "feat(conseiller): one redemption path with expiry and use limits"
```

---

## Task 3: Both unlock routes redeem through the service

**Files:**
- Modify: `backend/app/routes/analyses.py:190-215`
- Modify: `backend/app/routes/voyage.py:441-484`
- Test: `backend/tests/test_code_redemption_routes.py`

**Interfaces:**
- Consumes: `code_service.normalize / resolve / record` (Task 2).
- Produces: every redemption in the app now leaves a `code_redemptions` row.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_code_redemption_routes.py`:

```python
"""Both call sites log the redemption and honour the same three refusals.

test_unlock.py already covers the happy path each route had before; this file
covers what the redemption log and the limits add to them.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.analysis import Analysis
from app.models.code_redemption import CodeRedemption
from app.models.counselor_code import CounselorCode
from app.models.user import User
from app.models.voyage import Voyage


def _analysis():
    a = Analysis(
        inputs={"_path": "A", "_tier": "haiku", "cible_visee": "x"},
        status="success",
        output={"1": {"title": "t", "body_markdown": "b", "items": []}},
    )
    db.session.add(a)
    db.session.commit()
    return a


def _code(**kwargs):
    c = CounselorCode(label=kwargs.pop("label", "Cap Emploi test"), **kwargs)
    db.session.add(c)
    db.session.commit()
    return c


def _candidate(email="beneficiaire@test.com"):
    u = User(email=email, password_hash="x", role="candidate")
    db.session.add(u)
    db.session.commit()
    token = create_access_token(identity=str(u.id), additional_claims={"role": "candidate"})
    return u, {"Authorization": f"Bearer {token}"}


@patch("app.services.unlock_service.start_analysis")
def test_analysis_unlock_logs_an_anonymous_redemption(mock_start, client, app):
    """The route carries no auth decorator, so user_id may legitimately be NULL
    — and the use must still count."""
    a = _analysis()
    c = _code()
    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": c.code})
    assert r.status_code == 200

    row = CodeRedemption.query.filter_by(code_id=c.id).one()
    assert row.user_id is None
    assert row.target_type == "analysis"
    assert row.target_id == a.id


@patch("app.services.unlock_service.start_analysis")
def test_analysis_unlock_refuses_an_exhausted_code(mock_start, client, app):
    a = _analysis()
    c = _code(max_uses=1)
    db.session.add(CodeRedemption(code_id=c.id, target_type="voyage", target_id="v-0"))
    db.session.commit()

    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": c.code})
    assert r.status_code == 400
    assert r.get_json()["error"] == "Ce code a atteint sa limite d'utilisation."
    mock_start.assert_not_called()


@patch("app.services.unlock_service.start_analysis")
def test_analysis_unlock_refuses_an_expired_code(mock_start, client, app):
    a = _analysis()
    c = _code(expires_at=datetime.utcnow() - timedelta(days=1))
    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": c.code})
    assert r.status_code == 400
    assert r.get_json()["error"] == "Ce code a expiré."


def test_voyage_unlock_logs_the_person(client, app):
    user, headers = _candidate()
    v = Voyage(user_id=user.id)
    db.session.add(v)
    db.session.commit()
    c = _code()

    r = client.post("/api/voyage/unlock", json={"code": c.code}, headers=headers)
    assert r.status_code == 200

    row = CodeRedemption.query.filter_by(code_id=c.id).one()
    assert row.user_id == user.id
    assert row.target_type == "voyage"
    assert row.target_id == v.id


def test_voyage_unlock_refuses_an_exhausted_code(client, app):
    user, headers = _candidate()
    v = Voyage(user_id=user.id)
    db.session.add(v)
    db.session.commit()
    c = _code(max_uses=1)
    db.session.add(CodeRedemption(code_id=c.id, target_type="analysis", target_id="a-0"))
    db.session.commit()

    r = client.post("/api/voyage/unlock", json={"code": c.code}, headers=headers)
    assert r.status_code == 400
    assert r.get_json()["error"] == "Ce code a atteint sa limite d'utilisation."
    db.session.refresh(v)
    assert v.counselor_code_id is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_code_redemption_routes.py -v`
Expected: FAIL — no `code_redemptions` row is written (`NoResultFound`), and the limit tests get 200 instead of 400.

- [ ] **Step 3: Rewrite the body of `unlock_with_code` in `backend/app/routes/analyses.py:190-215`**

Keep the decorator and docstring; replace from `data = json_object()` to the `return`:

```python
    data = json_object()

    code_str = code_service.normalize(text_field(data, "code"))
    if not code_str:
        return jsonify({"error": "Code requis."}), 400

    code, refusal = code_service.resolve(code_str)
    if refusal:
        return jsonify({"error": refusal}), 400

    ok, reason = unlock_analysis(analysis, method="code")
    if not ok:
        return jsonify({"error": reason}), 409

    # analysis.user_id, not the JWT: this route has no auth decorator and the
    # anonymous flow is supported. An unowned analysis logs a NULL person and
    # still counts against the code.
    code_service.record(
        code, user_id=analysis.user_id, target_type="analysis", target_id=analysis.id
    )
    db.session.commit()
    return jsonify({"analysis": analysis.to_dict()}), 200
```

Add the import near the other service imports at the top of the file:

```python
from ..services import code_service
```

- [ ] **Step 4: Rewrite the tail of `unlock_voyage` in `backend/app/routes/voyage.py:464-484`**

Replace from `data = request.get_json(silent=True)` to the `return`:

```python
    # request.get_json(silent=True) or {} lets a JSON array or a bare string
    # survive as truthy, and the next .get() call then raises AttributeError
    # -> an unhandled 500 (the defect put_responses above was fixed for).
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}

    # normalize() also absorbs a non-string "code" (an int, a list, a dict),
    # which must not reach .strip() either.
    code_str = code_service.normalize(data.get("code"))
    if not code_str:
        return jsonify({"error": "Code requis."}), 400

    code, refusal = code_service.resolve(code_str)
    if refusal:
        return jsonify({"error": refusal}), 400

    voyage.counselor_code_id = code.id
    code_service.record(
        code, user_id=voyage.user_id, target_type="voyage", target_id=voyage.id
    )
    db.session.commit()
    return jsonify({"voyage": voyage.to_dict()}), 200
```

Add to the file's service imports:

```python
from ..services import code_service
```

- [ ] **Step 5: Run the new test and the existing unlock tests**

Run: `cd backend && venv/bin/pytest tests/test_code_redemption_routes.py tests/test_unlock.py tests/test_voyage_routes.py tests/test_malformed_bodies.py tests/test_no_500_on_hostile_input.py -v`
Expected: all pass. The hostile-input suites matter here — `normalize` replaced two hand-rolled guards.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/analyses.py backend/app/routes/voyage.py \
        backend/tests/test_code_redemption_routes.py
git commit -m "feat(conseiller): log every redemption and enforce expiry and use limits"
```

---

## Task 4: `approved_counselor_required`

**Files:**
- Modify: `backend/app/utils/decorators.py`
- Test: `backend/tests/test_counselor_guard.py`

**Interfaces:**
- Consumes: `CounselorProfile` (Task 1).
- Produces: `approved_counselor_required` — used by every `/api/counselor/*` route from Task 8 onward.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_counselor_guard.py`:

```python
"""The guard that reads the DB, not only the claim.

role_required checks get_jwt()["role"], which outlives a revocation by up to
JWT_ACCESS_TOKEN_EXPIRES (1 h). A revoked conseiller holding a valid token must
be refused on the next request, not on the next hour.
"""
import pytest
from flask import Flask, jsonify
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User
from app.utils.decorators import approved_counselor_required


@pytest.fixture
def guarded(app):
    """Mount a throwaway route carrying only the decorator under test."""
    @app.route("/api/_guarded")
    @approved_counselor_required
    def _guarded():
        return jsonify({"ok": True}), 200
    return app


def _user_with(status, role="counselor", email="c@test.com"):
    u = User(email=email, password_hash="x", role=role)
    db.session.add(u)
    db.session.commit()
    if status is not None:
        db.session.add(CounselorProfile(
            user_id=u.id, structure="s", fonction="f", telephone="t", status=status,
        ))
        db.session.commit()
    token = create_access_token(identity=str(u.id), additional_claims={"role": role})
    return {"Authorization": f"Bearer {token}"}


def test_approved_counselor_passes(guarded):
    headers = _user_with("approved")
    assert guarded.test_client().get("/api/_guarded", headers=headers).status_code == 200


def test_admin_passes_without_a_profile(guarded):
    headers = _user_with(None, role="admin", email="a@test.com")
    assert guarded.test_client().get("/api/_guarded", headers=headers).status_code == 200


def test_candidate_is_refused(guarded):
    headers = _user_with(None, role="candidate", email="p@test.com")
    assert guarded.test_client().get("/api/_guarded", headers=headers).status_code == 403


def test_pending_is_refused_even_with_a_counselor_claim(guarded):
    headers = _user_with("pending")
    assert guarded.test_client().get("/api/_guarded", headers=headers).status_code == 403


def test_revoked_is_refused_before_the_token_expires(guarded):
    """The token still says counselor. The DB no longer does."""
    headers = _user_with("revoked")
    assert guarded.test_client().get("/api/_guarded", headers=headers).status_code == 403
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_counselor_guard.py -v`
Expected: FAIL — `ImportError: cannot import name 'approved_counselor_required'`

- [ ] **Step 3: Append to `backend/app/utils/decorators.py`**

Change the import on line 3 and append the decorator:

```python
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request
```

```python
def approved_counselor_required(fn):
    """A conseiller surface: the claim says counselor AND the DB still agrees.

    role_required alone reads the JWT claim, which survives a revocation for up
    to JWT_ACCESS_TOKEN_EXPIRES (1 h, config.py:23). Revocation has to bite on
    the next request, so this one pays for a row read.

    Admins pass without a profile, the exception every /api/voyage/c/<token>
    route already makes.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Imported here, not at module scope: app.models imports the extensions
        # this module is loaded alongside, and a top-level import would make
        # that circular.
        from ..models.counselor_profile import CounselorProfile

        verify_jwt_in_request()
        role = get_jwt().get("role")
        if role == "admin":
            return fn(*args, **kwargs)
        if role != "counselor":
            return jsonify({"error": "Accès non autorisé."}), 403

        profile = CounselorProfile.query.filter_by(user_id=get_jwt_identity()).first()
        if profile is None or profile.status != "approved":
            return jsonify({"error": "Accès non autorisé."}), 403
        return fn(*args, **kwargs)
    return wrapper
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_counselor_guard.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/utils/decorators.py backend/tests/test_counselor_guard.py
git commit -m "feat(conseiller): guard that revokes access without waiting for the token"
```

---

## Task 5: `POST /api/counselor/apply` and `GET /api/counselor/me`

**Files:**
- Create: `backend/app/routes/counselor_space.py`
- Modify: `backend/app/__init__.py:159-172`
- Test: `backend/tests/test_counselor_apply.py`

**Interfaces:**
- Consumes: `CounselorProfile` (Task 1).
- Produces: blueprint `counselor_space_bp` at `/api/counselor`; JSON `{"profile": {...} | null}` from both routes.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_counselor_apply.py`:

```python
"""The demande, and the waiting room it puts someone in.

The rule this file exists to pin: a pending conseiller is role=candidate. A
pending account holding role=counselor would pass every /api/voyage/c/<token>
guard before anyone had reviewed it.
"""
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User

PAYLOAD = {
    "email": "conseiller@capemploi.fr",
    "password": "motdepasse1",
    "structure": "Cap Emploi 31",
    "fonction": "Conseillère en insertion",
    "telephone": "0561000000",
    "email_pro": "c.martin@capemploi.fr",
    "message": "J'accompagne une quinzaine de personnes par mois.",
    "consent": True,
}


def _authed(email="deja@test.com", role="candidate"):
    u = User(email=email, password_hash="x", role=role)
    db.session.add(u)
    db.session.commit()
    token = create_access_token(identity=str(u.id), additional_claims={"role": role})
    return u, {"Authorization": f"Bearer {token}"}


def test_apply_creates_a_pending_demande_and_a_candidate(client, app):
    r = client.post("/api/counselor/apply", json=PAYLOAD)
    assert r.status_code == 201
    body = r.get_json()
    assert body["profile"]["status"] == "pending"
    assert body["user"]["role"] == "candidate"     # not counselor. Not yet.

    user = User.query.filter_by(email="conseiller@capemploi.fr").one()
    assert user.role == "candidate"
    profile = CounselorProfile.query.filter_by(user_id=user.id).one()
    assert profile.structure == "Cap Emploi 31"
    assert profile.max_codes is None


def test_apply_requires_structure_fonction_and_telephone(client, app):
    for missing in ("structure", "fonction", "telephone"):
        payload = {**PAYLOAD, missing: ""}
        r = client.post("/api/counselor/apply", json=payload)
        assert r.status_code == 400, missing


def test_apply_requires_consent(client, app):
    r = client.post("/api/counselor/apply", json={**PAYLOAD, "consent": False})
    assert r.status_code == 400


def test_apply_refuses_a_taken_email(client, app):
    _authed(email=PAYLOAD["email"])
    r = client.post("/api/counselor/apply", json=PAYLOAD)
    assert r.status_code == 409


def test_an_existing_candidate_applies_without_a_second_account(client, app):
    user, headers = _authed()
    payload = {k: v for k, v in PAYLOAD.items() if k not in ("email", "password")}
    r = client.post("/api/counselor/apply", json=payload, headers=headers)
    assert r.status_code == 201
    assert User.query.count() == 1
    assert CounselorProfile.query.filter_by(user_id=user.id).one().status == "pending"


def test_a_second_demande_is_refused(client, app):
    user, headers = _authed()
    payload = {k: v for k, v in PAYLOAD.items() if k not in ("email", "password")}
    assert client.post("/api/counselor/apply", json=payload, headers=headers).status_code == 201
    r = client.post("/api/counselor/apply", json=payload, headers=headers)
    assert r.status_code == 409


def test_me_returns_null_for_someone_who_never_applied(client, app):
    _user, headers = _authed()
    r = client.get("/api/counselor/me", headers=headers)
    assert r.status_code == 200
    assert r.get_json()["profile"] is None


def test_me_returns_the_demande(client, app):
    user, headers = _authed()
    db.session.add(CounselorProfile(
        user_id=user.id, structure="Mission locale", fonction="Conseiller", telephone="0102030405",
    ))
    db.session.commit()

    r = client.get("/api/counselor/me", headers=headers)
    assert r.get_json()["profile"]["structure"] == "Mission locale"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_counselor_apply.py -v`
Expected: FAIL — 404 on every route; the blueprint does not exist.

- [ ] **Step 3: Create `backend/app/routes/counselor_space.py`**

```python
"""The conseiller's own surface: /api/counselor/*.

Not to be confused with routes/counselor.py, mounted at /api/c — that one
serves an analysis share link to whoever holds the token, with no account at
all. This blueprint is the account.
"""
from datetime import datetime

from flask import Blueprint, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
    verify_jwt_in_request,
)

from ..extensions import bcrypt, db
from ..models.counselor_profile import CounselorProfile
from ..models.user import User
from ..utils.request_body import json_object, raw_text_field, text_field

counselor_space_bp = Blueprint("counselor_space", __name__)

REQUIRED_FIELDS = ("structure", "fonction", "telephone")


@counselor_space_bp.post("/apply")
def apply():
    """Submit a demande — with or without an account already.

    An existing candidate applies from their espace and keeps the account they
    have; without a JWT the account is created here. Either way the person
    stays role='candidate' until an admin approves: the JWT claim is what every
    counselor guard reads, so granting the role now would open
    /api/voyage/c/<token> to someone nobody has reviewed.

    This is the app's only public endpoint that creates an account *and*
    enqueues admin work. v1 leans on the unique-email constraint and on a human
    reading the queue; a rate limit belongs here if demandes are ever spammed.
    """
    verify_jwt_in_request(optional=True)
    user_id = get_jwt_identity()

    data = json_object()
    fields = {name: text_field(data, name) for name in REQUIRED_FIELDS}
    missing = [name for name, value in fields.items() if not value]
    if missing:
        return jsonify({"error": "Structure, fonction et téléphone sont requis."}), 400
    if data.get("consent") is not True:
        return jsonify({"error": "Le consentement est requis."}), 400

    if user_id:
        user = User.query.get(user_id)
        if user is None:
            return jsonify({"error": "Utilisateur introuvable."}), 404
        created = False
    else:
        email = text_field(data, "email").lower()
        password = raw_text_field(data, "password")
        if not email or not password:
            return jsonify({"error": "Email et mot de passe requis."}), 400
        if len(password) < 8:
            return jsonify({"error": "Le mot de passe doit contenir au moins 8 caractères."}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Un compte existe déjà avec cet email."}), 409
        user = User(
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
        )
        db.session.add(user)
        db.session.flush()   # user.id, for the profile's FK
        created = True

    if CounselorProfile.query.filter_by(user_id=user.id).first():
        return jsonify({"error": "Une demande existe déjà pour ce compte."}), 409

    profile = CounselorProfile(
        user_id=user.id,
        email_pro=text_field(data, "email_pro") or None,
        message=text_field(data, "message") or None,
        **fields,
    )
    db.session.add(profile)
    db.session.commit()

    response = jsonify({"user": user.to_dict(), "profile": profile.to_dict()})
    if created:
        access_token = create_access_token(
            identity=user.id, additional_claims={"role": user.role}
        )
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, create_refresh_token(identity=user.id))
    return response, 201


@counselor_space_bp.get("/me")
@jwt_required()
def me():
    """The demande and its status — the switch the /conseiller page renders from.

    Deliberately not behind approved_counselor_required: the whole point is to
    be readable while pending, rejected or revoked.
    """
    profile = CounselorProfile.query.filter_by(user_id=get_jwt_identity()).first()
    return jsonify({"profile": profile.to_dict() if profile else None}), 200
```

- [ ] **Step 4: Register the blueprint in `backend/app/__init__.py`**

After line 161 (`from .routes.voyage import voyage_bp`) add the import, and after line 172 add the registration:

```python
    from .routes.counselor_space import counselor_space_bp
```

```python
    app.register_blueprint(counselor_space_bp, url_prefix="/api/counselor")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_counselor_apply.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/counselor_space.py backend/app/__init__.py \
        backend/tests/test_counselor_apply.py
git commit -m "feat(conseiller): submit a demande and read its status"
```

---

## Task 6: Admin review — approve, reject, limits, revoke

**Files:**
- Modify: `backend/app/routes/admin.py` (append after `deactivate_counselor_code`, line 196)
- Test: `backend/tests/test_counselor_review.py`

**Interfaces:**
- Consumes: `CounselorProfile` (Task 1), `admin_required` (existing).
- Produces: `GET /api/admin/counselor-applications`, `POST …/<id>/approve`, `POST …/<id>/reject`, `PUT …/<id>/limits`, `POST …/<id>/revoke`. Approve/revoke are the only writers of `user.role` besides `PUT /admin/users/<id>/role`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_counselor_review.py`:

```python
"""Approval is the only thing that grants the counselor role, and revocation
is the only thing that takes it back."""
from flask_jwt_extended import create_refresh_token

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User


def _demande(email="conseiller@test.com", status="pending"):
    u = User(email=email, password_hash="x", role="candidate")
    db.session.add(u)
    db.session.commit()
    p = CounselorProfile(
        user_id=u.id,
        structure="Cap Emploi 31",
        fonction="Conseillère",
        telephone="0561000000",
        status=status,
    )
    db.session.add(p)
    db.session.commit()
    return u, p


def test_the_queue_lists_pending_demandes_with_their_account(client, admin_headers):
    _demande()
    r = client.get("/api/admin/counselor-applications?status=pending", headers=admin_headers)
    assert r.status_code == 200
    rows = r.get_json()["applications"]
    assert len(rows) == 1
    assert rows[0]["structure"] == "Cap Emploi 31"
    assert rows[0]["user"]["email"] == "conseiller@test.com"


def test_the_queue_is_admin_only(client, app):
    r = client.get("/api/admin/counselor-applications")
    assert r.status_code == 401


def test_approve_grants_the_role_and_stores_the_limits(client, admin_headers):
    user, profile = _demande()
    r = client.post(
        f"/api/admin/counselor-applications/{profile.id}/approve",
        json={"max_codes": 25, "max_uses_per_code": 1},
        headers=admin_headers,
    )
    assert r.status_code == 200
    db.session.refresh(user)
    db.session.refresh(profile)
    assert user.role == "counselor"
    assert profile.status == "approved"
    assert profile.max_codes == 25
    assert profile.max_uses_per_code == 1
    assert profile.reviewed_at is not None
    assert profile.reviewed_by_id is not None


def test_refresh_mints_the_counselor_claim_after_approval(client, admin_headers):
    """The claim every counselor guard reads is minted from the row, so an
    approval reaches the browser on the next refresh — not in an hour."""
    user, profile = _demande()
    client.post(
        f"/api/admin/counselor-applications/{profile.id}/approve",
        json={}, headers=admin_headers,
    )
    refresh_headers = {
        "Authorization": f"Bearer {create_refresh_token(identity=str(user.id))}"
    }
    r = client.post("/api/auth/refresh", headers=refresh_headers)
    assert r.status_code == 200
    assert r.get_json()["user"]["role"] == "counselor"


def test_approve_with_no_limits_means_illimite(client, admin_headers):
    user, profile = _demande()
    r = client.post(
        f"/api/admin/counselor-applications/{profile.id}/approve",
        json={},
        headers=admin_headers,
    )
    assert r.status_code == 200
    db.session.refresh(profile)
    assert profile.max_codes is None
    assert profile.max_uses_per_code is None


def test_approve_refuses_a_negative_limit(client, admin_headers):
    _user, profile = _demande()
    r = client.post(
        f"/api/admin/counselor-applications/{profile.id}/approve",
        json={"max_codes": 0},
        headers=admin_headers,
    )
    assert r.status_code == 400


def test_reject_requires_a_reason_and_leaves_the_role_alone(client, admin_headers):
    user, profile = _demande()
    assert client.post(
        f"/api/admin/counselor-applications/{profile.id}/reject",
        json={}, headers=admin_headers,
    ).status_code == 400

    r = client.post(
        f"/api/admin/counselor-applications/{profile.id}/reject",
        json={"reason": "Structure non reconnue."},
        headers=admin_headers,
    )
    assert r.status_code == 200
    db.session.refresh(user)
    db.session.refresh(profile)
    assert profile.status == "rejected"
    assert profile.decision_reason == "Structure non reconnue."
    assert user.role == "candidate"


def test_revoke_takes_the_role_back_and_is_not_a_rejection(client, admin_headers):
    user, profile = _demande(status="approved")
    user.role = "counselor"
    db.session.commit()

    r = client.post(
        f"/api/admin/counselor-applications/{profile.id}/revoke",
        json={"reason": "Fin de convention."},
        headers=admin_headers,
    )
    assert r.status_code == 200
    db.session.refresh(user)
    db.session.refresh(profile)
    assert profile.status == "revoked"        # not "rejected"
    assert user.role == "candidate"


def test_limits_can_be_adjusted_after_approval(client, admin_headers):
    _user, profile = _demande(status="approved")
    r = client.put(
        f"/api/admin/counselor-applications/{profile.id}/limits",
        json={"max_codes": 50, "max_uses_per_code": 12},
        headers=admin_headers,
    )
    assert r.status_code == 200
    db.session.refresh(profile)
    assert profile.max_codes == 50
    assert profile.max_uses_per_code == 12


def test_a_decided_demande_cannot_be_approved_twice(client, admin_headers):
    _user, profile = _demande(status="rejected")
    r = client.post(
        f"/api/admin/counselor-applications/{profile.id}/approve",
        json={}, headers=admin_headers,
    )
    assert r.status_code == 409
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_counselor_review.py -v`
Expected: FAIL — 404 on every route.

- [ ] **Step 3: Append the routes to `backend/app/routes/admin.py`**

Add `CounselorProfile` to the model imports at the top, then append after `deactivate_counselor_code` (line 196):

```python
def _optional_limit(data: dict, key: str) -> tuple[int | None, str | None]:
    """A nullable positive integer. Absent or null means illimité.

    0 and negatives are refused rather than silently meaning "none": an admin
    typing 0 means "no codes", which is a revocation, not a limit.
    """
    value = data.get(key)
    if value is None:
        return None, None
    if isinstance(value, bool) or not isinstance(value, int):
        return None, f"{key} doit être un entier."
    if value < 1:
        return None, f"{key} doit être supérieur à zéro."
    return value, None


def _decide(profile, status, reason, reviewer_id):
    """Write the decision and keep user.role a function of it.

    approved <=> role 'counselor'. Nothing else may set that role for a
    conseiller: the JWT claim is minted from it, and every counselor guard
    reads the claim.
    """
    profile.status = status
    profile.decision_reason = reason
    profile.reviewed_at = datetime.utcnow()
    profile.reviewed_by_id = reviewer_id
    profile.user.role = "counselor" if status == "approved" else "candidate"


@admin_bp.get("/counselor-applications")
@admin_required
def list_counselor_applications():
    query = CounselorProfile.query
    status = request.args.get("status")
    if status:
        query = query.filter(CounselorProfile.status == status)
    rows = query.order_by(CounselorProfile.created_at.desc()).all()
    return jsonify({"applications": [p.to_dict(with_user=True) for p in rows]}), 200


@admin_bp.post("/counselor-applications/<profile_id>/approve")
@admin_required
def approve_counselor_application(profile_id):
    profile = CounselorProfile.query.get_or_404(profile_id)
    if profile.status != "pending":
        return jsonify({"error": "Cette demande a déjà été traitée."}), 409

    data = json_object()
    max_codes, error = _optional_limit(data, "max_codes")
    if error:
        return jsonify({"error": error}), 400
    max_uses, error = _optional_limit(data, "max_uses_per_code")
    if error:
        return jsonify({"error": error}), 400

    profile.max_codes = max_codes
    profile.max_uses_per_code = max_uses
    _decide(profile, "approved", None, get_jwt_identity())
    db.session.commit()

    # Task 7 adds the approval mail here, after the commit.
    return jsonify({"application": profile.to_dict(with_user=True)}), 200


@admin_bp.post("/counselor-applications/<profile_id>/reject")
@admin_required
def reject_counselor_application(profile_id):
    profile = CounselorProfile.query.get_or_404(profile_id)
    if profile.status != "pending":
        return jsonify({"error": "Cette demande a déjà été traitée."}), 409

    reason = text_field(json_object(), "reason")
    if not reason:
        return jsonify({"error": "Un motif est requis."}), 400

    _decide(profile, "rejected", reason, get_jwt_identity())
    db.session.commit()

    # Task 7 adds the rejection mail here, after the commit.
    return jsonify({"application": profile.to_dict(with_user=True)}), 200


@admin_bp.post("/counselor-applications/<profile_id>/revoke")
@admin_required
def revoke_counselor_application(profile_id):
    """Withdraw access from an approved conseiller.

    'revoked', not 'rejected': one is a demande that failed review, the other a
    conseiller who worked and whose access was withdrawn. Their codes stay
    valid — revoking the person is not the same as burning codes bénéficiaires
    already hold; deactivate those separately if that is what you mean.
    """
    profile = CounselorProfile.query.get_or_404(profile_id)
    if profile.status != "approved":
        return jsonify({"error": "Ce compte n'est pas actif."}), 409

    reason = text_field(json_object(), "reason")
    if not reason:
        return jsonify({"error": "Un motif est requis."}), 400

    _decide(profile, "revoked", reason, get_jwt_identity())
    db.session.commit()
    return jsonify({"application": profile.to_dict(with_user=True)}), 200


@admin_bp.put("/counselor-applications/<profile_id>/limits")
@admin_required
def set_counselor_limits(profile_id):
    profile = CounselorProfile.query.get_or_404(profile_id)
    data = json_object()

    max_codes, error = _optional_limit(data, "max_codes")
    if error:
        return jsonify({"error": error}), 400
    max_uses, error = _optional_limit(data, "max_uses_per_code")
    if error:
        return jsonify({"error": error}), 400

    profile.max_codes = max_codes
    profile.max_uses_per_code = max_uses
    db.session.commit()
    return jsonify({"application": profile.to_dict(with_user=True)}), 200
```

Add to the imports at the top of `admin.py`:

```python
from ..models.counselor_profile import CounselorProfile
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_counselor_review.py -v`
Expected: 10 passed

- [ ] **Step 5: Run the guard tests too — approval is what they depend on**

Run: `cd backend && venv/bin/pytest tests/test_counselor_guard.py tests/test_counselor_review.py -v`
Expected: 15 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/admin.py backend/tests/test_counselor_review.py
git commit -m "feat(conseiller): admin review grants and withdraws the role"
```

---

## Task 7: Email service and the two templates

**Files:**
- Create: `backend/app/services/email_service.py`
- Modify: `backend/app/config.py:28`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_email_service.py`

**Interfaces:**
- Consumes: `CounselorProfile` (Task 1).
- Produces: `send(to, subject, html) -> bool`, `send_counselor_approved(profile) -> bool`, `send_counselor_rejected(profile) -> bool`. All three return `False` on failure and never raise — Task 6 calls them after its commit.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_email_service.py`:

```python
"""The app's first transactional email. Fail-soft by contract.

An approval that already committed must not 500 because Resend is down, so
every path here returns a bool and none of them raises.
"""
from unittest.mock import patch

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User
from app.services import email_service


def _profile(status="approved", reason=None):
    u = User(email="conseiller@capemploi.fr", password_hash="x", role="counselor")
    db.session.add(u)
    db.session.commit()
    p = CounselorProfile(
        user_id=u.id, structure="Cap Emploi 31", fonction="Conseillère",
        telephone="0561000000", status=status, decision_reason=reason,
    )
    db.session.add(p)
    db.session.commit()
    return p


def test_send_without_a_key_returns_false_and_does_not_raise(app):
    app.config["RESEND_API_KEY"] = None
    assert email_service.send("a@b.fr", "Sujet", "<p>x</p>") is False


def test_send_swallows_a_provider_failure(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch("app.services.email_service.resend.Emails.send", side_effect=RuntimeError("boom")):
        assert email_service.send("a@b.fr", "Sujet", "<p>x</p>") is False


def test_send_returns_true_on_success(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch("app.services.email_service.resend.Emails.send", return_value={"id": "1"}):
        assert email_service.send("a@b.fr", "Sujet", "<p>x</p>") is True


def test_the_approval_mail_goes_to_the_login_address(app):
    app.config["RESEND_API_KEY"] = "re_test"
    profile = _profile()
    with patch("app.services.email_service.resend.Emails.send") as mock_send:
        assert email_service.send_counselor_approved(profile) is True
    payload = mock_send.call_args[0][0]
    assert payload["to"] == ["conseiller@capemploi.fr"]
    assert "conseiller" in payload["subject"].lower()


def test_the_rejection_mail_carries_the_reason(app):
    app.config["RESEND_API_KEY"] = "re_test"
    profile = _profile(status="rejected", reason="Structure non reconnue.")
    with patch("app.services.email_service.resend.Emails.send") as mock_send:
        email_service.send_counselor_rejected(profile)
    assert "Structure non reconnue." in mock_send.call_args[0][0]["html"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_email_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'email_service'`

- [ ] **Step 3: Create `backend/app/services/email_service.py`**

```python
"""Transactional email. The app's first — resend was in requirements and
RESEND_API_KEY in config, with nothing calling either.

Fail-soft by contract: send() returns False and logs, and never raises. It is
called after the decision has already committed, and a provider outage must not
turn a successful approval into a 500 the admin retries.
"""
import html as html_escape

import resend
from flask import current_app

from ..models.counselor_profile import CounselorProfile

APP_URL = "https://neoori.tech"


def send(to: str, subject: str, html: str) -> bool:
    key = current_app.config.get("RESEND_API_KEY")
    if not key:
        current_app.logger.warning("RESEND_API_KEY missing — mail to %s not sent.", to)
        return False
    try:
        resend.api_key = key
        resend.Emails.send({
            "from": current_app.config["MAIL_FROM"],
            "to": [to],
            "subject": subject,
            "html": html,
        })
        return True
    except Exception:
        current_app.logger.exception("Mail to %s failed.", to)
        return False


def _layout(title: str, body: str) -> str:
    """One sober frame for both mails. Inline styles: mail clients drop <style>."""
    return (
        '<div style="font-family:Inter,Helvetica,Arial,sans-serif;color:#1d1a17;'
        'max-width:520px;margin:0 auto;padding:24px">'
        f'<h1 style="font-size:20px;margin:0 0 16px">{title}</h1>'
        f'{body}'
        '<p style="font-size:13px;color:rgba(29,26,23,0.55);margin-top:28px">'
        'neoori — ce message est automatique, il ne se répond pas.</p>'
        '</div>'
    )


def send_counselor_approved(profile: CounselorProfile) -> bool:
    limits = (
        f"<li>Nombre de codes : {profile.max_codes}</li>"
        if profile.max_codes is not None
        else "<li>Nombre de codes : illimité</li>"
    ) + (
        f"<li>Utilisations par code : {profile.max_uses_per_code}</li>"
        if profile.max_uses_per_code is not None
        else "<li>Utilisations par code : illimité</li>"
    )
    body = (
        "<p>Votre compte conseiller est activé.</p>"
        "<p>Vous pouvez maintenant créer des codes pour les personnes que vous "
        "accompagnez, et suivre leur utilisation depuis votre espace.</p>"
        f'<ul style="font-size:14px">{limits}</ul>'
        f'<p><a href="{APP_URL}/conseiller" '
        'style="color:#c96442">Ouvrir mon espace conseiller</a></p>'
    )
    return send(profile.user.email, "Votre compte conseiller est activé", _layout(
        "Compte conseiller activé", body,
    ))


def send_counselor_rejected(profile: CounselorProfile) -> bool:
    reason = html_escape.escape(profile.decision_reason or "")
    body = (
        "<p>Votre demande de compte conseiller n'a pas été retenue.</p>"
        f'<p style="padding:12px;background:#f3eee2;border-radius:8px">{reason}</p>'
        "<p>Votre compte reste utilisable comme compte candidat.</p>"
    )
    return send(profile.user.email, "Votre demande de compte conseiller", _layout(
        "Demande non retenue", body,
    ))
```

- [ ] **Step 4: Add `MAIL_FROM` to `backend/app/config.py` after line 28**

```python
    # Resend refuses a From on an unverified domain, so neoori.tech must carry
    # the DNS records before the first mail goes out.
    MAIL_FROM = os.environ.get("MAIL_FROM", "neoori <bonjour@neoori.tech>")
```

And add to `backend/.env.example` under the existing `RESEND_API_KEY` line:

```
MAIL_FROM=neoori <bonjour@neoori.tech>
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_email_service.py -v`
Expected: 5 passed

- [ ] **Step 6: Wire the two mails into the decisions (Task 6's routes)**

In `backend/app/routes/admin.py`, add the import:

```python
from ..services import email_service
```

Replace the placeholder comment in `approve_counselor_application`:

```python
    email_service.send_counselor_approved(profile)
```

and the one in `reject_counselor_application`:

```python
    email_service.send_counselor_rejected(profile)
```

Both sit **after** `db.session.commit()`, on purpose: the decision is already durable, and a provider outage must not turn it into a 500 the admin retries.

- [ ] **Step 7: Add the test that the approval mails the conseiller**

Append to `backend/tests/test_counselor_review.py`:

```python
def test_approving_mails_the_conseiller(client, admin_headers, app):
    _user, profile = _demande()
    with patch("app.services.email_service.send") as mock_send:
        client.post(
            f"/api/admin/counselor-applications/{profile.id}/approve",
            json={}, headers=admin_headers,
        )
    assert mock_send.called
    assert mock_send.call_args[0][0] == "conseiller@test.com"


def test_a_mail_failure_does_not_undo_the_approval(client, admin_headers, app):
    """send() is fail-soft, but pin it: the decision has already committed."""
    user, profile = _demande()
    with patch("app.services.email_service.send", return_value=False):
        r = client.post(
            f"/api/admin/counselor-applications/{profile.id}/approve",
            json={}, headers=admin_headers,
        )
    assert r.status_code == 200
    db.session.refresh(user)
    assert user.role == "counselor"
```

Add to that file's imports:

```python
from unittest.mock import patch
```

- [ ] **Step 8: Run both files**

Run: `cd backend && venv/bin/pytest tests/test_email_service.py tests/test_counselor_review.py -v`
Expected: 5 + 12 passed

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/email_service.py backend/app/config.py backend/.env.example \
        backend/app/routes/admin.py \
        backend/tests/test_email_service.py backend/tests/test_counselor_review.py
git commit -m "feat(conseiller): approval and rejection emails"
```

- [ ] **Step 10: Note for deployment (do not implement)**

Add `MAIL_FROM` and a real `RESEND_API_KEY` to `/srv/neoori/.env` on the VPS, and verify the sending domain in the Resend dashboard, before announcing the feature. Without them every decision still works and the mail is silently skipped with a warning in the logs.

---

## Task 8: The conseiller's codes

**Files:**
- Modify: `backend/app/routes/counselor_space.py`
- Test: `backend/tests/test_counselor_codes.py`

**Interfaces:**
- Consumes: `approved_counselor_required` (Task 4), `code_service.redemption_count` (Task 2), `CounselorProfile` (Task 1).
- Produces: `GET/POST /api/counselor/codes`, `DELETE /api/counselor/codes/<id>`. Code rows come back as `code.to_dict()` plus `"uses"` (real count) and `"statut"` (`actif|utilise|expire|revoque`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_counselor_codes.py`:

```python
"""Minting, within the admin's two dials.

The clamp is the load-bearing rule: a conseiller may set a code lower than
their ceiling (a code for one person) and never higher.
"""
from datetime import datetime, timedelta

from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.code_redemption import CodeRedemption
from app.models.counselor_code import CounselorCode
from app.models.counselor_profile import CounselorProfile
from app.models.user import User


def _conseiller(max_codes=None, max_uses_per_code=None, status="approved", email="c@test.com"):
    u = User(email=email, password_hash="x", role="counselor")
    db.session.add(u)
    db.session.commit()
    db.session.add(CounselorProfile(
        user_id=u.id, structure="s", fonction="f", telephone="t", status=status,
        max_codes=max_codes, max_uses_per_code=max_uses_per_code,
    ))
    db.session.commit()
    token = create_access_token(identity=str(u.id), additional_claims={"role": "counselor"})
    return u, {"Authorization": f"Bearer {token}"}


def test_a_new_code_is_single_use_and_expires(client, app):
    _user, headers = _conseiller()
    r = client.post("/api/counselor/codes", json={"label": "Karim"}, headers=headers)
    assert r.status_code == 201
    code = r.get_json()["code"]
    assert code["label"] == "Karim"
    assert code["max_uses"] == 1
    assert code["expires_at"] is not None


def test_max_uses_is_clamped_to_the_admin_ceiling(client, app):
    _user, headers = _conseiller(max_uses_per_code=5)
    r = client.post(
        "/api/counselor/codes",
        json={"label": "Atelier", "max_uses": 40},
        headers=headers,
    )
    assert r.status_code == 201
    assert r.get_json()["code"]["max_uses"] == 5


def test_a_lower_number_is_kept(client, app):
    _user, headers = _conseiller(max_uses_per_code=5)
    r = client.post("/api/counselor/codes", json={"label": "Karim", "max_uses": 1}, headers=headers)
    assert r.get_json()["code"]["max_uses"] == 1


def test_max_codes_counts_codes_ever_created(client, app):
    """Decision 5: revoking an unused code must not refill the budget."""
    _user, headers = _conseiller(max_codes=1)
    first = client.post("/api/counselor/codes", json={"label": "A"}, headers=headers)
    assert first.status_code == 201

    client.delete(f"/api/counselor/codes/{first.get_json()['code']['id']}", headers=headers)

    r = client.post("/api/counselor/codes", json={"label": "B"}, headers=headers)
    assert r.status_code == 409
    assert "autorisé" in r.get_json()["error"]


def test_a_code_needs_a_label(client, app):
    _user, headers = _conseiller()
    assert client.post("/api/counselor/codes", json={}, headers=headers).status_code == 400


def test_the_list_shows_real_use_counts_and_a_status(client, app):
    user, headers = _conseiller()
    code = CounselorCode(label="Karim", owner_id=user.id, max_uses=1)
    db.session.add(code)
    db.session.commit()
    db.session.add(CodeRedemption(code_id=code.id, target_type="voyage", target_id="v-1"))
    db.session.commit()

    rows = client.get("/api/counselor/codes", headers=headers).get_json()["codes"]
    assert rows[0]["uses"] == 1
    assert rows[0]["statut"] == "utilise"


def test_an_expired_code_reads_as_expired(client, app):
    user, headers = _conseiller()
    db.session.add(CounselorCode(
        label="Vieux", owner_id=user.id, max_uses=1,
        expires_at=datetime.utcnow() - timedelta(days=1),
    ))
    db.session.commit()
    rows = client.get("/api/counselor/codes", headers=headers).get_json()["codes"]
    assert rows[0]["statut"] == "expire"


def test_a_conseiller_sees_only_their_own_codes(client, app):
    mine, headers = _conseiller(email="mine@test.com")
    other, _ = _conseiller(email="other@test.com")
    db.session.add(CounselorCode(label="à moi", owner_id=mine.id))
    db.session.add(CounselorCode(label="pas à moi", owner_id=other.id))
    db.session.add(CounselorCode(label="admin", owner_id=None))
    db.session.commit()

    labels = [c["label"] for c in client.get("/api/counselor/codes", headers=headers).get_json()["codes"]]
    assert labels == ["à moi"]


def test_a_used_code_cannot_be_revoked(client, app):
    user, headers = _conseiller()
    code = CounselorCode(label="Karim", owner_id=user.id, max_uses=1)
    db.session.add(code)
    db.session.commit()
    db.session.add(CodeRedemption(code_id=code.id, target_type="voyage", target_id="v-1"))
    db.session.commit()

    r = client.delete(f"/api/counselor/codes/{code.id}", headers=headers)
    assert r.status_code == 409


def test_a_pending_conseiller_cannot_mint(client, app):
    _user, headers = _conseiller(status="pending")
    assert client.post("/api/counselor/codes", json={"label": "x"}, headers=headers).status_code == 403
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_counselor_codes.py -v`
Expected: FAIL — 404 on `/api/counselor/codes`.

- [ ] **Step 3: Append to `backend/app/routes/counselor_space.py`**

Add to the imports at the top of the file:

```python
from datetime import timedelta

from ..models.counselor_code import CounselorCode
from ..services import code_service
from ..utils.decorators import approved_counselor_required
```

Then append:

```python
# A conseiller-minted code is for one person unless they say otherwise, and it
# stops being valid after this long. An unredeemed single-use code would
# otherwise stay live for ever: mint fifty, use twelve, and thirty-eight are
# still in circulation a year later.
DEFAULT_MAX_USES = 1
DEFAULT_EXPIRY_DAYS = 90


def _profile_or_none():
    return CounselorProfile.query.filter_by(user_id=get_jwt_identity()).first()


def _code_row(code: CounselorCode, uses: int) -> dict:
    """The code, its real use count, and one French status for the table."""
    if code.revoked_at is not None or not code.is_active:
        statut = "revoque"
    elif code.max_uses is not None and uses >= code.max_uses:
        statut = "utilise"
    elif code.expires_at is not None and code.expires_at <= datetime.utcnow():
        statut = "expire"
    else:
        statut = "actif"
    return {**code.to_dict(), "uses": uses, "statut": statut}


def _use_counts(code_ids: list[str]) -> dict[str, int]:
    """One grouped query instead of a count per row."""
    if not code_ids:
        return {}
    rows = (
        db.session.query(CodeRedemption.code_id, db.func.count(CodeRedemption.id))
        .filter(CodeRedemption.code_id.in_(code_ids))
        .group_by(CodeRedemption.code_id)
        .all()
    )
    return {code_id: count for code_id, count in rows}


@counselor_space_bp.get("/codes")
@approved_counselor_required
def list_codes():
    codes = (
        CounselorCode.query
        .filter_by(owner_id=get_jwt_identity())
        .order_by(CounselorCode.created_at.desc())
        .all()
    )
    counts = _use_counts([c.id for c in codes])
    return jsonify({"codes": [_code_row(c, counts.get(c.id, 0)) for c in codes]}), 200


@counselor_space_bp.post("/codes")
@approved_counselor_required
def create_code():
    """Mint a code, inside the admin's two dials.

    max_uses is clamped rather than refused: a conseiller asking for more
    places than their ceiling gets the ceiling, which is what they would have
    typed had they known it. max_codes is refused, because there is no
    smaller version of "one more code".
    """
    profile = _profile_or_none()
    if profile is None:
        return jsonify({"error": "Accès non autorisé."}), 403

    data = json_object()
    label = text_field(data, "label")
    if not label:
        return jsonify({"error": "Un libellé est requis."}), 400

    if profile.max_codes is not None:
        # Codes ever created, not codes still active: counting active ones lets
        # a revoked code be re-minted for ever (spec decision 5).
        created = CounselorCode.query.filter_by(owner_id=profile.user_id).count()
        if created >= profile.max_codes:
            return jsonify({
                "error": "Vous avez atteint votre nombre de codes autorisé."
            }), 409

    requested = data.get("max_uses")
    max_uses = requested if isinstance(requested, int) and not isinstance(requested, bool) else DEFAULT_MAX_USES
    max_uses = max(1, max_uses)
    if profile.max_uses_per_code is not None:
        max_uses = min(max_uses, profile.max_uses_per_code)

    days = data.get("expires_in_days")
    days = days if isinstance(days, int) and not isinstance(days, bool) and days > 0 else DEFAULT_EXPIRY_DAYS

    code = CounselorCode(
        label=label,
        owner_id=profile.user_id,
        created_by_id=profile.user_id,
        max_uses=max_uses,
        expires_at=datetime.utcnow() + timedelta(days=days),
    )
    db.session.add(code)
    db.session.commit()
    return jsonify({"code": _code_row(code, 0)}), 201


@counselor_space_bp.delete("/codes/<code_id>")
@approved_counselor_required
def revoke_code(code_id):
    """Revoke an unredeemed code. A redeemed one stays: the bénéficiaire has
    already been unlocked by it, and the row is their trace on the dashboard."""
    code = CounselorCode.query.get_or_404(code_id)
    if code.owner_id != get_jwt_identity():
        return jsonify({"error": "Accès non autorisé."}), 403
    if code_service.redemption_count(code.id) > 0:
        return jsonify({"error": "Ce code a déjà été utilisé."}), 409

    code.is_active = False
    code.revoked_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"code": _code_row(code, 0)}), 200
```

Also add `CodeRedemption` to the model imports at the top of the file:

```python
from ..models.code_redemption import CodeRedemption
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_counselor_codes.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/counselor_space.py backend/tests/test_counselor_codes.py
git commit -m "feat(conseiller): mint single-use codes within the admin's limits"
```

---

## Task 9: Dashboard data — stats and bénéficiaires

**Files:**
- Modify: `backend/app/routes/counselor_space.py`
- Test: `backend/tests/test_counselor_dashboard.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `GET /api/counselor/stats` → `{beneficiaires, accompagnements, codes_crees, max_codes, codes_restants, codes_en_circulation}`; `GET /api/counselor/beneficiaires` → `{beneficiaires: [{prenom, email, redeemed_at, target_type}]}`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_counselor_dashboard.py`:

```python
"""The four tiles and the list.

Two rules are pinned here: « Accompagnements » counts validated portraits and
not codes handed out, and the list names people without exposing anything they
wrote.
"""
from datetime import datetime, timedelta

from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.code_redemption import CodeRedemption
from app.models.counselor_code import CounselorCode
from app.models.counselor_profile import CounselorProfile
from app.models.profile import Profile
from app.models.user import User
from app.models.voyage import Voyage


def _conseiller(max_codes=None, email="c@test.com"):
    u = User(email=email, password_hash="x", role="counselor")
    db.session.add(u)
    db.session.commit()
    db.session.add(CounselorProfile(
        user_id=u.id, structure="s", fonction="f", telephone="t",
        status="approved", max_codes=max_codes,
    ))
    db.session.commit()
    token = create_access_token(identity=str(u.id), additional_claims={"role": "counselor"})
    return u, {"Authorization": f"Bearer {token}"}


def _beneficiaire(prenom, email):
    u = User(email=email, password_hash="x", role="candidate")
    db.session.add(u)
    db.session.commit()
    db.session.add(Profile(user_id=u.id, prenom=prenom))
    db.session.commit()
    return u


def test_stats_count_redemptions_not_codes(client, app):
    user, headers = _conseiller(max_codes=10)
    code = CounselorCode(label="Karim", owner_id=user.id, max_uses=1)
    unused = CounselorCode(label="Sonia", owner_id=user.id, max_uses=1,
                           expires_at=datetime.utcnow() + timedelta(days=30))
    db.session.add_all([code, unused])
    db.session.commit()
    db.session.add(CodeRedemption(code_id=code.id, target_type="voyage", target_id="v-1"))
    db.session.commit()

    stats = client.get("/api/counselor/stats", headers=headers).get_json()
    assert stats["beneficiaires"] == 1
    assert stats["codes_crees"] == 2
    assert stats["codes_restants"] == 8
    assert stats["codes_en_circulation"] == 1     # only the unused, unexpired one


def test_codes_restants_is_null_when_illimite(client, app):
    _user, headers = _conseiller()
    stats = client.get("/api/counselor/stats", headers=headers).get_json()
    assert stats["max_codes"] is None
    assert stats["codes_restants"] is None


def test_accompagnements_counts_validated_portraits(client, app):
    user, headers = _conseiller()
    candidate = _beneficiaire("Karim", "k@test.com")
    db.session.add(Voyage(user_id=candidate.id, validated_by_id=user.id))
    db.session.add(Voyage(user_id=candidate.id))       # not validated by anyone
    db.session.commit()

    stats = client.get("/api/counselor/stats", headers=headers).get_json()
    assert stats["accompagnements"] == 1


def test_beneficiaires_are_named_and_nothing_more(client, app):
    user, headers = _conseiller()
    candidate = _beneficiaire("Karim", "karim@test.com")
    code = CounselorCode(label="Karim", owner_id=user.id, max_uses=1)
    db.session.add(code)
    db.session.commit()
    db.session.add(CodeRedemption(
        code_id=code.id, user_id=candidate.id, target_type="voyage", target_id="v-1",
    ))
    db.session.commit()

    rows = client.get("/api/counselor/beneficiaires", headers=headers).get_json()["beneficiaires"]
    assert len(rows) == 1
    assert rows[0]["prenom"] == "Karim"
    assert rows[0]["email"] == "karim@test.com"
    assert rows[0]["target_type"] == "voyage"
    # No link, no token, no content — spec decision 9.
    assert "target_id" not in rows[0]
    assert "share_token" not in rows[0]


def test_an_anonymous_redemption_still_appears(client, app):
    user, headers = _conseiller()
    code = CounselorCode(label="Atelier", owner_id=user.id, max_uses=5)
    db.session.add(code)
    db.session.commit()
    db.session.add(CodeRedemption(code_id=code.id, target_type="analysis", target_id="a-1"))
    db.session.commit()

    rows = client.get("/api/counselor/beneficiaires", headers=headers).get_json()["beneficiaires"]
    assert rows[0]["prenom"] is None
    assert rows[0]["email"] is None


def test_another_conseillers_beneficiaires_are_invisible(client, app):
    _mine, headers = _conseiller(email="mine@test.com")
    other, _ = _conseiller(email="other@test.com")
    code = CounselorCode(label="pas à moi", owner_id=other.id)
    db.session.add(code)
    db.session.commit()
    db.session.add(CodeRedemption(code_id=code.id, target_type="voyage", target_id="v-9"))
    db.session.commit()

    rows = client.get("/api/counselor/beneficiaires", headers=headers).get_json()["beneficiaires"]
    assert rows == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_counselor_dashboard.py -v`
Expected: FAIL — 404 on `/api/counselor/stats`.

- [ ] **Step 3: Append to `backend/app/routes/counselor_space.py`**

Add to the imports:

```python
from ..models.profile import Profile
from ..models.voyage import Voyage
```

Then append:

```python
def _my_code_ids(user_id: str) -> list[str]:
    return [row.id for row in CounselorCode.query.filter_by(owner_id=user_id).all()]


@counselor_space_bp.get("/stats")
@approved_counselor_required
def stats():
    """The four tiles.

    « Bénéficiaires » counts redemptions and « Accompagnements » counts
    portraits this conseiller validated. Kept apart on purpose: handing out a
    code is not the same as doing the work.
    """
    profile = _profile_or_none()
    if profile is None:
        return jsonify({"error": "Accès non autorisé."}), 403
    user_id = profile.user_id

    codes = CounselorCode.query.filter_by(owner_id=user_id).all()
    counts = _use_counts([c.id for c in codes])
    now = datetime.utcnow()

    in_circulation = sum(
        1
        for c in codes
        if c.is_active
        and c.revoked_at is None
        and (c.expires_at is None or c.expires_at > now)
        and (c.max_uses is None or counts.get(c.id, 0) < c.max_uses)
    )

    return jsonify({
        "beneficiaires": sum(counts.values()),
        "accompagnements": Voyage.query.filter_by(validated_by_id=user_id).count(),
        "codes_crees": len(codes),
        "max_codes": profile.max_codes,
        "codes_restants": (
            None if profile.max_codes is None else max(0, profile.max_codes - len(codes))
        ),
        "codes_en_circulation": in_circulation,
        "max_uses_per_code": profile.max_uses_per_code,
    }), 200


@counselor_space_bp.get("/beneficiaires")
@approved_counselor_required
def beneficiaires():
    """Who used my codes, and when. Nothing they wrote.

    Reaching a voyage or a report still requires the person to hand over their
    own token — spec decision 9. No id and no token leaves this route.
    """
    code_ids = _my_code_ids(get_jwt_identity())
    if not code_ids:
        return jsonify({"beneficiaires": []}), 200

    rows = (
        db.session.query(CodeRedemption, User, Profile)
        .outerjoin(User, User.id == CodeRedemption.user_id)
        .outerjoin(Profile, Profile.user_id == User.id)
        .filter(CodeRedemption.code_id.in_(code_ids))
        .order_by(CodeRedemption.redeemed_at.desc())
        .all()
    )
    return jsonify({"beneficiaires": [
        {
            "prenom": profile.prenom if profile else None,
            "email": user.email if user else None,
            "target_type": redemption.target_type,
            "redeemed_at": redemption.redeemed_at.isoformat(),
        }
        for redemption, user, profile in rows
    ]}), 200
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && venv/bin/pytest tests/test_counselor_dashboard.py -v`
Expected: 6 passed

- [ ] **Step 5: Run the whole backend suite**

Run: `cd backend && venv/bin/pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/counselor_space.py backend/tests/test_counselor_dashboard.py
git commit -m "feat(conseiller): dashboard stats and the beneficiaires list"
```

---

## Task 10: Frontend types and API client

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/lib/counselor.ts`

**Interfaces:**
- Consumes: the backend routes from Tasks 5-9.
- Produces: `CounselorProfile`, `CounselorStatus`, `CounselorCodeRow`, `Beneficiaire`, `CounselorStats`, `CounselorApplication` types; `counselor.me/apply/stats/codes/createCode/revokeCode/beneficiaires` and `adminCounselor.list/approve/reject/revoke/limits`.

- [ ] **Step 1: Append the types to `frontend/src/types/index.ts`**

```ts
/** The demande, and the four states /conseiller renders from.
 *  'rejected' never passed review; 'revoked' was approved and withdrawn. */
export type CounselorStatus = "pending" | "approved" | "rejected" | "revoked"

export interface CounselorProfile {
  id: string
  user_id: string
  structure: string
  fonction: string
  telephone: string
  email_pro: string | null
  message: string | null
  status: CounselorStatus
  /** null = illimité, on both. The admin's two dials. */
  max_codes: number | null
  max_uses_per_code: number | null
  decision_reason: string | null
  reviewed_at: string | null
  created_at: string
}

/** A demande as the admin queue sees it: the file plus the account. */
export interface CounselorApplication extends CounselorProfile {
  user: User
}

export type CodeStatut = "actif" | "utilise" | "expire" | "revoque"

export interface CounselorCodeRow {
  id: string
  code: string
  label: string
  is_active: boolean
  max_uses: number | null
  expires_at: string | null
  revoked_at: string | null
  created_at: string
  /** Real count from code_redemptions, not the legacy uses_count. */
  uses: number
  statut: CodeStatut
}

/** Identified, and nothing more: no id, no token, no content (spec decision 9). */
export interface Beneficiaire {
  prenom: string | null
  email: string | null
  target_type: "analysis" | "voyage"
  redeemed_at: string
}

export interface CounselorStats {
  beneficiaires: number
  accompagnements: number
  codes_crees: number
  max_codes: number | null
  codes_restants: number | null
  codes_en_circulation: number
  max_uses_per_code: number | null
}
```

- [ ] **Step 2: Create `frontend/src/lib/counselor.ts`**

```ts
import { api } from "./api"
import type {
  Beneficiaire, CounselorApplication, CounselorCodeRow,
  CounselorProfile, CounselorStats, User,
} from "@/types"

export interface ApplyPayload {
  structure: string
  fonction: string
  telephone: string
  email_pro?: string
  message?: string
  consent: boolean
  /** Omitted when an already-signed-in candidate applies from their espace. */
  email?: string
  password?: string
}

/** The conseiller's own surface. /api/counselor, not /api/c — that one is the
 *  token-addressed share link for an analysis and has no account behind it. */
export const counselor = {
  apply: (payload: ApplyPayload) =>
    api.post<{ user: User; profile: CounselorProfile }>("/counselor/apply", payload),

  /** Readable while pending, rejected or revoked — it is the state switch. */
  me: () =>
    api.get<{ profile: CounselorProfile | null }>("/counselor/me", { skipRedirect: true }),

  stats: () => api.get<CounselorStats>("/counselor/stats"),

  codes: () => api.get<{ codes: CounselorCodeRow[] }>("/counselor/codes"),

  createCode: (label: string, maxUses?: number) =>
    api.post<{ code: CounselorCodeRow }>("/counselor/codes", { label, max_uses: maxUses }),

  revokeCode: (id: string) => api.delete<{ code: CounselorCodeRow }>(`/counselor/codes/${id}`),

  beneficiaires: () => api.get<{ beneficiaires: Beneficiaire[] }>("/counselor/beneficiaires"),
}

export const adminCounselor = {
  list: (status?: string) =>
    api.get<{ applications: CounselorApplication[] }>(
      `/admin/counselor-applications${status ? `?status=${status}` : ""}`,
    ),

  approve: (id: string, maxCodes: number | null, maxUsesPerCode: number | null) =>
    api.post<{ application: CounselorApplication }>(
      `/admin/counselor-applications/${id}/approve`,
      { max_codes: maxCodes, max_uses_per_code: maxUsesPerCode },
    ),

  reject: (id: string, reason: string) =>
    api.post<{ application: CounselorApplication }>(
      `/admin/counselor-applications/${id}/reject`, { reason },
    ),

  revoke: (id: string, reason: string) =>
    api.post<{ application: CounselorApplication }>(
      `/admin/counselor-applications/${id}/revoke`, { reason },
    ),

  limits: (id: string, maxCodes: number | null, maxUsesPerCode: number | null) =>
    api.put<{ application: CounselorApplication }>(
      `/admin/counselor-applications/${id}/limits`,
      { max_codes: maxCodes, max_uses_per_code: maxUsesPerCode },
    ),
}
```

- [ ] **Step 3: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/counselor.ts
git commit -m "feat(conseiller): types and API client for the counselor surface"
```

---

## Task 11: `/inscription-conseiller`

**Files:**
- Create: `frontend/src/app/(auth)/inscription-conseiller/page.tsx`

**Interfaces:**
- Consumes: `counselor.apply` (Task 10), `useAuth().refresh` (existing).

- [ ] **Step 1: Create the page**

Copy the shape of `(auth)/inscription/page.tsx` — `AuthLayout`, react-hook-form + zod, the same field markup.

```tsx
"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useAuth } from "@/lib/auth"
import { ApiError } from "@/lib/api"
import { counselor } from "@/lib/counselor"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"

// The approval file: what the admin decides on. Declared information only —
// no document upload, so a refusal costs the person nothing but the form.
const schema = z
  .object({
    structure: z.string().min(1, "Structure requise."),
    fonction: z.string().min(1, "Fonction requise."),
    telephone: z.string().min(6, "Téléphone requis."),
    email_pro: z.string().email("Email professionnel invalide.").or(z.literal("")),
    message: z.string(),
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

export default function InscriptionConseillerPage() {
  const { refresh } = useAuth()
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { consent: false, message: "", email_pro: "" },
  })

  const onSubmit = async (values: Fields) => {
    setError(null)
    try {
      await counselor.apply({
        structure: values.structure,
        fonction: values.fonction,
        telephone: values.telephone,
        email_pro: values.email_pro || undefined,
        message: values.message || undefined,
        email: values.email,
        password: values.password,
        consent: values.consent,
      })
      // apply() sets the cookies; refresh() puts the user in context before the
      // /conseiller page reads it.
      await refresh()
      router.push("/conseiller")
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur lors de l'envoi de la demande.")
    }
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-bold text-navy">Compte conseiller</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Votre demande est examinée avant l&apos;ouverture du compte.
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="structure">Structure</Label>
          <Input id="structure" className="h-10" placeholder="Cap Emploi 31" {...register("structure")} />
          {errors.structure && <p className="text-xs text-destructive">{errors.structure.message}</p>}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="fonction">Fonction</Label>
            <Input id="fonction" className="h-10" placeholder="Conseillère en insertion" {...register("fonction")} />
            {errors.fonction && <p className="text-xs text-destructive">{errors.fonction.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="telephone">Téléphone</Label>
            <Input id="telephone" type="tel" autoComplete="tel" className="h-10" placeholder="05 61 00 00 00" {...register("telephone")} />
            {errors.telephone && <p className="text-xs text-destructive">{errors.telephone.message}</p>}
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="email_pro">Email professionnel (facultatif)</Label>
          <Input id="email_pro" type="email" className="h-10" placeholder="c.martin@capemploi.fr" {...register("email_pro")} />
          {errors.email_pro && <p className="text-xs text-destructive">{errors.email_pro.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="message">Précisions (facultatif)</Label>
          <Textarea id="message" rows={3} placeholder="Nombre de personnes accompagnées, contexte…" {...register("message")} />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="email">Email de connexion</Label>
          <Input id="email" type="email" autoComplete="email" className="h-10" placeholder="vous@exemple.fr" {...register("email")} />
          {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="password">Mot de passe</Label>
            <Input id="password" type="password" autoComplete="new-password" className="h-10" placeholder="8 caractères minimum" {...register("password")} />
            {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="confirm">Confirmer</Label>
            <Input id="confirm" type="password" autoComplete="new-password" className="h-10" placeholder="••••••••" {...register("confirm")} />
            {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
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
              J&apos;accepte les{" "}
              <Link href="/cgv" target="_blank" className="text-navy underline underline-offset-2">CGV</Link>{" "}
              et la{" "}
              <Link href="/confidentialite" target="_blank" className="text-navy underline underline-offset-2">politique de confidentialité</Link>.
            </span>
          </label>
          {errors.consent && <p className="text-xs text-destructive">{errors.consent.message}</p>}
        </div>

        <Button type="submit" size="lg" className="h-11 w-full" disabled={isSubmitting}>
          {isSubmitting ? "Envoi…" : "Envoyer ma demande"}
        </Button>
      </form>

      <p className="mt-5 text-center text-sm text-muted-foreground">
        Vous cherchez un compte candidat ?{" "}
        <Link href="/inscription" className="link-underline font-medium text-orange-dark">
          Créer un compte
        </Link>
      </p>
    </AuthLayout>
  )
}
```

- [ ] **Step 2: Verify it compiles and renders**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

Then run the dev server on a free port (3001 may be taken by another session) and open the page:
Run: `cd frontend && npx next dev -p 3010`
Open `http://localhost:3010/inscription-conseiller`, submit with an empty form, and confirm each French validation message appears.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(auth)/inscription-conseiller/page.tsx"
git commit -m "feat(conseiller): demande form"
```

---

## Task 12: `/conseiller` — the four-state dashboard

**Files:**
- Create: `frontend/src/app/conseiller/page.tsx`
- Modify: `frontend/src/proxy.ts:5`

**Interfaces:**
- Consumes: `counselor.me/stats/codes/createCode/revokeCode/beneficiaires` (Task 10).

- [ ] **Step 1: Add `/conseiller` to the protected list in `frontend/src/proxy.ts:5`**

```ts
const PROTECTED = ["/admin", "/conseiller", "/profil", "/voyage"]
```

- [ ] **Step 2: Create `frontend/src/app/conseiller/page.tsx`**

```tsx
"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { AppBar } from "@/components/layout/AppBar"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { StatCard } from "@/components/ui/stat-card"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { counselor } from "@/lib/counselor"
import { fmtDate, fmtInt } from "@/lib/format"
import type { Beneficiaire, CodeStatut, CounselorCodeRow, CounselorProfile, CounselorStats } from "@/types"
import { Ban, Check, Copy, KeyRound, Plus, TicketCheck, UserCheck, Users } from "lucide-react"

const STATUT_LABEL: Record<CodeStatut, string> = {
  actif: "Actif",
  utilise: "Utilisé",
  expire: "Expiré",
  revoque: "Révoqué",
}

const STATUT_VARIANT: Record<CodeStatut, "success" | "secondary" | "warning"> = {
  actif: "success",
  utilise: "secondary",
  expire: "warning",
  revoque: "secondary",
}

export default function ConseillerPage() {
  const { user, loading: authLoading, refresh: refreshAuth } = useAuth()
  const router = useRouter()

  const [profile, setProfile] = useState<CounselorProfile | null>(null)
  const [loadingProfile, setLoadingProfile] = useState(true)
  const [stats, setStats] = useState<CounselorStats | null>(null)
  const [codes, setCodes] = useState<CounselorCodeRow[]>([])
  const [people, setPeople] = useState<Beneficiaire[]>([])
  const [error, setError] = useState<string | null>(null)
  const [label, setLabel] = useState("")
  const [places, setPlaces] = useState("1")
  const [creating, setCreating] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  // Expired cookie: keep the deep link so they land back here after signing in.
  useEffect(() => {
    if (!authLoading && !user) router.replace("/connexion?redirect=/conseiller")
  }, [authLoading, user, router])

  useEffect(() => {
    if (authLoading || !user) return
    counselor.me()
      .then((r) => setProfile(r.profile))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erreur de chargement."))
      .finally(() => setLoadingProfile(false))
  }, [authLoading, user])

  const loadDashboard = useCallback(async () => {
    try {
      const [s, c, b] = await Promise.all([
        counselor.stats(), counselor.codes(), counselor.beneficiaires(),
      ])
      setStats(s)
      setCodes(c.codes)
      setPeople(b.beneficiaires)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur de chargement.")
    }
  }, [])

  // Approval flips user.role in the DB, but the access token in the browser
  // still says "candidate" until it expires (1 h) — and every /api/counselor
  // route below /me reads the claim. POST /auth/refresh re-mints it from the
  // row (backend auth.py:93-99); useAuth().refresh is GET /auth/me and does
  // NOT, so both are needed: one for the cookie, one for the context.
  useEffect(() => {
    if (profile?.status !== "approved") return
    const run = async () => {
      if (user && user.role !== "counselor") {
        try {
          await api.post("/auth/refresh")
          await refreshAuth()
        } catch {
          // Refresh cookie gone: the 403 below tells them to sign in again.
        }
      }
      await loadDashboard()
    }
    run()
  }, [profile?.status, user, refreshAuth, loadDashboard])

  const handleCreate = async () => {
    if (!label.trim()) return
    setCreating(true)
    setError(null)
    try {
      const n = Number.parseInt(places, 10)
      await counselor.createCode(label.trim(), Number.isFinite(n) && n > 0 ? n : 1)
      setLabel("")
      setPlaces("1")
      await loadDashboard()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur lors de la création.")
    } finally {
      setCreating(false)
    }
  }

  const handleCopy = async (code: string, id: string) => {
    try {
      await navigator.clipboard.writeText(code)
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    } catch {
      setError("Impossible de copier le code dans le presse-papiers.")
    }
  }

  const handleRevoke = async (id: string) => {
    if (!window.confirm("Révoquer ce code ? Il ne pourra plus être utilisé.")) return
    try {
      await counselor.revokeCode(id)
      await loadDashboard()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur lors de la révocation.")
    }
  }

  if (authLoading || !user || loadingProfile) {
    return (
      <>
        <AppBar />
        <main className="mx-auto max-w-6xl px-5 py-10">
          <Skeleton className="h-8 w-64" />
        </main>
      </>
    )
  }

  return (
    <>
      <AppBar />
      <main className="mx-auto max-w-6xl px-5 py-10">
        <p className="eyebrow text-orange-dark">Espace conseiller</p>
        <h1 className="mt-1 font-display text-2xl font-bold text-navy sm:text-3xl">
          {profile?.status === "approved" ? "Mes bénéficiaires" : "Votre demande"}
        </h1>

        {error && (
          <Alert variant="destructive" className="mt-5">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* No demande at all */}
        {!profile && (
          <div className="mt-6 rounded-2xl bg-card p-6 ring-1 ring-foreground/10">
            <p className="text-sm text-muted-foreground">
              Aucune demande de compte conseiller n&apos;est associée à ce compte.
            </p>
            <Button render={<Link href="/inscription-conseiller" />} size="lg" className="mt-4">
              Faire une demande
            </Button>
          </div>
        )}

        {profile?.status === "pending" && (
          <div className="mt-6 rounded-2xl bg-card p-6 ring-1 ring-foreground/10">
            <p className="text-sm text-navy">Votre demande est en cours d&apos;examen.</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Vous recevrez un email dès qu&apos;elle aura été traitée. En attendant, votre
              compte fonctionne normalement comme compte candidat.
            </p>
            <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
              <div><dt className="eyebrow text-muted-foreground">Structure</dt><dd className="text-navy">{profile.structure}</dd></div>
              <div><dt className="eyebrow text-muted-foreground">Fonction</dt><dd className="text-navy">{profile.fonction}</dd></div>
              <div><dt className="eyebrow text-muted-foreground">Téléphone</dt><dd className="text-navy">{profile.telephone}</dd></div>
              <div><dt className="eyebrow text-muted-foreground">Demande envoyée le</dt><dd className="text-navy">{fmtDate(profile.created_at)}</dd></div>
            </dl>
          </div>
        )}

        {(profile?.status === "rejected" || profile?.status === "revoked") && (
          <div className="mt-6 rounded-2xl bg-card p-6 ring-1 ring-foreground/10">
            <p className="text-sm text-navy">
              {profile.status === "rejected"
                ? "Votre demande n'a pas été retenue."
                : "Votre accès conseiller a été retiré."}
            </p>
            {profile.decision_reason && (
              <p className="mt-3 rounded-lg bg-secondary px-4 py-3 text-sm text-muted-foreground">
                {profile.decision_reason}
              </p>
            )}
            <p className="mt-3 text-sm text-muted-foreground">
              Votre compte reste utilisable comme compte candidat.
            </p>
          </div>
        )}

        {profile?.status === "approved" && (
          <>
            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Bénéficiaires" value={stats ? fmtInt(stats.beneficiaires) : "—"} hint="Codes utilisés" icon={<Users className="size-4" />} />
              <StatCard label="Accompagnements" value={stats ? fmtInt(stats.accompagnements) : "—"} hint="Portraits validés" icon={<UserCheck className="size-4" />} accent />
              <StatCard label="Codes restants" value={stats ? (stats.codes_restants === null ? "Illimité" : fmtInt(stats.codes_restants)) : "—"} hint={stats?.max_codes === null ? "Aucune limite" : `Sur ${fmtInt(stats?.max_codes)}`} icon={<TicketCheck className="size-4" />} />
              <StatCard label="En circulation" value={stats ? fmtInt(stats.codes_en_circulation) : "—"} hint="Codes non utilisés" icon={<KeyRound className="size-4" />} />
            </div>

            <section className="mt-6 rounded-2xl bg-card ring-1 ring-foreground/10 shadow-soft">
              <div className="flex items-center gap-2 border-b border-border px-5 py-4">
                <KeyRound className="size-4 text-orange" />
                <h2 className="font-display text-base font-semibold text-navy">Mes codes</h2>
              </div>

              <div className="px-5 py-4">
                <form
                  onSubmit={(e) => { e.preventDefault(); handleCreate() }}
                  className="mb-5 flex flex-col gap-3 border-b border-border pb-5 sm:flex-row sm:items-end"
                >
                  <div className="flex-1 space-y-1.5">
                    <Label htmlFor="code-label">Pour qui ?</Label>
                    <Input id="code-label" className="h-10" placeholder="Prénom ou référence dossier"
                           value={label} onChange={(e) => setLabel(e.target.value)} disabled={creating} />
                  </div>
                  <div className="w-full space-y-1.5 sm:w-28">
                    <Label htmlFor="code-places">Places</Label>
                    <Input id="code-places" type="number" min={1} className="h-10"
                           value={places} onChange={(e) => setPlaces(e.target.value)} disabled={creating} />
                  </div>
                  <Button type="submit" variant="navy" size="lg" disabled={creating || !label.trim()} className="shrink-0">
                    <Plus className="size-4" />
                    {creating ? "Génération…" : "Générer"}
                  </Button>
                </form>

                <p className="mb-4 text-xs text-muted-foreground">
                  Un code par personne, valable 90 jours. Pour un atelier, indiquez le nombre
                  de places{stats?.max_uses_per_code != null ? ` (${stats.max_uses_per_code} maximum)` : ""}.
                </p>

                <div className="w-full overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left">
                        <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Code</th>
                        <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Libellé</th>
                        <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Statut</th>
                        <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Expire le</th>
                        <th className="eyebrow pb-2 text-right font-medium text-muted-foreground">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {codes.map((c) => (
                        <tr key={c.id} className="border-b border-border/60 last:border-0">
                          <td className="py-3 pr-4"><span className="select-all font-mono font-medium text-navy">{c.code}</span></td>
                          <td className="py-3 pr-4 text-navy">{c.label}</td>
                          <td className="py-3 pr-4"><Badge variant={STATUT_VARIANT[c.statut]}>{STATUT_LABEL[c.statut]}</Badge></td>
                          <td className="py-3 pr-4 font-mono text-xs text-muted-foreground whitespace-nowrap">{fmtDate(c.expires_at)}</td>
                          <td className="py-3">
                            <div className="flex items-center justify-end gap-1.5">
                              <Button size="sm" variant="outline" onClick={() => handleCopy(c.code, c.id)}>
                                {copiedId === c.id
                                  ? <><Check className="size-3.5 text-success" />Copié</>
                                  : <><Copy className="size-3.5" />Copier</>}
                              </Button>
                              {c.statut === "actif" && (
                                <Button size="sm" variant="ghost" onClick={() => handleRevoke(c.id)}
                                        className="text-destructive hover:bg-destructive/10 hover:text-destructive">
                                  <Ban className="size-3.5" />Révoquer
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {codes.length === 0 && (
                  <p className="py-10 text-center text-sm text-muted-foreground">
                    Aucun code généré pour le moment.
                  </p>
                )}
              </div>
            </section>

            <section className="mt-6 rounded-2xl bg-card ring-1 ring-foreground/10 shadow-soft">
              <div className="flex items-center gap-2 border-b border-border px-5 py-4">
                <Users className="size-4 text-orange" />
                <h2 className="font-display text-base font-semibold text-navy">Mes bénéficiaires</h2>
              </div>
              <div className="px-5 py-4">
                <div className="w-full overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left">
                        <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Prénom</th>
                        <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Email</th>
                        <th className="eyebrow pb-2 font-medium text-muted-foreground">Utilisé le</th>
                      </tr>
                    </thead>
                    <tbody>
                      {people.map((p, i) => (
                        <tr key={`${p.email ?? "anon"}-${i}`} className="border-b border-border/60 last:border-0">
                          <td className="py-2.5 pr-4 text-navy">{p.prenom ?? "—"}</td>
                          <td className="py-2.5 pr-4 text-navy">{p.email ?? "Bénéficiaire anonyme"}</td>
                          <td className="py-2.5 font-mono text-xs text-muted-foreground whitespace-nowrap">{fmtDate(p.redeemed_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {people.length === 0 && (
                  <p className="py-10 text-center text-sm text-muted-foreground">
                    Aucun code n&apos;a encore été utilisé.
                  </p>
                )}
              </div>
            </section>
          </>
        )}
      </main>
    </>
  )
}
```

- [ ] **Step 3: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Check the four states by hand**

With the backend running, sign up at `/inscription-conseiller` and confirm `/conseiller` shows « Votre demande est en cours d'examen. ». Approve the demande from the admin panel (Task 13) or directly in the DB, sign out and back in, and confirm the dashboard renders with its four tiles.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/conseiller/page.tsx frontend/src/proxy.ts
git commit -m "feat(conseiller): dashboard with codes and beneficiaires"
```

---

## Task 13: Admin — the Demandes panel

**Files:**
- Modify: `frontend/src/app/admin/conseillers/page.tsx`

**Interfaces:**
- Consumes: `adminCounselor.*` (Task 10).

- [ ] **Step 1: Add the panel above the existing two**

In `frontend/src/app/admin/conseillers/page.tsx`, add to the imports:

```tsx
import { adminCounselor } from "@/lib/counselor"
import type { CounselorApplication } from "@/types"
import { Textarea } from "@/components/ui/textarea"
import { ClipboardList } from "lucide-react"
```

Add the state and handlers inside the component, next to the existing ones:

```tsx
  const [applications, setApplications] = useState<CounselorApplication[]>([])
  const [loadingApps, setLoadingApps] = useState(true)
  const [decidingId, setDecidingId] = useState<string | null>(null)
  // Per-row draft inputs, keyed by application id, so two open rows don't share
  // one box.
  const [limits, setLimits] = useState<Record<string, { codes: string; uses: string }>>({})
  const [reasons, setReasons] = useState<Record<string, string>>({})

  const loadApplications = useCallback(() => {
    setLoadingApps(true)
    adminCounselor.list("pending")
      .then(r => setApplications(r.applications))
      .catch(err => setErrorCounselors(err?.message ?? "Erreur de chargement"))
      .finally(() => setLoadingApps(false))
  }, [])

  useEffect(() => { loadApplications() }, [loadApplications])

  const toInt = (raw: string | undefined) => {
    const n = Number.parseInt(raw ?? "", 10)
    return Number.isFinite(n) && n > 0 ? n : null   // blank = illimité
  }

  const handleApprove = useCallback(async (id: string) => {
    setDecidingId(id)
    try {
      await adminCounselor.approve(id, toInt(limits[id]?.codes), toInt(limits[id]?.uses))
      loadApplications()
    } catch (err) {
      setErrorCounselors(err instanceof ApiError ? err.message : "Erreur lors de l'approbation")
    } finally {
      setDecidingId(null)
    }
  }, [limits, loadApplications])

  const handleReject = useCallback(async (id: string) => {
    const reason = (reasons[id] ?? "").trim()
    if (!reason) {
      setErrorCounselors("Un motif est requis pour refuser une demande.")
      return
    }
    setDecidingId(id)
    try {
      await adminCounselor.reject(id, reason)
      loadApplications()
    } catch (err) {
      setErrorCounselors(err instanceof ApiError ? err.message : "Erreur lors du refus")
    } finally {
      setDecidingId(null)
    }
  }, [reasons, loadApplications])
```

Then insert this section between the summary tiles (line 135) and the existing `<div className="grid …lg:grid-cols-2">`:

```tsx
      <section className="mb-6 rounded-2xl bg-card ring-1 ring-foreground/10 shadow-soft">
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div className="flex items-center gap-2">
            <ClipboardList className="size-4 text-orange" />
            <h2 className="font-display text-base font-semibold text-navy">
              Demandes en attente
            </h2>
          </div>
          <span className="eyebrow text-muted-foreground">
            {applications.length} demande{applications.length !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="px-5 py-4">
          {loadingApps && <Skeleton className="h-24" />}

          {!loadingApps && applications.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Aucune demande en attente.
            </p>
          )}

          <div className="space-y-4">
            {applications.map(a => (
              <article key={a.id} className="rounded-xl border border-border p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="font-display font-semibold text-navy">{a.structure}</h3>
                  <span className="font-mono text-xs text-muted-foreground">{fmtDate(a.created_at)}</span>
                </div>

                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <div><dt className="eyebrow text-muted-foreground">Fonction</dt><dd className="text-navy">{a.fonction}</dd></div>
                  <div><dt className="eyebrow text-muted-foreground">Téléphone</dt><dd className="text-navy">{a.telephone}</dd></div>
                  <div><dt className="eyebrow text-muted-foreground">Email de connexion</dt><dd className="text-navy">{a.user.email}</dd></div>
                  <div><dt className="eyebrow text-muted-foreground">Email professionnel</dt><dd className="text-navy">{a.email_pro ?? "—"}</dd></div>
                </dl>

                {a.message && (
                  <p className="mt-3 rounded-lg bg-secondary px-4 py-3 text-sm text-muted-foreground">
                    {a.message}
                  </p>
                )}

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor={`codes-${a.id}`}>Nombre de codes</Label>
                    <Input
                      id={`codes-${a.id}`} type="number" min={1} className="h-10" placeholder="Illimité"
                      value={limits[a.id]?.codes ?? ""}
                      onChange={e => setLimits(p => ({ ...p, [a.id]: { codes: e.target.value, uses: p[a.id]?.uses ?? "" } }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`uses-${a.id}`}>Utilisations par code</Label>
                    <Input
                      id={`uses-${a.id}`} type="number" min={1} className="h-10" placeholder="Illimité"
                      value={limits[a.id]?.uses ?? ""}
                      onChange={e => setLimits(p => ({ ...p, [a.id]: { codes: p[a.id]?.codes ?? "", uses: e.target.value } }))}
                    />
                  </div>
                </div>

                <div className="mt-3 space-y-1.5">
                  <Label htmlFor={`reason-${a.id}`}>Motif (requis pour refuser)</Label>
                  <Textarea
                    id={`reason-${a.id}`} rows={2}
                    value={reasons[a.id] ?? ""}
                    onChange={e => setReasons(p => ({ ...p, [a.id]: e.target.value }))}
                  />
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <Button variant="navy" size="lg" disabled={decidingId === a.id} onClick={() => handleApprove(a.id)}>
                    <Check className="size-4" />
                    {decidingId === a.id ? "…" : "Approuver"}
                  </Button>
                  <Button
                    variant="ghost" size="lg" disabled={decidingId === a.id} onClick={() => handleReject(a.id)}
                    className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                  >
                    <Ban className="size-4" />Refuser
                  </Button>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
```

Finally update the page's subtitle (line 109-111) — the admin no longer creates conseillers by hand:

```tsx
        <p className="mt-1 text-sm text-muted-foreground">
          Demandes de comptes conseiller, comptes actifs, et codes d’accès créés directement.
        </p>
```

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Approve a demande end to end**

With both servers running: submit a demande, sign in as admin, open `/admin/conseillers`, set 25 / 1, approve. Sign in as the conseiller and confirm `/conseiller` shows the dashboard with « Codes restants 25 ».

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/admin/conseillers/page.tsx
git commit -m "feat(conseiller): admin queue to approve or refuse a demande"
```

---

## Task 14: Guards, navigation, and the legal line

**Files:**
- Modify: `frontend/src/app/admin/layout.tsx`
- Modify: `frontend/src/components/layout/AppBar.tsx`
- Modify: `frontend/src/app/(legal)/confidentialite/page.tsx` ⚠ **another session holds edits here**
- Modify: `frontend/src/app/(legal)/cgv/page.tsx` ⚠ **another session holds edits here**

**Interfaces:**
- Consumes: `useAuth()` (existing).

- [ ] **Step 1: Add the missing role guard to `frontend/src/app/admin/layout.tsx`**

The shell currently renders for anyone with a cookie — `proxy.ts:13` checks presence only, and this layout calls `useAuth()` for logout alone. Change line 24 and add the guard before the return:

```tsx
  const { user, loading, logout } = useAuth()

  // The proxy checks that a cookie exists, not what it says. Without this a
  // signed-in candidate typing /admin renders the entire admin shell and only
  // meets 403s in the data — the pattern copied from voyage/c/[token]:91-92,
  // which refuses before it fetches.
  useEffect(() => {
    if (!loading && !user) router.replace("/connexion?redirect=/admin")
  }, [loading, user, router])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-secondary">
        <Skeleton className="h-8 w-48" />
      </div>
    )
  }

  if (!user || user.role !== "admin") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-secondary px-5">
        <div className="max-w-md rounded-2xl bg-card p-6 text-center ring-1 ring-foreground/10">
          <h1 className="font-display text-lg font-semibold text-navy">Accès réservé</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Cette page est réservée à l&apos;administration.
          </p>
          <Button render={<Link href="/espace" />} size="lg" className="mt-4">
            Retour à mon espace
          </Button>
        </div>
      </div>
    )
  }
```

Add `useEffect` to the React import and `Skeleton` to the component imports:

```tsx
import { useEffect } from "react"
import { Skeleton } from "@/components/ui/skeleton"
```

- [ ] **Step 2: Add the conseiller entry to `frontend/src/components/layout/AppBar.tsx`**

After the `/voyage` item (line 56) and before the admin item:

```tsx
                {user.role === "counselor" && (
                  <DropdownMenuItem render={<Link href="/conseiller" />}>
                    <UserCheck />
                    Espace conseiller
                  </DropdownMenuItem>
                )}
```

Add `UserCheck` to the lucide import on line 11.

- [ ] **Step 3: Verify both compile and the guard bites**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

Then sign in as a candidate, type `/admin`, and confirm « Accès réservé » renders instead of the admin shell.

- [ ] **Step 4: Commit the guard and the nav — by path**

```bash
git add frontend/src/app/admin/layout.tsx frontend/src/components/layout/AppBar.tsx
git commit -m "fix(admin): refuse the admin shell to non-admins"
```

- [ ] **Step 5: Coordinate before touching the two legal pages**

`(legal)/confidentialite/page.tsx` and `(legal)/cgv/page.tsx` both carry another session's uncommitted edits. **Ask before editing them.** Once clear, add to `/confidentialite`, in the section listing who sees what:

> Si vous utilisez un code fourni par un conseiller, celui-ci voit votre prénom, votre adresse email et la date d'utilisation du code. Il n'a accès ni à votre analyse, ni à votre voyage, ni à aucun contenu que vous avez rédigé.

And to `/cgv`, in the accounts section:

> Un compte conseiller est ouvert après examen de la demande. Les codes créés par un conseiller donnent un accès gratuit aux analyses payantes, dans la limite fixée lors de l'ouverture du compte.

Commit those two files alone, by path, once the other session confirms:

```bash
git add "frontend/src/app/(legal)/confidentialite/page.tsx" "frontend/src/app/(legal)/cgv/page.tsx"
git commit -m "docs(legal): what a conseiller sees of a beneficiaire"
```

---

## Verification before calling this done

- [ ] `cd backend && venv/bin/pytest -q` — whole suite green, including `test_unlock.py`, `test_voyage_routes.py`, `test_malformed_bodies.py` and `test_migration_chain.py`
- [ ] `cd frontend && npx tsc --noEmit` — clean
- [ ] `cd frontend && npx next build` — builds
- [ ] `cd backend && venv/bin/flask db upgrade` against a scratch database, then run it **a second time** — the migration is idempotent and the second run must be a no-op
- [ ] End to end on a local stack: demande → admin approval → conseiller mints a code → candidate redeems it → the bénéficiaire appears on the conseiller dashboard
- [ ] `git status --short` shows none of the other session's eleven files staged by you

---

## Deployment notes (not part of any task)

- `MAIL_FROM` and a real `RESEND_API_KEY` must be in `/srv/neoori/.env`, and `neoori.tech` verified as a sending domain in Resend, before the first approval mail leaves.
- The production container applies migrations at start (`backend/entrypoint.sh:24`), so `e7f8a9b0c1d2` needs no manual step. A **local** database needs `flask db upgrade` run by hand — see CLAUDE.md's seed-vs-migration section.
- No seed script is needed: this feature adds no prompt slot.
