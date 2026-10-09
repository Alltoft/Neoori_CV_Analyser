"""The submit, per door (four-doors spec, « Submit, per door »)."""
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.analysis import Analysis
from app.models.code_redemption import CodeRedemption
from app.models.profile import CONSENT_VERSION, Profile
from app.models.run_log import RunLog
from app.services import code_service, held
from app.utils.tokens import hash_token
from tests.helpers_doors import (
    P1_INPUTS, bearer, code, counselor, expired_bearer, last_place_goes_after_resolve,
    stale_first_count_after_resolve, user,
)

START = "app.routes.analyses.start_analysis"


def _post(client, headers=None, **body):
    return client.post("/api/analyses/", json={"inputs": P1_INPUTS, **body}, headers=headers or {})


def _profiled(email="marie@test.fr"):
    u = user(email)
    db.session.add(Profile(user_id=u.id, prenom="Marie", ville="Lyon"))
    db.session.commit()
    return u


@patch(START)
def test_account_door_runs_the_free_tier_for_the_owner(start, client, app):
    u = _profiled()
    res = _post(client, bearer(u), door="account")
    assert res.status_code == 201, res.data
    row = db.session.get(Analysis, res.get_json()["analysis"]["id"])
    assert (row.user_id, row.door, row.inputs["_tier"], row.inputs["prenom"]) == (u.id, "account", "free", "Marie")
    assert RunLog.query.filter_by(door="account", user_id=u.id).count() == 1
    start.assert_called_once()


@patch(START)
def test_no_door_while_signed_in_is_the_account_door_and_tier_is_ignored(_s, client, app):
    u = user()
    res = _post(client, bearer(u), tier="premium")
    assert res.status_code == 201
    assert Analysis.query.one().inputs["_tier"] == "free"


@patch(START)
def test_force_analysis_tier_no_longer_exists(_s, client, app, monkeypatch):
    monkeypatch.setenv("FORCE_ANALYSIS_TIER", "paid")
    _post(client, bearer(user()), door="account")
    assert Analysis.query.one().inputs["_tier"] == "free"


@patch(START)
def test_account_door_needs_a_valid_session(_s, client, app):
    u = user()
    assert _post(client, door="account").status_code == 401
    assert _post(client, expired_bearer(u), door="account").status_code == 401


@patch(START)
def test_promo_door_runs_complet_and_spends_one_use(_s, client, app):
    u = _profiled()
    c = code(value="PROMO007", max_uses=5)
    res = _post(client, bearer(u), door="promo", code="promo-007")
    assert res.status_code == 201, res.data
    row = Analysis.query.one()
    assert (row.door, row.inputs["_tier"], row.user_id) == ("promo", "paid", u.id)
    redemption = CodeRedemption.query.one()
    assert (redemption.code_id, redemption.user_id, redemption.target_id) == (c.id, u.id, row.id)
    # Once per account.
    assert _post(client, bearer(u), door="promo", code="PROMO007").status_code == 409


@patch(START)
def test_advisor_door_sends_complet_to_the_counselor_only(start, client, app):
    c = counselor()
    code(c, max_uses=1, value="CONS0004")
    res = _post(client, door="advisor", code="CONS0004", prenom="  Zoé ", nom="N'Guessan-Kouamé",
                consent=True)
    assert res.status_code == 201, res.data
    assert res.get_json() == {}
    row = Analysis.query.one()
    assert (row.door, row.user_id, row.counselor_id, row.access_token_hash) == ("advisor", None, c.id, None)
    assert row.inputs["_tier"] == "paid"
    # Review focus 1: trimmed, accents kept.
    assert (row.inputs["prenom"], row.inputs["nom"]) == ("Zoé", "N'Guessan-Kouamé")
    assert row.consent_at is not None and row.consent_version == CONSENT_VERSION
    assert CodeRedemption.query.one().user_id is None
    start.assert_called_once()


@patch(START)
def test_advisor_door_folds_nothing_even_when_signed_in(_s, client, app):
    u = _profiled()
    code(counselor(), value="CONS0005")
    # The fold itself never runs — so no profile, no bloc 5, no voyage,
    # whatever the account holds.
    with patch("app.routes.analyses._merge_profile") as merge:
        _post(client, bearer(u), door="advisor", code="CONS0005", prenom="Marie", nom="Durand", consent=True)
    merge.assert_not_called()
    row = Analysis.query.one()
    assert row.user_id is None
    assert set(row.inputs) == {"cv_text", "cible_visee", "_chemin", "_path", "_tier", "prenom", "nom"}


