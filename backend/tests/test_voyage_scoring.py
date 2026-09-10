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


def test_top3_is_ordered_by_magnitude():
    """The ordering assertion this name actually promises.

    The axis-id tie-break is pinned in test_top3_picks_the_pole_the_sign_points_to
    (top3[0]["axis"] == "A4"), not here.

    score_s0 filters resultant == 0 out of `ranked` before taking [:3], but that
    filter is unreachable through top3: every axis resultant has the parity of
    its item count, and A1 (1 item), A2 (3) and A6 (5) are odd, so at least
    three axes are always non-zero and a zero-resultant axis can never reach
    ranked[:3]. Kept anyway as cheap insurance for if the PM ever adds
    session-0 items and changes an axis's parity.
    """
    result = scoring.score_s0(_answers())
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


def test_score_riasec_breaks_a_real_tie_by_letter_order():
    """A genuine tie, not a hypothetical one.

    S1-5 B gives R 4/12 and C 3/9 — both 0.333. RIASEC_LETTERS order puts R
    before C; alphabetical order would put C first, so this is the assertion
    that makes the documented tie-break load-bearing rather than decorative.
    """
    result = scoring.score_riasec(_answers(**{"S1-5": "B"}))
    assert result["normalized"]["R"] == result["normalized"]["C"] == 0.333
    assert [e["letter"] for e in result["top3"]] == ["I", "R", "C"]


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


# ── Session 2 — needs (SDT) and values (Schwartz) ────────────────────────────

def test_score_s2_is_none_until_session_2_is_complete():
    assert scoring.score_s2({"answers": {"S2-1": "A"}, "billets": {}}) is None


def test_score_s2_counts_only_session_2():
    """S3-4 D carries a schwartz tag. It must not reach this tally."""
    result = scoring.score_s2(_answers(**{"S3-4": "D"}))
    without = scoring.score_s2(_answers(**{"S3-4": "A"}))
    assert result["schwartz"] == without["schwartz"]


def test_score_s2_reports_every_key_including_zeros():
    result = scoring.score_s2(_answers())
    assert set(result["sdt"]) == set(bank.SDT)
    assert set(result["schwartz"]) == set(bank.SCHWARTZ)
    assert all(isinstance(v, int) for v in result["schwartz"].values())


def test_score_s2_dominant_is_a_list_of_all_tied_maxima():
    """Concrete values, not a recomputation of _dominant's own logic.

    Under the all-A fixture, schwartz has a genuine two-way tie at 2
    (reussite and bienveillance), which is what pins the rule that ties are
    reported in full, in SCHWARTZ order, rather than broken arbitrarily.
    """
    result = scoring.score_s2(_answers())
    assert result["sdt"] == {"autonomie": 1, "appartenance": 0, "competence": 0}
    assert result["sdt_dominant"] == ["autonomie"]
    assert result["schwartz"]["reussite"] == 2
    assert result["schwartz"]["bienveillance"] == 2
    assert result["schwartz_dominant"] == ["reussite", "bienveillance"]


def test_score_s2_ambivalences_is_the_s2_7_choice():
    result = scoring.score_s2(_answers(**{"S2-7": "F"}))
    assert result["ambivalences"] == {
        "item_id": "S2-7",
        "letter": "F",
        "label": "Liberté / Indépendance",
        "plain": "tu veux que ta vie t'appartienne",
    }


# ── Session 3 — Big Five and cognitive style ─────────────────────────────────

def test_score_s3_is_none_until_session_3_is_complete():
    assert scoring.score_s3({"answers": {"S3-1": "A"}, "billets": {}}) is None


def test_score_s3_nets_are_signed():
    """All A: nevrotisme picks up -1 from S3-1 A, -1 from S3-3 A, -1 from
    S3-5 A; extraversion +1 from S3-1 A and +1 from S3-3 A, -1 from S3-6 A
    and -1 from S3-7 B... — assert the sign, not a hand-summed total."""
    result = scoring.score_s3(_answers())
    assert set(result["big5"]) == set(bank.BIG5)
    assert result["big5"]["nevrotisme"] < 0

    all_d = _answers(**{f"S3-{k}": "D" for k in range(1, 8)})
    assert scoring.score_s3(all_d)["big5"]["nevrotisme"] > (
        scoring.score_s3(_answers())["big5"]["nevrotisme"]
    )


