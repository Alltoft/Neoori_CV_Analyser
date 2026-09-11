"""The voyage's lock reasons, portrait section titles and two numeric twins
are written twice — keep the two copies honest.

`backend/app/models/voyage.py` owns LOCK_CODE / LOCK_PROFILE / LOCK_ORDER and
`backend/app/services/voyage/generation.py` owns PORTRAIT_TITLES.
`frontend/src/types/voyage.ts` mirrors both: the hub renders a locked card's
reason client-side (sessionLock()) before the server ever answers, and the
candidate portrait page + counselor editor need the six section headings the
API does not send. A drift between the two files is silent: the wrong string
renders in French and nothing throws.

Two numeric constants are mirrored the same way, silently:
`backend/app/routes/voyage.py` BILLET_MAX_CHARS is the server's hard cap on a
billet field, and `frontend/src/components/voyage/BilletForm.tsx` mirrors it
as the Textarea's `maxLength` so the field stops accepting input at the same
length the server would refuse. And `MICRO_RETRY_STALE_MINUTES` (backend,
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
from app.services.voyage import generation

VOYAGE_TS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "voyage.ts"
)
BILLET_FORM_TS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "components"
    / "voyage" / "BilletForm.tsx"
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
def billet_form_source() -> str:
    assert BILLET_FORM_TS.exists(), f"missing {BILLET_FORM_TS}"
    return BILLET_FORM_TS.read_text(encoding="utf-8")


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


def test_billet_max_chars_matches(billet_form_source):
    """The Textarea's `maxLength` must stop input at the same length the
    server refuses, or a person can type past what will save."""
    fe = _ts_int_const(billet_form_source, "BILLET_MAX_CHARS", BILLET_FORM_TS)
    assert fe == voyage_routes.BILLET_MAX_CHARS


def test_micro_retry_stale_ms_matches_poll_max_ms(voyage_page_source):
    """The hub must not give up polling a generating phrase before the
    server itself would accept a retry — otherwise "Réessayer" can appear
    while the hub is still silently about to receive the very phrase it is
    offering to relaunch."""
    poll_max_ms = _ts_int_const(voyage_page_source, "POLL_MAX_MS", VOYAGE_PAGE_TS)
    assert poll_max_ms == voyage_routes.MICRO_RETRY_STALE_MINUTES * 60 * 1000
