# Les quatre portes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open the parcours 1 form to everyone and put four doors behind its
submit button — account (free tier), advisor code (Complet, report to the
counselor only), promo code (Complet, signed in), no login (free tier, private
link) — with the server deciding each door's tier and recipient.

**Architecture:** One pure rule table (`services/doors.py`) decides what each
door runs and for whom; `create_analysis` becomes the single submit that
applies it. Ownership is expressed by columns on `analyses` (`door`,
`counselor_id`, `access_token_hash`, `pending_user_id`). The database itself
enforces code limits (`code_redemptions.slot`, unique keys), and the daily caps
read an append-only `run_log`. Tokens live in an HttpOnly cookie (drafts) or
in a URL fragment (reports), never in a logged URL.

**Tech Stack:** Flask 3 + Flask-SQLAlchemy + Alembic (MySQL 8.4 in prod, SQLite
in tests), flask-jwt-extended (cookie JWT), pytest; Next.js 16 App Router +
TypeScript + Tailwind + shadcn/base-ui; nginx 1.29; gunicorn.

**Spec:** `docs/superpowers/specs/2026-10-08-four-doors-design.md` (this
branch, `feat/four-doors`). Decision numbers below (« decision 23 ») refer to
it. Read it first.

## Before you start (mandatory)

This plan was written on 2026-10-08 against `feat/social-sign-in` (27341dd)
plus the **sub-project 1 spec**. The build may only start once both
`feat/remove-parcours-2-3` and `feat/social-sign-in` are merged into
`initial`. Then:

1. Rebase this branch on `initial`: `git rebase initial`.
2. **Re-check every file/line reference in this plan against the merged code.**
   Line numbers here are indicative. Sub-project 1 removes parcours 2/3, so
   expect `create_analysis` to already stamp `_path = "1"` unconditionally,
   `VALIDATORS` to hold only `"1"`, `_FORCE_TIER`'s comment to say
   `/srv/neoori/.env`, and `section_registry.PARCOURS` to have one entry.
   Wherever this plan shows "current code", trust the merged file over the
   plan, and keep the plan's *intent*.
3. Find the migration head and use it as `down_revision` in Task 1:
   ```bash
   cd backend && python3 - <<'PY'
   import re, glob
   revs, downs = {}, set()
   for f in glob.glob("migrations/versions/*.py"):
       s = open(f).read()
       revs[re.search(r"^revision\s*=\s*['\"](\w+)", s, re.M).group(1)] = f
       downs |= set(re.findall(r"['\"](\w+)['\"]", re.search(r"^down_revision\s*=\s*(.+)$", s, re.M).group(1)))
   print([r for r in revs if r not in downs])
   PY
   ```
   Expected today: `['b0c1d2e3f4a5']` (sub-project 1 adds no migration).
4. Baseline: `cd backend && python -m pytest -q` — record the pass count. Every
   task ends with the full suite green, except the tests a task explicitly
   rewrites.
5. Backend tests: `cd backend && python -m pytest tests/<file> -q`. Frontend
   checks: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`.
   The frontend has no unit-test runner; its tasks end with those three plus
   a manual check through the local stack (`docker compose up -d` →
   http://localhost:8080).

## Global Constraints

- UI copy is French; code comments and commit messages are English (CLAUDE.md).
- No UI string may contain: boussole, copilote, miroir, révélation,
  épanouissement, alignement, excellence, talent unique, vous vous démarquez.
- Every French string in this plan is copied verbatim from the spec's « Copy »
  section; do not reword. The PM approves copy before launch, not during the
  build.
- New UI never uses `window.confirm`, `alert` or `prompt`: in-page confirmation
  only (spec, counselor delete).
- Migrations are idempotent, one guard per object (repo convention:
  `entrypoint.sh` runs `flask db upgrade` at every container start and MySQL
  DDL is not transactional).
- A client never sets a server-owned input key: `_voyage`, `_voyage_id`,
  `_conditions`, `_oeth`, `_tier`, `_path` (decision 37).
- "Signed in" means a valid, unexpired access token, read with
  `_optional_user_id()` — never `@jwt_required(optional=True)` on the open
  endpoints (decision 38).
- Mails are fail-soft (`email_service` returns False, never raises into a
  route) and never carry report content or a bénéficiaire's name.
- Tests that create an analysis patch the thread spawn:
  `@patch("app.routes.analyses.start_analysis")` (or the service module that
  imports it). No test may reach Anthropic.
- Limits (env, read from `current_app.config`): `ANONYMOUS_RUNS_PER_DAY=200`,
  `FREE_RUNS_PER_ACCOUNT_PER_DAY=5`, `ANONYMOUS_RETENTION_DAYS=30`,
  `ADVISOR_RETENTION_DAYS=365`, `HELD_DRAFT_RETENTION_HOURS=48`,
  `CV_TEXT_MAX=40000`, `CIBLE_MAX=10000`; prénom / nom ≤ 80 characters.
- Commit messages end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

The inputs and conditions most likely to bite a real person that no spec
requirement names directly. Each has its test in the owning task.

1. **Accents, apostrophes and stray spaces in prénom / nom** at the advisor
   door (« Zoé », « N'Guessan-Kouamé », «  Marie  »): stored trimmed, counted
   in characters not bytes, accepted up to 80 — Task 6.
2. **A code typed the way people type codes** (« abcd-1234 », « ABCD 1234 »,
   lowercase) at the door, at `/codes/check` and at `/debloquer`: normalised,
   accepted — Task 3.
3. **A long but real CV**: a 39 999-character paste passes, 40 001 fails,
   measured after trimming — Task 2.
4. **A counselor double-clicking « Relancer »**: the second click is refused
   (409) while the first run is queued or running, so one failure never
   becomes two paid runs — Task 10.
5. **Two tabs, one browser**: saving a signed-out draft twice reuses the same
   held row (one cookie), and claiming twice returns 404 the second time
   without breaking the form — Task 7.

---

## File structure

**Backend — new**
- `backend/app/services/analysis_inputs.py` — the client input allow-list and
  length caps (decision 37). One function, `clean()`.
- `backend/app/services/doors.py` — the door table (`Plan`), `decide()`, the
  daily caps over `run_log`, `log_run()`.
- `backend/app/services/held.py` — the `neoori_hold` cookie: set, clear, read
  the held row, mark for a new account, attach, unmark.
- `backend/app/services/purge.py` — selection and deletion for
  `flask purge-expired`.
- `backend/app/cli.py` — registers `flask purge-expired`.
- `backend/app/models/run_log.py` — `RunLog`.
- `backend/app/routes/codes.py` — `POST /api/codes/check`.
- `backend/migrations/versions/c1d2e3f4a5b6_four_doors.py` — the one migration.
- `scripts/neoori-purge.sh` — the cron wrapper.
- Tests: `test_four_doors_migration.py`, `test_analysis_inputs.py`,
  `test_doors.py`, `test_code_doors.py`, `test_analysis_access_tokens.py`,
  `test_submit_doors.py`, `test_held_drafts.py`, `test_checkout_owner.py`,
  `test_counselor_analyses.py`, `test_admin_promo_codes.py`,
  `test_counselor_mails.py`, `test_purge.py`.

**Backend — modified**
- `routes/analyses.py` (submit, drafts, held/claim/by-token, access, unlock),
  `routes/auth.py` (register mark, verify attach, reset unmark),
  `services/sign_in.py` (enter unmark), `services/code_service.py`,
  `services/unlock_service.py`, `routes/payments.py`, `routes/upload.py`,
  `routes/voyage.py` (unlock uses the per-kind resolver),
  `routes/counselor_space.py`, `routes/admin.py`, `models/analysis.py`,
  `models/code_redemption.py`, `models/counselor_note.py`,
  `models/profile.py` (`CONSENT_VERSION`), `models/__init__.py`,
  `services/section_registry.py`, `services/anthropic_service.py`,
  `services/email_service.py`, `app/__init__.py` (reaper, blueprints, CLI),
  `config.py`, `utils/tokens.py`.
- **Deleted:** `routes/counselor.py`.
- Infra: `nginx/templates-http/default.conf.template`,
  `nginx/templates-https/default.conf.template`, `nginx/dev.conf`,
  `backend/entrypoint.sh`, `.env.example` (and `backend/.env.example` if
  present).

**Frontend — new**
- `components/analyse/DoorsPanel.tsx` — the four doors.
- `components/analyse/RunProgress.tsx` — the waiting screen, extracted from
  `en-cours` so `/rapport` reuses it.
- `components/report/ReportDocument.tsx` — the A4 report, extracted from the
  owner's report page so `/rapport` and the counselor page reuse it.
- `lib/held.ts` — the client calls for held drafts, claim, hold, by-token.
- `app/analyse/envoyee/page.tsx`, `app/rapport/page.tsx`,
  `app/rapport/layout.tsx` (metadata), `app/conseiller/analyses/[id]/page.tsx`,
  `components/admin/PromoCodesPanel.tsx`.

**Frontend — modified**
- `proxy.ts`, `lib/api.ts`, `lib/counselor.ts`, `types/index.ts`,
  `app/analyse/nouveau/page.tsx`, `app/analyse/en-cours/[id]/page.tsx`,
  `app/analyse/[id]/rapport/page.tsx`, `app/analyse/[id]/debloquer/page.tsx`,
  `app/espace/page.tsx`, `app/conseiller/page.tsx`, `app/c/[token]/page.tsx`,
  `app/admin/conseillers/page.tsx`, `components/report/ReportSection.tsx`,
  `components/report/PriceProbe.tsx`, `app/page.tsx`,
  `app/(legal)/cgv/page.tsx`, `app/(legal)/confidentialite/page.tsx`.

**Docs:** `CLAUDE.md`, `DOCKER.md`, `TEST-PLAN.md`,
`docs/superpowers/specs/2026-09-24-conseiller-accounts-design.md` (dated note).

---
## Task 1: Schema — the migration, the models, `run_log`

Everything the later tasks store. No behaviour changes yet.

**Files:**
- Create: `backend/migrations/versions/c1d2e3f4a5b6_four_doors.py`
- Create: `backend/app/models/run_log.py`
- Modify: `backend/app/models/analysis.py` (columns after `stripe_session_id`)
- Modify: `backend/app/models/code_redemption.py` (`slot`, `__table_args__`)
- Modify: `backend/app/models/counselor_note.py` (`__table_args__`)
- Modify: `backend/app/__init__.py` (model import list in `create_app`)
- Create: `backend/tests/helpers_doors.py`
- Test: `backend/tests/test_four_doors_migration.py`

**Interfaces:**
- Produces: `Analysis.door`, `.access_token_hash`, `.counselor_id`,
  `.pending_user_id`, `.consent_at`, `.consent_version`, `.started_at`;
  `CodeRedemption.slot`; `RunLog(door, user_id, created_at)`; migration module
  functions `mark_legacy(conn) -> int`, `backfill_slots(conn) -> int`,
  `dedupe_user_redemptions(conn, table="code_redemptions") -> int`;
  test helpers `user()`, `bearer()`, `expired_bearer()`, `counselor()`,
  `code()`, `P1_INPUTS`.

- [ ] **Step 1: Write the shared test helpers**

`backend/tests/helpers_doors.py`:

```python
"""Factories the four-doors tests share (four-doors spec)."""
from datetime import datetime, timedelta

from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.counselor_code import CounselorCode
from app.models.counselor_profile import CounselorProfile
from app.models.user import User

# Parcours 1 inputs create_analysis accepts: chemin A (the default) needs a
# target of at least 50 characters.
P1_INPUTS = {
    "cv_text": "c" * 300,
    "cible_visee": "Chauffeur livreur PL dans une entreprise de transport régional",
}


def user(email="marie@test.fr", role="candidate", verified=True):
    u = User(
        email=email, password_hash="x", role=role,
        email_verified_at=datetime.utcnow() if verified else None,
    )
    db.session.add(u)
    db.session.commit()
    return u


def bearer(u):
    token = create_access_token(identity=str(u.id), additional_claims={"role": u.role})
    return {"Authorization": f"Bearer {token}"}


def expired_bearer(u):
    """A token that lapsed: the access cookie outlives the JWT inside it."""
    token = create_access_token(
        identity=str(u.id), additional_claims={"role": u.role},
        expires_delta=timedelta(seconds=-30),
    )
    return {"Authorization": f"Bearer {token}"}


def counselor(email="conseil@test.fr", status="approved"):
    """A conseiller account. role follows status, as admin._decide keeps it."""
    u = user(email, role="counselor" if status == "approved" else "candidate")
    db.session.add(CounselorProfile(
        user_id=u.id, structure="s", fonction="f", telephone="t", status=status,
    ))
    db.session.commit()
    return u


def code(owner=None, *, max_uses=None, label="Atelier mardi", value="ABCD1234", expires_at=None):
    """owner=None is an admin-minted code — a promo code (spec decision 17)."""
    c = CounselorCode(
        label=label, owner_id=owner.id if owner else None,
        max_uses=max_uses, code=value, expires_at=expires_at,
    )
    db.session.add(c)
    db.session.commit()
    return c
```

- [ ] **Step 2: Write the failing migration tests**

`backend/tests/test_four_doors_migration.py`:

```python
"""Migration c1d2e3f4a5b6's data steps, loaded straight from its file and run
on the test database's own connection — there is no Alembic in the test run
(same pattern as test_migration_erase_billets.py)."""
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

from app.extensions import db
from app.models.analysis import Analysis
from app.models.code_redemption import CodeRedemption
from tests.helpers_doors import code, user

