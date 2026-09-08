"""Per-parcours message formatting and validation."""
import json

import pytest

from app.routes.analyses import VALIDATORS
from app.services.anthropic_service import _format_user_message


# ── message formatting ───────────────────────────────────────────────────────

def test_p1_carries_cv_and_target():
    msg = _format_user_message({
        "_path": "1", "cv_text": "8 ans d'administration", "cible_visee": "Chargé RH",
        "prenom": "Marie", "nom": "dupont",
    })
    assert "8 ans d'administration" in msg
    assert "Chargé RH" in msg
    assert "Nom : DUPONT" in msg


def test_p1_chemin_b_adds_a_framing_note_and_no_lookup():
    """PM: framing note only at launch — no web search, so the report says
    the analysis rests on the description rather than on sourced data."""
    msg = _format_user_message({
        "_path": "1", "_chemin": "B", "cv_text": "x", "cible_visee": "Facteur",
    })
    assert "note de cadrage" in msg
    assert "d'après votre description" in msg


def test_p1_without_chemin_b_has_no_framing_note():
    msg = _format_user_message({"_path": "1", "cv_text": "x", "cible_visee": "Facteur"})
    assert "note de cadrage" not in msg


def test_p2_asks_three_questions_not_four():
    msg = _format_user_message({
        "_path": "2", "cv_text": "parcours",
        "satisfaction": "les projets d'équipe",
        "refus": "le reporting",
        "raison_changement": "un choix personnel",
    })
    assert "les projets d'équipe" in msg
    assert "le reporting" in msg
    assert "un choix personnel" in msg


def test_p3_runs_off_the_life_questionnaire():
    msg = _format_user_message({
        "_path": "3",
        "experiences": "bénévolat au club de foot",
        "aime_faire": "organiser",
        "refus": "le travail de nuit",
        "contraintes": "pas de voiture",
        "bon_travail": "une équipe",
    })
    assert "bénévolat au club de foot" in msg
    assert "QUESTIONNAIRE DE VIE" in msg


def test_p3_accepts_an_optional_partial_cv():
    base = {
        "_path": "3", "experiences": "x", "aime_faire": "y",
        "refus": "z", "contraintes": "w", "bon_travail": "v",
    }
    assert "CV PARTIEL" not in _format_user_message(base)
    assert "CV PARTIEL" in _format_user_message({**base, "cv_text": "quelques lignes"})


def test_legacy_path_codes_still_format():
    """Analyses written before the migration carry 'A'/'B'."""
    assert "CV DU CANDIDAT" in _format_user_message({"_path": "A", "cv_text": "x", "cible_visee": "y"})
    assert "QUESTIONNAIRE DE VIE" in _format_user_message({"_path": "B", "experiences": "x"})


# ── bloc 5 and OETH reach the prompt in reduced form only ────────────────────

def test_conditions_reach_the_prompt_already_reduced():
    msg = _format_user_message({
        "_path": "1", "cv_text": "x", "cible_visee": "y",
        "_conditions": {
            "points_forts": ["Rythme"],
            "possible_avec_adaptation": ["Attention"],
            "a_eviter": ["Déplacements"],
        },
    })
    assert "CONDITIONS DE TRAVAIL" in msg
    assert "Points forts (exigences que peu de gens tiennent) : Rythme" in msg


def test_conditions_block_is_omitted_when_bloc5_is_empty():
    msg = _format_user_message({"_path": "1", "cv_text": "x", "cible_visee": "y"})
    assert "CONDITIONS DE TRAVAIL" not in msg


def test_oeth_reaches_the_prompt_as_schemes_never_as_a_diagnosis():
    msg = _format_user_message({
        "_path": "1", "cv_text": "x", "cible_visee": "y", "_oeth": True,
    })
    assert "Agefiph" in msg
    assert "aucun terme médical" in msg or "terme médical" in msg
    # The instruction forbids naming the status in the report itself.
    assert "Ne jamais mentionner ce statut" in msg


def test_no_rights_block_without_the_flag():
    msg = _format_user_message({"_path": "1", "cv_text": "x", "cible_visee": "y"})
    assert "DISPOSITIFS MOBILISABLES" not in msg


# ── validation ───────────────────────────────────────────────────────────────

def test_p2_requires_a_cv_and_all_three_answers():
    errors = VALIDATORS["2"]({"cv_text": "trop court"})
    assert len(errors) == 4


def test_p2_accepts_a_complete_submission():
    assert VALIDATORS["2"]({
        "cv_text": "x" * 200,
        "satisfaction": "les projets menés de bout en bout",
        "refus": "les tâches purement administratives",
        "raison_changement": "une évolution de mon secteur",
    }) == []


def test_p3_needs_no_cv():
    """The parcours exists for people who don't have one."""
    assert VALIDATORS["3"]({
        "experiences": "bénévolat, garde d'enfants",
        "aime_faire": "organiser des événements",
        "refus": "le travail de nuit",
        "contraintes": "pas de permis",
        "bon_travail": "une équipe soudée",
    }) == []


