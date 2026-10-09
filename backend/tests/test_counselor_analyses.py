"""The counselor's own advisor-door reports (four-doors spec, decisions 26-27, 43)."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.analysis import Analysis
from app.models.code_redemption import CodeRedemption
from app.models.counselor_note import CounselorNote
from app.routes import counselor_space
from tests.helpers_doors import bearer, code, counselor, user

BASE = "/api/counselor/analyses"


def _advisor_row(c, *, status="success", via=None):
    row = Analysis(
        door="advisor", counselor_id=c.id, status=status,
        inputs={"_path": "1", "prenom": "Zoé", "nom": "Durand"},
        output={"1": {"title": "Lecture stratégique"}},
    )
    db.session.add(row)
    db.session.commit()
    if via is not None:
        db.session.add(CodeRedemption(code_id=via.id, target_type="analysis", target_id=row.id, slot=1))
        db.session.commit()
    return row


def test_the_counselor_lists_and_reads_their_reports(client, app):
    c = counselor()
    row = _advisor_row(c, via=code(c, max_uses=1, label="Atelier mardi"))
    listed = client.get(BASE, headers=bearer(c)).get_json()["analyses"]
    assert listed == [{
        "id": row.id, "prenom": "Zoé", "nom": "Durand", "code_label": "Atelier mardi",
        "status": "success", "created_at": row.created_at.isoformat(),
    }]
    res = client.get(f"{BASE}/{row.id}", headers=bearer(c))
    assert res.status_code == 200
    body = res.get_json()
    assert body["analysis"]["output"]["1"]["title"] == "Lecture stratégique"
    assert body["code_label"] == "Atelier mardi"


def test_another_counselor_a_candidate_and_a_revoked_counselor_cannot(client, app):
    c = counselor()
    row = _advisor_row(c)
    assert client.get(f"{BASE}/{row.id}", headers=bearer(counselor("autre@test.fr"))).status_code == 404
    assert client.get(f"{BASE}/{row.id}", headers=bearer(user())).status_code == 403
    revoked = counselor("revoque@test.fr", status="revoked")
    row.counselor_id = revoked.id
    db.session.commit()
    assert client.get(f"{BASE}/{row.id}", headers=bearer(revoked)).status_code == 403


def test_a_candidates_own_report_is_not_a_counselor_report(client, app):
    c = counselor()
    own = Analysis(user_id=c.id, door="account", status="success", inputs={"_path": "1"})
    db.session.add(own)
    db.session.commit()
    assert client.get(f"{BASE}/{own.id}", headers=bearer(c)).status_code == 404


@patch("app.routes.counselor_space.start_analysis")
def test_relaunch_only_a_failed_run_and_only_once(start, client, app):
    # Review focus 4: the double click.
    c = counselor()
    row = _advisor_row(c, status="error")
    assert client.post(f"{BASE}/{row.id}/relaunch", headers=bearer(c)).status_code == 200
    assert client.post(f"{BASE}/{row.id}/relaunch", headers=bearer(c)).status_code == 409
    start.assert_called_once()
    assert CodeRedemption.query.count() == 0


@patch("app.routes.counselor_space.start_analysis")
def test_a_finished_report_is_not_relaunched(start, client, app):
    c = counselor()
    row = _advisor_row(c)
    assert client.post(f"{BASE}/{row.id}/relaunch", headers=bearer(c)).status_code == 409
    start.assert_not_called()


def test_one_note_per_counselor_and_delete_takes_it_along(client, app):
    c = counselor()
    row = _advisor_row(c)
    for body in ("Première", "Seconde"):
        assert client.put(f"{BASE}/{row.id}/notes", json={"note": body}, headers=bearer(c)).status_code == 200
    assert CounselorNote.query.count() == 1
    assert client.get(f"{BASE}/{row.id}/notes", headers=bearer(c)).get_json() == {"note": "Seconde"}
    assert client.delete(f"{BASE}/{row.id}", headers=bearer(c)).status_code == 200
    assert CounselorNote.query.count() == 0
    assert Analysis.query.count() == 0


def test_a_note_has_a_ceiling(client, app):
    c = counselor()
    row = _advisor_row(c)
    res = client.put(f"{BASE}/{row.id}/notes", json={"note": "n" * 20_001}, headers=bearer(c))
    assert res.status_code == 400


def test_beneficiaires_name_the_advisor_reports(client, app):
    c = counselor()
    row = _advisor_row(c, via=code(c, max_uses=1))
    people = client.get("/api/counselor/beneficiaires", headers=bearer(c)).get_json()["beneficiaires"]
    assert len(people) == 1
    assert (people[0]["prenom"], people[0]["nom"], people[0]["analysis_id"]) == ("Zoé", "Durand", row.id)


def test_a_single_use_code_stays_in_circulation_until_both_kinds_are_spent(client, app):
    c = counselor()
    k = code(c, max_uses=1)
    db.session.add(CodeRedemption(code_id=k.id, target_type="voyage", target_id="v1", slot=1))
    db.session.commit()
    row = client.get("/api/counselor/codes", headers=bearer(c)).get_json()["codes"][0]
    assert row["statut"] == "actif"
    assert row["uses_by_kind"] == {"analysis": 0, "voyage": 1}
    assert client.get("/api/counselor/stats", headers=bearer(c)).get_json()["codes_en_circulation"] == 1


def test_the_share_link_is_gone(client, app):
    assert client.get("/api/c/anything").status_code == 404


def test_to_dict_has_no_counselor_audience(app):
    # created_at is set by hand: its default only fires on insert, and a
    # transient row cannot be serialised without it.
    data = Analysis(
        status="success", inputs={"_path": "1"}, output={}, created_at=datetime(2026, 10, 9),
    ).to_dict()
    assert "share_token" not in data and "counselor_keys" not in data


# ── what the tests above cannot see ──────────────────────────────────────────

def test_an_old_share_link_is_dead_even_for_a_token_that_exists(client, app):
    """The column stays and old rows keep their token (decision 43): the link
    must answer 404 for a token that really exists, not only for a made-up one
    — a route that merely failed to find "anything" would pass the test above."""
    c = counselor()
    old = Analysis(
        user_id=c.id, door="account", status="success", share_token="tok-old-link",
        inputs={"_path": "1", "prenom": "Zoé"}, output={"1": {"title": "Lecture stratégique"}},
    )
    db.session.add(old)
    db.session.commit()
    assert client.get("/api/c/tok-old-link").status_code == 404
    assert client.get("/api/c/tok-old-link/notes", headers=bearer(c)).status_code == 404
    assert client.put("/api/c/tok-old-link/notes", json={"body": "x"}, headers=bearer(c)).status_code == 404
    assert CounselorNote.query.count() == 0


def test_the_list_holds_only_my_advisor_reports_newest_first(client, app):
    c = counselor()
    older = _advisor_row(c)
    older.created_at = datetime.utcnow() - timedelta(days=2)
    newer = _advisor_row(c)
    _advisor_row(counselor("autre@test.fr"))
    db.session.add(Analysis(user_id=c.id, door="account", status="success", inputs={"_path": "1"}))
    db.session.add(Analysis(counselor_id=c.id, door="promo", status="success", inputs={"_path": "1"}))
    db.session.commit()
    listed = client.get(BASE, headers=bearer(c)).get_json()["analyses"]
    assert [a["id"] for a in listed] == [newer.id, older.id]
    assert all(a["code_label"] is None for a in listed)      # no redemption behind either


@pytest.mark.parametrize("method,suffix", [
    ("get", ""), ("get", "/r1"), ("delete", "/r1"), ("post", "/r1/relaunch"),
    ("get", "/r1/notes"), ("put", "/r1/notes"),
], ids=lambda v: v)
def test_every_route_needs_an_approved_counselor(method, suffix, client, app):
    """The list included. Its filter reads the caller's id, and with no caller
    that id is NULL: the advisor reports whose counselor account is gone would
    be listed to anyone, if the guard were ever left off."""
    owner = counselor()
    orphan = _advisor_row(owner)
    orphan.counselor_id = None
    db.session.commit()
    url = BASE + suffix
    call = getattr(client, method)
    assert call(url, json={"note": "x"}).status_code == 401
    assert call(url, json={"note": "x"}, headers=bearer(user())).status_code == 403
    assert call(url, json={"note": "x"}, headers=bearer(counselor("attente@test.fr", status="pending"))).status_code == 403


# Every route that takes a report id, with a body where it reads one.
ROUTES_BY_REPORT = [
    ("get", "", None),
    ("delete", "", None),
    ("post", "/relaunch", None),
    ("get", "/notes", None),
    ("put", "/notes", {"note": "Intrus"}),
]


@patch("app.routes.counselor_space.start_analysis")
@pytest.mark.parametrize("method,suffix,body", ROUTES_BY_REPORT, ids=lambda v: v if isinstance(v, str) else "")
def test_every_route_answers_404_to_anyone_but_the_reports_counselor(start, method, suffix, body, client, app):
    owner = counselor()
    report = _advisor_row(owner, status="error")
    own_candidate_report = Analysis(user_id=owner.id, door="account", status="error", inputs={"_path": "1"})
    # Naming the counselor is not enough: only the advisor door makes a report theirs.
    named_not_advisor = Analysis(counselor_id=owner.id, door="promo", status="error", inputs={"_path": "1"})
    db.session.add_all([own_candidate_report, named_not_advisor])
    db.session.commit()
    outsiders = [
        (counselor("autre@test.fr"), report.id),            # another counselor's report
        (user("admin@test.fr", role="admin"), report.id),   # the full report goes to the counselor only
        (owner, own_candidate_report.id),                   # their own candidate report
        (owner, named_not_advisor.id),                      # a row that names them, from another door
        (owner, "nope"),                                    # no such report
    ]
    for who, analysis_id in outsiders:
        res = getattr(client, method)(f"{BASE}/{analysis_id}{suffix}", json=body, headers=bearer(who))
        assert res.status_code == 404, (who.email, analysis_id)
    start.assert_not_called()
    assert Analysis.query.count() == 3
    assert CounselorNote.query.count() == 0
    assert {a.status for a in Analysis.query.all()} == {"error"}


def test_a_note_of_exactly_the_ceiling_is_kept(client, app):
    c = counselor()
    row = _advisor_row(c)
    res = client.put(f"{BASE}/{row.id}/notes", json={"note": "n" * 20_000}, headers=bearer(c))
    assert res.status_code == 200
    assert len(CounselorNote.query.one().body) == 20_000


def test_a_note_someone_else_left_on_the_report_is_neither_read_nor_overwritten(client, app):
    """The note is private to its author: an older note by another counselor
    (the retired share link let any signed-in counselor write one) is not the
    owner's to read, and saving theirs leaves it alone."""
    c = counselor()
    row = _advisor_row(c)
    other = counselor("autre@test.fr")
    db.session.add(CounselorNote(analysis_id=row.id, counselor_id=other.id, body="Note de l'autre"))
    db.session.commit()
    assert client.get(f"{BASE}/{row.id}/notes", headers=bearer(c)).get_json() == {"note": ""}
    assert client.put(f"{BASE}/{row.id}/notes", json={"note": "La mienne"}, headers=bearer(c)).status_code == 200
    assert client.get(f"{BASE}/{row.id}/notes", headers=bearer(c)).get_json() == {"note": "La mienne"}
    bodies = {n.counselor_id: n.body for n in CounselorNote.query.all()}
    assert bodies == {other.id: "Note de l'autre", c.id: "La mienne"}
    # Deleting the report takes every note on it along, the other author's too.
    assert client.delete(f"{BASE}/{row.id}", headers=bearer(c)).status_code == 200
    assert CounselorNote.query.count() == 0