MIGRATION = (
    Path(__file__).resolve().parents[1] / "migrations" / "versions"
    / "c1d2e3f4a5b6_four_doors.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("four_doors", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ownerless_rows_are_marked_legacy_and_owned_rows_are_not(app):
    owner = user("o@test.fr")
    ownerless = Analysis(user_id=None, status="success", inputs={})
    owned = Analysis(user_id=owner.id, status="success", inputs={})
    db.session.add_all([ownerless, owned])
    db.session.commit()

    marked = _migration().mark_legacy(db.session.connection())
    db.session.commit()
    db.session.expire_all()

    assert marked == 1
    assert db.session.get(Analysis, ownerless.id).door == "legacy"
    assert db.session.get(Analysis, owned.id).door is None


def test_mark_legacy_twice_marks_nothing_new(app):
    db.session.add(Analysis(user_id=None, status="success", inputs={}))
    db.session.commit()
    m = _migration()
    m.mark_legacy(db.session.connection())
    assert m.mark_legacy(db.session.connection()) == 0


def test_slots_are_numbered_per_code_and_kind_in_redemption_order(app):
    limited = code(max_uses=5, value="LIMIT001")
    unlimited = code(value="FREE0001")
    t0 = datetime(2026, 9, 1)
    rows = [
        CodeRedemption(code_id=limited.id, target_type="voyage", target_id="v2",
                       redeemed_at=t0 + timedelta(days=2)),
        CodeRedemption(code_id=limited.id, target_type="voyage", target_id="v1", redeemed_at=t0),
        CodeRedemption(code_id=limited.id, target_type="analysis", target_id="a1",
                       redeemed_at=t0 + timedelta(days=1)),
        CodeRedemption(code_id=unlimited.id, target_type="voyage", target_id="v3", redeemed_at=t0),
    ]
    db.session.add_all(rows)
    db.session.commit()

    _migration().backfill_slots(db.session.connection())
    db.session.commit()
    db.session.expire_all()

    slot = {r.target_id: db.session.get(CodeRedemption, r.id).slot for r in rows}
    assert slot == {"v1": 1, "v2": 2, "a1": 1, "v3": None}


def test_backfill_continues_after_slots_already_written(app):
    limited = code(max_uses=5, value="LIMIT002")
    t0 = datetime(2026, 9, 1)
    first = CodeRedemption(code_id=limited.id, target_type="voyage", target_id="v1",
                           redeemed_at=t0, slot=1)
    second = CodeRedemption(code_id=limited.id, target_type="voyage", target_id="v2",
                            redeemed_at=t0 + timedelta(days=1))
    db.session.add_all([first, second])
    db.session.commit()

    _migration().backfill_slots(db.session.connection())
    db.session.commit()
    db.session.expire_all()
    assert db.session.get(CodeRedemption, second.id).slot == 2


def test_duplicate_user_redemptions_keep_the_first_named(app):
    """A scratch table without the new unique key: the model already carries
    it, so the duplicates this step exists for cannot be inserted there."""
    conn = db.session.connection()
    conn.execute(db.text(
        "CREATE TABLE cr_scratch (id VARCHAR(36) PRIMARY KEY, code_id VARCHAR(36), "
        "user_id VARCHAR(36), target_type VARCHAR(16), target_id VARCHAR(36), "
        "redeemed_at DATETIME)"
    ))
    conn.execute(db.text(
        "INSERT INTO cr_scratch VALUES "
        "('r1','c1','u1','analysis','a1','2026-09-01'),"
        "('r2','c1','u1','analysis','a2','2026-09-02'),"
        "('r3','c1','u1','voyage','v1','2026-09-03')"
    ))
    nulled = _migration().dedupe_user_redemptions(conn, table="cr_scratch")
    rows = dict(conn.execute(db.text("SELECT id, user_id FROM cr_scratch")).fetchall())
    assert nulled == 1
    assert rows == {"r1": "u1", "r2": None, "r3": "u1"}
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd backend && python -m pytest tests/test_four_doors_migration.py -q`
Expected: FAIL — the migration file does not exist (`FileNotFoundError`), and
`code(...)` fails on the missing `slot` column once the file exists.

- [ ] **Step 4: Add `RunLog`**

`backend/app/models/run_log.py`:

```python
from uuid import uuid4
from datetime import datetime

from ..extensions import db


class RunLog(db.Model):
    """One row per submitted run, for the daily caps (four-doors spec,
    decision 40).

    Append-only, on purpose: the caps used to be counted from `analyses`, and a
    candidate or a token holder may delete their report — so run, read,
    delete, run again would never reach the cap. Nothing deletes from here but
    the purge, after two days.
    """

    __tablename__ = "run_log"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    door = db.Column(db.String(16), nullable=False)
    # No foreign key: this is a count, not a link, and it never needs the
    # account to still exist.
    user_id = db.Column(db.String(36), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.Index("ix_run_log_door_created_at", "door", "created_at"),
        db.Index("ix_run_log_user_id_created_at", "user_id", "created_at"),
    )
```

In `backend/app/__init__.py`, add `run_log` to the model import list in
`create_app()`:

```python
    from .models import (  # noqa: F401
        user, analysis, prompt_version, counselor_note, counselor_code,
        counselor_profile, code_redemption, profile, price_feedback, voyage,
        auth_identity, login_link, run_log,
    )
```

- [ ] **Step 5: Add the columns to the models**

In `backend/app/models/analysis.py`, after `stripe_session_id`:

```python
    # Which of the four doors this run came through (four-doors spec): account
    # / promo / advisor / anonymous, set at submit. 'legacy' marks the ownerless
    # rows written before accounts were required (decision 44). NULL for drafts
    # and for owned rows that predate the doors.
    door = db.Column(db.String(16), nullable=True)
    # SHA-256 of the key to a no-login report or a held draft (decisions 30,
    # 34). The key itself is never stored.
    access_token_hash = db.Column(db.CHAR(64), unique=True, nullable=True)
    # The counselor an advisor-door report belongs to — and the only person who
    # may read it (ruling 2). SET NULL keeps the row closed: `door` still says
    # advisor, and _may_access refuses on either.
    counselor_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The account a held row waits for: set by password signup, attached at
    # verify-email, dropped if the address is proven any other way first
    # (decisions 34, 36).
    pending_user_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The CGV + privacy box at the advisor and anonymous doors (decisions 25,
    # 31), which have no signup consent to rely on.
    consent_at = db.Column(db.DateTime, nullable=True)
    consent_version = db.Column(db.String(16), nullable=True)
    # When the row last went 'running' — the stale-run reaper's clock
    # (decision 47). created_at is wrong for a relaunch or an unlock.
    started_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (db.Index("ix_analyses_door_created_at", "door", "created_at"),)
```

In `backend/app/models/code_redemption.py`, add the column after
`target_id` and replace `__table_args__`:

```python
    # This redemption's place in the code's per-kind ceiling, 1..max_uses, or
    # NULL for an unlimited code. The unique key below makes the ceiling the
    # database's to enforce (four-doors spec, decision 23): two requests that
    # both read "0 used" both try slot 1, and only one insert succeeds.
    slot = db.Column(db.Integer, nullable=True)
```

```python
    __table_args__ = (
        # A retried unlock must not double-count.
        db.UniqueConstraint(
            "code_id", "target_type", "target_id", name="uq_code_redemptions_target"
        ),
        db.UniqueConstraint(
            "code_id", "target_type", "slot", name="uq_code_redemptions_slot"
        ),
        # One promo use per account, atomically. Advisor-door redemptions carry
        # user_id NULL, and NULLs never collide in a unique key.
        db.UniqueConstraint(
            "code_id", "target_type", "user_id", name="uq_code_redemptions_user"
        ),
    )
```

Also add `"slot": self.slot,` to `CodeRedemption.to_dict()`.

In `backend/app/models/counselor_note.py`, inside the class:

```python
    # One note per counselor per analysis: the counselor page upserts it.
    __table_args__ = (
        db.UniqueConstraint("analysis_id", "counselor_id", name="uq_counselor_notes_analysis_counselor"),
    )
```

- [ ] **Step 6: Write the migration**

`backend/migrations/versions/c1d2e3f4a5b6_four_doors.py` — set
`down_revision` to the head found in « Before you start », step 3:

```python
"""Four doors: who an analysis is for, and the limits that hold it

analyses gains door, access_token_hash, counselor_id, pending_user_id,
consent_at, consent_version and started_at; ownerless rows written before this
revision are marked door='legacy'. code_redemptions gains slot and two unique
keys; counselor_notes one unique key; run_log is new.

Rolling back past this revision is only safe after
`flask purge-expired --before-rollback --apply` (DOCKER.md, « Rollback »):
without it, advisor-door rows become plain ownerless rows, which the previous
image serves to anyone holding the id.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op


revision = 'c1d2e3f4a5b6'
down_revision = 'b0c1d2e3f4a5'
branch_labels = None
depends_on = None


def _inspect(bind):
    return sa.inspect(bind)


def _tables(bind) -> set[str]:
    return set(_inspect(bind).get_table_names())


def _columns(bind, table: str) -> set[str]:
    return {c["name"] for c in _inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    return {i["name"] for i in _inspect(bind).get_indexes(table)}


def _uniques(bind, table: str) -> set[str]:
    return {u["name"] for u in _inspect(bind).get_unique_constraints(table)}


def _foreign_keys(bind, table: str) -> set[str]:
    return {fk["name"] for fk in _inspect(bind).get_foreign_keys(table)}


def _analysis_columns():
    return [
        sa.Column("door", sa.String(16), nullable=True),
        sa.Column("access_token_hash", sa.CHAR(64), nullable=True),
        sa.Column("counselor_id", sa.String(36), nullable=True),
        sa.Column("pending_user_id", sa.String(36), nullable=True),
        sa.Column("consent_at", sa.DateTime(), nullable=True),
        sa.Column("consent_version", sa.String(16), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
    ]


def mark_legacy(conn) -> int:
    """Ownerless rows that exist now keep their by-id access (spec decision
    44). Marking them is what makes that explicit: from here on, a row with no
    owner, no token and no counselor is closed, not silently readable."""
    result = conn.execute(sa.text(
        "UPDATE analyses SET door = 'legacy' WHERE user_id IS NULL AND door IS NULL"
    ))
    return result.rowcount


def dedupe_user_redemptions(conn, table: str = "code_redemptions") -> int:
    """Before the (code_id, target_type, user_id) unique key: keep the person
    on their earliest redemption of a code per kind, and null them on the
    later ones. The rows stay, so a spent use stays spent. Prod had no such
    duplicate on 2026-10-08; a dev database may."""
    rows = conn.execute(sa.text(
        f"SELECT id, code_id, target_type, user_id FROM {table} "
        "WHERE user_id IS NOT NULL ORDER BY code_id, target_type, user_id, redeemed_at, id"
    )).fetchall()
    seen, nulled = set(), 0
    for rid, code_id, kind, user_id in rows:
        key = (code_id, kind, user_id)
        if key in seen:
            conn.execute(sa.text(f"UPDATE {table} SET user_id = NULL WHERE id = :id"), {"id": rid})
            nulled += 1
        seen.add(key)
    return nulled


def backfill_slots(conn) -> int:
    """Number the existing redemptions of limited codes 1..n per (code, kind),
    in redemption order, continuing after any slot already written — so a
    crash halfway resumes cleanly and the unique slot key holds from the first
    new redemption."""
    rows = conn.execute(sa.text(
        "SELECT r.id, r.code_id, r.target_type, r.slot FROM code_redemptions r "
        "JOIN counselor_codes c ON c.id = r.code_id "
        "WHERE c.max_uses IS NOT NULL "
        "ORDER BY r.code_id, r.target_type, r.redeemed_at, r.id"
    )).fetchall()
    top: dict[tuple[str, str], int] = {}
    for _rid, code_id, kind, slot in rows:
        if slot is not None:
            top[(code_id, kind)] = max(top.get((code_id, kind), 0), slot)
    filled = 0
    for rid, code_id, kind, slot in rows:
        if slot is None:
            top[(code_id, kind)] = top.get((code_id, kind), 0) + 1
            conn.execute(
                sa.text("UPDATE code_redemptions SET slot = :s WHERE id = :id"),
                {"s": top[(code_id, kind)], "id": rid},
            )
            filled += 1
    return filled


def upgrade():
    # Idempotent per this repo's convention (b0c1d2e3f4a5): entrypoint.sh runs
    # `db upgrade` at container start, and MySQL DDL is not transactional.
    bind = op.get_bind()

    existing = _columns(bind, "analyses")
    for column in _analysis_columns():
        if column.name not in existing:
            op.add_column("analyses", column)

    fks = _foreign_keys(bind, "analyses")
    for name, column in (
        ("fk_analyses_counselor_id_users", "counselor_id"),
        ("fk_analyses_pending_user_id_users", "pending_user_id"),
    ):
        if name not in fks:
            op.create_foreign_key(name, "analyses", "users", [column], ["id"], ondelete="SET NULL")

    indexes = _indexes(bind, "analyses")
    if "ix_analyses_door_created_at" not in indexes:
        op.create_index("ix_analyses_door_created_at", "analyses", ["door", "created_at"])
    if "ix_analyses_counselor_id" not in indexes:
        op.create_index("ix_analyses_counselor_id", "analyses", ["counselor_id"])
    if "ix_analyses_pending_user_id" not in indexes:
        op.create_index("ix_analyses_pending_user_id", "analyses", ["pending_user_id"])
    if "uq_analyses_access_token_hash" not in indexes | _uniques(bind, "analyses"):
        op.create_index(
            "uq_analyses_access_token_hash", "analyses", ["access_token_hash"], unique=True
        )

    mark_legacy(bind)

    if "slot" not in _columns(bind, "code_redemptions"):
        op.add_column("code_redemptions", sa.Column("slot", sa.Integer(), nullable=True))
    dedupe_user_redemptions(bind)
    backfill_slots(bind)
    uniques = _uniques(bind, "code_redemptions") | _indexes(bind, "code_redemptions")
    if "uq_code_redemptions_slot" not in uniques:
        op.create_unique_constraint(
            "uq_code_redemptions_slot", "code_redemptions", ["code_id", "target_type", "slot"]
        )
    if "uq_code_redemptions_user" not in uniques:
        op.create_unique_constraint(
            "uq_code_redemptions_user", "code_redemptions", ["code_id", "target_type", "user_id"]
        )

    if "uq_counselor_notes_analysis_counselor" not in (
        _uniques(bind, "counselor_notes") | _indexes(bind, "counselor_notes")
    ):
        op.create_unique_constraint(
            "uq_counselor_notes_analysis_counselor", "counselor_notes",
            ["analysis_id", "counselor_id"],
        )

    if "run_log" not in _tables(bind):
        op.create_table(
            "run_log",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("door", sa.String(16), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    run_log_indexes = _indexes(bind, "run_log")
    if "ix_run_log_door_created_at" not in run_log_indexes:
        op.create_index("ix_run_log_door_created_at", "run_log", ["door", "created_at"])
    if "ix_run_log_user_id_created_at" not in run_log_indexes:
        op.create_index("ix_run_log_user_id_created_at", "run_log", ["user_id", "created_at"])


def downgrade():
    bind = op.get_bind()
    if "run_log" in _tables(bind):
        op.drop_table("run_log")

    if "uq_counselor_notes_analysis_counselor" in (
        _uniques(bind, "counselor_notes") | _indexes(bind, "counselor_notes")
    ):
        op.drop_constraint("uq_counselor_notes_analysis_counselor", "counselor_notes", type_="unique")

    uniques = _uniques(bind, "code_redemptions") | _indexes(bind, "code_redemptions")
    for name in ("uq_code_redemptions_user", "uq_code_redemptions_slot"):
        if name in uniques:
            op.drop_constraint(name, "code_redemptions", type_="unique")
    if "slot" in _columns(bind, "code_redemptions"):
        op.drop_column("code_redemptions", "slot")

    fks = _foreign_keys(bind, "analyses")
    for name in ("fk_analyses_pending_user_id_users", "fk_analyses_counselor_id_users"):
        if name in fks:
            op.drop_constraint(name, "analyses", type_="foreignkey")
    indexes = _indexes(bind, "analyses")
    for name in ("uq_analyses_access_token_hash", "ix_analyses_pending_user_id",
                 "ix_analyses_counselor_id", "ix_analyses_door_created_at"):
        if name in indexes:
            op.drop_index(name, table_name="analyses")
    existing = _columns(bind, "analyses")
    for column in reversed(_analysis_columns()):
        if column.name in existing:
            op.drop_column("analyses", column.name)
```

- [ ] **Step 7: Run the tests**

Run: `cd backend && python -m pytest tests/test_four_doors_migration.py tests/test_migration_chain.py -q`
Expected: PASS (7 tests).

- [ ] **Step 8: Apply the migration to the local MySQL, both ways**

```bash
docker compose up -d
docker compose exec backend flask db upgrade
docker compose exec backend flask db downgrade b0c1d2e3f4a5   # the head you found
docker compose exec backend flask db upgrade
```
Expected: each command ends without error; the second `upgrade` re-adds what the
downgrade removed. If the dev database holds P2/P3 rows, that is fine — the
migration does not look at `_path`.

- [ ] **Step 9: Full suite, then commit**

Run: `cd backend && python -m pytest -q` — expected: baseline + 7, all green.

```bash
git add backend/migrations/versions/c1d2e3f4a5b6_four_doors.py backend/app/models \
        backend/app/__init__.py backend/tests/helpers_doors.py backend/tests/test_four_doors_migration.py
git commit -m "feat(doors): schema for the four doors — door, tokens, counselor, run log

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 2: The client input allow-list and the settings

**Files:**
- Create: `backend/app/services/analysis_inputs.py`
- Modify: `backend/app/config.py` (class `Config`)
- Test: `backend/tests/test_analysis_inputs.py`

**Interfaces:**
- Produces: `analysis_inputs.clean(raw: dict) -> tuple[dict, list[str]]`,
  `analysis_inputs.CLIENT_KEYS`; config keys `CV_TEXT_MAX`, `CIBLE_MAX`,
  `ANONYMOUS_RUNS_PER_DAY`, `FREE_RUNS_PER_ACCOUNT_PER_DAY`,
  `ANONYMOUS_RETENTION_DAYS`, `ADVISOR_RETENTION_DAYS`,
  `HELD_DRAFT_RETENTION_HOURS`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_analysis_inputs.py`:

```python
"""What a client may put in an analysis's inputs (four-doors spec, decision 37)."""
from app.services import analysis_inputs


def test_keeps_the_three_client_keys_and_drops_every_other(app):
    raw = {
        "cv_text": "c" * 300, "cible_visee": "t" * 60, "_chemin": "B",
        "_conditions": ["injected"], "_oeth": True, "_voyage": ["x"], "_voyage_id": "v",
        "_tier": "premium", "_path": "2", "notes_specifiques": "n", "prenom": "Zoé",
    }
    inputs, errors = analysis_inputs.clean(raw)
    assert errors == []
    assert set(inputs) == {"cv_text", "cible_visee", "_chemin"}


def test_a_non_string_value_becomes_empty(app):
    inputs, _ = analysis_inputs.clean({"cv_text": {"a": 1}, "cible_visee": ["x"]})
    assert inputs == {"cv_text": "", "cible_visee": ""}


def test_an_empty_draft_stays_empty(app):
    assert analysis_inputs.clean({}) == ({}, [])


def test_a_long_real_cv_passes_and_one_past_the_cap_fails(app):
    # Review focus 3: measured after trimming, so padding never counts.
    ok, errors = analysis_inputs.clean({"cv_text": "  " + "c" * 39_999 + "\n\n"})
    assert errors == [] and len(ok["cv_text"]) == 39_999

    _, errors = analysis_inputs.clean({"cv_text": "c" * 40_001})
    assert errors == ["CV trop long (40 000 caractères maximum)."]


def test_the_target_has_its_own_cap(app):
    _, errors = analysis_inputs.clean({"cible_visee": "t" * 10_001})
    assert errors == ["Cible visée trop longue (10 000 caractères maximum)."]


def test_the_caps_come_from_config(app):
    app.config["CV_TEXT_MAX"] = 500
    _, errors = analysis_inputs.clean({"cv_text": "c" * 501})
    assert errors == ["CV trop long (500 caractères maximum)."]
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_analysis_inputs.py -q`
Expected: FAIL — `ImportError: cannot import name 'analysis_inputs'`.

- [ ] **Step 3: Add the settings**

In `backend/app/config.py`, inside `class Config`, after `MAX_CONTENT_LENGTH`:

```python
    # Four-doors spec: the client input caps (decision 37), the daily caps on
    # free runs (decision 40), and how long ownerless rows live (decisions 12,
    # 29, 35). All overridable from /srv/neoori/.env.
    CV_TEXT_MAX = int(os.environ.get("CV_TEXT_MAX", "40000"))
    CIBLE_MAX = int(os.environ.get("CIBLE_MAX", "10000"))
    ANONYMOUS_RUNS_PER_DAY = int(os.environ.get("ANONYMOUS_RUNS_PER_DAY", "200"))
    FREE_RUNS_PER_ACCOUNT_PER_DAY = int(os.environ.get("FREE_RUNS_PER_ACCOUNT_PER_DAY", "5"))
    ANONYMOUS_RETENTION_DAYS = int(os.environ.get("ANONYMOUS_RETENTION_DAYS", "30"))
    ADVISOR_RETENTION_DAYS = int(os.environ.get("ADVISOR_RETENTION_DAYS", "365"))
    HELD_DRAFT_RETENTION_HOURS = int(os.environ.get("HELD_DRAFT_RETENTION_HOURS", "48"))
```

- [ ] **Step 4: Write `analysis_inputs`**

`backend/app/services/analysis_inputs.py`:

```python
"""What a client may put in an analysis's inputs (four-doors spec, decision 37).

Everything else in a stored `inputs` object is the server's: the parcours
stamp, the tier, the profile and voyage folds. Copying the client's object as
posted let any key through — a `_conditions` line straight into the prompt, or
ten megabytes of anything into a row nobody owns. This keeps three keys, as
trimmed text, inside their caps.
"""
from flask import current_app

from ..utils.request_body import text_field

CLIENT_KEYS = ("cv_text", "cible_visee", "_chemin")


def _thousands(n: int) -> str:
    """40000 -> "40 000", the way the French messages print it."""
    return f"{n:,}".replace(",", " ")


def clean(raw: dict) -> tuple[dict, list[str]]:
    """The allowed keys as trimmed strings, and the French errors for any
    over its cap. A key the client did not send stays absent, so an empty
    draft stays {}."""
    inputs = {key: text_field(raw, key) for key in CLIENT_KEYS if key in raw}

    errors = []
    cv_max = current_app.config["CV_TEXT_MAX"]
    if len(inputs.get("cv_text", "")) > cv_max:
        errors.append(f"CV trop long ({_thousands(cv_max)} caractères maximum).")
    cible_max = current_app.config["CIBLE_MAX"]
    if len(inputs.get("cible_visee", "")) > cible_max:
        errors.append(f"Cible visée trop longue ({_thousands(cible_max)} caractères maximum).")
    return inputs, errors
```

- [ ] **Step 5: Run the tests, then commit**

Run: `cd backend && python -m pytest tests/test_analysis_inputs.py -q` — expected: 6 passed.

```bash
git add backend/app/services/analysis_inputs.py backend/app/config.py backend/tests/test_analysis_inputs.py
git commit -m "feat(doors): client inputs are an allow-list with length caps

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 3: Codes — kinds, per-kind counting, the database ceiling, `/debloquer`

**Files:**
- Modify: `backend/app/services/code_service.py`
- Modify: `backend/app/services/unlock_service.py` (extract `refusal()`)
- Modify: `backend/app/routes/analyses.py` (`unlock_with_code`)
- Modify: `backend/app/routes/voyage.py` (`unlock_voyage`)
- Test: `backend/tests/test_code_doors.py`
- Modify tests: `test_code_service.py`, `test_code_redemption_routes.py`,
  `test_unlock.py`, `test_voyage_routes.py` (wherever they call `record()`,
  `resolve(code_str)` with one argument, or redeem a code on an ownerless row
  without a session)

**Interfaces:**
- Consumes: `CodeRedemption.slot` (Task 1); test helpers (Task 1).
- Produces:
  - `code_service.PROMO = "promo"`, `code_service.CONSEILLER = "conseiller"`,
    `code_service.kind(code) -> str`;
  - `code_service.redemption_count(code_id, target_type=None) -> int`;
  - `code_service.resolve(code_str, target_type) -> (CounselorCode | None, str | None)`;
  - `code_service.DoorRefusal(message, status, door=None)`;
  - `code_service.resolve_for_door(raw, door, user_id) -> (CounselorCode | None, DoorRefusal | None)`;
  - `code_service.redeem(code, *, user_id, target_type, target_id) -> str | None` (commits);
  - `code_service.ALREADY_USED`, `code_service.NOT_FOR_UNLOCK`;
  - `unlock_service.refusal(analysis) -> str | None`.
  - `record()` is removed.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_code_doors.py`:

```python
"""Codes under the four doors (four-doors spec, decisions 17-23)."""
from datetime import datetime
from unittest.mock import patch

from app.extensions import db
from app.models.analysis import Analysis
from app.models.code_redemption import CodeRedemption
from app.models.voyage import Voyage
from app.services import code_service
from tests.helpers_doors import bearer, code, counselor, user


def test_kind_is_derived_from_the_owner(app):
    assert code_service.kind(code(value="PROMO001")) == "promo"
    assert code_service.kind(code(counselor(), value="CONS0001")) == "conseiller"


def test_a_single_use_conseiller_code_opens_one_analysis_and_one_voyage(app):
    c = code(counselor(), max_uses=1)
    found, refusal = code_service.resolve("ABCD1234", "analysis")
    assert refusal is None
    assert code_service.redeem(found, user_id=None, target_type="analysis", target_id="a1") is None

    assert code_service.resolve("ABCD1234", "analysis") == (None, code_service.EXHAUSTED)
    found, refusal = code_service.resolve("ABCD1234", "voyage")
    assert refusal is None and found.id == c.id


def test_a_code_whose_counselor_is_not_approved_is_invalid_everywhere(app):
    for status, value in (("pending", "PEND0001"), ("rejected", "REJE0001"), ("revoked", "REVO0001")):
        code(counselor(f"{status}@test.fr", status=status), value=value)
        for kind in ("analysis", "voyage"):
            assert code_service.resolve(value, kind) == (None, code_service.INVALID)


def test_a_promo_code_has_no_owner_to_approve(app):
    code(value="PROMO002")
    found, refusal = code_service.resolve("PROMO002", "analysis")
    assert refusal is None and found is not None


def test_the_wrong_door_is_answered_with_the_right_one(app):
    code(counselor(), value="CONS0002")
    code(value="PROMO003")
    _, refusal = code_service.resolve_for_door("CONS0002", "promo", "u1")
    assert (refusal.status, refusal.door) == (409, "advisor")
    _, refusal = code_service.resolve_for_door("PROMO003", "advisor", None)
    assert (refusal.status, refusal.door) == (409, "promo")


def test_codes_are_accepted_as_people_type_them(app):
    # Review focus 2.
    code(counselor(), value="ABCD1234")
    for typed in ("abcd-1234", "ABCD 1234", " abcd1234 "):
        found, refusal = code_service.resolve_for_door(typed, "advisor", None)
        assert refusal is None and found is not None, typed


def test_a_promo_code_is_once_per_account(app):
    c = code(value="PROMO004", max_uses=10)
    u = user()
    assert code_service.redeem(c, user_id=u.id, target_type="analysis", target_id="a1") is None
    _, refusal = code_service.resolve_for_door("PROMO004", "promo", u.id)
    assert refusal.message == code_service.ALREADY_USED
    # And the database says the same, should the check above ever be skipped.
    assert code_service.redeem(c, user_id=u.id, target_type="analysis", target_id="a2") \
        == code_service.ALREADY_USED


def test_two_requests_for_the_last_place_give_one_redemption(app):
    """The first count is stale (MySQL REPEATABLE READ): the slot key refuses
    the second insert, the retry recounts, and the answer is EXHAUSTED."""
    c = code(counselor(), max_uses=1)
    db.session.add(CodeRedemption(code_id=c.id, target_type="analysis", target_id="a0", slot=1))
    db.session.commit()

    real = code_service.redemption_count
    calls = {"n": 0}

    def stale_once(code_id, target_type=None):
        calls["n"] += 1
        return 0 if calls["n"] == 1 else real(code_id, target_type)

    with patch.object(code_service, "redemption_count", side_effect=stale_once):
        assert code_service.redeem(c, user_id=None, target_type="analysis", target_id="a1") \
            == code_service.EXHAUSTED
    assert CodeRedemption.query.filter_by(code_id=c.id).count() == 1


@patch("app.services.unlock_service.start_analysis")
def test_debloquer_takes_a_promo_code_on_the_owners_free_report(_start, client, app):
    owner = user()
    analysis = Analysis(user_id=owner.id, status="success", door="account",
                        inputs={"_path": "1", "_tier": "free"}, output={"1": {}})
    db.session.add(analysis)
    db.session.commit()
    code(value="PROMO005")

    res = client.post(f"/api/analyses/{analysis.id}/unlock", json={"code": "promo-005"},
                      headers=bearer(owner))
    assert res.status_code == 200, res.data
    assert db.session.get(Analysis, analysis.id).unlock_method == "code"


def test_debloquer_refuses_a_conseiller_code(client, app):
    owner = user()
    analysis = Analysis(user_id=owner.id, status="success", door="account",
                        inputs={"_path": "1", "_tier": "free"}, output={"1": {}})
    db.session.add(analysis)
    db.session.commit()
    code(counselor(), value="CONS0003")

    res = client.post(f"/api/analyses/{analysis.id}/unlock", json={"code": "CONS0003"},
                      headers=bearer(owner))
    assert res.status_code == 409
    assert res.get_json()["error"] == code_service.NOT_FOR_UNLOCK
    assert CodeRedemption.query.count() == 0


def test_debloquer_needs_the_owner(client, app):
    owner, other = user(), user("other@test.fr")
    analysis = Analysis(user_id=owner.id, status="success", inputs={"_path": "1"}, output={"1": {}})
    db.session.add(analysis)
    db.session.commit()
    code(value="PROMO006")
    assert client.post(f"/api/analyses/{analysis.id}/unlock", json={"code": "PROMO006"}).status_code == 401
    assert client.post(f"/api/analyses/{analysis.id}/unlock", json={"code": "PROMO006"},
                       headers=bearer(other)).status_code == 403


def test_the_voyage_refuses_a_revoked_counselors_code(client, app):
    candidate = user()
    db.session.add(Voyage(user_id=candidate.id, consent_at=datetime.utcnow(), age_attested=True))
    db.session.commit()
    code(counselor(status="revoked"), value="REVO0002")
    res = client.post("/api/voyage/unlock", json={"code": "REVO0002"}, headers=bearer(candidate))
    assert res.status_code == 400
    assert res.get_json()["error"] == code_service.INVALID


def test_refusal_needs_a_finished_free_report(app):
    from app.services.unlock_service import refusal
    base = dict(inputs={"_path": "1"}, user_id=None)
    assert refusal(Analysis(status="error", **base)) is not None
    assert refusal(Analysis(status="running", **base)) is not None
    assert refusal(Analysis(status="success", output={"5": {}}, **base)) is not None
    assert refusal(Analysis(status="success", unlock_method="code", **base)) is not None
    assert refusal(Analysis(status="success", output={"1": {}}, **base)) is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_code_doors.py -q`
Expected: FAIL — `AttributeError: module 'app.services.code_service' has no attribute 'kind'` (and others).

- [ ] **Step 3: Rewrite `code_service`**

Replace `backend/app/services/code_service.py` with (keep `normalize()` as it
is):

```python
"""One redemption path for every code (four-doors spec, decisions 17-23).

A code's kind is derived: no owner means admin-minted, a promo code; an owner
means a conseiller code. Uses are counted per kind — a single-use conseiller
code opens one analysis AND one voyage (ruling 10) — and the ceiling is the
database's to enforce, not a count's: see redeem().
"""
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.code_redemption import CodeRedemption
from ..models.counselor_code import CounselorCode
from ..models.counselor_profile import CounselorProfile

INVALID = "Code invalide ou désactivé."
EXPIRED = "Ce code a expiré."
EXHAUSTED = "Ce code a atteint sa limite d'utilisation."
ALREADY_USED = "Vous avez déjà utilisé ce code."
REQUIRED = "Code requis."
NOT_FOR_UNLOCK = (
    "Ce code est un code conseiller : avec lui, le rapport complet est envoyé à "
    "votre conseiller. Lancez une nouvelle analyse et choisissez « J'ai un code "
    "conseiller »."
)

PROMO = "promo"
CONSEILLER = "conseiller"

# The door (services/doors.py names) each kind of code belongs to, and what to
# say to someone who typed it at the other one.
DOOR_OF = {PROMO: "promo", CONSEILLER: "advisor"}
WRONG_DOOR = {
    PROMO: "Ce code est un code promo : choisissez « J'ai un code promo ».",
    CONSEILLER: "Ce code est un code conseiller : choisissez « J'ai un code conseiller ».",
}


@dataclass(frozen=True)
class DoorRefusal:
    message: str
    status: int
    # The door this code belongs to, when it was typed at the wrong one: the
    # panel switches to it (spec decision 21).
    door: str | None = None


def normalize(raw) -> str:
    """Accept "ABCD1234", "abcd 1234", "ABCD-1234"… — codes are 8 alnum chars.

    A non-string value yields "", so the route answers its own « Code requis. »
    instead of raising AttributeError on .strip() -> an unhandled 500.
    """
    return re.sub(r"[^A-Za-z0-9]", "", raw if isinstance(raw, str) else "").upper()


def kind(code: CounselorCode) -> str:
    return PROMO if code.owner_id is None else CONSEILLER


def redemption_count(code_id: str, target_type: str | None = None) -> int:
    query = CodeRedemption.query.filter_by(code_id=code_id)
    if target_type is not None:
        query = query.filter_by(target_type=target_type)
    return query.count()


def _owner_approved(code: CounselorCode) -> bool:
    """A conseiller code works only while its counselor is approved (spec
    decision 20). A promo code has no counselor to ask."""
    if code.owner_id is None:
        return True
    profile = CounselorProfile.query.filter_by(user_id=code.owner_id).first()
    return profile is not None and profile.status == "approved"


def _used_by(code_id: str, target_type: str, user_id: str) -> bool:
    return CodeRedemption.query.filter_by(
        code_id=code_id, target_type=target_type, user_id=user_id
    ).first() is not None


def resolve(code_str: str, target_type: str) -> tuple[CounselorCode | None, str | None]:
    """The code, or the French refusal to hand back verbatim.

    Counted per kind from code_redemptions, never off uses_count (a legacy
    increment that can drift). This count is advisory: it gives the early,
    friendly answer. The guarantee is redeem()'s slot key.
    """
    code = CounselorCode.query.filter_by(code=code_str).with_for_update().first()
    if code is None or not code.is_active or code.revoked_at is not None:
        return None, INVALID
    if not _owner_approved(code):
        return None, INVALID
    if code.expires_at is not None and code.expires_at <= datetime.utcnow():
        return None, EXPIRED
    if code.max_uses is not None and redemption_count(code.id, target_type) >= code.max_uses:
        return None, EXHAUSTED
    return code, None


def resolve_for_door(raw, door: str, user_id: str | None) -> tuple[CounselorCode | None, DoorRefusal | None]:
    """The code a door may spend, or why not — including « wrong door »."""
    code_str = normalize(raw)
    if not code_str:
        return None, DoorRefusal(REQUIRED, 400)
    code, refusal = resolve(code_str, "analysis")
    if refusal:
        return None, DoorRefusal(refusal, 400)
    code_kind = kind(code)
    if DOOR_OF[code_kind] != door:
        return None, DoorRefusal(WRONG_DOOR[code_kind], 409, DOOR_OF[code_kind])
    if code_kind == PROMO and user_id is not None and _used_by(code.id, "analysis", user_id):
        return None, DoorRefusal(ALREADY_USED, 409)
    return code, None


def redeem(code: CounselorCode, *, user_id: str | None, target_type: str, target_id: str) -> str | None:
    """Write the redemption and COMMIT it — before whatever it pays for starts.

    For a limited code the row takes `slot = used + 1`, and the unique key on
    (code_id, target_type, slot) refuses a second request that read the same
    count. That read can be stale: under MySQL's REPEATABLE READ the snapshot is
    fixed at the transaction's first read. On a violation the transaction is
    rolled back — the next one gets a fresh snapshot — and the count is read
    again once. Unlimited codes write slot NULL, which never collides.

    Returns None on success, or the French refusal: EXHAUSTED, or ALREADY_USED
    when this account already spent this code on this kind (the unique key on
    (code_id, target_type, user_id)). A row already recorded for this very
    target — a retried request — counts as success.
    """
    code_id, max_uses = code.id, code.max_uses
    for _attempt in range(2):
        used = redemption_count(code_id, target_type)
        if max_uses is not None and used >= max_uses:
            return EXHAUSTED
        db.session.add(CodeRedemption(
            code_id=code_id,
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            slot=used + 1 if max_uses is not None else None,
        ))
        # The legacy counter, kept for the admin screens that still read it.
        CounselorCode.query.filter_by(id=code_id).update(
            {"uses_count": CounselorCode.uses_count + 1}, synchronize_session=False
        )
        try:
            db.session.commit()
            return None
        except IntegrityError:
            db.session.rollback()
            if user_id is not None and _used_by(code_id, target_type, user_id):
                return ALREADY_USED
            if CodeRedemption.query.filter_by(
                code_id=code_id, target_type=target_type, target_id=target_id
            ).first() is not None:
                return None
    return EXHAUSTED
```

- [ ] **Step 4: Extract `unlock_service.refusal()`**

In `backend/app/services/unlock_service.py`, add above `unlock_analysis` and
call it from there in place of its inline checks:

```python
def refusal(analysis: Analysis) -> str | None:
    """Why this analysis cannot be unlocked, or None. The one rule checkout
    and unlock_analysis share (four-doors spec, decision 41), so a payment is
    never taken for an unlock that then refuses."""
    if analysis.status in ("queued", "running"):
        return "Une génération est déjà en cours pour cette analyse."
    if analysis.status == "draft":
        return "Cette analyse n'a pas encore été générée."
    if analysis.status != "success":
        return "L'analyse doit être terminée avant le déblocage."
    if analysis.unlock_method or "5" in (analysis.output or {}):
        return "Cette analyse est déjà débloquée."
    return None
```

and at the top of `unlock_analysis`:

```python
    reason = refusal(analysis)
    if reason:
        return False, reason
```

(Delete the inline status / unlock_method checks it replaces. If sub-project 1
left a parcours 3 check here, it is already gone.)

- [ ] **Step 5: Rewrite `unlock_with_code`**

In `backend/app/routes/analyses.py`, replace `unlock_with_code` (add
`from ..services import unlock_service` to the imports):

```python
@analyses_bp.post("/<analysis_id>/unlock")
@jwt_required()
def unlock_with_code(analysis_id):
    """Redeem a promo code on the caller's own free report (four-doors spec,
    decision 22). A conseiller code is refused here: with one, the full report
    goes to the counselor through the advisor door, never back to the
    candidate (ruling 2)."""
    analysis = Analysis.query.get_or_404(analysis_id)
    user_id = get_jwt_identity()
    if analysis.user_id is None or analysis.user_id != user_id:
        return jsonify({"error": "Accès non autorisé."}), 403

    code_str = code_service.normalize(text_field(json_object(), "code"))
    if not code_str:
        return jsonify({"error": code_service.REQUIRED}), 400
    code, refusal = code_service.resolve(code_str, "analysis")
    if refusal:
        return jsonify({"error": refusal}), 400
    if code_service.kind(code) != code_service.PROMO:
        return jsonify({"error": code_service.NOT_FOR_UNLOCK}), 409

    reason = unlock_service.refusal(analysis)
    if reason:
        return jsonify({"error": reason}), 409
    refused = code_service.redeem(code, user_id=user_id, target_type="analysis", target_id=analysis.id)
    if refused:
        return jsonify({"error": refused}), 409

    ok, reason = unlock_analysis(analysis, method="code")
    if not ok:
        return jsonify({"error": reason}), 409
    return jsonify({"analysis": analysis.to_dict()}), 200
```

- [ ] **Step 6: Point the voyage unlock at the per-kind resolver**

In `backend/app/routes/voyage.py`, `unlock_voyage`, replace from
`code, refusal = code_service.resolve(code_str)` to the end of the function:

```python
    code, refusal = code_service.resolve(code_str, "voyage")
    if refusal:
        return jsonify({"error": refusal}), 400

    refused = code_service.redeem(
        code, user_id=voyage.user_id, target_type="voyage", target_id=voyage.id
    )
    if refused:
        return jsonify({"error": refused}), 400

    voyage.counselor_code_id = code.id
    db.session.commit()
    return jsonify({"voyage": voyage.to_dict()}), 200
```

- [ ] **Step 7: Update the existing tests that used the old API**

Run: `cd backend && grep -n "record(\|resolve(\|/unlock" tests/test_code_service.py tests/test_code_redemption_routes.py tests/test_unlock.py tests/test_voyage_routes.py`

For each hit:
- `code_service.record(code, …)` → `code_service.redeem(code, …)` (it now
  commits; drop the caller's `db.session.commit()` if it only served that).
- `code_service.resolve(x)` → `code_service.resolve(x, "analysis")` or
  `"voyage"`, matching what the test redeems.
- An unlock posted without a session, or on an ownerless analysis, now
  answers 401 / 403: give the analysis an owner and post with `bearer(owner)`.
- An unlock test that redeems a conseiller code (owner set) now expects 409
  `NOT_FOR_UNLOCK`; switch it to a promo code (`owner_id=None`) if it is
  about the unlock itself.
- A test asserting that one code use blocks both kinds now expects the other
  kind to stay open (ruling 10).

- [ ] **Step 8: Run, then commit**

Run: `cd backend && python -m pytest tests/test_code_doors.py tests/test_code_service.py tests/test_code_redemption_routes.py tests/test_unlock.py tests/test_voyage_routes.py -q`
Expected: all pass. Then `python -m pytest -q` — all green.

```bash
git add backend/app/services/code_service.py backend/app/services/unlock_service.py \
        backend/app/routes/analyses.py backend/app/routes/voyage.py backend/tests
git commit -m "feat(doors): codes by kind, counted per kind, ceiling held by the database

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 4: The door table and the daily caps

**Files:**
- Create: `backend/app/services/doors.py`
- Test: `backend/tests/test_doors.py`

**Interfaces:**
- Consumes: `RunLog` (Task 1), config caps (Task 2), `tiers.FREE`,
  `tiers.PAID`, `code_service.PROMO` / `CONSEILLER` (Task 3).
- Produces: `doors.ACCOUNT / PROMO / ADVISOR / ANONYMOUS / LEGACY`,
  `doors.NAME_MAX = 80`, `doors.Plan`, `doors.PLANS`,
  `doors.decide(door, *, user_id) -> (Plan | None, (message, status) | None)`,
  `doors.over_cap(plan, user_id) -> str | None`,
  `doors.log_run(door, user_id) -> None` (caller commits), and the messages
  `UNKNOWN`, `SIGN_IN`, `SIGNED_IN`, `CONSENT`, `IDENTITY`, `IDENTITY_LONG`,
  `ANONYMOUS_CAP`, `ACCOUNT_CAP`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_doors.py`:

```python
"""The four doors, as a table (four-doors spec, « Submit, per door »)."""
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models.analysis import Analysis
from app.models.run_log import RunLog
from app.services import doors


@pytest.mark.parametrize("door,tier,code_kind,folds,consent,identity,token", [
    ("account",   "free", None,         True,  False, False, False),
    ("promo",     "paid", "promo",      True,  False, False, False),
    ("advisor",   "paid", "conseiller", False, True,  True,  False),
    ("anonymous", "free", None,         False, True,  False, True),
])
def test_the_table(door, tier, code_kind, folds, consent, identity, token):
    plan = doors.PLANS[door]
    assert (plan.tier, plan.code_kind, plan.folds_profile, plan.needs_consent,
            plan.needs_identity, plan.gives_token) == (tier, code_kind, folds, consent, identity, token)
    assert plan.always_new_row is (door == "advisor")


@pytest.mark.parametrize("door,user_id,expected", [
    ("account", "u1", None), ("account", None, (doors.SIGN_IN, 401)),
    ("promo", "u1", None), ("promo", None, (doors.SIGN_IN, 401)),
    ("advisor", "u1", None), ("advisor", None, None),
    ("anonymous", None, None), ("anonymous", "u1", (doors.SIGNED_IN, 400)),
    ("premium", "u1", (doors.UNKNOWN, 400)), (["account"], "u1", (doors.UNKNOWN, 400)),
])
def test_decide(door, user_id, expected):
    plan, refusal = doors.decide(door, user_id=user_id)
    assert refusal == expected
    assert (plan is None) == (expected is not None)


def test_no_door_while_signed_in_means_the_account_door():
    # A stale tab posting {inputs, tier}: the free tier, never the tier it asked for.
    plan, refusal = doors.decide(None, user_id="u1")
    assert refusal is None and plan.door == "account" and plan.tier == "free"


def test_no_door_while_signed_out_is_unknown():
    assert doors.decide(None, user_id=None) == (None, (doors.UNKNOWN, 400))


def _log(door, user_id=None, hours_ago=0):
    db.session.add(RunLog(door=door, user_id=user_id,
                          created_at=datetime.utcnow() - timedelta(hours=hours_ago)))


def test_the_account_cap_counts_the_last_24_hours_of_this_account(app):
    for _ in range(5):
        _log("account", "u1")
    _log("account", "u1", hours_ago=25)
    _log("account", "u2")
    db.session.commit()
    plan = doors.PLANS["account"]
    assert doors.over_cap(plan, "u1") == doors.ACCOUNT_CAP.format(n=5)
    assert doors.over_cap(plan, "u2") is None


def test_deleting_reports_never_lowers_the_count(app):
    """Blocker B1 of the spec review: the count reads run_log, not analyses."""
    for _ in range(5):
        _log("account", "u1")
        db.session.add(Analysis(user_id=None, status="success", inputs={}))
    db.session.commit()
    Analysis.query.delete()
    db.session.commit()
    assert doors.over_cap(doors.PLANS["account"], "u1") is not None


def test_the_anonymous_cap_counts_every_no_login_run(app):
    app.config["ANONYMOUS_RUNS_PER_DAY"] = 3
    for _ in range(3):
        _log("anonymous")
    db.session.commit()
    assert doors.over_cap(doors.PLANS["anonymous"], None) == doors.ANONYMOUS_CAP


def test_promo_and_advisor_have_no_daily_cap(app):
    for _ in range(50):
        _log("promo", "u1")
        _log("advisor")
    db.session.commit()
    assert doors.over_cap(doors.PLANS["promo"], "u1") is None
    assert doors.over_cap(doors.PLANS["advisor"], None) is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_doors.py -q`
Expected: FAIL — `ImportError: cannot import name 'doors'`.

- [ ] **Step 3: Write `doors.py`**

`backend/app/services/doors.py`:

```python
"""The four doors behind « Générer mon analyse » (four-doors spec).

One table says, per door, which tier runs, who the report is for, what the
door must be given, and which daily cap it counts against. create_analysis
applies it and decides nothing on its own; in particular, nothing the browser
sends chooses a tier any more (decision 14).
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from flask import current_app

from ..extensions import db
from ..models.run_log import RunLog
from . import tiers

ACCOUNT = "account"
PROMO = "promo"
ADVISOR = "advisor"
ANONYMOUS = "anonymous"
# Not a door: the mark on ownerless rows written before accounts were required.
LEGACY = "legacy"

NAME_MAX = 80

UNKNOWN = "Porte inconnue."
SIGN_IN = "Non authentifié."
SIGNED_IN = "Vous êtes connecté : choisissez « Avec mon compte »."
CONSENT = "Merci d’accepter les CGV et la politique de confidentialité."
IDENTITY = "Prénom et nom requis."
IDENTITY_LONG = "Prénom ou nom trop long (80 caractères maximum)."
ANONYMOUS_CAP = (
    "La version sans compte est très demandée aujourd'hui. Créez un compte, "
    "ou revenez demain."
)
ACCOUNT_CAP = (
    "Vous avez lancé {n} analyses gratuites aujourd'hui. Revenez demain, ou "
    "débloquez une analyse existante."
)


@dataclass(frozen=True)
class Plan:
    door: str
    tier: str
    needs_session: bool      # account, promo: 401 without one
    refuses_session: bool    # anonymous: a signed-in visitor uses « Avec mon compte »
    code_kind: str | None    # code_service.PROMO / CONSEILLER, or no code
    folds_profile: bool      # the Profil de base and le voyage join the inputs
    needs_consent: bool      # no signup consent to rely on
    needs_identity: bool     # prénom + nom, for the counselor (ruling 9)
    always_new_row: bool     # never promote a draft the candidate holds an id to
    gives_token: bool        # the report's only key is a private link
    cap: str | None          # which daily cap counts this run


PLANS = {
    ACCOUNT: Plan(
        door=ACCOUNT, tier=tiers.FREE, needs_session=True, refuses_session=False,
        code_kind=None, folds_profile=True, needs_consent=False, needs_identity=False,
        always_new_row=False, gives_token=False, cap=ACCOUNT,
    ),
    PROMO: Plan(
        door=PROMO, tier=tiers.PAID, needs_session=True, refuses_session=False,
        code_kind="promo", folds_profile=True, needs_consent=False, needs_identity=False,
        always_new_row=False, gives_token=False, cap=None,
    ),
    ADVISOR: Plan(
        door=ADVISOR, tier=tiers.PAID, needs_session=False, refuses_session=False,
        code_kind="conseiller", folds_profile=False, needs_consent=True, needs_identity=True,
        always_new_row=True, gives_token=False, cap=None,
    ),
    ANONYMOUS: Plan(
        door=ANONYMOUS, tier=tiers.FREE, needs_session=False, refuses_session=True,
        code_kind=None, folds_profile=False, needs_consent=True, needs_identity=False,
        always_new_row=False, gives_token=True, cap=ANONYMOUS,
    ),
}


def decide(door, *, user_id: str | None) -> tuple[Plan | None, tuple[str, int] | None]:
    """The plan for this door and this caller, or (message, status)."""
    if door is None and user_id is not None:
        # A form tab older than the doors posts {inputs, tier}: it gets the
        # account door's free tier, never the tier it asked for.
        door = ACCOUNT
    plan = PLANS.get(door) if isinstance(door, str) else None
    if plan is None:
        return None, (UNKNOWN, 400)
    if plan.needs_session and user_id is None:
        return None, (SIGN_IN, 401)
    if plan.refuses_session and user_id is not None:
        return None, (SIGNED_IN, 400)
    return plan, None


def _since() -> datetime:
    return datetime.utcnow() - timedelta(days=1)


def over_cap(plan: Plan, user_id: str | None) -> str | None:
    """The French refusal when this run would pass its daily cap, else None.

    Counted from run_log over the last 24 hours (decision 40), never from
    analyses, which their holders may delete."""
    if plan.cap == ANONYMOUS:
        limit = current_app.config["ANONYMOUS_RUNS_PER_DAY"]
        count = RunLog.query.filter(
            RunLog.door == ANONYMOUS, RunLog.created_at >= _since()
        ).count()
        return ANONYMOUS_CAP if count >= limit else None
    if plan.cap == ACCOUNT:
        limit = current_app.config["FREE_RUNS_PER_ACCOUNT_PER_DAY"]
        count = RunLog.query.filter(
            RunLog.door == ACCOUNT, RunLog.user_id == user_id, RunLog.created_at >= _since()
        ).count()
        return ACCOUNT_CAP.format(n=limit) if count >= limit else None
    return None


def log_run(door: str, user_id: str | None) -> None:
    """Count one submitted run. The caller commits it with the row it counts."""
    db.session.add(RunLog(door=door, user_id=user_id))
```

- [ ] **Step 4: Run, then commit**

Run: `cd backend && python -m pytest tests/test_doors.py -q` — expected: all pass.

```bash
git add backend/app/services/doors.py backend/tests/test_doors.py
git commit -m "feat(doors): the door table and the daily caps over run_log

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
## Task 5: Who may read an analysis — tokens, `_may_access`, `/by-token`

**Files:**
- Modify: `backend/app/utils/tokens.py`
- Modify: `backend/app/routes/analyses.py` (`_may_access`, new `get_by_token`, imports)
- Modify: `backend/app/models/analysis.py` (`to_dict`: `door`, `access_expires_at`)
- Test: `backend/tests/test_analysis_access_tokens.py`
- Modify tests: `backend/tests/test_analysis_access.py` (ownerless rows that
  must stay readable now carry `door="legacy"`)

**Interfaces:**
- Consumes: the columns (Task 1), `doors.ADVISOR / LEGACY` (Task 4).
- Produces: `tokens.new_access_token() -> str`, `tokens.hash_token(token) -> str`;
  `analyses.TOKEN_HEADER = "X-Analysis-Token"`; `_header_token_hash() -> str | None`;
  `GET /api/analyses/by-token`; `to_dict()` keys `door`, `access_expires_at`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_analysis_access_tokens.py`:

```python
"""Who may read an analysis (four-doors spec, « Who may read an analysis »)."""
from datetime import timedelta

from app.extensions import db
from app.models.analysis import Analysis
from app.models.price_feedback import BUCKETS
from app.utils.tokens import hash_token, new_access_token
from tests.helpers_doors import bearer, counselor, expired_bearer, user


def _row(status="success", **fields):
    a = Analysis(status=status, inputs={"_path": "1"}, output={"1": {"title": "t"}}, **fields)
    db.session.add(a)
    db.session.commit()
    return a


def _get(client, a, headers=None):
    return client.get(f"/api/analyses/{a.id}", headers=headers or {}).status_code


def _token_row(**fields):
    token = new_access_token()
    return token, _row(user_id=None, door="anonymous", access_token_hash=hash_token(token), **fields)


def test_the_owner_reads_their_row_and_nobody_else_does(client, app):
    owner, other = user(), user("other@test.fr")
    a = _row(user_id=owner.id, door="account")
    assert _get(client, a, bearer(owner)) == 200
    assert _get(client, a, bearer(other)) == 403
    assert _get(client, a) == 403


def test_an_expired_session_is_a_signed_out_visitor(client, app):
    owner = user()
    a = _row(user_id=owner.id, door="account")
    assert _get(client, a, expired_bearer(owner)) == 403


def test_a_legacy_row_stays_open_by_id(client, app):
    assert _get(client, _row(user_id=None, door="legacy")) == 200


def test_a_row_with_nothing_set_is_closed(client, app):
    assert _get(client, _row(user_id=None)) == 403


def test_a_token_row_opens_with_its_token_only(client, app):
    token, a = _token_row()
    assert _get(client, a, {"X-Analysis-Token": token}) == 200
    assert _get(client, a, {"X-Analysis-Token": token + "x"}) == 403
    assert _get(client, a) == 403


def test_by_token_finds_the_report(client, app):
    token, a = _token_row()
    res = client.get("/api/analyses/by-token", headers={"X-Analysis-Token": token})
    assert res.status_code == 200
    assert res.get_json()["analysis"]["id"] == a.id
    assert client.get("/api/analyses/by-token", headers={"X-Analysis-Token": "nope"}).status_code == 404
    assert client.get("/api/analyses/by-token").status_code == 404


def test_by_token_never_serves_a_held_draft(client, app):
    token = new_access_token()
    _row(status="draft", user_id=None, access_token_hash=hash_token(token))
    assert client.get("/api/analyses/by-token", headers={"X-Analysis-Token": token}).status_code == 404


def test_an_advisor_row_is_closed_to_every_candidate_route(client, app):
    c = counselor()
    a = _row(user_id=None, door="advisor", counselor_id=c.id)
    assert _get(client, a, bearer(c)) == 403
    assert _get(client, a) == 403
    assert client.delete(f"/api/analyses/{a.id}").status_code == 403
    # The counselor's account erased (ON DELETE SET NULL): still closed.
    a.counselor_id = None
    db.session.commit()
    assert _get(client, a) == 403


def test_the_token_holder_may_answer_the_price_probe_and_delete(client, app):
    token, a = _token_row()
    headers = {"X-Analysis-Token": token}
    res = client.post(f"/api/analyses/{a.id}/price-feedback", json={"bucket": BUCKETS[0]}, headers=headers)
    assert res.status_code == 200
    assert client.delete(f"/api/analyses/{a.id}", headers=headers).status_code == 200


def test_the_report_says_when_its_link_expires(client, app):
    token, a = _token_row()
    body = client.get("/api/analyses/by-token", headers={"X-Analysis-Token": token}).get_json()["analysis"]
    assert body["door"] == "anonymous"
    assert body["access_expires_at"].startswith((a.created_at + timedelta(days=30)).date().isoformat())


def test_only_the_hash_is_stored():
    token = new_access_token()
    assert len(token) >= 43 and hash_token(token) != token and len(hash_token(token)) == 64
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_analysis_access_tokens.py -q`
Expected: FAIL — `ImportError: cannot import name 'hash_token'`.

- [ ] **Step 3: Add the token helpers**

Append to `backend/app/utils/tokens.py` (add `import hashlib` at the top):

```python
def new_access_token() -> str:
    """The key to a no-login report or a held draft (four-doors spec,
    decisions 30, 34): 32 random bytes, URL-safe. Only hash_token() of it is
    ever stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Rewrite `_may_access` and add `/by-token`**

In `backend/app/routes/analyses.py`, add to the imports:

```python
import hmac

from flask import request

from ..services import doors
from ..utils.tokens import hash_token, new_access_token
```

and `TOKEN_HEADER = "X-Analysis-Token"` under `analyses_bp = …`. Replace
`_may_access` and add a helper:

```python
def _header_token_hash() -> str | None:
    """The hash of the X-Analysis-Token header, or None. The page reads the
    token from its URL fragment and sends it here as a header, so it never
    lands in an access log (four-doors spec, decision 30)."""
    raw = request.headers.get(TOKEN_HEADER, "")
    return hash_token(raw) if raw else None


def _may_access(analysis: Analysis) -> bool:
    """Who may read or change an analysis on the candidate-facing routes —
    the spec's « Who may read an analysis », in its order.

    1. An advisor-door report is the counselor's alone (ruling 2), and its
       counselor reads it through /api/counselor, never here. `door` is tested
       as well as `counselor_id`, so erasing a counselor never opens one.
    2. A token row opens with its token, and only with it.
    3. An owned row opens for its owner.
    4. A legacy row — ownerless, written before accounts were required, marked
       by the four-doors migration — stays open by id, as it always was.
    5. Anything else is closed. A row that loses its owner some other way must
       not become readable by whoever has its id.
    """
    if analysis.door == doors.ADVISOR or analysis.counselor_id is not None:
        return False
    if analysis.access_token_hash is not None:
        presented = _header_token_hash()
        return presented is not None and hmac.compare_digest(presented, analysis.access_token_hash)
    if analysis.user_id is not None:
        return analysis.user_id == _optional_user_id()
    return analysis.door == doors.LEGACY
```

Add the route **above** `get_analysis` (a static path, matched before
`/<analysis_id>`):

```python
@analyses_bp.get("/by-token")
def get_by_token():
    """A no-login report, by the key in its link. A held draft is read through
    /held, by its cookie: its key never leaves the cookie."""
    presented = _header_token_hash()
    row = Analysis.query.filter_by(access_token_hash=presented).first() if presented else None
    if row is None or row.status == "draft":
        return jsonify({"error": "Ce lien n'est plus valide."}), 404
    return jsonify({"analysis": row.to_dict()}), 200
```

Update `get_analysis`'s docstring: the legacy sentence now reads "an ownerless
row stays readable by id only when the four-doors migration marked it
`legacy`".

- [ ] **Step 5: `to_dict` says the door and when the link expires**

In `backend/app/models/analysis.py` (add `from datetime import timedelta` and
`from flask import current_app`), add to the `data` dict in `to_dict`:

```python
            "door": self.door,
            "access_expires_at": self._access_expires_at(),
```

and the method:

```python
    def _access_expires_at(self) -> str | None:
        """When an unclaimed no-login report's link stops working (four-doors
        spec, decision 32). None for every other row."""
        if self.door != "anonymous" or self.user_id is not None or self.created_at is None:
            return None
        days = current_app.config.get("ANONYMOUS_RETENTION_DAYS", 30)
        return (self.created_at + timedelta(days=days)).isoformat()
```

- [ ] **Step 6: Mark the legacy rows in the existing access tests**

Run: `cd backend && python -m pytest tests/test_analysis_access.py -q`. Each test
that expects an ownerless row to be readable now needs `door="legacy"` on that
row; a test asserting an ownerless row is readable *without* that mark is
asserting what decision 44 removes — invert it to expect 403.

- [ ] **Step 7: Run, then commit**

Run: `cd backend && python -m pytest tests/test_analysis_access_tokens.py tests/test_analysis_access.py -q`, then `python -m pytest -q`.
Expected: all green.

```bash
git add backend/app/utils/tokens.py backend/app/routes/analyses.py backend/app/models/analysis.py backend/tests
git commit -m "feat(doors): who may read an analysis — tokens by header, legacy by mark

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 6: Held drafts — the cookie, `/held`, `/hold`, `/claim`, signup and verify

**Files:**
- Create: `backend/app/services/held.py`
- Modify: `backend/app/routes/analyses.py` (`save_draft`, new `get_held`, `hold_report`, `claim`)
- Modify: `backend/app/routes/auth.py` (`register`, `verify_email`, `reset_password`)
- Modify: `backend/app/services/sign_in.py` (`enter`)
- Test: `backend/tests/test_held_drafts.py`
- Modify tests: `backend/tests/test_anonymous_closed.py` — delete
  `test_a_draft_needs_an_account` (drafts are open now)

**Interfaces:**
- Consumes: `tokens.new_access_token / hash_token`, `TOKEN_HEADER`,
  `_header_token_hash`, `_optional_user_id` (Task 5); `analysis_inputs.clean`
  (Task 2); `doors.ANONYMOUS` (Task 4).
- Produces: `held.COOKIE = "neoori_hold"`, `held.set_cookie(response, token)`,
  `held.clear_cookie(response)`, `held.held_row(*, draft_only=False) -> Analysis | None`,
  `held.new_held_draft(inputs) -> (Analysis, token)`, `held.attach(row, user_id)`,
  `held.mark_for(user_id) -> bool`, `held.attach_pending(user_id) -> int`,
  `held.unmark(user_id) -> int`; routes `GET /api/analyses/held`,
  `POST /api/analyses/hold`, `POST /api/analyses/claim`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_held_drafts.py`:

```python
"""Held drafts and the neoori_hold cookie (four-doors spec, decisions 34-36)."""
from app.extensions import db
from app.models.analysis import Analysis
from app.services import held, sign_in
from app.utils import auth_links
from app.utils.tokens import hash_token, new_access_token
from tests.helpers_doors import P1_INPUTS, bearer, user


def _cookie(client):
    cookie = client.get_cookie(held.COOKIE, path="/api")
    return cookie.value if cookie else None


def _held_draft(client, inputs=P1_INPUTS):
    return client.post("/api/analyses/draft", json={"inputs": inputs})


def test_a_signed_out_draft_is_held_by_a_cookie_and_never_by_the_body(client, app):
    res = _held_draft(client)
    assert res.status_code == 201
    token = _cookie(client)
    assert token and token not in res.get_data(as_text=True)
    row = Analysis.query.one()
    assert (row.user_id, row.status, row.access_token_hash) == (None, "draft", hash_token(token))


def test_saving_again_reuses_the_held_row(client, app):
    # Review focus 5: two tabs, one browser, one cookie.
    _held_draft(client)
    res = _held_draft(client, {**P1_INPUTS, "cible_visee": "x" * 60})
    assert res.status_code == 200
    assert Analysis.query.count() == 1
    assert Analysis.query.one().inputs["cible_visee"] == "x" * 60


def test_a_held_draft_keeps_only_client_keys(client, app):
    _held_draft(client, {**P1_INPUTS, "_conditions": ["x"], "_tier": "premium"})
    assert set(Analysis.query.one().inputs) == {"cv_text", "cible_visee"}


def test_held_reads_the_draft_back_and_404s_without_a_cookie(client, app):
    assert client.get("/api/analyses/held").status_code == 404
    _held_draft(client)
    res = client.get("/api/analyses/held")
    assert res.status_code == 200
    assert res.get_json()["analysis"]["inputs"]["cv_text"] == P1_INPUTS["cv_text"]


def test_claim_attaches_the_held_draft_once(client, app):
    # Review focus 5: the second claim is a clean 404.
    _held_draft(client)
    u = user()
    assert client.post("/api/analyses/claim", headers=bearer(u)).status_code == 200
    row = Analysis.query.one()
    assert (row.user_id, row.access_token_hash) == (u.id, None)
    assert _cookie(client) is None
    assert client.post("/api/analyses/claim", headers=bearer(u)).status_code == 404


def test_claim_needs_a_session(client, app):
    _held_draft(client)
    assert client.post("/api/analyses/claim").status_code == 401


def test_hold_hands_a_no_login_report_to_the_cookie_and_claim_kills_the_link(client, app):
    token = new_access_token()
    report = Analysis(status="success", door="anonymous", inputs={}, access_token_hash=hash_token(token))
    db.session.add(report)
    db.session.commit()

    assert client.post("/api/analyses/hold", headers={"X-Analysis-Token": token}).status_code == 200
    assert _cookie(client) == token
    u = user()
    assert client.post("/api/analyses/claim", headers=bearer(u)).status_code == 200
    db.session.expire_all()
    assert db.session.get(Analysis, report.id).user_id == u.id
    assert client.get("/api/analyses/by-token", headers={"X-Analysis-Token": token}).status_code == 404


def test_hold_refuses_an_unknown_token(client, app):
    assert client.post("/api/analyses/hold", headers={"X-Analysis-Token": "nope"}).status_code == 404


def test_signup_marks_and_only_the_signup_password_attaches(client, app):
    _held_draft(client)
    res = client.post("/api/auth/register", json={"email": "zoe@test.fr", "password": "motdepasse1"})
    assert res.status_code == 201
    new_id = res.get_json()["user"]["id"]
    row = Analysis.query.one()
    assert (row.pending_user_id, row.user_id) == (new_id, None)   # marked, not attached

    from app.models.user import User
    token = auth_links.make_verify_token(db.session.get(User, new_id))
    assert client.post("/api/auth/verify-email",
                       json={"token": token, "password": "motdepasse1"}).status_code == 200
    db.session.expire_all()
    row = Analysis.query.one()
    assert (row.user_id, row.access_token_hash, row.pending_user_id) == (new_id, None, None)


def test_signup_for_a_taken_address_marks_nothing(client, app):
    user("zoe@test.fr")
    _held_draft(client)
    assert client.post("/api/auth/register",
                       json={"email": "zoe@test.fr", "password": "motdepasse1"}).status_code == 409
    assert Analysis.query.one().pending_user_id is None


def test_proving_the_address_another_way_drops_the_mark_and_keeps_the_row(client, app):
    _held_draft(client)
    res = client.post("/api/auth/register", json={"email": "zoe@test.fr", "password": "motdepasse1"})
    from app.models.user import User
    stranger_set = db.session.get(User, res.get_json()["user"]["id"])

    sign_in.enter(stranger_set)            # Google, Microsoft or the email link
    db.session.expire_all()
    row = Analysis.query.one()
    assert (row.pending_user_id, row.user_id) == (None, None)
    assert row.access_token_hash is not None    # still held by the browser that made it


def test_a_reset_on_an_unverified_account_drops_the_mark(client, app):
    _held_draft(client)
    res = client.post("/api/auth/register", json={"email": "zoe@test.fr", "password": "motdepasse1"})
    from app.models.user import User
    account = db.session.get(User, res.get_json()["user"]["id"])
    token = auth_links.make_reset_token(account)
    assert client.post("/api/auth/reset-password",
                       json={"token": token, "password": "nouveau-mdp1"}).status_code == 200
    db.session.expire_all()
    assert Analysis.query.one().pending_user_id is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_held_drafts.py -q`
Expected: FAIL — `ImportError: cannot import name 'held'`.

- [ ] **Step 3: Write `held.py`**

`backend/app/services/held.py`:

```python
"""The neoori_hold cookie (four-doors spec, decisions 34-36).

A signed-out draft has to survive a sign-in round trip — a Google redirect, or
the verification mail opened on a phone — without its key ever travelling in a
URL, a mail or a log. The key sits in this HttpOnly cookie; the row stores only
its hash. The same cookie carries a no-login report handed over by « Garder ».
One held row at a time.

Nothing here attaches a row to an account before the signup password has
proven its address (decision 36): signup only marks the row
(`pending_user_id`), verify-email attaches it, and any other proof of the
address drops the mark.
"""
from flask import current_app, request

from ..extensions import db
from ..models.analysis import Analysis
from ..utils.tokens import hash_token, new_access_token

COOKIE = "neoori_hold"
# Every /api route that reads it: drafts, claim, and /auth/register.
PATH = "/api"


def _secure() -> bool:
    return bool(current_app.config.get("SESSION_COOKIE_SECURE"))


def set_cookie(response, token: str) -> None:
    response.set_cookie(
        COOKIE, token,
        max_age=current_app.config["HELD_DRAFT_RETENTION_HOURS"] * 3600,
        path=PATH, httponly=True, samesite="Lax", secure=_secure(),
    )


def clear_cookie(response) -> None:
    response.delete_cookie(COOKIE, path=PATH, httponly=True, samesite="Lax", secure=_secure())


def held_row(*, draft_only: bool = False) -> Analysis | None:
    """The ownerless row this browser's cookie holds, or None."""
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    row = Analysis.query.filter_by(access_token_hash=hash_token(token)).first()
    if row is None or row.user_id is not None:
        return None
    if draft_only and row.status != "draft":
        return None
    return row


def new_held_draft(inputs: dict) -> tuple[Analysis, str]:
    """A new ownerless draft and the raw key for its cookie. Caller commits."""
    token = new_access_token()
    row = Analysis(inputs=inputs, status="draft", access_token_hash=hash_token(token))
    db.session.add(row)
    return row, token


def attach(row: Analysis, user_id: str) -> None:
    """The row becomes the account's own. Its key dies: an old link to it, or
    a stale cookie, now finds nothing. Caller commits."""
    row.user_id = user_id
    row.access_token_hash = None
    row.pending_user_id = None


def mark_for(user_id: str) -> bool:
    """Password signup: the held row waits for this account. Caller commits."""
    row = held_row()
    if row is None:
        return False
    row.pending_user_id = user_id
    return True


def attach_pending(user_id: str) -> int:
    """verify-email, with the signup password: attach what signup marked."""
    rows = Analysis.query.filter_by(pending_user_id=user_id, user_id=None).all()
    for row in rows:
        attach(row, user_id)
    return len(rows)


def unmark(user_id: str) -> int:
    """The address was proven without the signup password: whoever registered
    it may have been someone else, so nothing they held joins the account. The
    rows stay held by the browser that made them, and expire with it."""
    return Analysis.query.filter_by(pending_user_id=user_id).update(
        {"pending_user_id": None}, synchronize_session=False
    )
```

- [ ] **Step 4: Open the draft route and add `/held`, `/hold`, `/claim`**

In `backend/app/routes/analyses.py`, add
`from ..services import analysis_inputs, held` to the imports. Replace
`save_draft`:

```python
@analyses_bp.post("/draft")
def save_draft():
    """Create or update a draft.

    Signed in: the account's own draft, as before. Signed out: the draft this
    browser holds (four-doors spec, decision 34) — saved by the doors that need
    a sign-in round trip, keyed by the neoori_hold cookie and never by
    anything in the body.
    """
    user_id = _optional_user_id()
    data = json_object()
    inputs, errors = analysis_inputs.clean(dict_field(data, "inputs"))
    if errors:
        return jsonify({"errors": errors}), 400

    if user_id is None:
        row, token, status = held.held_row(draft_only=True), None, 200
        if row is None:
            row, token = held.new_held_draft(inputs)
            status = 201
        else:
            row.inputs = inputs
        db.session.commit()
        response = jsonify({"analysis": row.to_dict()})
        if token:
            held.set_cookie(response, token)
        return response, status

    # text_field, not a bare data.get(): a non-string draft_id (a list, a
    # dict) reaching filter_by(id=draft_id) as a query parameter raises
    # sqlalchemy.exc.ProgrammingError.
    draft_id = text_field(data, "draft_id")
    if draft_id:
        analysis = Analysis.query.filter_by(id=draft_id, user_id=user_id, status="draft").first()
        if analysis:
            analysis.inputs = inputs
            db.session.commit()
            return jsonify({"analysis": analysis.to_dict()}), 200

    analysis = Analysis(user_id=user_id, inputs=inputs, status="draft")
    db.session.add(analysis)
    db.session.commit()
    return jsonify({"analysis": analysis.to_dict()}), 201


@analyses_bp.get("/held")
def get_held():
    """The draft this browser holds, to refill the form after a round trip."""
    row = held.held_row(draft_only=True)
    if row is None:
        return jsonify({"error": "Votre brouillon a expiré."}), 404
    return jsonify({"analysis": row.to_dict()}), 200


@analyses_bp.post("/hold")
def hold_report():
    """« Créer un compte pour le garder » (decision 32): hand a no-login report
    to the cookie, so the claim after sign-in finds it. The page proves it
    holds the link with the header."""
    raw = request.headers.get(TOKEN_HEADER, "")
    row = Analysis.query.filter_by(access_token_hash=hash_token(raw)).first() if raw else None
    if row is None or row.user_id is not None or row.door != doors.ANONYMOUS:
        return jsonify({"error": "Ce lien n'est plus valide."}), 404
    response = jsonify({})
    held.set_cookie(response, raw)
    return response, 200


@analyses_bp.post("/claim")
def claim():
    """Attach the held row to the signed-in account, then forget the cookie."""
    user_id = _optional_user_id()
    if user_id is None:
        return jsonify({"error": doors.SIGN_IN}), 401
    row = held.held_row()
    if row is None:
        return jsonify({"error": "Votre brouillon a expiré."}), 404
    held.attach(row, user_id)
    db.session.commit()
    response = jsonify({"analysis": row.to_dict()})
    held.clear_cookie(response)
    return response, 200
```

- [ ] **Step 5: Signup marks, verify attaches, other proofs unmark**

In `backend/app/routes/auth.py` (import `from ..services import held`):

In `register`, after `db.session.commit()` that creates the user and before
the verification mail:

```python
    # A draft this browser holds waits for this account (four-doors spec,
    # decision 34): marked now, attached only once the signup password proves
    # the address at verify-email (decision 36). Never for an address that
    # already had an account — that answered 409 above.
    if held.mark_for(user.id):
        db.session.commit()
```

In `verify_email`, inside `if user.email_verified_at is None:` and before its
`db.session.commit()`:

```python
        # The link AND the signup password: the registrant. What signup marked
        # for this account is theirs.
        held.attach_pending(user.id)
```

In `reset_password`, inside its `if newly_verified:` branch (the one that sets
`email_verified_at`), before the commit:

```python
        # Proven without the signup password: whoever registered this address
        # may have been someone else (four-doors spec, decision 36).
        held.unmark(user.id)
```

In `backend/app/services/sign_in.py`, `enter`, inside `if newly_verified:`
(import `from . import held`):

```python
        # Same reason as the password above: a stranger may have registered
        # this address, and nothing they held joins the account.
        held.unmark(user.id)
```

- [ ] **Step 6: Drop the closed-draft assertion**

In `backend/tests/test_anonymous_closed.py`, delete
`test_a_draft_needs_an_account`.

- [ ] **Step 7: Run, then commit**

Run: `cd backend && python -m pytest tests/test_held_drafts.py tests/test_auth_link_routes.py tests/test_sign_in.py tests/test_anonymous_closed.py -q`, then `python -m pytest -q`.
Expected: all green.

```bash
git add backend/app/services/held.py backend/app/routes/analyses.py backend/app/routes/auth.py \
        backend/app/services/sign_in.py backend/tests
git commit -m "feat(doors): signed-out drafts held by an HttpOnly cookie, attached only after proof

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 7: The submit — four doors, one route; uploads open

**Files:**
- Modify: `backend/app/routes/analyses.py` (`create_analysis`; delete `_FORCE_TIER`)
- Modify: `backend/app/routes/upload.py` (drop `@jwt_required`)
- Modify: `backend/app/models/profile.py` (`CONSENT_VERSION = "v1.3"`)
- Test: `backend/tests/test_submit_doors.py`
- Delete: `backend/tests/test_anonymous_closed.py` (its remaining assertions
  are the closed surface this task opens; `test_submit_doors.py` covers the
  open one)
- Modify tests: every test that posts `/api/analyses/` and asserts a tier.
  Find them: `grep -rln "_tier\|\"tier\"" backend/tests`. Without
  `FORCE_ANALYSIS_TIER`, a signed-in post with no `door` runs the free tier.

**Interfaces:**
- Consumes: Tasks 2-6.
- Produces: `POST /api/analyses/` body
  `{inputs, door?, draft_id?, code?, prenom?, nom?, consent?}` → per door:
  `{analysis}` (account, promo) · `{}` (advisor) · `{analysis, access_token}`
  (anonymous); status 201.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_submit_doors.py`:

```python
"""The submit, per door (four-doors spec, « Submit, per door »)."""
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.analysis import Analysis
from app.models.code_redemption import CodeRedemption
from app.models.profile import CONSENT_VERSION, Profile
from app.models.run_log import RunLog
from app.utils.tokens import hash_token
from tests.helpers_doors import P1_INPUTS, bearer, code, counselor, expired_bearer, user

START = "app.routes.analyses.start_analysis"


def _post(client, headers=None, **body):
    return client.post("/api/analyses/", json={"inputs": P1_INPUTS, **body}, headers=headers or {})


def _profiled(email="marie@test.fr"):
    u = user(email)
    db.session.add(Profile(user_id=u.id, prenom="Marie", ville="Lyon"))
    db.session.commit()
    return u


@patch(START)
def test_account_door_runs_the_free_tier_for_the_owner(start, client, app):
    u = _profiled()
    res = _post(client, bearer(u), door="account")
    assert res.status_code == 201, res.data
    row = db.session.get(Analysis, res.get_json()["analysis"]["id"])
    assert (row.user_id, row.door, row.inputs["_tier"], row.inputs["prenom"]) == (u.id, "account", "free", "Marie")
    assert RunLog.query.filter_by(door="account", user_id=u.id).count() == 1
    start.assert_called_once()


@patch(START)
def test_no_door_while_signed_in_is_the_account_door_and_tier_is_ignored(_s, client, app):
    u = user()
    res = _post(client, bearer(u), tier="premium")
    assert res.status_code == 201
    assert Analysis.query.one().inputs["_tier"] == "free"


@patch(START)
def test_force_analysis_tier_no_longer_exists(_s, client, app, monkeypatch):
    monkeypatch.setenv("FORCE_ANALYSIS_TIER", "paid")
    _post(client, bearer(user()), door="account")
    assert Analysis.query.one().inputs["_tier"] == "free"


@patch(START)
def test_account_door_needs_a_valid_session(_s, client, app):
    u = user()
    assert _post(client, door="account").status_code == 401
    assert _post(client, expired_bearer(u), door="account").status_code == 401


@patch(START)
def test_promo_door_runs_complet_and_spends_one_use(_s, client, app):
    u = _profiled()
    c = code(value="PROMO007", max_uses=5)
    res = _post(client, bearer(u), door="promo", code="promo-007")
    assert res.status_code == 201, res.data
    row = Analysis.query.one()
    assert (row.door, row.inputs["_tier"], row.user_id) == ("promo", "paid", u.id)
    redemption = CodeRedemption.query.one()
    assert (redemption.code_id, redemption.user_id, redemption.target_id) == (c.id, u.id, row.id)
    # Once per account.
    assert _post(client, bearer(u), door="promo", code="PROMO007").status_code == 409


@patch(START)
def test_advisor_door_sends_complet_to_the_counselor_only(start, client, app):
    c = counselor()
    code(c, max_uses=1, value="CONS0004")
    res = _post(client, door="advisor", code="CONS0004", prenom="  Zoé ", nom="N'Guessan-Kouamé",
                consent=True)
    assert res.status_code == 201, res.data
    assert res.get_json() == {}
    row = Analysis.query.one()
    assert (row.door, row.user_id, row.counselor_id, row.access_token_hash) == ("advisor", None, c.id, None)
    assert row.inputs["_tier"] == "paid"
    # Review focus 1: trimmed, accents kept.
    assert (row.inputs["prenom"], row.inputs["nom"]) == ("Zoé", "N'Guessan-Kouamé")
    assert row.consent_at is not None and row.consent_version == CONSENT_VERSION
    assert CodeRedemption.query.one().user_id is None
    start.assert_called_once()


@patch(START)
def test_advisor_door_folds_nothing_even_when_signed_in(_s, client, app):
    u = _profiled()
    code(counselor(), value="CONS0005")
    _post(client, bearer(u), door="advisor", code="CONS0005", prenom="Marie", nom="Durand", consent=True)
    row = Analysis.query.one()
    assert row.user_id is None
    assert set(row.inputs) == {"cv_text", "cible_visee", "_chemin", "_path", "_tier", "prenom", "nom"}


@patch(START)
def test_advisor_door_writes_a_new_row_and_deletes_the_callers_draft(_s, client, app):
    u = user()
    draft = Analysis(user_id=u.id, status="draft", inputs=dict(P1_INPUTS))
    db.session.add(draft)
    db.session.commit()
    draft_id = draft.id
    code(counselor(), value="CONS0006")
    _post(client, bearer(u), door="advisor", code="CONS0006", prenom="M", nom="D",
          consent=True, draft_id=draft_id)
    assert db.session.get(Analysis, draft_id) is None
    assert Analysis.query.one().id != draft_id


@pytest.mark.parametrize("extra,expected", [
    ({"prenom": "", "nom": "Durand", "consent": True}, 400),
    ({"prenom": "Zoé", "nom": "D" * 81, "consent": True}, 400),
    ({"prenom": "Z" * 80, "nom": "D" * 80, "consent": True}, 201),   # Review focus 1
    ({"prenom": "Zoé", "nom": "Durand"}, 400),                        # no consent
    ({"prenom": "Zoé", "nom": "Durand", "consent": "yes"}, 400),
])
@patch(START)
def test_advisor_door_needs_identity_and_consent(_s, client, app, extra, expected):
    code(counselor(), value="CONS0007")
    assert _post(client, door="advisor", code="CONS0007", **extra).status_code == expected


@patch(START)
def test_anonymous_door_gives_a_private_link(_s, client, app):
    res = _post(client, door="anonymous", consent=True)
    assert res.status_code == 201, res.data
    body = res.get_json()
    row = Analysis.query.one()
    assert (row.door, row.user_id, row.inputs["_tier"]) == ("anonymous", None, "free")
    assert row.access_token_hash == hash_token(body["access_token"])
    assert body["analysis"]["access_expires_at"] is not None


@patch(START)
def test_anonymous_door_refuses_a_live_session_but_not_an_expired_one(_s, client, app):
    u = user()
    assert _post(client, bearer(u), door="anonymous", consent=True).status_code == 400
    assert _post(client, expired_bearer(u), door="anonymous", consent=True).status_code == 201


@patch(START)
def test_anonymous_door_promotes_the_held_draft_with_a_fresh_key(_s, client, app):
    client.post("/api/analyses/draft", json={"inputs": P1_INPUTS})
    draft = Analysis.query.one()
    draft_hash = draft.access_token_hash
    res = _post(client, door="anonymous", consent=True)
    row = db.session.get(Analysis, draft.id)
    assert row.status == "queued" and row.access_token_hash != draft_hash
    assert row.access_token_hash == hash_token(res.get_json()["access_token"])


@patch(START)
def test_server_keys_never_survive(_s, client, app):
    u = user()
    poisoned = {**P1_INPUTS, "_conditions": ["x"], "_oeth": True, "_voyage": ["y"], "_tier": "premium"}
    client.post("/api/analyses/", json={"inputs": poisoned, "door": "account"}, headers=bearer(u))
    inputs = Analysis.query.one().inputs
    assert "_conditions" not in inputs and "_oeth" not in inputs and "_voyage" not in inputs
    assert inputs["_tier"] == "free"


@patch(START)
def test_the_daily_caps_hold(_s, client, app):
    app.config["FREE_RUNS_PER_ACCOUNT_PER_DAY"] = 2
    app.config["ANONYMOUS_RUNS_PER_DAY"] = 1
    u = user()
    assert _post(client, bearer(u), door="account").status_code == 201
    assert _post(client, bearer(u), door="account").status_code == 201
    assert _post(client, bearer(u), door="account").status_code == 429
    assert _post(client, door="anonymous", consent=True).status_code == 201
    assert _post(client, door="anonymous", consent=True).status_code == 429


@patch(START)
def test_a_wrong_door_code_says_which_door(_s, client, app):
    code(counselor(), value="CONS0008")
    res = _post(client, bearer(user()), door="promo", code="CONS0008")
    assert res.status_code == 409 and res.get_json()["door"] == "advisor"
    assert Analysis.query.count() == 0


@patch(START)
def test_an_unknown_door_is_400(_s, client, app):
    assert _post(client, bearer(user()), door="premium").status_code == 400


@pytest.mark.parametrize("path", ["/api/upload/cv", "/api/upload/projet"])
def test_uploads_are_open(client, app, path):
    import io
    # Signed out, and past the gate: an unreadable PDF gets the route's own
    # 422 « Impossible d'extraire le texte », not a 401.
    data = {"file": (io.BytesIO(b"not a pdf body"), "cv.pdf", "application/pdf")}
    res = client.post(path, data=data, content_type="multipart/form-data")
    assert res.status_code == 422
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_submit_doors.py -q`
Expected: FAIL — most cases 401 (the route is still `@jwt_required`) or wrong tier.

- [ ] **Step 3: Rewrite `create_analysis`**

In `backend/app/routes/analyses.py`, delete the `_FORCE_TIER` block and its
comment. Add to the imports `from datetime import datetime`,
`from uuid import uuid4`, `from ..models.profile import CONSENT_VERSION`.
Replace `create_analysis`:

```python
@analyses_bp.post("/")
def create_analysis():
    """The submit behind « Générer mon analyse »: one of four doors (four-doors
    spec). services/doors.py decides the tier and who the report is for. A
    `tier` in the body, from a form older than the doors, is never read.

    Order matters: everything that can refuse runs before the code is spent,
    and the code is spent — committed — before the run starts (decision 23).
    """
    user_id = _optional_user_id()
    data = json_object()

    inputs, errors = analysis_inputs.clean(dict_field(data, "inputs"))
    if errors:
        return jsonify({"errors": errors}), 400

    plan, refusal = doors.decide(text_field(data, "door") or None, user_id=user_id)
    if refusal:
        message, status = refusal
        return jsonify({"error": message}), status

    inputs["_path"] = "1"
    inputs["_chemin"] = _normalize_chemin(inputs.get("_chemin"))
    errors = _validate_inputs(inputs)
    if errors:
        return jsonify({"errors": errors}), 400

    if plan.needs_identity:
        prenom, nom = text_field(data, "prenom"), text_field(data, "nom")
        if not prenom or not nom:
            return jsonify({"error": doors.IDENTITY}), 400
        if len(prenom) > doors.NAME_MAX or len(nom) > doors.NAME_MAX:
            return jsonify({"error": doors.IDENTITY_LONG}), 400
        inputs["prenom"], inputs["nom"] = prenom, nom

    if plan.needs_consent and data.get("consent") is not True:
        return jsonify({"error": doors.CONSENT}), 400

    over = doors.over_cap(plan, user_id)
    if over:
        return jsonify({"error": over}), 429

    code = None
    if plan.code_kind:
        code, door_refusal = code_service.resolve_for_door(data.get("code"), plan.door, user_id)
        if door_refusal:
            body = {"error": door_refusal.message}
            if door_refusal.door:
                body["door"] = door_refusal.door
            return jsonify(body), door_refusal.status

    inputs["_tier"] = plan.tier
    if plan.folds_profile:
        # Profil de base and le voyage join the inputs — account and promo
        # only. An advisor-door report goes to a counselor and must carry
        # nothing the candidate's account knows (decision 24).
        _merge_profile(inputs, user_id)

    draft = _draft_for(data, user_id)
    promote = draft is not None and not plan.always_new_row
    target_id = draft.id if promote else str(uuid4())

    if code is not None:
        refused = code_service.redeem(
            code,
            # Promo: the account, for once-per-account. Advisor: nobody — the
            # candidate stays out of the counselor's records but for prénom/nom.
            user_id=user_id if plan.door == doors.PROMO else None,
            target_type="analysis",
            target_id=target_id,
        )
        if refused:
            return jsonify({"error": refused}), 409
        if draft is not None:
            # redeem() committed; the draft row was expired with the session.
            draft = db.session.get(Analysis, draft.id)

    if promote:
        analysis = draft
    else:
        if draft is not None:
            db.session.delete(draft)
        analysis = Analysis(id=target_id)
        db.session.add(analysis)

    token = new_access_token() if plan.gives_token else None
    analysis.inputs = inputs
    analysis.status = "queued"
    # The run's time, not the draft's: retention and the report's date count
    # from here (decision 34).
    analysis.created_at = datetime.utcnow()
    analysis.door = plan.door
    analysis.user_id = user_id if plan.needs_session else None
    analysis.counselor_id = code.owner_id if plan.door == doors.ADVISOR else None
    analysis.pending_user_id = None
    analysis.access_token_hash = hash_token(token) if token else None
    if plan.needs_consent:
        analysis.consent_at = datetime.utcnow()
        analysis.consent_version = CONSENT_VERSION
    # Stored on the row as well as in the inputs blob: which voyage fed this
    # analysis stays queryable -- B2G traceability, as with prompt_version_id.
    analysis.voyage_id = inputs.get("_voyage_id")
    doors.log_run(plan.door, user_id)
    db.session.commit()

    # Hand the slow Anthropic call to a background thread so the HTTP
    # response returns immediately; the page polls for status.
    start_analysis(analysis.id, current_app._get_current_object())

    if plan.door == doors.ADVISOR:
        body = {}
    elif token:
        body = {"analysis": analysis.to_dict(), "access_token": token}
    else:
        body = {"analysis": analysis.to_dict()}
    response = jsonify(body)
    if user_id is None and draft is not None:
        held.clear_cookie(response)
    return response, 201


def _draft_for(data: dict, user_id: str | None) -> Analysis | None:
    """The draft this submit replaces: the caller's own (draft_id) when signed
    in, the one this browser holds when not. None when there is none."""
    if user_id is not None:
        draft_id = text_field(data, "draft_id")
        if not draft_id:
            return None
        return Analysis.query.filter_by(id=draft_id, user_id=user_id, status="draft").first()
    return held.held_row(draft_only=True)
```

Delete the now-unused import `generate_share_token` (share links are no longer
minted) and `tiers` if nothing else in the file uses it. Update
`_merge_profile`'s and `_merge_voyage`'s docstrings: the client's keys are
already allow-listed by `analysis_inputs.clean()`, so the pops in
`_merge_voyage` stay only as defence in depth.

- [ ] **Step 4: Open the uploads**

In `backend/app/routes/upload.py`, delete both `@jwt_required()` lines and the
`jwt_required` import. Add above `upload_cv`:

```python
# Open to signed-out visitors: the parcours 1 form is (four-doors spec, ruling
# 1). The text is extracted in memory and returned, never stored; nginx's
# `analyses` zone limits these per address (decision 39).
```

- [ ] **Step 5: Bump the consent version**

In `backend/app/models/profile.py`: `CONSENT_VERSION = "v1.3"` with the
comment `# v1.3: CGV §2 and §6 for the four doors (four-doors spec, decision 48).`

- [ ] **Step 6: Delete the closed-surface test file and fix tier assertions**

```bash
git rm backend/tests/test_anonymous_closed.py
grep -rln "_tier\|\"tier\"" backend/tests
```
In each listed file, a post to `/api/analyses/` that expected the forced
`"paid"` now gets `"free"` (account door) — change the expectation, or post
`door="promo"` with a promo code where the test is about a paid run. A test
that posts a `tier` to choose the tier asserts what decision 14 removes:
assert the free tier instead.

- [ ] **Step 7: Run, then commit**

Run: `cd backend && python -m pytest tests/test_submit_doors.py -q`, then `python -m pytest -q`.
Expected: all green.

```bash
git add backend/app/routes/analyses.py backend/app/routes/upload.py backend/app/models/profile.py backend/tests
git commit -m "feat(doors): one submit, four doors; the server decides the tier

FORCE_ANALYSIS_TIER and the browser's tier are gone. The form and the
uploads are open; each door says who the report is for.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 8: Payment — the owner pays, and only for an unlock that will happen

**Files:**
- Modify: `backend/app/routes/payments.py` (`create_checkout`, `verify_session`)
- Test: `backend/tests/test_checkout_owner.py`
- Modify tests: `test_checkout_503_without_key` (wherever it lives:
  `grep -rn "test_checkout_503_without_key" backend/tests`) signs in as the
  analysis owner first.

**Interfaces:**
- Consumes: `unlock_service.refusal` (Task 3).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_checkout_owner.py`:

```python
"""Checkout and verify belong to the owner, and checkout refuses exactly when
the unlock would (four-doors spec, decision 41)."""
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db
from app.models.analysis import Analysis
from tests.helpers_doors import bearer, user

STRIPE = "app.routes.payments._stripe"


def _analysis(owner, **fields):
    a = Analysis(user_id=owner.id, door="account", inputs={"_path": "1", "_tier": "free"},
                 **({"status": "success", "output": {"1": {}}} | fields))
    db.session.add(a)
    db.session.commit()
    return a


@patch(STRIPE)
def test_checkout_needs_a_session_and_the_owner(stripe_factory, client, app):
    stripe_factory.return_value = MagicMock()
    owner, other = user(), user("other@test.fr")
    a = _analysis(owner)
    body = {"analysis_id": a.id, "tier": "paid"}
    assert client.post("/api/payments/checkout", json=body).status_code == 401
    assert client.post("/api/payments/checkout", json=body, headers=bearer(other)).status_code == 403
    stripe_factory.return_value.checkout.Session.create.assert_not_called()


@pytest.mark.parametrize("fields", [
    {"status": "error"},
    {"status": "running"},
    {"output": {"1": {}, "5": {}}},          # already Complet: no Premium upgrade either
    {"unlock_method": "code"},
])
@patch(STRIPE)
def test_checkout_refuses_whenever_the_unlock_would(stripe_factory, client, app, fields):
    stripe_factory.return_value = MagicMock()
    owner = user()
    a = _analysis(owner, **fields)
    res = client.post("/api/payments/checkout", json={"analysis_id": a.id, "tier": "premium"},
                      headers=bearer(owner))
    assert res.status_code == 409
    stripe_factory.return_value.checkout.Session.create.assert_not_called()


@patch(STRIPE)
def test_checkout_goes_through_for_the_owners_free_report(stripe_factory, client, app):
    stripe = MagicMock()
    stripe.checkout.Session.create.return_value = MagicMock(url="https://stripe.test/s")
    stripe_factory.return_value = stripe
    owner = user()
    a = _analysis(owner)
    res = client.post("/api/payments/checkout", json={"analysis_id": a.id, "tier": "paid"},
                      headers=bearer(owner))
    assert res.status_code == 200 and res.get_json()["url"] == "https://stripe.test/s"


@patch(STRIPE)
def test_verify_needs_the_owner(stripe_factory, client, app):
    import stripe as stripe_lib

    stripe = MagicMock()
    owner, other = user(), user("other@test.fr")
    a = _analysis(owner)
    # A real StripeObject, as test_unlock.py uses: stripe v15 objects support
    # bracket access and .to_dict(), never .get().
    stripe.checkout.Session.retrieve.return_value = stripe_lib.StripeObject.construct_from(
        {"id": "cs_1", "payment_status": "paid", "metadata": {"analysis_id": a.id, "tier": "paid"}},
        "sk_test",
    )
    stripe_factory.return_value = stripe
    assert client.post("/api/payments/verify", json={"session_id": "cs_1"}).status_code == 401
    assert client.post("/api/payments/verify", json={"session_id": "cs_1"},
                       headers=bearer(other)).status_code == 403
```

If `StripeObject.construct_from` is not what the installed stripe version
offers, build the stub exactly as `tests/test_unlock.py` builds its own.

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_checkout_owner.py -q`
Expected: FAIL — 200 / 409 where 401 / 403 are expected.

- [ ] **Step 3: Owner-only checkout with the shared refusal**

In `backend/app/routes/payments.py` (import `jwt_required`,
`get_jwt_identity`, and `from ..services import unlock_service`):

- Decorate `create_checkout` with `@jwt_required()`.
- After `analysis = Analysis.query.get_or_404(analysis_id)`, replace the
  parcours-3 check (gone after sub-project 1), the `unlock_method` check and
  the `status != "success"` check with:

```python
    # The owner pays for their own report, and only for an unlock that will
    # happen: the same refusal unlock_analysis applies (four-doors spec,
    # decision 41). Without it, a report that already had §5 could be paid
    # for and then refuse to unlock.
    if analysis.user_id is None or analysis.user_id != get_jwt_identity():
        return jsonify({"error": "Accès non autorisé."}), 403
    reason = unlock_service.refusal(analysis)
    if reason:
        return jsonify({"error": reason}), 409
```

- Decorate `verify_session` with `@jwt_required()`, and as soon as it has
  loaded the analysis named by the session's metadata:

```python
    if analysis.user_id is None or analysis.user_id != get_jwt_identity():
        return jsonify({"error": "Accès non autorisé."}), 403
```

The webhook is unchanged: Stripe signs it, and it carries no session cookie.

- [ ] **Step 4: Sign in the 503 test**

In `test_checkout_503_without_key`, create the analysis with an owner and post
with `bearer(owner)`: the route now answers 401 before it looks for the key.

- [ ] **Step 5: Run, then commit**

Run: `cd backend && python -m pytest tests/test_checkout_owner.py tests/test_unlock.py -q`, then `python -m pytest -q`.

```bash
git add backend/app/routes/payments.py backend/tests
git commit -m "fix(payments): owner-only checkout and verify, same refusal as the unlock

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
## Task 9: The counselor's side — their reports, notes, relaunch; `/c/<token>` goes

**Files:**
- Delete: `backend/app/routes/counselor.py`; unregister it in `backend/app/__init__.py`
  (the `from .routes.counselor import counselor_bp` line and
  `app.register_blueprint(counselor_bp, url_prefix="/api/c")`)
- Modify: `backend/app/models/analysis.py` (`to_dict`, delete
  `COUNSELOR_VISIBLE_INPUT_KEYS`)
- Modify: `backend/app/services/section_registry.py` (drop `"counselor"`,
  `counselor_keys()`)
- Modify: `backend/app/services/code_service.py` (add `use_counts_by_kind`)
- Modify: `backend/app/routes/counselor_space.py`
- Test: `backend/tests/test_counselor_analyses.py`
- Modify tests: find them with
  `grep -rln "counselor_keys\|audience=\|/api/c/\|share_token\|COUNSELOR_VISIBLE" backend/tests`
  — `test_analysis_model.py` (counselor-view cases: delete), the `/api/c`
  notes rigs in `test_malformed_bodies.py` and `test_no_500_on_hostile_input.py`
  (delete those cases), `test_counselor_dashboard.py` and
  `test_counselor_codes.py` (a single-use code used for a voyage is now
  still `actif` and still in circulation: its analysis place is open).

**Interfaces:**
- Consumes: `doors.ADVISOR` (Task 4); columns (Task 1); `start_analysis`.
- Produces:
  - `code_service.use_counts_by_kind(code_ids) -> dict[str, dict[str, int]]`
    (`{"analysis": n, "voyage": m}` per code);
  - `GET /api/counselor/analyses` → `{analyses: [{id, prenom, nom, code_label, status, created_at}]}`;
  - `GET /api/counselor/analyses/<id>` → `{analysis, code_label}`;
  - `DELETE /api/counselor/analyses/<id>`;
  - `POST /api/counselor/analyses/<id>/relaunch` → `{analysis}`;
  - `GET` / `PUT /api/counselor/analyses/<id>/notes` → `{note}`;
  - `/beneficiaires` rows gain `nom`, `analysis_id`;
  - `/codes` rows gain `uses_by_kind`.
  - `to_dict()` no longer has `share_token` or `counselor_keys`, and takes no
    `audience`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_counselor_analyses.py`:

```python
"""The counselor's own advisor-door reports (four-doors spec, decisions 26-27, 43)."""
from unittest.mock import patch

from app.extensions import db
from app.models.analysis import Analysis
from app.models.code_redemption import CodeRedemption
from app.models.counselor_note import CounselorNote
from tests.helpers_doors import bearer, code, counselor, user

BASE = "/api/counselor/analyses"


def _advisor_row(c, *, status="success", via=None):
    row = Analysis(
        door="advisor", counselor_id=c.id, status=status,
        inputs={"_path": "1", "prenom": "Zoé", "nom": "Durand"},
        output={"1": {"title": "Lecture stratégique"}},
    )
    db.session.add(row)
    db.session.commit()
    if via is not None:
        db.session.add(CodeRedemption(code_id=via.id, target_type="analysis", target_id=row.id, slot=1))
        db.session.commit()
    return row


def test_the_counselor_lists_and_reads_their_reports(client, app):
    c = counselor()
    row = _advisor_row(c, via=code(c, max_uses=1, label="Atelier mardi"))
    listed = client.get(BASE, headers=bearer(c)).get_json()["analyses"]
    assert listed == [{
        "id": row.id, "prenom": "Zoé", "nom": "Durand", "code_label": "Atelier mardi",
        "status": "success", "created_at": row.created_at.isoformat(),
    }]
    res = client.get(f"{BASE}/{row.id}", headers=bearer(c))
    assert res.status_code == 200
    body = res.get_json()
    assert body["analysis"]["output"]["1"]["title"] == "Lecture stratégique"
    assert body["code_label"] == "Atelier mardi"


def test_another_counselor_a_candidate_and_a_revoked_counselor_cannot(client, app):
    c = counselor()
    row = _advisor_row(c)
    assert client.get(f"{BASE}/{row.id}", headers=bearer(counselor("autre@test.fr"))).status_code == 404
    assert client.get(f"{BASE}/{row.id}", headers=bearer(user())).status_code == 403
    revoked = counselor("revoque@test.fr", status="revoked")
    row.counselor_id = revoked.id
    db.session.commit()
    assert client.get(f"{BASE}/{row.id}", headers=bearer(revoked)).status_code == 403


def test_a_candidates_own_report_is_not_a_counselor_report(client, app):
    c = counselor()
    own = Analysis(user_id=c.id, door="account", status="success", inputs={"_path": "1"})
    db.session.add(own)
    db.session.commit()
    assert client.get(f"{BASE}/{own.id}", headers=bearer(c)).status_code == 404


@patch("app.routes.counselor_space.start_analysis")
def test_relaunch_only_a_failed_run_and_only_once(start, client, app):
    # Review focus 4: the double click.
    c = counselor()
    row = _advisor_row(c, status="error")
    assert client.post(f"{BASE}/{row.id}/relaunch", headers=bearer(c)).status_code == 200
    assert client.post(f"{BASE}/{row.id}/relaunch", headers=bearer(c)).status_code == 409
    start.assert_called_once()
    assert CodeRedemption.query.count() == 0


@patch("app.routes.counselor_space.start_analysis")
def test_a_finished_report_is_not_relaunched(start, client, app):
    c = counselor()
    row = _advisor_row(c)
    assert client.post(f"{BASE}/{row.id}/relaunch", headers=bearer(c)).status_code == 409
    start.assert_not_called()


def test_one_note_per_counselor_and_delete_takes_it_along(client, app):
    c = counselor()
    row = _advisor_row(c)
    for body in ("Première", "Seconde"):
        assert client.put(f"{BASE}/{row.id}/notes", json={"note": body}, headers=bearer(c)).status_code == 200
    assert CounselorNote.query.count() == 1
    assert client.get(f"{BASE}/{row.id}/notes", headers=bearer(c)).get_json() == {"note": "Seconde"}
    assert client.delete(f"{BASE}/{row.id}", headers=bearer(c)).status_code == 200
    assert CounselorNote.query.count() == 0
    assert Analysis.query.count() == 0


def test_a_note_has_a_ceiling(client, app):
    c = counselor()
    row = _advisor_row(c)
    res = client.put(f"{BASE}/{row.id}/notes", json={"note": "n" * 20_001}, headers=bearer(c))
    assert res.status_code == 400


def test_beneficiaires_name_the_advisor_reports(client, app):
    c = counselor()
    row = _advisor_row(c, via=code(c, max_uses=1))
    people = client.get("/api/counselor/beneficiaires", headers=bearer(c)).get_json()["beneficiaires"]
    assert len(people) == 1
    assert (people[0]["prenom"], people[0]["nom"], people[0]["analysis_id"]) == ("Zoé", "Durand", row.id)


def test_a_single_use_code_stays_in_circulation_until_both_kinds_are_spent(client, app):
    c = counselor()
    k = code(c, max_uses=1)
    db.session.add(CodeRedemption(code_id=k.id, target_type="voyage", target_id="v1", slot=1))
    db.session.commit()
    row = client.get("/api/counselor/codes", headers=bearer(c)).get_json()["codes"][0]
    assert row["statut"] == "actif"
    assert row["uses_by_kind"] == {"analysis": 0, "voyage": 1}
    assert client.get("/api/counselor/stats", headers=bearer(c)).get_json()["codes_en_circulation"] == 1


def test_the_share_link_is_gone(client, app):
    assert client.get("/api/c/anything").status_code == 404


def test_to_dict_has_no_counselor_audience(app):
    data = Analysis(status="success", inputs={"_path": "1"}, output={}).to_dict()
    assert "share_token" not in data and "counselor_keys" not in data
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_counselor_analyses.py -q`
Expected: FAIL — 404 on `/api/counselor/analyses`.

- [ ] **Step 3: Remove the share link and the counselor audience**

1. `git rm backend/app/routes/counselor.py`; delete its import and
   `register_blueprint` line in `backend/app/__init__.py`.
2. In `backend/app/models/analysis.py`: delete `COUNSELOR_VISIBLE_INPUT_KEYS`
   and its comment block; `to_dict(self)` loses its `audience` parameter, the
   `"share_token"` key, both `if audience == "counselor"` branches and
   `data["counselor_keys"]`. What remains after the base dict:

```python
        # Render instructions for the client: ordered, with titles and render
        # mode. The client must never sort output keys itself.
        data["sections_meta"] = registry.sections_meta(parcours)
        if self.output:
            data["output"] = self.output
        return data
```

   Also change the `share_token` column comment to
   `# The retired /c/<share_token> link (four-doors spec, decision 43): kept,
   no longer minted.`
3. In `backend/app/services/section_registry.py`: delete the `"counselor"`
   entry of `PARCOURS["1"]`, the comment above `PARCOURS` that describes it,
   and `counselor_keys()`. Run `grep -rn "counselor_keys" backend/app` —
   expected: no hit.

- [ ] **Step 4: Counts per kind**

Append to `backend/app/services/code_service.py`:

```python
def use_counts_by_kind(code_ids: list[str]) -> dict[str, dict[str, int]]:
    """{code_id: {"analysis": n, "voyage": m}} in one grouped query — the
    counselor's and the admin's code tables both show uses per kind (ruling 10)."""
    if not code_ids:
        return {}
    rows = (
        db.session.query(CodeRedemption.code_id, CodeRedemption.target_type, db.func.count(CodeRedemption.id))
        .filter(CodeRedemption.code_id.in_(code_ids))
        .group_by(CodeRedemption.code_id, CodeRedemption.target_type)
        .all()
    )
    counts: dict[str, dict[str, int]] = {}
    for code_id, target_type, n in rows:
        counts.setdefault(code_id, {"analysis": 0, "voyage": 0})[target_type] = n
    return counts
```

- [ ] **Step 5: The counselor routes**

In `backend/app/routes/counselor_space.py`: update the module docstring (the
`/api/c` sentence goes: "routes/counselor.py, mounted at /api/c, served an
analysis share link until the four-doors spec retired it"). Add imports:

```python
from flask import current_app

from ..models.analysis import Analysis
from ..models.counselor_note import CounselorNote
from ..models.price_feedback import PriceFeedback
from ..services import doors
from ..services.anthropic_service import start_analysis
```

Replace `_code_row` and `_use_counts`, and their callers:

```python
_NO_USES = {"analysis": 0, "voyage": 0}


def _code_row(code: CounselorCode, uses: dict[str, int]) -> dict:
    """The code, its real use counts per kind, and one French status.

    « utilisé » once BOTH kinds are spent: a single-use code opens one
    analysis and one voyage (four-doors spec, ruling 10)."""
    if code.revoked_at is not None or not code.is_active:
        statut = "revoque"
    elif code.max_uses is not None and min(uses.values()) >= code.max_uses:
        statut = "utilise"
    elif code.expires_at is not None and code.expires_at <= datetime.utcnow():
        statut = "expire"
    else:
        statut = "actif"
    return {**code.to_dict(), "uses": sum(uses.values()), "uses_by_kind": uses, "statut": statut}
```

- `list_codes`: `counts = code_service.use_counts_by_kind([c.id for c in codes])`
  and `_code_row(c, counts.get(c.id, dict(_NO_USES)))`.
- `create_code` and `revoke_code`: `_code_row(code, dict(_NO_USES))`.
- `stats`: `counts = code_service.use_counts_by_kind(...)`;
  `"beneficiaires": sum(sum(v.values()) for v in counts.values())`; the
  in-circulation test becomes
  `(c.max_uses is None or min(counts.get(c.id, _NO_USES).values()) < c.max_uses)`.

Replace `beneficiaires`:

```python
@counselor_space_bp.get("/beneficiaires")
@approved_counselor_required
def beneficiaires():
    """Who used my codes, and when — and, for an analysis sent through the
    advisor door, the report itself (four-doors spec, ruling 2, which reverses
    conseiller spec decision 9). A voyage is still reached only through the
    token the person hands over."""
    me = get_jwt_identity()
    code_ids = _my_code_ids(me)
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
    analysis_ids = [r.target_id for r, _u, _p in rows if r.target_type == "analysis"]
    mine = {
        a.id: a for a in Analysis.query.filter(
            Analysis.id.in_(analysis_ids), Analysis.counselor_id == me, Analysis.door == doors.ADVISOR,
        ).all()
    } if analysis_ids else {}

    people = []
    for redemption, user, profile in rows:
        report = mine.get(redemption.target_id) if redemption.target_type == "analysis" else None
        inputs = (report.inputs or {}) if report is not None else {}
        people.append({
            "prenom": inputs.get("prenom") or (profile.prenom if profile else None),
            "nom": inputs.get("nom"),
            "email": user.email if user else None,
            "target_type": redemption.target_type,
            "redeemed_at": redemption.redeemed_at.isoformat(),
            "analysis_id": report.id if report is not None else None,
        })
    return jsonify({"beneficiaires": people}), 200
```

Append the analysis routes:

```python
NOTE_MAX = 20_000


def _my_report(analysis_id: str) -> Analysis | None:
    """An advisor-door report this counselor owns, or None. Another
    counselor's, a candidate's own, or a missing one all answer the same 404."""
    row = db.session.get(Analysis, analysis_id)
    if row is None or row.door != doors.ADVISOR or row.counselor_id != get_jwt_identity():
        return None
    return row


def _code_labels(analysis_ids: list[str]) -> dict[str, str]:
    """Which code each report came through, by its label — how a counselor
    tells reports apart beside prénom and nom (ruling 9)."""
    if not analysis_ids:
        return {}
    rows = (
        db.session.query(CodeRedemption.target_id, CounselorCode.label)
        .join(CounselorCode, CounselorCode.id == CodeRedemption.code_id)
        .filter(CodeRedemption.target_type == "analysis", CodeRedemption.target_id.in_(analysis_ids))
        .all()
    )
    return dict(rows)


_NOT_FOUND = ({"error": "Analyse introuvable."}, 404)


@counselor_space_bp.get("/analyses")
@approved_counselor_required
def my_reports():
    rows = (
        Analysis.query.filter_by(counselor_id=get_jwt_identity(), door=doors.ADVISOR)
        .order_by(Analysis.created_at.desc())
        .all()
    )
    labels = _code_labels([r.id for r in rows])
    return jsonify({"analyses": [
        {
            "id": r.id,
            "prenom": (r.inputs or {}).get("prenom"),
            "nom": (r.inputs or {}).get("nom"),
            "code_label": labels.get(r.id),
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]}), 200


@counselor_space_bp.get("/analyses/<analysis_id>")
@approved_counselor_required
def my_report(analysis_id):
    row = _my_report(analysis_id)
    if row is None:
        return jsonify(_NOT_FOUND[0]), _NOT_FOUND[1]
    return jsonify({"analysis": row.to_dict(), "code_label": _code_labels([row.id]).get(row.id)}), 200


@counselor_space_bp.delete("/analyses/<analysis_id>")
@approved_counselor_required
def delete_my_report(analysis_id):
    row = _my_report(analysis_id)
    if row is None:
        return jsonify(_NOT_FOUND[0]), _NOT_FOUND[1]
    # counselor_notes' foreign key has no ON DELETE: the notes go first.
    CounselorNote.query.filter_by(analysis_id=row.id).delete()
    PriceFeedback.query.filter_by(analysis_id=row.id).delete()
    db.session.delete(row)
    db.session.commit()
    return jsonify({"message": "Analyse supprimée."}), 200


@counselor_space_bp.post("/analyses/<analysis_id>/relaunch")
@approved_counselor_required
def relaunch_my_report(analysis_id):
    """« Relancer » (decision 27): the same row, the same inputs, no new code
    use — the candidate left with /analyse/envoyee and cannot retry. Only a
    failed run: a second click while the first is queued is a 409, so one
    failure never becomes two paid runs."""
    row = _my_report(analysis_id)
    if row is None:
        return jsonify(_NOT_FOUND[0]), _NOT_FOUND[1]
    if row.status not in ("error", "timeout"):
        return jsonify({"error": "Cette analyse n'a pas besoin d'être relancée."}), 409
    row.status = "queued"
    row.progress = 0
    db.session.commit()
    start_analysis(row.id, current_app._get_current_object())
    return jsonify({"analysis": row.to_dict()}), 200


def _my_note(row: Analysis) -> CounselorNote | None:
    return CounselorNote.query.filter_by(analysis_id=row.id, counselor_id=get_jwt_identity()).first()


@counselor_space_bp.get("/analyses/<analysis_id>/notes")
@approved_counselor_required
def my_report_note(analysis_id):
    row = _my_report(analysis_id)
    if row is None:
        return jsonify(_NOT_FOUND[0]), _NOT_FOUND[1]
    note = _my_note(row)
    return jsonify({"note": (note.body or "") if note else ""}), 200


@counselor_space_bp.put("/analyses/<analysis_id>/notes")
@approved_counselor_required
def save_my_report_note(analysis_id):
    row = _my_report(analysis_id)
    if row is None:
        return jsonify(_NOT_FOUND[0]), _NOT_FOUND[1]
    body = raw_text_field(json_object(), "note")
    if len(body) > NOTE_MAX:
        return jsonify({"error": "Note trop longue (20 000 caractères maximum)."}), 400
    note = _my_note(row)
    if note is None:
        note = CounselorNote(analysis_id=row.id, counselor_id=get_jwt_identity())
        db.session.add(note)
    note.body = body
    db.session.commit()
    return jsonify({"note": note.body}), 200
```

- [ ] **Step 6: Fix the tests that asserted the old rules**

Run: `grep -rln "counselor_keys\|audience=\|/api/c/\|share_token\|COUNSELOR_VISIBLE" backend/tests`
and, per file, delete the counselor-view / share-link cases, and update
`codes_en_circulation` / `statut` expectations for single-use codes used on
one kind only.

- [ ] **Step 7: Run, then commit**

Run: `cd backend && python -m pytest tests/test_counselor_analyses.py tests/test_counselor_dashboard.py tests/test_counselor_codes.py tests/test_analysis_model.py -q`, then `python -m pytest -q`.

```bash
git add -A backend/app backend/tests
git commit -m "feat(doors): the counselor's own reports; the /c/ share link retires

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 10: Promo codes for the admin, and `/api/codes/check`

**Files:**
- Modify: `backend/app/routes/admin.py` (counselor-codes routes)
- Create: `backend/app/routes/codes.py`; register it in `backend/app/__init__.py`
  at `/api/codes`
- Test: `backend/tests/test_admin_promo_codes.py`

**Interfaces:**
- Consumes: `code_service.kind`, `resolve`, `use_counts_by_kind`, `normalize`,
  `REQUIRED` (Tasks 3, 9).
- Produces: `POST /api/admin/counselor-codes {label, max_uses?, expires_in_days?}`;
  `PATCH /api/admin/counselor-codes/<id> {max_uses?, expires_in_days?}`;
  `DELETE` sets `revoked_at`; list rows gain `kind`, `uses_by_kind`;
  `POST /api/codes/check {code}` → `{kind}`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_admin_promo_codes.py`:

```python
"""Admin promo codes (four-doors spec, decision 18) and /api/codes/check."""
from datetime import datetime, timedelta

from app.extensions import db
from app.models.counselor_code import CounselorCode
from app.services import code_service
from tests.helpers_doors import code, counselor

BASE = "/api/admin/counselor-codes"


def test_a_new_promo_code_is_one_use_and_ninety_days(client, admin_headers):
    res = client.post(BASE, json={"label": "Salon"}, headers=admin_headers)
    assert res.status_code == 201
    row = res.get_json()["code"]
    assert (row["kind"], row["max_uses"]) == ("promo", 1)
    expires = datetime.fromisoformat(row["expires_at"])
    assert abs(expires - (datetime.utcnow() + timedelta(days=90))) < timedelta(minutes=1)


def test_null_means_illimite(client, admin_headers):
    res = client.post(BASE, json={"label": "PM", "max_uses": None, "expires_in_days": None},
                      headers=admin_headers)
    row = res.get_json()["code"]
    assert (row["max_uses"], row["expires_at"]) == (None, None)


def test_patch_changes_an_existing_codes_limits(client, admin_headers, app):
    c = code(value="OLDCODE1")          # the 2026-10 prod code: NULL / NULL
    res = client.patch(f"{BASE}/{c.id}", json={"max_uses": 3, "expires_in_days": 30}, headers=admin_headers)
    assert res.status_code == 200
    assert res.get_json()["code"]["max_uses"] == 3
    assert client.patch(f"{BASE}/{c.id}", json={"max_uses": None}, headers=admin_headers) \
        .get_json()["code"]["max_uses"] is None
    assert client.patch(f"{BASE}/{c.id}", json={"max_uses": 0}, headers=admin_headers).status_code == 400


def test_revoke_sets_revoked_at_and_the_code_stops_working(client, admin_headers, app):
    c = code(value="REVOKE01")
    assert client.delete(f"{BASE}/{c.id}", headers=admin_headers).status_code == 200
    db.session.expire_all()
    assert db.session.get(CounselorCode, c.id).revoked_at is not None
    assert code_service.resolve("REVOKE01", "analysis") == (None, code_service.INVALID)


def test_the_list_says_kind_and_uses_per_kind(client, admin_headers, app):
    code(value="PROMO010")
    code(counselor(), value="CONS0010")
    rows = {r["code"]: r for r in client.get(BASE, headers=admin_headers).get_json()["codes"]}
    assert rows["PROMO010"]["kind"] == "promo" and rows["CONS0010"]["kind"] == "conseiller"
    assert rows["PROMO010"]["uses_by_kind"] == {"analysis": 0, "voyage": 0}


def test_check_says_the_kind(client, app):
    code(value="PROMO011")
    code(counselor(), value="CONS0011")
    assert client.post("/api/codes/check", json={"code": "promo-011"}).get_json() == {"kind": "promo"}
    assert client.post("/api/codes/check", json={"code": "cons 0011"}).get_json() == {"kind": "conseiller"}


def test_check_refuses_what_submit_would(client, app):
    code(counselor(status="revoked"), value="REVO0011")
    assert client.post("/api/codes/check", json={"code": "REVO0011"}).status_code == 400
    assert client.post("/api/codes/check", json={"code": ""}).status_code == 400
    assert client.post("/api/codes/check", json={"code": "NOPE0000"}).status_code == 400
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_admin_promo_codes.py -q`
Expected: FAIL — no `kind` key; 405 on PATCH; 404 on `/api/codes/check`.

- [ ] **Step 3: The admin routes**

In `backend/app/routes/admin.py` (import `from datetime import datetime,
timedelta` if absent and `from ..services import code_service`), replace the
three counselor-codes routes:

```python
# Promo codes (four-doors spec, decision 18): one use and 90 days unless the
# admin says otherwise, `null` meaning illimité. Same ceilings as the codes a
# conseiller mints (routes/counselor_space.py).
PROMO_DEFAULT_USES = 1
PROMO_DEFAULT_DAYS = 90
USES_CEILING = 1000
DAYS_CEILING = 3650


def _admin_code_row(code: CounselorCode, uses: dict[str, int]) -> dict:
    return {**code.to_dict(), "kind": code_service.kind(code), "uses_by_kind": uses}


def _promo_limit(data: dict, key: str, default: int | None) -> tuple[int | None, str | None]:
    """Absent: the default. null: illimité. Otherwise a positive integer."""
    if key not in data:
        return default, None
    return _optional_limit(data, key)


@admin_bp.get("/counselor-codes")
@admin_required
def list_counselor_codes():
    codes = CounselorCode.query.order_by(CounselorCode.created_at.desc()).all()
    counts = code_service.use_counts_by_kind([c.id for c in codes])
    empty = {"analysis": 0, "voyage": 0}
    return jsonify({"codes": [_admin_code_row(c, counts.get(c.id, dict(empty))) for c in codes]}), 200


@admin_bp.post("/counselor-codes")
@admin_required
def create_counselor_code():
    data = json_object()
    label = text_field(data, "label")
    if not label:
        return jsonify({"error": "label requis."}), 400
    max_uses, problem = _promo_limit(data, "max_uses", PROMO_DEFAULT_USES)
    if problem:
        return jsonify({"error": problem}), 400
    days, problem = _promo_limit(data, "expires_in_days", PROMO_DEFAULT_DAYS)
    if problem:
        return jsonify({"error": problem}), 400

    code = CounselorCode(
        label=label,
        created_by_id=get_jwt_identity(),
        max_uses=None if max_uses is None else min(max_uses, USES_CEILING),
        expires_at=None if days is None else datetime.utcnow() + timedelta(days=min(days, DAYS_CEILING)),
    )
    db.session.add(code)
    db.session.commit()
    return jsonify({"code": _admin_code_row(code, {"analysis": 0, "voyage": 0})}), 201


@admin_bp.patch("/counselor-codes/<code_id>")
@admin_required
def update_counselor_code(code_id):
    """Set a code's limits later — the one admin code that predates the doors
    has neither (decision 18)."""
    code = CounselorCode.query.get_or_404(code_id)
    data = json_object()
    if "max_uses" in data:
        value, problem = _optional_limit(data, "max_uses")
        if problem:
            return jsonify({"error": problem}), 400
        code.max_uses = None if value is None else min(value, USES_CEILING)
    if "expires_in_days" in data:
        days, problem = _optional_limit(data, "expires_in_days")
        if problem:
            return jsonify({"error": problem}), 400
        code.expires_at = None if days is None else datetime.utcnow() + timedelta(days=min(days, DAYS_CEILING))
    db.session.commit()
    counts = code_service.use_counts_by_kind([code.id])
    return jsonify({"code": _admin_code_row(code, counts.get(code.id, {"analysis": 0, "voyage": 0}))}), 200


@admin_bp.delete("/counselor-codes/<code_id>")
@admin_required
def deactivate_counselor_code(code_id):
    code = CounselorCode.query.get_or_404(code_id)
    code.is_active = False
    code.revoked_at = code.revoked_at or datetime.utcnow()
    db.session.commit()
    counts = code_service.use_counts_by_kind([code.id])
    return jsonify({"code": _admin_code_row(code, counts.get(code.id, {"analysis": 0, "voyage": 0}))}), 200
```

`_optional_limit` is defined further down in the same module; Python resolves
it at call time, so its position does not matter.

- [ ] **Step 4: `/api/codes/check`**

`backend/app/routes/codes.py`:

```python
"""POST /api/codes/check — which door a code belongs to, before submit
(four-doors spec). The panel uses it to show the advisor-door notice, or to
send a promo code's holder to sign in. It redeems nothing; nginx's `codes`
zone limits it per address (decision 39)."""
from flask import Blueprint, jsonify

from ..services import code_service
from ..utils.request_body import json_object

codes_bp = Blueprint("codes", __name__)


@codes_bp.post("/check")
def check_code():
    code_str = code_service.normalize(json_object().get("code"))
    if not code_str:
        return jsonify({"error": code_service.REQUIRED}), 400
    code, refusal = code_service.resolve(code_str, "analysis")
    if refusal:
        return jsonify({"error": refusal}), 400
    return jsonify({"kind": code_service.kind(code)}), 200
```

In `backend/app/__init__.py`: `from .routes.codes import codes_bp` and
`app.register_blueprint(codes_bp, url_prefix="/api/codes")`.

- [ ] **Step 5: Run, then commit**

Run: `cd backend && python -m pytest tests/test_admin_promo_codes.py tests/test_admin.py -q`, then `python -m pytest -q`.

```bash
git add backend/app/routes/admin.py backend/app/routes/codes.py backend/app/__init__.py backend/tests
git commit -m "feat(doors): admin promo codes with limits; /api/codes/check

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 11: Mails to the counselor, and the reaper's clock

**Files:**
- Modify: `backend/app/services/email_service.py` (two senders)
- Modify: `backend/app/services/anthropic_service.py` (`_run_analysis`
  sets `started_at`; `_notify_outcome` routes advisor rows)
- Modify: `backend/app/__init__.py` (`reap_stale_running`)
- Test: `backend/tests/test_counselor_mails.py`; append to
  `backend/tests/test_stale_reaper.py`

**Interfaces:**
- Produces: `email_service.send_counselor_analysis_ready(to) -> bool`,
  `email_service.send_counselor_analysis_failed(to) -> bool`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_counselor_mails.py`:

```python
"""Advisor-door runs mail their counselor, with no name and no content
(four-doors spec, decision 28)."""
from unittest.mock import patch

from app.extensions import db
from app.models.analysis import Analysis
from app.services import anthropic_service as svc
from app.services import email_service
from tests.helpers_doors import counselor, user

READY = "app.services.email_service.send_counselor_analysis_ready"
FAILED = "app.services.email_service.send_counselor_analysis_failed"
OWNER_READY = "app.services.email_service.send_analysis_ready"
SEND = "app.services.email_service.resend.Emails.send"


def _row(**fields):
    row = Analysis(inputs={"_path": "1", "prenom": "Zoé", "nom": "Durand"}, **fields)
    db.session.add(row)
    db.session.commit()
    return row.id


def test_a_finished_advisor_run_mails_its_counselor_only(app):
    c = counselor()
    analysis_id = _row(door="advisor", counselor_id=c.id, status="success")
    with patch(READY) as ready, patch(OWNER_READY) as owner_ready:
        svc._notify_outcome(analysis_id)
    ready.assert_called_once_with(c.email)
    owner_ready.assert_not_called()


def test_a_failed_advisor_run_says_so(app):
    c = counselor()
    analysis_id = _row(door="advisor", counselor_id=c.id, status="error")
    with patch(FAILED) as failed:
        svc._notify_outcome(analysis_id)
    failed.assert_called_once_with(c.email)


def test_an_unverified_counselor_gets_nothing(app):
    c = user("nonverifie@test.fr", role="counselor", verified=False)
    analysis_id = _row(door="advisor", counselor_id=c.id, status="success")
    with patch(READY) as ready:
        svc._notify_outcome(analysis_id)
    ready.assert_not_called()


def test_a_no_login_run_mails_nobody(app):
    analysis_id = _row(door="anonymous", status="success")
    with patch(READY) as ready, patch(OWNER_READY) as owner_ready:
        svc._notify_outcome(analysis_id)
    ready.assert_not_called()
    owner_ready.assert_not_called()


def test_the_mail_names_nobody_and_links_to_the_counselor_space(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as send:
        assert email_service.send_counselor_analysis_ready("c@test.fr") is True
    params = send.call_args[0][0]
    assert params["subject"] == "Une analyse est prête"
    assert "Zoé" not in params["html"] and "Durand" not in params["text"]
    assert "/conseiller" in params["text"]
```

Append to `backend/tests/test_stale_reaper.py`:

```python
def test_the_reaper_reads_started_at_not_created_at(app):
    """A counselor's « Relancer » re-runs a row created days ago (four-doors
    spec, decision 47): it must survive a boot while it streams."""
    from datetime import datetime, timedelta

    from app import reap_stale_running
    from app.extensions import db
    from app.models.analysis import Analysis

    old, now = datetime.utcnow() - timedelta(days=3), datetime.utcnow()
    relaunched = Analysis(status="running", created_at=old, started_at=now, inputs={})
    stuck = Analysis(status="running", created_at=old, started_at=old, inputs={})
    before_the_column = Analysis(status="running", created_at=old, inputs={})
    db.session.add_all([relaunched, stuck, before_the_column])
    db.session.commit()

    assert reap_stale_running() == 2
    db.session.expire_all()
    assert db.session.get(Analysis, relaunched.id).status == "running"
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_counselor_mails.py tests/test_stale_reaper.py -q`
Expected: FAIL — `AttributeError: ... send_counselor_analysis_ready`; the
reaper test reaps 3.

- [ ] **Step 3: The two senders**

In `backend/app/services/email_service.py`, after `send_analysis_failed`:

```python
def send_counselor_analysis_ready(to: str) -> bool:
    """« Une analyse est prête » — an advisor-door run finished (four-doors
    spec, decision 28). No name and no content: the report is behind the
    counselor's login."""
    try:
        body, text = _mail(
            [
                "Bonjour,",
                "Un bénéficiaire a utilisé votre code : son analyse est prête dans "
                "votre espace conseiller.",
            ],
            button=("Ouvrir mon espace conseiller", f"{_app_url()}/conseiller"),
        )
        return send(to, "Une analyse est prête", _layout("Analyse prête", body), text)
    except Exception:
        current_app.logger.exception("Could not build/send the counselor analysis-ready mail.")
        return False


def send_counselor_analysis_failed(to: str) -> bool:
    """« Une analyse n'a pas abouti » — the counselor can relaunch it; the
    candidate, who left with /analyse/envoyee, cannot."""
    try:
        body, text = _mail(
            [
                "Bonjour,",
                "Un bénéficiaire a utilisé votre code : son analyse n’a pas abouti. "
                "Vous pouvez la relancer depuis votre espace conseiller.",
            ],
            button=("Ouvrir mon espace conseiller", f"{_app_url()}/conseiller"),
        )
        return send(to, "Une analyse n’a pas abouti", _layout("Analyse interrompue", body), text)
    except Exception:
        current_app.logger.exception("Could not build/send the counselor analysis-failed mail.")
        return False
```

- [ ] **Step 4: Route the outcome mail; stamp `started_at`**

In `backend/app/services/anthropic_service.py`, `_notify_outcome`, right after
`analysis = db.session.get(Analysis, analysis_id)`:

```python
        if analysis is not None and analysis.door == "advisor":
            # The report is the counselor's (ruling 2), so is the mail. Same
            # rule as the owner's: only a proven address.
            counselor = db.session.get(User, analysis.counselor_id) if analysis.counselor_id else None
            if counselor is None or counselor.email_verified_at is None:
                return
            to, status = counselor.email, analysis.status
            db.session.remove()
            if status == "success":
                email_service.send_counselor_analysis_ready(to)
            elif status in ("error", "timeout"):
                email_service.send_counselor_analysis_failed(to)
            return
```

(import `User` from `..models.user` if the module lacks it). In
`_run_analysis`, where it sets `analysis.status = "running"`, add on the next
line `analysis.started_at = datetime.utcnow()` (import `datetime` if absent).

- [ ] **Step 5: The reaper's clock**

In `backend/app/__init__.py`, `reap_stale_running` (import
`from sqlalchemy import and_, or_` inside the function, beside the model
import):

```python
    stale = (
        Analysis.query
        .filter(Analysis.status == "running")
        .filter(or_(
            Analysis.started_at < cutoff,
            # Rows that went running before the column existed.
            and_(Analysis.started_at.is_(None), Analysis.created_at < cutoff),
        ))
        .update({"status": "error"}, synchronize_session=False)
    )
```

and add to its docstring: "The clock is `started_at` (four-doors spec,
decision 47): a relaunch or an unlock re-runs a row whose `created_at` may be
days old, and the nightly `flask purge-expired` boots an app too."

- [ ] **Step 6: Run, then commit**

Run: `cd backend && python -m pytest tests/test_counselor_mails.py tests/test_stale_reaper.py tests/test_analysis_outcome_mail.py -q`, then `python -m pytest -q`.

```bash
git add backend/app backend/tests
git commit -m "feat(doors): the counselor hears when a report is ready; reaper keys on started_at

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 12: `flask purge-expired`

**Files:**
- Create: `backend/app/services/purge.py`, `backend/app/cli.py`, `scripts/neoori-purge.sh`
- Modify: `backend/app/__init__.py` (register the CLI in `create_app`)
- Test: `backend/tests/test_purge.py`

**Interfaces:**
- Produces: `purge.run(*, apply: bool, before_rollback: bool = False, now: datetime | None = None) -> dict[str, int]`
  with keys `held_drafts`, `anonymous`, `advisor` and, in daily mode,
  `run_log`; CLI `flask purge-expired [--dry-run]` and
  `flask purge-expired --before-rollback [--apply]`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_purge.py`:

```python
"""flask purge-expired (four-doors spec, decision 46)."""
from datetime import datetime, timedelta

from app.extensions import db
from app.models.analysis import Analysis
from app.models.counselor_note import CounselorNote
from app.models.price_feedback import BUCKETS, PriceFeedback
from app.models.run_log import RunLog
from app.services import purge
from tests.helpers_doors import counselor, user


def _ago(**delta):
    return datetime.utcnow() - timedelta(**delta)


def _row(**fields):
    row = Analysis(inputs={}, **({"status": "success"} | fields))
    db.session.add(row)
    db.session.commit()
    return row


def _hash(ch):
    return ch * 64


def test_it_takes_exactly_the_expired_kinds_and_nothing_else(app):
    c, u = counselor(), user()
    expired = [
        _row(status="draft", access_token_hash=_hash("a"), created_at=_ago(hours=49)),
        _row(door="anonymous", access_token_hash=_hash("b"), created_at=_ago(days=31)),
        _row(door="advisor", counselor_id=c.id, created_at=_ago(days=366)),
    ]
    kept = [
        _row(status="draft", access_token_hash=_hash("c"), created_at=_ago(hours=47)),
        _row(door="anonymous", access_token_hash=_hash("d"), created_at=_ago(days=29)),
        _row(door="anonymous", user_id=u.id, created_at=_ago(days=90)),      # claimed
        _row(door="legacy", created_at=_ago(days=400)),
        _row(door="account", user_id=u.id, created_at=_ago(days=400)),
        _row(status="draft", user_id=u.id, created_at=_ago(days=400)),       # owned draft
        _row(door="advisor", counselor_id=c.id, created_at=_ago(days=364)),
    ]
    db.session.add(CounselorNote(analysis_id=expired[2].id, counselor_id=c.id, body="n"))
    db.session.add(PriceFeedback(analysis_id=expired[1].id, bucket=BUCKETS[0]))
    db.session.add_all([RunLog(door="anonymous", created_at=_ago(days=3)), RunLog(door="anonymous")])
    db.session.commit()

    assert purge.run(apply=True) == {"held_drafts": 1, "anonymous": 1, "advisor": 1, "run_log": 1}
    assert {a.id for a in Analysis.query.all()} == {a.id for a in kept}
    assert CounselorNote.query.count() == 0 and PriceFeedback.query.count() == 0
    assert RunLog.query.count() == 1
    assert purge.run(apply=True) == {"held_drafts": 0, "anonymous": 0, "advisor": 0, "run_log": 0}


def test_a_dry_run_changes_nothing(app):
    _row(door="anonymous", access_token_hash=_hash("e"), created_at=_ago(days=31))
    assert purge.run(apply=False)["anonymous"] == 1
    assert Analysis.query.count() == 1


def test_before_rollback_takes_every_row_the_old_image_would_expose(app):
    c, u = counselor(), user()
    _row(door="advisor", counselor_id=c.id)
    _row(door="anonymous", access_token_hash=_hash("f"))
    _row(status="draft", access_token_hash=_hash("g"))
    claimed = _row(door="anonymous", user_id=u.id)
    legacy = _row(door="legacy")
    counts = purge.run(apply=True, before_rollback=True)
    assert counts == {"held_drafts": 1, "anonymous": 1, "advisor": 1}
    assert {a.id for a in Analysis.query.all()} == {claimed.id, legacy.id}


def test_the_command(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["purge-expired", "--dry-run"])
    assert result.exit_code == 0 and "dry run" in result.output
    result = runner.invoke(args=["purge-expired", "--before-rollback"])
    assert result.exit_code == 0 and "dry run" in result.output
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_purge.py -q`
Expected: FAIL — `ImportError: cannot import name 'purge'`.

- [ ] **Step 3: Write the purge**

`backend/app/services/purge.py`:

```python
"""flask purge-expired (four-doors spec, decision 46).

Three kinds of rows live on a clock instead of an account, and run_log is a
counter. Nothing else is ever selected: a legacy row, an owned row or a
claimed one is never touched by the daily run.

The rollback mode is the one exception, and it is not a clock: before
downgrading past the four-doors migration, every row the previous image would
serve to anyone holding its id has to go (DOCKER.md, « Rollback »).
"""
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import and_

from ..extensions import db
from ..models.analysis import Analysis
from ..models.counselor_note import CounselorNote
from ..models.price_feedback import PriceFeedback
from ..models.run_log import RunLog
from . import doors

RUN_LOG_DAYS = 2


def _held():
    return and_(
        Analysis.status == "draft",
        Analysis.user_id.is_(None),
        Analysis.access_token_hash.isnot(None),
    )


def _unclaimed_anonymous():
    return and_(Analysis.door == doors.ANONYMOUS, Analysis.user_id.is_(None))


def _ids(query) -> list[str]:
    return [row.id for row in query.with_entities(Analysis.id).all()]


def _selection(now: datetime, before_rollback: bool) -> dict[str, list[str]]:
    if before_rollback:
        return {
            "held_drafts": _ids(Analysis.query.filter(_held())),
            "anonymous": _ids(Analysis.query.filter(_unclaimed_anonymous())),
            "advisor": _ids(Analysis.query.filter(Analysis.door == doors.ADVISOR)),
        }
    cfg = current_app.config
    return {
        "held_drafts": _ids(Analysis.query.filter(
            _held(), Analysis.created_at < now - timedelta(hours=cfg["HELD_DRAFT_RETENTION_HOURS"]),
        )),
        "anonymous": _ids(Analysis.query.filter(
            _unclaimed_anonymous(),
            Analysis.created_at < now - timedelta(days=cfg["ANONYMOUS_RETENTION_DAYS"]),
        )),
        "advisor": _ids(Analysis.query.filter(
            Analysis.door == doors.ADVISOR,
            Analysis.created_at < now - timedelta(days=cfg["ADVISOR_RETENTION_DAYS"]),
        )),
    }


def _delete(ids: list[str]) -> None:
    """Notes, price feedback, then the rows: counselor_notes' foreign key has
    no ON DELETE, and price_feedback's cascade is not relied upon."""
    if not ids:
        return
    CounselorNote.query.filter(CounselorNote.analysis_id.in_(ids)).delete(synchronize_session=False)
    PriceFeedback.query.filter(PriceFeedback.analysis_id.in_(ids)).delete(synchronize_session=False)
    Analysis.query.filter(Analysis.id.in_(ids)).delete(synchronize_session=False)


def run(*, apply: bool, before_rollback: bool = False, now: datetime | None = None) -> dict[str, int]:
    """Count, and with apply=True delete, in one transaction. Returns the
    counts per kind."""
    now = now or datetime.utcnow()
    selection = _selection(now, before_rollback)
    counts = {kind: len(ids) for kind, ids in selection.items()}
    old_runs = None
    if not before_rollback:
        old_runs = RunLog.query.filter(RunLog.created_at < now - timedelta(days=RUN_LOG_DAYS))
        counts["run_log"] = old_runs.count()
    if apply:
        try:
            for ids in selection.values():
                _delete(ids)
            if old_runs is not None:
                old_runs.delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    return counts
```

`backend/app/cli.py`:

```python
"""Flask CLI commands (`flask <name>` inside the backend container)."""
import click


def register(app) -> None:
    @app.cli.command("purge-expired")
    @click.option("--dry-run", is_flag=True, help="Count only; delete nothing.")
    @click.option("--before-rollback", is_flag=True,
                  help="Every advisor row, unclaimed anonymous row and held draft, whatever its age.")
    @click.option("--apply", "apply_", is_flag=True,
                  help="With --before-rollback: delete (it only counts without it).")
    def purge_expired(dry_run, before_rollback, apply_):
        """Daily: delete the rows past their retention (four-doors spec, decision 46)."""
        from .services import purge

        apply = apply_ if before_rollback else not dry_run
        counts = purge.run(apply=apply, before_rollback=before_rollback)
        for kind, n in counts.items():
            click.echo(f"{kind}: {n}")
        click.echo("deleted" if apply else "dry run — nothing deleted")
```

In `backend/app/__init__.py`, inside `create_app` after the blueprints:

```python
    from . import cli
    cli.register(app)
```

`scripts/neoori-purge.sh` (copy the header style of `scripts/neoori-backup.sh`):

```bash
#!/usr/bin/env bash
# Daily purge of the rows that live on a clock (four-doors spec, decision 46):
# held drafts after 48 h, unclaimed no-login reports after 30 days, advisor
# reports after 12 months, run_log after 2 days.
# Installed at /usr/local/bin/neoori-purge.sh, cron `30 3 * * *` (after the
# 03:00 backup), log /var/log/neoori-purge.log. See DOCKER.md, « Purge ».
set -euo pipefail
cd /srv/neoori
{
  echo "[$(date -u +%FT%TZ)] flask purge-expired"
  docker compose -f docker-compose.prod.yml exec -T backend flask purge-expired
} >> /var/log/neoori-purge.log 2>&1
```

`chmod +x scripts/neoori-purge.sh`.

- [ ] **Step 4: Run, then commit**

Run: `cd backend && python -m pytest tests/test_purge.py -q`, then `python -m pytest -q`.
Then once against MySQL: `docker compose exec backend flask purge-expired --dry-run`
— expected: four `kind: n` lines and « dry run — nothing deleted ».

```bash
git add backend/app/services/purge.py backend/app/cli.py backend/app/__init__.py scripts/neoori-purge.sh backend/tests/test_purge.py
git commit -m "feat(doors): flask purge-expired — held drafts, no-login and advisor reports, run log

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 13: nginx limits, path-only access logs, env example

**Files:**
- Modify: `nginx/templates-https/default.conf.template`,
  `nginx/templates-http/default.conf.template`, `nginx/dev.conf`
- Modify: `backend/entrypoint.sh`
- Modify: `.env.example`, `backend/.env.example`

- [ ] **Step 1: The zones and the log format (all three nginx files)**

After the `auth_oauth` `limit_req_zone` line and before `limit_req_status 429;`:

```nginx
# Four-doors spec, decision 39: what the open form exposes, POST only (the
# polling GETs are never limited). Sized for a workshop room behind one
# address: fifteen people, about four requests each, within minutes.
map "$request_method:$uri" $analyses_key {
    ~^POST:/api/(analyses(/draft)?|upload/(cv|projet))/?$  $binary_remote_addr;
    default "";
}
map "$request_method:$uri" $codes_key {
    ~^POST:/api/(codes/check|analyses/[^/]+/unlock|voyage/unlock)/?$  $binary_remote_addr;
    default "";
}
limit_req_zone $analyses_key zone=analyses:10m rate=10r/m;
limit_req_zone $codes_key    zone=codes:10m    rate=10r/m;

# Four-doors spec, decision 42: log the path, never the query string or the
# Referer. Verification and reset tokens, `next` paths and Stripe session ids
# travel in query strings, and the Referer repeats them.
log_format neoori_paths '$remote_addr [$time_local] "$request_method $uri" '
                        '$status $body_bytes_sent $request_time';
```

Inside `location /api/`, after the two existing `limit_req` lines:

```nginx
        limit_req zone=analyses burst=40 nodelay;
        limit_req zone=codes    burst=20 nodelay;
```

In **every** `server { … }` block of each file, as its first directive after
`server_name` (or `listen` where there is no `server_name`):

```nginx
    access_log /var/log/nginx/access.log neoori_paths;
```

(A server-level `access_log` replaces the http-level `main` one; an http-level
line in this included file would add a second log instead of replacing it.)

- [ ] **Step 2: gunicorn's format**

In `backend/entrypoint.sh`, after `--access-logfile - \`:

```sh
    --access-logformat '%(h)s %(t)s "%(m)s %(U)s" %(s)s %(b)s %(L)s' \
```

with a comment line above the `exec gunicorn` block:
`# Access log: the path only, no query string, no Referer (four-doors spec, decision 42).`

- [ ] **Step 3: The env examples**

In `.env.example` and `backend/.env.example`: delete the `FORCE_ANALYSIS_TIER`
line and its comment; set `MODEL_FREE=anthropic/claude-haiku-4-5-20251001`
(the `gemini/…` value would fail the Anthropic call); append:

```
# Four-doors spec — daily caps, input caps, retentions (defaults shown)
# ANONYMOUS_RUNS_PER_DAY=200
# FREE_RUNS_PER_ACCOUNT_PER_DAY=5
# CV_TEXT_MAX=40000
# CIBLE_MAX=10000
# ANONYMOUS_RETENTION_DAYS=30
# ADVISOR_RETENTION_DAYS=365
# HELD_DRAFT_RETENTION_HOURS=48
```

- [ ] **Step 4: Verify in the local stack**

`nginx/dev.conf` is a single-file bind mount: an editor that replaces the file
leaves nginx on the old inode, so recreate rather than reload.

```bash
docker compose up -d --force-recreate nginx backend
docker compose exec nginx nginx -t
# Expected: "syntax is ok" / "test is successful"

curl -s -o /dev/null 'http://localhost:8080/api/auth/providers?secret=PROBE123'
docker compose logs --tail=50 nginx backend | grep -c PROBE123
# Expected: 0

for i in $(seq 1 30); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8080/api/codes/check \
       -H 'Content-Type: application/json' -d '{"code":"x"}'
done | sort | uniq -c
# Expected: about 21 × 400, then 429s

for i in $(seq 1 30); do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/api/analyses/by-token
done | sort | uniq -c
# Expected: 30 × 404 — GETs are never limited
```

Render the https template once to check it parses outside the dev stack:

```bash
docker run --rm -e DOMAIN=example.test -v "$PWD/nginx/templates-https:/etc/nginx/templates:ro" \
  --add-host backend:127.0.0.1 --add-host frontend:127.0.0.1 nginx:1.29-alpine \
  sh -c 'envsubst "\$DOMAIN" < /etc/nginx/templates/default.conf.template > /tmp/d.conf && grep -c neoori_paths /tmp/d.conf'
# Expected: a count ≥ 4 (the format line plus one per server block)
```

- [ ] **Step 5: Commit**

```bash
git add nginx backend/entrypoint.sh .env.example backend/.env.example
git commit -m "feat(doors): per-address limits on the open endpoints; path-only access logs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
## Task 14: Frontend groundwork — types, api, proxy, shared report pieces; the share link goes

No new page yet. The pieces later tasks reuse, and the removals that would
otherwise break the type check (`share_token`, `counselor_keys`).

**Files:**
- Modify: `frontend/src/types/index.ts`, `frontend/src/lib/api.ts`,
  `frontend/src/proxy.ts`, `frontend/src/components/report/ReportSection.tsx`,
  `frontend/src/components/report/PriceProbe.tsx`,
  `frontend/src/app/analyse/[id]/rapport/page.tsx`,
  `frontend/src/app/analyse/en-cours/[id]/page.tsx`,
  `frontend/src/app/espace/page.tsx`, `frontend/src/app/c/[token]/page.tsx`
- Create: `frontend/src/lib/held.ts`,
  `frontend/src/components/report/ReportDocument.tsx`,
  `frontend/src/components/analyse/RunProgress.tsx`

**Interfaces:**
- Produces:
  - `type Door`; `Analysis.door`, `Analysis.access_expires_at`;
    `CounselorAnalysisRow`, `AdminCodeRow`; `Beneficiaire.nom`,
    `.analysis_id`; `CounselorCodeRow.uses_by_kind`.
  - `api.*(…, { token })` sends `X-Analysis-Token`.
  - `held.saveDraft(inputs)`, `held.get()`, `held.claim()`, `held.hold(token)`,
    `held.byToken(token)`, `held.remove(id, token)`, `tokenFromHash()`.
  - `<ReportDocument analysis loading unlockHref>{children}</ReportDocument>`,
    `isPaidReport(analysis)`.
  - `<RunProgress load onDone mailed onRestart />`.
  - `<PriceProbe analysisId token? />`.

- [ ] **Step 1: Types**

In `frontend/src/types/index.ts`:

- Add, above `interface Analysis`:

```ts
/** Which door an analysis came through (four-doors spec). "legacy" marks the
 *  ownerless rows written before accounts were required. */
export type Door = "account" | "promo" | "advisor" | "anonymous" | "legacy"
```

- In `interface Analysis`: delete `counselor_keys` and `share_token`; add

```ts
  door?: Door | null
  /** When an unclaimed no-login report's private link stops working. */
  access_expires_at?: string | null
```

- `interface Beneficiaire`: replace its doc comment with
  `/** Who used my codes — and, for an advisor-door analysis, the report's id
  (four-doors spec, ruling 2). */` and add `nom: string | null` and
  `analysis_id: string | null`.
- `interface CounselorCodeRow`: add
  `uses_by_kind: { analysis: number; voyage: number }`.
- Append:

```ts
/** An advisor-door report, as the counselor's list shows it. */
export interface CounselorAnalysisRow {
  id: string
  prenom: string | null
  nom: string | null
  code_label: string | null
  status: AnalysisStatus
  created_at: string
}

/** A code as the admin's table shows it: promo (no owner) or conseiller. */
export interface AdminCodeRow {
  id: string
  code: string
  label: string
  is_active: boolean
  owner_id: string | null
  max_uses: number | null
  expires_at: string | null
  revoked_at: string | null
  created_at: string
  kind: "promo" | "conseiller"
  uses_by_kind: { analysis: number; voyage: number }
}
```

- [ ] **Step 2: `api.ts` — the token header, and no redirect off a public page**

In `frontend/src/lib/api.ts`:

```ts
type ApiOptions = RequestInit & {
  skipRedirect?: boolean
  /** A no-login report's key, sent as X-Analysis-Token (four-doors spec,
   *  decision 30) — never in a URL, so never in an access log. */
  token?: string
}

/** Pages a signed-out visitor uses on purpose: a 401 there is an answer for
 *  the page to show, never a reason to leave for /connexion. */
const PUBLIC_PAGES = ["/analyse/nouveau", "/analyse/envoyee", "/rapport"]
```

In `request()`: `const { skipRedirect, token, ...init } = options`; build the
headers with the token in both branches:

```ts
  const tokenHeader: Record<string, string> = token ? { "X-Analysis-Token": token } : {}
```

```ts
      headers: isFormData
        ? { ...(init.headers as Record<string, string>), ...tokenHeader }
        : { "Content-Type": "application/json", ...(init.headers as Record<string, string>), ...tokenHeader },
```

and the 401 guard:

```ts
  if (
    res.status === 401 && !skipRedirect && typeof window !== "undefined"
    && !PUBLIC_PAGES.includes(window.location.pathname)
  ) {
```

- [ ] **Step 3: `proxy.ts` — the form is public**

In `frontend/src/proxy.ts`, below `SIGNUP_FIRST`:

```ts
/** Open to signed-out visitors inside /analyse (four-doors spec, ruling 1):
 *  the form, the advisor-door confirmation, and /analyse itself (a redirect
 *  to the form). Exact paths: /analyse/<id>/* stays the owner's. */
const PUBLIC = ["/analyse", "/analyse/nouveau", "/analyse/envoyee"]
```

and first thing in `proxy()` after reading `pathname`:

```ts
  if (PUBLIC.includes(pathname)) return NextResponse.next()
```

Update the comment on `PROTECTED` ("Routes that need an account") and on
`SIGNUP_FIRST` (it now applies to the report, waiting and unlock pages).
`/rapport` is outside every protected prefix: nothing to add.

- [ ] **Step 4: `lib/held.ts`**

```ts
import { api } from "./api"
import type { Analysis, AnalysisInputs } from "@/types"

export type FormInputs = Pick<AnalysisInputs, "cv_text" | "cible_visee" | "_chemin">

/** A no-login report's key lives in the URL fragment (four-doors spec,
 *  decision 30): a fragment is never sent to a server and never appears in
 *  a Referer. */
export function tokenFromHash(): string | null {
  const token = window.location.hash.replace(/^#/, "")
  return token || null
}

/** The signed-out draft and the no-login report. The draft's key never
 *  reaches this code: it lives in an HttpOnly cookie the server sets. */
export const held = {
  saveDraft: (inputs: FormInputs) =>
    api.post<{ analysis: Analysis }>("/analyses/draft", { inputs }, { skipRedirect: true }),
  get: () => api.get<{ analysis: Analysis }>("/analyses/held", { skipRedirect: true }),
  claim: () => api.post<{ analysis: Analysis }>("/analyses/claim", undefined, { skipRedirect: true }),
  hold: (token: string) => api.post<Record<string, never>>("/analyses/hold", undefined, { token, skipRedirect: true }),
  byToken: (token: string) =>
    api.get<{ analysis: Analysis }>("/analyses/by-token", { token, skipRedirect: true }),
  remove: (id: string, token: string) => api.delete(`/analyses/${id}`, { token, skipRedirect: true }),
}
```

- [ ] **Step 5: `ReportSection` and `PriceProbe`**

- `components/report/ReportSection.tsx`: delete the `counselor` prop (its
  destructured default, its type line) and render the badge as
  `{paid && <Badge …>plan payant</Badge>}`.
- `components/report/PriceProbe.tsx`: the signature becomes
  `export function PriceProbe({ analysisId, token }: { analysisId: string; token?: string })`
  and its post gains `{ token, skipRedirect: Boolean(token) }` as third
  argument.

- [ ] **Step 6: `ReportDocument` — the A4 report, extracted**

`frontend/src/components/report/ReportDocument.tsx` — the JSX is the
`report-shell` block of today's `app/analyse/[id]/rapport/page.tsx`, moved
unchanged except for the props:

```tsx
"use client"

import type { ReactNode } from "react"
import { Logo } from "@/components/brand/Logo"
import { Skeleton } from "@/components/ui/skeleton"
import { ReportSection } from "@/components/report/ReportSection"
import type { Analysis } from "@/types"

/** "Paid" is a property of what was generated, not of how it was paid for: a
 *  promo code, a Stripe payment and the advisor door produce the same report. */
export function isPaidReport(analysis: Analysis | null): boolean {
  const output = analysis?.output ?? {}
  return (
    analysis?.unlock_method != null ||
    (analysis?.sections_meta ?? []).some((m) => m.key in output && !m.tiers.includes("free"))
  )
}

/** The A4 report — header band, sections, page footer. One rendering for the
 *  owner's page, the no-login page and the counselor's page (four-doors spec). */
export function ReportDocument({
  analysis,
  loading,
  unlockHref,
  children,
}: {
  analysis: Analysis | null
  loading: boolean
  /** Where a locked section's « Débloquer → » points; null shows no link. */
  unlockHref: string | null
  /** Under the sections, above the page footer: an unlock offer, the price probe. */
  children?: ReactNode
}) {
  const output = analysis?.output ?? {}
  const hasOutput = Object.keys(output).length > 0
  // Order and titles come from the backend section registry. Never sort output
  // keys here.
  const meta = analysis?.sections_meta ?? []
  const generated = meta.filter((m) => m.key in output)
  // While loading, a short skeleton list (no phantom locked paid sections).
  const placeholder = meta.filter((m) => m.tiers.includes("free"))
  const isPaid = isPaidReport(analysis)
  const sections = hasOutput ? generated : placeholder
  const monthLabel = new Date(analysis?.created_at ?? "").toLocaleDateString("fr-FR", { month: "long", year: "numeric" })
  const name = [analysis?.inputs?.prenom, (analysis?.inputs?.nom ?? "").toUpperCase()].filter(Boolean).join(" ")

  return (
    <div className="report-shell">
      <div className="report-rule" />

      {/* Navy header band */}
      <div className="bg-navy px-8 pb-6 pt-6 text-white">
        <Logo tone="light" className="text-base" />
        {loading ? (
          <div className="mt-3 space-y-2">
            <Skeleton className="h-7 w-48 bg-white/20" />
            <Skeleton className="h-4 w-64 bg-white/10" />
          </div>
        ) : (
          <>
            <h1 className="mt-3 font-display text-2xl font-extrabold leading-tight text-white">{name || "—"}</h1>
            <p className="mt-1 text-sm italic text-peach">
              {`Cible : ${analysis?.inputs?.cible_visee?.slice(0, 60) ?? "—"} · ${monthLabel}`}
            </p>
          </>
        )}
      </div>

      <div className="px-8 py-7">
        {sections.map((m) => {
          const isPaidSection = !m.tiers.includes("free")
          const section = output[m.key]
          return (
            <ReportSection
              key={m.key}
              n={m.key}
              title={section?.title ?? m.title}
              section={section}
              render={m.render}
              paid={isPaidSection}
              locked={isPaidSection && !isPaid}
              unlockHref={unlockHref ?? undefined}
            />
          )
        })}

        {children}

        <div className="mt-8 flex items-center justify-between border-t border-border pt-4">
          <span className="font-mono text-[10px] text-muted-foreground">neoori · confidentiel</span>
          <span className="font-mono text-[10px] text-muted-foreground">{loading ? "" : monthLabel}</span>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 7: The owner's report page uses it; the counselor tab goes**

Rewrite `frontend/src/app/analyse/[id]/rapport/page.tsx`: keep the imports it
still needs, the `autoPrint` effect and the loading effect (title setting
included), and replace everything from the `share` function to the end:

```tsx
export default function RapportPage() {
  const { id } = useParams<{ id: string }>()
  const searchParams = useSearchParams()
  const autoPrint = searchParams.get("print") === "1"
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [loading, setLoading] = useState(true)

  /* … the autoPrint effect and the loading effect, unchanged … */

  const hasOutput = Object.keys(analysis?.output ?? {}).length > 0
  const isPaid = isPaidReport(analysis)

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />

      <div className="no-print sticky top-16 z-40 flex flex-wrap items-center justify-center gap-2 border-b border-border bg-secondary/95 py-3 backdrop-blur-sm">
        <Button variant="outline" size="sm" disabled={loading} onClick={() => setTimeout(() => window.print(), 50)}>
          <Printer className="size-3.5" /> PDF
        </Button>
      </div>

      <div className="px-4 py-8">
        <ReportDocument analysis={analysis} loading={loading} unlockHref={`/analyse/${id}/debloquer`}>
          {hasOutput && !isPaid && (
            <div className="no-print mt-2 flex flex-col items-start justify-between gap-4 rounded-xl bg-brand-gradient p-5 text-white sm:flex-row sm:items-center">
              <div>
                <p className="font-display font-bold">Débloquez les 6 sections restantes</p>
                <p className="mt-0.5 text-sm opacity-90">préconisations · réécriture · synthèse · pistes d’évolution · CV retravaillé</p>
              </div>
              <Button render={<Link href={`/analyse/${id}/debloquer`} />} size="lg" className="shrink-0 bg-white text-orange-dark hover:bg-white/90">
                Passer en payant — 9 €
              </Button>
            </div>
          )}
          {/* Below the unlock CTA on purpose: asking what someone would pay
              before offering them the thing reads as a negotiation. */}
          {hasOutput && !isPaid && <PriceProbe analysisId={id} />}
        </ReportDocument>
      </div>
    </div>
  )
}
```

Imports: drop `Badge`, `Tabs*`, `ReportSection`, `copyToClipboard`, `Share2`,
`Check`, `Logo`, `normalizeParcours`, `Skeleton`; add
`import { ReportDocument, isPaidReport } from "@/components/report/ReportDocument"`.

- [ ] **Step 8: `RunProgress` — the waiting screen, extracted**

Create `frontend/src/components/analyse/RunProgress.tsx` from
`app/analyse/en-cours/[id]/page.tsx`: move `STEPS`, the constants,
`DURATION_HINT`, `StepState`, all state, the polling effect and the JSX into

```tsx
export function RunProgress({
  load,
  onDone,
  mailed,
  onRestart,
}: {
  /** Fetch the row once; RunProgress polls it. */
  load: () => Promise<Analysis>
  /** Called once, on success, with the finished row. */
  onDone: (analysis: Analysis) => void
  /** An account is mailed when the run ends; a no-login run is not. */
  mailed: boolean
  /** « Nouvelle analyse » after a failure. */
  onRestart: () => void
}) {
```

with these changes inside:

- Keep `load` and `onDone` in refs so the polling effect runs once:
  `const loadRef = useRef(load); const doneRef = useRef(onDone)` and the
  effect's dependency list is `[]`.
- `const res = await api.get(...)` becomes `const analysis = await loadRef.current()`;
  read `status`, `progress`, `inputs` from `analysis`.
- On success: `schedule(800, () => doneRef.current(analysis))`.
- The error card's button calls `onRestart`.
- Text that promised a mail depends on `mailed`:
  - stalled subtitle: `mailed ? "Vous recevrez un email dès qu’elle sera prête." : "Gardez ce lien : le rapport s’affichera ici dès qu’il sera prêt."`
  - stalled card: render the « Retour à mon espace » button only when
    `mailed`; otherwise render nothing in its place.
  - the line under the bar: `mailed ? "Le rapport s’affiche ici automatiquement. Vous recevrez un email quand il sera prêt — vous pouvez fermer cette page." : "Le rapport s’affiche ici automatiquement. Gardez ce lien pour le retrouver."`
- `useRouter` is no longer used inside (« Retour à mon espace » becomes
  `<Button render={<Link href="/espace" />} …>`).

Then `app/analyse/en-cours/[id]/page.tsx` becomes:

```tsx
"use client"

import { useParams, useRouter } from "next/navigation"
import { RunProgress } from "@/components/analyse/RunProgress"
import { api } from "@/lib/api"
import type { Analysis } from "@/types"

export default function EnCoursPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  return (
    <RunProgress
      load={() => api.get<{ analysis: Analysis }>(`/analyses/${id}`).then((r) => r.analysis)}
      onDone={() => router.push(`/analyse/${id}/rapport`)}
      mailed
      onRestart={() => router.push("/analyse/nouveau")}
    />
  )
}
```

- [ ] **Step 9: `/espace` loses the analysis share link**

In `frontend/src/app/espace/page.tsx`: delete `copiedToken`, `origin` (and its
effect), `copyShare`, `shareable`, the per-analysis copy-link button
(`{a.share_token && (…)}`), and the bottom strip's « Partagez avec votre
conseiller » card. Make the bottom strip's grid `grid-cols-1`. Keep the
voyage's « Lien pour mon conseiller » (it reads `voyage.share_token`, a
different object). Remove imports lint reports unused.

- [ ] **Step 10: `/c/<token>` becomes a notice**

Replace `frontend/src/app/c/[token]/page.tsx`:

```tsx
import Link from "next/link"
import { Logo } from "@/components/brand/Logo"
import { Button } from "@/components/ui/button"

/** The retired analysis share link (four-doors spec, decision 43). Counselors
 *  still hold old links, so a notice rather than a 404 that looks like a bug. */
export default function LienConseillerRetirePage() {
  return (
    <div className="bg-mesh flex min-h-screen items-center justify-center px-5 py-12">
      <div className="w-full max-w-md text-center">
        <Logo className="mx-auto text-2xl" />
        <h1 className="mt-10 font-display text-2xl font-bold text-navy">Ce lien n’est plus actif.</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Les conseillers reçoivent désormais l’analyse complète dans leur espace, lorsque leur code est utilisé.
        </p>
        <Button render={<Link href="/" />} variant="outline" size="lg" className="mt-6">
          Retour à l’accueil
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 11: Check, then commit**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected: no error. `grep -rn "share_token\|counselor_keys\|/c/\${" frontend/src/app frontend/src/components | grep -v voyage`
— expected: no analysis share link left (the voyage's stays).

Manual (local stack, signed in): open an existing report — the header, the
sections and the 9 € offer render as before, there is no « Vue conseiller »
tab; launch a run from the old form — the waiting screen behaves as before;
open `/c/anything` — the notice.

```bash
git add frontend/src
git commit -m "refactor(frontend): shared report and waiting pieces; the analysis share link retires

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 15: The doors panel, the open form, `/analyse/envoyee`

**Files:**
- Create: `frontend/src/components/analyse/DoorsPanel.tsx`,
  `frontend/src/app/analyse/envoyee/page.tsx`
- Modify: `frontend/src/app/analyse/nouveau/page.tsx`

**Interfaces:**
- Consumes: `held`, `FormInputs` (Task 14); `POST /api/analyses/`,
  `POST /api/codes/check` (Tasks 7, 10).
- Produces: `<DoorsPanel inputs draftId initialDoor onClose />`,
  `type DoorId = "account" | "advisor" | "promo" | "anonymous"`.

- [ ] **Step 1: `DoorsPanel`**

`frontend/src/components/analyse/DoorsPanel.tsx`:

```tsx
"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowRight, X } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { held, type FormInputs } from "@/lib/held"
import { cn } from "@/lib/utils"
import type { Analysis } from "@/types"

export type DoorId = "account" | "advisor" | "promo" | "anonymous"

/** The promo code survives the sign-in round trip in this tab only — it
 *  never rides in a URL or a mail (four-doors spec, decision 34). */
const PROMO_KEY = "neoori_promo"

const DOORS: { id: DoorId; title: string }[] = [
  { id: "account", title: "Avec mon compte" },
  { id: "advisor", title: "J'ai un code conseiller" },
  { id: "promo", title: "J'ai un code promo" },
  { id: "anonymous", title: "Sans compte" },
]

const WRONG_FOR_PROMO = "Ce code est un code conseiller : choisissez « J'ai un code conseiller »."
const THROTTLED = "Trop de tentatives — réessayez dans une minute."

function readPromo(): string {
  try { return sessionStorage.getItem(PROMO_KEY) ?? "" } catch { return "" }
}
function writePromo(value: string | null) {
  try { value === null ? sessionStorage.removeItem(PROMO_KEY) : sessionStorage.setItem(PROMO_KEY, value) } catch { /* private mode */ }
}

function Consent({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-start gap-2.5 text-xs leading-relaxed text-muted-foreground">
      <input
        type="checkbox"
        className="mt-0.5 size-4 shrink-0 rounded border-input accent-[var(--primary)]"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        J’accepte les{" "}
        <Link href="/cgv" target="_blank" className="text-navy underline underline-offset-2">CGV</Link>{" "}
        et la{" "}
        <Link href="/confidentialite" target="_blank" className="text-navy underline underline-offset-2">politique de confidentialité</Link>.
      </span>
    </label>
  )
}

/** The four doors behind « Générer mon analyse » (four-doors spec). The
 *  server decides each door's tier and recipient; this only collects what
 *  the door needs and goes where the door leads. */
export function DoorsPanel({
  inputs,
  draftId,
  initialDoor,
  onClose,
}: {
  /** The form's current values, read at the moment a door is used. */
  inputs: () => FormInputs
  /** The signed-in caller's draft, promoted by the submit. */
  draftId: string | null
  initialDoor: DoorId | null
  onClose: () => void
}) {
  const router = useRouter()
  const { user } = useAuth()
  const signedIn = user !== null
  const doors = DOORS.filter((d) => !(signedIn && d.id === "anonymous"))

  const [open, setOpen] = useState<DoorId | null>(initialDoor)
  const [prenom, setPrenom] = useState("")
  const [nom, setNom] = useState("")
  const [code, setCode] = useState(readPromo)
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [retried, setRetried] = useState(false)

  const choose = (id: DoorId) => { setOpen(id); setError(null) }

  /** Sign in, then come back to the form with the draft held by the cookie. */
  const roundTrip = async (door: "account" | "promo") => {
    await held.saveDraft(inputs())
    const back = `/analyse/nouveau?reprendre=${door === "promo" ? "promo" : "compte"}`
    router.push(`/inscription?redirect=${encodeURIComponent(back)}`)
  }

  const submit = (door: DoorId, extra: Record<string, unknown> = {}) =>
    api.post<{ analysis?: Analysis; access_token?: string }>(
      "/analyses/",
      { inputs: inputs(), door, draft_id: draftId ?? undefined, ...extra },
      { skipRedirect: true },
    )

  const fail = (e: unknown) => {
    if (!(e instanceof ApiError)) { setError("Erreur inattendue."); return }
    const other = e.body?.door
    if (e.status === 409 && (other === "promo" || other === "advisor")) setOpen(other)
    setError(e.status === 429 && !e.body?.error ? THROTTLED : e.message)
  }

  const go = async () => {
    if (!open) return
    setBusy(true)
    setError(null)
    try {
      if (open === "account") {
        if (!signedIn) return await roundTrip("account")
        const res = await submit("account")
        router.push(`/analyse/en-cours/${res.analysis!.id}`)
      } else if (open === "promo") {
        const check = await api.post<{ kind: "promo" | "conseiller" }>("/codes/check", { code }, { skipRedirect: true })
        if (check.kind !== "promo") { setOpen("advisor"); setError(WRONG_FOR_PROMO); return }
        if (!signedIn) { writePromo(code); return await roundTrip("promo") }
        const res = await submit("promo", { code })
        writePromo(null)
        router.push(`/analyse/en-cours/${res.analysis!.id}`)
      } else if (open === "advisor") {
        await submit("advisor", { code, prenom, nom, consent })
        router.push("/analyse/envoyee")
      } else {
        const res = await submit("anonymous", { consent })
        router.push(`/rapport#${res.access_token}`)
      }
    } catch (e) {
      // A session that lapsed between the page load and the click: sign in
      // again, once (four-doors spec, decision 38).
      if (e instanceof ApiError && e.status === 401 && (open === "account" || open === "promo") && !retried) {
        setRetried(true)
        try { await roundTrip(open) } catch (again) { fail(again) }
      } else {
        fail(e)
      }
    } finally {
      setBusy(false)
    }
  }

  const field = (
    id: string, label: string, value: string, set: (v: string) => void,
    extra: Partial<React.ComponentProps<typeof Input>> = {},
  ) => (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} className="h-10" value={value} onChange={(e) => set(e.target.value)} disabled={busy} {...extra} />
    </div>
  )

  const body = (id: DoorId) => {
    switch (id) {
      case "account":
        return (
          <>
            <p className="text-sm text-muted-foreground">
              Version gratuite : les trois premières sections et le verdict, gardés dans votre espace. Le rapport complet reste disponible à 9 €.
            </p>
            <Button onClick={go} disabled={busy} size="lg">
              {signedIn ? "Lancer la version gratuite" : "Créer un compte ou me connecter"} <ArrowRight />
            </Button>
          </>
        )
      case "advisor":
        return (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {field("door-prenom", "Prénom", prenom, setPrenom, { maxLength: 80, autoComplete: "given-name" })}
              {field("door-nom", "Nom", nom, setNom, { maxLength: 80, autoComplete: "family-name" })}
            </div>
            {field("door-code-conseiller", "Code", code, setCode, { autoComplete: "off", placeholder: "ex. A1B2C3D4" })}
            <p className="rounded-lg bg-peach-soft p-3 text-xs leading-relaxed text-navy">
              Le rapport complet sera envoyé à votre conseiller, pas à vous : vous n'en recevrez pas de copie. Votre conseiller pourra vous le présenter ou vous le transmettre.
            </p>
            <Consent checked={consent} onChange={setConsent} />
            <Button onClick={go} size="lg" disabled={busy || !consent || !prenom.trim() || !nom.trim() || !code.trim()}>
              Envoyer à mon conseiller <ArrowRight />
            </Button>
          </>
        )
      case "promo":
        return (
          <>
            <p className="text-sm text-muted-foreground">Le rapport complet, offert. Un compte est nécessaire pour le recevoir.</p>
            {field("door-code-promo", "Code", code, setCode, { autoComplete: "off", placeholder: "ex. A1B2C3D4" })}
            <Button onClick={go} size="lg" disabled={busy || !code.trim()}>
              {signedIn ? "Lancer l’analyse complète" : "Continuer"} <ArrowRight />
            </Button>
          </>
        )
      case "anonymous":
        return (
          <>
            <p className="text-sm text-muted-foreground">
              Version gratuite, accessible par un lien privé pendant 30 jours. Sans compte, nous ne pourrons pas vous renvoyer ce lien.
            </p>
            <Consent checked={consent} onChange={setConsent} />
            <Button onClick={go} size="lg" disabled={busy || !consent}>
              Lancer sans compte <ArrowRight />
            </Button>
          </>
        )
    }
  }

  return (
    <section aria-labelledby="doors-title" className="rounded-2xl bg-card p-5 shadow-soft ring-1 ring-foreground/10">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 id="doors-title" className="font-display text-lg font-bold text-navy">Comment voulez-vous continuer ?</h2>
        <Button variant="ghost" size="icon-sm" aria-label="Fermer" onClick={onClose}><X className="size-4" /></Button>
      </div>
      {error && <Alert variant="destructive" className="mb-4"><AlertDescription>{error}</AlertDescription></Alert>}
      <div className="space-y-3">
        {doors.map((d) => (
          <div key={d.id} className={cn("rounded-xl border", open === d.id ? "border-navy" : "border-border")}>
            <button
              type="button"
              aria-expanded={open === d.id}
              onClick={() => choose(d.id)}
              className="w-full px-4 py-3 text-left text-sm font-semibold text-navy"
            >
              {d.title}
            </button>
            {open === d.id && <div className="space-y-3 border-t border-border px-4 py-4">{body(d.id)}</div>}
          </div>
        ))}
      </div>
    </section>
  )
}
```

- [ ] **Step 2: The form opens to everyone and leads to the panel**

In `frontend/src/app/analyse/nouveau/page.tsx`:

1. Imports: drop `useRequireSession`; add
   `import { DoorsPanel, type DoorId } from "@/components/analyse/DoorsPanel"`
   and `import { held } from "@/lib/held"`.
2. Delete `canPremium`, `submitting` and the old `onSubmit`. Replace
   `const ready = useRequireSession()` with `const ready = !authLoading`.
3. Add state and the submit that opens the panel:

```tsx
  const [panelOpen, setPanelOpen] = useState(false)
  const [initialDoor, setInitialDoor] = useState<DoorId | null>(null)
  const [resumeNotice, setResumeNotice] = useState<string | null>(null)

  // Validation passed: the doors decide what happens next (four-doors spec).
  const onSubmit = () => {
    setSubmitError(null)
    setPanelOpen(true)
  }
```

4. The return from a round trip:

```tsx
  // Back from a sign-in round trip (?reprendre=compte|promo): refill the form
  // from the held draft and reopen the panel at that door (four-doors spec,
  // decision 34). The person confirms; nothing starts on its own.
  useEffect(() => {
    const porte = searchParams.get("reprendre")
    if (!porte || authLoading) return
    const door: DoorId = porte === "promo" ? "promo" : "account"
    const restore = (a: Analysis, owned: boolean) => {
      const i = a.inputs ?? {}
      reset({ cv_text: i.cv_text ?? "", cible_visee: i.cible_visee ?? "", chemin: i._chemin === "B" ? "B" : "A" })
      if (owned) setDraftId(a.id)
      setInitialDoor(door)
      setPanelOpen(true)
    }
    if (user) {
      held.claim()
        .then((r) => restore(r.analysis, true))
        .catch(() =>
          // Verified on another device: signup attached the draft to this
          // account at verify-email, so it is the account's latest draft.
          api.get<{ analyses: Analysis[] }>("/analyses/", { skipRedirect: true })
            .then((r) => {
              const latest = r.analyses.find((a) => a.status === "draft")
              if (latest) restore(latest, true)
              else setResumeNotice("Votre formulaire est resté sur l’appareil où vous l’avez rempli : connectez-vous depuis celui-ci pour le retrouver.")
            })
            .catch(() => setResumeNotice("Votre brouillon a expiré.")),
        )
    } else {
      held.get()
        .then((r) => restore(r.analysis, false))
        .catch(() => setResumeNotice("Votre brouillon a expiré."))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading])
```

5. In the JSX:
   - Under `{submitError && …}` add
     `{resumeNotice && <Alert><AlertDescription>{resumeNotice}</AlertDescription></Alert>}`.
   - The paragraph « Le reste de l’analyse s’appuie sur ce que vous avez déjà
     donné… » renders only `{user && (…)}` (spec: a signed-out run has no
     profile).
   - The intro line « Votre CV et la cible que vous visez. Le reste vient de
     votre profil. » becomes `{user ? "Votre CV et la cible que vous visez. Le reste vient de votre profil." : "Votre CV et la cible que vous visez."}`.
   - « Enregistrer le brouillon » and its state lines render only `{user && (…)}`;
     the `draftState === "auth"` branch goes.
   - The submit button: `<Button type="submit" size="xl">Générer mon analyse <ArrowRight /></Button>`.
   - The shield line: `Données chiffrées, supprimables à tout moment.` for everyone.
   - After the `</form>`, the panel:

```tsx
        {panelOpen && (
          <div className="mt-6">
            <DoorsPanel
              inputs={() => toInputs(watch())}
              draftId={draftId}
              initialDoor={initialDoor}
              onClose={() => setPanelOpen(false)}
            />
          </div>
        )}
```

   - Update the skeleton comment above `if (!ready)`: the form now waits only
     for auth to resolve (so the doors know who is there), not for a session.

- [ ] **Step 3: `/analyse/envoyee`**

`frontend/src/app/analyse/envoyee/page.tsx`:

```tsx
import Link from "next/link"
import { CheckCircle2 } from "lucide-react"
import { Logo } from "@/components/brand/Logo"
import { Button } from "@/components/ui/button"

/** After the advisor door (four-doors spec, decision 26): no link, no id, no
 *  content — the report is the counselor's. */
export default function AnalyseEnvoyeePage() {
  return (
    <div className="bg-mesh flex min-h-screen items-center justify-center px-5 py-12">
      <div className="w-full max-w-md text-center">
        <Logo className="mx-auto text-2xl" />
        <CheckCircle2 className="mx-auto mt-10 size-8 text-success" />
        <h1 className="mt-4 font-display text-2xl font-bold text-navy">C’est envoyé.</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Votre conseiller recevra votre analyse d’ici quelques minutes, dans son espace. Il pourra vous la présenter lors de votre prochain échange.
        </p>
        <Button render={<Link href="/" />} variant="outline" size="lg" className="mt-6">
          Retour à l’accueil
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Check, then commit**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build` — no error.

Manual, local stack (`docker compose up -d`, http://localhost:8080):
1. Signed out: `/analyse/nouveau` opens (no redirect to `/inscription`); a CV
   upload works; « Générer mon analyse » opens four doors.
2. « Sans compte » with the box ticked → `/rapport#…` (Task 16 renders it;
   until then the page 404s — expected).
3. « J'ai un code conseiller » with a test counselor's code → `/analyse/envoyee`.
4. « Avec mon compte » signed out → `/inscription?redirect=…reprendre=compte`;
   sign up, open the verification link from the backend log **in a private
   window** (the phone case), finish: the form comes back filled, panel open
   at « Avec mon compte ».
5. « J'ai un code promo » with an admin code, signed out → after the round
   trip the code is pre-filled; confirm → waiting screen.
6. Type a conseiller code at the promo door → the panel switches to « J'ai un
   code conseiller » with the message.
7. Signed in: three doors, no « Sans compte ».

```bash
git add frontend/src
git commit -m "feat(frontend): the form opens to everyone; four doors behind « Générer mon analyse »

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 16: `/rapport` — the no-login report; « garder » into `/espace`

**Files:**
- Create: `frontend/src/app/rapport/page.tsx`, `frontend/src/app/rapport/layout.tsx`
- Modify: `frontend/src/app/espace/page.tsx` (`?garder=1`)

**Interfaces:**
- Consumes: `held`, `tokenFromHash` (Task 14), `RunProgress`,
  `ReportDocument`, `isPaidReport`, `PriceProbe` (Task 14).

- [ ] **Step 1: The layout — no referrer, no indexing**

`frontend/src/app/rapport/layout.tsx`:

```tsx
import type { Metadata } from "next"
import type { ReactNode } from "react"

// A private report: never indexed, and no Referer from it (four-doors spec,
// decision 30 — the key is in the fragment anyway, this is belt and braces).
export const metadata: Metadata = {
  title: "Votre rapport",
  referrer: "no-referrer",
  robots: { index: false, follow: false },
}

export default function RapportLayout({ children }: { children: ReactNode }) {
  return children
}
```

- [ ] **Step 2: The page**

`frontend/src/app/rapport/page.tsx`:

```tsx
"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Printer, Check, Link2, Trash2 } from "lucide-react"
import { AppBar } from "@/components/layout/AppBar"
import { Button } from "@/components/ui/button"
import { RunProgress } from "@/components/analyse/RunProgress"
import { ReportDocument, isPaidReport } from "@/components/report/ReportDocument"
import { PriceProbe } from "@/components/report/PriceProbe"
import { held, tokenFromHash } from "@/lib/held"
import { copyToClipboard } from "@/lib/utils"
import type { Analysis } from "@/types"

type State = "loading" | "running" | "ready" | "gone" | "deleted"

/** A no-login report, opened by the key in its URL fragment (four-doors spec,
 *  decisions 30-32). */
export default function RapportSansComptePage() {
  const router = useRouter()
  const [token, setToken] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [state, setState] = useState<State>("loading")
  const [copied, setCopied] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const t = tokenFromHash()
    setToken(t)
    if (!t) { setState("gone"); return }
    held.byToken(t)
      .then((r) => { setAnalysis(r.analysis); setState(r.analysis.status === "success" ? "ready" : "running") })
      .catch(() => setState("gone"))
  }, [])

  const copyLink = async () => {
    setCopied(await copyToClipboard(window.location.href))
    setTimeout(() => setCopied(false), 2500)
  }

  // « Créer un compte pour le garder »: hand the report to the hold cookie,
  // sign in, and /espace claims it (decision 32).
  const keep = async () => {
    if (!token) return
    setBusy(true)
    try {
      await held.hold(token)
      router.push(`/inscription?redirect=${encodeURIComponent("/espace?garder=1")}`)
    } catch {
      setBusy(false)
      setState("gone")
    }
  }

  const remove = async () => {
    if (!token || !analysis) return
    setBusy(true)
    try { await held.remove(analysis.id, token); setState("deleted") } finally { setBusy(false) }
  }

  if (state === "loading") return <div className="min-h-screen bg-secondary" />

  if (state === "gone" || state === "deleted") {
    return (
      <div className="bg-mesh flex min-h-screen items-center justify-center px-5 py-12">
        <div className="w-full max-w-md text-center">
          <h1 className="font-display text-2xl font-bold text-navy">
            {state === "deleted" ? "Rapport supprimé." : "Ce lien n'est plus valide."}
          </h1>
          <Button render={<Link href="/analyse/nouveau" />} variant="outline" size="lg" className="mt-6">
            Nouvelle analyse
          </Button>
        </div>
      </div>
    )
  }

  if (state === "running" && token) {
    return (
      <RunProgress
        load={() => held.byToken(token).then((r) => r.analysis)}
        onDone={(a) => { setAnalysis(a); setState("ready") }}
        mailed={false}
        onRestart={() => router.push("/analyse/nouveau")}
      />
    )
  }

  const until = analysis?.access_expires_at
    ? new Date(analysis.access_expires_at).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })
    : null
  const hasOutput = Object.keys(analysis?.output ?? {}).length > 0
  const isPaid = isPaidReport(analysis)

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />

      <div className="no-print border-b border-border bg-card px-4 py-3 text-center text-sm text-navy">
        {until && <p>Ce rapport n'est accessible que par ce lien, jusqu'au {until}.</p>}
        <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
          <Button variant="outline" size="sm" onClick={copyLink}>
            {copied ? <Check className="size-3.5 text-success" /> : <Link2 className="size-3.5" />}
            {copied ? "Lien copié" : "Copier le lien"}
          </Button>
          <Button size="sm" onClick={keep} disabled={busy}>Créer un compte pour le garder</Button>
          <Button variant="outline" size="sm" onClick={() => setTimeout(() => window.print(), 50)}>
            <Printer className="size-3.5" /> PDF
          </Button>
          {confirmDelete ? (
            <span className="inline-flex items-center gap-2">
              <span className="text-xs">Supprimer définitivement ce rapport ?</span>
              <Button variant="destructive" size="sm" onClick={remove} disabled={busy}>Supprimer</Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>Annuler</Button>
            </span>
          ) : (
            <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}>
              <Trash2 className="size-3.5" /> Supprimer ce rapport
            </Button>
          )}
        </div>
      </div>

      <div className="px-4 py-8">
        <ReportDocument analysis={analysis} loading={false} unlockHref={null}>
          {hasOutput && !isPaid && (
            <div className="no-print mt-2 flex flex-col items-start justify-between gap-4 rounded-xl bg-brand-gradient p-5 text-white sm:flex-row sm:items-center">
              <p className="font-display font-bold">Créez un compte pour débloquer le rapport complet</p>
              <Button onClick={keep} disabled={busy} size="lg" className="shrink-0 bg-white text-orange-dark hover:bg-white/90">
                Créer un compte pour le garder
              </Button>
            </div>
          )}
          {hasOutput && !isPaid && analysis && token && <PriceProbe analysisId={analysis.id} token={token} />}
        </ReportDocument>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: `/espace?garder=1` claims the held report**

