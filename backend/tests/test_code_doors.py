"""Codes under the four doors (four-doors spec, decisions 17-23)."""
from datetime import datetime
from unittest.mock import patch

from app.extensions import db
from app.models.analysis import Analysis
from app.models.code_redemption import CodeRedemption
from app.models.voyage import STATUS_TERMINE, Voyage
from app.services import code_service
from tests.helpers_doors import bearer, code, counselor, user


def test_kind_is_derived_from_the_owner(app):
    assert code_service.kind(code(value="PROMO001")) == "promo"
    assert code_service.kind(code(counselor(), value="CONS0001")) == "conseiller"


def test_a_single_use_conseiller_code_opens_one_analysis_and_one_voyage(app):
    c = code(counselor(), max_uses=1)
    found, refusal = code_service.resolve("ABCD1234", "analysis")
    assert refusal is None
    assert code_service.redeem(found, user_id=None, target_type="analysis", target_id="a1") is None

    assert code_service.resolve("ABCD1234", "analysis") == (None, code_service.EXHAUSTED)
    found, refusal = code_service.resolve("ABCD1234", "voyage")
    assert refusal is None and found.id == c.id


def test_a_code_whose_counselor_is_not_approved_is_invalid_everywhere(app):
    for status, value in (("pending", "PEND0001"), ("rejected", "REJE0001"), ("revoked", "REVO0001")):
        code(counselor(f"{status}@test.fr", status=status), value=value)
        for kind in ("analysis", "voyage"):
            assert code_service.resolve(value, kind) == (None, code_service.INVALID)


def test_a_promo_code_has_no_owner_to_approve(app):
    code(value="PROMO002")
    found, refusal = code_service.resolve("PROMO002", "analysis")
    assert refusal is None and found is not None


def test_the_wrong_door_is_answered_with_the_right_one(app):
    code(counselor(), value="CONS0002")
    code(value="PROMO003")
    _, refusal = code_service.resolve_for_door("CONS0002", "promo", "u1")
    assert (refusal.status, refusal.door) == (409, "advisor")
    _, refusal = code_service.resolve_for_door("PROMO003", "advisor", None)
    assert (refusal.status, refusal.door) == (409, "promo")


def test_codes_are_accepted_as_people_type_them(app):
    # normalize() drops spaces and dashes and upper-cases, so a door accepts a
    # code however it was typed.
    code(counselor(), value="ABCD1234")
    for typed in ("abcd-1234", "ABCD 1234", " abcd1234 "):
        found, refusal = code_service.resolve_for_door(typed, "advisor", None)
        assert refusal is None and found is not None, typed


def test_a_promo_code_is_once_per_account(app):
    c = code(value="PROMO004", max_uses=10)
    u = user()
    assert code_service.redeem(c, user_id=u.id, target_type="analysis", target_id="a1") is None
    _, refusal = code_service.resolve_for_door("PROMO004", "promo", u.id)
    assert refusal.message == code_service.ALREADY_USED
    # And the database says the same, should the check above ever be skipped.
    assert code_service.redeem(c, user_id=u.id, target_type="analysis", target_id="a2") \
        == code_service.ALREADY_USED


def test_two_requests_for_the_last_place_give_one_redemption(app):
    """The first count is stale (MySQL REPEATABLE READ): the slot key refuses
    the second insert, the retry recounts, and the answer is EXHAUSTED."""
    c = code(counselor(), max_uses=1)
    db.session.add(CodeRedemption(code_id=c.id, target_type="analysis", target_id="a0", slot=1))
    db.session.commit()

    real = code_service.redemption_count
    calls = {"n": 0}

    def stale_once(code_id, target_type=None):
        calls["n"] += 1
        return 0 if calls["n"] == 1 else real(code_id, target_type)

    with patch.object(code_service, "redemption_count", side_effect=stale_once):
        assert code_service.redeem(c, user_id=None, target_type="analysis", target_id="a1") \
            == code_service.EXHAUSTED
    assert CodeRedemption.query.filter_by(code_id=c.id).count() == 1


@patch("app.services.unlock_service.start_analysis")
def test_debloquer_takes_a_promo_code_on_the_owners_free_report(_start, client, app):
    owner = user()
    analysis = Analysis(user_id=owner.id, status="success", door="account",
                        inputs={"_path": "1", "_tier": "free"}, output={"1": {}})
    db.session.add(analysis)
    db.session.commit()
    code(value="PROMO005")

    res = client.post(f"/api/analyses/{analysis.id}/unlock", json={"code": "promo-005"},
                      headers=bearer(owner))
    assert res.status_code == 200, res.data
    assert db.session.get(Analysis, analysis.id).unlock_method == "code"


