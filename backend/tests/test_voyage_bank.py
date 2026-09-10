"""Bank integrity — the 53 items, their weights, and what public() must not leak.

The bank is the one place where a transcription slip produces wrong software
that still runs: every option would still render, every score would still add
up, and the portrait would simply be about a different person. These tests are
the transcription's proof.
"""
import json

from app.services.voyage import bank


def test_module_constants():
    assert bank.SCORING_VERSION == "cahier-2026-09"
    assert bank.SESSION_IDS == ("0", "1", "2", "3", "4", "5")
    assert bank.KIND_CHECKLIST == "checklist"
    assert bank.KIND_SCENES == "scenes"
    assert bank.RIASEC_LETTERS == ("R", "I", "A", "S", "E", "C")
    assert set(bank.RIASEC_UNIVERS) == set(bank.RIASEC_LETTERS)
    assert bank.SDT == ("autonomie", "appartenance", "competence")
    assert len(bank.SCHWARTZ) == 11
    assert bank.BIG5 == (
        "ouverture", "conscienciosite", "extraversion", "agreabilite", "nevrotisme",
    )
    assert bank.STYLES == ("holistique", "sequentiel", "adaptatif", "consultatif")
    assert set(bank.STYLE_PLAIN) == set(bank.STYLES)
    assert bank.RISK_LEVELS == ("Fort", "Modéré", "Calculé", "Faible")
    assert bank.S4_SLOTS == (
        "espace", "rythme", "equipe", "manager", "irritant", "vendredi",
    )


def test_public_strip_covers_every_tag_key_plus_plain():
    """`plain` is prompt-facing, not UI-facing — it must be stripped too."""
    assert set(bank.PUBLIC_STRIP) == set(bank.TAG_KEYS) | {"plain"}


AXIS_KEYS = {"label", "neg", "pos", "plain_neg", "plain_pos", "tension"}


def test_axes_shape():
    assert list(bank.AXES) == [f"A{i}" for i in range(1, 11)]
    for axis_id, axis in bank.AXES.items():
        assert set(axis) == AXIS_KEYS, axis_id
        for key, value in axis.items():
            assert isinstance(value, str) and value.strip(), f"{axis_id}.{key}"


def test_plain_axis_wording_never_names_a_framework():
    """plain_* and tension reach the prompt. label/neg/pos never do."""
    banned = ("axe", "score", "riasec", "schwartz", "big five", "névrotisme")
    for axis_id, axis in bank.AXES.items():
        for key in ("plain_neg", "plain_pos", "tension"):
            lowered = axis[key].lower()
            for word in banned:
                assert word not in lowered, f"{axis_id}.{key} contains {word!r}"


def test_tension_wording_is_a_versus_pair():
    for axis_id, axis in bank.AXES.items():
        assert " vs " in axis["tension"], axis_id
        assert axis["tension"] == axis["tension"].lower(), axis_id


def test_axis_lookup():
    assert bank.axis("A9")["label"] == "Rapport au corps"
    import pytest
    with pytest.raises(KeyError):
        bank.axis("A99")


def _session(n):
    return next(s for s in bank.SESSIONS if s["n"] == n)


def test_session_0_header_and_counts():
    s0 = _session("0")
    assert s0["title"] == "Dans 10 ans"
    assert s0["subtitle"] == "Ta vision instinctive — 20 affirmations"
    assert s0["duration"] == "5 min"
    assert s0["kind"] == bank.KIND_CHECKLIST
    assert len(s0["items"]) == 20
    assert [b["key"] for b in s0["billet"]] == ["top3", "surprise"]


def test_session_0_item_ids_are_zero_padded():
    ids = [i["id"] for i in _session("0")["items"]]
    assert ids == [f"S0-{n:02d}" for n in range(1, 21)]


def test_session_0_axis_loadings():
    """The complete map, from the manual's 'Axe(s) principal(aux)' column."""
    expected = {
        "S0-01": [("A9", 1)],
        "S0-02": [("A2", 1), ("A5", 1)],
        "S0-03": [("A7", 1)],
        "S0-04": [("A2", 1), ("A4", 1)],
        "S0-05": [("A6", 1), ("A9", 1)],
        "S0-06": [("A6", 1), ("A8", 1)],
        "S0-07": [("A6", 1)],
        "S0-08": [("A1", 1)],
        "S0-09": [("A7", 1), ("A10", 1)],
        "S0-10": [("A5", 1), ("A6", 1)],
        "S0-11": [("A5", -1)],
        "S0-12": [("A2", 1), ("A4", 1)],
        "S0-13": [("A3", -1)],
        "S0-14": [("A3", 1)],
        "S0-15": [("A4", 1)],
        "S0-16": [("A8", 1), ("A10", 1)],
        "S0-17": [("A6", -1)],
        "S0-18": [("A7", 1)],
        "S0-19": [("A5", 1)],
        "S0-20": [("A4", -1), ("A7", 1)],
    }
    actual = {i["id"]: i["axes"] for i in _session("0")["items"]}
    assert actual == expected


def test_session_0_axis_item_counts():
    """A1 has exactly one item — that is why TENSION_MIN_ITEMS exists."""
    counts = {a: len(bank.axis_items(a)) for a in bank.AXES}
    assert counts == {
        "A1": 1, "A2": 3, "A3": 2, "A4": 4, "A5": 4,
        "A6": 5, "A7": 4, "A8": 2, "A9": 2, "A10": 2,
    }


def test_session_0_items_are_well_formed():
    for item in _session("0")["items"]:
        assert set(item) == {"id", "text", "axes"}
        assert item["text"].strip()
        assert item["axes"]
        seen = set()
        for axis_id, sign in item["axes"]:
            assert axis_id in bank.AXES
            assert sign in (1, -1)
            assert axis_id not in seen, f"{item['id']} loads {axis_id} twice"
            seen.add(axis_id)