def test_score_s3_levels_use_the_plus_or_minus_two_thresholds():
    """Concrete values, not a recomputation of _level's own branching.

    The all-A fixture happens to exercise all three branches: Élevé at +3,
    Faible at -3, and Moyen at 0 and +1.
    """
    result = scoring.score_s3(_answers())
    assert result["big5"] == {
        "ouverture": 3, "conscienciosite": 1, "extraversion": 1,
        "agreabilite": 0, "nevrotisme": -3,
    }
    assert result["levels"] == {
        "ouverture": scoring.LEVEL_HIGH,
        "conscienciosite": scoring.LEVEL_MID,
        "extraversion": scoring.LEVEL_MID,
        "agreabilite": scoring.LEVEL_MID,
        "nevrotisme": scoring.LEVEL_LOW,
    }


def test_score_s3_style_counts_only_options_that_carry_one():
    """S3-4 D carries no style. Choosing it must not raise or invent one.

    Four of the seven all-A options carry no style (S3-2 A, S3-4 A, S3-5 A, S3-6 A).
    """
    result = scoring.score_s3(_answers(**{"S3-4": "D"}))
    assert set(result["style"]) == set(bank.STYLES)
    assert sum(result["style"].values()) == 3   # four of the seven all-A options carry no style
    assert result["style"] == {"holistique": 2, "sequentiel": 1, "adaptatif": 0, "consultatif": 0}
    assert result["style_dominant"] == ["holistique"]


def test_score_s3_intro_extra_is_plain_french_never_a_trait_name():
    """The extraversion net is +1 under this fixture, inside the band, so the
    middle phrasing is the right one. Pinned exactly rather than merely
    asserted to be one of the three."""
    result = scoring.score_s3(_answers())
    assert result["big5"]["extraversion"] == 1
    assert result["intro_extra"] == scoring.INTRO_EXTRA["mid"]
    assert result["intro_extra"] == "à l'aise dans les deux registres"
    lowered = result["intro_extra"].lower()
    assert "introversion" not in lowered and "extraversion" not in lowered


def test_dominant_reports_nothing_when_every_count_is_zero():
    """An all-zero tally has no dominant value — reporting every key would be
    worse than reporting none, since a counselor reads this aloud.

    S2-6 is the only sdt-carrying option reachable in the default fixture, so
    answering it B zeroes the whole tally.
    """
    result = scoring.score_s2(_answers(**{"S2-6": "B"}))
    assert result["sdt"] == {"autonomie": 0, "appartenance": 0, "competence": 0}
    assert result["sdt_dominant"] == []


# ── Session 4 — the environment ──────────────────────────────────────────────

def test_score_s4_maps_scene_position_to_slot():
    """All six slots pinned by value.

    The slot mapping is positional, so a transposition is silent: it yields a
    different but still plausible string. Note that asserting the dict's KEYS
    proves nothing here — score_s4 draws them from S4_SLOTS by construction,
    so they match in order even when the pairing is wrong. Only the values
    test the pairing, and the letters below are chosen so all six env strings
    differ.
    """
    assert scoring.score_s4({"answers": {"S4-1": "A"}, "billets": {}}) is None
    result = scoring.score_s4(_answers(**{
        "S4-1": "A", "S4-2": "B", "S4-3": "C",
        "S4-4": "D", "S4-5": "A", "S4-6": "B",
    }))
    assert result == {
        "espace": "bureau fermé et calme",
        "rythme": "démarrage progressif",
        "equipe": "grande équipe diverse",
        "manager": "un cap clair",
        "irritant": "les réunions longues et bruyantes",
        "vendredi": "fatigue mais recharge",
    }
    assert list(result) == list(bank.S4_SLOTS)


def test_score_s5_keys_and_registers():
    assert scoring.score_s5({"answers": {"S5-1": "A"}, "billets": {}}) is None
    result = scoring.score_s5(_answers(**{
        "S5-1": "C", "S5-2": "C", "S5-3": "D",
        "S5-4": "A", "S5-5": "B", "S5-6": "C", "S5-7": "A",
    }))
    assert result == {
        "risque": "Calculé",
        "rapport_echec": "elle analyse et recommence",
        "rapport_flou": "elle crée son propre cadre",
        "valeur_centrale": "l'injustice",
        "trace": "une trace dans les gens",
        "sacrifice": "le temps",
        "vivant": "elle crée",
    }