In `frontend/src/app/espace/page.tsx` (import `useSearchParams` from
`next/navigation`, `import { held } from "@/lib/held"` and
`import { Alert, AlertDescription } from "@/components/ui/alert"`; the page body
must sit inside a `<Suspense>` for `useSearchParams`, or `next build` fails —
wrap it the way `nouveau/page.tsx` wraps its form if the page does not
already):

```tsx
  const searchParams = useSearchParams()
  const [kept, setKept] = useState(false)

  // Back from « Créer un compte pour le garder » (four-doors spec, decision
  // 32): attach the held report to this account, then list it.
  useEffect(() => {
    if (!user || searchParams.get("garder") !== "1") return
    held.claim()
      .then(() => { setKept(true); return api.get<{ analyses: Analysis[] }>("/analyses/") })
      .then((r) => r && setAnalyses(r.analyses))
      .catch(() => { /* nothing held any more: the list stands as it is */ })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user])
```

and above the analyses grid:

```tsx
        {kept && (
          <Alert className="mb-4"><AlertDescription>Le rapport est maintenant dans votre espace.</AlertDescription></Alert>
        )}
```

(Use whatever list-loading function the page already has instead of a second
`api.get` if it exposes one.)

- [ ] **Step 4: Check, then commit**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build` — no error.

Manual, local stack:
1. « Sans compte » → `/rapport#…`: the waiting screen without any mail promise,
   then the report with the banner date 30 days out.
