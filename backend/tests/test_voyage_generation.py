"""The voyage's two AI calls.

Everything the person will read comes out of these two calls, and two things
have to be true of both: the portrait always has its six sections (a JSON
schema, not a sentence in the prompt), and neither call ever hands the model —
or gets back — a score, a trait name or a framework name.
"""
import copy
import json
import re
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import anthropic
import httpx
import pytest

from app.extensions import db
from app.models.prompt_version import PromptVersion
from app.models.profile import Profile
from app.models.user import User
from app.models.voyage import Voyage
from app.services import prompt_slots, tiers
from app.services.voyage import bank, scoring
from app.services.voyage import generation as gen


# ── fixtures ─────────────────────────────────────────────────────────────────

PROFILE_FIELDS = {
    "prenom": "Marie",
    "tranche_age": "25_34",
    "situation": "en_recherche",
    "projet": "reprendre un travail au contact des gens",
}

# The literal synthesize() return value pinned in the contracts doc § B.5.
# `risque` is deliberately "Calculé": "Faible" is both a risk level and a Big
# Five level word, and the vocabulary assertions below would not be able to
# tell the legitimate one from a leak.
SYNTHESIS = {
    "scoring_version": "cahier-2026-09",
    "s0": {
        "axes": {
            "A1": {"oui": 0, "non": 1, "resultant": -1, "n_items": 1, "tension": False},
            "A2": {"oui": 1, "non": 2, "resultant": -1, "n_items": 3, "tension": True},
            "A3": {"oui": 1, "non": 1, "resultant": 0, "n_items": 2, "tension": True},
            "A4": {"oui": 3, "non": 1, "resultant": 2, "n_items": 4, "tension": True},
            "A5": {"oui": 2, "non": 2, "resultant": 1, "n_items": 4, "tension": True},
            "A6": {"oui": 3, "non": 2, "resultant": 1, "n_items": 5, "tension": True},
            "A7": {"oui": 4, "non": 0, "resultant": 4, "n_items": 4, "tension": False},
            "A8": {"oui": 1, "non": 1, "resultant": 0, "n_items": 2, "tension": True},
            "A9": {"oui": 2, "non": 0, "resultant": 2, "n_items": 2, "tension": True},
            "A10": {"oui": 2, "non": 0, "resultant": 2, "n_items": 2, "tension": True},
        },
        "tensions": [
            {"axis": "A2", "resultant": -1, "label": "Visibilité",
             "tension": "discrétion vs reconnaissance"},
            {"axis": "A3", "resultant": 0, "label": "Rapport au collectif",
             "tension": "solo vs collectif"},
            {"axis": "A4", "resultant": 2, "label": "Échelle d'impact",
             "tension": "impact local vs impact global"},
            {"axis": "A5", "resultant": 1, "label": "Sécurité vs risque",
             "tension": "sécurité vs risque"},
            {"axis": "A6", "resultant": 1, "label": "Type de création",
             "tension": "méthode vs expression libre"},
            {"axis": "A8", "resultant": 0, "label": "Temporalité de l'impact",
             "tension": "impact différé vs impact immédiat"},
            {"axis": "A9", "resultant": 2, "label": "Rapport au corps",
             "tension": "bureau vs terrain"},
            {"axis": "A10", "resultant": 2, "label": "Transmission vs expertise",
             "tension": "expertise vs transmission"},
        ],
        "top3": [
            {"axis": "A7", "resultant": 4, "pole": "pos",
             "label": "Lien humain direct", "plain": "le lien avec les gens"},
            {"axis": "A4", "resultant": 2, "pole": "pos",
             "label": "Impact global / systémique", "plain": "un impact visible"},
            {"axis": "A9", "resultant": 2, "pole": "pos",
             "label": "Terrain / action physique", "plain": "le terrain et l'action"},
        ],
    },
    "riasec": {
        "scores": {"R": 8, "I": 5, "A": 3, "S": 4, "E": 7, "C": 6},
        "maxima": {"R": 12, "I": 11, "A": 10, "S": 10, "E": 11, "C": 9},
        "normalized": {"R": 0.667, "I": 0.455, "A": 0.3, "S": 0.4, "E": 0.636, "C": 0.667},
        "top3": [
            {"letter": "R", "univers": "Réaliste", "score": 8, "normalized": 0.667},
            {"letter": "C", "univers": "Conventionnel", "score": 6, "normalized": 0.667},
            {"letter": "E", "univers": "Entreprenant", "score": 7, "normalized": 0.636},
        ],
    },
    "s2": {
        "sdt": {"autonomie": 3, "appartenance": 2, "competence": 1},
        "sdt_dominant": ["autonomie"],
        "schwartz": {"autodirection": 2, "stimulation": 0, "hedonisme": 0, "reussite": 1,
                     "pouvoir": 0, "securite": 0, "conformite": 1, "bienveillance": 3,
                     "universalisme": 2, "integrite": 0, "conservation": 0},
        "schwartz_dominant": ["bienveillance"],
        "ambivalences": {"item_id": "S2-7", "letter": "F",
                         "label": "Liberté / Indépendance",
                         "plain": "tu veux que ta vie t'appartienne"},
    },
    "s3": {
        "big5": {"ouverture": 3, "conscienciosite": -1, "extraversion": 2,
                 "agreabilite": 0, "nevrotisme": -2},
        "levels": {"ouverture": "Élevé", "conscienciosite": "Moyen", "extraversion": "Élevé",
                   "agreabilite": "Moyen", "nevrotisme": "Faible"},
        "style": {"holistique": 2, "sequentiel": 1, "adaptatif": 1, "consultatif": 3},
        "style_dominant": ["consultatif"],
        "intro_extra": "plutôt tourné(e) vers les autres",
    },
    "s4": {
        "espace": "bureau fermé et calme",
        "rythme": "cycles courts",
        "equipe": "petite équipe soudée",
        "manager": "confiance et droit à l'essai",
        "irritant": "les interruptions constantes",
        "vendredi": "besoin de calme",
    },
    "s5": {
        "risque": "Calculé",
        "rapport_echec": "elle analyse et recommence",
        "rapport_flou": "elle crée son propre cadre",
        "valeur_centrale": "l'injustice",
        "trace": "une trace dans les gens",
        "sacrifice": "le temps",
        "vivant": "elle crée",
    },
    "completeness": {"0": True, "1": True, "2": True, "3": True, "4": True, "5": True},
}

CLEAN_SECTIONS = {
    "accroche": "Tu cherches des endroits où ce que tu fabriques sert vraiment à quelqu'un.",
    "qui_tu_es": "Tu as tendance à comprendre avant d'agir. Quand on te laisse de la marge, "
                 "tu vas vite. Les journées hachées te demandent plus d'énergie.",
    "vibrer": "Ce qui te met en mouvement, c'est de voir le résultat de ce que tu fais.",
    "besoins": "Tu travailles mieux au calme, avec des cycles courts et une petite équipe.",
    "chemins": "Les endroits où on fabrique, où on répare, où on met en route quelque chose.",
    "pas_encore": "Il reste une question : ce dont tu as besoin pour tenir sur la durée.",
}

LEAKY_SECTIONS = {
    **CLEAN_SECTIONS,
    "qui_tu_es": "Ton score de névrotisme est bas et ton RIASEC est net.",
}


def _full_responses() -> dict:
    """Every one of the 53 items answered: OUI on session 0, the first option
    everywhere else. Built from the bank, so it survives a bank edit."""
    answers = {}
    for n in bank.SESSION_IDS:
        checklist = bank.session(n)["kind"] == bank.KIND_CHECKLIST
        for item in bank.items(n):
            answers[item["id"]] = True if checklist else item["options"][0]["letter"]
    return {"answers": answers, "billets": {}}


def _s0_only_responses() -> dict:
    full = _full_responses()
    s0 = set(bank.item_ids("0"))
    return {"answers": {k: v for k, v in full["answers"].items() if k in s0},
            "billets": {}}


_HEADER_RE = re.compile(r"^---\s.+\s---$", re.MULTILINE)


def _block(message: str, header: str) -> str:
    """The lines under `header`, up to the next --- ... --- header."""
    assert header in message, f"{header} missing from the message"
    rest = message.split(header, 1)[1]
    nxt = _HEADER_RE.search(rest)
    return rest[: nxt.start()] if nxt else rest


