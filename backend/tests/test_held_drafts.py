"""Held drafts and the neoori_hold cookie (four-doors spec, decisions 34-36)."""
import re
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models.analysis import Analysis
from app.models.user import User
from app.services import held, sign_in
from app.utils import auth_links
from app.utils.tokens import hash_token, new_access_token
from tests.helpers_doors import P1_INPUTS, bearer, expired_bearer, user

# The `next` of the two round trips most tests below take: « Avec mon compte »
# on the form, and « Créer un compte pour le garder » on /rapport. Signup marks
# the held row only on a round trip this browser started (ruling R39).
FORM_ROUND_TRIP = "/analyse/nouveau?reprendre=compte"
KEEP_ROUND_TRIP = "/espace?garder=1"


def _cookie(client):
    cookie = client.get_cookie(held.COOKIE, path="/api")
    return cookie.value if cookie else None


def _held_draft(client, inputs=P1_INPUTS):
    return client.post("/api/analyses/draft", json={"inputs": inputs})


def test_a_signed_out_draft_is_held_by_a_cookie_and_never_by_the_body(client, app):
    res = _held_draft(client)
    assert res.status_code == 201
    token = _cookie(client)
    assert token and token not in res.get_data(as_text=True)
    row = Analysis.query.one()
    assert (row.user_id, row.status, row.access_token_hash) == (None, "draft", hash_token(token))


def test_saving_again_reuses_the_held_row(client, app):
    # Review focus 5: two tabs, one browser, one cookie.
    _held_draft(client)
    res = _held_draft(client, {**P1_INPUTS, "cible_visee": "x" * 60})
    assert res.status_code == 200
    assert Analysis.query.count() == 1
    assert Analysis.query.one().inputs["cible_visee"] == "x" * 60


def test_a_held_draft_keeps_only_client_keys(client, app):
    _held_draft(client, {**P1_INPUTS, "_conditions": ["x"], "_tier": "premium"})
    assert set(Analysis.query.one().inputs) == {"cv_text", "cible_visee"}


def test_the_global_ceiling_on_held_drafts(client, app):
    app.config["HELD_DRAFTS_MAX"] = 1
    assert _held_draft(client).status_code == 201
    stranger = app.test_client()                       # another browser, no cookie
    res = stranger.post("/api/analyses/draft", json={"inputs": P1_INPUTS})
    assert res.status_code == 429 and res.get_json()["error"] == held.TOO_MANY
    # The first browser still updates its own.
    assert _held_draft(client).status_code == 200


def test_held_reads_the_draft_back_and_404s_without_a_cookie(client, app):
    assert client.get("/api/analyses/held").status_code == 404
    _held_draft(client)
    res = client.get("/api/analyses/held")
    assert res.status_code == 200
    assert res.get_json()["analysis"]["inputs"]["cv_text"] == P1_INPUTS["cv_text"]


def test_claim_attaches_the_held_draft_once(client, app):
    # Review focus 5: the second claim is a clean 404.
    _held_draft(client)
    u = user()
    assert client.post("/api/analyses/claim", headers=bearer(u)).status_code == 200
    row = Analysis.query.one()
    assert (row.user_id, row.access_token_hash) == (u.id, None)
    assert _cookie(client) is None
    assert client.post("/api/analyses/claim", headers=bearer(u)).status_code == 404


def test_claim_needs_a_session(client, app):
    _held_draft(client)
    assert client.post("/api/analyses/claim").status_code == 401


def test_hold_hands_a_no_login_report_to_the_cookie_and_claim_kills_the_link(client, app):
    token = new_access_token()
    report = Analysis(status="success", door="anonymous", inputs={}, access_token_hash=hash_token(token))
    db.session.add(report)
    db.session.commit()

    assert client.post("/api/analyses/hold", headers={"X-Analysis-Token": token}).status_code == 200
    assert _cookie(client) == token
    u = user()
    assert client.post("/api/analyses/claim", headers=bearer(u)).status_code == 200
    db.session.expire_all()
    assert db.session.get(Analysis, report.id).user_id == u.id
    assert client.get("/api/analyses/by-token", headers={"X-Analysis-Token": token}).status_code == 404