2. « Copier le lien », paste in a private window → the same report. Remove one
   character of the fragment → « Ce lien n'est plus valide. ».
3. `docker compose logs nginx backend | grep -c <the token>` → 0.
4. « Créer un compte pour le garder » → sign up → verify (same browser) →
   `/espace` shows « Le rapport est maintenant dans votre espace. » and the
   report in the list. The old `/rapport#…` link → « Ce lien n'est plus valide. ».
5. A second no-login report → « Supprimer ce rapport » → confirm → « Rapport
   supprimé. ».

```bash
git add frontend/src
git commit -m "feat(frontend): /rapport — the no-login report, kept by signing up

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
## Task 17: The counselor's pages — the report, notes, relaunch; « Mes bénéficiaires »

**Files:**
- Modify: `frontend/src/lib/counselor.ts`, `frontend/src/app/conseiller/page.tsx`
- Create: `frontend/src/app/conseiller/analyses/[id]/page.tsx`

**Interfaces:**
- Consumes: the Task 9 routes; `ReportDocument` (Task 14); types (Task 14).
- Produces: `counselor.analyses()`, `.analysis(id)`, `.deleteAnalysis(id)`,
  `.relaunch(id)`, `.note(id)`, `.saveNote(id, note)`.

- [ ] **Step 1: The client calls**

In `frontend/src/lib/counselor.ts`, import `Analysis` and
`CounselorAnalysisRow` from `@/types`, fix the `counselor` object's comment
(`/api/c` is retired), and add inside `counselor`:

```ts
  /** Advisor-door reports — the counselor's alone (four-doors spec, ruling 2). */
  analyses: () => api.get<{ analyses: CounselorAnalysisRow[] }>("/counselor/analyses"),
  analysis: (id: string) =>
    api.get<{ analysis: Analysis; code_label: string | null }>(`/counselor/analyses/${id}`),
  deleteAnalysis: (id: string) => api.delete(`/counselor/analyses/${id}`),
  relaunch: (id: string) => api.post<{ analysis: Analysis }>(`/counselor/analyses/${id}/relaunch`),
  note: (id: string) => api.get<{ note: string }>(`/counselor/analyses/${id}/notes`),
  saveNote: (id: string, note: string) =>
    api.put<{ note: string }>(`/counselor/analyses/${id}/notes`, { note }),
