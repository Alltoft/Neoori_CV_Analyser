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
