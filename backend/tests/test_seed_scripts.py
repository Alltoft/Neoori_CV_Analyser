"""Guards the slot id the seed scripts write into PromptVersion.path.

CDC v1.2 replaced the A/B path codes with parcours ids, and the analysis lookup
filters on that column directly. A stale literal here seeds a prompt no analysis
can ever find — the run fails instantly with "Aucun prompt actif pour le chemin
1", which is what happened on the VPS after a fresh seed.

The voyage widened the column from a parcours id to a slot id, so the literal
regex reads a whole word now, not a single character.
"""
import ast
import re
from pathlib import Path

from app.services import prompt_slots

BACKEND = Path(__file__).resolve().parents[1]

# seed script → the slot its prompt belongs to
SEEDS = {
    "seed_prompt_v18.py": "1",                      # ex-path A, « J'ai une cible »
    "seed_prompt_v11_p3.py": "3",                   # ex-path B, « Je pars de zéro »
    "seed_prompt_v10_p2.py": "2",                   # authored after the migration
    "seed_prompt_v10_voyage_micro.py": "voyage_micro",
}

# (\w+), not (\w): a slot id is a name now, not a single character.
_LITERAL = re.compile(r"""(?:path\s*=|^PATH\s*=)\s*["'](\w+)["']""", re.MULTILINE)


def test_seed_scripts_write_valid_slot_ids():
    for name, expected in SEEDS.items():
        source = (BACKEND / name).read_text(encoding="utf-8")
        literals = set(_LITERAL.findall(source))
        assert literals, f"{name}: no path literal found"
        for value in literals:
            assert prompt_slots.is_valid(value), (
                f"{name}: path={value!r} is not a prompt slot "
                f"({list(prompt_slots.valid())})"
            )
            assert value == expected, f"{name}: expected path {expected!r}, found {value!r}"


def _promptversion_call_kwargs(source):
    """Keyword-argument dicts for every `PromptVersion(...)` constructor call.

    Walking the AST rather than grepping the raw text matters here: both seed
    scripts carry a long French docstring that *discusses* why the prompt
    lands active, and prose like that would satisfy a plain substring search.
    A docstring is an `ast.Expr`/`ast.Constant`, never an `ast.Call`, so it can
    never contribute a match here — only a real keyword argument on a real
    call to `PromptVersion(...)` does.
    """
    tree = ast.parse(source)
    return [
        {kw.arg: kw.value for kw in node.keywords if kw.arg}
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "PromptVersion"
    ]


def _filter_by_version_label_calls(source):
    """Keyword-argument dicts for every `<query>.filter_by(...)` call.

    Same reasoning as `_promptversion_call_kwargs`: the phrase
    `filter_by(version_label=VERSION_LABEL)` appears in the module docstring as
    prose explaining idempotency. The AST only sees real calls, so that prose
    contributes nothing to this check.
    """
    tree = ast.parse(source)
    return [
        {kw.arg: kw.value for kw in node.keywords if kw.arg}
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "filter_by"
    ]


def test_the_voyage_seeds_land_active():
    for name, slot in SEEDS.items():
        if not prompt_slots.is_voyage(slot):
            continue
        source = (BACKEND / name).read_text(encoding="utf-8")
        calls = _promptversion_call_kwargs(source)
        assert calls, f"{name}: no PromptVersion(...) constructor call found"
        assert any(
            isinstance(kwargs.get("is_active"), ast.Constant) and kwargs["is_active"].value is True
            for kwargs in calls
        ), f"{name}: must seed the prompt ACTIVE (is_active=True in the PromptVersion(...) call)"


def test_the_voyage_seeds_are_idempotent():
    """Re-running a seed on the VPS must not duplicate the version."""
    for name, slot in SEEDS.items():
        if not prompt_slots.is_voyage(slot):
            continue
        source = (BACKEND / name).read_text(encoding="utf-8")
        calls = _filter_by_version_label_calls(source)
        assert any(
            isinstance(kwargs.get("version_label"), ast.Name) and kwargs["version_label"].id == "VERSION_LABEL"
            for kwargs in calls
        ), f"{name}: must look the version up before inserting (filter_by(version_label=VERSION_LABEL))"