@patch(START)
def test_advisor_door_writes_a_new_row_and_deletes_the_callers_draft(_s, client, app):
    u = user()
    draft = Analysis(user_id=u.id, status="draft", inputs=dict(P1_INPUTS))
    db.session.add(draft)
    db.session.commit()
    draft_id = draft.id
    code(counselor(), value="CONS0006")
    _post(client, bearer(u), door="advisor", code="CONS0006", prenom="M", nom="D",
          consent=True, draft_id=draft_id)
    assert db.session.get(Analysis, draft_id) is None
    assert Analysis.query.one().id != draft_id


@pytest.mark.parametrize("extra,expected", [
    ({"prenom": "", "nom": "Durand", "consent": True}, 400),
    ({"prenom": "Zoé", "nom": "D" * 81, "consent": True}, 400),
    ({"prenom": "Z" * 80, "nom": "D" * 80, "consent": True}, 201),   # Review focus 1
    ({"prenom": "Zoé", "nom": "Durand"}, 400),                        # no consent
    ({"prenom": "Zoé", "nom": "Durand", "consent": "yes"}, 400),
])
@patch(START)
def test_advisor_door_needs_identity_and_consent(_s, client, app, extra, expected):
    code(counselor(), value="CONS0007")
    assert _post(client, door="advisor", code="CONS0007", **extra).status_code == expected


@patch(START)
def test_anonymous_door_gives_a_private_link(_s, client, app):
    res = _post(client, door="anonymous", consent=True)
    assert res.status_code == 201, res.data
    body = res.get_json()
    row = Analysis.query.one()
    assert (row.door, row.user_id, row.inputs["_tier"]) == ("anonymous", None, "free")
    assert row.access_token_hash == hash_token(body["access_token"])
    assert body["analysis"]["access_expires_at"] is not None


@patch(START)
def test_anonymous_door_refuses_a_live_session_but_not_an_expired_one(_s, client, app):
    u = user()
    assert _post(client, bearer(u), door="anonymous", consent=True).status_code == 400
    assert _post(client, expired_bearer(u), door="anonymous", consent=True).status_code == 201


@patch(START)
def test_anonymous_door_promotes_the_held_draft_with_a_fresh_key(_s, client, app):
    client.post("/api/analyses/draft", json={"inputs": P1_INPUTS})
    draft = Analysis.query.one()
    draft_hash = draft.access_token_hash
    res = _post(client, door="anonymous", consent=True)
    row = db.session.get(Analysis, draft.id)
    assert row.status == "queued" and row.access_token_hash != draft_hash
    assert row.access_token_hash == hash_token(res.get_json()["access_token"])


@patch(START)
def test_server_keys_never_survive(_s, client, app):
    u = user()
    poisoned = {**P1_INPUTS, "_conditions": ["x"], "_oeth": True, "_voyage": ["y"], "_tier": "premium"}
    client.post("/api/analyses/", json={"inputs": poisoned, "door": "account"}, headers=bearer(u))
    inputs = Analysis.query.one().inputs
    assert "_conditions" not in inputs and "_oeth" not in inputs and "_voyage" not in inputs
    assert inputs["_tier"] == "free"


@patch(START)
def test_the_daily_caps_hold(_s, client, app):
    app.config["FREE_RUNS_PER_ACCOUNT_PER_DAY"] = 2
    app.config["ANONYMOUS_RUNS_PER_DAY"] = 1
    u = user()
    assert _post(client, bearer(u), door="account").status_code == 201
    assert _post(client, bearer(u), door="account").status_code == 201
    assert _post(client, bearer(u), door="account").status_code == 429
    assert _post(client, door="anonymous", consent=True).status_code == 201
    assert _post(client, door="anonymous", consent=True).status_code == 429


@patch(START)
def test_a_wrong_door_code_says_which_door(_s, client, app):
    code(counselor(), value="CONS0008")
    res = _post(client, bearer(user()), door="promo", code="CONS0008")
    assert res.status_code == 409 and res.get_json()["door"] == "advisor"
    assert Analysis.query.count() == 0


