"""Ownership checks on the analysis endpoints.

GET /analyses/<id> used to be fully open and returned the raw inputs blob —
CV text, name, location, and the health context parcours 3 collects. Any
caller with an id could read any analysis.
"""
import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db as _db
from app.models.analysis import Analysis
from app.models.user import User


def _user(email):
    u = User(email=email, password_hash="x")
    _db.session.add(u)
    _db.session.commit()
    return u


def _headers(user):
    token = create_access_token(identity=str(user.id), additional_claims={"role": "candidate"})
    return {"Authorization": f"Bearer {token}"}


def _analysis(owner=None):
    a = Analysis(
        user_id=owner.id if owner else None,
        inputs={"_path": "1", "cv_text": "confidentiel", "prenom": "Marie"},
        status="success",
    )
    _db.session.add(a)
    _db.session.commit()
    return a


def test_owner_can_read_their_own(client, app):
    owner = _user("owner@test.fr")
    a = _analysis(owner)
    res = client.get(f"/api/analyses/{a.id}", headers=_headers(owner))
    assert res.status_code == 200
    assert res.get_json()["analysis"]["inputs"]["cv_text"] == "confidentiel"


def test_another_user_cannot_read_it(client, app):
    owner = _user("owner2@test.fr")
    intruder = _user("intruder@test.fr")
    a = _analysis(owner)
    res = client.get(f"/api/analyses/{a.id}", headers=_headers(intruder))
    assert res.status_code == 403
    assert "cv_text" not in res.get_data(as_text=True)


def test_anonymous_caller_cannot_read_an_owned_analysis(client, app):
    owner = _user("owner3@test.fr")
    a = _analysis(owner)
    assert client.get(f"/api/analyses/{a.id}").status_code == 403


def test_ownerless_analysis_stays_readable(client, app):
    """The anonymous flow polls its own analysis before any account exists;
    the UUID is the capability there. Phase 1 removes this branch."""
    a = _analysis(owner=None)
    assert client.get(f"/api/analyses/{a.id}").status_code == 200


def test_another_user_cannot_delete_it(client, app):
    owner = _user("owner4@test.fr")
    intruder = _user("intruder2@test.fr")
    a = _analysis(owner)
    assert client.delete(f"/api/analyses/{a.id}", headers=_headers(intruder)).status_code == 403
    assert _db.session.get(Analysis, a.id) is not None


def test_another_user_cannot_burn_a_code_against_it(client, app):
    """Unlock regenerates and consumes a counselor code — it needs the same
    ownership gate as read."""
    owner = _user("owner5@test.fr")
    intruder = _user("intruder3@test.fr")
    a = _analysis(owner)
    res = client.post(f"/api/analyses/{a.id}/unlock", json={"code": "ABCD1234"},
                      headers=_headers(intruder))
    assert res.status_code == 403