def _line(message: str, prefix: str) -> str:
    """The single line starting with `prefix`, with the prefix removed."""
    hits = [ln for ln in message.splitlines() if ln.startswith(prefix)]
    assert len(hits) == 1, f"expected exactly one line starting with {prefix!r}"
    return hits[0][len(prefix):]


# ── the portrait schema ──────────────────────────────────────────────────────

def test_the_portrait_schema_has_exactly_the_six_keys():
    schema = gen._portrait_schema()
    assert schema["type"] == "object"
    assert set(schema["properties"]) == set(gen.PORTRAIT_KEYS)
    assert schema["required"] == list(gen.PORTRAIT_KEYS)
    assert schema["additionalProperties"] is False


def test_every_portrait_property_is_a_described_string():
    """The description is where the per-section length and form rules live —
    the schema, not the prompt prose, is what the model cannot ignore."""
    for key, prop in gen._portrait_schema()["properties"].items():
        assert prop["type"] == "string", key
        assert prop["description"].strip(), key


def test_the_schema_keys_match_the_model_and_the_titles():
    from app.models import voyage as voyage_model
    assert tuple(gen.PORTRAIT_KEYS) == tuple(voyage_model.PORTRAIT_KEYS)
    assert tuple(gen.PORTRAIT_TITLES) == tuple(gen.PORTRAIT_KEYS)


def test_the_two_slots_are_the_ones_the_prompt_registry_knows():
    assert gen.MICRO_SLOT == prompt_slots.VOYAGE_MICRO
    assert gen.PORTRAIT_SLOT == prompt_slots.VOYAGE_PORTRAIT


def test_the_token_budgets_are_the_two_the_spec_pins_not_the_tier_defaults():
    """tiers.model_for() hands back 8000 for both plans. A one-sentence phrase
    does not need 8000, and the portrait is capped at 3000 on purpose."""
    assert gen.MICRO_MAX_TOKENS == 200
    assert gen.PORTRAIT_MAX_TOKENS == 3000
    assert gen.MICRO_WORDS == (15, 25)
    assert gen.PORTRAIT_MAX_TOKENS != tiers.model_for(tiers.PAID)[1]


def test_the_headers_and_the_two_flags_are_pinned_literally():
    """A header is a contract with prompt prose the PM edits from /admin/prompts
    without touching code: the stored system prompt addresses these blocks by
    name, so renaming one here silently breaks a prompt no test reads. That, not
    any ripple through this file, is why « --- SESSION 0 --- » keeps its digit.

    FLAG_VOCABULAIRE is the only value ever written into portrait["flags"] and
    ERROR_MAX_CHARS caps the encrypted payload's `error` key — both are read by
    the next batch's runners and by the counselor UI.
    """
    assert gen.HEADER_PROFIL == "--- PROFIL DE BASE ---"
    assert gen.HEADER_SESSION_0 == "--- SESSION 0 ---"
    assert gen.HEADER_CHOISI == "--- CE QUE TU AS CHOISI ---"
    assert gen.HEADER_SYNTHESE == "--- SYNTHÈSE ---"
    assert gen.WEIGHT_NOTE == " (à pondérer ×1,5)"
    assert gen.FLAG_VOCABULAIRE == "vocabulaire"
    assert gen.ERROR_MAX_CHARS == 500


# ── leak_check ───────────────────────────────────────────────────────────────

def test_a_clean_portrait_leaks_nothing():
    assert gen.leak_check(CLEAN_SECTIONS) == []


def test_the_word_portrait_does_not_trip_the_trait_pattern():
    """Word boundaries are the whole reason « trait » is safe to ban."""
    assert gen.leak_check({
        "accroche": "Ce portrait te ressemble.",
        "qui_tu_es": "Tu traites les choses une par une.",
    }) == []


def test_an_inflected_leak_is_caught_and_reported_under_its_canonical_word():
    """The optional trailing `s` and the [\\s-]+ join are the whole reason these
    three get caught. Reverting either leaves the suite green without this test."""
    assert gen.leak_check({"a": "Tes traits de personnalité ressortent."}) == ["trait"]
    assert gen.leak_check({"a": "Des scores élevés partout."}) == ["score"]
    assert gen.leak_check({"a": "Un profil Big-Five très net."}) == ["big five"]


def test_the_widening_does_not_swallow_ordinary_words():
    """« portrait » and « traites » are the words the boundary has to protect."""
    assert gen.leak_check(
        {"a": "Ce portrait te ressemble et tu traites tout à la suite."}) == []


def test_framework_words_come_back_lowercased_and_sorted():
    hit = gen.leak_check({"qui_tu_es": "Ton RIASEC est net.",
                          "vibrer": "Un Score élevé en Big Five."})
    assert hit == ["big five", "riasec", "score"]


def test_the_hits_come_back_sorted_and_deduplicated():
    """Schwartz is declared before Dunn in LEAK_PATTERNS and sorts after it, so
    this fixture tells « sorted » apart from « in declaration order » — a pair
    like riasec/score/trait cannot, their two orders coincide. « trait » is in
    both sections and must still come back once.
    """
    hit = gen.leak_check({
        "a": "Ton trait dominant, et Schwartz.",
        "b": "Encore un trait, et Dunn.",
    })
    assert hit == ["dunn", "schwartz", "trait"]


def test_accents_are_folded_so_one_entry_catches_both_spellings():
    assert gen.leak_check({"a": "névrotisme"}) == ["névrotisme"]
    assert gen.leak_check({"a": "nevrotisme"}) == ["névrotisme"]
    assert gen.leak_check({"a": "CONSCIENCIOSITE"}) == ["conscienciosité"]


def test_the_leak_vocabulary_is_the_one_the_contract_lists():
    """Pinned literally: the loop below tests the matcher, this tests the list.
    A typo here is a word that reaches a candidate, so it may not be derived
    from the thing it is checking."""
    assert gen.LEAK_PATTERNS == (
        "névrotisme", "neuroticisme", "big five", "riasec", "schwartz", "sdt",
        "dunn", "kahneman", "dweck", "frankl", "logothérapie", "conscienciosité",
        "agréabilité", "extraversion", "introversion", "score", "trait",
    )


def test_every_pattern_is_detected_on_its_own():
    for pattern in gen.LEAK_PATTERNS:
        assert gen.leak_check({"x": f"Une phrase avec {pattern} dedans."}) == [pattern]


def test_empty_and_missing_sections_are_tolerated():
    assert gen.leak_check({}) == []
    assert gen.leak_check(None) == []
    assert gen.leak_check({"accroche": None, "vibrer": ""}) == []


# ── _micro_user_message ──────────────────────────────────────────────────────

def test_the_micro_message_has_the_two_blocks_in_order():
    msg = gen._micro_user_message(SYNTHESIS, "Marie")
    assert msg.index(gen.HEADER_PROFIL) < msg.index(gen.HEADER_SESSION_0)
    assert "Prénom : Marie" in msg
    # The blank line between blocks is what keeps the headers legible to the
    # model — joining with a single "\n" would leave them buried in prose.
    assert f"\n\n{gen.HEADER_SESSION_0}" in msg


def test_the_micro_message_names_the_three_strongest_pulls_in_plain_french():
    msg = gen._micro_user_message(SYNTHESIS, "Marie")
    assert _line(msg, "Ce qui l'attire le plus : ") == (
        "le lien avec les gens, un impact visible, le terrain et l'action")


def test_the_micro_message_joins_the_tensions_with_a_middle_dot():
    msg = gen._micro_user_message(SYNTHESIS, "Marie")
    line = _line(msg, "Autant coché des deux côtés sur : ")
    assert line.split(" · ") == [t["tension"] for t in SYNTHESIS["s0"]["tensions"]]


def test_a_voyage_with_no_tension_gets_no_tension_line():
    """A label with nothing after it is worse than no label."""
    synthesis = copy.deepcopy(SYNTHESIS)
    synthesis["s0"]["tensions"] = []
    assert "Autant coché" not in gen._micro_user_message(synthesis, "Marie")


def test_the_profile_block_disappears_when_the_prenom_is_unknown():
    msg = gen._micro_user_message(SYNTHESIS, None)
    assert gen.HEADER_PROFIL not in msg
    assert "Prénom" not in msg
    assert msg.startswith(gen.HEADER_SESSION_0)


def test_an_s0_that_has_not_been_scored_yet_yields_an_empty_message():
    assert gen._micro_user_message({"s0": None}, None) == ""