def test_hold_refuses_an_unknown_token(client, app):
    assert client.post("/api/analyses/hold", headers={"X-Analysis-Token": "nope"}).status_code == 404


def test_signup_marks_and_only_the_signup_password_attaches(client, app):
    _held_draft(client)
    res = client.post("/api/auth/register", json={"email": "zoe@test.fr", "password": "motdepasse1",
                                                  "next": FORM_ROUND_TRIP})
    assert res.status_code == 201
    new_id = res.get_json()["user"]["id"]
    row = Analysis.query.one()
    assert (row.pending_user_id, row.user_id) == (new_id, None)   # marked, not attached

    from app.models.user import User
    token = auth_links.make_verify_token(db.session.get(User, new_id))
    assert client.post("/api/auth/verify-email",
                       json={"token": token, "password": "motdepasse1"}).status_code == 200
    db.session.expire_all()
    row = Analysis.query.one()
    assert (row.user_id, row.access_token_hash, row.pending_user_id) == (new_id, None, None)


def test_signup_for_a_taken_address_marks_nothing(client, app):
    user("zoe@test.fr")
    _held_draft(client)
    assert client.post("/api/auth/register",
                       json={"email": "zoe@test.fr", "password": "motdepasse1",
                             "next": FORM_ROUND_TRIP}).status_code == 409
    assert Analysis.query.one().pending_user_id is None


def test_proving_the_address_another_way_drops_the_mark_and_keeps_the_row(client, app):
    _held_draft(client)
    res = client.post("/api/auth/register", json={"email": "zoe@test.fr", "password": "motdepasse1",
                                                  "next": FORM_ROUND_TRIP})
    from app.models.user import User
    stranger_set = db.session.get(User, res.get_json()["user"]["id"])
    assert Analysis.query.one().pending_user_id == stranger_set.id     # marked first

    sign_in.enter(stranger_set)            # Google, Microsoft or the email link
    db.session.expire_all()
    row = Analysis.query.one()
    assert (row.pending_user_id, row.user_id) == (None, None)
    assert row.access_token_hash is not None    # still held by the browser that made it


def test_a_reset_on_an_unverified_account_drops_the_mark(client, app):
    _held_draft(client)
    res = client.post("/api/auth/register", json={"email": "zoe@test.fr", "password": "motdepasse1",
                                                  "next": FORM_ROUND_TRIP})
    from app.models.user import User
    account = db.session.get(User, res.get_json()["user"]["id"])
    assert Analysis.query.one().pending_user_id == account.id          # marked first
    token = auth_links.make_reset_token(account)
    assert client.post("/api/auth/reset-password",
                       json={"token": token, "password": "nouveau-mdp1"}).status_code == 200
    db.session.expire_all()
    assert Analysis.query.one().pending_user_id is None


# ── What the cookie, the bodies and the marks must never do ──────────────────
#
# Beyond the cases above. A test client request runs in this test's own app
# context, so the route and the test share one database session: work a route
# left uncommitted still reads back as done. _reload() rolls back first, which
# is what the end of a real request does, so only committed work survives it.

def _reload():
    db.session.rollback()
    db.session.expire_all()


def _set_cookie(res):
    """(value, attributes) of the neoori_hold Set-Cookie header, or (None, None).
    Attribute names are lowercased; a flag such as HttpOnly maps to ""."""
    for header in res.headers.getlist("Set-Cookie"):
        if header.startswith(f"{held.COOKIE}="):
            parts = [part.strip() for part in header.split(";")]
            attrs = {}
            for part in parts[1:]:
                name, _, value = part.partition("=")
                attrs[name.lower()] = value
            return parts[0].split("=", 1)[1], attrs
    return None, None


def _kept_report(client):
    """A no-login report handed to this browser's cookie by « Garder »."""
    token = new_access_token()
    report = Analysis(status="success", door="anonymous", inputs={}, access_token_hash=hash_token(token))
    db.session.add(report)
    db.session.commit()
    assert client.post("/api/analyses/hold", headers={"X-Analysis-Token": token}).status_code == 200
    return report, token


