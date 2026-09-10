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
