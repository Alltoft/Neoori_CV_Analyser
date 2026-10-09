"""Who may read an analysis (four-doors spec, « Who may read an analysis »)."""
from datetime import timedelta

from app.extensions import db
from app.models.analysis import Analysis
from app.models.counselor_note import CounselorNote
from app.models.price_feedback import BUCKETS, PriceFeedback
from app.utils.tokens import hash_token, new_access_token
from tests.helpers_doors import bearer, counselor, expired_bearer, user


def _row(status="success", **fields):
    a = Analysis(status=status, inputs={"_path": "1"}, output={"1": {"title": "t"}}, **fields)
    db.session.add(a)
    db.session.commit()
    return a


def _get(client, a, headers=None):
    return client.get(f"/api/analyses/{a.id}", headers=headers or {}).status_code


def _token_row(**fields):
    token = new_access_token()
    return token, _row(user_id=None, door="anonymous", access_token_hash=hash_token(token), **fields)


def test_the_owner_reads_their_row_and_nobody_else_does(client, app):
    owner, other = user(), user("other@test.fr")
    a = _row(user_id=owner.id, door="account")
    assert _get(client, a, bearer(owner)) == 200
    assert _get(client, a, bearer(other)) == 403
    assert _get(client, a) == 403


def test_an_expired_session_is_a_signed_out_visitor(client, app):
    owner = user()
    a = _row(user_id=owner.id, door="account")
    assert _get(client, a, expired_bearer(owner)) == 403


def test_a_legacy_row_stays_open_by_id(client, app):
    assert _get(client, _row(user_id=None, door="legacy")) == 200


def test_a_row_with_nothing_set_is_closed(client, app):
    assert _get(client, _row(user_id=None)) == 403


def test_a_token_row_opens_with_its_token_only(client, app):
    token, a = _token_row()
    assert _get(client, a, {"X-Analysis-Token": token}) == 200
    assert _get(client, a, {"X-Analysis-Token": token + "x"}) == 403
    assert _get(client, a) == 403


def test_by_token_finds_the_report(client, app):
    token, a = _token_row()
    res = client.get("/api/analyses/by-token", headers={"X-Analysis-Token": token})
    assert res.status_code == 200
    assert res.get_json()["analysis"]["id"] == a.id
    assert client.get("/api/analyses/by-token", headers={"X-Analysis-Token": "nope"}).status_code == 404
    assert client.get("/api/analyses/by-token").status_code == 404


def test_by_token_never_serves_a_held_draft(client, app):
    token = new_access_token()
    _row(status="draft", user_id=None, access_token_hash=hash_token(token))
    assert client.get("/api/analyses/by-token", headers={"X-Analysis-Token": token}).status_code == 404


def test_an_advisor_row_is_closed_to_every_candidate_route(client, app):
    c = counselor()
    a = _row(user_id=None, door="advisor", counselor_id=c.id)
    assert _get(client, a, bearer(c)) == 403
    assert _get(client, a) == 403
    assert client.delete(f"/api/analyses/{a.id}").status_code == 403
    # The counselor's account erased (ON DELETE SET NULL): still closed.
    a.counselor_id = None
    db.session.commit()
    assert _get(client, a) == 403


def test_the_token_holder_may_answer_the_price_probe_and_delete(client, app):
    token, a = _token_row()
    headers = {"X-Analysis-Token": token}
    res = client.post(f"/api/analyses/{a.id}/price-feedback", json={"bucket": BUCKETS[0]}, headers=headers)
    assert res.status_code == 200
    assert client.delete(f"/api/analyses/{a.id}", headers=headers).status_code == 200


def test_the_report_says_when_its_link_expires(client, app):
    token, a = _token_row()
    body = client.get("/api/analyses/by-token", headers={"X-Analysis-Token": token}).get_json()["analysis"]
    assert body["door"] == "anonymous"
    assert body["access_expires_at"].startswith((a.created_at + timedelta(days=30)).date().isoformat())