def test_the_micro_message_carries_no_number_and_no_framework_word():
    """« --- SESSION 0 --- » is the block label the module pins as a constant,
    not a figure derived from the scoring, so it is stripped before the digit
    rule applies — the same carve-out the synthesis block makes for the
    manual's own ×1,5 note."""
    msg = gen._micro_user_message(SYNTHESIS, "Marie")
    assert not re.search(r"\d", msg.replace(gen.HEADER_SESSION_0, ""))
    assert gen.leak_check({"message": msg}) == []
    for word in ("Élevé", "Moyen", "Faible", "ouverture", "conscienciosite",
                 "A1", "A9", "A10", "Réaliste"):
        assert word not in msg


# ── _portrait_user_message ───────────────────────────────────────────────────

def _own_words(block: str) -> str:
    """The right-hand side of every « Titre : ce que la personne a choisi » line.

    The scene title is cahier text and S2-7's is « Dans 20 ans », so the digit
    rule can only apply to what comes after the colon.

    The assertion keeps the helper from degrading into a no-op: with no
    « Titre : … » line at all this returns "", and every digit rule resting on
    it would pass vacuously against a builder that had stopped emitting lines.
    """
    words = "\n".join(ln.split(" : ", 1)[1] for ln in block.splitlines() if " : " in ln)
    assert words, "no « Titre : … » line in the block — the digit rule would be vacuous"
    return words


def test_the_three_headers_appear_in_order():
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    assert (msg.index(gen.HEADER_PROFIL)
            < msg.index(gen.HEADER_CHOISI)
            < msg.index(gen.HEADER_SYNTHESE))
    # Blocks are separated by a blank line, not just a newline.
    assert f"\n\n{gen.HEADER_CHOISI}" in msg
    assert f"\n\n{gen.HEADER_SYNTHESE}" in msg


def test_the_profile_block_carries_the_four_fields_it_is_given():
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    assert "Prénom : Marie" in msg
    assert "Tranche d'âge : 25_34" in msg
    assert "Situation actuelle : en_recherche" in msg
    assert "Projet : reprendre un travail au contact des gens" in msg


def test_the_profile_block_keeps_the_profil_de_base_order():
    """The order is the Profil de base's own, the order the person filled the
    fields in — reordering the labels leaves every `in msg` assertion green."""
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    lines = [ln for ln in _block(msg, gen.HEADER_PROFIL).splitlines() if ln.strip()]
    assert lines == [
        "Prénom : Marie",
        "Tranche d'âge : 25_34",
        "Situation actuelle : en_recherche",
        "Projet : reprendre un travail au contact des gens",
    ]


def test_an_empty_profile_field_never_leaves_a_naked_label():
    """The three shapes an absent field arrives in: missing, "", and whitespace.
    The last one is the reason _profile_lines strips before testing truthiness —
    it is the rule the synthesis block borrows."""
    msg = gen._portrait_user_message(
        SYNTHESIS, _full_responses(),
        {"prenom": "Marie", "tranche_age": None, "situation": "", "projet": "   "})
    assert "Prénom : Marie" in msg
    assert "Tranche d'âge" not in msg
    assert "Situation actuelle" not in msg
    assert "Projet" not in msg


def test_the_choices_block_has_one_line_per_scene():
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    lines = [ln for ln in _block(msg, gen.HEADER_CHOISI).splitlines() if ln.strip()]
    scenes = [i for n in ("1", "2", "3", "4", "5") for i in bank.item_ids(n)]
    assert len(scenes) == 33
    assert len(lines) == 33


def test_each_choice_line_is_the_scene_title_then_the_persons_own_words():
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    scene = bank.item("S1-1")
    assert f"{scene['title']} : {scene['options'][0]['plain']}" in msg


def test_a_scene_title_may_carry_a_digit_because_the_cahier_does():
    """S2-7 is « Dans 20 ans ». The digit rule covers the person's words, not
    the cahier's own scene titles."""
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    choisi = _block(msg, gen.HEADER_CHOISI)
    assert "Dans 20 ans : " in choisi
    assert not re.search(r"\d", _own_words(choisi))


def test_session_zero_contributes_nothing_to_the_choices_block():
    """S0 reaches the model through the synthesis block only — its twenty
    statements are checkboxes, not scenes, and they carry no title to emit."""
    block = _block(
        gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS),
        gen.HEADER_CHOISI)
    lines = [ln for ln in block.splitlines() if ln.strip()]
    scene_ids = [i for n in ("1", "2", "3", "4", "5") for i in bank.item_ids(n)]
    titles = {bank.item(i)["title"] for i in scene_ids}
    assert lines, "the choices block must not be empty"
    for line in lines:
        assert line.split(" : ", 1)[0] in titles, line
    assert len(lines) == len(scene_ids)


def test_the_synthese_block_is_the_twelve_pinned_lines():
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    lines = [ln for ln in _block(msg, gen.HEADER_SYNTHESE).splitlines() if ln.strip()]
    assert lines == [
        "Univers dominants : Réaliste, Conventionnel, Entreprenant",
        "Ce qui l'attire le plus dans dix ans : le lien avec les gens, un impact "
        "visible, le terrain et l'action",
        "Autant coché des deux côtés sur : discrétion vs reconnaissance · solo vs "
        "collectif · impact local vs impact global · sécurité vs risque · méthode vs "
        "expression libre · impact différé vs impact immédiat · bureau vs terrain · "
        "expertise vs transmission (à pondérer ×1,5)",
        "Besoin dominant : autonomie",
        "Façon de fonctionner : s'appuie sur les autres pour décider",
        "Cadre : bureau fermé et calme · cycles courts · petite équipe soudée · "
        "confiance et droit à l'essai",
        "Ce qui l'épuise : les interruptions constantes",
        "Rapport au risque : Calculé",
        "Ce qui la met en colère : l'injustice",
        "La trace voulue : une trace dans les gens",
        "Prête à sacrifier : le temps",
        "Se sent vivant(e) quand : elle crée",
    ]


def test_a_whitespace_only_field_is_dropped_rather_than_left_naked():
    """« Rapport au risque :   » is worse than no line — the same rule the profile
    block has always followed.

    Every one of these is whitespace, never "": an empty string is falsy, so a
    bare `if s4.get(k)` drops it too and the missing strip would go unnoticed.
    The Cadre line matters as much as the two labels — a blank member there
    leaves « Cadre :   · cycles courts ».
    """
    synthesis = copy.deepcopy(SYNTHESIS)
    synthesis["s5"]["risque"] = "   "
    synthesis["s4"]["irritant"] = "\t "
    synthesis["s4"]["espace"] = " "
    block = _block(
        gen._portrait_user_message(synthesis, _full_responses(), PROFILE_FIELDS),
        gen.HEADER_SYNTHESE)
    assert "Rapport au risque" not in block
    assert "Ce qui l'épuise" not in block
    assert ("Cadre : cycles courts · petite équipe soudée · "
            "confiance et droit à l'essai") in block


def test_an_incomplete_voyage_only_emits_the_lines_it_can_fill():
    synthesis = copy.deepcopy(SYNTHESIS)
    for key in ("riasec", "s2", "s3", "s4", "s5"):
        synthesis[key] = None
    msg = gen._portrait_user_message(synthesis, _s0_only_responses(), PROFILE_FIELDS)
    block = _block(msg, gen.HEADER_SYNTHESE)
    assert "Univers dominants" not in block
    assert "Ce qui l'attire le plus dans dix ans" in block
    assert gen.HEADER_CHOISI not in msg      # no scene answered yet


def test_the_portrait_message_carries_no_score_and_no_framework_word():
    """The profile block is exempt from the digit rule: `25_34` is the age
    bracket the Profil de base already holds, and the contracts doc pins that
    literal shape. Everything derived from the scoring must be digit-free apart
    from the manual's own x1,5 weighting note."""
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    synth = _block(msg, gen.HEADER_SYNTHESE).replace(gen.WEIGHT_NOTE, "")
    assert not re.search(r"\d", synth)
    assert not re.search(r"\d", _own_words(_block(msg, gen.HEADER_CHOISI)))
    assert gen.leak_check({"message": msg}) == []
    for word in ("Élevé", "Moyen", "ouverture", "conscienciosite",
                 "A1", "A9", "A10", "consultatif", "bienveillance"):
        assert word not in msg


