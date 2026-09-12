"""The counselor sheet's French labels are written twice — keep them honest.

`backend/app/services/voyage/bank.py` owns the scoring vocabulary. The API hands
it to the frontend as ASCII snake_case keys and bare axis ids (contracts § B.5),
so `frontend/src/lib/voyage-labels.ts` carries the accented French the counselor
manual prints. A drift there mislabels a column on the one page in the app
allowed to show scores at all — the counselor would read « Ouverture » over the
névrotisme figure and say the wrong thing out loud in a restitution.

Axes and RIASEC have real French in bank.py (AXES, RIASEC_UNIVERS), so those two
tests compare the parsed TS straight against it. BIG5, SDT, Schwartz, the four
cognitive styles and the S4 slots do not — bank.py carries only their ASCII
keys — so a key-only comparison cannot see a mislabelled column: swapping
"Ouverture" and "Névrotisme" in the TS left an earlier, key-only version of this
suite green. Each of those five tests therefore carries the expected French as
a literal, transcribed from `neoori_scoring_restitution-1.pdf`, and asserts the
parsed TS equals it exactly — key AND label, in order (phase-4 pre-flight
ruling R3).

scoring.py's three level words (Élevé / Moyen / Faible) are pinned the same way
below them — they have no home in bank.py either, and the counselor sheet reads
them as bare literals (ruling R4).

The last test is the other half of the job: spec decision 7 says the person
never sees a score, a trait name or a framework name, so this module may only be
imported by the counselor surface (ruling R5 — kept as a subset check, not
equality, until the counselor surface files exist).

There is no JS test runner in this repo, so this reads the TypeScript as text —
the same approach as test_conditions_parity.py.
"""
import re
from pathlib import Path

import pytest

from app.services.voyage import bank, scoring

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
LABELS_TS = FRONTEND / "lib" / "voyage-labels.ts"

# The only files allowed to import the counselor vocabulary.
COUNSELOR_SURFACE = {
    "app/voyage/c/[token]/page.tsx",
    "components/voyage/SynthesisSheet.tsx",
    "components/voyage/RiasecBars.tsx",
}


@pytest.fixture(scope="module")
def source() -> str:
    assert LABELS_TS.exists(), f"missing {LABELS_TS}"
    return LABELS_TS.read_text(encoding="utf-8")


def _block(source: str, name: str, end: str = "\n]") -> str:
    """The text of one exported const.

    Ends on the closing bracket that starts a line — the type annotations these
    consts carry (`{...}[] = [`) put a bracket ahead of the value itself.
    """
    start = source.index(f"export const {name}")
    return source[start : source.index(end, start)]


def _entries(block: str, *fields: str) -> list[tuple[str, ...]]:
    """Every `{ a: "…", b: "…" }` literal in a block, in file order."""
    pattern = r"\{\s*" + r",\s*".join(rf'{f}:\s*"([^"]+)"' for f in fields) + r"\s*\}"
    return re.findall(pattern, block)


def _record_keys(block: str) -> list[str]:
    """The keys of a `Record<string, string>` literal, in file order."""
    return re.findall(r'^\s+(\w+):\s*"', block, re.M)


def _record_entries(block: str) -> list[tuple[str, str]]:
    """The (key, value) pairs of a `Record<string, string>` literal, in file
    order — the label-carrying counterpart of `_record_keys`."""
    return re.findall(r'^\s+(\w+):\s*"([^"]+)"', block, re.M)


def test_the_ten_axes_match(source):
    rows = _entries(_block(source, "AXIS_ROWS"), "id", "label", "neg", "pos")
    assert [r[0] for r in rows] == list(bank.AXES)
    for axis_id, label, neg, pos in rows:
        axis = bank.AXES[axis_id]
        assert (label, neg, pos) == (axis["label"], axis["neg"], axis["pos"])


def test_the_six_riasec_universes_match(source):
    rows = _entries(_block(source, "RIASEC_ROWS"), "letter", "univers")
    assert [r[0] for r in rows] == list(bank.RIASEC_LETTERS)
    assert {letter: univers for letter, univers in rows} == bank.RIASEC_UNIVERS


# ── R3: bank.py has no French for these five groups, so key AND label are
# pinned as literals here, in order. ─────────────────────────────────────────