def test_only_the_hash_is_stored():
    token = new_access_token()
    assert len(token) >= 43 and hash_token(token) != token and len(hash_token(token)) == 64


def test_an_odd_token_header_is_a_wrong_token_not_an_error(client, app):
    _, a = _token_row()
    for odd in ("é", " ", "a" * 5000, "../etc"):
        assert _get(client, a, {"X-Analysis-Token": odd}) == 403
        assert client.get("/api/analyses/by-token", headers={"X-Analysis-Token": odd}).status_code == 404


def test_a_closed_row_stays_closed_to_its_token_and_its_owner(client, app):
    """The advisor check comes before the token and the owner checks, and
    `door` and `counselor_id` each close a row on their own."""
    c, owner = counselor(), user()
    token = new_access_token()
    advisor = _row(user_id=None, door="advisor", counselor_id=c.id, access_token_hash=hash_token(token))
    assert _get(client, advisor, {"X-Analysis-Token": token}) == 403
    # The counselor's account erased: `door` alone keeps it closed.
    advisor.counselor_id = None
    db.session.commit()
    assert _get(client, advisor, {"X-Analysis-Token": token}) == 403
    # And `counselor_id` alone closes a row, whatever its door says.
    owned = _row(user_id=owner.id, door="account", counselor_id=c.id)
    assert _get(client, owned, bearer(owner)) == 403


def test_by_token_never_serves_an_advisor_row_even_with_its_hash(client, app):
    """An advisor row holds no token by construction. Were one ever given a
    hash, /by-token still refuses it: it goes through _may_access like every
    other candidate route."""
    c = counselor()
    token = new_access_token()
    headers = {"X-Analysis-Token": token}
    row = _row(user_id=None, door="advisor", counselor_id=c.id, access_token_hash=hash_token(token))
    assert client.get("/api/analyses/by-token", headers=headers).status_code == 404
    # The counselor's account erased (ON DELETE SET NULL): `door` alone keeps it closed.
    row.counselor_id = None
    db.session.commit()
    assert client.get("/api/analyses/by-token", headers=headers).status_code == 404


def test_only_an_unclaimed_no_login_report_has_a_link_expiry(client, app):
    owner = user()
    for door in ("legacy", "advisor"):
        assert _row(user_id=None, door=door).to_dict()["access_expires_at"] is None
    assert _row(user_id=owner.id, door="account").to_dict()["access_expires_at"] is None
    claimed = _row(user_id=owner.id, door="anonymous")
    assert claimed.to_dict()["access_expires_at"] is None
    assert claimed.to_dict()["door"] == "anonymous"


def test_the_link_expiry_follows_the_retention_setting(client, app):
    app.config["ANONYMOUS_RETENTION_DAYS"] = 7
    _, a = _token_row()
    assert a.to_dict()["access_expires_at"].startswith((a.created_at + timedelta(days=7)).date().isoformat())


def test_deleting_a_report_takes_its_feedback_and_notes_and_only_those(client, app):
    owner, c = user(), counselor()
    gone, kept = _row(user_id=owner.id, door="account"), _row(user_id=owner.id, door="account")
    for row in (gone, kept):
        db.session.add(PriceFeedback(analysis_id=row.id, bucket=BUCKETS[0]))
        db.session.add(CounselorNote(analysis_id=row.id, counselor_id=c.id, body="privé"))
    db.session.commit()
    kept_id, gone_id = kept.id, gone.id
    assert client.delete(f"/api/analyses/{gone_id}", headers=bearer(owner)).status_code == 200
    assert db.session.get(Analysis, gone_id) is None
    assert PriceFeedback.query.filter_by(analysis_id=gone_id).count() == 0
    assert CounselorNote.query.filter_by(analysis_id=gone_id).count() == 0
    assert db.session.get(Analysis, kept_id) is not None
    assert PriceFeedback.query.filter_by(analysis_id=kept_id).count() == 1
    assert CounselorNote.query.filter_by(analysis_id=kept_id).count() == 1
