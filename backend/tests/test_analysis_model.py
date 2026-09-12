"""Analysis.to_dict() — parcours resolution, counselor filter, sections_meta."""

from datetime import datetime

import pytest

from app.extensions import db as _db
from app.models.analysis import Analysis


@pytest.fixture(autouse=True)
def _mappers(app):
    """Analysis declares a relationship to CounselorNote, so the mapper only
    configures once every model module is imported — which create_app() does."""
    yield


def _analysis(path, output=None):
    # created_at is nullable=False, but its default only fires on insert and
    # these are transient objects — set it so to_dict() can serialise.
    return Analysis(
        inputs={"_path": path},
        output=output,
        status="success",
        created_at=datetime(2026, 7, 29),
    )


# ── parcours resolution ──────────────────────────────────────────────────────

def test_parcours_resolves_legacy_path_codes():
    assert _analysis("A").parcours == "1"
    assert _analysis("B").parcours == "3"
    assert _analysis("2").parcours == "2"


def test_parcours_defaults_when_missing_or_unknown():
    assert Analysis(inputs=None).parcours == "1"
    assert Analysis(inputs={}).parcours == "1"
    assert _analysis("nonsense").parcours == "1"


# ── sections_meta ────────────────────────────────────────────────────────────

def test_sections_meta_is_ordered_and_typed():
    meta = _analysis("2").to_dict()["sections_meta"]
    assert [m["key"] for m in meta] == ["A", "C", "D", "verdict", "B", "E", "F", "G"]
    assert meta[0]["title"] == "Capital professionnel"
    # §C is the tag-cloud section for parcours 2
    assert next(m for m in meta if m["key"] == "C")["render"] == "tags"
    assert next(m for m in meta if m["key"] == "A")["render"] == "markdown"


def test_sections_meta_roman_order_is_not_lexicographic():
    """Sorted alphabetically this would be I, II, III, IV, V, VI -> wrong once
    IX/X exist; registry order is the contract, not any sort."""
    meta = _analysis("3").to_dict()["sections_meta"]
    assert [m["key"] for m in meta] == ["I", "II", "III", "verdict", "IV", "V", "VI"]


# ── counselor view ───────────────────────────────────────────────────────────

def test_counselor_view_filters_to_parcours_1_set():
    output = {k: {"title": k, "body_markdown": "b", "items": []}
              for k in ("1", "2", "3", "4", "5", "6")}
    data = _analysis("1", output).to_dict(audience="counselor")
    assert set(data["output"].keys()) == {"1", "4", "5"}
    assert [m["key"] for m in data["sections_meta"]] == ["1", "4", "5"]


def test_counselor_view_uses_the_right_set_per_parcours():
    """Regression: the filter was hardcoded to ('1','4','5') for every path,
    so a parcours-3 counselor link rendered empty skeletons."""
    output = {k: {"title": k, "body_markdown": "b", "items": []}
              for k in ("I", "II", "III", "IV", "V", "VI")}
    data = _analysis("3", output).to_dict(audience="counselor")
    assert set(data["output"].keys()) == {"I", "III", "V"}
    assert [m["key"] for m in data["sections_meta"]] == ["I", "III", "V"]


def test_candidate_view_keeps_every_generated_section():
    output = {k: {"title": k, "body_markdown": "b", "items": []} for k in ("1", "4", "5", "9")}
    data = _analysis("1", output).to_dict()
    assert set(data["output"].keys()) == {"1", "4", "5", "9"}


# ── voyage traceability ──────────────────────────────────────────────────────

def test_to_dict_carries_the_voyage_that_fed_the_analysis():
    """Same tier of data as prompt_version_id: which exploration produced this
    report, kept so a B2G file can be reconstructed after a retake."""
    analysis = _analysis("1")
    analysis.voyage_id = "voy-123"
    assert analysis.to_dict()["voyage_id"] == "voy-123"


def test_voyage_id_is_null_rather_than_absent_when_there_is_no_voyage():
    """The voyage is never required — every parcours runs identically without
    one, and the key must still be there so the client need not branch."""
    payload = _analysis("1").to_dict()
    assert "voyage_id" in payload
    assert payload["voyage_id"] is None


def test_the_counselor_view_carries_it_too():
    analysis = _analysis("1")
    analysis.voyage_id = "voy-456"
    assert analysis.to_dict(audience="counselor")["voyage_id"] == "voy-456"