```

- [ ] **Step 2: The report page**

`frontend/src/app/conseiller/analyses/[id]/page.tsx`:

```tsx
"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, Printer, RotateCcw, Trash2 } from "lucide-react"
import { AppBar } from "@/components/layout/AppBar"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { ReportDocument } from "@/components/report/ReportDocument"
import { ApiError } from "@/lib/api"
import { counselor } from "@/lib/counselor"
import type { Analysis } from "@/types"

const POLL_MS = 4000

/** An advisor-door report, on the counselor's page (four-doors spec,
 *  decisions 26-27): the full report, print, private notes, delete, and
 *  « Relancer » when the run failed. */
export default function ConseillerAnalysePage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [label, setLabel] = useState<string | null>(null)
  const [missing, setMissing] = useState(false)
  const [note, setNote] = useState("")
  const [noteState, setNoteState] = useState<"idle" | "saving" | "saved" | "error">("idle")
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const load = useCallback(async () => {
    try {
      const r = await counselor.analysis(id)
      setAnalysis(r.analysis)
      setLabel(r.code_label)
      if (r.analysis.status === "queued" || r.analysis.status === "running") {
        timer.current = setTimeout(load, POLL_MS)
      }
    } catch {
      setMissing(true)
    }
  }, [id])

  useEffect(() => {
    load()
    counselor.note(id).then((r) => setNote(r.note)).catch(() => {})
    return () => { if (timer.current) clearTimeout(timer.current) }
  }, [id, load])

  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : "Erreur inattendue.")

  const relaunch = async () => {
    setError(null)
    try {
      const r = await counselor.relaunch(id)
      setAnalysis(r.analysis)
      timer.current = setTimeout(load, POLL_MS)
    } catch (e) { fail(e) }
  }

  const saveNote = async () => {
    setNoteState("saving")
    try { await counselor.saveNote(id, note); setNoteState("saved") } catch { setNoteState("error") }
  }

  const remove = async () => {
    try { await counselor.deleteAnalysis(id); router.push("/conseiller") } catch (e) { fail(e) }
  }

  if (missing) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="mx-auto max-w-md py-24 text-center">
          <h1 className="font-display text-xl font-bold text-navy">Analyse introuvable.</h1>
          <Button render={<Link href="/conseiller" />} variant="outline" size="lg" className="mt-6">
            <ArrowLeft className="size-4" /> Mon espace conseiller
          </Button>
        </div>
      </div>
    )
  }

  const inputs = analysis?.inputs ?? {}
  const who = [inputs.prenom, (inputs.nom ?? "").toUpperCase()].filter(Boolean).join(" ")
  const date = analysis
    ? new Date(analysis.created_at).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })
    : ""
  const running = analysis?.status === "queued" || analysis?.status === "running"
  const failed = analysis?.status === "error" || analysis?.status === "timeout"

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />

      <div className="no-print sticky top-16 z-40 flex flex-wrap items-center justify-center gap-2 border-b border-border bg-secondary/95 py-3 backdrop-blur-sm">
        <Button render={<Link href="/conseiller" />} variant="ghost" size="sm">
          <ArrowLeft className="size-3.5" /> Mon espace conseiller
        </Button>
        <Button variant="outline" size="sm" disabled={!analysis || running || failed}
                onClick={() => setTimeout(() => window.print(), 50)}>
          <Printer className="size-3.5" /> PDF
        </Button>
        {failed && (
          <Button size="sm" onClick={relaunch}><RotateCcw className="size-3.5" /> Relancer</Button>
        )}
        {confirmDelete ? (
          <span className="inline-flex items-center gap-2">
            <span className="text-xs text-navy">Supprimer définitivement cette analyse ?</span>
            <Button variant="destructive" size="sm" onClick={remove}>Supprimer</Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>Annuler</Button>
          </span>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}>
            <Trash2 className="size-3.5" /> Supprimer l’analyse
          </Button>
        )}
      </div>

      <div className="mx-auto max-w-4xl px-4 py-6">
        <p className="no-print mb-4 text-sm font-medium text-navy">
          {[who || "—", label ? `code « ${label} »` : null, date].filter(Boolean).join(" · ")}
        </p>
        {error && <Alert variant="destructive" className="mb-4"><AlertDescription>{error}</AlertDescription></Alert>}
        {running && (
          <Alert className="mb-4"><AlertDescription>Analyse en cours… La page se met à jour toute seule.</AlertDescription></Alert>
        )}
        {failed && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>L’analyse n’a pas abouti. Vous pouvez la relancer.</AlertDescription>
          </Alert>
        )}
        {analysis && !running && !failed && <ReportDocument analysis={analysis} loading={false} unlockHref={null} />}

        <section className="no-print mt-6 rounded-2xl bg-card p-5 ring-1 ring-foreground/10">
          <h2 className="font-display text-base font-semibold text-navy">Notes privées</h2>
          <p className="mt-1 text-xs text-muted-foreground">Visibles par vous seul.</p>
          <Textarea
            className="mt-3 min-h-32 bg-background text-sm"
            value={note}
            maxLength={20000}
            onChange={(e) => { setNote(e.target.value); setNoteState("idle") }}
          />
          <div className="mt-3 flex items-center gap-3">
            <Button size="sm" variant="navy" onClick={saveNote} disabled={noteState === "saving"}>Enregistrer</Button>
            {noteState === "saved" && <span className="text-xs text-success">Enregistré.</span>}
            {noteState === "error" && <span className="text-xs text-destructive">Échec de l’enregistrement. Réessayez.</span>}
          </div>
        </section>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: « Mes bénéficiaires » links to the reports; places per kind**

