"""The voyage's lock reasons and portrait section titles are written twice —
keep the two copies honest.

`backend/app/models/voyage.py` owns LOCK_CODE / LOCK_PROFILE / LOCK_ORDER and
`backend/app/services/voyage/generation.py` owns PORTRAIT_TITLES.
`frontend/src/types/voyage.ts` mirrors both: the hub renders a locked card's
reason client-side (sessionLock()) before the server ever answers, and the
candidate portrait page + counselor editor need the six section headings the
API does not send. A drift between the two files is silent: the wrong string
renders in French and nothing throws.

There is no JS test runner in this repo, so this reads the TypeScript as
text — the same approach as test_conditions_parity.py.
"""
import re
from pathlib import Path

import pytest

from app.models import voyage
from app.services.voyage import generation

VOYAGE_TS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "voyage.ts"
)


@pytest.fixture(scope="module")
def source() -> str:
    assert VOYAGE_TS.exists(), f"missing {VOYAGE_TS}"
    return VOYAGE_TS.read_text(encoding="utf-8")


def _lock_value(source: str, name: str) -> str:
    """The string literal of `export const <name> = "…"`, anchored on the
    declaration so a match can't drift onto some other occurrence of the word."""
    m = re.search(rf'export const {name}\s*=\s*"([^"]*)"', source)
    assert m, f"could not find `export const {name} = \"...\"` in {VOYAGE_TS}"
    return m.group(1)


def _portrait_sections(source: str) -> list[tuple[str, str]]:
    """The ordered (key, title) pairs out of the PORTRAIT_SECTIONS array."""
    start = source.index("export const PORTRAIT_SECTIONS")
    end = source.index("\n]", start)
    block = source[start:end]
    return re.findall(r'key:\s*"([^"]+)",\s*title:\s*"([^"]+)"', block)


def test_lock_code_matches(source):
    assert _lock_value(source, "LOCK_CODE") == voyage.LOCK_CODE


def test_lock_profile_matches(source):
    assert _lock_value(source, "LOCK_PROFILE") == voyage.LOCK_PROFILE


def test_lock_order_matches(source):
    assert _lock_value(source, "LOCK_ORDER") == voyage.LOCK_ORDER


def test_portrait_sections_match_titles_in_order(source):
    pairs = _portrait_sections(source)
    assert pairs == list(generation.PORTRAIT_TITLES.items())


def test_portrait_sections_keys_match_portrait_keys(source):
    pairs = _portrait_sections(source)
    assert [key for key, _title in pairs] == list(voyage.PORTRAIT_KEYS)
