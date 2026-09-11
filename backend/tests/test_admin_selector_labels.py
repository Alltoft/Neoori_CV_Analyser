"""The admin prompt selector's French labels are a copy. Keep it honest.

`prompt_slots.LABELS` owns the vocabulary, and `prompt_slots.choices()` exists
to serve it — but nothing consumes it: there is no endpoint behind it, so the
Next.js page hard-codes the same five strings in `SLOT_LABEL`. Two copies that
agree today drift tomorrow, and the drift is invisible: the page keeps
rendering, the API keeps accepting the slot, and the PM edits a prompt under a
name the backend no longer uses.

This module is the only thing standing between the two copies. It reads the
page source as text — the backend has no way to run TypeScript — and fails if a
label is changed on either side, or if a slot stops being offered at all.

It parses `SLOT_LABEL` rather than asking whether each backend label merely
*appears* somewhere in the file: substring containment cannot see a label that
grew a suffix ("Voyage · portrait" → "Voyage · portrait complet" contains the
original), and that is exactly the kind of edit a copy-editing pass makes.

If you are here because this failed: the fix is to edit *both*
`backend/app/services/prompt_slots.py` and
`frontend/src/app/admin/prompts/page.tsx`, not to loosen the assertion.
"""
import re
from pathlib import Path

from app.services import prompt_slots

REPO = Path(__file__).resolve().parents[2]
PAGE = REPO / "frontend" / "src" / "app" / "admin" / "prompts" / "page.tsx"

# `const SLOTS: PromptSlot[] = ["1", ...]` — the array the selector maps over.
_SLOTS_RE = re.compile(r"const SLOTS: PromptSlot\[\] = \[(?P<body>[^\]]*)\]")

# `const SLOT_LABEL: Record<PromptSlot, string> = { ... }`, up to the closing
# brace in column 0.
_LABEL_MAP_RE = re.compile(
    r"const SLOT_LABEL: Record<PromptSlot, string> = \{(?P<body>.*?)\n\}",
    re.DOTALL,
)

# One `key: "value",` entry. Keys are quoted when numeric, bare otherwise.
_ENTRY_RE = re.compile(r'^\s*"?(?P<key>[A-Za-z0-9_]+)"?:\s*"(?P<label>[^"]*)",\s*$')


def _page_source() -> str:
    """The selector's source. A missing file is a failure, never a skip —
    a skip would silently retire the only guard the two copies have."""
    assert PAGE.is_file(), f"admin selector not found at {PAGE}"
    return PAGE.read_text(encoding="utf-8")


def _selector_labels() -> dict:
    match = _LABEL_MAP_RE.search(_page_source())
    assert match, "could not find `const SLOT_LABEL: Record<PromptSlot, string>`"
    labels = {}
    for line in match.group("body").splitlines():
        if not line.strip():
            continue
        entry = _ENTRY_RE.match(line)
        assert entry, f"unparsable SLOT_LABEL entry: {line!r}"
        labels[entry.group("key")] = entry.group("label")
    return labels


def test_the_admin_selector_carries_prompt_slots_labels_verbatim():
    """Byte-identical per slot, middle dot and apostrophe included."""
    assert _selector_labels() == prompt_slots.LABELS


def test_the_selector_offers_every_slot():
    """A label the chip array never renders is a slot the PM cannot reach."""
    match = _SLOTS_RE.search(_page_source())
    assert match, "could not find `const SLOTS: PromptSlot[] = [...]` in the page"
    rendered = tuple(re.findall(r'"([^"]+)"', match.group("body")))
    assert rendered == prompt_slots.valid()