In `frontend/src/app/conseiller/page.tsx` (import `Link` from `next/link` if
the file does not already):

- The bénéficiaires table: the « Prénom » cell shows
  `{[p.prenom, p.nom].filter(Boolean).join(" ") || "—"}`; the email cell shows
  `{p.email ?? (p.analysis_id ? "—" : "Bénéficiaire anonyme")}`; add a fourth
  header `<th …>Analyse</th>` and cell:

```tsx
                          <td className="py-2.5 text-xs">
                            {p.analysis_id
                              ? <Link href={`/conseiller/analyses/${p.analysis_id}`} className="text-navy underline underline-offset-2">Voir l’analyse</Link>
                              : "—"}
                          </td>
```

  Key the rows by `` `${p.redeemed_at}-${i}` ``.
- The codes hint sentence « Un code par personne, valable 90 jours. Pour un
  atelier, indiquez le nombre de places… » gets one more sentence at the end:
  ` 1 analyse et 1 voyage par place.`
- The codes table's uses cell shows both kinds:
  `{c.uses_by_kind.analysis} analyse · {c.uses_by_kind.voyage} voyage`
  (keep the `/ max_uses` the cell shows today, if it shows one, after each).

- [ ] **Step 4: Check, then commit**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build` — no error.

Manual, local stack: with a test counselor approved by the admin, mint a code
in `/conseiller`, run the advisor door signed out with it, then as the
counselor:
1. receive the mail (backend log, « Une analyse est prête »);
2. `/conseiller` → « Mes bénéficiaires » → « Voir l’analyse »;
3. the report renders in full; PDF prints; a note saves and reloads;
4. make a run fail (stop the backend mid-run, restart: the reaper marks it) →
   « Relancer » → it runs again; a second click is refused;
5. « Supprimer l’analyse » → confirm → back on `/conseiller`, the row gone.

```bash
git add frontend/src
git commit -m "feat(frontend): the counselor's report page; bénéficiaires link to their analyses

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 18: `/debloquer` takes promo codes; the admin's promo-code panel

