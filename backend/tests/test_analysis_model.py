"""Analysis.to_dict() — parcours resolution, counselor filter, sections_meta."""

from datetime import datetime

import pytest

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