# ── counselor view: inputs allow-list ───────────────────────────────────────
# GET /api/c/<share_token> is public and unauthenticated: anyone holding the
# link receives whatever to_dict(audience="counselor") puts in "inputs". The
# candidate's cv_text, the encrypted-profile-derived _conditions/_oeth lines,
# and the _voyage/_voyage_id lines must never be in that response -- the
# counselor page (frontend/src/app/c/[token]/page.tsx) never renders them.

# Keys the counselor page never reads -- must be stripped from a public link.
_SENSITIVE_INPUT_KEYS = {"cv_text", "_conditions", "_oeth", "_voyage", "_voyage_id"}

# Every analysis.inputs.X access in frontend/src/app/c/[token]/page.tsx
# (verified 2026-09-12): the parcours discriminator, the header name, and the
# "key facts" strip for both the parcours-1/2 layout and the parcours-3 one.
_RENDERED_INPUT_KEYS = {
    "_path", "prenom", "nom", "cible_visee", "type_mobilite",
    "situation_actuelle", "notes_specifiques",
    "_sub_profile", "aime", "refuse", "accompagnement",
}


def _full_inputs(**extra):
    """A submission carrying every sensitive key the counselor view must
    never leak, plus every key the counselor page actually renders."""
    data = {
        "cv_text": "Jean Dupont, 15 ans d'experience en logistique...",
        "_conditions": {"rqth": True, "amenagements": ["horaires"]},
        "_oeth": True,
        "_voyage": {"phrases": ["une phrase issue du parcours voyage"]},
        "_voyage_id": "voy-secret-1",
        "_path": "1",
        "prenom": "Camille",
        "nom": "Durand",
        "cible_visee": "Chef de projet logistique",
        "type_mobilite": "evolution",
        "situation_actuelle": "en poste",
        "notes_specifiques": "Anxieuse a l'idee de changer de secteur.",
        "_sub_profile": "b2",
        "aime": ["organiser", "negocier"],
        "refuse": ["itinerance"],
        "accompagnement": "a distance",
    }
    data.update(extra)
    return data


def _persisted_analysis(inputs, share_token=None):
    """Like _analysis() above, but written to the DB -- needed to hit the
    real HTTP route, which looks the row up by share_token instead of
    calling to_dict() directly."""
    a = Analysis(
        inputs=inputs,
        status="success",
        share_token=share_token,
        created_at=datetime(2026, 9, 12),
    )
    _db.session.add(a)
    _db.session.commit()
    return a


def test_public_share_link_hides_cv_text_and_sensitive_inputs(client):
    """The actual defect surface: no Authorization header at all. The
    response's inputs must be exactly the rendered set -- checked as an
    exact key-set match, never with `in` on a substring, so a sibling leak
    can't hide behind one correct key."""
    _persisted_analysis(_full_inputs(), share_token="tok-public-share")

    res = client.get("/api/c/tok-public-share")

    assert res.status_code == 200
    returned = set(res.get_json()["analysis"]["inputs"].keys())
    assert returned == _RENDERED_INPUT_KEYS
    assert returned.isdisjoint(_SENSITIVE_INPUT_KEYS)


def test_candidate_audience_still_gets_every_input_key(client):
    """Owner access is unchanged: the filter applies only to audience=
    "counselor". Same shape of analysis as the share-link test above."""
    inputs = _full_inputs()
    analysis = _persisted_analysis(inputs, share_token="tok-owner-view")

    data = analysis.to_dict()  # default audience="candidate"

    assert set(data["inputs"].keys()) == set(inputs.keys())
    assert data["inputs"]["cv_text"] == inputs["cv_text"]


def test_an_unknown_input_key_does_not_reach_the_counselor_payload():
    """The filter is an allow-list, not a deny-list: a key nobody has
    classified yet (a typo, or a field added later) must default to hidden,
    never shown."""
    analysis = Analysis(
        inputs=_full_inputs(_future_secret="x"),
        status="success",
        created_at=datetime(2026, 9, 12),
    )

    data = analysis.to_dict(audience="counselor")

    assert "_future_secret" not in data["inputs"]
    assert set(data["inputs"].keys()) == _RENDERED_INPUT_KEYS
