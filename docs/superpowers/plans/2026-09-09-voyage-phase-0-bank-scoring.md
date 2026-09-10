# Le voyage — Phase 0: Question bank + scoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the voyage's question bank (53 scored items, verbatim French) and its deterministic scoring engine as pure Python, fully unit-tested, with no database, no network and no UI.

**Architecture:** Two modules under a new `backend/app/services/voyage/` package. `bank.py` is data: the six sessions with every item's literal French text plus the scoring tags transcribed from the counselor manual, and a `public()` view that strips every weight. `scoring.py` is arithmetic: five per-session scorers, a `synthesize()` that assembles the counselor's synthesis sheet, and a `prompt_context()` that reduces that sheet to plain French lines with no numbers and no framework vocabulary. Nothing here imports Flask or SQLAlchemy, so every test runs in milliseconds against plain dicts.

**Tech Stack:** Python 3, pytest 8.3.4 (already in `backend/requirements.txt`), no new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-09-voyage-design.md`
**Contracts:** `docs/superpowers/plans/2026-09-09-voyage-contracts.md` — sections **A** (bank) and **B** (scoring) are binding for every name, key and shape in this plan.

## Global Constraints

- App UI strings are **French**. Code comments and commit messages are **English**. (`CLAUDE.md`)
- Copy ban list, never in user-facing French text: **boussole, copilote, miroir, révélation, épanouissement, alignement, excellence, talent unique, vous vous démarquez**.
- The candidate **never** sees a score, a trait name, an axis name or a framework name. In this phase that rule is carried by `bank.public()` and by `scoring.prompt_context()`; both have tests that assert it.
- Everything in `bank.py` marked *verbatim* is copied character for character from the PDF text extraction. Do not paraphrase, do not fix the PM's punctuation, do not convert `…` to `...` or `'` to `'`.
- `scoring.py` imports **only** `bank`. No DB, no I/O, no Flask, and it never mutates `bank.SESSIONS`.
- Tests run from `backend/`: `pytest`. Config is `backend/pytest.ini` (`testpaths = tests`, `pythonpath = .`).
- Python 3 tuple-typed data (`list[tuple[str, int]]`) is used in the bank; after a JSON round-trip those become lists, which is why `public()` is tested on the **JSON-serialised** payload.
- This phase adds **no** migration, **no** route, **no** model, **no** frontend file. It is invisible to the running app and safe to deploy alone.

---

## Source material

Two PDFs at the repo root are the source of truth. Plain-text extractions already exist — read those, do not re-extract:

| Source | Extraction | Supplies |
|---|---|---|
| `neoori_cahier_papier.pdf` | `/private/tmp/claude-501/-Users-imran-Downloads-design-handoff-cv-analyzer/ca172e29-6890-4ffa-aef3-1c38e9ade8e9/scratchpad/cahier.txt` | every session's title, subtitle, intro, narrative, question, option text, billet labels |
| `neoori_scoring_restitution-1.pdf` | `.../scratchpad/scoring.txt` | every option's `label` and its scoring tags (the *Option* and *Dimension* / *Points attribués* columns) |

If an extraction file is missing, regenerate it:

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
pdftotext -layout neoori_cahier_papier.pdf /tmp/cahier.txt
pdftotext -layout neoori_scoring_restitution-1.pdf /tmp/scoring.txt
```

Every literal string in this plan has already been transcribed from those extractions. **Type what this plan shows.** Consult the extraction only to resolve a doubt, never as a substitute for the text here.

---

## File Structure

| Action | Path | Single responsibility |
|---|---|---|
| Create | `backend/app/services/voyage/__init__.py` | Package marker. Empty. |
| Create | `backend/app/services/voyage/bank.py` | The 6 sessions, 53 items, 10 axes, their weights, and the lookup + `public()` helpers. Data plus pure accessors, nothing else. |
| Create | `backend/app/services/voyage/scoring.py` | Arithmetic over a `responses` dict: 5 scorers, `synthesize()`, `prompt_context()`, completeness helpers. |
| Create | `backend/tests/test_voyage_bank.py` | Bank integrity: counts, id formats, tag vocabulary, computed RIASEC maxima, `public()` leaks nothing. |
| Create | `backend/tests/test_voyage_scoring.py` | Scoring behaviour: signs, tension band, the A1 exclusion, ties as lists, incomplete sessions, `prompt_context()` invariants. |

`bank.py` is large (~1100 lines) because it holds 53 items of literal French. That is data, not logic, and splitting it per session would scatter one table across six files for no gain. `scoring.py` stays under ~400 lines.

---

## Task 1: Package skeleton and module constants

**Files:**
- Create: `backend/app/services/voyage/__init__.py`
- Create: `backend/app/services/voyage/bank.py`
- Test: `backend/tests/test_voyage_bank.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SCORING_VERSION`, `SESSION_IDS`, `KIND_CHECKLIST`, `KIND_SCENES`, `TAG_KEYS`, `PUBLIC_STRIP`, `RIASEC_LETTERS`, `RIASEC_UNIVERS`, `SDT`, `SCHWARTZ`, `BIG5`, `STYLES`, `STYLE_PLAIN`, `RISK_LEVELS`, `S4_SLOTS` — all from contract § A.1.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_voyage_bank.py`:

```python
"""Bank integrity — the 53 items, their weights, and what public() must not leak.

The bank is the one place where a transcription slip produces wrong software
that still runs: every option would still render, every score would still add
up, and the portrait would simply be about a different person. These tests are
the transcription's proof.
"""
import json

from app.services.voyage import bank


def test_module_constants():
    assert bank.SCORING_VERSION == "cahier-2026-09"
    assert bank.SESSION_IDS == ("0", "1", "2", "3", "4", "5")
    assert bank.KIND_CHECKLIST == "checklist"
    assert bank.KIND_SCENES == "scenes"
    assert bank.RIASEC_LETTERS == ("R", "I", "A", "S", "E", "C")
    assert set(bank.RIASEC_UNIVERS) == set(bank.RIASEC_LETTERS)
    assert bank.SDT == ("autonomie", "appartenance", "competence")
    assert len(bank.SCHWARTZ) == 11
    assert bank.BIG5 == (
        "ouverture", "conscienciosite", "extraversion", "agreabilite", "nevrotisme",
    )
    assert bank.STYLES == ("holistique", "sequentiel", "adaptatif", "consultatif")
    assert set(bank.STYLE_PLAIN) == set(bank.STYLES)
    assert bank.RISK_LEVELS == ("Fort", "Modéré", "Calculé", "Faible")
    assert bank.S4_SLOTS == (
        "espace", "rythme", "equipe", "manager", "irritant", "vendredi",
    )


