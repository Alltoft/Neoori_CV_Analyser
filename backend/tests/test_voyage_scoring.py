"""Scoring — the arithmetic behind the counselor's synthesis sheet.

Every number a counselor reads and every plain-French line a prompt receives is
produced here, from the answers alone. There is no model in this path, so these
tests are the whole of its correctness.
"""
import pytest

from app.services.voyage import bank, scoring


def _answers(**overrides):
    """A complete answer set: every S0 item False, every scene on option A."""
    answers = {item_id: False for item_id in bank.item_ids("0")}
    for n in ("1", "2", "3", "4", "5"):
        for item_id in bank.item_ids(n):
            answers[item_id] = "A"
    answers.update(overrides)
    return {"answers": answers, "billets": {}}


def test_module_constants():
    assert scoring.STAGES == (scoring.STAGE_S0, scoring.STAGE_VALIDATED)
    assert scoring.TENSION_BAND == (-2, 2)
    assert scoring.TENSION_MIN_ITEMS == 2
    assert (scoring.BIG5_HIGH, scoring.BIG5_LOW) == (2, -2)
    assert (scoring.LEVEL_HIGH, scoring.LEVEL_MID, scoring.LEVEL_LOW) == (
        "Élevé", "Moyen", "Faible",
    )
    assert set(scoring.INTRO_EXTRA) == {"high", "mid", "low"}


def test_missing_items_and_session_complete():
    empty = {"answers": {}, "billets": {}}
    assert scoring.missing_items(empty, "0") == bank.item_ids("0")
    assert scoring.session_complete(empty, "0") is False

    full = _answers()
    assert scoring.missing_items(full, "0") == []
    assert scoring.session_complete(full, "0") is True

    partial = {"answers": {"S0-01": True}, "billets": {}}
    assert "S0-01" not in scoring.missing_items(partial, "0")
    assert len(scoring.missing_items(partial, "0")) == 19


def test_missing_items_rejects_an_invalid_value():
    """A stored answer that no longer validates leaves the session incomplete
    rather than scoring as something arbitrary."""
    bad = {"answers": {item_id: "Z" for item_id in bank.item_ids("1")}, "billets": {}}
    assert scoring.missing_items(bad, "1") == bank.item_ids("1")


def test_completeness_is_keyed_by_session_id():
    assert scoring.completeness({"answers": {}, "billets": {}}) == {
        "0": False, "1": False, "2": False, "3": False, "4": False, "5": False,
    }
    assert scoring.completeness(_answers()) == {
        "0": True, "1": True, "2": True, "3": True, "4": True, "5": True,
    }


def test_chosen_option():
    responses = _answers(**{"S1-1": "C"})
    assert scoring.chosen_option(responses, "S1-1")["label"] == "Les prospecteurs"
    assert scoring.chosen_option({"answers": {}, "billets": {}}, "S1-1") is None
    assert scoring.chosen_option(responses, "S0-01") is None   # checklist, no options