def _signup(client, email="zoe@test.fr", password="motdepasse1", next_path=FORM_ROUND_TRIP):
    """Password signup in this browser, as committed, on the round trip
    `next_path` (None: no `next` at all). Returns the new, still unverified
    account."""
    body = {"email": email, "password": password}
    if next_path is not None:
        body["next"] = next_path
    res = client.post("/api/auth/register", json=body)
    assert res.status_code == 201
    account_id = res.get_json()["user"]["id"]
    _reload()
    return db.session.get(User, account_id)


def _verify(client, account, password="motdepasse1"):
    """The verification link and the password typed with it; the response,
    after the request's work has been reduced to what it committed."""
    token = auth_links.make_verify_token(account)
    res = client.post("/api/auth/verify-email", json={"token": token, "password": password})
    _reload()
    return res


def _claim(client, account):
    res = client.post("/api/analyses/claim", headers=bearer(account))
    _reload()
    return res


def test_the_cookie_is_httponly_lax_scoped_to_api_and_lives_48_hours(client, app):
    value, attrs = _set_cookie(_held_draft(client))
    assert value == _cookie(client)
    assert attrs["path"] == "/api"
    assert attrs["samesite"] == "Lax"
    assert attrs["max-age"] == str(48 * 3600)
    assert "httponly" in attrs
    assert "secure" not in attrs        # the test config leaves SESSION_COOKIE_SECURE unset


def test_the_cookie_is_secure_where_the_session_cookie_is(client, app):
    app.config["SESSION_COOKIE_SECURE"] = True      # production
    _, attrs = _set_cookie(_held_draft(client))
    assert "secure" in attrs


def test_claim_clears_the_cookie_under_the_path_that_set_it(client, app):
    _held_draft(client)
    res = client.post("/api/analyses/claim", headers=bearer(user()))
    value, attrs = _set_cookie(res)
    assert (value, attrs["path"], attrs["max-age"]) == ("", "/api", "0")


def test_no_response_body_carries_the_key_or_its_hash(client, app):
    first = _held_draft(client)
    token = _cookie(client)
    other = app.test_client()
    _, kept = _kept_report(other)
    answers = [                 # (response, the key it must not carry)
        (first, token),
        (_held_draft(client), token),
        (client.get("/api/analyses/held"), token),
        (client.post("/api/analyses/claim", headers=bearer(user())), token),
        (other.post("/api/analyses/hold", headers={"X-Analysis-Token": kept}), kept),
    ]
    for res, key in answers:
        assert res.status_code in (200, 201)
        body = res.get_data(as_text=True)
        assert key not in body and hash_token(key) not in body


def test_a_draft_over_the_caps_is_refused_and_leaves_nothing_held(client, app):
    res = _held_draft(client, {**P1_INPUTS, "cv_text": "c" * 40_001})
    assert res.status_code == 400
    assert res.get_json()["errors"] == ["CV trop long (40 000 caractères maximum)."]
    assert Analysis.query.count() == 0 and _cookie(client) is None


def test_a_signed_in_draft_belongs_to_the_account_and_sets_no_cookie(client, app):
    u = user()
    res = client.post("/api/analyses/draft", json={"inputs": P1_INPUTS}, headers=bearer(u))
    assert res.status_code == 201
    _reload()
    row = Analysis.query.one()
    assert (row.user_id, row.access_token_hash) == (u.id, None)
    assert _cookie(client) is None


def test_a_lapsed_session_saves_a_held_draft(client, app):
    # The access cookie outlives the JWT inside it: expired means signed out.
    res = client.post("/api/analyses/draft", json={"inputs": P1_INPUTS}, headers=expired_bearer(user()))
    assert res.status_code == 201
    _reload()
    assert Analysis.query.one().user_id is None
    assert _cookie(client)


def test_a_held_draft_and_its_update_are_committed(client, app):
    _held_draft(client)
    _reload()
    assert Analysis.query.count() == 1
    assert _held_draft(client, {**P1_INPUTS, "cible_visee": "y" * 60}).status_code == 200
    _reload()
    assert Analysis.query.one().inputs["cible_visee"] == "y" * 60


