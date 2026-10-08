import json

from app.services.anthropic_service import (
    _build_output_schema,
    _parse_output,
    _section_keys,
    _split_markdown_sections,
)


# ── _parse_output: JSON paths ─────────────────────────────────────────────────

def test_parse_clean_json():
    raw = json.dumps({"1": {"title": "T", "body_markdown": "b", "items": []}})
    out = _parse_output(raw)
    assert out["1"]["title"] == "T"


def test_parse_json_in_fences():
    raw = "```json\n" + json.dumps({"1": {"title": "T", "body_markdown": "b", "items": []},
                                    "2": {"title": "U", "body_markdown": "c", "items": ["x"]}}) + "\n```"
    out = _parse_output(raw)
    assert set(out.keys()) == {"1", "2"}


def test_parse_malformed_json_repaired():
    raw = '{"1": {"title": "T", "body_markdown": "line\nbreak", "items": [],}}'
    out = _parse_output(raw)
    assert "1" in out


# ── _parse_output: markdown fallback (PM prose prompt → markdown response) ───

MD_RESPONSE = """# ANALYSE NEOORI — MARIE DUPONT
## Document d'analyse — Sections §1 à §4

---

## §1 Lecture strategique du parcours

Marie cumule 8 années d'expérience dans l'administration.

**Décalage profil/cible : modéré.**

## §2 Forces du profil pour la cible

**Rigueur** · ancrée dans le CV.

### §3 Compétences transférables

Gestion d'agenda · Facturation · Accueil

## §4 Ce qui reste à renforcer

Constat : pas d'expérience RH.

---

**Fin de l'analyse — Sections §1 à §4**
"""


def test_markdown_response_splits_into_sections():
    out = _parse_output(MD_RESPONSE)
    assert set(out.keys()) == {"1", "2", "3", "4"}
    assert "8 années" in out["1"]["body_markdown"]
    assert out["1"]["title"].startswith("Lecture")
    assert "Rigueur" in out["2"]["body_markdown"]
    assert "Facturation" in out["3"]["body_markdown"]
    # §2 content must not leak into §1
    assert "Rigueur" not in out["1"]["body_markdown"]


def test_markdown_section_word_headings():
    raw = "Section 1 : Lecture\ncorps un\nSection 2 — Forces\ncorps deux\n"
    out = _parse_output(raw)
    assert set(out.keys()) == {"1", "2"}
    assert out["2"]["body_markdown"] == "corps deux"


def test_plain_text_falls_back_to_section_1():
    raw = "Juste un paragraphe sans structure aucune."
    out = _parse_output(raw)
    assert list(out.keys()) == ["1"]
    assert out["1"]["body_markdown"] == raw


def test_split_returns_none_for_single_heading():
    assert _split_markdown_sections("## §1 Titre\ncorps", "1") is None


def test_duplicate_headings_keep_first():
    raw = "## §1 A\nun\n## §2 B\ndeux\n## §1 A encore\ntrois"
    out = _split_markdown_sections(raw, "1")
    assert out["1"]["body_markdown"] == "un"


# ── markdown fallback: two-digit keys ─────────────────────────────────────────

def test_two_digit_headings_are_not_read_as_section_1():
    """§10 and §11 land in their own slots, never in §1's (the coverage the
    roman-numeral test gave before parcours 3 was retired)."""
    raw = "## §1 Lecture\ncorps un\n## §10 Entretien\ncorps dix\n## §11 Questions\ncorps onze\n"
    out = _parse_output(raw, "1")
    assert set(out.keys()) == {"1", "10", "11"}
    assert out["1"]["body_markdown"] == "corps un"
    assert out["10"]["body_markdown"] == "corps dix"
    assert out["11"]["body_markdown"] == "corps onze"


# ── schema builder ────────────────────────────────────────────────────────────

def test_section_keys_per_tier():
    # Free tier is §1-§3 plus the verdict; §4 moved to paid in CDC v1.2.
    assert _section_keys("1", "haiku") == ["1", "2", "3", "verdict"]
    assert _section_keys("1", "sonnet") == [str(n) for n in range(1, 10)]
    assert _section_keys("1", "opus") == [str(n) for n in range(1, 12)]


