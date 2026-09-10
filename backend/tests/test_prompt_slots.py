"""PromptVersion.path holds a prompt *slot*, not a parcours id.

The voyage adds two prompts that are not parcours. Numbering them "4" and "5"
would make them appear as parcours everywhere the section registry is iterated
— the admin selector, the cost dashboard, the report renderer — so they get
names instead, and this module is the only place that knows the legal set.
"""
from app.services import prompt_slots
from app.services import section_registry as registry


def test_the_five_slots_are_the_parcours_plus_the_two_voyage_prompts():
    assert prompt_slots.valid() == ("1", "2", "3", "voyage_micro", "voyage_portrait")


def test_parcours_ids_come_first():
    """The admin selector renders valid() in order; parcours are the daily job."""
    assert prompt_slots.valid()[:3] == tuple(registry.PARCOURS)


def test_every_slot_fits_the_column():
    """prompt_versions.path is String(16); 'voyage_portrait' is 15 characters."""
    assert max(len(s) for s in prompt_slots.valid()) <= 16


def test_legacy_path_codes_still_fold_onto_parcours():
    """Rows written before the 3-parcours migration carry 'A'/'B'."""
    assert prompt_slots.normalize("A") == "1"
    assert prompt_slots.normalize("B") == "3"
    assert prompt_slots.normalize("a") == "1"


def test_empty_and_unknown_fall_back_to_parcours_one():
    assert prompt_slots.normalize(None) == "1"
    assert prompt_slots.normalize("") == "1"
    assert prompt_slots.normalize("   ") == "1"
    assert prompt_slots.normalize("nonsense") == registry.DEFAULT_PARCOURS


def test_voyage_slots_survive_normalisation_whatever_the_case():
    """The old _read_path uppercased before validating, and 'VOYAGE_MICRO' is
    not a slot — the voyage check has to happen before any .upper()."""
    assert prompt_slots.normalize("voyage_micro") == "voyage_micro"
    assert prompt_slots.normalize("VOYAGE_MICRO") == "voyage_micro"
    assert prompt_slots.normalize("  Voyage_Portrait  ") == "voyage_portrait"


def test_is_valid_and_is_voyage():
    assert prompt_slots.is_valid("voyage_portrait") is True
    assert prompt_slots.is_valid("4") is False
    assert prompt_slots.is_valid(None) is False
    assert prompt_slots.is_voyage("voyage_micro") is True
    assert prompt_slots.is_voyage("1") is False


def test_labels_are_french_and_cover_every_slot():
    for slot in prompt_slots.valid():
        assert prompt_slots.label(slot) != slot, f"{slot} has no label"
    assert prompt_slots.label("voyage_micro") == "Voyage · phrase (S0)"
    assert prompt_slots.label("voyage_portrait") == "Voyage · portrait"


def test_choices_are_selector_ready():
    assert prompt_slots.choices() == [
        {"value": "1", "label": "Parcours 1 · J'ai une cible"},
        {"value": "2", "label": "Parcours 2 · Je cherche ma direction"},
        {"value": "3", "label": "Parcours 3 · Je pars de zéro"},
        {"value": "voyage_micro", "label": "Voyage · phrase (S0)"},
        {"value": "voyage_portrait", "label": "Voyage · portrait"},
    ]


# ── the column that holds a slot ─────────────────────────────────────────────

def test_the_path_column_is_wide_enough_for_a_slot():
    """'voyage_portrait' is 15 characters. On MySQL a String(1) column would
    have refused it (or truncated it, which is worse: the generation lookup
    filters on this column and would silently find nothing)."""
    from app.models.prompt_version import PromptVersion
    assert PromptVersion.__table__.c.path.type.length == 16


def test_a_voyage_slot_survives_a_round_trip_through_the_column(app):
    from app.extensions import db
    from app.models.prompt_version import PromptVersion
    prompt = PromptVersion(
        version_label="v1.0-VM",
        system_prompt_text="…",
        path=prompt_slots.VOYAGE_PORTRAIT,
        is_active=True,
    )
    db.session.add(prompt)
    db.session.commit()
    found = PromptVersion.query.filter_by(is_active=True, path="voyage_portrait").first()
    assert found is not None
    assert found.to_dict(include_text=False)["path"] == "voyage_portrait"


# ── the admin route that writes the column ───────────────────────────────────

def test_the_prompts_route_accepts_a_voyage_slot(client, admin_headers):
    """Without this the PM cannot publish either voyage prompt from
    /admin/prompts, and the feature errors on first use."""
    res = client.post("/api/prompts/", headers=admin_headers, json={
        "version_label": "v1.0-VM",
        "system_prompt_text": "Tu écris une phrase.",
        "path": "voyage_micro",
        "activate": True,
    })
    assert res.status_code == 201
    assert res.get_json()["prompt"]["path"] == "voyage_micro"

    active = client.get("/api/prompts/active?path=voyage_micro")
    assert active.status_code == 200
    assert active.get_json()["prompt"]["version_label"] == "v1.0-VM"


def test_the_same_label_may_exist_once_per_slot(client, admin_headers):
    """The uniqueness check is scoped to the slot, so 'v1.0' can belong to a
    parcours and to a voyage prompt at once."""
    body = {"version_label": "v1.0", "system_prompt_text": "x"}
    assert client.post("/api/prompts/", headers=admin_headers,
                       json={**body, "path": "1"}).status_code == 201
    assert client.post("/api/prompts/", headers=admin_headers,
                       json={**body, "path": "voyage_portrait"}).status_code == 201
    assert client.post("/api/prompts/", headers=admin_headers,
                       json={**body, "path": "voyage_portrait"}).status_code == 409


def test_activating_a_voyage_prompt_leaves_the_parcours_prompts_alone(client, admin_headers):
    """Activation deactivates the others *for that slot* only — activating the
    portrait prompt must not silently disable parcours 1."""
    from app.models.prompt_version import PromptVersion
    client.post("/api/prompts/", headers=admin_headers, json={
        "version_label": "v9-P1", "system_prompt_text": "x", "path": "1", "activate": True})
    client.post("/api/prompts/", headers=admin_headers, json={
        "version_label": "v9-VP", "system_prompt_text": "x",
        "path": "voyage_portrait", "activate": True})
    assert PromptVersion.query.filter_by(is_active=True, path="1").count() == 1
    assert PromptVersion.query.filter_by(is_active=True, path="voyage_portrait").count() == 1
