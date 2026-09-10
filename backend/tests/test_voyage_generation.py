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


# ── leak_check ───────────────────────────────────────────────────────────────

def test_a_clean_portrait_leaks_nothing():
    assert gen.leak_check(CLEAN_SECTIONS) == []


def test_the_word_portrait_does_not_trip_the_trait_pattern():
    """Word boundaries are the whole reason « trait » is safe to ban."""
    assert gen.leak_check({
        "accroche": "Ce portrait te ressemble.",
        "qui_tu_es": "Tu traites les choses une par une.",
    }) == []


def test_framework_words_come_back_lowercased_and_sorted():
    hit = gen.leak_check({"qui_tu_es": "Ton RIASEC est net.",
                          "vibrer": "Un Score élevé en Big Five."})
    assert hit == ["big five", "riasec", "score"]


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
