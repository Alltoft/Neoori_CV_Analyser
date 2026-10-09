"""Analysis.to_dict() — parcours resolution, sections_meta, the whole report."""

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

def test_parcours_resolves_the_legacy_path_code():
    assert _analysis("A").parcours == "1"


def test_retired_parcours_read_as_parcours_1():
    for retired in ("2", "3", "B"):
        assert _analysis(retired).parcours == "1"


def test_parcours_defaults_when_missing_or_unknown():
    assert Analysis(inputs=None).parcours == "1"
    assert Analysis(inputs={}).parcours == "1"
    assert _analysis("nonsense").parcours == "1"


# ── sections_meta ────────────────────────────────────────────────────────────

def test_sections_meta_is_ordered_and_typed():
    """Registry order is the contract: the verdict sits between §3 and §4,
    and a string sort would put §10 and §11 before §2."""
    meta = _analysis("1").to_dict()["sections_meta"]
    assert [m["key"] for m in meta] == [
        "1", "2", "3", "verdict", "4", "5", "6", "7", "8", "9", "10", "11",
    ]
    assert meta[0]["title"] == "Lecture stratégique du parcours"
    assert next(m for m in meta if m["key"] == "3")["render"] == "tags"
    assert next(m for m in meta if m["key"] == "1")["render"] == "markdown"


# ── the report ───────────────────────────────────────────────────────────────

def test_to_dict_keeps_every_generated_section():
    """One dict for every reader, the counselor's page included: nothing is
    filtered to a subset of sections any more."""
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
    """The voyage is never required — an analysis runs identically without
    one, and the key must still be there so the client need not branch."""
    payload = _analysis("1").to_dict()
    assert "voyage_id" in payload
    assert payload["voyage_id"] is None


# ── retired parcours ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("retired", ["2", "3", "B"])
def test_a_leftover_retired_row_is_served_as_parcours_1(retired):
    """Review Focus 2. Between the deploy and the purge, a P2/P3/'B' row must
    render as parcours 1 — never a 500."""
    row = Analysis(
        inputs={"_path": retired, "cv_text": "x"},
        output={"A": {"title": "Capital", "body_markdown": "b", "items": []}},
        status="success",
        created_at=datetime(2026, 9, 12),
    )
    _db.session.add(row)
    _db.session.commit()

    assert row.to_dict()["sections_meta"][0]["key"] == "1"
