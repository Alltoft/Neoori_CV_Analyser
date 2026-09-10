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


def test_score_s0_is_none_until_the_session_is_complete():
    assert scoring.score_s0({"answers": {"S0-01": True}, "billets": {}}) is None


def test_score_s0_sign_of_a_reversed_item():
    """S0-11 loads A5 negatively. OUI pushes A5 toward stability."""
    oui = scoring.score_s0(_answers(**{"S0-11": True}))
    non = scoring.score_s0(_answers(**{"S0-11": False}))
    # every other A5 item is False, so they each contribute -1 (sign +1, NON)
    assert oui["axes"]["A5"]["resultant"] == non["axes"]["A5"]["resultant"] - 2
    assert oui["axes"]["A5"]["oui"] == 1
    assert oui["axes"]["A5"]["non"] == 3


def test_score_s0_all_false_gives_every_positive_axis_its_full_negative():
    result = scoring.score_s0(_answers())
    # A9 has two items, both sign +1; both NON -> -2
    assert result["axes"]["A9"] == {
        "oui": 0, "non": 2, "resultant": -2, "n_items": 2, "tension": True,
    }
    assert set(result["axes"]) == set(bank.AXES)


def test_a1_is_never_a_tension_even_though_it_always_lands_in_the_band():
    """A1 has one item, so its resultant is always -1 or +1 — inside the band
    for every person alive. Flagging it would weight it x1.5 in every portrait."""
    for value in (True, False):
        result = scoring.score_s0(_answers(**{"S0-08": value}))
        assert result["axes"]["A1"]["n_items"] == 1
        assert result["axes"]["A1"]["resultant"] in (-1, 1)
        assert result["axes"]["A1"]["tension"] is False
        assert all(t["axis"] != "A1" for t in result["tensions"])


def test_tension_band_edges():
    result = scoring.score_s0(_answers())
    for entry in result["axes"].values():
        inside = scoring.TENSION_BAND[0] <= entry["resultant"] <= scoring.TENSION_BAND[1]
        expected = inside and entry["n_items"] >= scoring.TENSION_MIN_ITEMS
        assert entry["tension"] is expected


def test_tensions_are_ordered_by_axis_id_and_carry_plain_wording():
    result = scoring.score_s0(_answers())
    ids = [t["axis"] for t in result["tensions"]]
    assert ids == sorted(ids, key=lambda a: int(a[1:]))
    for entry in result["tensions"]:
        assert set(entry) == {"axis", "resultant", "label", "tension"}
        assert " vs " in entry["tension"]


def test_top3_picks_the_pole_the_sign_points_to():
    """Answer only the A7 items OUI: A7 resolves positive and ranks."""
    a7_items = [item_id for item_id, _ in bank.axis_items("A7")]
    result = scoring.score_s0(_answers(**{item_id: True for item_id in a7_items}))
    a7 = next((e for e in result["top3"] if e["axis"] == "A7"), None)
    assert a7 is not None, "A7 should rank in the top three"
    assert result["top3"][0]["axis"] == "A4", "ties break toward the lower axis id"
    assert a7["pole"] == "pos"
    assert a7["label"] == bank.AXES["A7"]["pos"]
    assert a7["plain"] == bank.AXES["A7"]["plain_pos"]
    assert len(result["top3"]) <= 3


def test_top3_excludes_zero_and_breaks_ties_by_axis_id():
    result = scoring.score_s0(_answers())
    for entry in result["top3"]:
        assert entry["resultant"] != 0
    magnitudes = [abs(e["resultant"]) for e in result["top3"]]
    assert magnitudes == sorted(magnitudes, reverse=True)


# ── Session 1 — RIASEC ───────────────────────────────────────────────────────

def test_score_riasec_is_none_until_session_1_is_complete():
    partial = {"answers": {"S1-1": "A"}, "billets": {}}
    assert scoring.score_riasec(partial) is None


def test_score_riasec_sums_the_chosen_options():
    """All A: S1-1 R1 I1 E1 C1 · S1-2 I2 C1 · S1-3 I2 R1 · S1-4 R2 C1
       · S1-5 R2 C1 · S1-6 I2."""
    result = scoring.score_riasec(_answers())
    assert result["scores"] == {"R": 6, "I": 7, "A": 0, "S": 0, "E": 1, "C": 4}
    assert result["maxima"] == bank.riasec_maxima()


def test_score_riasec_normalizes_against_each_letter_own_ceiling():
    result = scoring.score_riasec(_answers())
    assert result["normalized"]["R"] == round(6 / 12, 3)
    assert result["normalized"]["C"] == round(4 / 9, 3)
    for letter, value in result["normalized"].items():
        assert 0.0 <= value <= 1.0, letter


def test_score_riasec_top3_ranks_on_normalized_not_raw():
    result = scoring.score_riasec(_answers())
    assert len(result["top3"]) == 3
    order = [e["normalized"] for e in result["top3"]]
    assert order == sorted(order, reverse=True)
    assert result["top3"][0]["letter"] == "I"          # 7/11 = 0.636
    assert result["top3"][0]["univers"] == "Investigateur"
    assert set(result["top3"][0]) == {"letter", "univers", "score", "normalized"}
    assert [e["letter"] for e in result["top3"]] == ["I", "R", "C"]


def test_score_riasec_ties_break_on_letter_order():
    """A tie on normalized resolves R I A S E C, never alphabetically or by dict
    insertion — otherwise the same answers could rank differently across runs."""
    result = scoring.score_riasec(_answers())
    letters = [e["letter"] for e in result["top3"]]
    for first, second in zip(letters, letters[1:]):
        n_first = result["normalized"][first]
        n_second = result["normalized"][second]
        if n_first == n_second:
            assert bank.RIASEC_LETTERS.index(first) < bank.RIASEC_LETTERS.index(second)


def test_score_riasec_ranks_on_normalized_not_raw_where_they_disagree():
    """Answering S1-6 H gives R and C the SAME raw score against different
    ceilings — R out of 12, C out of 9. Ranked raw, R comes first on the
    letter-order tie-break; ranked normalised, C must come first, because
    6/9 beats 6/12. This is the case the whole normalisation exists for,
    and it is the only thing separating a correct implementation from one
    that sorts on the raw score."""
    result = scoring.score_riasec(_answers(**{"S1-6": "H"}))
    assert result["scores"]["R"] == 6
    assert result["scores"]["C"] == 6
    assert result["normalized"]["C"] > result["normalized"]["R"]
    assert [e["letter"] for e in result["top3"]] == ["C", "R", "I"]
