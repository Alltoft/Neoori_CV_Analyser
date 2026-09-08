"""Bloc 5's taxonomy is written twice — keep the two copies honest.

`backend/app/models/profile.py` validates the answers and `frontend/src/types/
conditions.ts` renders the form and the live synthesis. The backend drops any
family or state it does not recognise rather than raising, because a malformed
optional answer should not cost someone their profile — which means a drift
between the two files loses answers *silently*: the person fills a row, sees it
in « Ce que votre profil dit déjà », and the report never receives it.

DIFFERENTIATING is the sharper one. It decides which point fort counts as a
strength, and it is the rule the live synthesis promises: "un point fort, c'est
une exigence que peu de gens tiennent". If the frontend set grew a family the
backend does not share, the panel would show someone a strength the report is
then guaranteed to ignore.

There is no JS test runner in this repo, so this reads the TypeScript as text —
the same approach as test_prompt_section_keys.py.
"""
import re
from pathlib import Path

import pytest

from app.models import profile

CONDITIONS_TS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "conditions.ts"
)


@pytest.fixture(scope="module")
def source() -> str:
    assert CONDITIONS_TS.exists(), f"missing {CONDITIONS_TS}"
    return CONDITIONS_TS.read_text(encoding="utf-8")


def _block(source: str, name: str) -> str:
    """The text of an exported const array.

    Ends on the `]` that starts a line — the type annotation these consts carry
    (`{...}[] = [`) puts a closing bracket ahead of the array itself.
    """
    start = source.index(f"export const {name}")
    return source[start : source.index("\n]", start)]


def _values(block: str) -> set[str]:
    return set(re.findall(r'value:\s*"([^"]+)"', block))


def test_the_eight_families_match(source):
    assert _values(_block(source, "CONDITION_FAMILIES")) == set(profile.CONDITION_FAMILIES)


def test_the_three_states_match(source):
    assert _values(_block(source, "CONDITION_STATES")) == set(profile.CONDITION_STATES)


def test_the_differentiating_families_match(source):
    """The live synthesis must promote exactly what prompt_context() promotes."""
    start = source.index("const DIFFERENTIATING")
    declared = set(re.findall(r'"([^"]+)"', source[start : source.index(")", start)]))
    assert declared == profile.DIFFERENTIATING


def test_a_preference_is_never_shown_as_a_strength():
    """The rule the panel exists to hold: tolerating a demanding requirement
    differentiates, preferring a comfortable one does not."""
    assert profile.DIFFERENTIATING < set(profile.CONDITION_FAMILIES)
    for family in ("attention", "relation", "consignes", "organisation"):
        assert family not in profile.DIFFERENTIATING
        ctx = profile.prompt_context({family: {"state": "me_convient", "point_fort": True}})
        assert ctx["points_forts"] == []


def test_a_tolerated_demanding_requirement_is_a_strength():
    ctx = profile.prompt_context({"rythme": {"state": "a_eviter", "point_fort": True}})
    assert ctx["points_forts"] == ["rythme"]
