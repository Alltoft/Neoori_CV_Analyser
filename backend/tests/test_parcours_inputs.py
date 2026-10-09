"""Parcours 1 — message formatting and validation."""
import json

import pytest

from app.routes.analyses import _validate_inputs
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


@pytest.mark.parametrize("stored", ["1", "A", "2", "3", "B", None])
def test_every_stored_path_builds_the_parcours_1_message(stored):
    """Rows written before the migration carry 'A'; a retired '2', '3' or 'B'
    row still in the database before the purge reads as parcours 1 too."""
    inputs = {"cv_text": "x", "cible_visee": "y"}
    if stored is not None:
        inputs["_path"] = stored
    assert "--- CV DU CANDIDAT ---" in _format_user_message(inputs)


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

def test_p1_needs_only_a_cv_and_a_target():
    """The Profil de base supplies the rest.

    Identity, age, location, situation and `type_mobilite` used to be required
    here, so an analysis could be rejected over fields the person had already
    filled once — and over `type_mobilite`, which the CDC v1.2 profile merged
    into `situation` and no longer exists anywhere.
    """
    errors = _validate_inputs({"cv_text": "c" * 300, "cible_visee": "t" * 60})
    assert errors == []


def test_p1_still_requires_the_cv_and_the_target():
    errors = _validate_inputs({"cv_text": "trop court", "cible_visee": "trop courte"})
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
    errors = _validate_inputs({
        "cv_text": "c" * 300, "_chemin": "B", "cible_visee": "Chauffeur livreur PL",
    })
    assert errors == []


def test_chemin_a_still_wants_a_real_offer():
    """20 characters of job ad is a paste that went wrong."""
    errors = _validate_inputs({
        "cv_text": "c" * 300, "_chemin": "A", "cible_visee": "Chauffeur livreur PL",
    })
    assert errors == ["Cible visée trop courte (minimum 50 caractères)."]


def test_an_analysis_without_a_chemin_is_treated_as_an_offer():
    """Rows written before the split behaved as chemin A — no framing note,
    and the 50-character floor."""
    errors = _validate_inputs({"cv_text": "c" * 300, "cible_visee": "trop court"})
    assert errors == ["Cible visée trop courte (minimum 50 caractères)."]


def test_normalize_chemin_defaults_to_the_offer():
    from app.routes.analyses import _normalize_chemin

    assert _normalize_chemin("b") == "B"
    assert _normalize_chemin("A") == "A"
    assert _normalize_chemin(None) == "A"
    assert _normalize_chemin("nonsense") == "A"


def test_create_persists_the_chemin_so_the_framing_note_can_fire(app, client, candidate_headers):
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
        }}, headers=candidate_headers)
    assert res.status_code == 201, res.data

    stored = json.loads(res.data)["analysis"]["inputs"]
    assert stored["_chemin"] == "B"
    assert "note de cadrage" in _format_user_message(stored)


# ── parcours 2 and 3 are retired: every new analysis is parcours 1 ───────────

P1_TARGET = "Chargé de recrutement dans une PME industrielle du bassin lyonnais"


@pytest.mark.parametrize("posted", ["2", "3", "B", "b", ["2"], None])
def test_create_stamps_parcours_1_whatever_the_body_says(posted, app, client, candidate_headers):
    """The stored id is the server's: a stale page posting a retired parcours
    still gets a parcours 1 analysis, with its chemin."""
    from unittest.mock import patch

    inputs = {"cv_text": "c" * 300, "cible_visee": P1_TARGET}
    if posted is not None:
        inputs["_path"] = posted
    with patch("app.routes.analyses.start_analysis"):
        res = client.post("/api/analyses/", json={"inputs": inputs}, headers=candidate_headers)
    assert res.status_code == 201, res.data
    stored = json.loads(res.data)["analysis"]["inputs"]
    assert stored["_path"] == "1"
    assert stored["_chemin"] == "A"


def test_a_stale_parcours_3_form_gets_the_parcours_1_errors(app, client, candidate_headers):
    """Review Focus 1. The old P3 form sent no CV and no target: it now meets
    parcours 1's validation — a 400 in French, no run, never a 500."""
    from unittest.mock import patch

    with patch("app.routes.analyses.start_analysis") as start:
        res = client.post("/api/analyses/", json={"inputs": {
            "_path": "3",
            "experiences": "bénévolat au club de foot pendant six ans",
            "aime_faire": "organiser, réparer des choses",
            "refus": "le travail de nuit",
            "contraintes": "pas de permis",
            "bon_travail": "une équipe, dehors",
        }}, headers=candidate_headers)
    assert res.status_code == 400
    assert json.loads(res.data)["errors"] == [
        "CV trop court (minimum 200 caractères).",
        "Cible visée trop courte (minimum 50 caractères).",
    ]
    start.assert_not_called()


def test_a_stale_parcours_2_form_gets_the_parcours_1_error(app, client, candidate_headers):
    """Review Focus 1, the other retired page. The old P2 form did post a CV,
    so only the target is missing: parcours 1's validation answers with that
    one error — a 400 in French, no run, never a 500."""
    from unittest.mock import patch

    with patch("app.routes.analyses.start_analysis") as start:
        res = client.post("/api/analyses/", json={"inputs": {
            "_path": "2",
            "cv_text": "c" * 300,
            "satisfaction": "les projets menés de bout en bout",
            "refus": "les tâches purement administratives",
            "raison_changement": "une évolution de mon secteur",
        }}, headers=candidate_headers)
    assert res.status_code == 400
    assert json.loads(res.data)["errors"] == [
        "Cible visée trop courte (minimum 50 caractères).",
    ]
    start.assert_not_called()


@pytest.mark.parametrize("posted", ["2", "3", "B"])
def test_a_draft_carrying_a_retired_parcours_keeps_no_parcours(posted, app, client, candidate_headers):
    """A draft keeps only the allow-listed keys (four-doors spec, decision 37),
    and _path is not one of them: a stale page posting a retired parcours
    leaves none on the row, which reads as parcours 1, the only one left."""
    from app.models.analysis import Analysis

    res = client.post("/api/analyses/draft", json={"inputs": {"_path": posted, "cv_text": "x"}},
                      headers=candidate_headers)
    assert res.status_code == 201, res.data
    assert json.loads(res.data)["analysis"]["inputs"] == {"cv_text": "x"}
    assert Analysis.query.one().parcours == "1"


def test_a_draft_without_a_parcours_stays_without_one(app, client, candidate_headers):
    """An absent _path already means parcours 1; test_malformed_bodies.py also
    pins that an empty draft stays {}."""
    res = client.post("/api/analyses/draft", json={"inputs": {"cv_text": "x"}},
                      headers=candidate_headers)
    assert res.status_code == 201, res.data
    assert "_path" not in json.loads(res.data)["analysis"]["inputs"]
