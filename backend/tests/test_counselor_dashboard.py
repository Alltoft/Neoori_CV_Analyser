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
    # consent_at is NOT NULL with no default (models/voyage.py:71).
    db.session.add(Voyage(
        user_id=candidate.id, validated_by_id=user.id, consent_at=datetime.utcnow(),
    ))
    db.session.add(Voyage(user_id=candidate.id, consent_at=datetime.utcnow()))  # not validated
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
    mine, headers = _conseiller(email="mine@test.com")
    other, _ = _conseiller(email="other@test.com")

    my_code = CounselorCode(label="à moi", owner_id=mine.id)
    their_code = CounselorCode(label="pas à moi", owner_id=other.id)
    db.session.add_all([my_code, their_code])
    db.session.commit()

    karim = _beneficiaire("Karim", "karim@test.com")
    db.session.add(CodeRedemption(
        code_id=my_code.id, user_id=karim.id, target_type="voyage", target_id="v-1",
    ))
    db.session.add(CodeRedemption(
        code_id=their_code.id, target_type="voyage", target_id="v-9",
    ))
    db.session.commit()

    rows = client.get("/api/counselor/beneficiaires", headers=headers).get_json()["beneficiaires"]
    assert len(rows) == 1
    assert rows[0]["prenom"] == "Karim"


def test_stats_ignore_another_conseillers_activity(client, app):
    mine, headers = _conseiller(email="mine@test.com")
    other, _ = _conseiller(email="other@test.com")

    my_code = CounselorCode(label="à moi", owner_id=mine.id, max_uses=1)
    their_code = CounselorCode(label="pas à moi", owner_id=other.id, max_uses=1)
    db.session.add_all([my_code, their_code])
    db.session.commit()

    db.session.add(CodeRedemption(
        code_id=their_code.id, target_type="voyage", target_id="v-9",
    ))
    candidate = _beneficiaire("Sonia", "sonia@test.com")
    db.session.add(Voyage(
        user_id=candidate.id, validated_by_id=other.id, consent_at=datetime.utcnow(),
    ))
    db.session.commit()

    stats = client.get("/api/counselor/stats", headers=headers).get_json()
    assert stats["beneficiaires"] == 0
    assert stats["accompagnements"] == 0
    assert stats["codes_crees"] == 1
