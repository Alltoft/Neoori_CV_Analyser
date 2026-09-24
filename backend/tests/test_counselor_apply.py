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


def test_an_admin_cannot_file_a_demande(client, app):
    """Deciding a demande rewrites user.role, so an admin holding one could be
    demoted out of their own dashboard with no way back in."""
    _user, headers = _authed(email="admin@test.com", role="admin")
    payload = {k: v for k, v in PAYLOAD.items() if k not in ("email", "password")}
    r = client.post("/api/counselor/apply", json=payload, headers=headers)
    assert r.status_code == 409
    assert CounselorProfile.query.count() == 0


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
