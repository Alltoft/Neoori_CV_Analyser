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
