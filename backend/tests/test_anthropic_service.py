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


# ── markdown fallback: letter and Roman key sets ─────────────────────────────

def test_markdown_letter_keys_parcours_2():
    raw = "## §A Capital\ncorps A\n## §C Compétences\ncorps C\n"
    out = _parse_output(raw, "2")
    assert set(out.keys()) == {"A", "C"}
    assert out["A"]["body_markdown"] == "corps A"


def test_markdown_roman_keys_parcours_3():
    raw = "## §I Capital de vie\ncorps un\n## §II Compétences\ncorps deux\n"
    out = _parse_output(raw, "3")
    assert set(out.keys()) == {"I", "II"}
    assert out["II"]["body_markdown"] == "corps deux"


def test_roman_vi_not_read_as_v():
    """Longest-first alternation: §VI must not match the §V branch."""
    raw = "## §V Dispositifs\ncorps V\n## §VI Ébauche de CV\ncorps VI\n"
    out = _parse_output(raw, "3")
    assert set(out.keys()) == {"V", "VI"}
    assert out["VI"]["body_markdown"] == "corps VI"
    assert out["V"]["body_markdown"] == "corps V"


def test_letter_keyed_json_is_not_rejected():
    """Regression: the old validity test was `any(k.isdigit())`, which sent
    letter-keyed JSON down the last-resort path and collapsed the report."""
    raw = json.dumps({
        "A": {"title": "Capital", "body_markdown": "b", "items": []},
        "C": {"title": "Compétences", "body_markdown": "", "items": ["x"]},
    })
    out = _parse_output(raw, "2")
    assert set(out.keys()) == {"A", "C"}


def test_plain_text_falls_back_to_first_key_of_parcours():
    raw = "Juste un paragraphe sans structure aucune."
    assert list(_parse_output(raw, "2").keys()) == ["A"]
    assert list(_parse_output(raw, "3").keys()) == ["I"]


# ── schema builder ────────────────────────────────────────────────────────────

def test_section_keys_per_parcours_tier():
    # Free tier is §1-§3 plus the verdict; §4 moved to paid in CDC v1.2.
    assert _section_keys("1", "haiku") == ["1", "2", "3", "verdict"]
    assert _section_keys("1", "sonnet") == [str(n) for n in range(1, 10)]
    assert _section_keys("1", "opus") == [str(n) for n in range(1, 12)]
    assert _section_keys("2", "sonnet") == ["A", "C", "D", "B", "E", "F", "G"]
    assert _section_keys("3", "sonnet") == ["I", "II", "III", "IV", "V", "VI"]


def test_legacy_path_codes_still_resolve():
    """Rows written before the 3-parcours migration carry 'A'/'B'."""
    assert _section_keys("A", "sonnet") == _section_keys("1", "sonnet")
    assert _section_keys("B", "sonnet") == _section_keys("3", "sonnet")


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


def test_schema_shape_parcours_2():
    schema = _build_output_schema("2", "sonnet")
    assert set(schema["properties"].keys()) == {"A", "B", "C", "D", "E", "F", "G"}
    assert "Capital professionnel" in schema["properties"]["A"]["description"]


def test_schema_shape_parcours_3_premium():
    schema = _build_output_schema("3", "opus")
    assert set(schema["properties"].keys()) == {"I", "II", "III", "IV", "V", "VI"}
    assert "Ébauche de CV" in schema["properties"]["VI"]["description"]


def test_tags_sections_get_a_tags_description():
    schema = _build_output_schema("1", "haiku")
    tags_sec = schema["properties"]["3"]
    assert "tags" in tags_sec["properties"]["items"]["description"].lower()
    assert "Chaîne vide" in tags_sec["properties"]["body_markdown"]["description"]