@patch(START)
def test_an_unknown_door_is_400(_s, client, app):
    assert _post(client, bearer(user()), door="premium").status_code == 400


@pytest.mark.parametrize("path", ["/api/upload/cv", "/api/upload/projet"])
def test_uploads_are_open(client, app, path):
    import io
    # Signed out, and past the gate: an unreadable PDF gets the route's own
    # 422 « Impossible d'extraire le texte », not a 401.
    data = {"file": (io.BytesIO(b"not a pdf body"), "cv.pdf", "application/pdf")}
    res = client.post(path, data=data, content_type="multipart/form-data")
    assert res.status_code == 422


@patch(START)
def test_a_failed_promo_run_is_relaunched_once_by_its_owner(start, client, app):
    owner, other = user(), user("other@test.fr")
    row = Analysis(user_id=owner.id, door="promo", status="error", inputs={"_path": "1", "_tier": "paid"})
    db.session.add(row)
    db.session.commit()
    assert client.post(f"/api/analyses/{row.id}/relaunch", headers=bearer(other)).status_code == 403
    assert client.post(f"/api/analyses/{row.id}/relaunch", headers=bearer(owner)).status_code == 200
    assert client.post(f"/api/analyses/{row.id}/relaunch", headers=bearer(owner)).status_code == 409
    start.assert_called_once()


@patch(START)
def test_only_the_promo_door_has_an_owner_relaunch(_s, client, app):
    owner = user()
    row = Analysis(user_id=owner.id, door="account", status="error", inputs={"_path": "1"})
    db.session.add(row)
    db.session.commit()
    assert client.post(f"/api/analyses/{row.id}/relaunch", headers=bearer(owner)).status_code == 403


# ── Beyond the table: what each door writes, and what it never reads ─────────

def _door_request(door, *, max_uses=None, draft=False):
    """(headers, fields, code, draft_id): what gets one submit through `door`.

    With `draft` the caller is signed in and holds a draft of their own, which
    their body names — any door but the anonymous one, which refuses a session.
    """
    u = _profiled() if door in ("account", "promo") or draft else None
    fields, c = {}, None
    if door == "promo":
        c = code(value="PROMO0D1", max_uses=max_uses)
        fields = {"code": "PROMO0D1"}
    elif door == "advisor":
        c = code(counselor(), value="CONS0D01", max_uses=max_uses)
        fields = {"code": "CONS0D01", "prenom": "Zoé", "nom": "Durand", "consent": True}
    elif door == "anonymous":
        fields = {"consent": True}
    draft_id = None
    if draft:
        held_draft = Analysis(user_id=u.id, status="draft", inputs=dict(P1_INPUTS))
        db.session.add(held_draft)
        db.session.commit()
        draft_id = held_draft.id
        fields["draft_id"] = draft_id
    return (bearer(u) if u else {}), fields, c, draft_id


@pytest.mark.parametrize("door,signed_in,names_the_account", [
    ("account", True, True),
    ("promo", True, False),
    ("advisor", True, False),
    ("anonymous", False, False),
])
@patch(START)
def test_run_log_names_an_account_only_where_a_cap_reads_it(_s, client, app, door, signed_in,
                                                           names_the_account):
    """Final review, minor 1. An advisor report belongs to no account: a
    run_log row carrying the signed-in caller's id would link it back to
    theirs. Only the account door's cap counts per account (doors.over_cap),
    so only that door keeps the id."""
    u = _profiled()
    fields = {}
    if door == "promo":
        code(value="PROMO0L1", max_uses=5)
        fields = {"code": "PROMO0L1"}
    elif door == "advisor":
        code(counselor(), value="CONS0L01")
        fields = {"code": "CONS0L01", "prenom": "Zoé", "nom": "Durand", "consent": True}
    elif door == "anonymous":
        fields = {"consent": True}
    res = _post(client, bearer(u) if signed_in else None, door=door, **fields)
    assert res.status_code == 201, res.data
    log = RunLog.query.one()
    assert (log.door, log.user_id) == (door, u.id if names_the_account else None)


