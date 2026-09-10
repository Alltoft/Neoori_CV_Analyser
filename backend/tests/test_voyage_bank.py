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


import pytest

SCENE_KEYS = {"id", "title", "subtitle", "narrative", "question", "options"}
OPTION_MANDATORY = {"letter", "label", "text", "plain"}


@pytest.mark.parametrize("n", [s["n"] for s in bank.SESSIONS if s["kind"] == bank.KIND_SCENES])
def test_scene_sessions_are_well_formed(n):
    session = _session(n)
    assert session["kind"] == bank.KIND_SCENES
    for scene in session["items"]:
        assert set(scene) == SCENE_KEYS, scene["id"]
        assert scene["id"].startswith(f"S{n}-")
        assert scene["title"].strip() and scene["subtitle"].strip()
        assert scene["question"].strip()
        assert isinstance(scene["narrative"], list)
        assert 4 <= len(scene["options"]) <= 8, scene["id"]
        letters = [o["letter"] for o in scene["options"]]
        assert letters == sorted(letters), scene["id"]
        assert len(set(letters)) == len(letters), scene["id"]
        for option in scene["options"]:
            assert OPTION_MANDATORY <= set(option), f"{scene['id']}{option['letter']}"
            extra = set(option) - OPTION_MANDATORY
            assert extra, f"{scene['id']}{option['letter']} carries no tag"
            assert extra <= set(bank.TAG_KEYS), f"{scene['id']}{option['letter']}: {extra}"
            assert option["plain"] == option["plain"].lower() or "'" in option["plain"]


def test_session_1_header_and_scene_ids():
    s1 = _session("1")
    assert s1["title"] == "Ce que tu faisais naturellement"
    assert s1["subtitle"] == "Là où tout a commencé… · 6 scènes de ton enfance"
    assert s1["duration"] == "15–20 min"
    assert [i["id"] for i in s1["items"]] == [f"S1-{k}" for k in range(1, 7)]
    assert [b["key"] for b in s1["billet"]] == ["cabane", "jeu", "fierte", "regard"]


def test_session_1_every_option_carries_riasec():
    for scene in _session("1")["items"]:
        for option in scene["options"]:
            assert "riasec" in option, f"{scene['id']}{option['letter']}"
            for letter, points in option["riasec"].items():
                assert letter in bank.RIASEC_LETTERS
                assert points in (1, 2), f"{scene['id']}{option['letter']}"


def test_session_1_scene_shapes():
    """S1-6 is the only eight-option scene."""
    counts = {s["id"]: len(s["options"]) for s in _session("1")["items"]}
    assert counts == {"S1-1": 6, "S1-2": 6, "S1-3": 6, "S1-4": 6, "S1-5": 6, "S1-6": 8}


def test_riasec_maxima_are_computed_not_copied():
    """The manual prints E 10 / C 10. Summing the best option per scene gives
    E 11 / C 9 — the manual's two transcription slips (spec errata 17b)."""
    assert bank.riasec_maxima() == {"R": 12, "I": 11, "A": 10, "S": 10, "E": 11, "C": 9}