def test_debloquer_refuses_a_conseiller_code(client, app):
    owner = user()
    analysis = Analysis(user_id=owner.id, status="success", door="account",
                        inputs={"_path": "1", "_tier": "free"}, output={"1": {}})
    db.session.add(analysis)
    db.session.commit()
    code(counselor(), value="CONS0003")

    res = client.post(f"/api/analyses/{analysis.id}/unlock", json={"code": "CONS0003"},
                      headers=bearer(owner))
    assert res.status_code == 409
    assert res.get_json()["error"] == code_service.NOT_FOR_UNLOCK
    assert CodeRedemption.query.count() == 0


def test_debloquer_needs_the_owner(client, app):
    owner, other = user(), user("other@test.fr")
    analysis = Analysis(user_id=owner.id, status="success", inputs={"_path": "1"}, output={"1": {}})
    db.session.add(analysis)
    db.session.commit()
    code(value="PROMO006")
    assert client.post(f"/api/analyses/{analysis.id}/unlock", json={"code": "PROMO006"}).status_code == 401
    assert client.post(f"/api/analyses/{analysis.id}/unlock", json={"code": "PROMO006"},
                       headers=bearer(other)).status_code == 403


def test_the_voyage_refuses_a_revoked_counselors_code(client, app):
    candidate = user()
    db.session.add(Voyage(user_id=candidate.id, consent_at=datetime.utcnow(), age_attested=True))
    db.session.commit()
    code(counselor(status="revoked"), value="REVO0002")
    res = client.post("/api/voyage/unlock", json={"code": "REVO0002"}, headers=bearer(candidate))
    assert res.status_code == 400
    assert res.get_json()["error"] == code_service.INVALID


def test_refusal_needs_a_finished_free_report(app):
    from app.services.unlock_service import refusal
    base = dict(inputs={"_path": "1"}, user_id=None)
    assert refusal(Analysis(status="error", **base)) is not None
    assert refusal(Analysis(status="running", **base)) is not None
    assert refusal(Analysis(status="success", output={"5": {}}, **base)) is not None
    assert refusal(Analysis(status="success", unlock_method="code", **base)) is not None
    assert refusal(Analysis(status="success", output={"1": {}}, **base)) is None


def test_erasing_a_voyage_unlinks_its_redemption(client, app):
    candidate = user()
    voyage = Voyage(user_id=candidate.id, consent_at=datetime.utcnow(), age_attested=True)
    db.session.add(voyage)
    db.session.commit()
    c = code(counselor(), max_uses=5, value="CONS0012")
    code_service.redeem(c, user_id=candidate.id, target_type="voyage", target_id=voyage.id)

    assert client.delete("/api/voyage", headers=bearer(candidate)).status_code == 200
    redemption = CodeRedemption.query.one()
    assert redemption.user_id is None          # the use stays counted


def test_a_retake_cannot_spend_the_same_code_twice(client, app):
    """The per-account key holds for voyages too: the second voyage of an
    account that already spent this code is refused, and stays locked."""
    candidate = user()
    db.session.add(Voyage(user_id=candidate.id, consent_at=datetime.utcnow(),
                          age_attested=True, status=STATUS_TERMINE))
    db.session.commit()
    code(counselor(), max_uses=5, value="CONS0013")
    headers = bearer(candidate)
    assert client.post("/api/voyage/unlock", json={"code": "CONS0013"}, headers=headers).status_code == 200

    retake = Voyage(user_id=candidate.id, consent_at=datetime.utcnow(), age_attested=True)
    db.session.add(retake)
    db.session.commit()
    res = client.post("/api/voyage/unlock", json={"code": "CONS0013"}, headers=headers)
    assert res.status_code == 400
    assert res.get_json()["error"] == code_service.ALREADY_USED
    assert db.session.get(Voyage, retake.id).counselor_code_id is None
    assert CodeRedemption.query.count() == 1


