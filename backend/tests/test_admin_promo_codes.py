"""Admin promo codes (four-doors spec, decision 18) and /api/codes/check."""
from datetime import datetime, timedelta

from app.extensions import db
from app.models.counselor_code import CounselorCode
from app.services import code_service
from tests.helpers_doors import code, counselor

BASE = "/api/admin/counselor-codes"


def test_a_new_promo_code_is_one_use_and_ninety_days(client, admin_headers):
    res = client.post(BASE, json={"label": "Salon"}, headers=admin_headers)
    assert res.status_code == 201
    row = res.get_json()["code"]
    assert (row["kind"], row["max_uses"]) == ("promo", 1)
    expires = datetime.fromisoformat(row["expires_at"])
    assert abs(expires - (datetime.utcnow() + timedelta(days=90))) < timedelta(minutes=1)


def test_null_means_illimite(client, admin_headers):
    res = client.post(BASE, json={"label": "PM", "max_uses": None, "expires_in_days": None},
                      headers=admin_headers)
    row = res.get_json()["code"]
    assert (row["max_uses"], row["expires_at"]) == (None, None)


def test_patch_changes_an_existing_codes_limits(client, admin_headers, app):
    c = code(value="OLDCODE1")          # the 2026-10 prod code: NULL / NULL
    res = client.patch(f"{BASE}/{c.id}", json={"max_uses": 3, "expires_in_days": 30}, headers=admin_headers)
    assert res.status_code == 200
    assert res.get_json()["code"]["max_uses"] == 3
    assert client.patch(f"{BASE}/{c.id}", json={"max_uses": None}, headers=admin_headers) \
        .get_json()["code"]["max_uses"] is None
    assert client.patch(f"{BASE}/{c.id}", json={"max_uses": 0}, headers=admin_headers).status_code == 400


def test_revoke_sets_revoked_at_and_the_code_stops_working(client, admin_headers, app):
    c = code(value="REVOKE01")
    assert client.delete(f"{BASE}/{c.id}", headers=admin_headers).status_code == 200
    db.session.expire_all()
    assert db.session.get(CounselorCode, c.id).revoked_at is not None
    assert code_service.resolve("REVOKE01", "analysis") == (None, code_service.INVALID)


def test_the_list_says_kind_and_uses_per_kind(client, admin_headers, app):
    code(value="PROMO010")
    code(counselor(), value="CONS0010")
    rows = {r["code"]: r for r in client.get(BASE, headers=admin_headers).get_json()["codes"]}
    assert rows["PROMO010"]["kind"] == "promo" and rows["CONS0010"]["kind"] == "conseiller"
    assert rows["PROMO010"]["uses_by_kind"] == {"analysis": 0, "voyage": 0}


def test_check_says_the_kind(client, app):
    code(value="PROMO011")
    code(counselor(), value="CONS0011")
    assert client.post("/api/codes/check", json={"code": "promo-011"}).get_json() == {"kind": "promo"}
    assert client.post("/api/codes/check", json={"code": "cons 0011"}).get_json() == {"kind": "conseiller"}


def test_check_refuses_what_submit_would(client, app):
    code(counselor(status="revoked"), value="REVO0011")
    assert client.post("/api/codes/check", json={"code": "REVO0011"}).status_code == 400
    assert client.post("/api/codes/check", json={"code": ""}).status_code == 400
    assert client.post("/api/codes/check", json={"code": "NOPE0000"}).status_code == 400