def test_the_ceiling_counts_only_live_ownerless_held_drafts(client, app):
    app.config["HELD_DRAFTS_MAX"] = 1
    owner = user()
    db.session.add_all([
        # owned: not ownerless
        Analysis(user_id=owner.id, status="draft", inputs={},
                 access_token_hash=hash_token(new_access_token())),
        # past its 48 hours
        Analysis(status="draft", inputs={}, access_token_hash=hash_token(new_access_token()),
                 created_at=datetime.utcnow() - timedelta(hours=49)),
        # a report, not a draft
        Analysis(status="success", door="anonymous", inputs={},
                 access_token_hash=hash_token(new_access_token())),
        # held by nobody: no key to find it by
        Analysis(status="draft", inputs={}),
    ])
    db.session.commit()
    assert _held_draft(client).status_code == 201           # none of the four counts
    assert app.test_client().post(
        "/api/analyses/draft", json={"inputs": P1_INPUTS}).status_code == 429


def test_held_never_serves_a_kept_report(client, app):
    _kept_report(client)
    assert client.get("/api/analyses/held").status_code == 404


def test_a_draft_saved_after_keeping_a_report_displaces_the_cookie_not_the_link(client, app):
    report, token = _kept_report(client)
    assert _held_draft(client).status_code == 201       # the cookie held a report: a new row
    assert _cookie(client) not in (None, token)
    _reload()
    assert db.session.get(Analysis, report.id).access_token_hash == hash_token(token)
    assert client.get("/api/analyses/by-token", headers={"X-Analysis-Token": token}).status_code == 200


def test_hold_takes_only_an_ownerless_no_login_report(client, app):
    owner = user()
    keys = []
    for fields in (
        {"status": "success", "door": "anonymous", "user_id": owner.id},   # already owned
        {"status": "draft"},                                               # a held draft
    ):
        key = new_access_token()
        db.session.add(Analysis(inputs={}, access_token_hash=hash_token(key), **fields))
        keys.append(key)
    db.session.commit()
    for key in keys:
        assert client.post("/api/analyses/hold", headers={"X-Analysis-Token": key}).status_code == 404
    assert client.post("/api/analyses/hold").status_code == 404         # no header at all
    assert _cookie(client) is None


def test_an_owned_row_is_never_held_whatever_it_carries(client, app):
    # Unreachable through the app, since attach() clears the key. This pins
    # the guard itself: a cookie must never reach, or claim, a row with an owner.
    key = new_access_token()
    db.session.add(Analysis(user_id=user().id, status="draft", inputs={},
                            access_token_hash=hash_token(key)))
    db.session.commit()
    client.set_cookie(held.COOKIE, key, path="/api")
    assert client.get("/api/analyses/held").status_code == 404
    assert client.post("/api/analyses/claim", headers=bearer(user("autre@test.fr"))).status_code == 404


def test_signup_marks_for_good(client, app):
    _held_draft(client)
    account = _signup(client)                       # committed, then reloaded
    assert Analysis.query.one().pending_user_id == account.id


def test_a_wrong_signup_password_attaches_nothing(client, app):
    _held_draft(client)
    account = _signup(client)
    assert _verify(client, account, password="pas-le-bon-mdp1").status_code == 401
    row = Analysis.query.one()
    assert (row.user_id, row.pending_user_id) == (None, account.id)     # still waiting
    assert db.session.get(User, account.id).email_verified_at is None


def test_the_signup_password_attaches_for_good(client, app):
    _held_draft(client)
    account = _signup(client)
    assert _verify(client, account).status_code == 200
    row = Analysis.query.one()
    assert (row.user_id, row.access_token_hash, row.pending_user_id) == (account.id, None, None)


def test_the_cookie_finds_nothing_once_verify_has_attached_the_row(client, app):
    _held_draft(client)
    account = _signup(client)
    assert _verify(client, account).status_code == 200
    assert client.get("/api/analyses/held").status_code == 404
    assert client.post("/api/analyses/claim", headers=bearer(account)).status_code == 404


def test_a_kept_report_follows_the_signup_password_path(client, app):
    report, token = _kept_report(client)
    account = _signup(client, next_path=KEEP_ROUND_TRIP)
    assert _verify(client, account).status_code == 200
    row = db.session.get(Analysis, report.id)
    assert (row.user_id, row.access_token_hash, row.pending_user_id) == (account.id, None, None)
    assert client.get("/api/analyses/by-token", headers={"X-Analysis-Token": token}).status_code == 404