def test_a_real_synthesis_feeds_both_builders_without_a_gap(app):
    """The literal fixture above pins the wording; this one proves the shape
    scoring.synthesize() actually produces is the shape the builders read."""
    responses = _full_responses()
    synthesis = scoring.synthesize(responses)
    micro = gen._micro_user_message(synthesis, "Marie")
    portrait = gen._portrait_user_message(synthesis, responses, PROFILE_FIELDS)
    assert gen.HEADER_SESSION_0 in micro
    assert gen.HEADER_CHOISI in portrait
    assert gen.HEADER_SYNTHESE in portrait
    assert gen.leak_check({"a": micro, "b": portrait}) == []
    assert not re.search(r"\d", micro.replace(gen.HEADER_SESSION_0, ""))
    assert not re.search(r"\d", _own_words(_block(portrait, gen.HEADER_CHOISI)))
    assert not re.search(
        r"\d", _block(portrait, gen.HEADER_SYNTHESE).replace(gen.WEIGHT_NOTE, ""))


# ── mocked Anthropic client ──────────────────────────────────────────────────

def _stream_of(text, usage=(300, 900)):
    """One `client.messages.stream(...)` result: a context manager exposing
    `.text_stream` and `.get_final_message()`. Same shape as the stand-in in
    tests/test_stream_progress.py.

    `text` is one delta or a list of them. A real stream emits many, so a test
    that wants to pin the concatenation passes a list.
    """
    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.text_stream = iter([text] if isinstance(text, str) else list(text))
    stream.get_final_message.return_value = MagicMock(
        usage=MagicMock(input_tokens=usage[0], output_tokens=usage[1]))
    return stream


def _client(*answers, usage=(300, 900)):
    """An Anthropic stand-in. A str answer is streamed; an Exception is raised."""
    client = MagicMock()
    client.messages.stream.side_effect = [
        a if isinstance(a, BaseException) else _stream_of(a, usage) for a in answers
    ]
    return client


def _bad_request():
    return anthropic.BadRequestError(
        "output_config is not supported",
        response=httpx.Response(
            400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")),
        body=None,
    )


def _voyage(responses, prenom="Marie", **columns):
    """A user with a profile and one voyage carrying `responses`."""
    user = User(email=f"v{uuid4().hex[:8]}@test.com", password_hash="x",
                role="candidate", plan="free")
    db.session.add(user)
    db.session.commit()
    db.session.add(Profile(user_id=user.id, prenom=prenom,
                           tranche_age="25_34", situation="en_recherche",
                           projet="reprendre un travail au contact des gens"))
    row = Voyage(user_id=user.id, consent_at=datetime.utcnow(), age_attested=True,
                 **columns)
    row.responses = responses
    db.session.add(row)
    db.session.commit()
    return row


def _seed(slot, text="Consigne système.", active=True):
    """One PromptVersion on `slot`. `active=False` seeds a rolled-back version —
    the normal production state for a slot with history behind it."""
    row = PromptVersion(version_label=f"v0-{slot}", system_prompt_text=text,
                        is_active=active, path=slot)
    db.session.add(row)
    db.session.commit()
    return row


def _reload(voyage_id):
    """The row as it stands after the runner committed from its own context."""
    db.session.expire_all()
    return db.session.get(Voyage, voyage_id)


# ── _run_micro ───────────────────────────────────────────────────────────────

def test_the_micro_run_writes_the_phrase_and_flips_the_status(app):
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    _seed("voyage_micro", "Tu écris une phrase.")
    voyage_id = voyage.id

    client = _client("  « Tu cherches des endroits où ce que tu fabriques compte. »  ",
                     usage=(120, 40))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "success"
    assert row.micro_phrase == "Tu cherches des endroits où ce que tu fabriques compte."
    assert row.micro["tokens_in"] == 120
    assert row.micro["tokens_out"] == 40
    assert row.micro["error"] is None
    assert row.tokens_in == 120
    assert row.tokens_out == 40


def test_the_micro_run_records_the_prompt_version_it_used(app):
    """B2G traceability: every generated text names the prompt that wrote it."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine")
    _seed("voyage_micro")
    voyage_id = voyage.id
    expected = PromptVersion.query.filter_by(path="voyage_micro").first().id

    with patch.object(gen, "_get_client", return_value=_client("Une phrase.")):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    # R9 seeds prompt_version_id before the stream, so without this line the
    # assertion below is also satisfied by a run that failed — and this test
    # names the success path.
    assert row.micro_status == "success"
    assert row.micro["prompt_version_id"] == expected


def test_the_micro_run_uses_the_free_tier_model_and_a_two_hundred_token_budget(app):
    voyage = _voyage(_s0_only_responses(), status="s0_termine")
    _seed("voyage_micro", "Consigne micro.")
    voyage_id = voyage.id

    client = _client("Une phrase.")
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    kwargs = client.messages.stream.call_args.kwargs
    assert kwargs["model"] == tiers.model_for(tiers.FREE)[0]
    assert kwargs["max_tokens"] == gen.MICRO_MAX_TOKENS
    assert kwargs["system"] == "Consigne micro."
    # Plain text, no schema: the phrase is one sentence, not an object.
    assert "extra_body" not in kwargs
    assert kwargs["messages"] == [
        {"role": "user", "content": gen._micro_user_message(
            scoring.synthesize(_s0_only_responses()), "Marie")}]


def test_a_missing_slot_prompt_puts_the_micro_in_error(app):
    """Without a seeded prompt the feature errors on first use — which is the
    whole reason both seed scripts land ACTIVE."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    voyage_id = voyage.id

    gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert row.micro["error"] == "Aucun prompt actif pour le slot voyage_micro."
    assert row.micro_phrase is None


def test_an_api_failure_is_recorded_on_the_row_not_raised(app):
    voyage = _voyage(_s0_only_responses(), status="s0_termine")
    _seed("voyage_micro")
    voyage_id = voyage.id

    client = MagicMock()
    client.messages.stream.side_effect = RuntimeError("connection reset by peer")
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert "connection reset by peer" in row.micro["error"]


def test_a_failed_run_still_records_which_prompt_it_used(app):
    """B2G traceability: an error row that cannot name its prompt is not traceable."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine")
    _seed("voyage_micro")
    voyage_id = voyage.id
    expected = PromptVersion.query.filter_by(path="voyage_micro").first().id

    client = MagicMock()
    client.messages.stream.side_effect = RuntimeError("upstream is down")
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert row.micro["prompt_version_id"] == expected


def test_a_build_that_raises_fails_the_row_instead_of_stranding_it(app):
    """The route commits micro_status = "generating" before spawning us. If the
    message build raises, this thread is the only thing that will ever move that
    status — so it has to move it."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    _seed("voyage_micro")
    voyage_id = voyage.id

    with patch.object(gen, "_micro_user_message", side_effect=ValueError("bank drift")):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert "bank drift" in row.micro["error"]


def test_the_db_connection_is_released_before_the_stream(app):
    """Holding a pooled connection across the call is what leaves rows stuck
    'generating' — see the comment in anthropic_service._run_analysis."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine")
    _seed("voyage_micro")
    voyage_id = voyage.id

    seen = {}

    def streaming(**_kwargs):
        # db.session.remove() empties the scoped registry; it stays empty until
        # something asks for a session again. That is the observable fact.
        seen["registry_empty"] = not db.session.registry.has()
        return _stream_of("Une phrase.")

    client = MagicMock()
    client.messages.stream.side_effect = streaming
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    assert seen["registry_empty"] is True
    assert _reload(voyage_id).micro_status == "success"


def test_a_deleted_voyage_is_a_silent_no_op(app):
    gen._run_micro("does-not-exist", app)   # must not raise


def test_start_micro_spawns_a_daemon_thread_and_returns(app):
    with patch.object(gen.threading, "Thread") as Thread:
        gen.start_micro("some-id", app)
    Thread.assert_called_once_with(target=gen._run_micro, args=("some-id", app),
                                   daemon=True)
    Thread.return_value.start.assert_called_once()


# ── _stream_text, directly ───────────────────────────────────────────────────

def test_a_schema_call_carries_the_output_config_and_is_sent_once():
    """The portrait's structure is enforced here, not in prompt prose. Nothing
    in the micro path builds an extra_body, so this is the only place the shape
    is pinned before Task 8 depends on it."""
    schema = gen._portrait_schema()
    client = _client("{}")
    with patch.object(gen, "_get_client", return_value=client):
        gen._stream_text("m", "sys", [{"role": "user", "content": "u"}], 3000, schema)

    assert client.messages.stream.call_count == 1
    assert client.messages.stream.call_args.kwargs["extra_body"] == {
        "output_config": {"format": {"type": "json_schema", "schema": schema}}
    }


def test_a_refused_schema_is_retried_once_without_it():
    """The degrade path: the API refuses output_config, the same call goes out
    again as plain text. The retry must drop extra_body — retrying with it would
    fail identically."""
    client = _client(_bad_request(), "Une phrase.")
    with patch.object(gen, "_get_client", return_value=client):
        text, _, _ = gen._stream_text(
            "m", "sys", [{"role": "user", "content": "u"}], 3000,
            gen._portrait_schema())

    assert text == "Une phrase."
    assert client.messages.stream.call_count == 2
    first, second = client.messages.stream.call_args_list
    assert "extra_body" in first.kwargs
    assert "extra_body" not in second.kwargs


def test_a_schema_less_bad_request_is_raised_rather_than_retried():
    """Every micro call passes schema=None, so there is no extra_body to drop:
    a retry would re-send a byte-identical request that just failed, billing and
    waiting twice for the same 400."""
    client = _client(_bad_request(), "jamais atteint")
    with patch.object(gen, "_get_client", return_value=client):
        with pytest.raises(anthropic.BadRequestError):
            gen._stream_text("m", "sys", [{"role": "user", "content": "u"}], 200, None)

    assert client.messages.stream.call_count == 1


def test_a_bad_request_on_the_micro_path_costs_one_call_and_errors_the_row(app):
    """The same rule seen from the runner: one upstream call, row in error."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    _seed("voyage_micro")
    voyage_id = voyage.id

    client = _client(_bad_request(), "jamais atteint")
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    assert client.messages.stream.call_count == 1
    assert _reload(voyage_id).micro_status == "error"


# ── _one_sentence ────────────────────────────────────────────────────────────

def test_a_dash_then_quoted_answer_is_fully_unwrapped():
    """« - « Phrase. » » is an ordinary shape for a model asked for one quoted
    sentence. A single quotes-then-dash pass leaves the opening guillemet on the
    phrase the candidate reads."""
    assert gen._one_sentence("- « Tu cherches des endroits. »") == \
        "Tu cherches des endroits."
    assert gen._one_sentence('— "Phrase."') == "Phrase."
    assert gen._one_sentence("- Phrase.") == "Phrase."
    assert gen._one_sentence("  «  Phrase.  »  ") == "Phrase."


def test_a_long_answer_comes_back_whole():
    """« It never truncates » at a length where a cap would actually bite: a
    15-25 word French sentence runs 120-200 characters, so the one 56-character
    fixture below cannot tell an uncapped result from a capped one."""
    raw = " ".join(f"mot{i}" for i in range(60))
    out = gen._one_sentence(raw)
    assert out == raw
    assert len(out) > 300


def test_nothing_at_all_normalises_to_the_empty_string():
    """The falsy guard in str(raw or ""): the runner turns this into an error
    row rather than an empty success."""
    assert gen._one_sentence(None) == ""
    assert gen._one_sentence("") == ""
    assert gen._one_sentence("   ") == ""
    assert gen._one_sentence(" « » ") == ""


# ── _run_micro, continued ────────────────────────────────────────────────────

def test_an_empty_phrase_is_an_error_not_a_success(app):
    """micro_phrase reads an empty phrase back as None, and Voyage.for_prompt
    selects on micro_status == "success" — so a successful row with no phrase
    would be handed to an analysis as the S0-phrase carrier."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    _seed("voyage_micro")
    voyage_id = voyage.id

    with patch.object(gen, "_get_client", return_value=_client("  « »  ")):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert row.micro_phrase is None
    assert row.micro["error"] == "Le modèle n'a renvoyé aucune phrase lisible."
    assert Voyage.for_prompt(row.user_id) is None


def test_the_run_uses_the_active_prompt_not_a_rolled_back_one(app):
    """Version history with rollback is a hard requirement, so inactive rows on
    a slot are the normal production state. The inactive row is seeded first, so
    dropping the is_active filter would pick it."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine")
    _seed("voyage_micro", "Consigne annulée.", active=False)
    active = _seed("voyage_micro", "Consigne en vigueur.")
    voyage_id, active_id = voyage.id, active.id

    client = _client("Une phrase.")
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    assert client.messages.stream.call_args.kwargs["system"] == "Consigne en vigueur."
    assert _reload(voyage_id).micro["prompt_version_id"] == active_id