@pytest.mark.parametrize("door,tier", [
    ("account", "free"), ("promo", "paid"), ("advisor", "paid"), ("anonymous", "free"),
])
@patch(START)
def test_the_door_decides_the_tier_whatever_the_body_says(_s, client, app, door, tier):
    headers, fields, _, _ = _door_request(door)
    res = _post(client, headers, door=door, tier="premium", **fields)
    assert res.status_code == 201, res.data
    assert Analysis.query.one().inputs["_tier"] == tier


@pytest.mark.parametrize("door,keys", [
    ("account", {"analysis"}), ("promo", {"analysis"}),
    ("advisor", set()), ("anonymous", {"analysis", "access_token"}),
])
@patch(START)
def test_the_response_carries_only_what_the_door_gives(_s, client, app, door, keys):
    headers, fields, _, _ = _door_request(door)
    res = _post(client, headers, door=door, **fields)
    assert res.status_code == 201, res.data
    assert set(res.get_json()) == keys
    # Share links are retired: no door mints one.
    assert Analysis.query.one().share_token is None


@pytest.mark.parametrize("door,recorded", [
    ("account", False), ("promo", False), ("advisor", True), ("anonymous", True),
])
@patch(START)
def test_consent_is_recorded_only_where_there_is_no_signup(_s, client, app, door, recorded):
    headers, fields, _, _ = _door_request(door)
    assert _post(client, headers, door=door, **fields).status_code == 201
    row = Analysis.query.one()
    assert CONSENT_VERSION == "v1.3"                  # CGV §2 and §6 changed (decision 48)
    if recorded:
        assert row.consent_at is not None and row.consent_version == "v1.3"
    else:
        assert (row.consent_at, row.consent_version) == (None, None)


@pytest.mark.parametrize("door", ["account", "promo"])
@patch(START)
def test_a_signed_in_draft_is_promoted_and_dated_from_the_run(_s, client, app, door):
    """The draft the body names becomes the run's row, and from now on its date
    is the run's: retention and the report's date count from the submit."""
    u = _profiled()
    draft = Analysis(user_id=u.id, status="draft", inputs=dict(P1_INPUTS),
                     created_at=datetime.utcnow() - timedelta(days=3))
    db.session.add(draft)
    db.session.commit()
    draft_id = draft.id
    extra = {}
    if door == "promo":
        code(value="PROMO0D2")
        extra = {"code": "PROMO0D2"}

    res = _post(client, bearer(u), door=door, draft_id=draft_id, **extra)

    assert res.status_code == 201, res.data
    assert res.get_json()["analysis"]["id"] == draft_id
    row = Analysis.query.one()
    assert (row.id, row.status, row.door, row.user_id) == (draft_id, "queued", door, u.id)
    assert row.created_at > datetime.utcnow() - timedelta(minutes=1)


@pytest.mark.parametrize("callers_own,status", [(False, "draft"), (True, "success")])
@patch(START)
def test_only_the_callers_own_draft_is_ever_promoted(_s, client, app, callers_own, status):
    """A draft_id that is another account's, or the caller's own finished
    report, finds nothing to promote: the submit writes a new row."""
    owner, caller = user(), user("autre@test.fr")
    row = Analysis(user_id=(caller if callers_own else owner).id, status=status, door="account",
                   inputs=dict(P1_INPUTS))
    db.session.add(row)
    db.session.commit()
    row_id = row.id

    res = _post(client, bearer(caller), door="account", draft_id=row_id)

    assert res.status_code == 201, res.data
    assert res.get_json()["analysis"]["id"] != row_id
    assert db.session.get(Analysis, row_id).status == status


@patch(START)
def test_the_anonymous_door_forgets_the_held_draft_it_used(_s, client, app):
    client.post("/api/analyses/draft", json={"inputs": P1_INPUTS})
    assert client.get_cookie(held.COOKIE, path="/api") is not None
    assert _post(client, door="anonymous", consent=True).status_code == 201
    assert client.get_cookie(held.COOKIE, path="/api") is None


@patch(START)
def test_the_advisor_door_deletes_the_held_draft_and_forgets_it(_s, client, app):
    client.post("/api/analyses/draft", json={"inputs": P1_INPUTS})
    draft_id = Analysis.query.one().id
    code(counselor(), value="CONS0009")

    res = _post(client, door="advisor", code="CONS0009", prenom="Zoé", nom="Durand", consent=True)

    assert res.status_code == 201, res.data
    assert db.session.get(Analysis, draft_id) is None
    assert Analysis.query.one().door == "advisor"
    assert client.get_cookie(held.COOKIE, path="/api") is None