def test_score_s5_risque_is_one_of_the_four_levels():
    """Pinned per letter, not merely asserted to be a member of RISK_LEVELS —
    membership alone would pass an implementation that returned the same
    level for every answer, or scrambled the mapping."""
    expected = {"A": "Fort", "B": "Modéré", "C": "Calculé", "D": "Faible"}
    for letter, level in expected.items():
        result = scoring.score_s5(_answers(**{"S5-1": letter}))
        assert result["risque"] == level, f"S5-1={letter}"
        assert result["risque"] in bank.RISK_LEVELS


# ── Synthesis sheet ──────────────────────────────────────────────────────────

SECTION_KEYS = ("s0", "riasec", "s2", "s3", "s4", "s5")


def test_synthesize_never_returns_none_and_always_has_every_key():
    result = scoring.synthesize({"answers": {}, "billets": {}})
    assert result is not None
    assert set(result) == {"scoring_version", "completeness", *SECTION_KEYS}
    assert result["scoring_version"] == bank.SCORING_VERSION
    assert all(result[key] is None for key in SECTION_KEYS)
    assert result["completeness"] == dict.fromkeys(bank.SESSION_IDS, False)


def test_synthesize_s0_only_is_a_normal_state():
    """The self-serve half of the product produces exactly this."""
    s0_only = {"answers": {i: True for i in bank.item_ids("0")}, "billets": {}}
    result = scoring.synthesize(s0_only)
    assert result["s0"] is not None
    assert all(result[key] is None for key in ("riasec", "s2", "s3", "s4", "s5"))
    assert result["completeness"] == {
        "0": True, "1": False, "2": False, "3": False, "4": False, "5": False,
    }


def test_synthesize_complete_fills_every_section():
    result = scoring.synthesize(_answers())
    assert all(result[key] is not None for key in SECTION_KEYS)
    assert result["completeness"] == dict.fromkeys(bank.SESSION_IDS, True)
    assert set(result["s0"]) == {"axes", "tensions", "top3"}
    assert set(result["riasec"]) == {"scores", "maxima", "normalized", "top3"}
    assert set(result["s2"]) == {
        "sdt", "sdt_dominant", "schwartz", "schwartz_dominant", "ambivalences",
    }
    assert set(result["s3"]) == {
        "big5", "levels", "style", "style_dominant", "intro_extra",
    }
    assert set(result["s4"]) == set(bank.S4_SLOTS)
    assert set(result["s5"]) == {
        "risque", "rapport_echec", "rapport_flou",
        "valeur_centrale", "trace", "sacrifice", "vivant",
    }


def test_synthesize_is_pure():
    """Same answers, same sheet — twice, and without touching the bank."""
    responses = _answers()
    assert scoring.synthesize(responses) == scoring.synthesize(responses)
    assert bank.SESSIONS[0]["items"][0]["text"] == (
        "Travailler dehors, sur le terrain, en mouvement"
    )


# ── prompt_context — the reduced block, with no numbers in it ───────────────

import re
import unicodedata

BANNED_ROOTS = (
    "nevrotisme", "neuroticisme", "big five", "riasec", "schwartz", "sdt", "dunn",
    "kahneman", "dweck", "frankl", "logotherapie", "conscienciosite", "agreabilite",
    "extraversion", "introversion", "score", "trait", "axe",
)

# Pins the ordered label sequence of the validated-stage block: this pins
# count, presence and order in one assertion, and stays stable when a
# scorer's values legitimately change — unlike pinning all nine lines
# verbatim, which would couple these tests to every scorer's output.
EXPECTED_LABELS = [
    "Phrase révélée",
    "Ce qui l'attire le plus dans dix ans",
    "Univers dominants",
    "Besoin dominant",
    "Ambivalences relevées",
    "Cadre où elle donne le meilleur",
    "Ce qui l'épuise",
    "Ce qui la met en colère",
    "Se sent vivant(e) quand",
]


def _fold(text):
    stripped = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in stripped if unicodedata.category(c) != "Mn")


