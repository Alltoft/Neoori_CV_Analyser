"""The admin's side of email verification (spec decisions 15 and 16)."""
import re

from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User

REFRESH_COOKIE = re.compile(r"refresh_token_cookie=([^;]+)")


def _demande(make_user, email, verified):
    user = make_user(email=email, verified=verified)
    profile = CounselorProfile(
        user_id=user.id, structure="Cap Emploi 31", fonction="Conseillère", telephone="0561000000",
    )
    db.session.add(profile)
    db.session.commit()
    return user, profile


def _verify_by_admin(client, admin_headers, user):
    return client.post(f"/api/admin/users/{user.id}/verify-email", headers=admin_headers)


def test_the_admin_marks_an_address_verified(client, admin_headers, make_user):
    user = make_user(email="test@test.fr", verified=False)
    res = _verify_by_admin(client, admin_headers, user)
    assert res.status_code == 200
    assert res.get_json()["user"]["email_verified"] is True


def test_marking_twice_keeps_the_first_timestamp(client, admin_headers, make_user):
    user = make_user(email="twice@test.fr", verified=False)
    _verify_by_admin(client, admin_headers, user)
    db.session.expire_all()
    first = db.session.get(User, user.id).email_verified_at
    _verify_by_admin(client, admin_headers, user)
    db.session.expire_all()
    assert db.session.get(User, user.id).email_verified_at == first


def test_a_candidate_cannot_mark_an_address(client, make_user):
    target = make_user(email="cible@test.fr", verified=False)
    candidate = make_user(email="curieux@test.fr")
    token = create_access_token(identity=str(candidate.id), additional_claims={"role": "candidate"})
    res = client.post(f"/api/admin/users/{target.id}/verify-email",
                      headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_a_manually_verified_account_logs_in_with_a_working_refresh(client, admin_headers, make_user):
    # Review Focus 5: the refresh token login mints must actually refresh.
    user = make_user(email="manuel@test.fr", verified=False)
    creds = {"email": "manuel@test.fr", "password": "motdepasse1"}
    assert client.post("/api/auth/login", json=creds).status_code == 403
    _verify_by_admin(client, admin_headers, user)
    login = client.post("/api/auth/login", json=creds)
    assert login.status_code == 200
    match = REFRESH_COOKIE.search(" ".join(login.headers.getlist("Set-Cookie")))
    assert match, "login set no refresh_token_cookie"
    # TestingConfig reads JWTs from headers, so the minted token is replayed
    # as a Bearer header.
    refreshed = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {match.group(1)}"})
    assert refreshed.status_code == 200
    assert "access_token_cookie" in " ".join(refreshed.headers.getlist("Set-Cookie"))


def test_the_users_list_carries_the_flag(client, admin_headers, make_user):
    make_user(email="flag@test.fr", verified=False)
    users = client.get("/api/admin/users", headers=admin_headers).get_json()["users"]
    assert {u["email"]: u["email_verified"] for u in users}["flag@test.fr"] is False


def test_unverified_demandes_stay_out_of_the_queue(client, admin_headers, make_user):
    _demande(make_user, "vu@test.fr", verified=True)
    _demande(make_user, "pasvu@test.fr", verified=False)
    rows = client.get("/api/admin/counselor-applications", headers=admin_headers).get_json()["applications"]
    emails = {row["user"]["email"] for row in rows}
    assert emails == {"vu@test.fr"}


def test_an_unverified_demande_cannot_be_approved(client, admin_headers, make_user):
    _user, profile = _demande(make_user, "pasvu@test.fr", verified=False)
    res = client.post(f"/api/admin/counselor-applications/{profile.id}/approve",
                      json={}, headers=admin_headers)
    assert res.status_code == 409
    db.session.expire_all()
    assert db.session.get(CounselorProfile, profile.id).status == "pending"