def test_public_strip_covers_every_tag_key_plus_plain():
    """`plain` is prompt-facing, not UI-facing — it must be stripped too."""
    assert set(bank.PUBLIC_STRIP) == set(bank.TAG_KEYS) | {"plain"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_bank.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.voyage'`

- [ ] **Step 3: Create the package and write the constants**

Create `backend/app/services/voyage/__init__.py` as an **empty file**:

```bash
: > backend/app/services/voyage/__init__.py
```

Create `backend/app/services/voyage/bank.py`:

```python
"""The voyage's question bank — text and weights in one place.

Six sessions, 53 scored items. Every item's French text is transcribed verbatim
from `neoori_cahier_papier.pdf`; every option's scoring tags come from the
counselor manual `neoori_scoring_restitution-1.pdf`.

Text and weights live together on purpose. They were authored together on paper
and they drift apart the moment they are split: an option whose wording is edited
in one file and whose points sit in another is a silent scoring bug. `public()`
is what keeps the weights server-side — it strips them, so the API can serve this
same structure without leaking the mapping the product is built on.

Pure data plus lookups. No DB, no I/O, no Flask import.
"""

SCORING_VERSION = "cahier-2026-09"

SESSION_IDS = ("0", "1", "2", "3", "4", "5")

KIND_CHECKLIST = "checklist"
KIND_SCENES = "scenes"

# Every key that carries a weight or an interpretation.
TAG_KEYS = ("riasec", "axes", "sdt", "schwartz", "big5", "style", "env", "risk", "sens")

# `plain` is the prompt-facing paraphrase of an option. It is not a weight, but it
# is not for the browser either — it is written for the model, in a register the
# UI never uses. public() strips it with the rest.
PUBLIC_STRIP = TAG_KEYS + ("plain",)

# Tie-break order for RIASEC, in this order.
RIASEC_LETTERS = ("R", "I", "A", "S", "E", "C")

RIASEC_UNIVERS = {
    "R": "Réaliste",
    "I": "Investigateur",
    "A": "Artistique",
    "S": "Social",
    "E": "Entreprenant",
    "C": "Conventionnel",
}

SDT = ("autonomie", "appartenance", "competence")

# Exactly the eleven values the counselor manual's Dimension column uses. Two of
# them — conservation, integrite — are not canonical Schwartz basic values; they
# are the manual's own vocabulary and the counselor sheet has to match the paper
# it replaces. A twelfth value appearing here is a bank bug.
SCHWARTZ = (
    "autodirection", "stimulation", "hedonisme", "reussite", "pouvoir", "securite",
    "conformite", "bienveillance", "universalisme", "integrite", "conservation",
)

BIG5 = ("ouverture", "conscienciosite", "extraversion", "agreabilite", "nevrotisme")

STYLES = ("holistique", "sequentiel", "adaptatif", "consultatif")

# What the prompt is allowed to say instead of the tag.
STYLE_PLAIN = {
    "holistique": "part de l'ensemble et improvise",
    "sequentiel": "avance par étapes structurées",
    "adaptatif": "ajuste sa méthode au contexte",
    "consultatif": "s'appuie sur les autres pour décider",
}

# S5-1 only. The manual's own casing.
RISK_LEVELS = ("Fort", "Modéré", "Calculé", "Faible")

# S4-1 -> espace, S4-2 -> rythme, S4-3 -> equipe, S4-4 -> manager,
# S4-5 -> irritant, S4-6 -> vendredi. Position in the session, not a tag.
S4_SLOTS = ("espace", "rythme", "equipe", "manager", "irritant", "vendredi")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_bank.py -v`
Expected: PASS — 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/__init__.py backend/app/services/voyage/bank.py backend/tests/test_voyage_bank.py
git commit -m "feat(voyage): the bank's scoring vocabulary"
```

---

## Task 2: The ten bipolar axes

**Files:**
- Modify: `backend/app/services/voyage/bank.py` (append after `S4_SLOTS`)
- Test: `backend/tests/test_voyage_bank.py` (append)

**Interfaces:**
- Consumes: nothing.
- Produces: `AXES: dict[str, dict[str, str]]` — ten keys `A1`…`A10`, each with exactly the six keys `label`, `neg`, `pos`, `plain_neg`, `plain_pos`, `tension`.

The `label` / `neg` / `pos` triple is the counselor manual's own wording and appears only on the counselor's synthesis sheet. The `plain_neg` / `plain_pos` / `tension` triple is plain French with no framework word in it, and is the only form that ever reaches a prompt or the `_voyage` block. Keeping both on one object is what lets `prompt_context()` be pure over the synthesis — it never has to decide which register it is in.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_bank.py`:

```python
AXIS_KEYS = {"label", "neg", "pos", "plain_neg", "plain_pos", "tension"}


def test_axes_shape():
    assert list(bank.AXES) == [f"A{i}" for i in range(1, 11)]
    for axis_id, axis in bank.AXES.items():
        assert set(axis) == AXIS_KEYS, axis_id
        for key, value in axis.items():
            assert isinstance(value, str) and value.strip(), f"{axis_id}.{key}"


def test_plain_axis_wording_never_names_a_framework():
    """plain_* and tension reach the prompt. label/neg/pos never do."""
    banned = ("axe", "score", "riasec", "schwartz", "big five", "névrotisme")
    for axis_id, axis in bank.AXES.items():
        for key in ("plain_neg", "plain_pos", "tension"):
            lowered = axis[key].lower()
            for word in banned:
                assert word not in lowered, f"{axis_id}.{key} contains {word!r}"


def test_tension_wording_is_a_versus_pair():
    for axis_id, axis in bank.AXES.items():
        assert " vs " in axis["tension"], axis_id
        assert axis["tension"] == axis["tension"].lower(), axis_id


def test_axis_lookup():
    assert bank.axis("A9")["label"] == "Rapport au corps"
    import pytest
    with pytest.raises(KeyError):
        bank.axis("A99")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_bank.py -v`
Expected: FAIL — `AttributeError: module 'app.services.voyage.bank' has no attribute 'AXES'`

- [ ] **Step 3: Write AXES and its accessor**

Append to `backend/app/services/voyage/bank.py`:

```python
# ── The ten S0 bipolar axes ──────────────────────────────────────────────────
# label / neg / pos are the counselor manual's wording and appear only on the
# counselor's synthesis sheet. plain_neg / plain_pos / tension are plain French
# with no framework word in them, and are the only form that reaches a prompt or
# the _voyage block — see scoring.prompt_context(), which is pure over these.
AXES: dict[str, dict[str, str]] = {
    "A1": {
        "label": "Mobilité territoriale",
        "neg": "Ancrage local",
        "pos": "Mobilité / international",
        "plain_neg": "rester près de chez elle",
        "plain_pos": "bouger, voir d'autres pays",
        "tension": "ancrage vs mobilité",
    },
    "A2": {
        "label": "Visibilité",
        "neg": "Discrétion",
        "pos": "Reconnaissance publique",
        "plain_neg": "travailler dans l'ombre",
        "plain_pos": "être reconnue publiquement",
        "tension": "discrétion vs reconnaissance",
    },
    "A3": {
        "label": "Rapport au collectif",
        "neg": "Indépendance / solo",
        "pos": "Collectif / équipe",
        "plain_neg": "travailler seule",
        "plain_pos": "travailler en équipe",
        "tension": "solo vs collectif",
    },
    "A4": {
        "label": "Échelle d'impact",
        "neg": "Impact local",
        "pos": "Impact global / systémique",
        "plain_neg": "compter pour les gens autour d'elle",
        "plain_pos": "un impact visible",
        "tension": "impact local vs impact global",
    },
    "A5": {
        "label": "Sécurité vs risque",
        "neg": "Stabilité / salariat",
        "pos": "Risque / entrepreneuriat",
        "plain_neg": "un cadre stable",
        "plain_pos": "prendre des risques",
        "tension": "sécurité vs risque",
    },
    "A6": {
        "label": "Type de création",
        "neg": "Organisation / méthode",
        "pos": "Expression libre",
        "plain_neg": "organiser et planifier",
        "plain_pos": "créer librement",
        "tension": "méthode vs expression libre",
    },
    "A7": {
        "label": "Nature du lien",
        "neg": "Systèmes / idées",
        "pos": "Lien humain direct",
        "plain_neg": "les systèmes et les idées",
        "plain_pos": "le lien avec les gens",
        "tension": "idées vs personnes",
    },
    "A8": {
        "label": "Temporalité de l'impact",
        "neg": "Long terme / différé",
        "pos": "Impact immédiat / visible",
        "plain_neg": "construire sur la durée",
        "plain_pos": "voir le résultat tout de suite",
        "tension": "impact différé vs impact immédiat",
    },
    "A9": {
        "label": "Rapport au corps",
        "neg": "Sédentaire / bureau",
        "pos": "Terrain / action physique",
        "plain_neg": "le bureau et la réflexion",
        "plain_pos": "le terrain et l'action",
        "tension": "bureau vs terrain",
    },
    "A10": {
        "label": "Transmission vs expertise",
        "neg": "Expertise individuelle",
        "pos": "Transmission / enseigner",
        "plain_neg": "maîtriser un domaine",
        "plain_pos": "transmettre",
        "tension": "expertise vs transmission",
    },
}


def axis(axis_id: str) -> dict:
    """One axis. Raises KeyError on an unknown id — a caller asking for an axis
    that doesn't exist has a bug, and returning None would hide it."""
    return AXES[axis_id]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_bank.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/bank.py backend/tests/test_voyage_bank.py
git commit -m "feat(voyage): the ten bipolar axes, in both registers"
```

---

## Task 3: Session 0 — the 20 affirmations

**Files:**
- Modify: `backend/app/services/voyage/bank.py` (append)
- Test: `backend/tests/test_voyage_bank.py` (append)

**Interfaces:**
- Consumes: `AXES` (task 2).
- Produces: `SESSIONS` (first entry only, `"0"`); the checklist item shape `{"id", "text", "axes"}`.

Session 0 is the only `KIND_CHECKLIST` session and the only place the `axes` tag appears. Each item's sign is per *(axis, item)* pair, not per item: `S0-20` loads `A4` negatively and `A7` positively, because being useful to your local community pushes the impact axis toward *local* while still being about the human bond.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_bank.py`:

```python
def _session(n):
    return next(s for s in bank.SESSIONS if s["n"] == n)


def test_session_0_header_and_counts():
    s0 = _session("0")
    assert s0["title"] == "Dans 10 ans"
    assert s0["subtitle"] == "Ta vision instinctive — 20 affirmations"
    assert s0["duration"] == "5 min"
    assert s0["kind"] == bank.KIND_CHECKLIST
    assert len(s0["items"]) == 20
    assert [b["key"] for b in s0["billet"]] == ["top3", "surprise"]


def test_session_0_item_ids_are_zero_padded():
    ids = [i["id"] for i in _session("0")["items"]]
    assert ids == [f"S0-{n:02d}" for n in range(1, 21)]


def test_session_0_axis_loadings():
    """The complete map, from the manual's 'Axe(s) principal(aux)' column."""
    expected = {
        "S0-01": [("A9", 1)],
        "S0-02": [("A2", 1), ("A5", 1)],
        "S0-03": [("A7", 1)],
        "S0-04": [("A2", 1), ("A4", 1)],
        "S0-05": [("A6", 1), ("A9", 1)],
        "S0-06": [("A6", 1), ("A8", 1)],
        "S0-07": [("A6", 1)],
        "S0-08": [("A1", 1)],
        "S0-09": [("A7", 1), ("A10", 1)],
        "S0-10": [("A5", 1), ("A6", 1)],
        "S0-11": [("A5", -1)],
        "S0-12": [("A2", 1), ("A4", 1)],
        "S0-13": [("A3", -1)],
        "S0-14": [("A3", 1)],
        "S0-15": [("A4", 1)],
        "S0-16": [("A8", 1), ("A10", 1)],
        "S0-17": [("A6", -1)],
        "S0-18": [("A7", 1)],
        "S0-19": [("A5", 1)],
        "S0-20": [("A4", -1), ("A7", 1)],
    }
    actual = {i["id"]: i["axes"] for i in _session("0")["items"]}
    assert actual == expected


def test_session_0_axis_item_counts():
    """A1 has exactly one item — that is why TENSION_MIN_ITEMS exists."""
    counts = {a: len(bank.axis_items(a)) for a in bank.AXES}
    assert counts == {
        "A1": 1, "A2": 3, "A3": 2, "A4": 4, "A5": 4,
        "A6": 5, "A7": 4, "A8": 2, "A9": 2, "A10": 2,
    }


def test_session_0_items_are_well_formed():
    for item in _session("0")["items"]:
        assert set(item) == {"id", "text", "axes"}
        assert item["text"].strip()
        assert item["axes"]
        seen = set()
        for axis_id, sign in item["axes"]:
            assert axis_id in bank.AXES
            assert sign in (1, -1)
            assert axis_id not in seen, f"{item['id']} loads {axis_id} twice"
            seen.add(axis_id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_bank.py -v`
Expected: FAIL — `AttributeError: module 'app.services.voyage.bank' has no attribute 'SESSIONS'`

- [ ] **Step 3: Write session 0 and `axis_items`**

Append to `backend/app/services/voyage/bank.py`:

```python
# ── The six sessions ─────────────────────────────────────────────────────────
# Text is verbatim from neoori_cahier_papier.pdf. Tags are from the counselor
# manual. Session order is the play order; item order within a session is the
# order they appear on paper.

_SESSION_0 = {
    "n": "0",
    "title": "Dans 10 ans",
    "subtitle": "Ta vision instinctive — 20 affirmations",
    "intro": [
        "Dans 10 ans, tout s'est passé comme tu l'espérais. Tu travailles. "
        "Pas parce que tu le dois — mais parce que tu le veux. "
        "À quoi ressemble ta vie ?",
        "Pour chaque affirmation : coche ✓ si ça te parle, ✗ si ce n'est pas toi.",
        "Fais confiance à ton premier ressenti. Pas de réflexion — instinctif.",
    ],
    "outro": [],
    "duration": "5 min",
    "kind": KIND_CHECKLIST,
    "items": [
        {"id": "S0-01", "text": "Travailler dehors, sur le terrain, en mouvement",
         "axes": [("A9", 1)]},
        {"id": "S0-02", "text": "Avoir mes propres horaires, travailler à mon rythme",
         "axes": [("A2", 1), ("A5", 1)]},
        {"id": "S0-03", "text": "Aider des personnes au quotidien",
         "axes": [("A7", 1)]},
        {"id": "S0-04", "text": "Diriger une équipe ou une entreprise",
         "axes": [("A2", 1), ("A4", 1)]},
        {"id": "S0-05", "text": "Créer des choses avec mes mains (objets, bâtiments...)",
         "axes": [("A6", 1), ("A9", 1)]},
        {"id": "S0-06", "text": "Analyser, comprendre, résoudre des problèmes complexes",
         "axes": [("A6", 1), ("A8", 1)]},
        {"id": "S0-07", "text": "Créer des contenus, des images, de la musique, du texte",
         "axes": [("A6", 1)]},
        {"id": "S0-08", "text": "Voyager, travailler dans plusieurs pays ou villes",
         "axes": [("A1", 1)]},
        {"id": "S0-09", "text": "Enseigner, transmettre, former",
         "axes": [("A7", 1), ("A10", 1)]},
        {"id": "S0-10", "text": "Innover, créer un projet qui n'existe pas encore",
         "axes": [("A5", 1), ("A6", 1)]},
        {"id": "S0-11", "text": "Avoir un emploi stable avec un salaire régulier",
         "axes": [("A5", -1)]},
        {"id": "S0-12", "text": "Être connu(e), avoir une visibilité publique",
         "axes": [("A2", 1), ("A4", 1)]},
        {"id": "S0-13", "text": "Travailler seul(e) sur des projets indépendants",
         "axes": [("A3", -1)]},
        {"id": "S0-14", "text": "Travailler en grande équipe, beaucoup d'interactions",
         "axes": [("A3", 1)]},
        {"id": "S0-15", "text": "Avoir un impact visible sur la société ou le monde",
         "axes": [("A4", 1)]},
        {"id": "S0-16", "text": "Maîtriser un domaine technique pointu",
         "axes": [("A8", 1), ("A10", 1)]},
        {"id": "S0-17", "text": "Organiser, planifier, gérer des projets",
         "axes": [("A6", -1)]},
        {"id": "S0-18", "text": "Travailler dans le secteur du soin ou du social",
         "axes": [("A7", 1)]},
        {"id": "S0-19", "text": "Gagner beaucoup d'argent",
         "axes": [("A5", 1)]},
        {"id": "S0-20", "text": "Être utile à ma communauté locale",
         "axes": [("A4", -1), ("A7", 1)]},
    ],
    "billet": [
        {"key": "top3", "label": "Les 3 affirmations qui m'ont le plus parlé :"},
        {"key": "surprise", "label": "Quelque chose qui m'a surpris(e) dans mes réponses :"},
    ],
}
```

Then, at the very end of the file for now (later tasks insert the other five sessions before it):

```python
SESSIONS: list[dict] = [_SESSION_0]


def axis_items(axis_id: str) -> list[tuple[str, int]]:
    """Every S0 item loading on this axis, as (item_id, sign) in item order."""
    out = []
    for item in _SESSION_0["items"]:
        for loaded_axis, sign in item["axes"]:
            if loaded_axis == axis_id:
                out.append((item["id"], sign))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_bank.py -v`
Expected: PASS — 11 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/bank.py backend/tests/test_voyage_bank.py
git commit -m "feat(voyage): session 0, the twenty affirmations"
```

---

## Task 4: Session 1 — the six childhood scenes and the RIASEC map

**Files:**
- Modify: `backend/app/services/voyage/bank.py` (insert `_SESSION_1` before `SESSIONS`, add `"1"` to the list)
- Test: `backend/tests/test_voyage_bank.py` (append)

**Interfaces:**
- Consumes: `KIND_SCENES`, `RIASEC_LETTERS` (task 1).
- Produces: `_SESSION_1`; the scene item shape `{"id", "title", "subtitle", "narrative", "question", "options"}` and the option shape `{"letter", "label", "text", "plain", + tags}`.

Session 1 is the only session where the `riasec` tag is mandatory on every option, and it is the only input to `riasec_maxima()`. Scene `S1-6` is the only eight-option scene; the other five have six. Get the points wrong here and every portrait names the wrong universes, with nothing failing.

`label` comes from the counselor manual's *Option* column ("Architectes", "Bâtisseurs"…). `text` is the cahier's descriptive line. `plain` is authored: lowercase, second person, what the prompt is allowed to say the person chose.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_bank.py`:

```python
import pytest

SCENE_KEYS = {"id", "title", "subtitle", "narrative", "question", "options"}
OPTION_MANDATORY = {"letter", "label", "text", "plain"}


@pytest.mark.parametrize("n", ["1", "2", "3", "4", "5"])
def test_scene_sessions_are_well_formed(n):
    session = _session(n)
    assert session["kind"] == bank.KIND_SCENES
    for scene in session["items"]:
        assert set(scene) == SCENE_KEYS, scene["id"]
        assert scene["id"].startswith(f"S{n}-")
        assert scene["title"].strip() and scene["subtitle"].strip()
        assert scene["question"].strip()
        assert isinstance(scene["narrative"], list)
        assert 4 <= len(scene["options"]) <= 8, scene["id"]
        letters = [o["letter"] for o in scene["options"]]
        assert letters == sorted(letters), scene["id"]
        assert len(set(letters)) == len(letters), scene["id"]
        for option in scene["options"]:
            assert OPTION_MANDATORY <= set(option), f"{scene['id']}{option['letter']}"
            extra = set(option) - OPTION_MANDATORY
            assert extra, f"{scene['id']}{option['letter']} carries no tag"
            assert extra <= set(bank.TAG_KEYS), f"{scene['id']}{option['letter']}: {extra}"
            assert option["plain"] == option["plain"].lower() or "'" in option["plain"]


def test_session_1_header_and_scene_ids():
    s1 = _session("1")
    assert s1["title"] == "Ce que tu faisais naturellement"
    assert s1["subtitle"] == "Là où tout a commencé… · 6 scènes de ton enfance"
    assert s1["duration"] == "15–20 min"
    assert [i["id"] for i in s1["items"]] == [f"S1-{k}" for k in range(1, 7)]
    assert [b["key"] for b in s1["billet"]] == ["cabane", "jeu", "fierte", "regard"]


def test_session_1_every_option_carries_riasec():
    for scene in _session("1")["items"]:
        for option in scene["options"]:
            assert "riasec" in option, f"{scene['id']}{option['letter']}"
            for letter, points in option["riasec"].items():
                assert letter in bank.RIASEC_LETTERS
                assert points in (1, 2), f"{scene['id']}{option['letter']}"


def test_session_1_scene_shapes():
    """S1-6 is the only eight-option scene."""
    counts = {s["id"]: len(s["options"]) for s in _session("1")["items"]}
    assert counts == {"S1-1": 6, "S1-2": 6, "S1-3": 6, "S1-4": 6, "S1-5": 6, "S1-6": 8}


def test_riasec_maxima_are_computed_not_copied():
    """The manual prints E 10 / C 10. Summing the best option per scene gives
    E 11 / C 9 — the manual's two transcription slips (spec errata 17b)."""
    assert bank.riasec_maxima() == {"R": 12, "I": 11, "A": 10, "S": 10, "E": 11, "C": 9}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_bank.py -v`
Expected: FAIL — `StopIteration` from `_session("1")` (no session with `n == "1"` yet)

- [ ] **Step 3: Write session 1**

Insert into `backend/app/services/voyage/bank.py`, immediately before the `SESSIONS` list:

```python
_SESSION_1 = {
    "n": "1",
    "title": "Ce que tu faisais naturellement",
    "subtitle": "Là où tout a commencé… · 6 scènes de ton enfance",
    "intro": [
        "Bienvenue dans cette session.",
        "Aujourd'hui, on remonte plus loin. Bien plus loin. "
        "On retourne dans ta cour d'école. "
        "L'époque où quelque chose, déjà, te branchait. "
        "Où tu étais naturellement, sans réfléchir.",
        "Je vais te décrire 6 scènes de vie. Pour chacune, une question simple : "
        "quelle était TA place là-dedans ?",
    ],
    "outro": [
        "Voilà. Tu viens de poser les 6 premières pierres de ton portrait Neoori.",
        "Ce que tu as choisi, ce ne sont pas des réponses à un questionnaire. "
        "Ce sont des empreintes. Des traces laissées par ton fonctionnement naturel.",
    ],
    "duration": "15–20 min",
    "kind": KIND_SCENES,
    "items": [
        {
            "id": "S1-1",
            "title": "La cabane",
            "subtitle": "Ce que tu construisais avec les autres",
            "narrative": [
                "Il y a des bouts de bois, des cartons, des couvertures usées.",
                "Et une idée qui flotte dans l'air : construire une cabane.",
                "Autour de cette cabane, il y a toujours plusieurs tribus d'enfants.",
                "Toi, tu repères instinctivement OÙ TU ÉTAIS.",
            ],
            "question": "À cet âge-là… tu te reconnaissais dans quel groupe ?",
            "options": [
                {"letter": "A", "label": "Les architectes",
                 "text": "Ceux qui dessinaient le plan, qui avaient la vision.",
                 "plain": "tu dessinais le plan, tu avais la vision",
                 "riasec": {"R": 1, "I": 1, "E": 1, "C": 1}},
                {"letter": "B", "label": "Les bâtisseurs",
                 "text": "Ceux qui attrapaient les planches et construisaient. L'énergie brute.",
                 "plain": "tu attrapais les planches et tu construisais",
                 "riasec": {"R": 2, "C": 1}},
                {"letter": "C", "label": "Les prospecteurs",
                 "text": "Ceux qui partaient fouiller les garages, qui ramenaient LE bon carton.",
                 "plain": "tu partais chercher et tu ramenais ce qu'il fallait",
                 "riasec": {"R": 1, "I": 1}},
                {"letter": "D", "label": "Les décorateurs",
                 "text": "Ceux qui rendaient l'intérieur vivable et chaleureux.",
                 "plain": "tu rendais l'endroit vivable et chaleureux",
                 "riasec": {"A": 2, "C": 1}},
                {"letter": "E", "label": "Les gardiens",
                 "text": "Ceux qui montaient la garde, négociaient le territoire.",
                 "plain": "tu gardais et tu négociais le territoire",
                 "riasec": {"S": 1, "E": 1}},
                {"letter": "F", "label": "Les rêveurs",
                 "text": "Ceux qui racontaient des histoires une fois la cabane finie.",
                 "plain": "tu racontais les histoires une fois la cabane finie",
                 "riasec": {"A": 1, "I": 1}},
            ],
        },
        {
            "id": "S1-2",
            "title": "Le cours qu'on attendait",
            "subtitle": "La matière où le temps disparaissait",
            "narrative": [
                "La plupart des cours… bon. Mais il y avait CE cours,",
                "où le temps n'existait plus. Où la sonnerie te faisait sursauter.",
            ],
            "question": "L'ambiance qui te parle le plus viscéralement :",
            "options": [
                {"letter": "A", "label": "Le labo",
                 "text": "Microscopes, réactions chimiques. Le plaisir de comprendre les rouages.",
                 "plain": "le plaisir de comprendre comment les choses marchent",
                 "riasec": {"I": 2, "C": 1}},
                {"letter": "B", "label": "L'atelier",
                 "text": "Travaux manuels. La fierté de voir quelque chose naître entre ses mains.",
                 "plain": "la fierté de voir quelque chose naître entre tes mains",
                 "riasec": {"R": 2, "C": 1}},
                {"letter": "C", "label": "La scène",
                 "text": "Théâtre, musique, exposé. Le trac qui devient excitation.",
                 "plain": "le trac qui devient de l'excitation devant les autres",
                 "riasec": {"A": 2, "S": 1, "E": 1}},
                {"letter": "D", "label": "Le terrain",
                 "text": "Sport, sorties nature. S'adapter au réel, coordonner son corps.",
                 "plain": "t'adapter au réel, bouger, coordonner ton corps",
                 "riasec": {"R": 1, "S": 1}},
                {"letter": "E", "label": "La bibliothèque",
                 "text": "Le plaisir des mots, des histoires, des univers inventés.",
                 "plain": "le plaisir des mots et des univers inventés",
                 "riasec": {"I": 1, "A": 2}},
                {"letter": "F", "label": "La cour",
                 "text": "L'intercours. Organiser le jeu, convaincre les copains, rassembler.",
                 "plain": "organiser le jeu, convaincre, rassembler",
                 "riasec": {"E": 2, "S": 1}},
            ],
        },
        {
            "id": "S1-3",
            "title": "L'histoire qu'on racontait",
            "subtitle": "Les archétypes de l'enfance",
            "narrative": [
                "Quand t'étais petit(e), les adultes déposaient en toi des graines de métiers.",
                "Lequel de ces archétypes résonne encore — celui qui, à 8 ans, "
                "t'a fait dire « plus tard, je veux faire ça » pendant une semaine ?",
            ],
            "question": "Ta pulsion derrière, elle était réelle. La tienne, c'était quoi ?",
            "options": [
                {"letter": "A", "label": "L'archéologue",
                 "text": "Celui qui découvre des trucs enfouis, qui lit le passé comme un livre.",
                 "plain": "découvrir ce qui est enfoui et le déchiffrer",
                 "riasec": {"I": 2, "R": 1}},
                {"letter": "B", "label": "L'astronaute",
                 "text": "Celui qui va là où personne n'est allé. La conquête.",
                 "plain": "aller là où personne n'est allé",
                 "riasec": {"I": 1, "E": 2}},
                {"letter": "C", "label": "Le vétérinaire",
                 "text": "Celui qui soigne, qui répare le vivant. La douceur, le soin.",
                 "plain": "soigner, réparer le vivant",
                 "riasec": {"S": 2, "R": 1}},
                {"letter": "D", "label": "Le pompier",
                 "text": "Celui qui sauve. Le courage physique, l'action héroïque, l'urgence.",
                 "plain": "sauver, agir dans l'urgence",
                 "riasec": {"R": 2, "S": 1}},
                {"letter": "E", "label": "La maîtresse/le maître",
                 "text": "Celui qui apprend aux autres. La transmission.",
                 "plain": "apprendre aux autres, transmettre",
                 "riasec": {"S": 2, "C": 1}},
                {"letter": "F", "label": "Le/la chef(fe)",
                 "text": "Celui qui décide. Le pouvoir, la responsabilité.",
                 "plain": "décider et porter la responsabilité",
                 "riasec": {"E": 2, "C": 1}},
            ],
        },
        {
            "id": "S1-4",
            "title": "Le jeu dont tu ne te lassais pas",
            "subtitle": "L'activité qui faisait perdre le temps",
            "narrative": [
                "On a tous eu CE jeu. Une activité ludique qui pouvait nous occuper des heures.",
                "Laquelle te faisait vraiment perdre la notion du temps ?",
            ],
            "question": "Laquelle te faisait vraiment kiffer ?",
            "options": [
                {"letter": "A", "label": "Construire",
                 "text": "Légos, Kapla, cabanes dans le jardin. La création matérielle.",
                 "plain": "construire des choses de tes mains",
                 "riasec": {"R": 2, "C": 1}},
                {"letter": "B", "label": "Stratégie",
                 "text": "Échecs, Risk. Le jeu où on gagnait par le plan, la ruse, l'intelligence.",
                 "plain": "gagner par le plan et la ruse",
                 "riasec": {"I": 2, "E": 1}},
                {"letter": "C", "label": "Imaginer",
                 "text": "Playmobil, poupées, les univers qu'on inventait. Fiction, faire-semblant.",
                 "plain": "inventer des univers",
                 "riasec": {"A": 2, "I": 1}},
                {"letter": "D", "label": "Conquérir",
                 "text": "Jeu vidéo d'action, cache-cache, sport. Adrénaline, défi physique.",
                 "plain": "l'adrénaline et le défi physique",
                 "riasec": {"R": 1, "E": 2}},
                {"letter": "E", "label": "Collectionner",
                 "text": "Cartes, timbres, billes. L'ordre, le classement, la complétude.",
                 "plain": "l'ordre, le classement, la collection complète",
                 "riasec": {"C": 2}},
                {"letter": "F", "label": "Partager",
                 "text": "Jeux de société, être ensemble. La connivence, le lien, le collectif.",
                 "plain": "être ensemble, la connivence",
                 "riasec": {"S": 2}},
            ],
        },
        {
            "id": "S1-5",
            "title": "Le moment de fierté",
            "subtitle": "La fierté qui montait de l'intérieur",
            "narrative": [
                "Un moment, entre 6 et 12 ans, où tu as ressenti une fierté immense.",
                "Pas celle que les adultes t'ont donnée — celle qui est montée de l'intérieur.",
            ],
            "question": "En fermant les yeux… lequel de ces souvenirs émet encore une petite lumière ?",
            "options": [
                {"letter": "A", "label": "De ses mains",
                 "text": "J'ai réussi à faire quelque chose de mes mains. "
                         "Un objet qui n'existait pas avant.",
                 "plain": "faire de tes mains un objet qui n'existait pas",
                 "riasec": {"R": 2, "C": 1}},
                {"letter": "B", "label": "Comprendre",
                 "text": "J'ai compris quelque chose de compliqué. "
                         "« Ahhh, c'est ça ! » La lumière, l'intuition.",
                 "plain": "comprendre enfin quelque chose de compliqué",
                 "riasec": {"I": 2}},
                {"letter": "C", "label": "Captiver",
                 "text": "J'ai fait rire ou j'ai captivé. J'ai raconté, et les autres ont réagi.",
                 "plain": "captiver, raconter et voir les autres réagir",
                 "riasec": {"A": 2, "S": 1}},
                {"letter": "D", "label": "Gagner",
                 "text": "J'ai gagné. Le match, la compétition, la course. "
                         "Le sentiment de la victoire.",
                 "plain": "gagner, le sentiment de la victoire",
                 "riasec": {"E": 2, "R": 1}},
                {"letter": "E", "label": "Aider",
                 "text": "J'ai aidé. J'ai consolé quelqu'un, défendu un plus petit.",
                 "plain": "aider, consoler, défendre plus petit que toi",
                 "riasec": {"S": 2}},
                {"letter": "F", "label": "Organiser",
                 "text": "J'ai organisé. J'ai réuni, mené le projet, décidé. Et ça a marché.",
                 "plain": "organiser, réunir, mener le projet",
                 "riasec": {"E": 1, "C": 2}},
            ],
        },
        {
            "id": "S1-6",
            "title": "Ce qu'on disait de toi",
            "subtitle": "Le regard des autres — enfant",
            "narrative": [
                "Quand tu étais enfant, les adultes utilisaient des mots pour te décrire.",
                "Des qualificatifs qui revenaient. Lequel collait le plus à ta peau d'enfant ?",
            ],
            "question": "S'il y avait UN adjectif qui revenait comme un leitmotiv… c'était lequel ?",
            "options": [
                {"letter": "A", "label": "Curieux(se)",
                 "text": "« Il/elle est curieux(se) » — Tu posais tout le temps des questions.",
                 "plain": "on te disait curieux, tu posais tout le temps des questions",
                 "riasec": {"I": 2}},
                {"letter": "B", "label": "Habile de ses mains",
                 "text": "« Il/elle est habile de ses mains » — Tu réparais, bricolais, construisais.",
                 "plain": "on te disait habile de tes mains",
                 "riasec": {"R": 2}},
                {"letter": "C", "label": "Imaginatif(ve)",
                 "text": "« Il/elle est imaginatif(ve) » — Tu inventais des histoires, des mondes.",
                 "plain": "on te disait imaginatif, tu inventais des mondes",
                 "riasec": {"A": 2}},
                {"letter": "D", "label": "Sportif(ve)",
                 "text": "« Il/elle est sportif(ve) » — Tu avais besoin de bouger, courir.",
                 "plain": "on te disait sportif, tu avais besoin de bouger",
                 "riasec": {"R": 2, "E": 1}},
                {"letter": "E", "label": "Sensible",
                 "text": "« Il/elle est sensible » — Tu ressentais les émotions des autres.",
                 "plain": "on te disait sensible aux émotions des autres",
                 "riasec": {"S": 2}},
                {"letter": "F", "label": "Suite dans les idées",
                 "text": "« Il/elle a de la suite dans les idées » — Tu ne lâchais pas, tu insistais.",
                 "plain": "on disait que tu avais de la suite dans les idées",
                 "riasec": {"E": 1, "C": 2}},
                {"letter": "G", "label": "Fédérateur(trice)",
                 "text": "« Il/elle est fédérateur(trice) » — Les jeux s'organisaient autour de toi.",
                 "plain": "les jeux s'organisaient autour de toi",
                 "riasec": {"S": 1, "E": 2}},
                {"letter": "H", "label": "Sérieux(se)",
                 "text": "« Il/elle est sérieux(se) » — Tu écoutais, tu suivais les règles.",
                 "plain": "on te disait sérieux, tu suivais les règles",
                 "riasec": {"C": 2}},
            ],
        },
    ],
    "billet": [
        {"key": "cabane", "label": "Dans la cabane, tu étais plutôt :"},
        {"key": "jeu", "label": "Au jeu, tu préférais :"},
        {"key": "fierte", "label": "Ta fierté venait de :"},
        {"key": "regard", "label": "Les autres disaient que tu étais :"},
    ],
}
```

Update the `SESSIONS` list and add `riasec_maxima()`:

```python
SESSIONS: list[dict] = [_SESSION_0, _SESSION_1]


def riasec_maxima() -> dict[str, int]:
    """The best score reachable per RIASEC letter, computed from session 1.

    Computed, never a literal: the counselor manual prints E 10 and C 10, but
    summing the best available option per scene gives E 11 and C 9. Those two
    are transcription slips in the paper sheet (spec errata 17b), and a
    normalisation against the printed maxima would score E too high and C too
    low for every person, invisibly.
    """
    maxima = {letter: 0 for letter in RIASEC_LETTERS}
    for scene in _SESSION_1["items"]:
        for letter in RIASEC_LETTERS:
            best = max(
                (option.get("riasec", {}).get(letter, 0) for option in scene["options"]),
                default=0,
            )
            maxima[letter] += best
    return maxima
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_bank.py -v`
Expected: PASS — the five parametrised cases for sessions 2–5 will fail with `StopIteration` until task 8. Run only what exists:
`cd backend && pytest tests/test_voyage_bank.py -v -k "not [2] and not [3] and not [4] and not [5]"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/bank.py backend/tests/test_voyage_bank.py
git commit -m "feat(voyage): session 1 and the computed RIASEC maxima"
```

---

## Task 5: Session 2 — values and needs

**Files:**
- Modify: `backend/app/services/voyage/bank.py`
- Test: `backend/tests/test_voyage_bank.py` (append)

**Interfaces:**
- Consumes: `SDT`, `SCHWARTZ`, `BIG5` (task 1).
- Produces: `_SESSION_2`.

Two transcription notes, both recorded in code comments so a later reader does not "fix" them:

1. The manual's *Dimension* column sometimes names something outside the closed vocabulary — `S2-1 A` says « SDT : Sécurité cognitive », and SDT has only autonomie / appartenance / competence. Those rows carry the nearest in-vocabulary value and a comment quoting the manual.
2. `schwartz` is a list because the manual routinely names two (« Conformité + Intégrité » on `S2-5 B`).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_bank.py`:

```python
def test_session_2_header():
    s2 = _session("2")
    assert s2["title"] == "Ce qui compte vraiment pour toi"
    assert s2["subtitle"] == "Ce qui te donne envie de te lever le matin · 7 situations"
    assert s2["duration"] == "20 min"
    assert [i["id"] for i in s2["items"]] == [f"S2-{k}" for k in range(1, 8)]
    assert [b["key"] for b in s2["billet"]] == ["vibrer", "vide", "vingt_ans"]


def test_tag_values_are_in_vocabulary():
    """Every sdt / schwartz / big5 / style value across the whole bank."""
    for session in bank.SESSIONS:
        if session["kind"] != bank.KIND_SCENES:
            continue
        for scene in session["items"]:
            for option in scene["options"]:
                where = f"{scene['id']}{option['letter']}"
                if "sdt" in option:
                    assert option["sdt"] in bank.SDT, where
                if "schwartz" in option:
                    assert isinstance(option["schwartz"], list) and option["schwartz"], where
                    for value in option["schwartz"]:
                        assert value in bank.SCHWARTZ, f"{where}: {value}"
                if "big5" in option:
                    assert option["big5"], where
                    for trait, sign in option["big5"].items():
                        assert trait in bank.BIG5, f"{where}: {trait}"
                        assert sign in (1, -1), f"{where}: {trait}={sign}"
                if "style" in option:
                    assert option["style"] in bank.STYLES, where


def test_session_2_seventh_scene_is_the_ambivalence_probe():
    """score_s2 reports S2-7 as `ambivalences`; it must have six options."""
    scene = next(s for s in _session("2")["items"] if s["id"] == "S2-7")
    assert len(scene["options"]) == 6
    assert [o["letter"] for o in scene["options"]] == list("ABCDEF")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_bank.py::test_session_2_header -v`
Expected: FAIL — `StopIteration`

- [ ] **Step 3: Write session 2**

Insert `_SESSION_2` before the `SESSIONS` list and add it to that list:

```python
_SESSION_2 = {
    "n": "2",
    "title": "Ce qui compte vraiment pour toi",
    "subtitle": "Ce qui te donne envie de te lever le matin · 7 situations",
    "intro": [
        "Aujourd'hui, on va plus loin. On va chercher ce qui te fait vraiment vibrer.",
        "Pas ce qui est « bien » ou « raisonnable ». Ce qui, quand c'est là, "
        "te donne envie de te lever le matin. Et quand c'est absent, te vide de "
        "l'intérieur, même si tout va bien.",
        "7 scènes. Dans chacune, entoure la lettre qui te correspond.",
    ],
    "outro": [],
    "duration": "20 min",
    "kind": KIND_SCENES,
    "items": [
        {
            "id": "S2-1",
            "title": "Le projet passion",
            "subtitle": "La liberté d'un projet sans contrainte",
            "narrative": [
                "On t'a confié un projet. Carte blanche sur la façon de le mener.",
                "Personne ne regarde par-dessus ton épaule. Résultat dans 3 mois.",
            ],
            "question": "Comment tu fonctionnes, toi ? Avant la raison, avant la stratégie.",
            "options": [
                {"letter": "A", "label": "Structure dès le début",
                 "text": "Tu structures tout dès le premier jour. Planning, jalons, deadlines. "
                         "Tu sais où tu vas.",
                 "plain": "tu structures tout dès le premier jour",
                 # manual: "SDT : Sécurité cognitive" — not one of the three SDT
                 # needs, so only the Schwartz value it also names is carried.
                 "schwartz": ["conformite"],
                 "big5": {"conscienciosite": 1}},
                {"letter": "B", "label": "Explorer d'abord",
                 "text": "Tu commences par explorer. Tu testes, tu tâtonnes, "
                         "tu vois ce qui émerge.",
                 "plain": "tu explores et tu tâtonnes avant de décider",
                 "sdt": "autonomie", "schwartz": ["autodirection"]},
                {"letter": "C", "label": "Aller vers les autres",
                 "text": "Tu vas parler aux gens. Tu échanges, tu construis avec eux. "
                         "Le collectif te porte.",
                 "plain": "tu vas parler aux gens, le collectif te porte",
                 "sdt": "appartenance", "schwartz": ["bienveillance"]},
                {"letter": "D", "label": "Fond et qualité",
                 "text": "Tu te concentres sur le fond. Tu veux que ce soit parfait, "
                         "que ça tienne la route.",
                 "plain": "tu veux que ça tienne vraiment la route",
                 "sdt": "competence", "schwartz": ["reussite"]},
            ],
        },
        {
            "id": "S2-2",
            "title": "La proposition qu'on t'a faite",
            "subtitle": "Quitter la sécurité pour l'aventure",
            "narrative": [
                "Tu es bien là où tu es. L'équipe sympa, rien à redire.",
                "Et là, on te propose autre chose. Différent, un peu risqué — "
                "mais si ça marche, ça peut être grand.",
            ],
            "question": "Écoute ton premier réflexe. Avant la raison. Qu'est-ce qui se passe en toi ?",
            "options": [
                {"letter": "A", "label": "Rester — sécurité",
                 "text": "Tu réfléchis, tu pèses le pour et le contre, et tu restes. "
                         "La sécurité, c'est trop important.",
                 "plain": "tu restes, la sécurité compte trop",
                 "schwartz": ["conservation", "securite"]},
                {"letter": "B", "label": "Foncer — aventure",
                 "text": "Ton cœur s'emballe. Le risque, l'aventure — c'est ça qui te fait "
                         "sentir vivant(e). Tu te lances.",
                 "plain": "tu te lances, le risque te fait te sentir vivant",
                 "schwartz": ["stimulation"], "big5": {"ouverture": 1}},
                {"letter": "C", "label": "Consulter — lien",
                 "text": "Tu demandes conseil autour de toi. Tu ne prendras pas cette "
                         "décision seul(e).",
                 "plain": "tu ne décides pas seul, tu demandes conseil",
                 "schwartz": ["bienveillance"], "sdt": "appartenance"},
                {"letter": "D", "label": "Questionner le sens",
                 "text": "Tu te demandes : « est-ce que ça a du sens ? » "
                         "Si c'est juste pour gagner plus, ça ne t'intéresse pas.",
                 "plain": "tu demandes d'abord si ça a du sens",
                 "schwartz": ["universalisme"]},
            ],
        },
        {
            "id": "S2-3",
            "title": "La reconnaissance",
            "subtitle": "Ce qui te touche vraiment après un succès",
            "narrative": [
                "Tu viens de finir un gros projet. Ça a marché. Vraiment bien marché.",
                "Le lendemain, plusieurs choses se passent. "
                "Laquelle te touche le PLUS profondément ?",
            ],
            "question": "Laquelle fait vibrer quelque chose en toi, là, maintenant ?",
            "options": [
                {"letter": "A", "label": "Validation du chef",
                 "text": "Ton responsable te prend à part : « Franchement, super boulot. "
                         "J'ai vu tout ce que t'as mis là-dedans. »",
                 "plain": "que ton responsable voie ce que tu y as mis",
                 # manual: "Besoin de feedback hiérarchique" — nearest closed value.
                 "schwartz": ["reussite"]},
                {"letter": "B", "label": "Verre en équipe",
                 "text": "Ton équipe t'emmène boire un verre. Personne ne fait de discours, "
                         "mais tout le monde est là.",
                 "plain": "que toute l'équipe soit là, sans discours",
                 "sdt": "appartenance", "schwartz": ["bienveillance"]},
                {"letter": "C", "label": "Reconnaissance publique",
                 "text": "On annonce les résultats en réunion. Ton nom est cité devant tout le monde.",
                 "plain": "que ton nom soit cité devant tout le monde",
                 "schwartz": ["reussite", "pouvoir"]},
                {"letter": "D", "label": "Satisfaction intérieure",
                 "text": "Personne ne dit rien. Mais toi, tu sais que t'as fait du bon boulot. "
                         "La satisfaction intérieure te suffit.",
                 "plain": "savoir toi-même que c'était du bon travail te suffit",
                 "sdt": "competence", "schwartz": ["autodirection"]},
            ],
        },
        {
            "id": "S2-4",
            "title": "Le conflit d'équipe",
            "subtitle": "Valeurs en tension",
            "narrative": [
                "Dans ton équipe, il y a des tensions. Deux personnes ne sont pas d'accord.",
                "L'un veut livrer vite. L'autre veut prendre le temps, faire solide. "
                "Toi, tu te situes où ?",
            ],
            "question": "Instinctivement, tu fais quoi dans ce genre de situation ?",
            "options": [
                {"letter": "A", "label": "Compromis",
                 "text": "Tu écoutes les deux, tu proposes une synthèse, tu cherches le compromis. "
                         "L'harmonie du groupe est primordiale.",
                 "plain": "tu cherches le compromis, l'harmonie du groupe compte",
                 "big5": {"agreabilite": 1}, "schwartz": ["bienveillance"]},
                {"letter": "B", "label": "Prendre position",
                 "text": "Tu prends position. Clairement. Tu dis ce que tu penses, "
                         "même si ça crée un clash.",
                 "plain": "tu dis ce que tu penses même si ça crée un clash",
                 "big5": {"agreabilite": -1}, "schwartz": ["integrite"]},
                {"letter": "C", "label": "Analyser le fond",
                 "text": "Tu essaies de comprendre le fond du problème. "
                         "Tu joues le médiateur analytique.",
                 "plain": "tu cherches le fond du problème avant de trancher",
                 "big5": {"ouverture": 1}},
                {"letter": "D", "label": "Procédure collective",
                 "text": "Tu proposes qu'on vote en réunion, qu'on décide collectivement "
                         "et qu'on avance. La procédure rassure.",
                 "plain": "tu proposes qu'on décide collectivement et qu'on avance",
                 "schwartz": ["conformite"]},
            ],
        },
        {
            "id": "S2-5",
            "title": "Le moment difficile",
            "subtitle": "Pourquoi on tient quand c'est dur",
            "narrative": [
                "Ça fait plusieurs mois que ça ne va pas. Le travail est devenu difficile.",
                "Pas intéressant. Parfois même un peu absurde. "
                "Mais il y a une raison pour laquelle tu restes.",
            ],
            "question": "La raison profonde. Celle qui est honnête. Laquelle te ressemble ?",
            "options": [
                {"letter": "A", "label": "Les autres comptent",
                 "text": "Tu as des gens qui comptent sur toi. Tu ne peux pas les laisser tomber.",
                 "plain": "des gens comptent sur toi et tu ne les lâches pas",
                 "schwartz": ["bienveillance"]},
                {"letter": "B", "label": "Je me suis engagé(e)",
                 "text": "Tu t'es engagé(e). Tu as promis que tu finirais. "
                         "Tu n'es pas du genre à lâcher.",
                 "plain": "tu as promis de finir et tu finis",
                 "schwartz": ["conformite", "integrite"]},
                {"letter": "C", "label": "Ça a de l'impact",
                 "text": "Tu sais que ce que tu fais a un impact. Quelque part, ça aide des gens.",
                 "plain": "ce que tu fais aide des gens quelque part",
                 "schwartz": ["universalisme"]},
                {"letter": "D", "label": "Je dois prouver",
                 "text": "Tu veux prouver que tu peux le faire. À toi-même, d'abord. "
                         "Abandonner = reconnaître l'échec.",
                 "plain": "tu veux te prouver à toi-même que tu peux le faire",
                 "schwartz": ["reussite"]},
            ],
        },
        {
            "id": "S2-6",
            "title": "Le chef idéal",
            "subtitle": "Besoins relationnels au travail",
            "narrative": [
                "Si tu devais décrire le chef idéal pour toi,",
                "celui avec qui tu donnerais le meilleur de toi-même, ce serait lequel ?",
            ],
            "question": "Le chef avec lequel tu t'épanouirais vraiment. Sans compromis. C'est lequel ?",
            "options": [
                {"letter": "A", "label": "Confiance + autonomie",
                 "text": "Celui qui te fait confiance, qui te laisse de l'autonomie. "
                         "« Débrouille-toi, je te fais confiance. »",
                 "plain": "celui qui te laisse de l'autonomie",
                 "sdt": "autonomie", "schwartz": ["autodirection"]},
                {"letter": "B", "label": "Exigence + défi",
                 "text": "Celui qui est exigeant. Qui te pousse à te dépasser, "
                         "qui attend le meilleur de toi.",
                 "plain": "celui qui est exigeant et te pousse à te dépasser",
                 "schwartz": ["hedonisme", "reussite"]},
                {"letter": "C", "label": "Lien + présence",
                 "text": "Celui qui est présent. Qui prend des nouvelles, "
                         "crée une vraie relation humaine.",
                 "plain": "celui qui est présent et prend des nouvelles",
                 "sdt": "appartenance"},
                {"letter": "D", "label": "Vision + sécurité",
                 "text": "Celui qui sait où il va. Vision claire, décisions difficiles. "
                         "« On va par là, suis-moi. »",
                 "plain": "celui qui sait où il va et l'annonce clairement",
                 "schwartz": ["securite", "pouvoir"]},
            ],
        },
        {
            "id": "S2-7",
            "title": "Dans 20 ans",
            "subtitle": "La projection existentielle",
            "narrative": [
                "Ultime scène pour aujourd'hui. On se projette loin. Très loin. Dans 20 ans.",
                "Quand tu regardes ta vie professionnelle en arrière, qu'est-ce qui te fera "
                "dire : « voilà, ça valait le coup, je ne regrette rien » ?",
            ],
            "question": "Sans filtre. La réponse qui vient du ventre. Dans 20 ans, qu'est-ce qui compte ?",
            "options": [
                {"letter": "A", "label": "Construire / Héritage",
                 "text": "« J'ai construit des choses qui durent. Des réalisations dont je suis "
                         "fier(e), quelque chose qui restera. »",
                 "plain": "tu veux avoir construit des choses qui durent",
                 "schwartz": ["reussite"]},
                {"letter": "B", "label": "Aventure / Intensité",
                 "text": "« J'ai vécu des aventures incroyables. Des projets fous, "
                         "des moments où mon cœur battait fort. »",
                 "plain": "tu veux avoir vécu des projets fous",
                 "schwartz": ["hedonisme", "stimulation"]},
                {"letter": "C", "label": "Utilité / Sens",
                 "text": "« J'ai été utile. J'ai aidé des gens, j'ai changé des vies. "
                         "Le monde est un peu meilleur grâce à moi. »",
                 "plain": "tu veux avoir été utile et avoir changé des vies",
                 "schwartz": ["universalisme"]},
                {"letter": "D", "label": "Liens / Collectif",
                 "text": "« J'étais entouré(e). Des équipes formidables, des liens forts. "
                         "Je n'étais pas seul(e). »",
                 "plain": "tu veux avoir été entouré de liens forts",
                 "schwartz": ["bienveillance"], "sdt": "appartenance"},
                {"letter": "E", "label": "Compétence / Maîtrise",
                 "text": "« J'ai grandi. Je suis devenu(e) meilleur(e), plus compétent(e), "
                         "plus sage. »",
                 "plain": "tu veux être devenu meilleur et plus sage",
                 "sdt": "competence"},
                {"letter": "F", "label": "Liberté / Indépendance",
                 "text": "« J'étais libre. J'ai fait ce que je voulais, quand je voulais. "
                         "Ma vie m'appartenait. »",
                 "plain": "tu veux que ta vie t'appartienne",
                 "schwartz": ["autodirection"], "sdt": "autonomie"},
            ],
        },
    ],
    "billet": [
        {"key": "vibrer", "label": "Ce qui me fait vibrer, c'est quand :"},
        {"key": "vide", "label": "Ce qui me vide, c'est quand :"},
        {"key": "vingt_ans", "label": "Dans 20 ans, je veux pouvoir dire que :"},
    ],
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_bank.py -v -k "not [3] and not [4] and not [5]"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/bank.py backend/tests/test_voyage_bank.py
git commit -m "feat(voyage): session 2, values and needs"
```

---

## Task 6: Session 3 — how you think

**Files:**
- Modify: `backend/app/services/voyage/bank.py`
- Test: `backend/tests/test_voyage_bank.py` (append)

**Interfaces:**
- Consumes: `BIG5`, `STYLES` (task 1).
- Produces: `_SESSION_3`.

Session 3 is the only source of `big5` and `style` counts. Signs matter and are easy to get backwards: the manual's « Faible Névrotisme » means `nevrotisme: -1`, and « Introversion » means `extraversion: -1`. Reading either as `+1` inverts the Big Five levels for the whole portrait with nothing failing.

`style` is optional here — some manual rows name a style the four-value vocabulary has no slot for. Contract § A.3 cites « Style hybride » on `S3-6 C` as the example. This plan maps it to `adaptatif` rather than dropping it, because « seul(e) pour réfléchir, ensemble pour valider » is precisely `STYLE_PLAIN["adaptatif"]` — "ajuste sa méthode au contexte" — and because dropping it would leave that option with only a `big5` tag that the manual does not actually assert. **This refines contract § A.3's parenthetical; record it when the contract is next revised.** `S3-4 D` genuinely has no Big Five or style content (the manual reads « Motivation intrinsèque conditionnelle — Besoin de finalité »), so it carries a `schwartz` tag instead, which `score_s2` correctly ignores because that scorer counts session 2 only.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_bank.py`:

```python
def test_session_3_header():
    s3 = _session("3")
    assert s3["title"] == "Comment tu penses et tu fonctionnes"
    assert s3["subtitle"] == "Pas ce que tu fais — comment tu le fais · 7 situations"
    assert s3["duration"] == "20 min"
    assert [i["id"] for i in s3["items"]] == [f"S3-{k}" for k in range(1, 8)]
    assert [b["key"] for b in s3["billet"]] == ["imprevu", "meilleur", "pression"]


def test_session_3_negative_signs_are_preserved():
    """« Faible Névrotisme » is -1 and « Introversion » is -1. Reading either as
    +1 inverts the levels for every person, and nothing would fail."""
    def big5(item_id, letter):
        return bank.option(item_id, letter)["big5"]

    assert big5("S3-1", "A")["nevrotisme"] == -1     # "Faible Névrotisme"
    assert big5("S3-1", "C")["extraversion"] == -1   # "Introversion"
    assert big5("S3-2", "D")["extraversion"] == -1   # "Extraversion basse"
    assert big5("S3-3", "A")["nevrotisme"] == -1
    assert big5("S3-4", "B")["ouverture"] == -1      # "Faible Ouverture"
    assert big5("S3-5", "A")["nevrotisme"] == -1
    assert big5("S3-6", "A")["extraversion"] == -1
    assert big5("S3-7", "B")["extraversion"] == -1
    assert big5("S3-7", "D")["nevrotisme"] == -1


def test_session_3_styles_are_assigned_where_the_manual_names_one():
    assert bank.option("S3-1", "A")["style"] == "holistique"
    assert bank.option("S3-1", "B")["style"] == "sequentiel"
    assert bank.option("S3-6", "B")["style"] == "consultatif"
    assert bank.option("S3-6", "C")["style"] == "adaptatif"
    assert "style" not in bank.option("S3-4", "D")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_bank.py::test_session_3_header -v`
Expected: FAIL — `StopIteration`

- [ ] **Step 3: Write session 3**

Insert `_SESSION_3` before `SESSIONS` and add it to the list:

```python
_SESSION_3 = {
    "n": "3",
    "title": "Comment tu penses et tu fonctionnes",
    "subtitle": "Pas ce que tu fais — comment tu le fais · 7 situations",
    "intro": [
        "Les fois précédentes, on a regardé ce que tu faisais naturellement, "
        "et ce qui te fait vibrer.",
        "Aujourd'hui, on s'intéresse à quelque chose de plus difficile à voir. "
        "Pas ce que tu fais. Comment tu le fais.",
        "Ta façon naturelle de traiter l'information. De prendre des décisions. "
        "D'interagir avec les autres. De te recharger, de te fatiguer.",
    ],
    "outro": [],
    "duration": "20 min",
    "kind": KIND_SCENES,
    "items": [
        {
            "id": "S3-1",
            "title": "La réunion surprise",
            "subtitle": "Décider sans préparation",
            "narrative": [
                "Il est 9h. On t'annonce une réunion dans 5 minutes.",
                "Tu n'as rien préparé. Tu dois prendre position sur un sujet important.",
            ],
            "question": "Comment tu réagis ?",
            "options": [
                {"letter": "A", "label": "S'adapte, improvise",
                 "text": "Tu t'adaptes. Tu improvises, tu te lances. L'imprévu te réveille.",
                 "plain": "tu improvises, l'imprévu te réveille",
                 "big5": {"extraversion": 1, "ouverture": 1, "nevrotisme": -1},
                 "style": "holistique"},
                {"letter": "B", "label": "Prend 5 min de structure",
                 "text": "Tu prends 5 minutes pour noter les points essentiels. "
                         "Un minimum de structure.",
                 "plain": "tu prends cinq minutes pour te donner un minimum de structure",
                 "big5": {"conscienciosite": 1}, "style": "sequentiel"},
                {"letter": "C", "label": "Écoute les autres d'abord",
                 "text": "Tu stresses un peu, mais tu écoutes les autres d'abord "
                         "avant de te positionner.",
                 "plain": "tu écoutes les autres avant de te positionner",
                 "big5": {"agreabilite": 1, "extraversion": -1}, "style": "consultatif"},
                {"letter": "D", "label": "Mal à l'aise sans prépa",
                 "text": "Tu es mal à l'aise. Décider sans préparation, c'est contre ta nature.",
                 "plain": "décider sans préparation va contre ta nature",
                 "big5": {"nevrotisme": 1, "conscienciosite": 1}},
            ],
        },
        {
            "id": "S3-2",
            "title": "Le collègue très différent",
            "subtitle": "Travailler avec son opposé",
            "narrative": [
                "Tu dois travailler pendant 3 semaines avec quelqu'un qui fonctionne "
                "à l'opposé de toi.",
                "Il/elle pense différemment, n'a pas les mêmes méthodes.",
            ],
            "question": "Comment tu vis les 3 premières semaines ?",
            "options": [
                {"letter": "A", "label": "Stimulant",
                 "text": "C'est stimulant. Les différences forcent à voir les choses autrement.",
                 "plain": "les différences te stimulent",
                 "big5": {"ouverture": 1}},
                {"letter": "B", "label": "Inconfortable → s'adapte",
                 "text": "Inconfortable au début, mais tu t'adaptes. "
                         "Tu cherches à comprendre sa logique.",
                 "plain": "tu t'adaptes et tu cherches à comprendre sa logique",
                 "big5": {"agreabilite": 1, "ouverture": 1}, "style": "adaptatif"},
                {"letter": "C", "label": "S'ajuste, harmonie",
                 "text": "Tu t'ajustes à lui/elle plus que tu ne l'exprimes. L'harmonie avant tout.",
                 "plain": "tu t'ajustes plutôt que de l'exprimer",
                 "big5": {"agreabilite": 1}},
                {"letter": "D", "label": "Épuisant",
                 "text": "C'est épuisant. Être en décalage constant, ça consomme de l'énergie.",
                 "plain": "le décalage constant te consomme de l'énergie",
                 "big5": {"nevrotisme": 1, "extraversion": -1}},
            ],
        },
        {
            "id": "S3-3",
            "title": "L'information incomplète",
            "subtitle": "Agir sans tout savoir",
            "narrative": [
                "Tu dois prendre une décision importante, mais tu n'as pas toutes "
                "les informations.",
                "Il te manque des données clés.",
            ],
            "question": "Comment tu procèdes ?",
            "options": [
                {"letter": "A", "label": "Décide quand même",
                 "text": "Tu décides quand même. Avec ce que tu as, tu avances. "
                         "L'attente est pire que l'imperfection.",
                 "plain": "tu avances avec ce que tu as",
                 "big5": {"nevrotisme": -1, "extraversion": 1}, "style": "holistique"},
                {"letter": "B", "label": "Cartographie les manques",
                 "text": "Tu cartographies ce que tu sais et ce que tu ne sais pas. "
                         "Tu identifies tes angles morts.",
                 "plain": "tu cartographies ce que tu sais et ce qui te manque",
                 "big5": {"ouverture": 1, "conscienciosite": 1}, "style": "sequentiel"},
                {"letter": "C", "label": "Demande aux autres",
                 "text": "Tu demandes à d'autres personnes. "
                         "Plusieurs perspectives compensent les manques.",
                 "plain": "tu vas chercher d'autres points de vue",
                 "big5": {"agreabilite": 1, "extraversion": 1}, "style": "consultatif"},
                {"letter": "D", "label": "Attend plus d'éléments",
                 "text": "Tu attends. Tu repousses la décision jusqu'à avoir plus d'éléments.",
                 "plain": "tu attends d'avoir plus d'éléments",
                 "big5": {"conscienciosite": 1, "nevrotisme": 1}},
            ],
        },
        {
            "id": "S3-4",
            "title": "La tâche répétitive",
            "subtitle": "Le rapport à la routine",
            "narrative": [
                "Tu dois effectuer la même tâche, dans le même ordre, "
                "tous les jours pendant un mois.",
            ],
            "question": "Au bout d'une semaine, qu'est-ce qui se passe en toi ?",
            "options": [
                {"letter": "A", "label": "S'ennuie",
                 "text": "Tu t'ennuies assez vite. La répétition t'anesthésie. "
                         "Tu as besoin de changement.",
                 "plain": "la répétition t'anesthésie vite",
                 "big5": {"ouverture": 1}},
                {"letter": "B", "label": "Confort dans la routine",
                 "text": "Tu trouves une forme de confort. Maîtriser, ne pas avoir de surprise.",
                 "plain": "tu trouves du confort à maîtriser sans surprise",
                 "big5": {"conscienciosite": 1, "ouverture": -1}},
                {"letter": "C", "label": "Optimise",
                 "text": "Tu optimises. Puisque c'est répétitif, tu cherches comment "
                         "le faire mieux.",
                 "plain": "tu cherches comment le faire mieux",
                 "big5": {"ouverture": 1, "conscienciosite": 1}, "style": "adaptatif"},
                {"letter": "D", "label": "Tient si ça a du sens",
                 "text": "Ça dépend du contexte. Si ça a du sens, tu tiens. Sinon, non.",
                 "plain": "tu tiens si ça a du sens, pas autrement",
                 # manual: "Motivation intrinsèque conditionnelle — Besoin de finalité".
                 # Neither a Big Five trait nor a cognitive style; carried as the
                 # meaning signal it is. score_s2 counts session 2 only, so this
                 # never reaches the Schwartz tally.
                 "schwartz": ["universalisme"]},
            ],
        },
        {
            "id": "S3-5",
            "title": "Le feedback difficile",
            "subtitle": "Recevoir une critique sur son travail",
            "narrative": [
                "Ton responsable t'a dit que ton travail avait des lacunes.",
                "La critique est juste, mais elle fait mal.",
            ],
            "question": "Ce soir-là, qu'est-ce qui se passe ?",
            "options": [
                {"letter": "A", "label": "Digère et avance",
                 "text": "Tu digères et tu avances. Avoir tort ne te définit pas.",
                 "plain": "avoir tort ne te définit pas, tu avances",
                 "big5": {"nevrotisme": -1}},
                {"letter": "B", "label": "Cerveau ne lâche pas",
                 "text": "Tu refais mentalement tout le chemin. "
                         "Ton cerveau ne lâche pas facilement.",
                 "plain": "tu refais mentalement tout le chemin",
                 "big5": {"nevrotisme": 1}, "style": "sequentiel"},
                {"letter": "C", "label": "Besoin d'en parler",
                 "text": "Tu as besoin d'en parler à quelqu'un de confiance.",
                 "plain": "tu as besoin d'en parler à quelqu'un de confiance",
                 "big5": {"agreabilite": 1, "extraversion": 1}, "style": "consultatif"},
                {"letter": "D", "label": "Analyse le pourquoi",
                 "text": "Tu veux comprendre exactement pourquoi c'est une erreur. Tu analyses.",
                 "plain": "tu veux comprendre exactement pourquoi",
                 "big5": {"ouverture": 1, "conscienciosite": 1}, "style": "sequentiel"},
            ],
        },
        {
            "id": "S3-6",
            "title": "Solo ou ensemble ?",
            "subtitle": "Source d'énergie au travail",
            "narrative": [
                "Pour une tâche importante qui demande beaucoup de réflexion,",
            ],
            "question": "Qu'est-ce que tu choisirais instinctivement ?",
            "options": [
                {"letter": "A", "label": "Seul(e)",
                 "text": "Seul(e). La concentration profonde, c'est là que tu produis le mieux.",
                 "plain": "tu produis le mieux dans la concentration profonde, seul",
                 "big5": {"extraversion": -1}},
                {"letter": "B", "label": "Ensemble",
                 "text": "Ensemble. Les échanges génèrent des idées que tu n'aurais pas "
                         "eues seul(e).",
                 "plain": "les échanges te donnent des idées que tu n'aurais pas eues seul",
                 "big5": {"extraversion": 1}, "style": "consultatif"},
                {"letter": "C", "label": "Seul(e) puis ensemble",
                 "text": "Seul(e) pour réfléchir, ensemble pour valider. Le meilleur des deux.",
                 "plain": "seul pour réfléchir, ensemble pour valider",
                 # manual: "Ambiversion — Style hybride". Mapped to adaptatif:
                 # switching mode by task is what STYLE_PLAIN["adaptatif"] says.
                 "style": "adaptatif"},
                {"letter": "D", "label": "S'adapte",
                 "text": "Ça dépend de la tâche. Tu t'adaptes.",
                 "plain": "tu t'adaptes à la tâche",
                 "big5": {"ouverture": 1, "agreabilite": 1}, "style": "adaptatif"},
            ],
        },
        {
            "id": "S3-7",
            "title": "La surcharge",
            "subtitle": "Quand trop de choses arrivent en même temps",
            "narrative": [
                "Trois urgences arrivent en même temps. Ton téléphone sonne. "
                "Tes collègues te sollicitent.",
            ],
            "question": "Comment tu t'en sors instinctivement ?",
            "options": [
                {"letter": "A", "label": "Priorise, liste",
                 "text": "Tu priorises. Tu fais une liste, tu identifies l'urgent et l'important.",
                 "plain": "tu fais une liste et tu tries l'urgent de l'important",
                 "big5": {"conscienciosite": 1}, "style": "sequentiel"},
                {"letter": "B", "label": "S'isole",
                 "text": "Tu t'isoles. Tu coupes les notifications, tu te mets dans une bulle.",
                 "plain": "tu coupes tout et tu te mets dans une bulle",
                 "big5": {"extraversion": -1}},
                {"letter": "C", "label": "Délègue ou demande aide",
                 "text": "Tu délègues ou tu demandes de l'aide.",
                 "plain": "tu délègues ou tu demandes de l'aide",
                 "big5": {"agreabilite": 1, "extraversion": 1}, "style": "consultatif"},
                {"letter": "D", "label": "Absorbe, jongle",
                 "text": "Tu absorbes. Tu encaisses, tu gères, tu jonglles. "
                         "Les autres sont souvent surpris.",
                 "plain": "tu encaisses et tu jongles, ça surprend les autres",
                 "big5": {"nevrotisme": -1}, "style": "holistique"},
            ],
        },
    ],
    "billet": [
        {"key": "imprevu", "label": "Face à l'imprévu, je suis plutôt :"},
        {"key": "meilleur", "label": "Je produis le mieux quand je suis :"},
        {"key": "pression", "label": "Sous pression, mon premier réflexe est de :"},
    ],
}
```

Note on `S3-7 D`: the cahier reads « tu jonglles » — a typo in the PM's source. It is transcribed as-is; *verbatim* means verbatim. Fixing it is the PM's call, and it belongs in a copy pass, not in this task.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_bank.py -v -k "not [4] and not [5]"`
Expected: PASS. `test_session_3_styles_...` calls `bank.option()`, which task 9 adds — until then, run without it: add `and not styles_are_assigned` to the `-k` expression, and re-run the full file at the end of task 9.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/bank.py backend/tests/test_voyage_bank.py
git commit -m "feat(voyage): session 3, cognitive style and Big Five signs"
```

---

## Task 7: Session 4 — the environment

**Files:**
- Modify: `backend/app/services/voyage/bank.py`
- Test: `backend/tests/test_voyage_bank.py` (append)

**Interfaces:**
- Consumes: `S4_SLOTS` (task 1).
- Produces: `_SESSION_4`.

Session 4 carries no arithmetic at all: `score_s4` simply reads the `env` label of the chosen option into a fixed slot, by scene position. `S4_SLOTS` is that mapping — `S4-1 → espace`, `S4-2 → rythme`, `S4-3 → equipe`, `S4-4 → manager`, `S4-5 → irritant`, `S4-6 → vendredi`. The `env` strings are written to drop straight into a French sentence in the `_voyage` block, so they are lowercase noun phrases with no trailing period.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_bank.py`:

```python
def test_session_4_header():
    s4 = _session("4")
    assert s4["title"] == "Le cadre qui te permet de te révéler"
    assert s4["subtitle"] == "Pas le métier — l'environnement · 6 situations"
    assert s4["duration"] == "15 min"
    assert [i["id"] for i in s4["items"]] == [f"S4-{k}" for k in range(1, 7)]
    assert [b["key"] for b in s4["billet"]] == [
        "environnement", "vide", "cadre_relationnel", "rythme",
    ]


def test_session_4_every_option_carries_env():
    """score_s4 reads `env` by scene position — a missing one is a KeyError
    at synthesis time, long after the bank was edited."""
    for scene in _session("4")["items"]:
        for option in scene["options"]:
            env = option.get("env")
            assert env, f"{scene['id']}{option['letter']}"
            assert env == env.lower(), env
            assert not env.endswith("."), env
            assert 1 <= len(env.split()) <= 5, env
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_bank.py::test_session_4_header -v`
Expected: FAIL — `StopIteration`

- [ ] **Step 3: Write session 4**

```python
_SESSION_4 = {
    "n": "4",
    "title": "Le cadre qui te permet de te révéler",
    "subtitle": "Pas le métier — l'environnement · 6 situations",
    "intro": [
        "On arrive à la session qui change tout.",
        "Pas le métier. Pas le secteur. Pas la fiche de poste. Le cadre.",
        "Certains s'épanouissent dans le bruit et le mouvement. "
        "D'autres ont besoin de silence et de profondeur. "
        "Ni mieux, ni moins bien. Juste différent.",
        "Et pourtant, être dans un cadre qui ne te correspond pas, "
        "c'est l'une des causes les plus silencieuses d'épuisement professionnel.",
    ],
    "outro": [],
    "duration": "15 min",
    "kind": KIND_SCENES,
    "items": [
        {
            "id": "S4-1",
            "title": "L'espace idéal",
            "subtitle": "Le bureau de tes rêves",
            "narrative": ["Si tu pouvais choisir ton espace de travail idéal,"],
            "question": "Lequel de ces espaces t'attire instinctivement ?",
            "options": [
                {"letter": "A", "label": "Bureau fermé calme",
                 "text": "Un bureau fermé, calme, à toi. Lumière naturelle. "
                         "Tu peux fermer la porte.",
                 "plain": "un bureau fermé et calme, où tu peux fermer la porte",
                 "env": "bureau fermé et calme"},
                {"letter": "B", "label": "Open space vivant",
                 "text": "Un open space vivant, au milieu des autres. "
                         "L'énergie collective te porte.",
                 "plain": "un open space vivant, l'énergie collective te porte",
                 "env": "open space vivant"},
                {"letter": "C", "label": "Espace flexible",
                 "text": "Un espace flexible — bureau le matin, café, télétravail. "
                         "La variété te stimule.",
                 "plain": "un espace flexible, la variété te stimule",
                 "env": "espace flexible"},
                {"letter": "D", "label": "En mouvement / terrain",
                 "text": "Un espace en mouvement — chantier, terrain, déplacements. "
                         "Ton bureau, c'est le monde.",
                 "plain": "en mouvement, ton bureau c'est le monde",
                 "env": "en mouvement, sur le terrain"},
            ],
        },
        {
            "id": "S4-2",
            "title": "La journée parfaite",
            "subtitle": "Le rythme idéal",
            "narrative": ["Si tu pouvais organiser ta journée exactement comme tu le veux,"],
            "question": "Lequel de ces portraits de journée te fait dire « oui, c'est ça » ?",
            "options": [
                {"letter": "A", "label": "Tôt, calme, focus",
                 "text": "Démarrer tôt, dans le calme. Deux heures de concentration. "
                         "Puis réunions, échanges. Rentrer tôt.",
                 "plain": "démarrer tôt dans le calme, puis les échanges",
                 "env": "démarrage tôt, au calme"},
                {"letter": "B", "label": "Démarrer doucement",
                 "text": "Démarrer doucement. Pas à 100% avant 10h. "
                         "Pic d'énergie en fin de matinée ou l'après-midi.",
                 "plain": "démarrer doucement, ton pic d'énergie vient plus tard",
                 "env": "démarrage progressif"},
                {"letter": "C", "label": "Cycles courts intenses",
                 "text": "Des cycles courts et intenses : 90 minutes, vraie pause, "
                         "90 minutes. Alterner les tâches.",
                 "plain": "des cycles courts et intenses avec de vraies pauses",
                 "env": "cycles courts et intenses"},
                {"letter": "D", "label": "Sans horaire fixe",
                 "text": "Sans horaire fixe — tu travailles quand ça vient. "
                         "Tu gères ton énergie, pas ton temps.",
                 "plain": "sans horaire fixe, tu gères ton énergie plutôt que ton temps",
                 "env": "sans horaire fixe"},
            ],
        },
        {
            "id": "S4-3",
            "title": "L'équipe parfaite",
            "subtitle": "Configurations relationnelles",
            "narrative": ["Dans quel type d'équipe tu te sens le mieux ?"],
            "question": "Laquelle te correspond le mieux, toi ?",
            "options": [
                {"letter": "A", "label": "Petite équipe soudée",
                 "text": "Une petite équipe soudée — 4 à 6 personnes. "
                         "Tu te connais, tu te fais confiance.",
                 "plain": "une petite équipe soudée où on se connaît",
                 "env": "petite équipe soudée"},
                {"letter": "B", "label": "Seul(e) + référents",
                 "text": "Seul(e) avec un ou deux référents. Autonomie, "
                         "mais points réguliers avec quelqu'un de solide.",
                 "plain": "autonome, avec un ou deux référents solides",
                 "env": "autonomie avec un référent"},
                {"letter": "C", "label": "Grande équipe diverse",
                 "text": "Une grande équipe diverse. Beaucoup de profils, "
                         "d'interactions, de points de vue.",
                 "plain": "une grande équipe, beaucoup de profils et d'interactions",
                 "env": "grande équipe diverse"},
                {"letter": "D", "label": "Clarté des rôles",
                 "text": "Peu importe la taille — ce qui compte, c'est la clarté des rôles. "
                         "Qui fait quoi.",
                 "plain": "peu importe la taille, ce sont les rôles clairs qui comptent",
                 "env": "des rôles clairs"},
            ],
        },
        {
            "id": "S4-4",
            "title": "Le manager qu'on n'oublie pas",
            "subtitle": "Ce qui t'a permis de te révéler",
            "narrative": [
                "Pense à un adulte (prof, animateur, parent, entraîneur...) "
                "avec qui tu as vraiment pu être toi-même et donner le meilleur.",
            ],
            "question": "Qu'est-ce qui faisait que ça marchait ?",
            "options": [
                {"letter": "A", "label": "Confiance — essai/erreur",
                 "text": "Il/elle te faisait confiance. Te laissait essayer, rater, recommencer. "
                         "Sans surveillance.",
                 "plain": "on te laissait essayer, rater et recommencer",
                 "env": "confiance et droit à l'essai"},
                {"letter": "B", "label": "Exigeant",
                 "text": "Il/elle t'exigeait. Attendait plus que tu ne te croyais capable.",
                 "plain": "on attendait de toi plus que tu ne t'en croyais capable",
                 "env": "exigence et défi"},
                {"letter": "C", "label": "Voyait la personne",
                 "text": "Il/elle te voyait. Pas juste ta production — toi. Ce que tu traversais.",
                 "plain": "on te voyait toi, pas seulement ce que tu produisais",
                 "env": "attention à la personne"},
                {"letter": "D", "label": "Vision claire / cap",
                 "text": "Il/elle savait où aller. Vision claire, décisions difficiles. "
                         "Tu pouvais faire confiance au cap.",
                 "plain": "on savait où aller et tu pouvais faire confiance au cap",
                 "env": "un cap clair"},
            ],
        },
        {
            "id": "S4-5",
            "title": "La réunion de trop",
            "subtitle": "Ce qui épuise vs ce qui recharge",
            "narrative": [
                "Parmi ces situations, laquelle te pèse le plus ?",
                "Celle qui, à la fin de la journée, te laisse vraiment vidé(e) ?",
            ],
            "question": "Laquelle te pèse le plus ?",
            "options": [
                {"letter": "A", "label": "Réunions longues/bruyantes",
                 "text": "Les réunions longues avec trop de monde, trop de bruit. "
                         "Tu ressors épuisé(e).",
                 "plain": "les réunions longues et bruyantes t'épuisent",
                 "env": "les réunions longues et bruyantes"},
                {"letter": "B", "label": "Interruptions constantes",
                 "text": "Être constamment interrompu(e). Les notifications, "
                         "les « t'as 5 minutes ? ».",
                 "plain": "être constamment interrompu",
                 "env": "les interruptions constantes"},
                {"letter": "C", "label": "Relations tendues/floues",
                 "text": "Les relations tendues ou floues. "
                         "Sentir une tension non dite dans l'équipe.",
                 "plain": "les tensions non dites dans l'équipe",
                 "env": "les tensions non dites"},
                {"letter": "D", "label": "Absence de sens",
                 "text": "L'absence de sens visible. Des tâches dont tu ne vois pas la finalité.",
                 "plain": "des tâches dont tu ne vois pas la finalité",
                 "env": "les tâches sans finalité"},
            ],
        },
        {
            "id": "S4-6",
            "title": "Le vendredi soir",
            "subtitle": "Bilan énergétique de la semaine",
            "narrative": ["C'est vendredi soir. La semaine se termine."],
            "question": "Comment tu fermes la semaine ?",
            "options": [
                {"letter": "A", "label": "Contente des cases cochées",
                 "text": "Content(e) de ce que tu as produit. Des choses abouties, terminées. "
                         "Tu peux cocher des cases.",
                 "plain": "content d'avoir des choses terminées",
                 "env": "des choses terminées"},
                {"letter": "B", "label": "Fatigué(e) mais rechargé(e)",
                 "text": "Fatigué(e) mais rechargé(e). De bonnes interactions, "
                         "des apprentissages. La fatigue est bonne.",
                 "plain": "fatigué mais rechargé par les échanges",
                 "env": "fatigue mais recharge"},
                {"letter": "C", "label": "Besoin de calme",
                 "text": "Besoin de calme et de solitude. Les échanges de la semaine "
                         "demandent un grand silence.",
                 "plain": "besoin de calme après les échanges de la semaine",
                 "env": "besoin de calme"},
                {"letter": "D", "label": "Sentiment d'inachèvement",
                 "text": "Avec un sentiment d'inachèvement. "
                         "Tu vois déjà ce qu'il reste à faire.",
                 "plain": "tu vois déjà ce qu'il reste à faire",
                 "env": "sentiment d'inachèvement"},
            ],
        },
    ],
    "billet": [
        {"key": "environnement", "label": "Je me révèle dans un environnement :"},
        {"key": "vide", "label": "Ce qui me vide, c'est :"},
        {"key": "cadre_relationnel",
         "label": "Le cadre relationnel dans lequel je donne le meilleur :"},
        {"key": "rythme", "label": "Mon rythme naturel ressemble à :"},
    ],
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_bank.py -v -k "not [5] and not styles_are_assigned"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/bank.py backend/tests/test_voyage_bank.py
git commit -m "feat(voyage): session 4, the environment slots"
```

---

## Task 8: Session 5 — risk and meaning

**Files:**
- Modify: `backend/app/services/voyage/bank.py`
- Test: `backend/tests/test_voyage_bank.py` (append)

**Interfaces:**
- Consumes: `RISK_LEVELS` (task 1).
- Produces: `_SESSION_5`, and `SESSIONS` complete with all six entries.

Two tag registers here, both fixed by contract § A.3:

- `risk` on `S5-1` is one of `RISK_LEVELS` exactly (capitalised — the manual's own casing, and `score_s5` passes it straight through to the counselor sheet). On `S5-2` and `S5-3` it is a free lowercase clause.
- `sens` on `S5-4/5/6` is a **noun phrase** (« l'injustice », « le temps ») and on `S5-7` a **third-person clause** (« elle crée »). The register differs because these strings land in different sentences of the `_voyage` block: « Ce qui la met en colère : l'injustice » versus « Se sent vivant(e) quand : elle crée ».

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_bank.py`:

```python
def test_session_5_header():
    s5 = _session("5")
    assert s5["title"] == "Ton rapport à ce qui n'existe pas encore"
    assert s5["subtitle"] == "Risque · Sens · 7 situations"
    assert s5["duration"] == "20 min"
    assert [i["id"] for i in s5["items"]] == [f"S5-{k}" for k in range(1, 8)]
    assert [b["key"] for b in s5["billet"]] == ["risque", "colere", "trace", "vivant"]


def test_s5_1_risk_values_are_the_four_levels():
    letters = {o["letter"]: o["risk"] for o in bank.item("S5-1")["options"]}
    assert letters == {"A": "Fort", "B": "Modéré", "C": "Calculé", "D": "Faible"}
    assert set(letters.values()) == set(bank.RISK_LEVELS)


def test_s5_2_and_s5_3_risk_labels_are_free_lowercase():
    for item_id in ("S5-2", "S5-3"):
        for option in bank.item(item_id)["options"]:
            label = option["risk"]
            assert label == label.lower(), f"{item_id}{option['letter']}: {label}"
            assert label not in bank.RISK_LEVELS


def test_s5_sens_registers():
    """S5-4/5/6 are noun phrases; S5-7 is a third-person clause."""
    for item_id in ("S5-4", "S5-5", "S5-6"):
        for option in bank.item(item_id)["options"]:
            assert option["sens"], f"{item_id}{option['letter']}"
            assert not option["sens"].startswith("elle "), item_id
    for option in bank.item("S5-7")["options"]:
        assert option["sens"].startswith("elle "), option["letter"]


def test_bank_totals():
    assert len(bank.SESSIONS) == 6
    assert [s["n"] for s in bank.SESSIONS] == list(bank.SESSION_IDS)
    assert len(bank.all_item_ids()) == 53
    assert len(set(bank.all_item_ids())) == 53
    assert sum(len(s["billet"]) for s in bank.SESSIONS) == 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_bank.py::test_session_5_header -v`
Expected: FAIL — `StopIteration`

- [ ] **Step 3: Write session 5 and complete `SESSIONS`**

```python
_SESSION_5 = {
    "n": "5",
    "title": "Ton rapport à ce qui n'existe pas encore",
    "subtitle": "Risque · Sens · 7 situations",
    "intro": [
        "Bienvenue en Session 5. La dernière avant ton portrait.",
        "Les fois précédentes, on a exploré qui tu es, ce qui compte pour toi, "
        "comment tu fonctionnes, et dans quel monde tu te révèles.",
        "Aujourd'hui, on regarde devant. Dans l'inconnu. "
        "Dans ce qui n'existe pas encore. Dans ce que tu es prêt(e) à risquer pour y arriver.",
        "Et on regarde aussi le sens. Pas le sens qu'on te raconte. "
        "Celui qui te fait vraiment lever le matin, ou te garder éveillé(e) le soir.",
    ],
    "outro": [
        "Voilà. C'est fait. Cinq sessions. Des dizaines de choix. "
        "Des petites fenêtres ouvertes sur toi-même.",
    ],
    "duration": "20 min",
    "kind": KIND_SCENES,
    "items": [
        {
            "id": "S5-1",
            "title": "La porte entrouverte",
            "subtitle": "Saisir ou laisser passer",
            "narrative": [
                "Une opportunité se présente. Pas complètement sûre. "
                "Pas complètement claire.",
                "C'est un peu flou, un peu risqué. Ça pourrait être génial. "
                "Ça pourrait ne mener nulle part.",
            ],
            "question": "Ton premier réflexe — pas ta décision raisonnée.",
            "options": [
                {"letter": "A", "label": "Fonce",
                 "text": "Tu y vas. Le risque de rater quelque chose de grand est pire "
                         "que le risque d'échouer.",
                 "plain": "tu y vas, rater une occasion serait pire qu'échouer",
                 "risk": "Fort"},
                {"letter": "B", "label": "Attend",
                 "text": "Tu attends. Tu observes, tu te renseignes. Si ça se confirme, "
                         "tu avanceras.",
                 "plain": "tu observes et tu avanceras si ça se confirme",
                 "risk": "Modéré"},
                {"letter": "C", "label": "Calcule",
                 "text": "Tu calcules. Pour/contre, probabilités, avis de confiance. "
                         "Pas de risque inconsidéré.",
                 "plain": "tu calcules, pas de risque inconsidéré",
                 "risk": "Calculé"},
                {"letter": "D", "label": "Passe son chemin",
                 "text": "Tu passes ton chemin. Trop flou. Tu préfères ce que tu connais, "
                         "ce que tu maîtrises.",
                 "plain": "tu préfères ce que tu connais et maîtrises",
                 "risk": "Faible"},
            ],
        },
        {
            "id": "S5-2",
            "title": "L'échec possible",
            "subtitle": "Le rapport à l'échec public",
            "narrative": [
                "Tu te lances dans un projet important. Ça peut marcher. Ça peut échouer.",
                "Si ça échoue, ce ne sera pas invisible. Des gens le sauront.",
            ],
            "question": "L'échec potentiel, sous les yeux des autres. Comment tu vis ça ?",
            "options": [
                {"letter": "A", "label": "Ça stresse",
                 "text": "Ça me stresse. L'idée d'échouer devant les autres, "
                         "d'être jugé(e), de perdre la face.",
                 "plain": "échouer devant les autres te stresse",
                 "risk": "l'échec public l'inquiète"},
                {"letter": "B", "label": "Ça fait partie du jeu",
                 "text": "Ça fait partie du jeu. Si tu ne rates jamais rien, "
                         "c'est que tu ne tentes rien d'assez grand.",
                 "plain": "rater fait partie du jeu",
                 "risk": "l'échec fait partie du jeu"},
                {"letter": "C", "label": "Apprendre et recommencer",
                 "text": "Je veux tout faire pour que ça marche, mais si ça rate, "
                         "j'analyserai, j'apprendrai, je recommencerai.",
                 "plain": "si ça rate, tu analyses et tu recommences",
                 "risk": "elle analyse et recommence"},
                {"letter": "D", "label": "Ne pas y penser",
                 "text": "Je ne veux pas y penser. Je préfère me concentrer sur la réussite.",
                 "plain": "tu préfères te concentrer sur la réussite",
                 "risk": "elle préfère ne pas y penser"},
            ],
        },
        {
            "id": "S5-3",
            "title": "Le flou",
            "subtitle": "La tolérance à l'ambiguïté",
            "narrative": [
                "Tu commences une nouvelle mission. Les objectifs sont clairs.",
                "Mais la route pour y arriver… personne ne la connaît vraiment.",
                "Tu vas devoir inventer, tâtonner, avancer sans filet.",
            ],
            "question": "Ta réaction naturelle — pas idéale, naturelle.",
            "options": [
                {"letter": "A", "label": "Inconfortable",
                 "text": "C'est inconfortable. J'aime savoir où je vais, comment j'y vais. "
                         "Le flou me paralyse presque.",
                 "plain": "le flou te paralyse presque",
                 "risk": "le flou la bloque"},
                {"letter": "B", "label": "Excitant",
                 "text": "C'est excitant. Le chemin à inventer, les surprises, "
                         "les découvertes — c'est ça qui est intéressant.",
                 "plain": "le chemin à inventer, c'est ça qui t'intéresse",
                 "risk": "le flou l'attire"},
                {"letter": "C", "label": "Variable selon contexte",
                 "text": "Ça dépend. Parfois ça me stimule, parfois ça m'angoisse. "
                         "J'ai besoin d'un équilibre.",
                 "plain": "parfois ça te stimule, parfois ça t'angoisse",
                 "risk": "le flou dépend du contexte"},
                {"letter": "D", "label": "Crée son propre cadre",
                 "text": "Je vais créer mon propre cadre. Jalons, checkpoints. "
                         "Je réduis le flou moi-même.",
                 "plain": "tu réduis le flou en créant ton propre cadre",
                 "risk": "elle crée son propre cadre"},
            ],
        },
        {
            "id": "S5-4",
            "title": "Ce qui te met en colère",
            "subtitle": "La valeur bafouée — le sens révélé",
            "narrative": [
                "Qu'est-ce qui, dans le monde, te met vraiment en colère ?",
                "Pas énervé(e). Pas agacé(e). En colère. Jusqu'au fond.",
            ],
            "question": "La réponse honnête — pas celle qui est politiquement correcte.",
            "options": [
                {"letter": "A", "label": "L'injustice",
                 "text": "L'injustice. Quand les plus faibles sont écrasés, "
                         "quand les règles ne s'appliquent pas à tout le monde.",
                 "plain": "l'injustice te met en colère",
                 "sens": "l'injustice"},
                {"letter": "B", "label": "La bêtise",
                 "text": "La bêtise. L'incompétence, les décisions prises sans réflexion, "
                         "sans penser aux conséquences.",
                 "plain": "la bêtise et les décisions sans réflexion te mettent en colère",
                 "sens": "la bêtise"},
                {"letter": "C", "label": "L'indifférence",
                 "text": "L'indifférence. Quand les gens pourraient aider et ne font rien.",
                 "plain": "l'indifférence te met en colère",
                 "sens": "l'indifférence"},
                {"letter": "D", "label": "Le gâchis",
                 "text": "Le gâchis. De talent, de temps, de ressources. "
                         "Quand on pourrait faire quelque chose de beau.",
                 "plain": "le gâchis de talent et de temps te met en colère",
                 "sens": "le gâchis"},
                {"letter": "E", "label": "La malhonnêteté",
                 "text": "La malhonnêteté. Les mensonges, les promesses non tenues.",
                 "plain": "la malhonnêteté te met en colère",
                 "sens": "la malhonnêteté"},
                {"letter": "F", "label": "La violence",
                 "text": "La violence. La force utilisée contre la faiblesse, "
                         "l'écrasement des plus vulnérables.",
                 "plain": "la violence contre les plus vulnérables te met en colère",
                 "sens": "la violence"},
            ],
        },
        {
            "id": "S5-5",
            "title": "La trace",
            "subtitle": "L'impact souhaité",
            "narrative": ["À la fin de ta vie professionnelle, tu regardes en arrière."],
            "question": "La trace. Ton rapport à ce qui reste quand tu n'es plus là.",
            "options": [
                {"letter": "A", "label": "Trace visible",
                 "text": "Une trace visible. Des réalisations concrètes, "
                         "que quelqu'un puisse dire « c'est lui/elle qui a fait ça ».",
                 "plain": "des réalisations concrètes qu'on puisse te attribuer",
                 "sens": "une trace visible"},
                {"letter": "B", "label": "Trace dans les gens",
                 "text": "Une trace dans les gens. Des personnes que tu as aidées, "
                         "formées, inspirées.",
                 "plain": "des personnes que tu as aidées et formées",
                 "sens": "une trace dans les gens"},
                {"letter": "C", "label": "Trace dans le système",
                 "text": "Une trace dans le système. Avoir changé une organisation, "
                         "une façon de faire.",
                 "plain": "avoir changé une organisation ou une façon de faire",
                 "sens": "une trace dans le système"},
                {"letter": "D", "label": "Pas besoin de trace",
                 "text": "Pas besoin de trace. Ce qui compte, c'est ce que tu as vécu. "
                         "L'aventure elle-même.",
                 "plain": "ce qui compte c'est ce que tu as vécu",
                 "sens": "pas besoin de trace"},
                {"letter": "E", "label": "Trace discrète",
                 "text": "Une trace discrète. Avoir contribué à quelque chose de plus grand "
                         "que toi, sans que ton nom soit connu.",
                 "plain": "avoir contribué à plus grand que toi, sans ton nom dessus",
                 "sens": "une trace discrète"},
            ],
        },
        {
            "id": "S5-6",
            "title": "Le sacrifice",
            "subtitle": "Jusqu'où pour du sens",
            "narrative": [
                "Parfois, pour que quelque chose ait vraiment du sens, "
                "il faut accepter de sacrifier autre chose.",
            ],
            "question": "Pour quelque chose qui compte vraiment. Jusqu'où tu iras ?",
            "options": [
                {"letter": "A", "label": "Le confort",
                 "text": "Le confort. Accepter de gagner moins, de vivre plus simplement.",
                 "plain": "tu accepterais de gagner moins",
                 "sens": "le confort"},
                {"letter": "B", "label": "La sécurité",
                 "text": "La sécurité. Accepter l'instabilité, "
                         "ne pas savoir de quoi demain sera fait.",
                 "plain": "tu accepterais l'instabilité",
                 "sens": "la sécurité"},
                {"letter": "C", "label": "Le temps",
                 "text": "Le temps. Accepter d'y passer des heures, des soirées, des week-ends.",
                 "plain": "tu y passerais des soirées et des week-ends",
                 "sens": "le temps"},
                {"letter": "D", "label": "Les relations",
                 "text": "Les relations. Accepter que certaines personnes ne comprennent pas, "
                         "s'éloignent.",
                 "plain": "tu accepterais que certains ne comprennent pas",
                 "sens": "les relations"},
                {"letter": "E", "label": "Rien — équilibre",
                 "text": "Rien. Le sens c'est important, mais pas au point de perdre "
                         "ce qui compte déjà. L'équilibre avant tout.",
                 "plain": "pas au point de perdre ce qui compte déjà",
                 "sens": "rien, l'équilibre avant tout"},
            ],
        },
        {
            "id": "S5-7",
            "title": "Là où tu te sens vivant(e)",
            "subtitle": "Synthèse — Ce qui fait battre le cœur",
            "narrative": [
                "Dernière situation. Dernière avant le portrait.",
                "Dans quel genre de moment te sens-tu vraiment, profondément vivant(e) ?",
            ],
            "question": "Sans chercher la bonne réponse. Le moment où tu te sens "
                        "vraiment vivant(e). C'est quoi ?",
            "options": [
                {"letter": "A", "label": "Créer",
                 "text": "Quand tu crées. Quand quelque chose naît de toi, de tes mains, "
                         "de ton imagination.",
                 "plain": "quand quelque chose naît de toi",
                 "sens": "elle crée"},
                {"letter": "B", "label": "Aider",
                 "text": "Quand tu aides. Quand quelqu'un va mieux grâce à toi, "
                         "quand tu vois que tu as compté.",
                 "plain": "quand quelqu'un va mieux grâce à toi",
                 "sens": "elle aide"},
                {"letter": "C", "label": "Comprendre",
                 "text": "Quand tu comprends. Quand les pièces s'assemblent, "
                         "quand tu saisis quelque chose de nouveau.",
                 "plain": "quand les pièces s'assemblent",
                 "sens": "elle comprend"},
                {"letter": "D", "label": "Gagner",
                 "text": "Quand tu gagnes. Quand tu réussis quelque chose de difficile, "
                         "que tu arrives là où peu arrivent.",
                 "plain": "quand tu réussis là où peu arrivent",
                 "sens": "elle gagne"},
                {"letter": "E", "label": "Harmonie",
                 "text": "Quand tu es en harmonie. Quand tout est à sa place, "
                         "que tu es en phase avec toi-même.",
                 "plain": "quand tout est à sa place",
                 "sens": "elle est en harmonie"},
                {"letter": "F", "label": "Explorer",
                 "text": "Quand tu explores. Quand tu découvres, "
                         "quand tu vas là où tu n'es jamais allé(e).",
                 "plain": "quand tu vas là où tu n'es jamais allé",
                 "sens": "elle explore"},
            ],
        },
    ],
    "billet": [
        {"key": "risque", "label": "Face au risque, je suis plutôt :"},
        {"key": "colere", "label": "Ce qui me met en colère, c'est :"},
        {"key": "trace", "label": "La trace que je veux laisser, c'est :"},
        {"key": "vivant", "label": "Je me sens vivant(e) quand :"},
    ],
}

SESSIONS: list[dict] = [
    _SESSION_0, _SESSION_1, _SESSION_2, _SESSION_3, _SESSION_4, _SESSION_5,
]
```

Delete the earlier partial `SESSIONS` assignments from tasks 3–7 — there must be exactly one.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_bank.py -v -k "not styles_are_assigned and not bank_totals"`
Expected: PASS. `test_bank_totals` and `test_session_3_styles_...` need `all_item_ids()` / `option()`, which task 9 adds.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/bank.py backend/tests/test_voyage_bank.py
git commit -m "feat(voyage): session 5, risk and meaning — the bank is complete"
```

---

## Task 9: Bank lookups and the `public()` view

**Files:**
- Modify: `backend/app/services/voyage/bank.py` (append, after `SESSIONS`)
- Test: `backend/tests/test_voyage_bank.py` (append)

**Interfaces:**
- Consumes: `SESSIONS`, `PUBLIC_STRIP` (tasks 1–8).
- Produces: `public()`, `sessions()`, `session(n)`, `items(n)`, `item(item_id)`, `item_ids(n)`, `all_item_ids()`, `option(item_id, letter)`, `billet_keys(n)`, `validate_answer(item_id, value)`.

`public()` is one of the three places the invariant "the candidate never sees a score or a trait name" is actually enforced. It deep-copies and strips, and its test walks the **JSON-serialised** payload — because that is the form the browser receives, and because a tuple that survives stripping would serialise into a list and go unnoticed by a shallower check.

`validate_answer()` is the rule `PUT /api/voyage/responses` will enforce in phase 1. It lives here, next to the data it validates against, so that adding a session cannot leave the validator behind.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_bank.py`:

```python
def test_public_strips_every_weight_at_every_depth():
    payload = json.loads(json.dumps(bank.public()))

    def walk(node, path="$"):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key not in bank.PUBLIC_STRIP, f"{path}.{key} leaked"
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(payload)
    assert payload["scoring_version"] == bank.SCORING_VERSION
    assert len(payload["sessions"]) == 6
    assert "AXES" not in payload and "axes" not in payload


def test_public_keeps_every_piece_of_text_the_ui_needs():
    payload = bank.public()
    s1 = next(s for s in payload["sessions"] if s["n"] == "1")
    scene = s1["items"][0]
    assert scene["title"] == "La cabane"
    assert scene["options"][0]["label"] == "Les architectes"
    assert scene["options"][0]["text"].startswith("Ceux qui dessinaient")
    assert scene["options"][0]["letter"] == "A"


def test_public_is_a_deep_copy():
    payload = bank.public()
    payload["sessions"][0]["items"][0]["text"] = "MUTATED"
    assert bank.SESSIONS[0]["items"][0]["text"] != "MUTATED"


def test_lookups():
    assert bank.session("0")["title"] == "Dans 10 ans"
    with pytest.raises(KeyError):
        bank.session("9")
    assert len(bank.items("1")) == 6
    assert bank.item("S1-1")["title"] == "La cabane"
    assert bank.item("S9-9") is None
    assert bank.item_ids("4") == [f"S4-{k}" for k in range(1, 7)]
    assert bank.option("S1-1", "B")["label"] == "Les bâtisseurs"
    assert bank.option("S1-1", "Z") is None
    assert bank.option("S0-01", "A") is None      # checklist items have no options
    assert bank.billet_keys("5") == ["risque", "colere", "trace", "vivant"]


def test_all_item_ids_is_session_order_then_item_order():
    ids = bank.all_item_ids()
    assert ids[0] == "S0-01"
    assert ids[19] == "S0-20"
    assert ids[20] == "S1-1"
    assert ids[-1] == "S5-7"


def test_validate_answer():
    # session 0 takes booleans, and only booleans
    assert bank.validate_answer("S0-01", True) is True
    assert bank.validate_answer("S0-01", False) is True
    assert bank.validate_answer("S0-01", "A") is False
    assert bank.validate_answer("S0-01", 1) is False
    assert bank.validate_answer("S0-01", "oui") is False
    # scenes take a letter that exists on that scene
    assert bank.validate_answer("S1-6", "H") is True
    assert bank.validate_answer("S1-1", "H") is False    # S1-1 stops at F
    assert bank.validate_answer("S1-1", "a") is False    # case-sensitive
    assert bank.validate_answer("S1-1", True) is False
    # unknown ids
    assert bank.validate_answer("S9-1", "A") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_bank.py::test_lookups -v`
Expected: FAIL — `AttributeError: module 'app.services.voyage.bank' has no attribute 'session'`

- [ ] **Step 3: Write the lookups**

Append to `backend/app/services/voyage/bank.py`:

```python
# ── Lookups ──────────────────────────────────────────────────────────────────

def sessions() -> list[dict]:
    """All six sessions, in play order."""
    return SESSIONS


def session(n: str) -> dict:
    """One session. Raises KeyError on an unknown id."""
    for entry in SESSIONS:
        if entry["n"] == n:
            return entry
    raise KeyError(n)


def items(n: str) -> list[dict]:
    return session(n)["items"]


def item_ids(n: str) -> list[str]:
    return [entry["id"] for entry in items(n)]


def all_item_ids() -> list[str]:
    """The 53 ids, session order then item order."""
    return [entry["id"] for s in SESSIONS for entry in s["items"]]


def item(item_id: str) -> dict | None:
    """One item by id, or None. None rather than KeyError: item ids arrive from
    the client, and an unknown one is a 400, not a crash."""
    for s in SESSIONS:
        for entry in s["items"]:
            if entry["id"] == item_id:
                return entry
    return None


def option(item_id: str, letter: str) -> dict | None:
    """One option of a scene, or None — including when the item is a checklist
    item, which has no options at all."""
    entry = item(item_id)
    if entry is None:
        return None
    for candidate in entry.get("options", []):
        if candidate["letter"] == letter:
            return candidate
    return None


def billet_keys(n: str) -> list[str]:
    return [field["key"] for field in session(n)["billet"]]


def validate_answer(item_id: str, value) -> bool:
    """Is `value` an acceptable answer to `item_id`?

    The rule PUT /api/voyage/responses enforces. Deliberately strict about
    booleans: `1` and `"oui"` are rejected, because a truthy check here would
    let a client's stray string score as OUI on every axis the item loads.
    """
    entry = item(item_id)
    if entry is None:
        return False
    if "options" not in entry:                      # session 0 checklist item
        return value is True or value is False
    if not isinstance(value, str):
        return False
    return any(candidate["letter"] == value for candidate in entry["options"])


# ── The public view ──────────────────────────────────────────────────────────

def _strip(node):
    """Deep copy with every PUBLIC_STRIP key removed, at every depth."""
    if isinstance(node, dict):
        return {k: _strip(v) for k, v in node.items() if k not in PUBLIC_STRIP}
    if isinstance(node, (list, tuple)):
        return [_strip(v) for v in node]
    return node


def public() -> dict:
    """The bank as GET /api/voyage/bank serves it: text only, no weights.

    A deep copy — a caller mutating the result must not touch SESSIONS.

    AXES is deliberately absent. Axis names are scoring output, and the person
    never sees an axis, a trait or a framework name (spec decision 7). The same
    reasoning removes `plain`: it is the model's paraphrase of an option, in a
    register the UI never uses.
    """
    return {"scoring_version": SCORING_VERSION, "sessions": _strip(SESSIONS)}
```

- [ ] **Step 4: Run the whole bank suite**

Run: `cd backend && pytest tests/test_voyage_bank.py -v`
Expected: PASS — every test, including the ones deferred in tasks 6 and 8.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/bank.py backend/tests/test_voyage_bank.py
git commit -m "feat(voyage): bank lookups and the weight-free public view"
```

---

## Task 10: Scoring module — constants and completeness helpers

**Files:**
- Create: `backend/app/services/voyage/scoring.py`
- Test: `backend/tests/test_voyage_scoring.py`

**Interfaces:**
- Consumes: `bank.SESSIONS`, `bank.item_ids`, `bank.item`, `bank.option`, `bank.SESSION_IDS`.
- Produces: `STAGE_S0`, `STAGE_VALIDATED`, `STAGES`, `TENSION_BAND`, `TENSION_MIN_ITEMS`, `BIG5_HIGH`, `BIG5_LOW`, `LEVEL_HIGH`, `LEVEL_MID`, `LEVEL_LOW`, `INTRO_EXTRA`, `missing_items()`, `session_complete()`, `completeness()`, `chosen_option()`.

Every function in this module takes the **full** responses object — `{"answers": {...}, "billets": {...}}` — never a bare answers dict. One shape from the model, through the routes, into scoring, out to the synthesis: nothing in the chain has to remember to unwrap.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_voyage_scoring.py`:

```python
"""Scoring — the arithmetic behind the counselor's synthesis sheet.

Every number a counselor reads and every plain-French line a prompt receives is
produced here, from the answers alone. There is no model in this path, so these
tests are the whole of its correctness.
"""
import pytest

from app.services.voyage import bank, scoring


def _answers(**overrides):
    """A complete answer set: every S0 item False, every scene on option A."""
    answers = {item_id: False for item_id in bank.item_ids("0")}
    for n in ("1", "2", "3", "4", "5"):
        for item_id in bank.item_ids(n):
            answers[item_id] = "A"
    answers.update(overrides)
    return {"answers": answers, "billets": {}}


def test_module_constants():
    assert scoring.STAGES == (scoring.STAGE_S0, scoring.STAGE_VALIDATED)
    assert scoring.TENSION_BAND == (-2, 2)
    assert scoring.TENSION_MIN_ITEMS == 2
    assert (scoring.BIG5_HIGH, scoring.BIG5_LOW) == (2, -2)
    assert (scoring.LEVEL_HIGH, scoring.LEVEL_MID, scoring.LEVEL_LOW) == (
        "Élevé", "Moyen", "Faible",
    )
    assert set(scoring.INTRO_EXTRA) == {"high", "mid", "low"}


def test_missing_items_and_session_complete():
    empty = {"answers": {}, "billets": {}}
    assert scoring.missing_items(empty, "0") == bank.item_ids("0")
    assert scoring.session_complete(empty, "0") is False

    full = _answers()
    assert scoring.missing_items(full, "0") == []
    assert scoring.session_complete(full, "0") is True

    partial = {"answers": {"S0-01": True}, "billets": {}}
    assert "S0-01" not in scoring.missing_items(partial, "0")
    assert len(scoring.missing_items(partial, "0")) == 19


def test_missing_items_rejects_an_invalid_value():
    """A stored answer that no longer validates leaves the session incomplete
    rather than scoring as something arbitrary."""
    bad = {"answers": {item_id: "Z" for item_id in bank.item_ids("1")}, "billets": {}}
    assert scoring.missing_items(bad, "1") == bank.item_ids("1")


def test_completeness_is_keyed_by_session_id():
    assert scoring.completeness({"answers": {}, "billets": {}}) == {
        "0": False, "1": False, "2": False, "3": False, "4": False, "5": False,
    }
    assert scoring.completeness(_answers()) == {
        "0": True, "1": True, "2": True, "3": True, "4": True, "5": True,
    }


def test_chosen_option():
    responses = _answers(**{"S1-1": "C"})
    assert scoring.chosen_option(responses, "S1-1")["label"] == "Les prospecteurs"
    assert scoring.chosen_option({"answers": {}, "billets": {}}, "S1-1") is None
    assert scoring.chosen_option(responses, "S0-01") is None   # checklist, no options
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_scoring.py -v`
Expected: FAIL — `ImportError: cannot import name 'scoring' from 'app.services.voyage'`

- [ ] **Step 3: Write the module head**

Create `backend/app/services/voyage/scoring.py`:

```python
"""Scoring the voyage — arithmetic only, no model, no I/O.

Deterministic by design. The counselor's paper manual adds columns of points;
this module does the same additions, so the same answers always produce the same
sheet and a correction to a scoring table is a code review, not a re-run.

Scores are never stored. `Voyage.synthesis()` calls `synthesize()` on read, so a
fix to a table takes effect for every voyage at once; the portrait keeps a
snapshot of the sheet it was actually written from, which is what makes an old
portrait explainable after a table changes.

`bank` is the only import. Nothing here mutates it.
"""
from . import bank

STAGE_S0 = "s0"
STAGE_VALIDATED = "validated"
STAGES = (STAGE_S0, STAGE_VALIDATED)

# An axis whose resultant lands in this band is an ambivalence the counselor
# explores in restitution — the manual weights those ×1.5 in the portrait.
TENSION_BAND = (-2, 2)

# An axis carried by a single item is inside the band for everyone: one OUI puts
# it at +1, one NON at -1, and it can never leave. A1 (Mobilité) is that axis.
# Flagging it would print a tension on every sheet ever produced (spec errata 17a).
TENSION_MIN_ITEMS = 2

BIG5_HIGH = 2
BIG5_LOW = -2
LEVEL_HIGH, LEVEL_MID, LEVEL_LOW = "Élevé", "Moyen", "Faible"

# Plain French for the extraversion net. Never the words the leak check bans —
# "introversion" and "extraversion" are trait names and stay on the counselor's
# sheet only.
INTRO_EXTRA = {
    "high": "plutôt tourné(e) vers les autres",
    "mid": "à l'aise dans les deux registres",
    "low": "plutôt tourné(e) vers l'intérieur",
}


# ── Completeness ─────────────────────────────────────────────────────────────

def _answers(responses: dict) -> dict:
    return (responses or {}).get("answers") or {}


def missing_items(responses: dict, n: str) -> list[str]:
    """Item ids of session `n` with no valid answer, in bank order.

    An answer that fails bank.validate_answer counts as missing rather than as
    present-but-wrong: the alternative is scoring a stale letter from a bank
    revision that removed it.
    """
    given = _answers(responses)
    return [
        item_id
        for item_id in bank.item_ids(n)
        if item_id not in given or not bank.validate_answer(item_id, given[item_id])
    ]


def session_complete(responses: dict, n: str) -> bool:
    return not missing_items(responses, n)


def completeness(responses: dict) -> dict[str, bool]:
    return {n: session_complete(responses, n) for n in bank.SESSION_IDS}


def chosen_option(responses: dict, item_id: str) -> dict | None:
    """The option dict the person picked, or None if unanswered or not a scene."""
    value = _answers(responses).get(item_id)
    if not isinstance(value, str):
        return None
    return bank.option(item_id, value)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_scoring.py -v`
Expected: PASS — 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/scoring.py backend/tests/test_voyage_scoring.py
git commit -m "feat(voyage): scoring constants and completeness helpers"
```

---

## Task 11: `score_s0` — the bipolar axes and the tension rule

**Files:**
- Modify: `backend/app/services/voyage/scoring.py`
- Test: `backend/tests/test_voyage_scoring.py` (append)

**Interfaces:**
- Consumes: `bank.AXES`, `bank.axis_items`, `missing_items` (task 10).
- Produces: `score_s0(responses) -> dict | None` returning `{"axes", "tensions", "top3"}`.

The arithmetic, from the manual: each item loading on an axis with sign *s* contributes `+s` when answered OUI and `−s` when answered NON. So `S0-11` (« Avoir un emploi stable ») carries `("A5", -1)`: answering OUI pushes A5 one step toward *Stabilité*, answering NON one step toward *Risque*. `oui` and `non` are counts of contributing items; `resultant` is the signed sum.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_scoring.py`:

```python
def test_score_s0_is_none_until_the_session_is_complete():
    assert scoring.score_s0({"answers": {"S0-01": True}, "billets": {}}) is None


def test_score_s0_sign_of_a_reversed_item():
    """S0-11 loads A5 negatively. OUI pushes A5 toward stability."""
    oui = scoring.score_s0(_answers(**{"S0-11": True}))
    non = scoring.score_s0(_answers(**{"S0-11": False}))
    # every other A5 item is False, so they each contribute -1 (sign +1, NON)
    assert oui["axes"]["A5"]["resultant"] == non["axes"]["A5"]["resultant"] + 2
    assert oui["axes"]["A5"]["oui"] == 1
    assert oui["axes"]["A5"]["non"] == 3


def test_score_s0_all_false_gives_every_positive_axis_its_full_negative():
    result = scoring.score_s0(_answers())
    # A9 has two items, both sign +1; both NON -> -2
    assert result["axes"]["A9"] == {
        "oui": 0, "non": 2, "resultant": -2, "n_items": 2, "tension": True,
    }
    assert set(result["axes"]) == set(bank.AXES)


def test_a1_is_never_a_tension_even_though_it_always_lands_in_the_band():
    """A1 has one item, so its resultant is always -1 or +1 — inside the band
    for every person alive. Flagging it would weight it x1.5 in every portrait."""
    for value in (True, False):
        result = scoring.score_s0(_answers(**{"S0-08": value}))
        assert result["axes"]["A1"]["n_items"] == 1
        assert result["axes"]["A1"]["resultant"] in (-1, 1)
        assert result["axes"]["A1"]["tension"] is False
        assert all(t["axis"] != "A1" for t in result["tensions"])


def test_tension_band_edges():
    result = scoring.score_s0(_answers())
    for entry in result["axes"].values():
        inside = scoring.TENSION_BAND[0] <= entry["resultant"] <= scoring.TENSION_BAND[1]
        expected = inside and entry["n_items"] >= scoring.TENSION_MIN_ITEMS
        assert entry["tension"] is expected


def test_tensions_are_ordered_by_axis_id_and_carry_plain_wording():
    result = scoring.score_s0(_answers())
    ids = [t["axis"] for t in result["tensions"]]
    assert ids == sorted(ids, key=lambda a: int(a[1:]))
    for entry in result["tensions"]:
        assert set(entry) == {"axis", "resultant", "label", "tension"}
        assert " vs " in entry["tension"]


def test_top3_picks_the_pole_the_sign_points_to():
    """Answer only the A7 items OUI: A7 resolves positive and leads."""
    a7_items = [item_id for item_id, _ in bank.axis_items("A7")]
    result = scoring.score_s0(_answers(**{item_id: True for item_id in a7_items}))
    top = result["top3"][0]
    assert top["axis"] == "A7"
    assert top["pole"] == "pos"
    assert top["label"] == bank.AXES["A7"]["pos"]
    assert top["plain"] == bank.AXES["A7"]["plain_pos"]
    assert len(result["top3"]) <= 3


def test_top3_excludes_zero_and_breaks_ties_by_axis_id():
    result = scoring.score_s0(_answers())
    for entry in result["top3"]:
        assert entry["resultant"] != 0
    magnitudes = [abs(e["resultant"]) for e in result["top3"]]
    assert magnitudes == sorted(magnitudes, reverse=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_scoring.py -k score_s0 -v`
Expected: FAIL — `AttributeError: module 'app.services.voyage.scoring' has no attribute 'score_s0'`

- [ ] **Step 3: Write `score_s0`**

Append to `backend/app/services/voyage/scoring.py`:

```python
# ── Session 0 — the ten bipolar axes ─────────────────────────────────────────

def score_s0(responses: dict) -> dict | None:
    """The manual's page-1 grid: ten axes, their tensions, and the top three.

    Per item loading on an axis with sign s: OUI contributes +s, NON contributes
    -s. `oui` / `non` count contributing items; `resultant` is the signed sum.
    """
    if not session_complete(responses, "0"):
        return None

    given = _answers(responses)
    axes = {}
    for axis_id, meta in bank.AXES.items():
        loadings = bank.axis_items(axis_id)
        oui = sum(1 for item_id, _ in loadings if given[item_id] is True)
        non = len(loadings) - oui
        resultant = sum(
            sign if given[item_id] is True else -sign for item_id, sign in loadings
        )
        axes[axis_id] = {
            "oui": oui,
            "non": non,
            "resultant": resultant,
            "n_items": len(loadings),
            "tension": (
                TENSION_BAND[0] <= resultant <= TENSION_BAND[1]
                and len(loadings) >= TENSION_MIN_ITEMS
            ),
        }

    tensions = [
        {
            "axis": axis_id,
            "resultant": entry["resultant"],
            "label": bank.AXES[axis_id]["label"],
            "tension": bank.AXES[axis_id]["tension"],
        }
        for axis_id, entry in axes.items()
        if entry["tension"]
    ]
    tensions.sort(key=lambda t: int(t["axis"][1:]))

    ranked = [
        (axis_id, entry["resultant"])
        for axis_id, entry in axes.items()
        if entry["resultant"] != 0
    ]
    ranked.sort(key=lambda pair: (-abs(pair[1]), int(pair[0][1:])))
    top3 = []
    for axis_id, resultant in ranked[:3]:
        pole = "pos" if resultant > 0 else "neg"
        meta = bank.AXES[axis_id]
        top3.append({
            "axis": axis_id,
            "resultant": resultant,
            "pole": pole,
            "label": meta[pole],
            "plain": meta[f"plain_{pole}"],
        })

    return {"axes": axes, "tensions": tensions, "top3": top3}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_scoring.py -v`
Expected: PASS — 13 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/scoring.py backend/tests/test_voyage_scoring.py
git commit -m "feat(voyage): score session 0, with the single-item axis excluded"
```

---

## Task 12: `score_riasec` — normalised against computed maxima

**Files:**
- Modify: `backend/app/services/voyage/scoring.py`
- Test: `backend/tests/test_voyage_scoring.py` (append)

**Interfaces:**
- Consumes: `bank.riasec_maxima`, `bank.RIASEC_LETTERS`, `bank.RIASEC_UNIVERS`, `chosen_option`.
- Produces: `score_riasec(responses) -> dict | None` returning `{"scores", "maxima", "normalized", "top3"}`.

The letters have different ceilings — R can reach 12, C only 9 — so raw scores are not comparable across letters. `top3` ranks on `normalized`, and ties break on `RIASEC_LETTERS` order.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_scoring.py`:

```python
def test_score_riasec_is_none_until_session_1_is_complete():
    partial = {"answers": {"S1-1": "A"}, "billets": {}}
    assert scoring.score_riasec(partial) is None


def test_score_riasec_sums_the_chosen_options():
    """All A: S1-1 R1 I1 E1 C1 · S1-2 I2 C1 · S1-3 I2 R1 · S1-4 R2 C1
       · S1-5 R2 C1 · S1-6 I2."""
    result = scoring.score_riasec(_answers())
    assert result["scores"] == {"R": 6, "I": 7, "A": 0, "S": 0, "E": 1, "C": 4}
    assert result["maxima"] == bank.riasec_maxima()


def test_score_riasec_normalizes_against_each_letter_own_ceiling():
    result = scoring.score_riasec(_answers())
    assert result["normalized"]["R"] == round(6 / 12, 3)
    assert result["normalized"]["C"] == round(4 / 9, 3)
    for letter, value in result["normalized"].items():
        assert 0.0 <= value <= 1.0, letter


def test_score_riasec_top3_ranks_on_normalized_not_raw():
    result = scoring.score_riasec(_answers())
    assert len(result["top3"]) == 3
    order = [e["normalized"] for e in result["top3"]]
    assert order == sorted(order, reverse=True)
    assert result["top3"][0]["letter"] == "I"          # 7/11 = 0.636
    assert result["top3"][0]["univers"] == "Investigateur"
    assert set(result["top3"][0]) == {"letter", "univers", "score", "normalized"}


def test_score_riasec_ties_break_on_letter_order():
    """A tie on normalized resolves R I A S E C, never alphabetically or by dict
    insertion — otherwise the same answers could rank differently across runs."""
    result = scoring.score_riasec(_answers())
    letters = [e["letter"] for e in result["top3"]]
    for first, second in zip(letters, letters[1:]):
        n_first = result["normalized"][first]
        n_second = result["normalized"][second]
        if n_first == n_second:
            assert bank.RIASEC_LETTERS.index(first) < bank.RIASEC_LETTERS.index(second)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_scoring.py -k riasec -v`
Expected: FAIL — `AttributeError: ... has no attribute 'score_riasec'`

- [ ] **Step 3: Write `score_riasec`**

```python
# ── Session 1 — RIASEC ───────────────────────────────────────────────────────

def score_riasec(responses: dict) -> dict | None:
    """Holland letters, summed over the six childhood scenes.

    Normalised because the letters have different ceilings: R can reach 12 and C
    only 9, so a raw 9 means "at the top" for C and "three short" for R. `top3`
    therefore ranks on the ratio, never on the raw score.
    """
    if not session_complete(responses, "1"):
        return None

    scores = {letter: 0 for letter in bank.RIASEC_LETTERS}
    for item_id in bank.item_ids("1"):
        option = chosen_option(responses, item_id)
        for letter, points in (option.get("riasec") or {}).items():
            scores[letter] += points

    maxima = bank.riasec_maxima()
    normalized = {
        letter: round(scores[letter] / maxima[letter], 3) if maxima[letter] else 0.0
        for letter in bank.RIASEC_LETTERS
    }

    ranked = sorted(
        bank.RIASEC_LETTERS,
        key=lambda letter: (-normalized[letter], bank.RIASEC_LETTERS.index(letter)),
    )
    top3 = [
        {
            "letter": letter,
            "univers": bank.RIASEC_UNIVERS[letter],
            "score": scores[letter],
            "normalized": normalized[letter],
        }
        for letter in ranked[:3]
    ]

    return {"scores": scores, "maxima": maxima, "normalized": normalized, "top3": top3}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_scoring.py -v`
Expected: PASS — 18 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/scoring.py backend/tests/test_voyage_scoring.py
git commit -m "feat(voyage): RIASEC normalised against each letter's own ceiling"
```

---

## Task 13: `score_s2` — needs and values

**Files:**
- Modify: `backend/app/services/voyage/scoring.py`
- Test: `backend/tests/test_voyage_scoring.py` (append)

**Interfaces:**
- Consumes: `bank.SDT`, `bank.SCHWARTZ`, `chosen_option`.
- Produces: `score_s2(responses) -> dict | None` returning `{"sdt", "sdt_dominant", "schwartz", "schwartz_dominant", "ambivalences"}`.

Counted over **S2-1 … S2-7 only**. Tags carried by options in other sessions are ignored — `S3-4 D` carries a `schwartz` tag and must not reach this tally.

`*_dominant` is a **list of all tied maxima**, never a single winner. The manual gives no tie-break, and inventing one would silently pick a value for the counselor to read aloud.

- [ ] **Step 1: Write the failing test**

```python
def test_score_s2_is_none_until_session_2_is_complete():
    assert scoring.score_s2({"answers": {"S2-1": "A"}, "billets": {}}) is None


def test_score_s2_counts_only_session_2():
    """S3-4 D carries a schwartz tag. It must not reach this tally."""
    result = scoring.score_s2(_answers(**{"S3-4": "D"}))
    without = scoring.score_s2(_answers(**{"S3-4": "A"}))
    assert result["schwartz"] == without["schwartz"]


def test_score_s2_reports_every_key_including_zeros():
    result = scoring.score_s2(_answers())
    assert set(result["sdt"]) == set(bank.SDT)
    assert set(result["schwartz"]) == set(bank.SCHWARTZ)
    assert all(isinstance(v, int) for v in result["schwartz"].values())


def test_score_s2_dominant_is_a_list_of_all_tied_maxima():
    result = scoring.score_s2(_answers())
    top = max(result["sdt"].values())
    expected = [k for k in bank.SDT if result["sdt"][k] == top]
    assert result["sdt_dominant"] == expected
    top_s = max(result["schwartz"].values())
    assert result["schwartz_dominant"] == [
        k for k in bank.SCHWARTZ if result["schwartz"][k] == top_s
    ]


def test_score_s2_ambivalences_is_the_s2_7_choice():
    result = scoring.score_s2(_answers(**{"S2-7": "F"}))
    assert result["ambivalences"] == {
        "item_id": "S2-7",
        "letter": "F",
        "label": "Liberté / Indépendance",
        "plain": "tu veux que ta vie t'appartienne",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_scoring.py -k score_s2 -v`
Expected: FAIL — `AttributeError: ... has no attribute 'score_s2'`

- [ ] **Step 3: Write `score_s2`**

```python
# ── Session 2 — needs (SDT) and values (Schwartz) ────────────────────────────

def _dominant(counts: dict, order) -> list[str]:
    """Every key holding the maximum, in `order`. A list, not a winner.

    The manual names no tie-break, and a counselor reads this aloud: picking one
    of two equals by dict order would put a value in someone's mouth.
    """
    if not counts:
        return []
    top = max(counts.values())
    if top == 0:
        return []
    return [key for key in order if counts.get(key, 0) == top]


def score_s2(responses: dict) -> dict | None:
    """The manual's Session 2 synthesis box, counted over S2-1..S2-7 only."""
    if not session_complete(responses, "2"):
        return None

    sdt = {need: 0 for need in bank.SDT}
    schwartz = {value: 0 for value in bank.SCHWARTZ}
    for item_id in bank.item_ids("2"):
        option = chosen_option(responses, item_id)
        if option.get("sdt"):
            sdt[option["sdt"]] += 1
        for value in option.get("schwartz") or []:
            schwartz[value] += 1

    probe = chosen_option(responses, "S2-7")
    return {
        "sdt": sdt,
        "sdt_dominant": _dominant(sdt, bank.SDT),
        "schwartz": schwartz,
        "schwartz_dominant": _dominant(schwartz, bank.SCHWARTZ),
        "ambivalences": {
            "item_id": "S2-7",
            "letter": probe["letter"],
            "label": probe["label"],
            "plain": probe["plain"],
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_scoring.py -v`
Expected: PASS — 23 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/scoring.py backend/tests/test_voyage_scoring.py
git commit -m "feat(voyage): score session 2, ties reported rather than broken"
```

---

## Task 14: `score_s3` — Big Five nets and cognitive style

**Files:**
- Modify: `backend/app/services/voyage/scoring.py`
- Test: `backend/tests/test_voyage_scoring.py` (append)

**Interfaces:**
- Consumes: `bank.BIG5`, `bank.STYLES`, `chosen_option`, `_dominant` (task 13).
- Produces: `score_s3(responses) -> dict | None` returning `{"big5", "levels", "style", "style_dominant", "intro_extra"}`.

`big5` values are **signed nets**, so « Faible Névrotisme » subtracts. The manual prints no thresholds at all — it just says *Élevé / Moyen / Faible* — so this plan applies ±2 (spec errata 17c), calibrated on the fact that every tag is ±1 and each trait appears on at most seven scenes.

`levels` values and `big5` trait names are **counselor-facing only**. `prompt_context()` never emits either, and task 17 has the test that proves it.

- [ ] **Step 1: Write the failing test**

```python
def test_score_s3_is_none_until_session_3_is_complete():
    assert scoring.score_s3({"answers": {"S3-1": "A"}, "billets": {}}) is None


def test_score_s3_nets_are_signed():
    """All A: nevrotisme picks up -1 from S3-1 A, -1 from S3-3 A, -1 from
    S3-5 A; extraversion +1 from S3-1 A and +1 from S3-3 A, -1 from S3-6 A
    and -1 from S3-7 B... — assert the sign, not a hand-summed total."""
    result = scoring.score_s3(_answers())
    assert set(result["big5"]) == set(bank.BIG5)
    assert result["big5"]["nevrotisme"] < 0

    all_d = _answers(**{f"S3-{k}": "D" for k in range(1, 8)})
    assert scoring.score_s3(all_d)["big5"]["nevrotisme"] > (
        scoring.score_s3(_answers())["big5"]["nevrotisme"]
    )


def test_score_s3_levels_use_the_plus_or_minus_two_thresholds():
    result = scoring.score_s3(_answers())
    for trait, net in result["big5"].items():
        if net >= scoring.BIG5_HIGH:
            assert result["levels"][trait] == scoring.LEVEL_HIGH, trait
        elif net <= scoring.BIG5_LOW:
            assert result["levels"][trait] == scoring.LEVEL_LOW, trait
        else:
            assert result["levels"][trait] == scoring.LEVEL_MID, trait


def test_score_s3_style_counts_only_options_that_carry_one():
    """S3-4 D carries no style. Choosing it must not raise or invent one."""
    result = scoring.score_s3(_answers(**{"S3-4": "D"}))
    assert set(result["style"]) == set(bank.STYLES)
    assert sum(result["style"].values()) == 6      # 7 scenes, one carries no style
    assert result["style_dominant"] == scoring._dominant(result["style"], bank.STYLES)


def test_score_s3_intro_extra_is_plain_french_never_a_trait_name():
    result = scoring.score_s3(_answers())
    assert result["intro_extra"] in scoring.INTRO_EXTRA.values()
    lowered = result["intro_extra"].lower()
    assert "introversion" not in lowered and "extraversion" not in lowered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_scoring.py -k score_s3 -v`
Expected: FAIL — `AttributeError: ... has no attribute 'score_s3'`

- [ ] **Step 3: Write `score_s3`**

```python
# ── Session 3 — Big Five and cognitive style ─────────────────────────────────

def _level(net: int) -> str:
    if net >= BIG5_HIGH:
        return LEVEL_HIGH
    if net <= BIG5_LOW:
        return LEVEL_LOW
    return LEVEL_MID


def score_s3(responses: dict) -> dict | None:
    """The manual's Big Five box, counted over S3-1..S3-7 only.

    Nets, not counts: the manual's « Faible Névrotisme » is a -1 on the same
    trait as « Névrotisme », so reading either as a plain count would score an
    unusually steady person as an unusually anxious one.
    """
    if not session_complete(responses, "3"):
        return None

    big5 = {trait: 0 for trait in bank.BIG5}
    style = {name: 0 for name in bank.STYLES}
    for item_id in bank.item_ids("3"):
        option = chosen_option(responses, item_id)
        for trait, sign in (option.get("big5") or {}).items():
            big5[trait] += sign
        if option.get("style"):
            style[option["style"]] += 1

    extraversion = big5["extraversion"]
    if extraversion >= BIG5_HIGH:
        bucket = "high"
    elif extraversion <= BIG5_LOW:
        bucket = "low"
    else:
        bucket = "mid"

    return {
        "big5": big5,
        "levels": {trait: _level(net) for trait, net in big5.items()},
        "style": style,
        "style_dominant": _dominant(style, bank.STYLES),
        "intro_extra": INTRO_EXTRA[bucket],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_scoring.py -v`
Expected: PASS — 28 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/scoring.py backend/tests/test_voyage_scoring.py
git commit -m "feat(voyage): Big Five nets, signed, with the plus-minus-two levels"
```

---

## Task 15: `score_s4` and `score_s5` — environment, risk, meaning

**Files:**
- Modify: `backend/app/services/voyage/scoring.py`
- Test: `backend/tests/test_voyage_scoring.py` (append)

**Interfaces:**
- Consumes: `bank.S4_SLOTS`, `bank.RISK_LEVELS`, `chosen_option`.
- Produces: `score_s4(responses) -> dict | None` (six string keys), `score_s5(responses) -> dict | None` (seven string keys).

Neither does arithmetic. `score_s4` reads the chosen option's `env` into a slot by scene position; `score_s5` reads `risk` from S5-1/2/3 and `sens` from S5-4/5/6/7. No combination rule is invented across S5-1/2/3 — the manual names all three as sources of "appétence au risque" and gives no formula, so the three labels sit side by side and the counselor reads them together.

- [ ] **Step 1: Write the failing test**

```python
def test_score_s4_maps_scene_position_to_slot():
    assert scoring.score_s4({"answers": {"S4-1": "A"}, "billets": {}}) is None
    result = scoring.score_s4(_answers(**{"S4-1": "D", "S4-5": "B"}))
    assert list(result) == list(bank.S4_SLOTS)
    assert result["espace"] == "en mouvement, sur le terrain"
    assert result["irritant"] == "les interruptions constantes"
    assert all(isinstance(v, str) and v for v in result.values())


def test_score_s5_keys_and_registers():
    assert scoring.score_s5({"answers": {"S5-1": "A"}, "billets": {}}) is None
    result = scoring.score_s5(_answers(**{
        "S5-1": "C", "S5-2": "C", "S5-3": "D",
        "S5-4": "A", "S5-5": "B", "S5-6": "C", "S5-7": "A",
    }))
    assert result == {
        "risque": "Calculé",
        "rapport_echec": "elle analyse et recommence",
        "rapport_flou": "elle crée son propre cadre",
        "valeur_centrale": "l'injustice",
        "trace": "une trace dans les gens",
        "sacrifice": "le temps",
        "vivant": "elle crée",
    }


def test_score_s5_risque_is_one_of_the_four_levels():
    for letter in "ABCD":
        result = scoring.score_s5(_answers(**{"S5-1": letter}))
        assert result["risque"] in bank.RISK_LEVELS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_scoring.py -k "score_s4 or score_s5" -v`
Expected: FAIL — `AttributeError: ... has no attribute 'score_s4'`

- [ ] **Step 3: Write both scorers**

```python
# ── Session 4 — the environment ──────────────────────────────────────────────

def score_s4(responses: dict) -> dict | None:
    """Six labels, by scene position. No arithmetic — S4 is a preference, not a
    score, and averaging preferences would say nothing."""
    if not session_complete(responses, "4"):
        return None
    return {
        slot: chosen_option(responses, item_id)["env"]
        for slot, item_id in zip(bank.S4_SLOTS, bank.item_ids("4"))
    }


# ── Session 5 — risk and meaning ─────────────────────────────────────────────

def score_s5(responses: dict) -> dict | None:
    """Risk appetite and the meaning signals.

    S5-1/2/3 all speak to risk and the manual names no way to combine them, so
    the three labels stay side by side rather than collapsing into one score the
    paper sheet never produced.
    """
    if not session_complete(responses, "5"):
        return None

    def tag(item_id: str, key: str) -> str:
        return chosen_option(responses, item_id)[key]

    return {
        "risque": tag("S5-1", "risk"),
        "rapport_echec": tag("S5-2", "risk"),
        "rapport_flou": tag("S5-3", "risk"),
        "valeur_centrale": tag("S5-4", "sens"),
        "trace": tag("S5-5", "sens"),
        "sacrifice": tag("S5-6", "sens"),
        "vivant": tag("S5-7", "sens"),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_scoring.py -v`
Expected: PASS — 31 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/scoring.py backend/tests/test_voyage_scoring.py
git commit -m "feat(voyage): score sessions 4 and 5"
```

---

## Task 16: `synthesize` — the counselor's page-18 sheet

**Files:**
- Modify: `backend/app/services/voyage/scoring.py`
- Test: `backend/tests/test_voyage_scoring.py` (append)

**Interfaces:**
- Consumes: every `score_*` (tasks 11–15), `completeness` (task 10), `bank.SCORING_VERSION`.
- Produces: `synthesize(responses) -> dict` with keys `scoring_version`, `s0`, `riasec`, `s2`, `s3`, `s4`, `s5`, `completeness`.

`synthesize()` never returns `None`; the six section values do. The session-1 key is `riasec`, not `s1` — it names what the section contains rather than where it came from, and phases 2, 4 and 5 all read it by that name.

An S0-only voyage — the self-serve half — yields `s0` filled and the other five `None`. That is the normal state for most rows, not an error.

- [ ] **Step 1: Write the failing test**

```python
SECTION_KEYS = ("s0", "riasec", "s2", "s3", "s4", "s5")


def test_synthesize_never_returns_none_and_always_has_every_key():
    result = scoring.synthesize({"answers": {}, "billets": {}})
    assert result is not None
    assert set(result) == {"scoring_version", "completeness", *SECTION_KEYS}
    assert result["scoring_version"] == bank.SCORING_VERSION
    assert all(result[key] is None for key in SECTION_KEYS)
    assert result["completeness"] == dict.fromkeys(bank.SESSION_IDS, False)


def test_synthesize_s0_only_is_a_normal_state():
    """The self-serve half of the product produces exactly this."""
    s0_only = {"answers": {i: True for i in bank.item_ids("0")}, "billets": {}}
    result = scoring.synthesize(s0_only)
    assert result["s0"] is not None
    assert all(result[key] is None for key in ("riasec", "s2", "s3", "s4", "s5"))
    assert result["completeness"] == {
        "0": True, "1": False, "2": False, "3": False, "4": False, "5": False,
    }


def test_synthesize_complete_fills_every_section():
    result = scoring.synthesize(_answers())
    assert all(result[key] is not None for key in SECTION_KEYS)
    assert result["completeness"] == dict.fromkeys(bank.SESSION_IDS, True)
    assert set(result["s0"]) == {"axes", "tensions", "top3"}
    assert set(result["riasec"]) == {"scores", "maxima", "normalized", "top3"}
    assert set(result["s4"]) == set(bank.S4_SLOTS)


def test_synthesize_is_pure():
    """Same answers, same sheet — twice, and without touching the bank."""
    responses = _answers()
    assert scoring.synthesize(responses) == scoring.synthesize(responses)
    assert bank.SESSIONS[0]["items"][0]["text"] == (
        "Travailler dehors, sur le terrain, en mouvement"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_scoring.py -k synthesize -v`
Expected: FAIL — `AttributeError: ... has no attribute 'synthesize'`

- [ ] **Step 3: Write `synthesize`**

```python
# ── The synthesis sheet ──────────────────────────────────────────────────────

def synthesize(responses: dict) -> dict:
    """The counselor manual's page-18 sheet, assembled from the answers.

    Never None: a voyage that has only finished session 0 still has a sheet, and
    a caller should read `completeness` rather than probe for a missing key. The
    session-1 section is keyed `riasec` because that is what it contains — the
    other five keep their session number since no single framework names them.
    """
    return {
        "scoring_version": bank.SCORING_VERSION,
        "s0": score_s0(responses),
        "riasec": score_riasec(responses),
        "s2": score_s2(responses),
        "s3": score_s3(responses),
        "s4": score_s4(responses),
        "s5": score_s5(responses),
        "completeness": completeness(responses),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_scoring.py -v`
Expected: PASS — 35 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/scoring.py backend/tests/test_voyage_scoring.py
git commit -m "feat(voyage): assemble the synthesis sheet"
```

---

## Task 17: `prompt_context` — the reduced block, with no numbers in it

**Files:**
- Modify: `backend/app/services/voyage/scoring.py`
- Test: `backend/tests/test_voyage_scoring.py` (append)

**Interfaces:**
- Consumes: `synthesize()`'s return value (task 16), `STAGE_S0`, `STAGE_VALIDATED`.
- Produces: `prompt_context(synthesis, micro_phrase, stage) -> list[str]`.

This is where the "candidate never sees a trait name" invariant becomes a machine-checked property rather than a promise. The function is **pure over `synthesis`** — it never reaches back into the bank — so every string it can possibly emit is already present in the sheet, and the tests below can enumerate what must not appear.

Two stages. Before a counselor has validated the portrait, an analysis gets only the phrase and the session-0 attractions; the person has not been restituted yet, and an analysis must not tell them what the counselor hasn't. After validation, all nine lines.

Nine possible lines, in this order (contract § H):

| # | Label | Source | Stage |
|---|---|---|---|
| 1 | `Phrase révélée : ` | `micro_phrase` | s0 |
| 2 | `Ce qui l'attire le plus dans dix ans : ` | `s0.top3[].plain`, comma-joined | s0 |
| 3 | `Univers dominants : ` | `riasec.top3[].univers`, comma-joined | validated |
| 4 | `Besoin dominant : ` | `s2.sdt_dominant`, comma-joined | validated |
| 5 | `Ambivalences relevées : ` | `s0.tensions[].tension`, ` · `-joined | validated |
| 6 | `Cadre où elle donne le meilleur : ` | `s4.espace`, `s4.rythme`, `s4.equipe`, ` · `-joined | validated |
| 7 | `Ce qui l'épuise : ` | `s4.irritant` | validated |
| 8 | `Ce qui la met en colère : ` | `s5.valeur_centrale` | validated |
| 9 | `Se sent vivant(e) quand : ` | `s5.vivant` | validated |

A line whose value is empty or `None` is omitted entirely — the block never prints a label with nothing after it.

**Note for phase 3:** « Phrase révélée » shares a root with the banned « révélation ». It is model-facing prompt text, so the UI ban list does not reach it — but the candidate-facing hub must **not** reuse this wording as its label for the phrase.

- [ ] **Step 1: Write the failing test**

```python
import re
import unicodedata

BANNED_ROOTS = (
    "nevrotisme", "neuroticisme", "big five", "riasec", "schwartz", "sdt", "dunn",
    "kahneman", "dweck", "frankl", "logotherapie", "conscienciosite", "agreabilite",
    "extraversion", "introversion", "score", "trait", "axe",
)


def _fold(text):
    stripped = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in stripped if unicodedata.category(c) != "Mn")


def test_prompt_context_s0_stage_is_the_phrase_and_the_attractions():
    synthesis = scoring.synthesize(_answers())
    lines = scoring.prompt_context(synthesis, "Une phrase.", scoring.STAGE_S0)
    assert len(lines) == 2
    assert lines[0] == "Phrase révélée : Une phrase."
    assert lines[1].startswith("Ce qui l'attire le plus dans dix ans : ")


def test_prompt_context_validated_stage_adds_the_rest():
    synthesis = scoring.synthesize(_answers())
    lines = scoring.prompt_context(synthesis, "Une phrase.", scoring.STAGE_VALIDATED)
    assert 3 <= len(lines) <= 9
    joined = "\n".join(lines)
    assert "Univers dominants : " in joined
    assert "Se sent vivant(e) quand : " in joined


def test_prompt_context_never_emits_a_digit():
    """A number in the block is a score reaching the report, whatever it counts."""
    synthesis = scoring.synthesize(_answers())
    for stage in scoring.STAGES:
        for line in scoring.prompt_context(synthesis, "Une phrase.", stage):
            assert not re.search(r"[0-9]", line), line


def test_prompt_context_never_emits_a_framework_word():
    synthesis = scoring.synthesize(_answers())
    for stage in scoring.STAGES:
        for line in scoring.prompt_context(synthesis, "Une phrase.", stage):
            folded = _fold(line)
            for word in BANNED_ROOTS:
                assert not re.search(rf"\b{re.escape(word)}\b", folded), f"{word}: {line}"


def test_prompt_context_never_emits_a_level_or_an_axis_label():
    synthesis = scoring.synthesize(_answers())
    lines = scoring.prompt_context(synthesis, "p", scoring.STAGE_VALIDATED)
    joined = "\n".join(lines)
    for level in (scoring.LEVEL_HIGH, scoring.LEVEL_MID, scoring.LEVEL_LOW):
        assert level not in joined
    for axis in bank.AXES.values():
        assert axis["label"] not in joined
        assert axis["pos"] not in joined
        assert axis["neg"] not in joined


def test_prompt_context_omits_a_line_rather_than_printing_an_empty_label():
    synthesis = scoring.synthesize({"answers": {}, "billets": {}})
    assert scoring.prompt_context(synthesis, None, scoring.STAGE_S0) == []
    lines = scoring.prompt_context(synthesis, "Une phrase.", scoring.STAGE_VALIDATED)
    assert lines == ["Phrase révélée : Une phrase."]
    for line in lines:
        assert not line.rstrip().endswith(":")


def test_prompt_context_treats_an_unknown_stage_as_s0():
    """Fail closed: an unrecognised stage must not leak the validated block."""
    synthesis = scoring.synthesize(_answers())
    unknown = scoring.prompt_context(synthesis, "p", "something-else")
    assert unknown == scoring.prompt_context(synthesis, "p", scoring.STAGE_S0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_voyage_scoring.py -k prompt_context -v`
Expected: FAIL — `AttributeError: ... has no attribute 'prompt_context'`

- [ ] **Step 3: Write `prompt_context`**

```python
# ── The reduced block that reaches an analysis ───────────────────────────────

def _line(label: str, value) -> str | None:
    """A labelled line, or None when there is nothing to say.

    Never prints a label with an empty value: a bare « Besoin dominant : » in
    the prompt invites the model to fill the blank.
    """
    if isinstance(value, (list, tuple)):
        value = ", ".join(v for v in value if v)
    text = (value or "").strip() if isinstance(value, str) else ""
    return f"{label} : {text}" if text else None


def prompt_context(synthesis: dict, micro_phrase: str | None, stage: str) -> list[str]:
    """The plain-French lines stored as Analysis.inputs["_voyage"].

    Content lines only — anthropic_service._voyage_block() adds the
    "--- ... ---" header, exactly as _conditions_block() does for bloc 5.

    Pure over `synthesis`: every string it can emit is already in that dict, and
    it never reaches back into the bank. That is what makes "no numbers, no
    framework words" a testable property rather than a promise.

    Two stages, and the distinction is load-bearing. Before a counselor has
    validated the portrait, an analysis receives only the phrase and the
    session-0 attractions — the person has not been restituted yet, and a report
    must not tell them what the counselor hasn't. An unrecognised stage is
    treated as s0: this fails closed.
    """
    synthesis = synthesis or {}
    lines = [_line("Phrase révélée", micro_phrase)]

    s0 = synthesis.get("s0") or {}
    lines.append(_line(
        "Ce qui l'attire le plus dans dix ans",
        [entry["plain"] for entry in s0.get("top3") or []],
    ))

    if stage == STAGE_VALIDATED:
        riasec = synthesis.get("riasec") or {}
        s2 = synthesis.get("s2") or {}
        s4 = synthesis.get("s4") or {}
        s5 = synthesis.get("s5") or {}
        lines.append(_line(
            "Univers dominants",
            [entry["univers"] for entry in riasec.get("top3") or []],
        ))
        lines.append(_line("Besoin dominant", s2.get("sdt_dominant") or []))
        lines.append(_line(
            "Ambivalences relevées",
            " · ".join(t["tension"] for t in s0.get("tensions") or []),
        ))
        lines.append(_line(
            "Cadre où elle donne le meilleur",
            " · ".join(
                v for v in (s4.get("espace"), s4.get("rythme"), s4.get("equipe")) if v
            ),
        ))
        lines.append(_line("Ce qui l'épuise", s4.get("irritant")))
        lines.append(_line("Ce qui la met en colère", s5.get("valeur_centrale")))
        lines.append(_line("Se sent vivant(e) quand", s5.get("vivant")))

    return [line for line in lines if line]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_voyage_scoring.py -v`
Expected: PASS — 42 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/voyage/scoring.py backend/tests/test_voyage_scoring.py
git commit -m "feat(voyage): the reduced voyage block, staged and number-free"
```

---

## Task 18: Full verification

**Files:**
- Modify: none — this task only runs and records.

**Interfaces:**
- Consumes: everything in tasks 1–17.
- Produces: a green suite, and the phase-1 handoff.

- [ ] **Step 1: Run the two new suites**

Run: `cd backend && pytest tests/test_voyage_bank.py tests/test_voyage_scoring.py -v`
Expected: PASS — all tests, no skips, no warnings other than the ones `pytest.ini` already filters.

- [ ] **Step 2: Run the whole backend suite**

Run: `cd backend && pytest`
Expected: PASS — every pre-existing test still passes. This phase adds files and imports nothing existing, so a failure anywhere else means something was edited that should not have been. Do not proceed until it is green.

- [ ] **Step 3: Confirm the package is genuinely isolated**

Run:

```bash
cd backend && grep -nE "^(from|import) " app/services/voyage/bank.py app/services/voyage/scoring.py
```

Expected: exactly one import line in total — `from . import bank` in `scoring.py`. `bank.py` imports nothing. Any `flask`, `sqlalchemy`, `os`, or `..models` import here is a boundary violation: this package must stay runnable without an app context, because phase 1's model calls it inside a request and phase 2's generation calls it from a background thread.

- [ ] **Step 4: Confirm the invariant that phase 5 depends on**

Run:

```bash
cd backend && python -c "
from app.services.voyage import bank, scoring
answers = {i: False for i in bank.item_ids('0')}
for n in '12345':
    for i in bank.item_ids(n):
        answers[i] = 'A'
r = {'answers': answers, 'billets': {}}
s = scoring.synthesize(r)
for stage in scoring.STAGES:
    for line in scoring.prompt_context(s, 'Une phrase de test.', stage):
        print(f'[{stage}] {line}')
print('sessions', len(bank.SESSIONS), 'items', len(bank.all_item_ids()))
print('maxima', bank.riasec_maxima())
"
```

Expected: two `[s0]` lines, then up to nine `[validated]` lines, none containing a digit; `sessions 6 items 53`; `maxima {'R': 12, 'I': 11, 'A': 10, 'S': 10, 'E': 11, 'C': 9}`.

- [ ] **Step 5: Commit**

```bash
git add -A backend/app/services/voyage backend/tests/test_voyage_bank.py backend/tests/test_voyage_scoring.py
git commit -m "test(voyage): phase 0 verified — 53 items, 6 sessions, scoring green"
```

---

## Handoff to phase 1

Phase 1 (`2026-09-09-voyage-phase-1-models-api.md`) consumes exactly this surface:

| Symbol | Used by |
|---|---|
| `bank.public()` | `GET /api/voyage/bank` |
| `bank.validate_answer(item_id, value)` | `PUT /api/voyage/responses` |
| `bank.item_ids(n)`, `bank.SESSION_IDS` | session locking |
| `scoring.missing_items(responses, n)` | `POST /sessions/<n>/complete` — the guard and the 400 body |
| `scoring.synthesize(responses)` | `Voyage.synthesis()`, the counselor sheet |
| `scoring.prompt_context(synthesis, phrase, stage)` | phase 5's `_merge_profile` |
| `scoring.STAGE_S0`, `scoring.STAGE_VALIDATED` | phase 5's stage rule |
| `bank.SCORING_VERSION` | `Voyage.scoring_version` default |

Nothing in phase 0 knows what a `Voyage` is. That is deliberate: scoring stays testable against plain dicts, and a correction to a scoring table never needs a database to verify.

`session_complete()` and `completeness()` are **internal** to this phase — every `score_*` calls the
first, `synthesize()` calls the second. Phase 1 does not use either: `Voyage.to_dict()` reports the
stored `sessions_completed` column (contract § C.5) rather than recomputing, so the value the client
sees cannot drift from the one the session-lock gate reads.

## Open for the PM — carried forward, not blocking

1. **Two Schwartz values are the manual's, not Schwartz's** — `conservation` and `integrite` are not canonical basic values. Faithful to the paper sheet the counselor already uses; worth confirming since it is what they read aloud.
2. **Three errata implemented** (spec ⚑17): A1 excluded from tensions (one item), RIASEC maxima computed as E 11 / C 9 rather than the printed 10 / 10, Big Five levels at ±2 where the manual gives no threshold.
3. **`S3-6 C` mapped to `adaptatif`** where the manual says « Style hybride » — see task 6.
4. **The `_voyage` block is written in the feminine third person** (« Ce qui l'attire », « elle crée »), transcribed from the spec's literal example. The app collects no gender. A neutral rewrite touches only the nine labels in `prompt_context()` and the S5 `sens` strings.
5. **`S3-7 D` contains « jonglles »**, a typo in the cahier, transcribed as-is.