def test_prompt_context_s0_stage_is_the_phrase_and_the_attractions():
    synthesis = scoring.synthesize(_answers())
    lines = scoring.prompt_context(synthesis, "Une phrase.", scoring.STAGE_S0)
    assert [line.split(" : ", 1)[0] for line in lines] == EXPECTED_LABELS[:2]
    assert lines[0] == "Phrase révélée : Une phrase."
    assert lines[1].startswith("Ce qui l'attire le plus dans dix ans : ")


def test_prompt_context_validated_stage_adds_the_rest():
    """The ordered label sequence pins count, presence and order in one
    assertion, and stays stable when a scorer's values legitimately change —
    unlike pinning all nine lines verbatim, which would couple this test to
    every scorer's output.
    """
    synthesis = scoring.synthesize(_answers())
    lines = scoring.prompt_context(synthesis, "Une phrase.", scoring.STAGE_VALIDATED)
    assert [line.split(" : ", 1)[0] for line in lines] == EXPECTED_LABELS
    assert lines[0] == "Phrase révélée : Une phrase."
    assert lines[2] == "Univers dominants : Investigateur, Réaliste, Conventionnel"
    assert lines[8] == "Se sent vivant(e) quand : elle crée"


def test_prompt_context_never_emits_a_digit():
    """A number in the block is a score reaching the report, whatever it counts."""
    synthesis = scoring.synthesize(_answers())
    for stage in scoring.STAGES:
        lines = scoring.prompt_context(synthesis, "Une phrase.", stage)
        assert lines, stage
        for line in lines:
            assert not re.search(r"[0-9]", line), line


def test_prompt_context_never_emits_a_framework_word():
    synthesis = scoring.synthesize(_answers())
    for stage in scoring.STAGES:
        lines = scoring.prompt_context(synthesis, "Une phrase.", stage)
        assert lines, stage
        for line in lines:
            folded = _fold(line)
            for word in BANNED_ROOTS:
                assert not re.search(rf"\b{re.escape(word)}\b", folded), f"{word}: {line}"


def test_prompt_context_never_emits_a_level_or_an_axis_label():
    synthesis = scoring.synthesize(_answers())
    lines = scoring.prompt_context(synthesis, "p", scoring.STAGE_VALIDATED)
    joined = "\n".join(lines)
    for level in (scoring.LEVEL_HIGH, scoring.LEVEL_MID, scoring.LEVEL_LOW):
        assert level not in joined
    for axis in bank.AXES.values():
        assert axis["label"] not in joined
        assert axis["pos"] not in joined
        assert axis["neg"] not in joined


def test_prompt_context_omits_a_line_rather_than_printing_an_empty_label():
    synthesis = scoring.synthesize({"answers": {}, "billets": {}})
    assert scoring.prompt_context(synthesis, None, scoring.STAGE_S0) == []
    lines = scoring.prompt_context(synthesis, "Une phrase.", scoring.STAGE_VALIDATED)
    assert lines == ["Phrase révélée : Une phrase."]
    for line in lines:
        assert not line.rstrip().endswith(":")


def test_prompt_context_treats_an_unknown_stage_as_s0():
    """Fail closed: an unrecognised stage must not leak the validated block."""
    synthesis = scoring.synthesize(_answers())
    unknown = scoring.prompt_context(synthesis, "p", "something-else")
    assert unknown == scoring.prompt_context(synthesis, "p", scoring.STAGE_S0)


def test_prompt_context_emits_only_what_exists_at_the_validated_stage():
    """The state most voyages actually sit in: session 0 done, 1-5 not.

    Session 0 is the self-serve half of the product and sessions 1-5 need a
    counselor, so this is the common case, not an edge case. It is also the
    only one where the stage rule and the omission rule interact — the
    validated stage asks for nine lines, six sources are None, and
    "Ambivalences relevées" still emits because it reads s0.tensions.
    """
    s0_only = scoring.synthesize(
        {"answers": {item_id: True for item_id in bank.item_ids("0")}, "billets": {}}
    )
    lines = scoring.prompt_context(s0_only, "Une phrase.", scoring.STAGE_VALIDATED)
    assert [line.split(" : ", 1)[0] for line in lines] == [
        "Phrase révélée",
        "Ce qui l'attire le plus dans dix ans",
        "Ambivalences relevées",
    ]
    assert lines[0] == "Phrase révélée : Une phrase."
    for line in lines:
        assert not line.rstrip().endswith(":")
