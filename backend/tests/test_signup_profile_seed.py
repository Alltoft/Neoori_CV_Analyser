"""Signup carries the two fields session 1 has always demanded.

session_lock has required a prénom and a tranche d'âge before S1 since the
voyage shipped. Asking for them mid-journey is a bounce to a form, which is the
one thing the PM's placement exists to remove: they are collected at the only
moment the person is already filling a form anyway.

Both stay optional on the wire — the old two-field shape still registers an
account, and nothing seeds a profile behind someone's back.
"""
from app.extensions import db
from app.models.profile import CONSENT_VERSION, Profile


def _register(client, email, **extra):
    return client.post("/api/auth/register",
                       json={"email": email, "password": "motdepasse", **extra})


def test_signup_seeds_the_profile_session_one_wants(client, app):
    res = _register(client, "seed@test.fr", consent=True,
                    prenom="Marie", tranche_age="18_21")
    assert res.status_code == 201

    profile = Profile.query.one()
    assert profile.prenom == "Marie"
    assert profile.tranche_age == "18_21"
    assert profile.consent_at is not None
    assert profile.consent_version == CONSENT_VERSION


def test_a_seeded_profile_opens_session_one(client, app):
    """The whole point: no LOCK_PROFILE bounce left to hit."""
    from app.models.voyage import LOCK_PROFILE, session_lock

    _register(client, "opens@test.fr", consent=True, prenom="Marie", tranche_age="22_24")
    profile = Profile.query.one()

    class _Voyage:
        has_code = True
        sessions_completed = ["0"]

    assert session_lock(_Voyage(), profile, "1") != LOCK_PROFILE
    assert session_lock(_Voyage(), profile, "1") is None


def test_signup_without_the_fields_seeds_nothing(client, app):
    """The old shape still registers an account, and a person who gave no
    profile data has no profile row to erase."""
    assert _register(client, "bare@test.fr").status_code == 201
    assert Profile.query.count() == 0


def test_the_seed_needs_the_consent_the_form_already_collects(client, app):
    """Same rule as PUT /api/profile: nothing is stored before the box is
    ticked. The signup form has always shown it — it just never sent it."""
    res = _register(client, "noconsent@test.fr", prenom="Marie", tranche_age="18_21")
    assert res.status_code == 400
    assert "consentement" in res.get_json()["error"].lower()
    assert Profile.query.count() == 0
    # and no half-made account either
    assert _register(client, "noconsent@test.fr", consent=True).status_code == 201


def test_the_seed_refuses_a_bracket_that_is_not_one(client, app):
    res = _register(client, "badbracket@test.fr", consent=True,
                    prenom="Marie", tranche_age="14_99")
    assert res.status_code == 400
    assert Profile.query.count() == 0


def test_a_legacy_bracket_still_seeds(client, app):
    """Accepted on write, never offered — the same rule the form follows."""
    assert _register(client, "legacy@test.fr", consent=True,
                     prenom="Marie", tranche_age="moins_25").status_code == 201
    assert Profile.query.one().tranche_age == "moins_25"


def test_a_prenom_alone_seeds_what_it_has(client, app):
    """The bracket is a select and the prénom a text field; a person who
    somehow sends one without the other keeps what they gave."""
    _register(client, "partial@test.fr", consent=True, prenom="Marie")
    profile = Profile.query.one()
    assert profile.prenom == "Marie"
    assert profile.tranche_age is None
