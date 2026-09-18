"""The voyage's lock reasons, portrait section titles and two numeric twins
are written twice — keep the two copies honest.

`backend/app/models/voyage.py` owns LOCK_CODE / LOCK_PROFILE / LOCK_ORDER and
`backend/app/services/voyage/generation.py` owns PORTRAIT_TITLES.
`frontend/src/types/voyage.ts` mirrors both: the hub renders a locked card's
reason client-side (sessionLock()) before the server ever answers, and the
candidate portrait page + counselor editor need the six section headings the
API does not send. A drift between the two files is silent: the wrong string
renders in French and nothing throws.

Numeric constants are mirrored the same way, silently. `bank.NEUTRAL_MAX` and
`bank.RANK_MAX` are the counts at which the player greys out a « – » or a
further ranked choice — the counts the server refuses. And
`MICRO_RETRY_STALE_MINUTES` (backend,
converted to milliseconds) is the point past which the server allows a
session-0 phrase retry; the hub's own `POLL_MAX_MS` (frontend/src/app/
voyage/page.tsx) has to give up polling no earlier than that, or a person
could see the "Réessayer" button while the hub is still silently polling
(F8, final-review fix wave).

There is no JS test runner in this repo, so this reads the TypeScript as
text — the same approach as test_conditions_parity.py.
"""
import re
from pathlib import Path

import pytest

from app.models import voyage
from app.routes import voyage as voyage_routes
from app.services.voyage import bank, generation

VOYAGE_TS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "voyage.ts"
)
VOYAGE_PAGE_TS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "app" / "voyage"
    / "page.tsx"
)


@pytest.fixture(scope="module")
def source() -> str:
    assert VOYAGE_TS.exists(), f"missing {VOYAGE_TS}"
    return VOYAGE_TS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def voyage_page_source() -> str:
    assert VOYAGE_PAGE_TS.exists(), f"missing {VOYAGE_PAGE_TS}"
    return VOYAGE_PAGE_TS.read_text(encoding="utf-8")


def _lock_value(source: str, name: str) -> str:
    """The string literal of `export const <name> = "…"`, anchored on the
    declaration so a match can't drift onto some other occurrence of the word."""
    m = re.search(rf'export const {name}\s*=\s*"([^"]*)"', source)
    assert m, f"could not find `export const {name} = \"...\"` in {VOYAGE_TS}"
    return m.group(1)


def _ts_int_const(source: str, name: str, path: Path) -> int:
    """The value of `const <name> = <expr>`, anchored on the declaration.

    `<expr>` must be a bare integer literal or a `*`-chain of integer
    literals (e.g. `3 * 60 * 1000`) — the only two shapes this file's
    constants use. Anything else fails loudly rather than falling through to
    `eval` on arbitrary source text (F8, final-review fix wave)."""
    m = re.search(rf'const {name}\s*=\s*([^\n;]+)', source)
    assert m, f"could not find `const {name} = ...` in {path}"
    expr = m.group(1).strip()
    assert re.fullmatch(r"\d+(?:\s*\*\s*\d+)*", expr), (
        f"unexpected expression for {name} in {path}: {expr!r}"
    )
    value = 1
    for factor in expr.split("*"):
        value *= int(factor.strip())
    return value


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


def test_neutral_answer_matches(source):
    """The checklist row sends this string, and the bank accepts only this
    one — a drift turns every « – » tap into a 400."""
    assert _lock_value(source, "NEUTRAL") == bank.NEUTRAL


def test_neutral_max_matches(source):
    """The row greys out its « – » button at the same count the server
    refuses."""
    assert _ts_int_const(source, "NEUTRAL_MAX", VOYAGE_TS) == bank.NEUTRAL_MAX


def test_rank_max_matches(source):
    """A scene greys out further options at the same count the server
    refuses."""
    assert _ts_int_const(source, "RANK_MAX", VOYAGE_TS) == bank.RANK_MAX


def test_micro_retry_stale_ms_matches_poll_max_ms(voyage_page_source):
    """The hub must not give up polling a generating phrase before the
    server itself would accept a retry — otherwise "Réessayer" can appear
    while the hub is still silently about to receive the very phrase it is
    offering to relaunch."""
    poll_max_ms = _ts_int_const(voyage_page_source, "POLL_MAX_MS", VOYAGE_PAGE_TS)
    assert poll_max_ms == voyage_routes.MICRO_RETRY_STALE_MINUTES * 60 * 1000


def test_lock_parcours_matches(source):
    assert _lock_value(source, "LOCK_PARCOURS") == voyage.LOCK_PARCOURS


def test_lock_conditions_matches(source):
    assert _lock_value(source, "LOCK_CONDITIONS") == voyage.LOCK_CONDITIONS


def test_the_parcours_fields_match(source):
    """hasParcours() in the mirror must ask for the same fields as
    models.voyage.has_parcours, or the hub locks a card the server opens."""
    import re
    listed = re.search(
        r"\[([^\]]*)\]\s*as\s*const\)\s*\n?\s*\.every", source, re.S
    )
    assert listed, "hasParcours()'s field list not found in the mirror"
    assert set(re.findall(r'"([^"]+)"', listed.group(1))) == set(voyage.PARCOURS_FIELDS)


STEPS_TS = (
    Path(__file__).resolve().parents[2]
    / "frontend" / "src" / "lib" / "profile-steps.ts"
)


def test_every_remedy_link_names_a_real_lock():
    """LOCK_TO_STEP keys the locked card's remedy link off the lock string
    itself. A lock renamed on one side and not the other does not fail to
    compile — it silently drops the link, and the card goes back to naming a
    page the person has to go and find."""
    assert STEPS_TS.exists(), f"missing {STEPS_TS}"
    block = re.search(
        r"export const LOCK_TO_STEP[^{]*\{(.*?)\}", STEPS_TS.read_text(encoding="utf-8"), re.S,
    )
    assert block, "LOCK_TO_STEP not found"

    mapped = dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', block.group(1)))
    assert mapped == {
        voyage.LOCK_PROFILE: "entree",
        voyage.LOCK_PARCOURS: "parcours",
        voyage.LOCK_CONDITIONS: "conditions",
    }

    # The two with no step: a code comes from a counselor, an order is fixed by
    # playing. Neither is something a form can answer.
    assert voyage.LOCK_CODE not in mapped
    assert voyage.LOCK_ORDER not in mapped