**Files:**
- Modify: `frontend/src/lib/api.ts` (add `patch`)
- Modify: `frontend/src/app/analyse/[id]/debloquer/page.tsx`
- Create: `frontend/src/components/admin/PromoCodesPanel.tsx`
- Modify: `frontend/src/app/admin/conseillers/page.tsx`

- [ ] **Step 1: `api.patch`**

In `frontend/src/lib/api.ts`, in the `api` object after `put`:

```ts
  patch:  <T>(path: string, body?: unknown, opts?: ApiOptions) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body), ...opts }),
```

- [ ] **Step 2: `/debloquer`**

In `frontend/src/app/analyse/[id]/debloquer/page.tsx`, four strings (spec,
copy row 7):

| Before | After |
|---|---|
| `Saisissez votre code conseiller.` | `Saisissez votre code promo.` |
| `Livrable 9 sections + CV retravaillé + export conseiller` | `Livrable 9 sections + CV retravaillé` |
| `Paiement sécurisé par Stripe · gratuit pour les bénéficiaires Cap Emploi / France Travail (code conseiller)` | `Paiement sécurisé par Stripe` |
| `Déjà un code conseiller ?` | `Déjà un code promo ?` |

The redeem handler already shows the server's message on error, which is how
the conseiller-code refusal (decision 22) reaches the person. Rename the
`{/* Counselor code */}` comment to `{/* Promo code */}`.

