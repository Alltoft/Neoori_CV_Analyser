"""Migration b4c5d6e7f8a9 erases the billet de sortie from stored voyages.

Loaded straight from its file and run on the test database's own connection —
there is no Alembic in the test run — so what is checked is the very function
upgrade() calls at container start.
"""
import importlib.util
from datetime import datetime
from pathlib import Path

from app.extensions import db
from app.models.user import User
from app.models.voyage import Voyage
from app.utils import crypto

MIGRATION = (
    Path(__file__).resolve().parents[1] / "migrations" / "versions"
    / "b4c5d6e7f8a9_erase_voyage_billets.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("erase_voyage_billets", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(email, token):
    """A voyage whose column holds `token` exactly, written past the model's
    setter — which would itself drop the billets this test needs to find."""
    user = User(email=email, password_hash="x", role="candidate", plan="free")
    db.session.add(user)
    db.session.commit()
    voyage = Voyage(user_id=user.id, consent_at=datetime.utcnow(), age_attested=True)
    db.session.add(voyage)
    db.session.commit()
    db.session.execute(
        db.text("UPDATE voyages SET responses_encrypted = :token WHERE id = :id"),
        {"token": token, "id": voyage.id},
    )
    db.session.commit()
    return voyage.id


def _column(voyage_id):
    return tuple(db.session.execute(
        db.text("SELECT responses_encrypted, updated_at FROM voyages WHERE id = :id"),
        {"id": voyage_id},
    ).first())


def test_the_migration_erases_billets_and_keeps_everything_else(app):
    with_billet = _row("billet@test.fr", crypto.encrypt_json({
        "answers": {"S0-01": True, "S1-1": ["B", "A"]},
        "billets": {"0": {"surprise": "je déteste le bureau"}},
    }))
    answers_only = _row("clean@test.fr", crypto.encrypt_json({"answers": {"S0-02": False}}))
    unreadable = _row("broken@test.fr", "not-a-fernet-token")
    before = {i: _column(i) for i in (with_billet, answers_only, unreadable)}

    rewritten = _migration().strip_billets(db.session.connection())
    db.session.commit()

    assert rewritten == 1
    token, stamp = _column(with_billet)
    assert crypto.decrypt_json(token) == {"answers": {"S0-01": True, "S1-1": ["B", "A"]}}
    assert stamp == before[with_billet][1]          # the stall rules' clock does not move
    assert _column(answers_only) == before[answers_only]
    assert _column(unreadable) == before[unreadable]   # skipped, never fatal


def test_the_migration_is_idempotent(app):
    _row("twice@test.fr", crypto.encrypt_json({"answers": {}, "billets": {"0": {"top3": "x"}}}))
    migration = _migration()

    assert migration.strip_billets(db.session.connection()) == 1
    db.session.commit()
    assert migration.strip_billets(db.session.connection()) == 0