def test_erasing_a_voyage_lets_the_account_unlock_a_new_one_with_the_code(client, app):
    """The reason the redemption is unlinked: the use stays spent, and the
    per-account key no longer refuses the person their next voyage."""
    candidate = user()
    db.session.add(Voyage(user_id=candidate.id, consent_at=datetime.utcnow(), age_attested=True))
    db.session.commit()
    c = code(counselor(), max_uses=5, value="CONS0014")
    headers = bearer(candidate)
    assert client.post("/api/voyage/unlock", json={"code": "CONS0014"}, headers=headers).status_code == 200
    assert client.delete("/api/voyage", headers=headers).status_code == 200
    assert code_service.redemption_count(c.id, "voyage") == 1       # still spent

    db.session.add(Voyage(user_id=candidate.id, consent_at=datetime.utcnow(), age_attested=True))
    db.session.commit()
    res = client.post("/api/voyage/unlock", json={"code": "CONS0014"}, headers=headers)
    assert res.status_code == 200, res.data
    assert code_service.redemption_count(c.id, "voyage") == 2


def _unlockable_voyage():
    candidate = user()
    voyage = Voyage(user_id=candidate.id, consent_at=datetime.utcnow(), age_attested=True)
    db.session.add(voyage)
    db.session.commit()
    return candidate, voyage


def test_the_voyage_unlock_and_its_redemption_land_in_one_commit(client, app):
    """redeem()'s commit carries the unlock: there is no moment where a use is
    spent and the voyage is still locked."""
    candidate, voyage = _unlockable_voyage()
    c = code(counselor(), max_uses=2, value="CONS0015")

    with patch.object(db.session, "commit", wraps=db.session.commit) as commit:
        res = client.post("/api/voyage/unlock", json={"code": "CONS0015"}, headers=bearer(candidate))

    assert res.status_code == 200, res.data
    assert commit.call_count == 1
    assert db.session.get(Voyage, voyage.id).counselor_code_id == c.id
    redemption = CodeRedemption.query.one()
    assert (redemption.target_id, redemption.slot) == (voyage.id, 1)


def test_a_retried_redemption_still_unlocks_the_voyage(client, app):
    """When another request took the slot first, redeem() rolls back and
    commits only the redemption on its retry. The unlock rode on the commit
    that was rolled back, so the route has to finish it."""
    candidate, voyage = _unlockable_voyage()
    c = code(counselor(), max_uses=2, value="CONS0016")
    db.session.add(CodeRedemption(code_id=c.id, target_type="voyage", target_id="v-other", slot=1))
    db.session.commit()

    real_resolve, real_count = code_service.resolve, code_service.redemption_count
    state = {"stale_next": False, "stale_served": False}

    def resolve_then_go_stale(code_str, target_type):
        found = real_resolve(code_str, target_type)
        state["stale_next"] = True          # redeem()'s first read follows
        return found

    def count(code_id, target_type=None):
        if state["stale_next"]:
            state["stale_next"], state["stale_served"] = False, True
            return 0                        # a snapshot from before slot 1 was taken
        return real_count(code_id, target_type)

    with patch.object(code_service, "resolve", side_effect=resolve_then_go_stale), \
            patch.object(code_service, "redemption_count", side_effect=count):
        res = client.post("/api/voyage/unlock", json={"code": "CONS0016"}, headers=bearer(candidate))

    assert res.status_code == 200, res.data
    assert state["stale_served"]            # the first attempt did collide on slot 1
    assert res.get_json()["voyage"]["has_code"] is True
    assert db.session.get(Voyage, voyage.id).counselor_code_id == c.id
    assert sorted(r.slot for r in CodeRedemption.query.filter_by(code_id=c.id)) == [1, 2]


def test_a_refusal_after_the_check_leaves_the_voyage_locked(client, app):
    """redeem() can still refuse once resolve() has said yes: the last place
    went in between. The unlock set ahead of the redemption must not outlive
    that refusal."""
    candidate, voyage = _unlockable_voyage()
    c = code(counselor(), max_uses=1, value="CONS0017")
    code_id = c.id

    real_resolve = code_service.resolve

    def resolve_then_lose_the_place(code_str, target_type):
        found = real_resolve(code_str, target_type)
        db.session.add(CodeRedemption(code_id=code_id, target_type="voyage", target_id="v-other", slot=1))
        db.session.commit()
        return found

    with patch.object(code_service, "resolve", side_effect=resolve_then_lose_the_place):
        res = client.post("/api/voyage/unlock", json={"code": "CONS0017"}, headers=bearer(candidate))

    assert res.status_code == 400
    assert res.get_json()["error"] == code_service.EXHAUSTED
    db.session.expire_all()
    assert db.session.get(Voyage, voyage.id).counselor_code_id is None
    assert CodeRedemption.query.count() == 1                 # the other request's