def test_the_five_big_five_labels_match(source):
    rows = _entries(_block(source, "BIG5_ROWS"), "key", "label")
    assert rows == [
        ("ouverture", "Ouverture"),
        ("conscienciosite", "Conscienciosité"),
        ("extraversion", "Extraversion"),
        ("agreabilite", "Agréabilité"),
        ("nevrotisme", "Névrotisme"),
    ]
    assert [r[0] for r in rows] == list(bank.BIG5)


def test_the_three_sdt_labels_match(source):
    rows = _entries(_block(source, "SDT_ROWS"), "key", "label")
    assert rows == [
        ("autonomie", "Autonomie"),
        ("appartenance", "Appartenance"),
        ("competence", "Compétence"),
    ]
    assert [r[0] for r in rows] == list(bank.SDT)


def test_the_eleven_schwartz_labels_match(source):
    rows = _record_entries(_block(source, "SCHWARTZ_LABELS", "\n}"))
    assert rows == [
        ("autodirection", "Auto-direction"),
        ("stimulation", "Stimulation"),
        ("hedonisme", "Hédonisme"),
        ("reussite", "Réussite"),
        ("pouvoir", "Pouvoir"),
        ("securite", "Sécurité"),
        ("conformite", "Conformité"),
        ("bienveillance", "Bienveillance"),
        ("universalisme", "Universalisme"),
        ("integrite", "Intégrité"),
        ("conservation", "Conservation"),
    ]
    assert [r[0] for r in rows] == list(bank.SCHWARTZ)


def test_the_four_style_labels_match(source):
    rows = _record_entries(_block(source, "STYLE_LABELS", "\n}"))
    assert rows == [
        ("holistique", "Holistique"),
        ("sequentiel", "Séquentiel"),
        ("adaptatif", "Adaptatif"),
        ("consultatif", "Consultatif"),
    ]
    assert [r[0] for r in rows] == list(bank.STYLES)


def test_the_six_environment_slots_match(source):
    """S4_ROWS is not in bank.S4_SLOTS order: the manual's box only has room
    for four cells (S4-1/2/3/5), so the TS prints those first and the other two
    (manager, vendredi) after — see the const's own docstring. Order here is
    therefore pinned against the literal, not against bank.S4_SLOTS, which
    only backs the set-equality check on the last line."""
    rows = _entries(_block(source, "S4_ROWS"), "key", "label")
    assert rows == [
        ("espace", "Espace physique idéal (S4-1)"),
        ("rythme", "Rythme & chronotype (S4-2)"),
        ("equipe", "Configuration d'équipe (S4-3)"),
        ("irritant", "Ce qui épuise (S4-5)"),
        ("manager", "Le manager idéal (S4-4)"),
        ("vendredi", "Le vendredi soir (S4-6)"),
    ]
    assert sorted(r[0] for r in rows) == sorted(bank.S4_SLOTS)


# ── R4: the level words live in scoring.py, not bank.py. ─────────────────────

def test_the_level_words_match_scoring(source):
    """« Élevé / Moyen / Faible » — the counselor sheet compares S3Score.levels
    against these as bare literals (e.g. `highLevel("Élevé")`), so pin them
    here against their one source of truth."""
    levels = dict(re.findall(r'export const (LEVEL_\w+) = "([^"]+)"', source))
    assert levels == {
        "LEVEL_HIGH": scoring.LEVEL_HIGH,
        "LEVEL_MID": scoring.LEVEL_MID,
        "LEVEL_LOW": scoring.LEVEL_LOW,
    }


def test_the_vocabulary_never_leaves_the_counselor_surface():
    """Spec decision 7 — the person never sees a trait name or a framework name.

    R5: kept as a subset check (`<=`), not equality. None of the three
    counselor-surface files exist yet (they land in later phase-4 batches), so
    an equality check would fail today for a reason unrelated to a leak. Task
    13 tightens this to `==` once all three exist, which also catches an
    unused fourth import.
    """
    importers = sorted(
        path.relative_to(FRONTEND).as_posix()
        for path in FRONTEND.rglob("*.ts*")
        if "voyage-labels" in path.read_text(encoding="utf-8")
        and path != LABELS_TS
    )
    assert set(importers) <= COUNSELOR_SURFACE, (
        "voyage-labels.ts is imported outside the counselor surface: "
        f"{sorted(set(importers) - COUNSELOR_SURFACE)}"
    )
