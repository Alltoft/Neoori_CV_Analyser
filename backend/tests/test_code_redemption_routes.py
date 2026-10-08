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


def _analysis(owner):
    a = Analysis(
        user_id=owner.id,
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
def test_analysis_unlock_logs_the_person(mock_start, client, app):
    """/unlock is the owner's alone (four-doors spec, decision 22), so the
    redemption always names the account that spent the code."""
    user, headers = _candidate()
    a = _analysis(user)
    c = _code()
    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": c.code}, headers=headers)
    assert r.status_code == 200

    row = CodeRedemption.query.filter_by(code_id=c.id).one()
    assert row.user_id == user.id
    assert row.target_type == "analysis"
    assert row.target_id == a.id


@patch("app.services.unlock_service.start_analysis")
def test_analysis_unlock_refuses_an_exhausted_code(mock_start, client, app):
    user, headers = _candidate()
    a = _analysis(user)
    c = _code(max_uses=1)
    db.session.add(CodeRedemption(code_id=c.id, target_type="analysis", target_id="a-0", slot=1))
    db.session.commit()

    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": c.code}, headers=headers)
    assert r.status_code == 400
    assert r.get_json()["error"] == "Ce code a atteint sa limite d'utilisation."
    mock_start.assert_not_called()


@patch("app.services.unlock_service.start_analysis")
def test_a_voyage_use_leaves_the_analysis_unlock_open(mock_start, client, app):
    """Uses are counted per kind (ruling 10): a single-use code already spent
    on a voyage still opens one analysis."""
    user, headers = _candidate()
    a = _analysis(user)
    c = _code(max_uses=1)
    db.session.add(CodeRedemption(code_id=c.id, target_type="voyage", target_id="v-0", slot=1))
    db.session.commit()

    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": c.code}, headers=headers)
    assert r.status_code == 200
    mock_start.assert_called_once()


@patch("app.services.unlock_service.start_analysis")
def test_analysis_unlock_refuses_an_expired_code(mock_start, client, app):
    user, headers = _candidate()
    a = _analysis(user)
    c = _code(expires_at=datetime.utcnow() - timedelta(days=1))
    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": c.code}, headers=headers)
    assert r.status_code == 400
    assert r.get_json()["error"] == "Ce code a expiré."


def test_voyage_unlock_logs_the_person(client, app):
    user, headers = _candidate()
    # consent_at is NOT NULL with no default (models/voyage.py:71) — omit it and
    # the commit dies on IntegrityError before any assertion runs.
    v = Voyage(user_id=user.id, consent_at=datetime.utcnow())
    db.session.add(v)
    db.session.commit()
    c = _code()

    r = client.post("/api/voyage/unlock", json={"code": c.code}, headers=headers)
    assert r.status_code == 200

    row = CodeRedemption.query.filter_by(code_id=c.id).one()
    assert row.user_id == user.id
    assert row.target_type == "voyage"
    assert row.target_id == v.id


def test_voyage_unlock_refuses_an_expired_code(client, app):
    user, headers = _candidate()
    # consent_at is NOT NULL with no default (models/voyage.py:71) — omit it and
    # the commit dies on IntegrityError before any assertion runs.
    v = Voyage(user_id=user.id, consent_at=datetime.utcnow())
    db.session.add(v)
    db.session.commit()
    c = _code(expires_at=datetime.utcnow() - timedelta(days=1))

    r = client.post("/api/voyage/unlock", json={"code": c.code}, headers=headers)
    assert r.status_code == 400
    assert r.get_json()["error"] == "Ce code a expiré."
    db.session.refresh(v)
    assert v.counselor_code_id is None


def test_voyage_unlock_refuses_an_exhausted_code(client, app):
    user, headers = _candidate()
    # consent_at is NOT NULL with no default (models/voyage.py:71) — omit it and
    # the commit dies on IntegrityError before any assertion runs.
    v = Voyage(user_id=user.id, consent_at=datetime.utcnow())
    db.session.add(v)
    db.session.commit()
    c = _code(max_uses=1)
    db.session.add(CodeRedemption(code_id=c.id, target_type="voyage", target_id="v-0", slot=1))
    db.session.commit()

    r = client.post("/api/voyage/unlock", json={"code": c.code}, headers=headers)
    assert r.status_code == 400
    assert r.get_json()["error"] == "Ce code a atteint sa limite d'utilisation."
    db.session.refresh(v)
    assert v.counselor_code_id is None


def test_an_analysis_use_leaves_the_voyage_unlock_open(client, app):
    """The other direction of ruling 10: a single-use code already spent on an
    analysis still opens one voyage."""
    user, headers = _candidate()
    v = Voyage(user_id=user.id, consent_at=datetime.utcnow())
    db.session.add(v)
    db.session.commit()
    c = _code(max_uses=1)
    db.session.add(CodeRedemption(code_id=c.id, target_type="analysis", target_id="a-0", slot=1))
    db.session.commit()

    r = client.post("/api/voyage/unlock", json={"code": c.code}, headers=headers)
    assert r.status_code == 200
    db.session.refresh(v)
    assert v.counselor_code_id == c.id
