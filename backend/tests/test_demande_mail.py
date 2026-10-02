"""A new conseiller demande mails the admins once, when its address is proven
(transactional mails spec, 2026-10-02)."""
import logging
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.profile import Profile
from app.models.user import User
from app.services import demande_mail
from app.utils import auth_links

NEW_DEMANDE = "app.services.email_service.send_new_demande"
SEND = "app.services.email_service.resend.Emails.send"

# The demande form, without the account half (a signed-in applicant has one).
DEMANDE = {
    "structure": "Cap Emploi 31",
    "type_structure": "cap_emploi",
    "siret": "12345678901234",
    "adresse_rue": "12 rue des Lois",
    "adresse_code_postal": "31000",
    "adresse_ville": "Toulouse",
    "domaines": ["insertion_emploi"],
    "nom_complet": "Claire Martin",
    "fonction": "Conseillère en insertion",
    "telephone": "0561000000",
    "consent": True,
    "consent_donnees": True,
}
ACCOUNT = {"email": "claire@capemploi.fr", "password": "motdepasse1"}


def _admin(make_user, email="admin@neoori.tech", verified=True):
    return make_user(email=email, role="admin", verified=verified)


def _pending(make_user, email="claire@capemploi.fr"):
    """A verified account holding a pending demande."""
    user = make_user(email=email)
    db.session.add(CounselorProfile(user_id=user.id, structure="Cap Emploi 31",
                                    fonction="Conseillère", telephone="0561000000"))
    db.session.commit()
    return user


def _signed_in(user) -> dict:
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return {"Authorization": f"Bearer {token}"}


def _told(mock_new_demande) -> list[str]:
    return [c.args[0] for c in mock_new_demande.call_args_list]


def _apply_without_account(client) -> User:
    assert client.post("/api/counselor/apply", json={**DEMANDE, **ACCOUNT}).status_code == 201
    return User.query.filter_by(email=ACCOUNT["email"]).one()


def _verify(client, user):
    return client.post("/api/auth/verify-email", json={
        "token": auth_links.make_verify_token(user), "password": ACCOUNT["password"],
    })


def _reset(client, user):
    return client.post("/api/auth/reset-password", json={
        "token": auth_links.make_reset_token(user), "password": "nouveau-mdp1",
    })


# ── the three doors into the queue ───────────────────────────────────────────

def test_a_signed_in_applicant_reaches_the_admins_at_once(client, make_user):
    admin = _admin(make_user)
    applicant = make_user(email="claire@capemploi.fr")       # verified
    with patch(NEW_DEMANDE) as told:
        r = client.post("/api/counselor/apply", json=DEMANDE, headers=_signed_in(applicant))
    assert r.status_code == 201
    assert _told(told) == [admin.email]


def test_a_new_account_demande_waits_for_its_address(client, make_user):
    admin = _admin(make_user)
    with patch(NEW_DEMANDE) as told:
        applicant = _apply_without_account(client)
    told.assert_not_called()

    with patch(NEW_DEMANDE) as told:
        assert _verify(client, applicant).status_code == 200
    assert _told(told) == [admin.email]

    # A second use of the link is a login: nobody is told twice.
    with patch(NEW_DEMANDE) as told:
        assert _verify(client, applicant).status_code == 200
    told.assert_not_called()


def test_a_reset_that_proves_the_address_tells_the_admins(client, make_user):
    admin = _admin(make_user)
    applicant = _apply_without_account(client)
    with patch(NEW_DEMANDE) as told:
        assert _reset(client, applicant).status_code == 200
    assert _told(told) == [admin.email]


def test_a_reset_of_a_proven_address_tells_nobody_again(client, make_user):
    _admin(make_user)
    applicant = _pending(make_user)                            # already verified
    with patch(NEW_DEMANDE) as told:
        assert _reset(client, applicant).status_code == 200
    told.assert_not_called()


def test_marking_an_address_verified_by_hand_tells_nobody(client, admin_headers, make_user):
    """« Marquer comme vérifié » is the fourth way an address gets proven, and
    deliberately not a door: the admin who clicked is already in the queue."""
    _admin(make_user)
    applicant = _apply_without_account(client)
    with patch(NEW_DEMANDE) as told:
        r = client.post(f"/api/admin/users/{applicant.id}/verify-email", headers=admin_headers)
    assert r.status_code == 200
    told.assert_not_called()


# ── what counts as news, and who hears it ────────────────────────────────────

@pytest.mark.parametrize("status", ["approved", "rejected", "revoked"])
def test_only_a_pending_demande_is_news(app, make_user, status):
    _admin(make_user)
    user = make_user(email="claire@capemploi.fr")
    db.session.add(CounselorProfile(user_id=user.id, structure="X", fonction="Y",
                                    telephone="0102030405", status=status))
    db.session.commit()
    with patch(NEW_DEMANDE) as told:
        demande_mail.notify_if_visible(user)
    told.assert_not_called()