def test_the_link_attaches_only_at_the_first_proof_of_the_address(client, app):
    # Link and password on an account already verified (an admin did it, and
    # asked for no password) are a login, not the registrant's proof.
    _held_draft(client)
    account = _signup(client)
    account.email_verified_at = datetime.utcnow()
    db.session.commit()
    assert _verify(client, account).status_code == 200
    assert Analysis.query.one().user_id is None


def test_a_reset_on_an_unverified_account_attaches_nothing(client, app):
    # The brief's reset test pins that the mark goes; this pins that the row
    # does not move with it, and that dropping the mark is committed.
    _held_draft(client)
    account = _signup(client)
    token = auth_links.make_reset_token(account)
    assert client.post("/api/auth/reset-password",
                       json={"token": token, "password": "nouveau-mdp1"}).status_code == 200
    _reload()
    row = Analysis.query.one()
    assert (row.pending_user_id, row.user_id) == (None, None)
    assert row.access_token_hash is not None        # still held by the browser that made it


def test_an_email_link_sign_in_drops_the_mark_through_the_route(client, app):
    # sign_in.enter called directly shares the test's session, so a mark
    # dropped after enter's commit would still read as dropped there. Through
    # the route, only what rode the commit survives the request.
    _held_draft(client)
    _signup(client)
    app.config["RESEND_API_KEY"] = "re_test"
    with patch("app.services.email_service.resend.Emails.send", return_value={"id": "1"}) as send:
        assert client.post("/api/auth/email-link", json={"email": "zoe@test.fr"}).status_code == 200
    token = re.search(r"token=([A-Za-z0-9_.\-]+)", send.call_args[0][0]["text"]).group(1)

    assert client.post("/api/auth/email-link/consume", json={"token": token}).status_code == 200
    _reload()
    row = Analysis.query.one()
    assert (row.pending_user_id, row.user_id) == (None, None)
    assert row.access_token_hash is not None


def test_after_the_mark_is_dropped_the_same_browser_can_still_claim(client, app):
    _held_draft(client)
    account = _signup(client)
    sign_in.enter(account)                  # the address proven by Google, say
    assert _claim(client, account).status_code == 200
    assert Analysis.query.one().user_id == account.id


def test_verify_attaches_only_the_rows_marked_for_that_account(client, app):
    other = app.test_client()                       # a second browser, a second signup
    _held_draft(client)
    _held_draft(other)
    mine = _signup(client)
    theirs = _signup(other, email="paul@test.fr")

    assert _verify(client, mine).status_code == 200
    waiting = Analysis.query.filter(Analysis.user_id.is_(None)).one()
    assert waiting.pending_user_id == theirs.id
    assert Analysis.query.filter_by(user_id=mine.id).count() == 1


def test_dropping_one_mark_leaves_the_others(client, app):
    other = app.test_client()
    _held_draft(client)
    _held_draft(other)
    mine = _signup(client)
    theirs = _signup(other, email="paul@test.fr")

    sign_in.enter(mine)
    _reload()
    assert {row.pending_user_id for row in Analysis.query.all()} == {None, theirs.id}


def test_a_claimed_draft_becomes_the_accounts_newest(client, app):
    # The form picks the account's latest draft (spec decision 34): a draft
    # held for a day must not sort behind the ones the account made meanwhile.
    _held_draft(client)
    Analysis.query.one().created_at = datetime.utcnow() - timedelta(hours=30)
    db.session.commit()
    before = datetime.utcnow()
    assert _claim(client, user()).status_code == 200
    assert Analysis.query.one().created_at >= before


def test_a_claimed_report_keeps_its_date(client, app):
    # Retention counts from the run, not from the claim.
    report, _ = _kept_report(client)
    ran = datetime.utcnow() - timedelta(days=3)
    report.created_at = ran
    db.session.commit()
    assert _claim(client, user()).status_code == 200
    assert db.session.get(Analysis, report.id).created_at == ran


def test_the_refusals_speak_french(client, app):
    expired = {"error": "Votre brouillon a expiré."}
    assert client.get("/api/analyses/held").get_json() == expired
    assert client.post("/api/analyses/claim", headers=bearer(user())).get_json() == expired
    assert client.post("/api/analyses/claim").get_json() == {"error": "Non authentifié."}
    refused = client.post("/api/analyses/hold", headers={"X-Analysis-Token": "nope"})
    assert refused.get_json() == {"error": "Ce lien n'est plus valide."}