def test_p3_thresholds_are_lower_than_p2():
    """A long-answer requirement is the kind of barrier parcours 3 removes."""
    short = "x" * 12
    assert VALIDATORS["3"]({
        "experiences": short, "aime_faire": short, "refus": short,
        "contraintes": short, "bon_travail": short,
    }) == []
    assert VALIDATORS["2"]({"cv_text": "x" * 200, "satisfaction": short,
                            "refus": short, "raison_changement": short}) != []


def test_p1_needs_only_a_cv_and_a_target():
    """The Profil de base supplies the rest.

    Identity, age, location, situation and `type_mobilite` used to be required
    here, so an analysis could be rejected over fields the person had already
    filled once — and over `type_mobilite`, which the CDC v1.2 profile merged
    into `situation` and no longer exists anywhere.
    """
    errors = VALIDATORS["1"]({"cv_text": "c" * 300, "cible_visee": "t" * 60})
    assert errors == []


def test_p1_still_requires_the_cv_and_the_target():
    errors = VALIDATORS["1"]({"cv_text": "trop court", "cible_visee": "trop courte"})
    assert len(errors) == 2


def test_p1_omits_the_notes_line_when_there_is_none():
    """The field is gone from the form; a run without one must not send an
    empty placeholder the model would try to interpret."""
    msg = _format_user_message({"_path": "1", "cv_text": "x", "cible_visee": "y"})
    assert "Notes spécifiques" not in msg


def test_p1_still_carries_notes_from_a_pre_migration_draft():
    msg = _format_user_message({
        "_path": "1", "cv_text": "x", "cible_visee": "y",
        "notes_specifiques": "disponible à partir de septembre",
    })
    assert "Notes spécifiques : disponible à partir de septembre" in msg


# ── chemin A / B (Parcours doc §4) ───────────────────────────────────────────

def test_chemin_b_lets_a_short_target_through():
    """The doc puts the floor for a described target at 20 characters."""
    errors = VALIDATORS["1"]({
        "cv_text": "c" * 300, "_chemin": "B", "cible_visee": "Chauffeur livreur PL",
    })
    assert errors == []


def test_chemin_a_still_wants_a_real_offer():
    """20 characters of job ad is a paste that went wrong."""
    errors = VALIDATORS["1"]({
        "cv_text": "c" * 300, "_chemin": "A", "cible_visee": "Chauffeur livreur PL",
    })
    assert errors == ["Cible visée trop courte (minimum 50 caractères)."]


def test_an_analysis_without_a_chemin_is_treated_as_an_offer():
    """Rows written before the split behaved as chemin A — no framing note,
    and the 50-character floor."""
    errors = VALIDATORS["1"]({"cv_text": "c" * 300, "cible_visee": "trop court"})
    assert errors == ["Cible visée trop courte (minimum 50 caractères)."]


def test_normalize_chemin_defaults_to_the_offer():
    from app.routes.analyses import _normalize_chemin

    assert _normalize_chemin("b") == "B"
    assert _normalize_chemin("A") == "A"
    assert _normalize_chemin(None) == "A"
    assert _normalize_chemin("nonsense") == "A"


def test_create_persists_the_chemin_so_the_framing_note_can_fire(app, client):
    """The whole point of the wiring.

    `_chemin` was read by _format_user_message_p1 and set by nobody, so the
    chemin B framing note was unreachable code. This is the end-to-end path:
    the form sends it, create stores it, and the message built from those
    stored inputs carries the note.
    """
    from unittest.mock import patch

    with patch("app.routes.analyses.start_analysis"):
        res = client.post("/api/analyses/", json={"inputs": {
            "_path": "1", "_chemin": "B",
            "cv_text": "c" * 300, "cible_visee": "Chauffeur livreur PL",
        }})
    assert res.status_code == 201, res.data

    stored = json.loads(res.data)["analysis"]["inputs"]
    assert stored["_chemin"] == "B"
    assert "note de cadrage" in _format_user_message(stored)


def test_create_leaves_parcours_2_and_3_without_a_chemin(app, client):
    """Only parcours 1 has chemins; the key elsewhere would be noise in the
    stored inputs and in every prompt built from them."""
    from unittest.mock import patch

    with patch("app.routes.analyses.start_analysis"):
        res = client.post("/api/analyses/", json={"inputs": {
            "_path": "3",
            "experiences": "bénévolat au club de foot pendant six ans",
            "aime_faire": "organiser, réparer des choses",
            "refus": "le travail de nuit",
            "contraintes": "pas de permis",
            "bon_travail": "une équipe, dehors",
        }})
    assert res.status_code == 201, res.data
    assert "_chemin" not in json.loads(res.data)["analysis"]["inputs"]