def test_the_token_counters_accumulate_rather_than_overwrite(app):
    """Task 8's portrait run writes these same two columns, so `=` in place of
    `+=` would silently erase the micro's tokens from the cost dashboard and the
    B2G token trail."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine",
                     tokens_in=5, tokens_out=7)
    _seed("voyage_micro")
    voyage_id = voyage.id

    with patch.object(gen, "_get_client",
                      return_value=_client("Une phrase.", usage=(120, 40))):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.tokens_in == 125
    assert row.tokens_out == 47


def test_the_prenom_comes_from_this_voyages_own_profile(app):
    """The decoy profile is created first, so reading Profile.query.first()
    instead of filtering on user_id would put a stranger's prénom in the message
    the model writes the candidate's phrase from."""
    _voyage(_s0_only_responses(), prenom="Autre")
    voyage = _voyage(_s0_only_responses(), prenom="Marie", status="s0_termine")
    _seed("voyage_micro")
    voyage_id = voyage.id

    client = _client("Une phrase.")
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    sent = client.messages.stream.call_args.kwargs["messages"][0]["content"]
    assert "Prénom : Marie" in sent
    assert "Autre" not in sent


def test_every_streamed_chunk_reaches_the_phrase(app):
    """A real stream emits many deltas; keeping only the last one would hand the
    candidate the tail of a sentence."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine")
    _seed("voyage_micro")
    voyage_id = voyage.id

    chunks = ["Tu cherches ", "des endroits ", "où ce que tu fabriques compte."]
    with patch.object(gen, "_get_client", return_value=_client(chunks)):
        gen._run_micro(voyage_id, app)

    assert _reload(voyage_id).micro_phrase == "".join(chunks)


def test_a_huge_error_message_is_capped_before_it_is_stored(app):
    """ERROR_MAX_CHARS: an upstream traceback in the payload must not turn one
    failed row into an unbounded encrypted blob."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine")
    _seed("voyage_micro")
    voyage_id = voyage.id

    client = MagicMock()
    client.messages.stream.side_effect = RuntimeError("x" * 5000)
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert len(row.micro["error"]) == gen.ERROR_MAX_CHARS


def test_the_success_write_back_does_not_inherit_the_streams_session(app):
    """The stream holds no connection, so anything left in the registry when it
    returns may be stale. Here the stream dirties a session; the write-back must
    discard it rather than flush its pending change alongside the phrase."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", tokens_in=5)
    _seed("voyage_micro")
    voyage_id = voyage.id

    def streaming(**_kwargs):
        db.session.get(Voyage, voyage_id).tokens_in = 999
        return _stream_of("Une phrase.", usage=(120, 40))

    client = MagicMock()
    client.messages.stream.side_effect = streaming
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "success"
    assert row.tokens_in == 125       # 5 + 120, not 999 + 120


def test_the_error_write_back_does_not_inherit_the_streams_session(app):
    """Same rule on the path that matters most: the failure has to be recorded
    from a fresh, pre-pinged session, not from whatever the stream left."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", tokens_in=5)
    _seed("voyage_micro")
    voyage_id = voyage.id

    def streaming(**_kwargs):
        db.session.get(Voyage, voyage_id).tokens_in = 999
        raise RuntimeError("connection reset by peer")

    client = MagicMock()
    client.messages.stream.side_effect = streaming
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert row.tokens_in == 5


# ── _run_micro: the phrase's leak check ──────────────────────────────────────
# The portrait's scan, with the one difference that decides everything below:
# no counselor reads the phrase before the person does. A phrase that still
# leaks after one corrective turn is refused, never kept.

