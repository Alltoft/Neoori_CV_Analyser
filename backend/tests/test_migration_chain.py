"""The revision graph has exactly one head.

Nothing else catches a fork: the test suite builds its schema with create_all(),
so a second head only surfaces at container start, where `flask db upgrade`
aborts with "Multiple head revisions are present" and keeps the backend down.
"""
import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"

_REVISION = re.compile(r"^revision(?::\s*str)?\s*=\s*['\"]([^'\"]+)", re.M)
_DOWN = re.compile(r"^down_revision(?::\s*[^=]+?)?\s*=\s*['\"]([^'\"]+)", re.M)


def _graph():
    revisions, parents = {}, set()
    for path in VERSIONS.glob("*.py"):
        text = path.read_text()
        found = _REVISION.search(text)
        if not found:
            continue
        revisions[found.group(1)] = path.name
        down = _DOWN.search(text)
        if down:
            parents.add(down.group(1))
    return revisions, parents


def test_exactly_one_head():
    revisions, parents = _graph()
    heads = sorted(name for rev, name in revisions.items() if rev not in parents)
    assert len(heads) == 1, f"expected one head, found {heads}"


def test_every_down_revision_resolves():
    revisions, parents = _graph()
    dangling = sorted(parent for parent in parents if parent not in revisions)
    assert not dangling, f"down_revision points at nothing: {dangling}"