def test_plan_names_and_legacy_nicknames_agree():
    """Tier moved from model nicknames to plan names; both must resolve."""
    assert _section_keys("1", "free") == _section_keys("1", "haiku")
    assert _section_keys("1", "paid") == _section_keys("1", "sonnet")
    assert _section_keys("1", "premium") == _section_keys("1", "opus")


def test_premium_adds_the_interview_modules():
    assert _section_keys("1", "premium")[-2:] == ["10", "11"]


def test_legacy_and_retired_path_codes_resolve_to_parcours_1():
    """'A' predates the 3-parcours migration; '2', '3' and 'B' are retired."""
    for path in ("A", "2", "3", "B"):
        assert _section_keys(path, "sonnet") == _section_keys("1", "sonnet")


def test_verdict_is_free_only():
    assert "verdict" in _section_keys("1", "haiku")
    assert "verdict" not in _section_keys("1", "sonnet")
    assert "verdict" not in _section_keys("1", "opus")


def test_schema_shape_free():
    schema = _build_output_schema("1", "haiku")
    assert schema["required"] == ["1", "2", "3", "verdict"]
    assert schema["additionalProperties"] is False
    sec = schema["properties"]["1"]
    assert sec["required"] == ["title", "body_markdown", "items"]
    assert sec["additionalProperties"] is False


def test_tags_sections_get_a_tags_description():
    schema = _build_output_schema("1", "haiku")
    tags_sec = schema["properties"]["3"]
    assert "tags" in tags_sec["properties"]["items"]["description"].lower()
    assert "Chaîne vide" in tags_sec["properties"]["body_markdown"]["description"]


# ── _profile_block ────────────────────────────────────────────────────────────

def _block(**inputs) -> str:
    from app.services.anthropic_service import _profile_block
    return "\n".join(_profile_block(inputs))


def test_the_profile_block_carries_the_parcours_answers():
    """« Ton parcours » reaches the model in the same block as the rest of the
    Profil de base — it is one of its blocks now, not a voyage extra."""
    text = _block(prenom="Marie", diplome="bac", type_etudes="technologiques",
                  intitule_etudes="Bac STI2D", appetence_etudes="courtes")
    assert "Dernier diplôme : bac" in text
    assert "Type d'études : technologiques" in text
    assert "Intitulé : Bac STI2D" in text
    assert "Études envisagées : courtes" in text


def test_an_unanswered_parcours_says_so_rather_than_vanishing():
    """Same rule as every other line of the block: a missing answer is a fact
    the model should see, not a line it never gets."""
    text = _block(prenom="Marie")
    assert "Dernier diplôme : Non renseigné." in text
    assert "Études envisagées : Non renseigné." in text


def test_the_optional_intitule_is_dropped_when_empty():
    """It is free text and filters nothing, so an empty one is noise."""
    assert "Intitulé" not in _block(prenom="Marie", diplome="bac")


def test_the_radius_prints_only_for_rows_that_still_carry_one():
    """Retired from every form: ville plus the bassin d'emploi replaces it.
    Rows that answered it before keep sending it — the line is not re-asked,
    and it is not thrown away either."""
    assert "Rayon de recherche : 30km" in _block(prenom="Marie", rayon="30km")
    assert "Rayon" not in _block(prenom="Marie")


def test_the_projet_line_prints_only_when_the_profile_carries_one():
    """Retired from /profil: the analysis form's « cible visée » asks the same
    question, and the two were reaching the model as two lines saying the same
    thing. Rows that answered it before keep sending it."""
    assert "Projet : Devenir soudeur" in _block(prenom="Marie", projet="Devenir soudeur")
    assert "Projet" not in _block(prenom="Marie")


def test_a_bare_profile_block_has_no_placeholder_lines_left_over():
    """What survives with nothing filled in: identity, the fields that filter,
    and the constraints line. Never a « Projet : Non renseigné. » for a
    question the person was not asked."""
    text = _block(prenom="Marie")
    assert "Non renseigné." in text          # tranche d'âge, ville, situation…
    assert "Projet" not in text
    assert "Rayon" not in text