CLEAN_PHRASE = "Tu cherches des endroits où ce que tu fabriques sert à quelqu'un."
LEAKY_PHRASE = "Ton score de névrotisme est bas et tu cherches des endroits calmes."
# ASCII on purpose: a second leaking sentence whose absence from the payload
# cannot be hidden by json.dumps escaping its accents.
OTHER_LEAKY_PHRASE = "Ton profil RIASEC montre que tu aimes le terrain et les gens."


def _client_with_usages(*answers):
    """Like _client(), but every answer carries its own usage, so a sum can be
    told apart from any single call's figure. An answer is (text, (in, out)),
    or an Exception to raise."""
    client = MagicMock()
    client.messages.stream.side_effect = [
        a if isinstance(a, BaseException) else _stream_of(a[0], a[1]) for a in answers
    ]
    return client


def _payload_text(row) -> str:
    """The decrypted micro payload as one string. ensure_ascii=False, because
    the default escapes « é » as \\u00e9 and would make every « not in » below
    vacuous for an accented sentence."""
    return json.dumps(row.micro, ensure_ascii=False)


def test_the_phrase_fixtures_are_what_their_names_say():
    assert gen.leak_check({"p": CLEAN_PHRASE}) == []
    assert gen.leak_check({"p": LEAKY_PHRASE}) == ["névrotisme", "score"]
    assert gen.leak_check({"p": OTHER_LEAKY_PHRASE}) == ["riasec"]
    assert OTHER_LEAKY_PHRASE.isascii()


def test_the_phrase_corrective_turn_is_pinned_word_for_word():
    """Compared whole, not by containment: every clause is a rule — the words
    quoted, no other technical term, one sentence of the manual's length,
    nothing else — and dropping any one of them left a containment check
    green. This text lives in code, not in a prompt the PM edits."""
    assert gen._micro_leak_retry_message(["riasec", "trait"]) == (
        "Cette phrase contient des mots interdits : riasec, trait. "
        "Réécris-la sans ces mots et sans aucun autre terme technique de "
        "psychologie ou de ressources humaines. Une seule phrase, de 15 à 25 mots. "
        "Réponds uniquement avec la phrase."
    )


def test_the_corrective_call_is_the_same_call_as_the_first(app):
    """Same free model, same active system prompt, same 200-token budget, no
    schema: the correction must not silently move to the paid model or lose
    the PM's prompt."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    _seed("voyage_micro", "Consigne micro.")
    voyage_id = voyage.id

    client = _client(LEAKY_PHRASE, CLEAN_PHRASE)
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    assert client.messages.stream.call_count == 2
    for call in client.messages.stream.call_args_list:
        assert call.kwargs["model"] == tiers.model_for(tiers.FREE)[0]
        assert call.kwargs["system"] == "Consigne micro."
        assert call.kwargs["max_tokens"] == gen.MICRO_MAX_TOKENS
        assert "extra_body" not in call.kwargs
    assert tiers.model_for(tiers.FREE)[0] != tiers.model_for(tiers.PAID)[0]
    assert _reload(voyage_id).micro_phrase == CLEAN_PHRASE


def test_a_clean_phrase_costs_one_call_and_is_kept(app):
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    _seed("voyage_micro")
    voyage_id = voyage.id

    client = _client(CLEAN_PHRASE)
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    assert client.messages.stream.call_count == 1
    row = _reload(voyage_id)
    assert row.micro_status == "success"
    assert row.micro_phrase == CLEAN_PHRASE


def test_a_leaking_phrase_is_rewritten_once_with_the_words_quoted(app):
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating",
                     tokens_in=5, tokens_out=7)
    _seed("voyage_micro")
    voyage_id = voyage.id

    client = _client_with_usages((f"« {LEAKY_PHRASE} »", (100, 30)),
                                 (CLEAN_PHRASE, (110, 35)))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    assert client.messages.stream.call_count == 2
    first, second = (c.kwargs["messages"] for c in client.messages.stream.call_args_list)
    # The original user turn, then the normalised phrase as the model's own
    # turn, then the correction quoting the words it must drop.
    assert len(first) == 1
    assert len(second) == 3
    assert second[0] == first[0]
    assert second[1] == {"role": "assistant", "content": LEAKY_PHRASE}
    assert second[2]["role"] == "user"
    assert second[2]["content"] == gen._micro_leak_retry_message(["névrotisme", "score"])
    assert "névrotisme, score" in second[2]["content"]

    row = _reload(voyage_id)
    assert row.micro_status == "success"
    assert row.micro_phrase == CLEAN_PHRASE
    assert LEAKY_PHRASE not in _payload_text(row)
    # Both calls are billed: the payload carries their sum, the row adds it.
    assert (row.micro["tokens_in"], row.micro["tokens_out"]) == (210, 65)
    assert (row.tokens_in, row.tokens_out) == (215, 72)


def test_a_phrase_that_still_leaks_is_refused_and_never_stored(app):
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating",
                     tokens_in=5, tokens_out=7)
    _seed("voyage_micro")
    voyage_id, user_id = voyage.id, voyage.user_id

    client = _client_with_usages((LEAKY_PHRASE, (100, 30)),
                                 (OTHER_LEAKY_PHRASE, (110, 35)))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    assert client.messages.stream.call_count == 2      # one retry, never two
    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert row.micro_phrase is None
    assert row.to_dict()["micro_phrase"] is None
    assert Voyage.for_prompt(user_id) is None
    assert row.micro["error"] == "Vocabulaire interdit dans la phrase : riasec."
    assert LEAKY_PHRASE not in _payload_text(row)
    assert OTHER_LEAKY_PHRASE not in _payload_text(row)
    assert OTHER_LEAKY_PHRASE not in json.dumps(row.micro)
    # Refused, but both calls were paid for.
    assert (row.tokens_in, row.tokens_out) == (215, 72)


def test_a_corrective_call_that_raises_keeps_nothing(app):
    """Unlike the portrait, there is no draft worth keeping: nobody stands
    between this phrase and the person, so the leaking one is dropped too."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating",
                     tokens_in=5, tokens_out=7)
    _seed("voyage_micro")
    voyage_id = voyage.id

    client = _client_with_usages((LEAKY_PHRASE, (100, 30)), RuntimeError("upstream timeout"))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    assert client.messages.stream.call_count == 2
    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert row.micro["error"] == "upstream timeout"
    assert row.micro_phrase is None
    assert row.to_dict()["micro_phrase"] is None
    assert LEAKY_PHRASE not in _payload_text(row)
    # The call that answered is billed; the one that raised cost nothing.
    assert (row.tokens_in, row.tokens_out) == (105, 37)


def test_a_corrective_call_that_raises_with_no_message_is_still_an_error(app):
    """TimeoutError() stringifies to "". A failure recorded as "" is falsy, so
    a write-back that branched on the message would commit "success" with an
    empty phrase: for_prompt would hand the row to an analysis, and the retry
    route refuses a success, so the person could never get out."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    _seed("voyage_micro")
    voyage_id, user_id = voyage.id, voyage.user_id

    client = _client_with_usages((LEAKY_PHRASE, (100, 30)), TimeoutError())
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert row.micro_phrase is None
    assert Voyage.for_prompt(user_id) is None
    assert row.micro["error"] == "TimeoutError"
    assert LEAKY_PHRASE not in _payload_text(row)


def test_the_write_back_never_commits_an_empty_phrase_whatever_the_reason(app):
    """The second half of the defence above, proven on its own: the write-back
    branches on the phrase, so an empty phrase arriving with an empty reason
    still ends in "error" with the stock message, never in "success"."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    _seed("voyage_micro")
    voyage_id, user_id = voyage.id, voyage.user_id

    with patch.object(gen, "_generate_phrase", return_value=("", "", 100, 30)):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert row.micro_phrase is None
    assert Voyage.for_prompt(user_id) is None
    assert row.micro["error"] == "Le modèle n'a renvoyé aucune phrase lisible."


def test_a_rewrite_that_comes_back_empty_is_an_error_and_keeps_nothing(app):
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    _seed("voyage_micro")
    voyage_id = voyage.id

    client = _client_with_usages((LEAKY_PHRASE, (100, 30)), ("  « »  ", (110, 35)))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert row.micro["error"] == "Le modèle n'a renvoyé aucune phrase lisible."
    assert row.micro_phrase is None
    assert LEAKY_PHRASE not in _payload_text(row)
    assert (row.tokens_in, row.tokens_out) == (210, 65)