@patch("app.routes.counselor_space.start_analysis")
@pytest.mark.parametrize("status", ["error", "timeout"])
def test_relaunch_queues_the_same_row_and_starts_it(start, status, client, app):
    c = counselor()
    row = _advisor_row(c, status=status)
    row.progress = 40
    db.session.commit()
    res = client.post(f"{BASE}/{row.id}/relaunch", headers=bearer(c))
    assert res.status_code == 200
    report = res.get_json()["analysis"]
    assert (report["id"], report["status"], report["progress"]) == (row.id, "queued", 0)
    assert start.call_args.args[0] == row.id
    assert Analysis.query.count() == 1


@patch("app.routes.counselor_space.start_analysis")
@pytest.mark.parametrize("status", ["draft", "queued", "running", "success"])
def test_only_a_failed_run_can_be_relaunched(start, status, client, app):
    c = counselor()
    row = _advisor_row(c, status=status)
    assert client.post(f"{BASE}/{row.id}/relaunch", headers=bearer(c)).status_code == 409
    start.assert_not_called()
    assert db.session.get(Analysis, row.id).status == status


@patch("app.routes.counselor_space.start_analysis")
def test_a_click_that_read_the_failure_before_the_other_claimed_it_starts_nothing(start, client, app):
    """The double click as the database sees it: both requests read 'error' and
    the other one's write lands first. The claim is one conditional UPDATE, so
    the loser's rowcount is 0; a check on the row it already read would still
    say 'error' and start a second run — which the sequential test above cannot
    tell apart, since its second click reads the committed 'queued'."""
    c = counselor()
    row = _advisor_row(c, status="error")
    real = counselor_space._my_report

    def read_then_lose_the_race(analysis_id):
        found = real(analysis_id)
        # The other click's claim, written behind the session's back: the row
        # this request holds keeps saying 'error'.
        Analysis.query.filter_by(id=analysis_id).update({"status": "queued"}, synchronize_session=False)
        return found

    with patch.object(counselor_space, "_my_report", side_effect=read_then_lose_the_race):
        res = client.post(f"{BASE}/{row.id}/relaunch", headers=bearer(c))
    assert res.status_code == 409
    start.assert_not_called()
