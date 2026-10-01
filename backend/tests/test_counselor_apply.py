"""The demande, and the waiting room it puts someone in.

The rule this file exists to pin: a pending conseiller is role=candidate. A
pending account holding role=counselor would pass every /api/voyage/c/<token>
guard before anyone had reviewed it.
"""
from datetime import timedelta

from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User

PAYLOAD = {
    # Connexion — one email since the PM's 2026-09-30 form merged the
    # professional address into the account address.
    "email": "conseiller@capemploi.fr",
    "password": "motdepasse1",
    # Votre structure
    "structure": "Cap Emploi 31",
    "type_structure": "cap_emploi",
    "siret": "12345678901234",
    "adresse_rue": "12 rue des Lois",
    "adresse_code_postal": "31000",
    "adresse_ville": "Toulouse",
    "domaines": ["insertion_emploi", "handicap"],
    # Vous
    "nom_complet": "Claire Martin",
    "fonction": "Conseillère en insertion",
    "telephone": "0561000000",
    # Validation — two ticks now
    "consent": True,
    "consent_donnees": True,
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


def test_apply_requires_every_marked_field(client, app):
    for missing in (
        "structure", "type_structure", "adresse_rue", "adresse_code_postal",
        "adresse_ville", "nom_complet", "fonction", "telephone",
    ):
        payload = {**PAYLOAD, missing: ""}
        r = client.post("/api/counselor/apply", json=payload)
        assert r.status_code == 400, missing


def test_apply_requires_both_ticks(client, app):
    """Two separate consents since the 2026-09-30 form: the CGV, and the
    processing of the applicant's own professional data."""
    for tick in ("consent", "consent_donnees"):
        r = client.post("/api/counselor/apply", json={**PAYLOAD, tick: False})
        assert r.status_code == 400, tick


def test_apply_refuses_an_unknown_structure_type(client, app):
    r = client.post("/api/counselor/apply", json={**PAYLOAD, "type_structure": "banque"})
    assert r.status_code == 400


def test_autre_requires_the_free_text(client, app):
    r = client.post("/api/counselor/apply", json={**PAYLOAD, "type_structure": "autre"})
    assert r.status_code == 400

    r = client.post("/api/counselor/apply", json={
        **PAYLOAD, "type_structure": "autre", "type_structure_autre": "Fondation",
    })
    assert r.status_code == 201


def test_siret_must_be_fourteen_digits(client, app):
    for bad in ("123", "1234567890123456", "abcdefghijklmn"):
        r = client.post("/api/counselor/apply", json={**PAYLOAD, "siret": bad})
        assert r.status_code == 400, bad


def test_siret_accepts_spaced_input_and_stores_digits(client, app):
    r = client.post("/api/counselor/apply", json={**PAYLOAD, "siret": "123 456 789 01234"})
    assert r.status_code == 201
    assert CounselorProfile.query.one().siret == "12345678901234"


def test_siret_is_required_except_for_an_independant(client, app):
    r = client.post("/api/counselor/apply", json={**PAYLOAD, "siret": ""})
    assert r.status_code == 400

    r = client.post("/api/counselor/apply", json={
        **PAYLOAD, "siret": "", "type_structure": "independant",
    })
    assert r.status_code == 201
    assert CounselorProfile.query.one().siret is None


def test_an_independant_who_types_a_siret_is_still_checked(client, app):
    r = client.post("/api/counselor/apply", json={
        **PAYLOAD, "type_structure": "independant", "siret": "42",
    })
    assert r.status_code == 400


def test_at_least_one_domaine_is_required(client, app):
    for bad in ([], ["pilotage"], "insertion_emploi", None):
        r = client.post("/api/counselor/apply", json={**PAYLOAD, "domaines": bad})
        assert r.status_code == 400, bad


def test_unknown_domaines_are_dropped_rather_than_refused(client, app):
    r = client.post("/api/counselor/apply", json={
        **PAYLOAD, "domaines": ["handicap", "pilotage"],
    })
    assert r.status_code == 201
    assert CounselorProfile.query.one().domaines == ["handicap"]


def test_the_new_fields_are_stored_and_returned(client, app):
    r = client.post("/api/counselor/apply", json=PAYLOAD)
    assert r.status_code == 201
    body = r.get_json()["profile"]
    assert body["nom_complet"] == "Claire Martin"
    assert body["type_structure"] == "cap_emploi"
    assert body["adresse_ville"] == "Toulouse"
    assert body["domaines"] == ["insertion_emploi", "handicap"]


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


def test_a_stale_token_does_not_block_an_anonymous_demande(client, app):
    """optional=True swallows only a MISSING token. A visitor whose session
    lapsed still carries a cookie, and the public form must still work."""
    expired = create_access_token(
        identity="ghost",
        additional_claims={"role": "candidate"},
        expires_delta=timedelta(seconds=-1),
    )
    r = client.post(
        "/api/counselor/apply",
        json=PAYLOAD,
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert r.status_code == 201
    assert r.get_json()["user"]["email"] == PAYLOAD["email"]


def test_a_new_account_demande_opens_no_session(client, app):
    app.debug = False   # FLASK_DEBUG in a developer's shell must not flip mail_sent
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