def test_an_inflected_leak_is_enough_to_trigger_the_rewrite(app):
    """« tes traits » only matches through phase 2's widened matcher (the
    optional trailing s). A narrower check written for the phrase would let
    this sentence through on the first call."""
    inflected = "Tes traits de caractère te poussent vers les endroits où l'on fabrique."
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    _seed("voyage_micro")
    voyage_id = voyage.id

    client = _client(inflected, CLEAN_PHRASE)
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    assert client.messages.stream.call_count == 2
    retry = client.messages.stream.call_args_list[1].kwargs["messages"]
    assert retry[-1]["content"] == gen._micro_leak_retry_message(["trait"])
    assert _reload(voyage_id).micro_phrase == CLEAN_PHRASE


def _succeeded(**columns):
    """A voyage whose phrase run already succeeded — run A of a twin pair."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="success",
                     **columns)
    voyage.micro = {"phrase": CLEAN_PHRASE, "prompt_version_id": "pv-a",
                    "tokens_in": 120, "tokens_out": 40, "error": None}
    db.session.commit()
    return voyage.id


def test_a_failure_drops_any_phrase_already_in_the_payload(app):
    """The invariant: micro_phrase is readable only on a success row. /espace
    renders micro_phrase whenever it is set, so a phrase left beside "error"
    would be shown next to a failure."""
    voyage_id = _succeeded()

    gen._fail_micro(db.session.get(Voyage, voyage_id),
                    "Vocabulaire interdit dans la phrase : riasec.")

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert row.micro_phrase is None
    assert row.to_dict()["micro_phrase"] is None
    assert "phrase" not in row.micro
    assert row.micro == {"prompt_version_id": "pv-a", "tokens_in": 120, "tokens_out": 40,
                         "error": "Vocabulaire interdit dans la phrase : riasec."}


def test_a_twin_run_that_fails_after_a_success_leaves_no_phrase_beside_the_error(app):
    """The race behind the rule: run A wrote its phrase, then twin B —
    relaunched while A looked stalled — leaks twice and fails on the same row.
    Last write wins, and what it wins with must be coherent."""
    voyage_id = _succeeded()
    _seed("voyage_micro")

    with patch.object(gen, "_get_client",
                      return_value=_client(LEAKY_PHRASE, OTHER_LEAKY_PHRASE)):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert row.micro_phrase is None
    assert row.to_dict()["micro_phrase"] is None
    assert CLEAN_PHRASE not in _payload_text(row)


def test_no_connection_is_held_across_either_call(app):
    """Both calls run between the pre-stream remove() and the write-back."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    _seed("voyage_micro")
    voyage_id = voyage.id

    seen = []
    answers = iter([LEAKY_PHRASE, CLEAN_PHRASE])

    def streaming(**_kwargs):
        seen.append(not db.session.registry.has())
        return _stream_of(next(answers))

    client = MagicMock()
    client.messages.stream.side_effect = streaming
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    assert seen == [True, True]
    assert _reload(voyage_id).micro_phrase == CLEAN_PHRASE