def test_a_candidate_without_a_demande_is_not_news(app, make_user):
    _admin(make_user)
    with patch(NEW_DEMANDE) as told:
        demande_mail.notify_if_visible(make_user(email="marie@test.fr"))
    told.assert_not_called()


def test_every_verified_admin_is_told_and_no_one_else(app, make_user):
    _admin(make_user, "a1@neoori.tech")
    _admin(make_user, "a2@neoori.tech")
    _admin(make_user, "a3@neoori.tech", verified=False)
    make_user(email="candidat@test.fr")
    applicant = _pending(make_user)
    with patch(NEW_DEMANDE) as told:
        demande_mail.notify_if_visible(applicant)
    assert sorted(_told(told)) == ["a1@neoori.tech", "a2@neoori.tech"]


def test_one_failed_send_does_not_cost_the_other_admin_their_mail(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    _admin(make_user, "a1@neoori.tech")
    _admin(make_user, "a2@neoori.tech")
    applicant = _pending(make_user)
    with patch(SEND, side_effect=[RuntimeError("bounce"), {"id": "2"}]) as mock_send:
        demande_mail.notify_if_visible(applicant)
    assert mock_send.call_count == 2


def test_no_verified_admin_is_a_warning_not_a_crash(app, make_user, caplog):
    applicant = _pending(make_user)
    with patch(NEW_DEMANDE) as told, caplog.at_level(logging.WARNING):
        demande_mail.notify_if_visible(applicant)
    told.assert_not_called()
    assert "no verified admin" in caplog.text


def test_the_admin_mail_carries_nothing_of_the_applicant(client, app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    admin = _admin(make_user)
    applicant = make_user(email="claire@capemploi.fr")
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        client.post("/api/counselor/apply", json=DEMANDE, headers=_signed_in(applicant))
    mail = mock_send.call_args[0][0]
    assert mail["to"] == [admin.email]
    for detail in ("Claire Martin", "Cap Emploi 31", "0561000000", "12345678901234",
                   "Toulouse", "claire@capemploi.fr"):
        assert detail not in mail["html"]
        assert detail not in mail["text"]


def test_a_failed_admin_lookup_does_not_block_the_verification(client, make_user):
    # Review Focus 3: the person proved their address. A 500 here would keep
    # them out over a mail they never asked for.
    _admin(make_user)
    applicant = _apply_without_account(client)

    def poison_session(*args, **kwargs):
        # Inject a constraint violation to poison the session, like a dropped
        # connection would. The flush fails; the session is left pending
        # rollback. Without db.session.rollback() in notify_if_visible's
        # except, the route's next query (_landing) raises PendingRollbackError.
        db.session.add(User(email=None, password_hash="x"))
        db.session.flush()

    with patch("app.services.demande_mail.CounselorProfile") as broken:
        broken.query.filter_by.side_effect = poison_session
        r = _verify(client, applicant)
    assert r.status_code == 200
    assert "access_token_cookie" in " ".join(r.headers.getlist("Set-Cookie"))
    # The verification itself survived the failed admin lookup.
    db.session.expire_all()
    assert db.session.get(User, applicant.id).email_verified_at is not None


# ── ADMIN_NOTIFY_EMAIL: production names the inbox ───────────────────────────

def test_the_setting_names_the_only_recipients(app, make_user):
    """The shared admin login has no mailbox (neoori.dev has no MX record), so
    production names a real inbox; a verified admin outside the list hears
    nothing."""
    app.config["ADMIN_NOTIFY_EMAILS"] = ["ouakouriimran@gmail.com"]
    _admin(make_user)
    applicant = _pending(make_user)
    with patch(NEW_DEMANDE) as told:
        demande_mail.notify_if_visible(applicant)
    assert _told(told) == ["ouakouriimran@gmail.com"]


def test_a_named_address_with_an_account_is_greeted_by_its_prenom(app, make_user):
    app.config["ADMIN_NOTIFY_EMAILS"] = ["boss@neoori.tech"]
    boss = make_user(email="boss@neoori.tech", role="admin")
    db.session.add(Profile(user_id=boss.id, prenom="Imran"))
    db.session.commit()
    applicant = _pending(make_user)
    with patch(NEW_DEMANDE) as told:
        demande_mail.notify_if_visible(applicant)
    assert told.call_args_list[0].args == ("boss@neoori.tech", "Imran")


def test_the_setting_does_not_skip_the_queue_rules(app, make_user):
    app.config["ADMIN_NOTIFY_EMAILS"] = ["ouakouriimran@gmail.com"]
    with patch(NEW_DEMANDE) as told:
        demande_mail.notify_if_visible(make_user(email="marie@test.fr"))   # no demande
    told.assert_not_called()


def test_the_setting_reads_a_comma_separated_list():
    from app.config import _addresses

    assert _addresses(" Ouakouriimran@Gmail.com , ,pm@neoori.tech ") == [
        "ouakouriimran@gmail.com", "pm@neoori.tech",
    ]
    assert _addresses("") == []