@pytest.mark.parametrize("value", ["x" * 10_000, "é" * 40, "a b", '"quoted"', "%ff", "../etc"])
def test_a_hostile_cookie_finds_nothing(client, app, value):
    client.set_cookie(held.COOKIE, value, path="/api")
    assert client.get("/api/analyses/held").status_code == 404
    assert client.post("/api/analyses/claim", headers=bearer(user())).status_code == 404


@pytest.mark.parametrize("value", ["x" * 10_000, "é" * 40, " ", "../etc"])
def test_a_hostile_token_header_is_refused(client, app, value):
    assert client.post("/api/analyses/hold", headers={"X-Analysis-Token": value}).status_code == 404
    assert _cookie(client) is None


# ── Fix round 1: a draft held after the session lapsed must not outlive logout ─
#
# Decision 38: an expired session is a signed-out one, so the form's draft goes
# to the cookie. On a shared computer that row would otherwise stay readable at
# /held, and claimable by whoever signs in next, for 48 hours after logout.

def _logout(client, headers=None):
    """POST /logout, then back to what the request committed."""
    res = client.post("/api/auth/logout", headers=headers or {})
    _reload()
    return res


def test_logout_deletes_the_draft_a_lapsed_session_left_in_the_cookie(client, app):
    lapsed = expired_bearer(user())
    saved = client.post("/api/analyses/draft", json={"inputs": P1_INPUTS}, headers=lapsed)
    assert (saved.status_code, saved.get_json()["held"]) == (201, True)
    key = _cookie(client)

    res = _logout(client, headers=lapsed)           # no live session to log out of

    assert res.status_code == 200
    assert Analysis.query.count() == 0              # gone, and committed
    value, attrs = _set_cookie(res)
    assert (value, attrs["path"], attrs["max-age"]) == ("", "/api", "0")
    assert _cookie(client) is None
    assert client.get("/api/analyses/held").status_code == 404
    # The server forgot it too, not only the browser: the old key finds nothing.
    client.set_cookie(held.COOKIE, key, path="/api")
    assert client.get("/api/analyses/held").status_code == 404
    assert client.post("/api/analyses/claim", headers=bearer(user("suivant@test.fr"))).status_code == 404


def test_logout_leaves_a_kept_report_to_its_own_link_and_clears_the_cookie(client, app):
    report, key = _kept_report(client)

    res = _logout(client)

    assert res.status_code == 200
    assert db.session.get(Analysis, report.id) is not None
    assert client.get("/api/analyses/by-token", headers={"X-Analysis-Token": key}).status_code == 200
    value, attrs = _set_cookie(res)
    assert (value, attrs["path"]) == ("", "/api")
    assert _cookie(client) is None


def test_logout_with_no_cookie_and_no_session_answers_as_before(client, app):
    res = client.post("/api/auth/logout")
    assert res.status_code == 200
    assert res.get_json() == {"message": "Déconnecté."}
    names = {header.split("=", 1)[0] for header in res.headers.getlist("Set-Cookie")}
    assert {"neoori_access", "neoori_refresh"} <= names     # the JWT pair still goes


def test_logout_deletes_only_the_draft_its_own_cookie_points_at(client, app):
    elsewhere = app.test_client()                   # another browser, its own held draft
    _held_draft(elsewhere)
    _held_draft(client)

    assert _logout(client).status_code == 200
    assert Analysis.query.count() == 1
    assert _logout(app.test_client()).status_code == 200            # no cookie: nothing to delete
    assert Analysis.query.count() == 1
    assert elsewhere.get("/api/analyses/held").status_code == 200


def test_logout_still_ends_the_session_when_the_draft_cannot_be_deleted(client, app, monkeypatch):
    # Logout touched no database before this fix, so it must not start failing
    # on one: a 500 here would leave the HttpOnly session cookies in place.
    _held_draft(client)

    def database_gone():
        raise OperationalError("DELETE", {}, Exception("database is gone"))

    monkeypatch.setattr(held, "drop_held_draft", database_gone)
    res = client.post("/api/auth/logout")

    assert res.status_code == 200
    assert res.get_json() == {"message": "Déconnecté."}
    names = {header.split("=", 1)[0] for header in res.headers.getlist("Set-Cookie")}
    assert {"neoori_access", "neoori_refresh", held.COOKIE} <= names
    assert _cookie(client) is None          # the browser forgets the key; the row expires


