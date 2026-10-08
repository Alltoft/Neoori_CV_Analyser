"""What a client may put in an analysis's inputs (four-doors spec, decision 37)."""
from app.services import analysis_inputs


def test_keeps_the_three_client_keys_and_drops_every_other(app):
    raw = {
        "cv_text": "c" * 300, "cible_visee": "t" * 60, "_chemin": "B",
        "_conditions": ["injected"], "_oeth": True, "_voyage": ["x"], "_voyage_id": "v",
        "_tier": "premium", "_path": "2", "notes_specifiques": "n", "prenom": "Zoé",
    }
    inputs, errors = analysis_inputs.clean(raw)
    assert errors == []
    assert set(inputs) == {"cv_text", "cible_visee", "_chemin"}


def test_a_non_string_value_becomes_empty(app):
    inputs, _ = analysis_inputs.clean({"cv_text": {"a": 1}, "cible_visee": ["x"]})
    assert inputs == {"cv_text": "", "cible_visee": ""}


def test_an_empty_draft_stays_empty(app):
    assert analysis_inputs.clean({}) == ({}, [])


def test_a_long_real_cv_passes_and_one_past_the_cap_fails(app):
    # Review focus 3: measured after trimming, so padding never counts.
    ok, errors = analysis_inputs.clean({"cv_text": "  " + "c" * 39_999 + "\n\n"})
    assert errors == [] and len(ok["cv_text"]) == 39_999

    _, errors = analysis_inputs.clean({"cv_text": "c" * 40_001})
    assert errors == ["CV trop long (40 000 caractères maximum)."]


def test_the_target_has_its_own_cap(app):
    _, errors = analysis_inputs.clean({"cible_visee": "t" * 10_001})
    assert errors == ["Cible visée trop longue (10 000 caractères maximum)."]


def test_the_caps_come_from_config(app):
    app.config["CV_TEXT_MAX"] = 500
    _, errors = analysis_inputs.clean({"cv_text": "c" * 501})
    assert errors == ["CV trop long (500 caractères maximum)."]
