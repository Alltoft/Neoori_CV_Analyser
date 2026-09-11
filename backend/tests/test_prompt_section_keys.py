"""Every seeded prompt must describe the sections its schema actually asks for.

Parcours 3 shipped for weeks on a prompt that documented sections 1, 2, 3, 8
and 9 while the registry emitted I, II, III, verdict, IV, V and VI. Nothing
failed loudly: `_build_output_schema` is built from the registry and the model
obeys the schema, so the report came back with the right keys and content
written against instructions for sections that no longer existed.

That is the drift this file exists to catch. A prompt is free to say whatever
the PM wants about tone, length and content — but the key set it declares in
its ```json example has to match the registry, because that example is the
only place the prompt and the schema are supposed to agree.

The seed scripts call create_app() at import time, so these read them as text
rather than importing them.
"""
import json
import re
from pathlib import Path

import pytest

from app.services import prompt_slots
from app.services import section_registry as registry

BACKEND = Path(__file__).resolve().parent.parent

# `PATH = "2"` — the parcours a seed script targets.
_PATH_RE = re.compile(r'^PATH\s*=\s*["\'](\w+)["\']', re.MULTILINE)
# The ```json ... ``` response example inside the prompt text.
_JSON_BLOCK_RE = re.compile(r"```json\s*\n(\{.*?\n\})\s*\n```", re.DOTALL)


def _seed_scripts():
    """(filename, parcours, declared keys) for every parcours-bound seed script."""
    found = []
    for script in sorted(BACKEND.glob("seed_prompt*.py")):
        source = script.read_text(encoding="utf-8")
        path_match = _PATH_RE.search(source)
        if not path_match:
            # seed_prompt.py predates the path column; the reheal migration
            # assigns it. Nothing to check against a parcours here.
            continue
        slot = path_match.group(1)
        if prompt_slots.is_voyage(slot):
            # The voyage prompts are not parcours: they have no registry
            # sections, and the phrase prompt returns one plain sentence with no
            # JSON at all. test_seed_scripts.py guards their shape instead.
            continue
        block = _JSON_BLOCK_RE.search(source)
        assert block, f"{script.name} declares PATH but has no ```json example"
        keys = list(json.loads(block.group(1)).keys())
        found.append(pytest.param(script.name, slot, keys, id=script.name))
    return found


SEEDS = _seed_scripts()


def test_there_is_a_seed_script_for_every_parcours():
    """A parcours with no seeded prompt fails at generation time with
    "Aucun prompt actif" — a blank report rather than a bad one."""
    covered = {parcours for p in SEEDS for parcours in [p.values[1]]}
    assert covered == set(registry.PARCOURS), (
        f"parcours without a seed script: {set(registry.PARCOURS) - covered}"
    )


@pytest.mark.parametrize("name,parcours,declared", SEEDS)
def test_the_prompt_declares_exactly_the_registry_sections(name, parcours, declared):
    expected = registry.section_keys(parcours)
    assert declared == expected, (
        f"{name} documents {declared} but the schema for parcours {parcours} "
        f"asks for {expected}"
    )


@pytest.mark.parametrize("name,parcours,declared", SEEDS)
def test_tag_sections_are_documented_as_items_only(name, parcours, declared):
    """A "tags" section renders as a tag cloud: prose in body_markdown is
    dropped on the page, so a prompt that asks for it wastes tokens on text
    nobody sees."""
    tag_keys = {s["key"] for s in registry.sections(parcours) if s["render"] == registry.TAGS}
    source = (BACKEND / name).read_text(encoding="utf-8")
    example = json.loads(_JSON_BLOCK_RE.search(source).group(1))
    for key in tag_keys:
        # Absent is fine — the schema makes body_markdown required anyway, so
        # the model always sends one. What must not appear is a prose
        # placeholder, which asks for paragraphs the tag cloud then discards.
        assert not example[key].get("body_markdown"), (
            f"{name}: section {key} renders as a tag cloud, so its example must "
            f'not ask for prose in body_markdown'
        )
