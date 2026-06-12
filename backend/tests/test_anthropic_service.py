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
    assert _split_markdown_sections("## §1 Titre\ncorps") is None


def test_duplicate_headings_keep_first():
    raw = "## §1 A\nun\n## §2 B\ndeux\n## §1 A encore\ntrois"
    out = _split_markdown_sections(raw)
    assert out["1"]["body_markdown"] == "un"


# ── schema builder ────────────────────────────────────────────────────────────

def test_section_keys_per_path_tier():
    assert _section_keys("A", "haiku") == ["1", "2", "3", "4"]
    assert _section_keys("A", "sonnet") == [str(n) for n in range(1, 10)]
    assert _section_keys("B", "sonnet") == ["1", "2", "3", "8", "9"]


def test_schema_shape_haiku():
    schema = _build_output_schema("A", "haiku")
    assert schema["required"] == ["1", "2", "3", "4"]
    assert schema["additionalProperties"] is False
    sec = schema["properties"]["1"]
    assert sec["required"] == ["title", "body_markdown", "items"]
    assert sec["additionalProperties"] is False


def test_schema_shape_path_b():
    schema = _build_output_schema("B", "sonnet")
    assert set(schema["properties"].keys()) == {"1", "2", "3", "8", "9"}
    assert "Forces latentes" in schema["properties"]["2"]["description"]