def test_logout_never_deletes_an_owned_row(client, app):
    # Unreachable through the app (attach() clears the key). This pins that
    # logout goes through the held-row guard and never reaches an account's data.
    key = new_access_token()
    db.session.add(Analysis(user_id=user().id, status="draft", inputs={},
                            access_token_hash=hash_token(key)))
    db.session.commit()
    client.set_cookie(held.COOKIE, key, path="/api")
    assert _logout(client).status_code == 200
    assert Analysis.query.count() == 1


def test_a_signed_out_save_says_it_is_held_and_a_signed_in_one_does_not(client, app):
    created = _held_draft(client)
    updated = _held_draft(client)
    assert (created.status_code, created.get_json()["held"]) == (201, True)
    assert (updated.status_code, updated.get_json()["held"]) == (200, True)

    u = user()
    signed_in = client.post("/api/analyses/draft", json={"inputs": P1_INPUTS}, headers=bearer(u))
    assert signed_in.status_code == 201 and "held" not in signed_in.get_json()
    again = client.post("/api/analyses/draft", headers=bearer(u), json={
        "inputs": P1_INPUTS, "draft_id": signed_in.get_json()["analysis"]["id"],
    })
    assert again.status_code == 200 and "held" not in again.get_json()


# ── Final review (ruling R39): only the round trip this browser started marks ─
#
# A held row may be the leftover of someone else on this browser: « Avec mon
# compte » or « Garder », then no signup. A later signup that did not start
# from one of those round trips — from the landing through « Se connecter »
# (no `next`), or from /espace — must not take it over: verify-email would
# attach the stranger's CV to the new account for good, and the purge would
# never select it again.

ROUND_TRIPS = [
    "/analyse/nouveau?reprendre=compte",
    "/analyse/nouveau?reprendre=promo",
    "/analyse/nouveau?reprendre=brouillon",        # ruling R14's lapsed-session link
    "/espace?garder=1",                            # « Créer un compte pour le garder »
]


def _unmarked_and_still_held():
    row = Analysis.query.one()
    assert (row.pending_user_id, row.user_id) == (None, None)
    assert row.access_token_hash is not None       # still the browser's, and expires with it


@pytest.mark.parametrize("next_path", ROUND_TRIPS)
def test_each_round_trip_signup_marks_and_verify_attaches(client, app, next_path):
    _held_draft(client)
    account = _signup(client, next_path=next_path)
    assert Analysis.query.one().pending_user_id == account.id
    assert _verify(client, account).status_code == 200
    row = Analysis.query.one()
    assert (row.user_id, row.access_token_hash, row.pending_user_id) == (account.id, None, None)


def test_a_signup_heading_for_espace_marks_nothing(client, app):
    _held_draft(client)
    account = _signup(client, next_path="/espace")
    _unmarked_and_still_held()
    assert _verify(client, account).status_code == 200     # the registrant's proof...
    _unmarked_and_still_held()                             # ...attaches nothing either


def test_a_signup_with_no_next_marks_nothing(client, app):
    _held_draft(client)
    _signup(client, next_path=None)
    _unmarked_and_still_held()


@pytest.mark.parametrize("next_path", [
    "/espace?garder=1&x=1",                        # starts with an allowed value
    "/analyse/nouveau?reprendre=compte&x=1",
    "/analyse/nouveau?reprendre=comptes",
    "/analyse/nouveau?reprendre=promo#x",
    "/espace?garder=10",
    "/espace/?garder=1",
    "/Espace?garder=1",
    "%2Fespace%3Fgarder%3D1",                      # compared as given, never decoded
])
def test_a_next_that_only_resembles_a_round_trip_marks_nothing(client, app, next_path):
    _held_draft(client)
    _signup(client, next_path=next_path)
    _unmarked_and_still_held()


def test_a_kept_report_is_not_marked_by_a_signup_from_elsewhere(client, app):
    _kept_report(client)
    _signup(client, next_path="/espace")
    _unmarked_and_still_held()