@patch(START)
def test_a_held_report_is_left_alone_by_a_new_submit(_s, client, app):
    """Only a held *draft* is the submit's to promote: the no-login report the
    cookie keeps for « Garder » stays what it is."""
    key = "k" * 43
    report = Analysis(status="success", door="anonymous", inputs=dict(P1_INPUTS),
                      access_token_hash=hash_token(key))
    db.session.add(report)
    db.session.commit()
    report_id = report.id
    client.set_cookie(held.COOKIE, key, path="/api")

    res = _post(client, door="anonymous", consent=True)

    assert res.status_code == 201, res.data
    assert res.get_json()["analysis"]["id"] != report_id
    assert db.session.get(Analysis, report_id).status == "success"
    assert client.get_cookie(held.COOKIE, path="/api") is not None


@patch(START)
def test_a_promo_code_at_the_advisor_door_says_promo(_s, client, app):
    code(value="PROMO0W1")
    res = _post(client, door="advisor", code="PROMO0W1", prenom="Zoé", nom="Durand", consent=True)
    assert res.status_code == 409 and res.get_json()["door"] == "promo"
    assert Analysis.query.count() == 0


@pytest.mark.parametrize("inputs,extra", [
    ({**P1_INPUTS, "cv_text": "trop court"}, {"prenom": "Zoé", "nom": "Durand", "consent": True}),
    (P1_INPUTS, {"prenom": "", "nom": "Durand", "consent": True}),
    (P1_INPUTS, {"prenom": "Zoé", "nom": "Durand"}),
])
@patch(START)
def test_whatever_refuses_runs_before_the_code_is_spent(start, client, app, inputs, extra):
    code(counselor(), value="CONS0010")
    res = client.post("/api/analyses/", json={
        "inputs": inputs, "door": "advisor", "code": "CONS0010", **extra,
    })
    assert res.status_code == 400
    assert (Analysis.query.count(), RunLog.query.count(), CodeRedemption.query.count()) == (0, 0, 0)
    start.assert_not_called()


@pytest.mark.parametrize("status,expected", [
    ("error", 200), ("timeout", 200), ("success", 409), ("running", 409), ("queued", 409),
])
@patch(START)
def test_a_relaunch_takes_a_failed_run_and_nothing_else(start, client, app, status, expected):
    owner = user()
    row = Analysis(user_id=owner.id, door="promo", status=status, inputs={"_path": "1", "_tier": "paid"})
    db.session.add(row)
    db.session.commit()

    res = client.post(f"/api/analyses/{row.id}/relaunch", headers=bearer(owner))

    assert res.status_code == expected
    assert start.called == (expected == 200)
    if expected == 200:
        assert res.get_json()["analysis"]["status"] == "queued"


def test_a_relaunch_needs_a_session(client, app):
    row = Analysis(user_id=user().id, door="promo", status="error", inputs={"_path": "1"})
    db.session.add(row)
    db.session.commit()
    assert client.post(f"/api/analyses/{row.id}/relaunch").status_code == 401


# ── One commit per submit ─────────────────────────────────────────────────────
# A code is spent before the run starts (decision 23), and the use must never be
# spent on a run that has no row: redeem()'s single commit carries the row, its
# run_log entry and the redemption together.

@contextmanager
def _ordered_events():
    """Every commit the session makes and every run that starts, in order."""
    events, real_commit = [], db.session.commit

    def commit():
        events.append("commit")
        return real_commit()

    with patch.object(db.session, "commit", side_effect=commit), \
            patch(START, side_effect=lambda *a, **k: events.append("start")):
        yield events


@pytest.mark.parametrize("door", ["account", "anonymous"])
def test_a_door_with_no_code_commits_once_then_starts_the_run(client, app, door):
    headers, fields, _, _ = _door_request(door)
    with _ordered_events() as events:
        res = _post(client, headers, door=door, **fields)
    assert res.status_code == 201, res.data
    assert events == ["commit", "start"]
    assert (Analysis.query.one().status, RunLog.query.filter_by(door=door).count()) == ("queued", 1)