- [ ] **Step 3: `PromoCodesPanel`**

`frontend/src/components/admin/PromoCodesPanel.tsx`:

```tsx
"use client"

import { useEffect, useState } from "react"
import { Check, Copy } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api, ApiError } from "@/lib/api"
import { copyToClipboard } from "@/lib/utils"
import type { AdminCodeRow } from "@/types"

const fmtDate = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : "—")
/** An empty field means illimité, as the API's null does. */
const limit = (raw: string): number | null => (raw.trim() === "" ? null : Number.parseInt(raw, 10))

function statut(c: AdminCodeRow): string {
  if (c.revoked_at || !c.is_active) return "Révoqué"
  if (c.expires_at && new Date(c.expires_at) <= new Date()) return "Expiré"
  return "Actif"
}

/** The admin's codes (four-doors spec, decision 18). A code with no owner is
 *  a promo code: signed in, Complet, once per account. Conseiller codes are
 *  listed for reference; their limits are the conseiller's. */
export function PromoCodesPanel() {
  const [codes, setCodes] = useState<AdminCodeRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [label, setLabel] = useState("")
  const [uses, setUses] = useState("1")
  const [days, setDays] = useState("90")
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)
  const [editing, setEditing] = useState<{ id: string; uses: string; days: string } | null>(null)
  const [revoking, setRevoking] = useState<string | null>(null)

  useEffect(() => {
    api.get<{ codes: AdminCodeRow[] }>("/admin/counselor-codes")
      .then((r) => setCodes(r.codes))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erreur de chargement"))
      .finally(() => setLoading(false))
  }, [])

  const replace = (row: AdminCodeRow) => setCodes((all) => all.map((c) => (c.id === row.id ? row : c)))
  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : "Erreur inattendue.")

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = await api.post<{ code: AdminCodeRow }>("/admin/counselor-codes", {
        label, max_uses: limit(uses), expires_in_days: limit(days),
      })
      setCodes((all) => [r.code, ...all])
      setLabel("")
    } catch (err) { fail(err) } finally { setBusy(false) }
  }

  const saveLimits = async () => {
    if (!editing) return
    setBusy(true)
    setError(null)
    try {
      // Validity left empty while editing means "unchanged", not illimité.
      const body: Record<string, number | null> = { max_uses: limit(editing.uses) }
      if (editing.days.trim()) body.expires_in_days = limit(editing.days)
      const r = await api.patch<{ code: AdminCodeRow }>(`/admin/counselor-codes/${editing.id}`, body)
      replace(r.code)
      setEditing(null)
    } catch (err) { fail(err) } finally { setBusy(false) }
  }

  const revoke = async (id: string) => {
    setBusy(true)
    setError(null)
    try {
      const r = await api.delete<{ code: AdminCodeRow }>(`/admin/counselor-codes/${id}`)
      replace(r.code)
      setRevoking(null)
    } catch (err) { fail(err) } finally { setBusy(false) }
  }

  const copy = async (value: string) => {
    if (await copyToClipboard(value)) {
      setCopied(value)
      setTimeout(() => setCopied(null), 2000)
    }
  }

  return (
    <section className="rounded-2xl bg-card shadow-soft ring-1 ring-foreground/10">
      <div className="border-b border-border px-5 py-4">
        <h2 className="font-display text-base font-semibold text-navy">Codes promo</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Un code promo donne le rapport complet, une fois par compte. Un champ vide signifie « illimité ».
        </p>
      </div>
      <div className="px-5 py-4">
        {error && <Alert variant="destructive" className="mb-4"><AlertDescription>{error}</AlertDescription></Alert>}

        <form onSubmit={create} className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="promo-label">Libellé</Label>
            <Input id="promo-label" className="h-10" value={label} disabled={busy}
                   onChange={(e) => setLabel(e.target.value)} placeholder="Salon, partenaire, relecture PM…" />
          </div>
          <div className="w-full space-y-1.5 sm:w-28">
            <Label htmlFor="promo-uses">Utilisations</Label>
            <Input id="promo-uses" type="number" min={1} className="h-10" value={uses} disabled={busy}
                   onChange={(e) => setUses(e.target.value)} />
          </div>
          <div className="w-full space-y-1.5 sm:w-28">
            <Label htmlFor="promo-days">Validité (jours)</Label>
            <Input id="promo-days" type="number" min={1} className="h-10" value={days} disabled={busy}
                   onChange={(e) => setDays(e.target.value)} />
          </div>
          <Button type="submit" variant="navy" size="lg" disabled={busy || !label.trim()}>Créer le code</Button>
        </form>

        <div className="w-full overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                {["Code", "Libellé", "Type", "Analyses", "Voyages", "Limite", "Expire le", "Statut", ""].map((h) => (
                  <th key={h} className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {codes.map((c) => {
                const isEditing = editing?.id === c.id
                return (
                  <tr key={c.id} className="border-b border-border/60 last:border-0">
                    <td className="whitespace-nowrap py-2.5 pr-4 font-mono text-xs">
                      {c.code}{" "}
                      <button type="button" aria-label="Copier le code" onClick={() => copy(c.code)}>
                        {copied === c.code ? <Check className="inline size-3.5 text-success" /> : <Copy className="inline size-3.5" />}
                      </button>
                    </td>
                    <td className="py-2.5 pr-4">{c.label}</td>
                    <td className="py-2.5 pr-4"><Badge variant="outline">{c.kind === "promo" ? "Promo" : "Conseiller"}</Badge></td>
                    <td className="py-2.5 pr-4 tabular-nums">{c.uses_by_kind.analysis}</td>
                    <td className="py-2.5 pr-4 tabular-nums">{c.uses_by_kind.voyage}</td>
                    <td className="py-2.5 pr-4">
                      {isEditing
                        ? <Input className="h-8 w-20" type="number" min={1} value={editing.uses}
                                 onChange={(e) => setEditing({ ...editing, uses: e.target.value })} />
                        : (c.max_uses ?? "illimité")}
                    </td>
                    <td className="py-2.5 pr-4">
                      {isEditing
                        ? <Input className="h-8 w-24" type="number" min={1} placeholder="inchangé" value={editing.days}
                                 onChange={(e) => setEditing({ ...editing, days: e.target.value })} />
                        : fmtDate(c.expires_at)}
                    </td>
                    <td className="py-2.5 pr-4">{statut(c)}</td>
                    <td className="whitespace-nowrap py-2.5 text-right">
                      {c.kind === "promo" && !c.revoked_at && (
                        isEditing ? (
                          <>
                            <Button size="sm" variant="navy" onClick={saveLimits} disabled={busy}>Enregistrer</Button>{" "}
                            <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>Annuler</Button>
                          </>
                        ) : revoking === c.id ? (
                          <>
                            <span className="text-xs">Révoquer ce code ?</span>{" "}
                            <Button size="sm" variant="destructive" onClick={() => revoke(c.id)} disabled={busy}>Révoquer</Button>{" "}
                            <Button size="sm" variant="ghost" onClick={() => setRevoking(null)}>Annuler</Button>
                          </>
                        ) : (
                          <>
                            <Button size="sm" variant="outline"
                                    onClick={() => setEditing({ id: c.id, uses: c.max_uses?.toString() ?? "", days: "" })}>
                              Limites
                            </Button>{" "}
                            <Button size="sm" variant="ghost" onClick={() => setRevoking(c.id)}>Révoquer</Button>
                          </>
                        )
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {!loading && codes.length === 0 && (
          <p className="py-10 text-center text-sm text-muted-foreground">Aucun code pour le moment.</p>
        )}
      </div>
    </section>
  )
}
```

- [ ] **Step 4: The admin page uses the panel**

In `frontend/src/app/admin/conseillers/page.tsx`, delete the codes machinery —
the `codes`, `loadingCodes`, `errorCodes`, new-label, creating and deleting
state; the `/admin/counselor-codes` fetch effect; `activeCodes`; the copy,
create and deactivate handlers (the one with `window.confirm`); the two stat
cards « Codes d’accès » and « Codes actifs »; and the codes section's JSX —
then render `<PromoCodesPanel />` where that section stood
(`import { PromoCodesPanel } from "@/components/admin/PromoCodesPanel"`).
Remove the `CounselorCode` type import if nothing else uses it.

- [ ] **Step 5: Check, then commit**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build` — no error.

Manual, local stack, as admin: create a promo code with defaults (1 use, 90
days); create one with both fields empty (illimité / —); « Limites » on the
old code → set 3 uses, leave validity empty → it keeps its expiry; revoke →
« Révoqué ». As a candidate on a free report's `/debloquer`: a conseiller
code → the refusal sentence; a promo code → the waiting screen.

```bash
git add frontend/src
git commit -m "feat(frontend): promo codes in /debloquer and in the admin's panel

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 19: Copy — landing, CGV, confidentialité

Every row of the spec's « Changed strings » table not yet done (rows 1–5,
8–13; rows 6–7 are in Tasks 15 and 18). In JSX text, keep the file's own
escaping (`&apos;` where it writes `&apos;`).

**Files:**
- Modify: `frontend/src/app/page.tsx`, `frontend/src/app/(legal)/cgv/page.tsx`,
  `frontend/src/app/(legal)/confidentialite/page.tsx`

- [ ] **Step 1: Landing (`app/page.tsx`)**

1. Counselor card `desc` (today `page.tsx:158`): replace the whole string with
   « Avec votre code, vos bénéficiaires lancent l’analyse de leur CV, et le
   rapport complet arrive dans votre espace conseiller : leurs forces, leurs
   fragilités, vos préconisations. Vous le reprenez ensemble en entretien, à
   partir d’une même base. Vous gagnez du temps. Eux, de la confiance. Le même
   code leur ouvre les sessions du voyage — et vous relisez leur portrait avec
   eux avant qu’ils ne le reçoivent. »
2. FAQ « Combien ça coûte ? » (as sub-project 1 left it): « sans carte
   bancaire : » → « sans carte bancaire et sans compte obligatoire : », and
   the last sentence « Si votre conseiller vous a remis un code, le rapport
   complet et les sessions 1 à 5 du voyage sont offerts. » → « Si votre
   conseiller vous a remis un code, les sessions 1 à 5 du voyage vous sont
   offertes, ainsi que votre analyse : son rapport complet est envoyé à votre
   conseiller, qui le reprend avec vous. »
3. Report section (today `page.tsx:411`): « Si vous êtes accompagné par un
   conseiller, il a peut-être un code qui vous donne accès à tout —
   gratuitement. Ça vaut la peine de lui demander. » → « Si vous êtes
   accompagné par un conseiller, il a peut-être un code : votre analyse
   complète lui est alors envoyée, gratuitement, pour qu’il la reprenne avec
   vous. Ça vaut la peine de lui demander. »
4. Free card small print: « … Aucune carte bancaire demandée. » → « … Aucune
   carte bancaire demandée, et pas de compte obligatoire pour l’analyse. »
5. « Code conseiller » card (today `page.tsx:528`): → « Vous êtes accompagné
   par un conseiller ? Avec son code, votre analyse complète lui est envoyée
   pour qu’il la reprenne avec vous, et les sessions 1 à 5 du voyage vous sont
   ouvertes — gratuitement. Ça vaut la peine de lui demander. »

- [ ] **Step 2: CGV (`(legal)/cgv/page.tsx`)**

1. §2 (as sub-project 1 left it): after « ainsi qu'un verdict de diagnostic. »
   insert « Elle est accessible avec ou sans compte ; sans compte, le rapport
   n'est accessible que par un lien privé, pendant 30 jours, sauf si
   l'utilisateur crée un compte pour le conserver. », and « L'offre payante
   débloque le rapport complet, ainsi que l'export conseiller. » → « L'offre
   payante débloque le rapport complet. »
2. §6: title « Bénéficiaires accompagnés (code conseiller) » → « Codes
   conseiller et codes promotionnels »; its paragraph becomes two:

```tsx
      <p>
        Les bénéficiaires d&apos;un accompagnement Cap Emploi, France Travail, Mission Locale ou CEP
        peuvent, au moyen d&apos;un code fourni par leur conseiller, faire réaliser gratuitement une
        analyse complète et accéder aux sessions 1 à 5 du voyage. Le rapport de cette analyse est
        transmis au seul conseiller titulaire du code, et non au bénéficiaire ; il est conservé 12 mois
        dans l&apos;espace de ce conseiller. Ce code est strictement personnel à la structure qui le
        délivre.
      </p>
      <p>
        neoori peut remettre des codes promotionnels. Un code promotionnel donne accès gratuitement,
        une fois par compte, au rapport complet d&apos;une analyse ; il nécessite un compte. Il peut
        être limité en nombre d&apos;utilisations et dans le temps, et neoori peut le désactiver à tout
        moment.
      </p>
```

- [ ] **Step 3: Confidentialité (`(legal)/confidentialite/page.tsx`)**

1. §2 « Notes du conseiller » bullet: « … les notes qu&apos;un conseiller prend
   sur votre analyse ou votre voyage pour préparer l&apos;entretien. » → « … les
   notes qu&apos;un conseiller prend sur votre voyage, ou sur une analyse lancée
   avec son code, pour préparer l&apos;entretien. »
2. §2, a new bullet right after « Analyses »:

```tsx
        <li>
          <strong>Analyse sans compte</strong> : le contenu de votre CV et la cible visée, conservés
          30 jours puis supprimés, sauf si vous créez un compte pour garder le rapport. Le lien privé
          du rapport en est la seule clé : nous ne pouvons pas le retrouver pour vous.
        </li>
```

3. §3, a new bullet after « Génération du rapport d&apos;analyse — exécution du
   contrat. »:

```tsx
        <li>Analyse sans compte, ou avec le code de votre conseiller — exécution du contrat (CGV acceptées à l&apos;envoi).</li>
```

4. §5: replace the « Le lien de partage conseiller (« /c/… ») … » paragraph:

```tsx
      <p>
        Si vous lancez une analyse avec le code de votre conseiller, le rapport complet, votre prénom,
        votre nom, votre CV et la cible visée sont transmis à ce conseiller, dans son espace, et à lui
        seul ; vous n&apos;en recevez pas de copie. Ce rapport est supprimé 12 mois après sa création,
        ou plus tôt si le conseiller le supprime. Pour en obtenir une copie ou sa suppression,
        adressez-vous à votre conseiller ou écrivez-nous. Lorsque vous utilisez son code pour le
        voyage, le conseiller voit votre prénom, votre email et la date d&apos;utilisation.
      </p>
```

- [ ] **Step 4: Check, then commit**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build` — no error.
Run the banned-word check over the whole frontend:

```bash
grep -rniE "boussole|copilote|miroir|révélation|épanouissement|alignement|excellence|talent unique|vous vous démarquez" frontend/src/app frontend/src/components
```
Expected: no hit this branch added. To tell, run the same pattern against the
base: `git grep -niE "<same pattern>" initial -- frontend/src` — every hit above
must also appear there.

```bash
git add frontend/src
git commit -m "copy: the four doors on the landing, in the CGV and the privacy policy

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Task 20: Docs, and the whole-branch check

**Files:**
- Modify: `CLAUDE.md`, `DOCKER.md`, `TEST-PLAN.md`,
  `docs/superpowers/specs/2026-09-24-conseiller-accounts-design.md`

- [ ] **Step 1: `CLAUDE.md`**

1. Replace the section « ## Counselor view — sections 1, 4, 5 only » with:

````markdown
## Les quatre portes

The parcours 1 form is open to everyone; « Générer mon analyse » leads to four
doors. `services/doors.py` decides each door's tier and recipient — the
browser never chooses a tier, and `FORCE_ANALYSIS_TIER` is gone. Spec:
`docs/superpowers/specs/2026-10-08-four-doors-design.md`.

| Door | Account | Runs | The report goes to |
|---|---|---|---|
| `account` « Avec mon compte » | required | free (§1–3 + verdict) | the account; 9 € / 24 € unlock as before |
| `promo` « J'ai un code promo » | required | Complet (§1–9) | the account; once per account |
| `advisor` « J'ai un code conseiller » | never asked | Complet (§1–9) | **only** the counselor who owns the code, at `/conseiller/analyses/<id>` |
| `anonymous` « Sans compte » | none | free | a private link `/rapport#<token>`, 30 days |

- **A code's kind is its owner**: none = promo (admin-minted), one = conseiller.
  Uses count per kind — a single-use conseiller code opens one analysis and one
  voyage. The database holds the ceiling (`code_redemptions.slot` + unique
  keys); `code_service.redeem()` commits before the run starts.
- **Who may read an analysis** is `_may_access()` in `routes/analyses.py`:
  advisor rows never on candidate routes; token rows by the `X-Analysis-Token`
  header; owned rows by their owner; `legacy` rows (ownerless, from before
  accounts were required) by id; anything else closed.
- **No token in a URL a server sees.** The report link carries its key in the
  fragment; a signed-out draft is held by the HttpOnly `neoori_hold` cookie.
  Password signup only marks a held row (`pending_user_id`); verify-email
  with the signup password attaches it; any other proof of the address drops
  the mark.
- **Caps** read the append-only `run_log`, so deleting a report never lowers
  them: `ANONYMOUS_RUNS_PER_DAY`, `FREE_RUNS_PER_ACCOUNT_PER_DAY`. nginx limits
  the open POSTs per address (`analyses`, `codes` zones).
- **Retention** — `flask purge-expired`, host cron 03:30 (DOCKER.md « Purge »):
  held drafts 48 h, unclaimed no-login reports 30 days, advisor reports 12
  months, `run_log` 2 days.
- **Rolling back below the four-doors migration** needs
  `flask purge-expired --before-rollback --apply` first, then
  `flask db downgrade`: otherwise advisor rows become plain ownerless rows the
  previous image serves by id.
- Access logs (nginx, gunicorn) record the path only — no query string, no
  Referer.
````

2. « ## Paywall »: « Counselor code → free access (Cap Emploi / France Travail
   beneficiaries) » → « Conseiller code → the advisor door: Complet, sent to the
   counselor, not the candidate. Promo code → Complet for a signed-in account,
   once. »
3. « ## AI call spec »: the line « Counselor code grants paid-tier model access
   (free for Cap Emploi / France Travail beneficiaries) » → « The tier is the
   door's (`services/doors.py`); nothing the browser sends selects a model. »
4. « ## Email verification »: « Analyses and CV uploads require an account;
   `/analyse/*` sends a signed-out visitor to `/inscription`. » → « The
   analysis form and the CV upload are open (Les quatre portes);
   `/analyse/<id>/*` — report, waiting and unlock pages — needs the owner, and
   sends a signed-out visitor to `/inscription`. »
5. « ### What reaches an analysis »: its first sentence says
   `routes/analyses._merge_voyage()` folds the voyage into **`account` and
   `promo` runs** (the advisor and anonymous doors fold nothing).
6. « ## Mails transactionnels » table: add the row
   `| Une analyse est prête / n'a pas abouti (conseiller) | the counselor who owns the code, verified only | anthropic_service._notify_outcome, advisor-door runs |`.

- [ ] **Step 2: `DOCKER.md`**

Add after « ## Backups »:

````markdown
## Purge

Rows that live on a clock, not an account (four-doors spec, decision 46):
held drafts after 48 h, unclaimed no-login reports after 30 days, advisor-door
reports after 12 months, `run_log` after 2 days. Script in the repo:
`scripts/neoori-purge.sh`, installed like the backup:

```bash
scp scripts/neoori-purge.sh neoori:/usr/local/bin/neoori-purge.sh
ssh neoori 'chmod +x /usr/local/bin/neoori-purge.sh'
ssh neoori '(crontab -l; echo "30 3 * * * /usr/local/bin/neoori-purge.sh") | crontab -'
ssh neoori 'cd /srv/neoori && docker compose -f docker-compose.prod.yml exec -T backend flask purge-expired --dry-run'
```

Log: `/var/log/neoori-purge.log`. Before adding the cron line, `crontab -l`
must already show the backup's `0 3 * * *` line — add beside it, never replace.

### Rolling back below the four-doors migration

The previous image cannot start against a database at this revision
(`flask db upgrade` under `set -e`), and the downgrade alone would leave
advisor-door rows readable by id. In order, with the new image still running:

```bash
C="docker compose -f docker-compose.prod.yml exec -T backend"
$C flask purge-expired --before-rollback          # counts only
$C flask purge-expired --before-rollback --apply
$C flask db downgrade b0c1d2e3f4a5                # the revision before c1d2e3f4a5b6
IMAGE_TAG=<sha> docker compose -f docker-compose.prod.yml up -d
```
````

Beside the auth rate-limit notes, add: « The `analyses` zone (10 r/min, burst
40) and the `codes` zone (10 r/min, burst 20) limit the open form's POSTs per
address; the polling GETs are not limited. » And under the nginx / logging
notes: « nginx and gunicorn log the path only (`log_format neoori_paths`,
`--access-logformat`): sign-in links, `next` paths and Stripe session ids
travel in query strings. »

- [ ] **Step 3: `TEST-PLAN.md`**

Replace the counselor-view (`/c/…`) checks with a « Les quatre portes »
section listing the walkthrough of Step 6 below.

- [ ] **Step 4: The conseiller spec's dated note**

Under decision 9 of
`docs/superpowers/specs/2026-09-24-conseiller-accounts-design.md`, add one
line, leaving the decision text as it is:

`> Reversed on 2026-10-08 by the four-doors spec (ruling 2): an analysis run through the advisor door goes to the counselor, in full, and only to them.`

- [ ] **Step 5: Whole branch, automated**

```bash
cd backend && python -m pytest -q
cd ../frontend && npx tsc --noEmit && npm run lint && npm run build
```
Expected: all green; the backend count is the baseline plus this plan's tests,
minus the deleted ones.

- [ ] **Step 6: Whole branch, by hand (local stack through nginx, http://localhost:8080)**

1. Each door signed out; each available door signed in; each with an
   expired access cookie (sign in, wait past `JWT_ACCESS_TOKEN_EXPIRES` or
   edit the cookie's token to an expired one).
2. Password signup with the verification link opened in a second browser
   profile — the draft is there.
3. An email-link sign-in opened in that second profile — the cross-device
   message.
4. A Google round trip, if the keys are set locally.
5. The counselor side: mail, report, print, note, relaunch, delete.
6. `/rapport#…` → « Créer un compte pour le garder » → `/espace`.
7. A burst of submits reaching the nginx 429, and the panel's sentence.
8. `docker compose logs nginx backend` shows paths only — no `?`, no token.
9. The old `/c/<token>` notice.
10. `flask purge-expired --dry-run` prints four counts.
11. The race, on real MySQL (spec « Testing »: SQLite does not reproduce the
    snapshot). Mint a single-use code for the test counselor, then fire ten
    advisor submits at once and count the answers:

    ```bash
    BODY='{"door":"advisor","code":"<CODE>","prenom":"Test","nom":"Course","consent":true,"inputs":{"cv_text":"'"$(printf 'c%.0s' $(seq 1 300))"'","cible_visee":"Chauffeur livreur PL dans une entreprise de transport régional"}}'
    seq 1 10 | xargs -P 10 -I{} curl -s -o /dev/null -w "%{http_code}\n" \
      -X POST http://localhost:8080/api/analyses/ -H 'Content-Type: application/json' -d "$BODY" | sort | uniq -c
    ```
    Expected: exactly one `201`; the others `400` (« Ce code a atteint sa
    limite d'utilisation. ») or `409`; and in MySQL
    `SELECT COUNT(*) FROM code_redemptions WHERE code_id = …` is 1. (Ten requests
    fit the `analyses` burst of 40.)

- [ ] **Step 7: Commit**

```bash
git add CLAUDE.md DOCKER.md TEST-PLAN.md docs/superpowers/specs/2026-09-24-conseiller-accounts-design.md
git commit -m "docs: the four doors — CLAUDE.md, DOCKER.md purge and rollback, test plan

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## After the build (developer's go, not part of the tasks)

The spec's « Rollout », in order: PM copy approval → merge and push → remove
`FORCE_ANALYSIS_TIER=paid` from `/srv/neoori/.env` → install the purge cron →
prod smoke test of each door (the first free-tier run production will ever
make) → PM reads the free-tier and CV-only sample reports.