def test_an_empty_phrase_is_still_billed(app):
    """Every call that returned was paid for, whatever it produced."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating",
                     tokens_in=5, tokens_out=7)
    _seed("voyage_micro")
    voyage_id = voyage.id

    with patch.object(gen, "_get_client", return_value=_client("  « »  ", usage=(120, 40))):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert (row.tokens_in, row.tokens_out) == (125, 47)


# ── _parse_sections ──────────────────────────────────────────────────────────

def _portrait_json(sections):
    return json.dumps(sections, ensure_ascii=False)


def test_a_well_formed_answer_parses_into_the_six_sections():
    assert gen._parse_sections(_portrait_json(CLEAN_SECTIONS)) == CLEAN_SECTIONS


def test_a_portrait_truncated_at_the_token_cap_keeps_what_arrived():
    """The realistic failure: six prose sections against PORTRAIT_MAX_TOKENS =
    3000, the answer cut off mid-sentence with no closing quote or brace.

    json.loads cannot read that at all, so without the repair rung the whole
    draft becomes "" × 6 and the empty-result guard turns a nearly finished
    portrait into an error row. The five complete sections have to survive, and
    the partial sixth is left for the counselor to finish.
    """
    whole = _portrait_json(CLEAN_SECTIONS)
    cut = whole.index(CLEAN_SECTIONS["pas_encore"]) + 17
    sections = gen._parse_sections(whole[:cut])

    assert set(sections) == set(gen.PORTRAIT_KEYS)
    for key in ("accroche", "qui_tu_es", "vibrer", "besoins", "chemins"):
        assert sections[key] == CLEAN_SECTIONS[key], key
    assert sections["pas_encore"] == CLEAN_SECTIONS["pas_encore"][:17]


def test_single_quoted_json_is_repaired_rather_than_lost():
    """A degraded (schema-less) call can come back as a Python-style dict. Rung
    one rejects it outright — only the repair rung reads it."""
    sections = gen._parse_sections(str(CLEAN_SECTIONS))
    assert sections == CLEAN_SECTIONS


def test_a_trailing_comma_is_repaired_rather_than_lost():
    sections = gen._parse_sections(_portrait_json(CLEAN_SECTIONS)[:-1] + ",}")
    assert sections == CLEAN_SECTIONS


def test_an_answer_that_is_not_json_at_all_yields_six_empty_sections():
    """Neither rung can read prose, and that is what the runner's empty-result
    guard is for. The six keys still come back, so nothing downstream has to
    guard for a missing one."""
    sections = gen._parse_sections("Je ne peux pas répondre à cette demande.")
    assert set(sections) == set(gen.PORTRAIT_KEYS)
    assert not any(sections.values())


# ── _run_portrait ────────────────────────────────────────────────────────────


def test_the_portrait_run_stores_six_sections_a_snapshot_and_a_draft_status(app):
    voyage = _voyage(_full_responses(), status="termine", portrait_status="generating")
    _seed("voyage_portrait", "Tu écris six sections.")
    voyage_id = voyage.id

    with patch.object(gen, "_get_client",
                      return_value=_client(_portrait_json(CLEAN_SECTIONS))):
        gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "draft"
    assert row.portrait_sections == CLEAN_SECTIONS
    assert row.portrait["flags"] == []
    assert row.portrait["edited"] is False
    assert row.portrait["error"] is None
    assert row.portrait["snapshot"]["scoring_version"] == bank.SCORING_VERSION
    assert row.portrait["tokens_in"] == 300
    assert row.portrait["tokens_out"] == 900
    assert row.tokens_in == 300


def test_the_portrait_call_carries_the_schema_the_paid_model_and_the_budget(app):
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    client = _client(_portrait_json(CLEAN_SECTIONS))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    kwargs = client.messages.stream.call_args.kwargs
    assert kwargs["model"] == tiers.model_for(tiers.PAID)[0]
    assert kwargs["max_tokens"] == gen.PORTRAIT_MAX_TOKENS
    fmt = kwargs["extra_body"]["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert list(fmt["schema"]["properties"]) == list(gen.PORTRAIT_KEYS)


def test_a_refused_output_config_degrades_to_a_plain_call(app):
    """Same fallback as _run_analysis: an old API surface must not cost the
    portrait, only its schema."""
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    client = _client(_bad_request(), "```json\n" + _portrait_json(CLEAN_SECTIONS) + "\n```")
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    first, second = client.messages.stream.call_args_list
    assert "extra_body" in first.kwargs
    assert "extra_body" not in second.kwargs
    row = _reload(voyage_id)
    assert row.portrait_status == "draft"
    assert row.portrait_sections == CLEAN_SECTIONS


def test_a_leaking_draft_is_regenerated_once_with_the_words_quoted(app):
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    client = _client(_portrait_json(LEAKY_SECTIONS), _portrait_json(CLEAN_SECTIONS))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    assert client.messages.stream.call_count == 2
    retry = client.messages.stream.call_args_list[1].kwargs["messages"]
    assert [m["role"] for m in retry] == ["user", "assistant", "user"]
    for word in ("névrotisme", "riasec", "score"):
        assert word in retry[-1]["content"]

    row = _reload(voyage_id)
    assert row.portrait_status == "draft"
    assert row.portrait["flags"] == []
    assert row.portrait_sections["qui_tu_es"] == CLEAN_SECTIONS["qui_tu_es"]
    # Both calls are billed to the row.
    assert row.portrait["tokens_in"] == 600
    assert row.portrait["tokens_out"] == 1800


def test_a_draft_that_still_leaks_is_kept_and_flagged(app):
    """Flag-and-keep, not fail: a counselor validates before the person reads
    it, and a flagged draft is more useful than none."""
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    client = _client(_portrait_json(LEAKY_SECTIONS), _portrait_json(LEAKY_SECTIONS))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    assert client.messages.stream.call_count == 2      # one retry, never two
    row = _reload(voyage_id)
    assert row.portrait_status == "draft"
    assert row.portrait["flags"] == [gen.FLAG_VOCABULAIRE]
    assert row.portrait_sections["qui_tu_es"] == LEAKY_SECTIONS["qui_tu_es"]


def test_a_missing_slot_prompt_puts_the_portrait_in_error(app):
    voyage = _voyage(_full_responses(), status="termine", portrait_status="generating")
    voyage_id = voyage.id

    gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "error"
    assert row.portrait["error"] == "Aucun prompt actif pour le slot voyage_portrait."
    assert row.portrait_sections == {}


def test_an_unreadable_answer_puts_the_portrait_in_error(app):
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    with patch.object(gen, "_get_client",
                      return_value=_client("Je ne peux pas répondre à cette demande.")):
        gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "error"
    assert row.portrait["error"]


def test_an_api_failure_puts_the_portrait_in_error(app):
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    client = MagicMock()
    client.messages.stream.side_effect = RuntimeError("upstream timeout")
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "error"
    assert "upstream timeout" in row.portrait["error"]


def test_a_retry_that_never_answers_keeps_the_first_draft_and_flags_it(app):
    """A timeout on the corrective turn must not cost the portrait.

    The retry is an improvement, not a precondition: the module's rule is that a
    still-leaking draft is kept and flagged, because a flagged draft is more
    useful than none. A draft that leaked once and then lost its retry to a 500
    is in exactly that position — letting the exception reach the outer handler
    would send it to "error" instead, throwing away six usable sections over a
    transient upstream failure.
    """
    voyage = _voyage(_full_responses(), status="termine", portrait_status="generating")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    client = _client(_portrait_json(LEAKY_SECTIONS), RuntimeError("upstream timeout"))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    assert client.messages.stream.call_count == 2
    row = _reload(voyage_id)
    assert row.portrait_status == "draft"
    assert row.portrait["flags"] == [gen.FLAG_VOCABULAIRE]
    assert row.portrait["error"] is None
    assert row.portrait_sections["qui_tu_es"] == LEAKY_SECTIONS["qui_tu_es"]
    # Only the first call ever returned, so only the first call is billed.
    assert row.portrait["tokens_in"] == 300
    assert row.portrait["tokens_out"] == 900


def test_a_first_call_that_never_answers_is_still_an_error(app):
    """The other half of the rule, and the reason the outer handler stays: when
    the FIRST call fails there is no draft to keep, so "error" is the only
    honest status. A blanket "keep what we have" would commit six empty
    sections as a draft."""
    voyage = _voyage(_full_responses(), status="termine", portrait_status="generating")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    client = _client(RuntimeError("upstream timeout"), _portrait_json(CLEAN_SECTIONS))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    assert client.messages.stream.call_count == 1
    row = _reload(voyage_id)
    assert row.portrait_status == "error"
    assert "upstream timeout" in row.portrait["error"]
    assert row.portrait_sections == {}


def test_the_snapshot_is_the_synthesis_the_portrait_was_written_from(app):
    """Provenance, not a copy of whatever the row says later.

    The snapshot exists so that a corrected scoring table can never make an
    existing portrait a lie: it has to be the synthesis that went INTO the
    prompt, captured before the stream, not a fresh synthesis() read at
    write-back. Here the answers change while the model is streaming, so the
    two values genuinely differ — re-reading at write-back stores a sheet this
    portrait was never written from.
    """
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id
    before = scoring.synthesize(_full_responses())

    def streaming(**_kwargs):
        # The person retakes a session mid-generation (or a scoring fix lands).
        row = db.session.get(Voyage, voyage_id)
        row.responses = _s0_only_responses()
        db.session.commit()
        return _stream_of(_portrait_json(CLEAN_SECTIONS))

    client = MagicMock()
    client.messages.stream.side_effect = streaming
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    after = row.synthesis()
    assert after != before, "the fixture must actually change the synthesis"
    assert row.portrait["snapshot"] == before
    assert row.portrait["snapshot"] != after


def test_a_missing_key_comes_back_as_an_empty_section_not_a_crash(app):
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id
    partial = {k: v for k, v in CLEAN_SECTIONS.items() if k != "pas_encore"}

    with patch.object(gen, "_get_client", return_value=_client(_portrait_json(partial))):
        gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "draft"
    assert set(row.portrait["sections"]) == set(gen.PORTRAIT_KEYS)
    assert row.portrait["sections"]["pas_encore"] == ""


def test_a_portrait_build_that_raises_fails_the_row_instead_of_stranding_it(app):
    """The route commits portrait_status = "generating" before spawning us. If
    the message build raises, this thread is the only thing that will ever move
    that status — so it has to move it."""
    voyage = _voyage(_full_responses(), status="termine", portrait_status="generating")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    with patch.object(gen, "_portrait_user_message", side_effect=ValueError("bank drift")):
        gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "error"
    assert "bank drift" in row.portrait["error"]


def test_a_failed_portrait_run_still_records_which_prompt_it_used(app):
    """B2G traceability: an error row that cannot name its prompt is not traceable."""
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id
    expected = PromptVersion.query.filter_by(path="voyage_portrait").first().id

    client = MagicMock()
    client.messages.stream.side_effect = RuntimeError("upstream is down")
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "error"
    assert row.portrait["prompt_version_id"] == expected


def test_the_portrait_success_write_back_does_not_inherit_the_streams_session(app):
    """The stream holds no connection, so anything left in the registry when it
    returns may be stale. Here the stream dirties a session; the write-back must
    discard it rather than flush its pending change alongside the sections."""
    voyage = _voyage(_full_responses(), status="termine", tokens_in=5)
    _seed("voyage_portrait")
    voyage_id = voyage.id

    def streaming(**_kwargs):
        db.session.get(Voyage, voyage_id).tokens_in = 999
        return _stream_of(_portrait_json(CLEAN_SECTIONS))

    client = MagicMock()
    client.messages.stream.side_effect = streaming
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "draft"
    assert row.tokens_in == 305       # 5 + 300, not 999 + 300


def test_the_portrait_error_write_back_does_not_inherit_the_streams_session(app):
    """Same rule on the path that matters most: the failure has to be recorded
    from a fresh, pre-pinged session, not from whatever the stream left."""
    voyage = _voyage(_full_responses(), status="termine", tokens_in=5)
    _seed("voyage_portrait")
    voyage_id = voyage.id

    def streaming(**_kwargs):
        db.session.get(Voyage, voyage_id).tokens_in = 999
        raise RuntimeError("connection reset by peer")

    client = MagicMock()
    client.messages.stream.side_effect = streaming
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "error"
    assert row.tokens_in == 5


def test_the_generated_texts_are_ciphertext_at_rest(app):
    """A psychometric portrait is more sensitive than bloc 5. The plaintext
    columns hold statuses and timestamps, nothing else."""
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_micro")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    with patch.object(gen, "_get_client", return_value=_client("Une phrase à toi.")):
        gen._run_micro(voyage_id, app)
    with patch.object(gen, "_get_client",
                      return_value=_client(_portrait_json(CLEAN_SECTIONS))):
        gen._run_portrait(voyage_id, app)

    db.session.expire_all()
    raw = db.session.execute(
        db.text("SELECT micro_encrypted, portrait_encrypted FROM voyages WHERE id = :i"),
        {"i": voyage_id}).first()
    blob = f"{raw[0]}{raw[1]}"
    assert "Une phrase à toi." not in blob
    assert CLEAN_SECTIONS["accroche"] not in blob
    assert "accroche" not in blob


def test_start_portrait_spawns_a_daemon_thread_and_returns(app):
    with patch.object(gen.threading, "Thread") as Thread:
        gen.start_portrait("some-id", app)
    Thread.assert_called_once_with(target=gen._run_portrait, args=("some-id", app),
                                   daemon=True)
    Thread.return_value.start.assert_called_once()