@pytest.mark.parametrize("draft", [False, True])
@pytest.mark.parametrize("door", ["promo", "advisor"])
def test_the_row_the_run_log_and_the_redemption_land_in_one_commit(client, app, door, draft):
    headers, fields, c, draft_id = _door_request(door, max_uses=2, draft=draft)
    with _ordered_events() as events:
        res = _post(client, headers, door=door, **fields)

    assert res.status_code == 201, res.data
    assert events == ["commit", "start"]
    row = Analysis.query.one()                    # a draft is promoted or replaced, never left
    assert (row.status, row.door) == ("queued", door)
    if draft and door == "promo":
        assert row.id == draft_id
    elif draft:
        assert row.id != draft_id
    assert RunLog.query.filter_by(door=door).count() == 1
    redemption = CodeRedemption.query.one()
    assert (redemption.code_id, redemption.target_id, redemption.slot) == (c.id, row.id, 1)


@pytest.mark.parametrize("draft", [False, True])
@pytest.mark.parametrize("door", ["promo", "advisor"])
@patch(START)
def test_a_retried_redemption_still_queues_the_run(start, client, app, door, draft):
    """When another request took the slot first, redeem() rolls back — the row,
    its run_log entry and the draft's deletion with it — and commits only the
    redemption on its retry. The route puts them back, and the run starts once,
    after that commit."""
    headers, fields, c, draft_id = _door_request(door, max_uses=2, draft=draft)
    db.session.add(CodeRedemption(code_id=c.id, target_type="analysis", target_id="a-other", slot=1))
    db.session.commit()

    with stale_first_count_after_resolve() as stale:
        res = _post(client, headers, door=door, **fields)

    assert res.status_code == 201, res.data
    assert stale["served"]                  # the first attempt did collide on slot 1
    start.assert_called_once()
    row = Analysis.query.one()
    assert (row.status, row.door) == ("queued", door)
    if draft and door == "promo":
        assert row.id == draft_id
    elif draft:
        assert row.id != draft_id
    assert RunLog.query.filter_by(door=door).count() == 1
    assert CodeRedemption.query.filter_by(target_id=row.id).count() == 1
    assert sorted(r.slot for r in CodeRedemption.query.filter_by(code_id=c.id)) == [1, 2]


@pytest.mark.parametrize("draft", [False, True])
@pytest.mark.parametrize("door", ["promo", "advisor"])
@patch(START)
def test_a_refusal_after_the_check_leaves_nothing_behind(start, client, app, door, draft):
    """redeem() can still refuse once resolve_for_door() has said yes: the last
    place went in between. What was staged ahead of the redemption must not
    outlive that refusal — no row, no run_log entry, the draft as it was — and
    no run starts."""
    headers, fields, c, draft_id = _door_request(door, max_uses=1, draft=draft)

    with last_place_goes_after_resolve(c.id, "analysis"):
        res = _post(client, headers, door=door, **fields)

    assert res.status_code == 409
    assert res.get_json()["error"] == code_service.EXHAUSTED
    start.assert_not_called()
    assert RunLog.query.count() == 0
    assert CodeRedemption.query.count() == 1                 # the other request's
    if draft:
        row = Analysis.query.one()
        assert (row.id, row.status, row.door) == (draft_id, "draft", None)
    else:
        assert Analysis.query.count() == 0


@patch(START)
def test_two_overlapping_promo_submits_by_one_account_run_once(start, client, app):
    """The other tab's request spends the account's use between this one's
    check and its write: the database refuses the second use (ALREADY_USED) and
    nothing of this request is left."""
    u = _profiled()
    c = code(value="PROMO0R1", max_uses=5)
    real_resolve = code_service.resolve

    def resolve_then_the_other_tab_wins(code_str, target_type):
        found = real_resolve(code_str, target_type)
        db.session.add(CodeRedemption(code_id=c.id, user_id=u.id, target_type="analysis",
                                      target_id="a-other", slot=1))
        db.session.commit()
        return found

    with patch.object(code_service, "resolve", side_effect=resolve_then_the_other_tab_wins):
        res = _post(client, bearer(u), door="promo", code="PROMO0R1")

    assert res.status_code == 409
    assert res.get_json()["error"] == code_service.ALREADY_USED
    start.assert_not_called()
    assert (Analysis.query.count(), RunLog.query.count(), CodeRedemption.query.count()) == (0, 0, 1)
