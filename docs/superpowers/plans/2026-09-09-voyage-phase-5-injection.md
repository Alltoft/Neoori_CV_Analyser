# Le voyage — Phase 5 · Injection into analyses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fold a person's voyage into every new analysis as a handful of reduced plain-French lines, stamp which voyage fed which analysis, and document the module.

**Architecture:** `routes/analyses._merge_profile()` gains a voyage fold that runs alongside the existing Profil de base fold: it asks `Voyage.for_prompt(user_id)` for the row that may speak, reduces it through `scoring.prompt_context()` and stores the result as `inputs["_voyage"]` plus `inputs["_voyage_id"]`; `create_analysis()` copies that id onto the `Analysis.voyage_id` column. `anthropic_service._voyage_block()` wraps those lines under one header and is appended inside `_common_tail()`, which all three parcours formatters already call — so one change reaches parcours 1, 2 and 3. Reduction happens once, at merge time, so unlocking an analysis regenerates it with exactly the voyage the first run saw.

**Tech Stack:** Flask 3 · Flask-SQLAlchemy · Flask-JWT-Extended · pytest (SQLite in-memory) · Next.js 16 + TypeScript (types only, no runtime change) · Markdown docs

**Spec:** docs/superpowers/specs/2026-09-09-voyage-design.md
**Contracts:** docs/superpowers/plans/2026-09-09-voyage-contracts.md

---

## Global Constraints

- App UI strings are **French**. Code comments, docstrings and commit messages are **English** (`CLAUDE.md`).
- Copy ban list, never in user-facing French text: `boussole`, `copilote`, `miroir`, `révélation`, `épanouissement`, `alignement`, `excellence`, `talent unique`, `vous vous démarquez`.
- The block header `--- CE QUE LE VOYAGE A RÉVÉLÉ ---` and the label `Phrase révélée : ` share a root with the banned « révélation ». They are **model-facing prompt text, not UI chrome**, so the ban does not reach them (contracts § H). Do not "fix" them. The ban does reach anything a person reads on a page.
- **The candidate never sees a score or a trait name** (spec decision 7). Enforced in code, not in prompt prose: everything that leaves the scoring layer is plain French.
- **Never required.** Every parcours runs identically with no voyage; the block is simply absent — no key, no header, no empty placeholder (spec decision 11).
- **The stage rule.** Until a counselor validates the portrait, an analysis receives only session 0's phrase and its three attractions. The full reduction travels only at `stage == "validated"`.
- Statuses are `String(16)`, never native enums — widening a MySQL ENUM is the one migration step this repo cannot rehearse locally. **This phase adds no migration.** The `analyses.voyage_id` column and its migration `e1f2a3b4c5d6` are phase 1's (contracts § D). The alembic head after phase 1 is `f2a3b4c5d6e7`.
- Prompts live in the DB (`PromptVersion`), never in code. Structure comes from a JSON-schema `output_config` passed via `extra_body`, never from prompt prose. **This phase writes no prompt and no seed.**
- Never hold a DB connection across an Anthropic stream: `db.session.remove()` before the stream, re-acquire after (`anthropic_service._run_analysis`, lines 462–522). This phase does not touch the runner; do not disturb that ordering.
- Backend tests: `pytest`, SQLite in-memory, run from `/Users/imran/Downloads/design_handoff_cv_analyzer/backend`. Fixtures `app`, `client`, `admin_headers` live in `backend/tests/conftest.py`. A logged-in candidate is built the way `tests/test_profile.py::auth` does — `create_access_token(identity=..., additional_claims={"role": "candidate"})`, `TestingConfig` puts the JWT in headers, not cookies.
- Frontend has **no test runner**. Verification is `cd frontend && npm run lint` and `cd frontend && npm run build`, plus rows added to `TEST-PLAN.md`.
- **Next.js caveat** (`frontend/AGENTS.md`): "This is NOT the Next.js you know — APIs, conventions and file structure may differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code." Task 6 carries the doc-reading step.
- Branch `initial` is the deploy branch: `git push` triggers GitHub Actions → GHCR images → VPS. Every commit must leave `pytest` green and `npm run build` passing.
- Commit style: Conventional Commits, English subject, lowercase, no trailing period, scope `voyage`. Add whatever attribution trailer your own session rules require.

### Prerequisites — phase 5 sits on top of phases 0–4

Phase 5 consumes these names. Each is pinned by the contracts document; none is invented here. Task 1 Step 1 verifies they exist before anything else runs.

| Name | Signature / value | Owner | Contract |
|---|---|---|---|
| `app.services.voyage.bank.SESSION_IDS` | `("0","1","2","3","4","5")` | phase 0 | § A.1 |
| `app.services.voyage.bank.item_ids(n: str) -> list[str]` | — | phase 0 | § A.4 |
| `app.services.voyage.bank.item(item_id: str) -> dict \| None` | — | phase 0 | § A.4 |
| `app.services.voyage.bank.AXES` | `dict[str, dict[str, str]]`, ten keys | phase 0 | § A.2 |
| `app.services.voyage.bank.BIG5` | `("ouverture","conscienciosite","extraversion","agreabilite","nevrotisme")` | phase 0 | § A.1 |
| `app.services.voyage.scoring.STAGE_S0` | `"s0"` | phase 0 | § B.1 |
| `app.services.voyage.scoring.STAGE_VALIDATED` | `"validated"` | phase 0 | § B.1 |
| `app.services.voyage.scoring.LEVEL_HIGH / LEVEL_MID / LEVEL_LOW` | `"Élevé" / "Moyen" / "Faible"` | phase 0 | § B.1 |
| `app.services.voyage.scoring.synthesize(responses: dict) -> dict` | — | phase 0 | § B.5 |
| `app.services.voyage.scoring.prompt_context(synthesis: dict, micro_phrase: str \| None, stage: str) -> list[str]` | — | phase 0 | § B.6 |
| `app.models.voyage.Voyage.for_prompt(user_id: str \| None) -> "Voyage \| None"` | newest validated, else newest with a phrase, else `None` | phase 1 | § C.4 |
| `app.models.voyage.Voyage.synthesis() -> dict` | `scoring.synthesize(self.responses)` | phase 1 | § C.4 |
| `app.models.voyage.Voyage.micro_phrase -> str \| None` | — | phase 1 | § C.4 |
| `app.models.voyage.Voyage.portrait_status` | `String(16)`, ∈ `("none","generating","draft","validated","error")` | phase 1 | § C.2 |
| `app.models.analysis.Analysis.voyage_id` | `db.String(36)`, nullable FK to `voyages.id` | phase 1 | § C/D |
| `app.services.voyage.generation.leak_check(sections: dict[str, str]) -> list[str]` | offending words, `[]` when clean | phase 2 | § G.5 |
| `app.services.voyage.generation.LEAK_PATTERNS` | 17 framework words | phase 2 | § G.5 |

If any of these is missing, **stop**. The missing phase must land first; do not stub it here.

---

## File Structure

| File | Created / Modified | The one thing it is responsible for |
|---|---|---|
| `backend/app/services/anthropic_service.py` | Modify (`:82-102`) | Turning `inputs["_voyage"]` into the block every parcours message carries |
| `backend/app/routes/analyses.py` | Modify (`:6-15`, `:90-95`, `:233-256`) | Deciding which voyage may speak to this analysis, at which stage, and stamping the id |
| `backend/app/models/analysis.py` | Modify (`:58-73`) | Exposing `voyage_id` on the analysis payload, alongside `prompt_version_id` |
| `backend/tests/test_voyage_prompt_context.py` | Create | Holding the four rules: never required · the stage rule · no numbers or framework words · traceability |
| `frontend/src/types/index.ts` | Modify (`:61-70`, `:104-125`) | Typing the three fields phase 5 puts on the wire |
| `TEST-PLAN.md` | Modify (`:193-211` renumber, new § 10) | The PM-facing manual checks for the injection |
| `CLAUDE.md` | Modify (new section before `:148`) | Telling the next developer what le voyage sends to an analysis — and which out-of-scope line **not** to delete |

Nothing else is touched. In particular: **no migration**, **no prompt seed**, **no route file**, and `README.md` / `plan.md` are read-only for this phase (Task 8 asserts it).

---

### Task 1: The `_voyage_block` every parcours carries

**Files:**
- Modify: `backend/app/services/anthropic_service.py:82-102` (insert `_voyage_block` after `_rights_block`, extend `_common_tail`)
- Create: `backend/tests/test_voyage_prompt_context.py`
- Test: `backend/tests/test_voyage_prompt_context.py`

**Interfaces:**
- Consumes: `anthropic_service._conditions_block(inputs: dict) -> list[str]` (existing, `anthropic_service.py:62`); `anthropic_service._rights_block(inputs: dict) -> list[str]` (existing, `anthropic_service.py:82`); the phase 0–2 surface listed in *Prerequisites*
- Produces: `anthropic_service._voyage_block(inputs: dict) -> list[str]` — returns `[]` when `inputs["_voyage"]` is absent/empty, else `["", "--- CE QUE LE VOYAGE A RÉVÉLÉ ---"] + list(lines)`. `_common_tail(inputs: dict) -> list[str]` keeps its signature and gains the block.

---

- [ ] **Step 1: Pre-flight — confirm phases 0–4 have landed**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && venv/bin/python - <<'PY'
from app import create_app
from app.models.analysis import Analysis
from app.models.voyage import Voyage
from app.services.voyage import bank, scoring, generation

missing = [n for n in ("for_prompt", "synthesis", "micro_phrase", "portrait_status")
           if not hasattr(Voyage, n)]
assert not missing, f"Voyage is missing {missing} — phase 1 has not landed"
assert hasattr(Analysis, "voyage_id"), \
    "analyses.voyage_id missing — phase 1 migration e1f2a3b4c5d6 has not landed"
assert scoring.STAGE_S0 == "s0" and scoring.STAGE_VALIDATED == "validated"
assert callable(scoring.prompt_context) and callable(scoring.synthesize)
assert len(bank.AXES) == 10 and len(bank.BIG5) == 5
assert callable(generation.leak_check) and len(generation.LEAK_PATTERNS) == 17, \
    "phase 2 has not landed"
create_app("testing")
print("phase 0-2 surface OK")
PY
```
Expected: `phase 0-2 surface OK`

If any assertion fires, stop and land the phase it names. Do not stub the missing name.

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_voyage_prompt_context.py`. This is the whole file: the preamble (docstring, imports, constants, helpers) that every later task appends to, plus Task 1's own tests.

```python
"""Le voyage reaches an analysis as reduced plain lines — and nothing else.

Phase 5 wires three pieces together:

  scoring.prompt_context()          a synthesis -> 2 or 9 plain French lines
  routes/analyses._merge_voyage()   those lines -> Analysis.inputs["_voyage"],
                                    the voyage id -> inputs["_voyage_id"]
  anthropic_service._voyage_block() those lines -> one block in every parcours
                                    message

Four rules live here, in order of how much damage breaking one does.

1. « Never required ». No voyage means no key and no block. Every parcours runs
   identically without one — parcours 3 exists to remove barriers, and a
   six-session game would be the largest barrier in the product.

2. The stage rule. After session 5 the app drafts a portrait, but nobody has
   restituted it yet. An analysis run in that window must not tell a person
   what their counselor has not told them: only session 0's phrase and its
   three attractions travel until a counselor validates.

3. No numbers, no framework words. The person never sees a score or a trait
   name, and neither does the model — it is handed plain French only, so it
   cannot echo a vocabulary back at them.

4. Traceability. Which voyage fed which analysis is recoverable afterwards,
   the same discipline as prompt_version_id.

Nothing here calls Anthropic: start_analysis is patched out everywhere, so the
route tests exercise the wiring and stop at the thread boundary.
"""
import re
from datetime import datetime
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.analysis import Analysis
from app.models.profile import Profile
from app.models.user import User
from app.models.voyage import Voyage
from app.services.anthropic_service import (
    _format_user_message,
    _format_user_message_p1,
    _format_user_message_p2,
    _format_user_message_p3,
    _voyage_block,
)
from app.services.voyage import bank, generation, scoring

VOYAGE_HEADER = "--- CE QUE LE VOYAGE A RÉVÉLÉ ---"

PHRASE = ("Tu cherches des endroits où ce que tu fabriques sert vraiment "
          "à quelqu'un.")

# The nine labels prompt_context() may emit, in the order it emits them
# (contracts § H). A label whose value is empty is omitted entirely, so a real
# block is an ordered subset of this list — never a reordering of it.
ALL_LABELS = [
    "Phrase révélée",
    "Ce qui l'attire le plus dans dix ans",
    "Univers dominants",
    "Besoin dominant",
    "Ambivalences relevées",
    "Cadre où elle donne le meilleur",
    "Ce qui l'épuise",
    "Ce qui la met en colère",
    "Se sent vivant(e) quand",
]

S0_LABELS = ALL_LABELS[:2]

# Two lines exactly as the s0 stage emits them. Hand-written rather than
# computed: a safety net woven out of the thing it is meant to catch catches
# nothing.
S0_LINES = [
    f"Phrase révélée : {PHRASE}",
    "Ce qui l'attire le plus dans dix ans : le terrain et l'action, "
    "transmettre, un impact visible",
]

# CLAUDE.md's ban list. It governs what a *person* reads. The block header and
# « Phrase révélée » share a root with « révélation » and are deliberately kept
# — contracts § H: they are model-facing prompt text, not UI chrome.
BAN_LIST = ("boussole", "copilote", "miroir", "révélation", "épanouissement",
            "alignement", "excellence", "talent unique", "vous vous démarquez")

# The minimum each parcours' formatter needs to produce a message.
P1 = {"_path": "1", "cv_text": "8 ans d'administration", "cible_visee": "Chargé RH"}
P2 = {"_path": "2", "cv_text": "parcours", "satisfaction": "les projets d'équipe",
      "refus": "le reporting", "raison_changement": "un choix personnel"}
P3 = {"_path": "3", "experiences": "bénévolat", "aime_faire": "organiser",
      "refus": "le travail de nuit", "contraintes": "pas de voiture",
      "bon_travail": "une équipe"}

# What POST /api/analyses/ accepts for parcours 1: 200+ characters of CV and a
# target of at least 50 (chemin A's floor).
P1_FULL = {
    "_path": "1",
    "cv_text": "c" * 300,
    "cible_visee": "Chargé de recrutement dans une PME industrielle du bassin lyonnais",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def _labels(lines) -> list[str]:
    """The label half of each emitted line, « Label : valeur »."""
    return [line.split(" : ", 1)[0] for line in lines]


def _ordered_subset(got: list[str], reference: list[str]) -> bool:
    """True when `got` appears inside `reference` in the same order."""
    it = iter(reference)
    return all(label in it for label in got)


def _user(email: str) -> User:
    user = User(email=email, password_hash="x")
    db.session.add(user)
    db.session.commit()
    return user


def _auth(user: User) -> dict:
    """Bearer headers — TestingConfig reads the JWT from headers, not cookies."""
    token = create_access_token(
        identity=str(user.id), additional_claims={"role": "candidate"}
    )
    return {"Authorization": f"Bearer {token}"}


def _s0_answers() -> dict:
    """Every session-0 item answered OUI. Enough for a filled `s0` section."""
    return {item_id: True for item_id in bank.item_ids("0")}


def _all_answers() -> dict:
    """All 53 items answered — session 0 all OUI, every scene on its first
    option. The content is irrelevant; the point is that synthesize() returns
    all six sections filled, so the validated stage has something to emit."""
    answers = {}
    for n in bank.SESSION_IDS:
        for item_id in bank.item_ids(n):
            if n == "0":
                answers[item_id] = True
            else:
                answers[item_id] = bank.item(item_id)["options"][0]["letter"]
    return answers


def _voyage(user, *, answers=None, portrait_status="none", status="s0_termine",
            sessions_completed=None, created_at=None, share_token=None,
            phrase=PHRASE) -> Voyage:
    """A voyage the way the phase-1 routes leave one behind.

    created_at is passed explicitly wherever a test compares two rows: rows
    inserted in the same transaction otherwise share a timestamp and
    for_prompt()'s "newest" ordering stops being decidable.

    `sessions_completed` is compared against None, not truth-tested: a test
    that wants an empty list must get an empty list, not the default.
    """
    voyage = Voyage(
        user_id=user.id,
        status=status,
        sessions_completed=["0"] if sessions_completed is None else sessions_completed,
        consent_at=datetime(2026, 9, 1),
        age_attested=True,
        micro_status="success",
        portrait_status=portrait_status,
        share_token=share_token,
        created_at=created_at or datetime(2026, 9, 1),
    )
    if portrait_status == "validated":
        voyage.portrait_validated_at = datetime(2026, 9, 2)
    voyage.responses = {
        "answers": _s0_answers() if answers is None else answers,
        "billets": {},
    }
    voyage.micro = {"phrase": phrase, "prompt_version_id": None,
                    "tokens_in": 0, "tokens_out": 0}
    db.session.add(voyage)
    db.session.commit()
    return voyage


# ── the block itself ─────────────────────────────────────────────────────────

def test_no_voyage_means_no_block_at_all():
    """Rule 1. Not an empty header, not a placeholder line — nothing."""
    assert _voyage_block({}) == []
    assert _voyage_block({"_voyage": []}) == []
    assert _voyage_block({"_voyage": None}) == []


def test_the_block_is_the_header_then_the_lines():
    assert _voyage_block({"_voyage": S0_LINES}) == ["", VOYAGE_HEADER] + S0_LINES


def test_the_block_does_not_hand_out_the_stored_list():
    """inputs["_voyage"] is a JSON column value. Handing a reference to it
    downstream would let a message builder edit the stored row."""
    stored = list(S0_LINES)
    block = _voyage_block({"_voyage": stored})
    block.append("intrus")
    assert stored == S0_LINES


@pytest.mark.parametrize("formatter, inputs", [
    (_format_user_message_p1, P1),
    (_format_user_message_p2, P2),
    (_format_user_message_p3, P3),
])
def test_every_parcours_carries_the_block(formatter, inputs):
    """One voyage, three parcours. The block is appended by _common_tail, so a
    parcours added later inherits it instead of forgetting it."""
    msg = formatter({**inputs, "_voyage": S0_LINES})
    assert VOYAGE_HEADER in msg
    for line in S0_LINES:
        assert line in msg


@pytest.mark.parametrize("formatter, inputs", [
    (_format_user_message_p1, P1),
    (_format_user_message_p2, P2),
    (_format_user_message_p3, P3),
])
def test_no_parcours_carries_the_block_without_a_voyage(formatter, inputs):
    assert VOYAGE_HEADER not in formatter(inputs)


def test_the_block_comes_after_the_conditions_and_the_rights_blocks():
    """Ordering is part of the message contract: profile, then bloc 5, then
    the OETH note, then the voyage. A reader (and the model) sees the
    hard-edged administrative facts before the exploratory ones."""
    msg = _format_user_message_p1({
        **P1,
        "_conditions": {"points_forts": ["rythme"],
                        "possible_avec_adaptation": [], "a_eviter": []},
        "_oeth": True,
        "_voyage": S0_LINES,
    })
    assert msg.index("--- CONDITIONS DE TRAVAIL ---") \
        < msg.index("--- DISPOSITIFS MOBILISABLES ---") \
        < msg.index(VOYAGE_HEADER)


def test_a_legacy_path_code_still_gets_the_block():
    """Analyses written before the parcours migration carry '_path': 'A'/'B'."""
    assert VOYAGE_HEADER in _format_user_message(
        {"_path": "A", "cv_text": "x", "cible_visee": "y", "_voyage": S0_LINES}
    )
    assert VOYAGE_HEADER in _format_user_message(
        {"_path": "B", "experiences": "x", "_voyage": S0_LINES}
    )
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && venv/bin/python -m pytest tests/test_voyage_prompt_context.py -v`

Expected: FAIL at collection with
```
ImportError: cannot import name '_voyage_block' from 'app.services.anthropic_service'
```

- [ ] **Step 4: Write minimal implementation**

In `backend/app/services/anthropic_service.py`, insert `_voyage_block` between `_rights_block` (ends line 98) and `_common_tail` (line 101), and add it to `_common_tail`'s return. Replace lines 99–102 — currently two blank lines followed by:

```python
def _common_tail(inputs: dict) -> list[str]:
    return _conditions_block(inputs) + _rights_block(inputs)
```

with:

```python
def _voyage_block(inputs: dict) -> list[str]:
    """Le voyage, already reduced to plain lines by scoring.prompt_context().

    Mirrors _conditions_block: the caller stores only the reduced lines and
    this adds the blank separator and the header. Two lines before a counselor
    has validated the portrait, up to nine after — the reduction is decided at
    merge time, so what an unlock regenerates is what the first run sent.

    No voyage means no block and no header. Every parcours runs identically
    without one; the voyage is never required.
    """
    lines = inputs.get("_voyage") or []
    if not lines:
        return []
    return ["", "--- CE QUE LE VOYAGE A RÉVÉLÉ ---"] + list(lines)


def _common_tail(inputs: dict) -> list[str]:
    return _conditions_block(inputs) + _rights_block(inputs) + _voyage_block(inputs)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && venv/bin/python -m pytest tests/test_voyage_prompt_context.py -v`

Expected: PASS — **11 passed** (1 + 1 + 1 + 3 parametrised + 3 parametrised + 1 + 1 — that is `test_no_voyage_means_no_block_at_all`, `test_the_block_is_the_header_then_the_lines`, `test_the_block_does_not_hand_out_the_stored_list`, three `test_every_parcours_carries_the_block`, three `test_no_parcours_carries_the_block_without_a_voyage`, `test_the_block_comes_after_the_conditions_and_the_rights_blocks`, `test_a_legacy_path_code_still_gets_the_block`).

- [ ] **Step 6: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/services/anthropic_service.py backend/tests/test_voyage_prompt_context.py
git commit -F - <<'MSG'
feat(voyage): carry the voyage into every parcours message

_common_tail is what all three formatters already call, so the block lands in
parcours 1, 2 and 3 from one place — and a fourth parcours would inherit it
rather than have to remember it.

The block is absent, header included, when there is no voyage. Every parcours
has to run identically without one: parcours 3 exists to remove barriers, and
a six-session game gated on a counselor would be the largest barrier in the
product.
MSG
```

---

### Task 2: Fold the voyage into `_merge_profile` and stamp `Analysis.voyage_id`

Implements the fold at the **session-0 stage only**. The stage rule is widened in Task 3. Starting narrow is deliberate: the intermediate state under-discloses, which is the safe direction to be wrong in.

**Files:**
- Modify: `backend/app/routes/analyses.py:6-15` (imports), `:90-95` (the `Analysis(...)` constructor), `:233-256` (`_merge_profile`)
- Modify: `backend/app/models/analysis.py:58-73` (`to_dict`)
- Test: `backend/tests/test_voyage_prompt_context.py` (append)

**Interfaces:**
- Consumes: `Voyage.for_prompt(user_id: str | None) -> "Voyage | None"` (contracts § C.4); `Voyage.synthesis() -> dict` (§ C.4); `Voyage.micro_phrase -> str | None` (§ C.4); `scoring.prompt_context(synthesis: dict, micro_phrase: str | None, stage: str) -> list[str]` (§ B.6); `scoring.STAGE_S0 == "s0"` (§ B.1); the `Analysis.voyage_id` column (§ D, migration `e1f2a3b4c5d6`); `anthropic_service._voyage_block` from Task 1
- Produces: `analyses._merge_voyage(inputs: dict, user_id: str) -> None`; `inputs["_voyage_id"]: str`; `inputs["_voyage"]: list[str]`; `Analysis.to_dict()["voyage_id"]: str | None`

---

- [ ] **Step 1: Check whether phase 1 already exposed `voyage_id` on the payload**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && grep -n '"voyage_id"' app/models/analysis.py`

- No output → the key is missing; Step 4 adds it.
- One line inside `to_dict()` → phase 1 already added it; in Step 4, skip the `models/analysis.py` edit and change nothing else.

- [ ] **Step 2: Write the failing test**

Append to `backend/tests/test_voyage_prompt_context.py`. It uses the preamble Task 1 created — `VOYAGE_HEADER`, `P1_FULL`, `_user()`, `_auth()`, `_voyage()`, `_labels()`, `S0_LABELS`. If those names are not in the file, Task 1 has not been done.

```python
# ── the fold: what create_analysis stores ────────────────────────────────────

@patch("app.routes.analyses.start_analysis")
def test_an_analysis_without_a_voyage_carries_no_voyage_key(_start, client, app):
    """Rule 1 at the route level. Not `"_voyage": []` — no key at all. An empty
    key is a shape the prompt builder, the TypeScript types and every later
    reader would have to allow for, forever, for nothing."""
    user = _user("sans-voyage@test.fr")
    res = client.post("/api/analyses/", json={"inputs": dict(P1_FULL)},
                      headers=_auth(user))
    assert res.status_code == 201, res.data

    payload = res.get_json()["analysis"]
    assert "_voyage" not in payload["inputs"]
    assert "_voyage_id" not in payload["inputs"]
    assert payload["voyage_id"] is None
    assert VOYAGE_HEADER not in _format_user_message(payload["inputs"])


@patch("app.routes.analyses.start_analysis")
def test_a_voyage_is_reduced_into_the_inputs_and_stamped_on_the_row(
        _start, client, app):
    """Rule 4. The id is recoverable from the row itself, not only from the
    JSON blob — the same discipline as prompt_version_id."""
    user = _user("avec-voyage@test.fr")
    voyage = _voyage(user)

    res = client.post("/api/analyses/", json={"inputs": dict(P1_FULL)},
                      headers=_auth(user))
    assert res.status_code == 201, res.data
    payload = res.get_json()["analysis"]

    assert payload["inputs"]["_voyage_id"] == voyage.id
    assert payload["voyage_id"] == voyage.id

    lines = payload["inputs"]["_voyage"]
    assert lines, "a voyage with a phrase must reduce to at least one line"
    assert _labels(lines)[0] == "Phrase révélée"

    row = Analysis.query.get(payload["id"])
    assert row.voyage_id == voyage.id
    assert VOYAGE_HEADER in _format_user_message(row.inputs)


@patch("app.routes.analyses.start_analysis")
def test_the_voyage_is_folded_even_without_a_profil_de_base(_start, client, app):
    """Session 0 is the 5-minute self-serve entry and does not require a
    profile (spec decision 12). _merge_profile used to return early when the
    Profile row was missing, so folding the voyage after that return would
    have dropped it for exactly the people the module opens with."""
    user = _user("sans-profil@test.fr")
    voyage = _voyage(user)
    assert Profile.query.filter_by(user_id=user.id).first() is None

    res = client.post("/api/analyses/", json={"inputs": dict(P1_FULL)},
                      headers=_auth(user))
    assert res.status_code == 201, res.data
    assert res.get_json()["analysis"]["inputs"]["_voyage_id"] == voyage.id


@patch("app.routes.analyses.start_analysis")
def test_the_profil_de_base_still_reaches_the_analysis(_start, client, app):
    """Regression guard on the restructured _merge_profile: the voyage fold
    must not have displaced the profile fold it now sits beside."""
    user = _user("profil-intact@test.fr")
    profile = Profile(user_id=user.id, prenom="Marie", nom="DUPONT",
                      ville="Lyon", tranche_age="35_44")
    db.session.add(profile)
    db.session.commit()
    _voyage(user)

    res = client.post("/api/analyses/", json={"inputs": dict(P1_FULL)},
                      headers=_auth(user))
    stored = res.get_json()["analysis"]["inputs"]
    assert stored["prenom"] == "Marie"
    assert stored["ville"] == "Lyon"
    assert stored["_voyage_id"]


@patch("app.routes.analyses.start_analysis")
def test_an_anonymous_analysis_carries_no_voyage(_start, client, app):
    """No user id, no lookup — and no crash on the way past."""
    res = client.post("/api/analyses/", json={"inputs": dict(P1_FULL)})
    assert res.status_code == 201, res.data
    assert "_voyage" not in res.get_json()["analysis"]["inputs"]


@patch("app.routes.analyses.start_analysis")
def test_another_users_voyage_is_never_folded_in(_start, client, app):
    """for_prompt is scoped to the caller. A shared machine, two accounts."""
    owner = _user("proprietaire@test.fr")
    _voyage(owner)
    other = _user("autre@test.fr")

    res = client.post("/api/analyses/", json={"inputs": dict(P1_FULL)},
                      headers=_auth(other))
    assert "_voyage_id" not in res.get_json()["analysis"]["inputs"]


@patch("app.routes.analyses.start_analysis")
def test_a_voyage_that_never_finished_session_zero_says_nothing(
        _start, client, app):
    """for_prompt takes the newest validated portrait, else the newest voyage
    that has a phrase. A voyage still in `en_cours` has neither, so it is not
    a source — the person has been told nothing yet."""
    user = _user("en-cours@test.fr")
    voyage = _voyage(user, status="en_cours", sessions_completed=[],
                     answers={}, phrase=None)
    voyage.micro_status = "none"
    voyage.micro = {}
    db.session.commit()

    res = client.post("/api/analyses/", json={"inputs": dict(P1_FULL)},
                      headers=_auth(user))
    assert "_voyage_id" not in res.get_json()["analysis"]["inputs"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && venv/bin/python -m pytest tests/test_voyage_prompt_context.py -v`

Expected: FAIL. First failure is `test_an_analysis_without_a_voyage_carries_no_voyage_key` with
```
KeyError: 'voyage_id'
```
(from `payload["voyage_id"]`), and `test_a_voyage_is_reduced_into_the_inputs_and_stamped_on_the_row` fails with `KeyError: '_voyage_id'`.

If Step 1 found `"voyage_id"` already in `to_dict()`, the first failure is instead
```
assert None == '<voyage id>'
```
in `test_a_voyage_is_reduced_into_the_inputs_and_stamped_on_the_row`.

- [ ] **Step 4: Write minimal implementation**

**4a.** `backend/app/models/analysis.py` — add one key to `to_dict()`. Skip this edit if Step 1 found it already present. Replace line 68:

```python
            "prompt_version_id": self.prompt_version_id,
```

with:

```python
            "prompt_version_id": self.prompt_version_id,
            # Which voyage fed this analysis. Same traceability discipline as
            # prompt_version_id: the reduction stored in inputs["_voyage"] is
            # a snapshot, this says what it was a snapshot of.
            "voyage_id": self.voyage_id,
```

**4b.** `backend/app/routes/analyses.py` — imports. Replace line 10:

```python
from ..models.profile import Profile, prompt_context
```

with:

```python
from ..models.profile import Profile, prompt_context
from ..models.voyage import Voyage
from ..services.voyage.scoring import STAGE_S0
from ..services.voyage.scoring import prompt_context as voyage_prompt_context
```

The alias is required: `prompt_context` is already bound to bloc 5's reducer on the line above, and the two shape completely different things.

**4c.** `backend/app/routes/analyses.py` — stamp the column. Replace lines 90–95:

```python
    analysis = Analysis(
        user_id=user_id,
        inputs=inputs,
        status="queued",
        share_token=generate_share_token(),
    )
```

with:

```python
    analysis = Analysis(
        user_id=user_id,
        inputs=inputs,
        status="queued",
        share_token=generate_share_token(),
        # Set by _merge_voyage a few lines up. Stored on the row as well as in
        # the inputs blob so "which voyage fed this analysis" survives a JSON
        # schema change and is queryable — B2G traceability, as with
        # prompt_version_id.
        voyage_id=inputs.get("_voyage_id"),
    )
```

**4d.** `backend/app/routes/analyses.py` — restructure `_merge_profile` and add `_merge_voyage`. Replace lines 233–256 in full:

```python
def _merge_profile(inputs: dict, user_id: str | None) -> None:
    """Copy the Profil de base and le voyage into this analysis's inputs.

    The ordinary profile fields are copied so the analysis stays readable on
    its own (a later profile edit must not silently rewrite an already-
    delivered report). Bloc 5 is reduced to prompt_context() first, and the
    OETH flag becomes a plain boolean — neither the raw condition answers nor
    the status itself is ever stored on the analysis.

    The voyage fold sits *beside* the profile fold rather than inside it: a
    person can have played session 0 and never opened the profile, because S0
    is the five-minute self-serve entry and requires no profile at all.
    """
    if not user_id:
        return

    profile = Profile.query.filter_by(user_id=user_id).first()
    if profile is not None:
        for field in ("prenom", "nom", "ville", "rayon", "tranche_age",
                      "situation", "reconversion_scope", "projet",
                      "contraintes_pratiques"):
            inputs.setdefault(field, getattr(profile, field, None))

        sensitive = profile.sensitive
        if sensitive is not None:
            inputs["_conditions"] = prompt_context(sensitive.conditions)
            inputs["_oeth"] = sensitive.oeth

    _merge_voyage(inputs, user_id)


def _merge_voyage(inputs: dict, user_id: str) -> None:
    """Fold le voyage into this analysis's inputs, reduced to plain lines.

    Reduced here rather than at prompt-build time, exactly like bloc 5: the
    stored lines are what the model saw, so unlocking this analysis months
    later regenerates it from the same material instead of from whatever the
    person's voyage has become since.

    No voyage: no key. Every parcours runs identically without one, and an
    empty key would be a shape every later reader has to allow for.
    """
    voyage = Voyage.for_prompt(user_id)
    if voyage is None:
        return

    inputs["_voyage_id"] = voyage.id
    inputs["_voyage"] = voyage_prompt_context(
        voyage.synthesis(), voyage.micro_phrase, STAGE_S0
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && venv/bin/python -m pytest tests/test_voyage_prompt_context.py tests/test_parcours_inputs.py tests/test_analysis_model.py -v`

Expected: PASS — **18 passed** in `test_voyage_prompt_context.py` (Task 1's 11 plus the 7 above), and every pre-existing test in `test_parcours_inputs.py` and `test_analysis_model.py` still green.

- [ ] **Step 6: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/routes/analyses.py backend/app/models/analysis.py backend/tests/test_voyage_prompt_context.py
git commit -F - <<'MSG'
feat(voyage): fold the voyage into every new analysis

_merge_profile now folds two things, and the voyage half runs whether or not a
Profil de base exists. Session 0 is the five-minute self-serve entry and asks
for no profile, so gating the fold behind the profile lookup would have
dropped the voyage for exactly the people the module opens with.

The reduction is computed once, here, and stored on the row — the same
treatment bloc 5 gets. An unlock regenerating this analysis re-sends what the
first run sent, not whatever the person's voyage has become since.

voyage_id lands on the column as well as in the inputs blob, so "which voyage
fed which analysis" is queryable and survives a JSON shape change. Same
discipline as prompt_version_id.

Only session 0 travels for now; the validated stage is the next commit.
MSG
```

---

### Task 3: The stage rule — a draft portrait must not reach an analysis

**Files:**
- Modify: `backend/app/routes/analyses.py` (`_merge_voyage`, added in Task 2)
- Test: `backend/tests/test_voyage_prompt_context.py` (append)

**Interfaces:**
- Consumes: `scoring.STAGE_VALIDATED == "validated"` (contracts § B.1); `Voyage.portrait_status` ∈ `("none","generating","draft","validated","error")` (§ C.2); `Voyage.for_prompt` ordering (§ C.4)
- Produces: no new names. `_merge_voyage` chooses its stage instead of hardcoding `STAGE_S0`.

---

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_prompt_context.py`. Uses the Task 1 preamble — `P1_FULL`, `ALL_LABELS`, `S0_LABELS`, `_labels()`, `_ordered_subset()`, `_user()`, `_auth()`, `_voyage()`, `_all_answers()`.

```python
# ── the stage rule ───────────────────────────────────────────────────────────
#
# The load-bearing rule of the module. The paper protocol makes restitution a
# human act: a counselor reads the portrait to the person, in a room, and
# answers what it raises. Between session 5 and that conversation the draft
# exists but has been said to nobody. An analysis that quoted it would perform
# the restitution first, badly, in writing, unaccompanied.

# The eight labels a complete voyage always produces. « Ambivalences relevées »
# is left out on purpose: a person with no axis inside the tension band has no
# ambivalence, and prompt_context() drops the label rather than print an empty
# one.
ALWAYS_PRESENT = {
    "Phrase révélée",
    "Ce qui l'attire le plus dans dix ans",
    "Univers dominants",
    "Besoin dominant",
    "Cadre où elle donne le meilleur",
    "Ce qui l'épuise",
    "Ce qui la met en colère",
    "Se sent vivant(e) quand",
}


def _run(client, user):
    """POST an analysis as `user`, return the stored inputs."""
    res = client.post("/api/analyses/", json={"inputs": dict(P1_FULL)},
                      headers=_auth(user))
    assert res.status_code == 201, res.data
    return res.get_json()["analysis"]["inputs"]


@pytest.mark.parametrize("portrait_status", ["none", "generating", "draft", "error"])
@patch("app.routes.analyses.start_analysis")
def test_an_unvalidated_portrait_sends_only_session_zero(
        _start, portrait_status, client, app):
    """Every state short of `validated` stops at session 0 — including
    `draft`, which is the whole point, and `error`, which must fail closed."""
    user = _user(f"stage-{portrait_status}@test.fr")
    _voyage(user, answers=_all_answers(), portrait_status=portrait_status,
            status="termine", sessions_completed=["0", "1", "2", "3", "4", "5"],
            share_token=f"tok-{portrait_status}")

    lines = _run(client, user)["_voyage"]
    assert _labels(lines) == S0_LABELS
    assert not any(line.startswith("Univers dominants") for line in lines)


@patch("app.routes.analyses.start_analysis")
def test_a_validated_portrait_sends_the_full_reduction(_start, client, app):
    """Once a counselor has restituted, the analysis may use all of it."""
    user = _user("stage-validated@test.fr")
    _voyage(user, answers=_all_answers(), portrait_status="validated",
            status="termine", sessions_completed=["0", "1", "2", "3", "4", "5"],
            share_token="tok-validated")

    labels = _labels(_run(client, user)["_voyage"])
    assert _ordered_subset(labels, ALL_LABELS), labels
    assert ALWAYS_PRESENT <= set(labels), ALWAYS_PRESENT - set(labels)


@patch("app.routes.analyses.start_analysis")
def test_validating_widens_what_a_new_analysis_receives(_start, client, app):
    """The same voyage, before and after validation. Two lines, then more."""
    user = _user("avant-apres@test.fr")
    voyage = _voyage(user, answers=_all_answers(), portrait_status="draft",
                     status="termine",
                     sessions_completed=["0", "1", "2", "3", "4", "5"],
                     share_token="tok-avant-apres")

    before = _run(client, user)["_voyage"]
    assert _labels(before) == S0_LABELS

    voyage.portrait_status = "validated"
    voyage.portrait_validated_at = datetime(2026, 9, 12)
    db.session.commit()

    after = _run(client, user)["_voyage"]
    assert len(after) > len(before)
    assert before == after[:2], "the two session-0 lines must not be rewritten"


@patch("app.routes.analyses.start_analysis")
def test_an_earlier_analysis_is_not_rewritten_by_a_later_validation(
        _start, client, app):
    """The reduction is a snapshot. A report already delivered must not gain
    content retroactively — that is what storing it on the row buys."""
    user = _user("figee@test.fr")
    voyage = _voyage(user, answers=_all_answers(), portrait_status="draft",
                     status="termine",
                     sessions_completed=["0", "1", "2", "3", "4", "5"],
                     share_token="tok-figee")

    res = client.post("/api/analyses/", json={"inputs": dict(P1_FULL)},
                      headers=_auth(user))
    analysis_id = res.get_json()["analysis"]["id"]

    voyage.portrait_status = "validated"
    db.session.commit()

    row = Analysis.query.get(analysis_id)
    assert _labels(row.inputs["_voyage"]) == S0_LABELS


@patch("app.routes.analyses.start_analysis")
def test_a_validated_portrait_outranks_a_newer_retake(_start, client, app):
    """for_prompt takes the newest validated row first and only then the
    newest row with a phrase (contracts § C.4). A retake in progress must not
    demote a portrait a counselor has already restituted."""
    user = _user("reprise@test.fr")
    validated = _voyage(user, answers=_all_answers(), portrait_status="validated",
                        status="termine",
                        sessions_completed=["0", "1", "2", "3", "4", "5"],
                        share_token="tok-reprise", created_at=datetime(2026, 8, 1))
    newer = _voyage(user, created_at=datetime(2026, 9, 5))
    assert newer.created_at > validated.created_at

    inputs = _run(client, user)
    assert inputs["_voyage_id"] == validated.id
    assert ALWAYS_PRESENT <= set(_labels(inputs["_voyage"]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && venv/bin/python -m pytest tests/test_voyage_prompt_context.py -v -k "stage or valid or figee or reprise or avant"`

Expected: FAIL. `test_a_validated_portrait_sends_the_full_reduction` fails with
```
AssertionError: {'Univers dominants', 'Besoin dominant', 'Cadre où elle donne le meilleur', 'Ce qui l'épuise', 'Ce qui la met en colère', 'Se sent vivant(e) quand'}
assert ALWAYS_PRESENT <= set(labels), ALWAYS_PRESENT - set(labels)
```
because `_merge_voyage` still passes `STAGE_S0` unconditionally. `test_validating_widens_what_a_new_analysis_receives` and `test_a_validated_portrait_outranks_a_newer_retake` fail for the same reason. The four `test_an_unvalidated_portrait_sends_only_session_zero` cases and `test_an_earlier_analysis_is_not_rewritten_by_a_later_validation` already pass — they assert the narrow behaviour Task 2 shipped.

- [ ] **Step 3: Write minimal implementation**

**3a.** `backend/app/routes/analyses.py` — extend the import added in Task 2. Replace:

```python
from ..services.voyage.scoring import STAGE_S0
```

with:

```python
from ..services.voyage.scoring import STAGE_S0, STAGE_VALIDATED
```

**3b.** `backend/app/routes/analyses.py` — replace the body of `_merge_voyage` (the function added in Task 2) in full:

```python
def _merge_voyage(inputs: dict, user_id: str) -> None:
    """Fold le voyage into this analysis's inputs, reduced to plain lines.

    Reduced here rather than at prompt-build time, exactly like bloc 5: the
    stored lines are what the model saw, so unlocking this analysis months
    later regenerates it from the same material instead of from whatever the
    person's voyage has become since.

    Two stages, and the narrow one is the default. Until a counselor has
    validated the portrait, only session 0 travels — its phrase and its three
    attractions, which the person has already read on their own screen.
    Everything else waits for the restitution the paper protocol makes a human
    act. An analysis is not allowed to perform it first.

    No voyage: no key. Every parcours runs identically without one, and an
    empty key would be a shape every later reader has to allow for.
    """
    voyage = Voyage.for_prompt(user_id)
    if voyage is None:
        return

    stage = STAGE_VALIDATED if voyage.portrait_status == "validated" else STAGE_S0
    inputs["_voyage_id"] = voyage.id
    inputs["_voyage"] = voyage_prompt_context(
        voyage.synthesis(), voyage.micro_phrase, stage
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && venv/bin/python -m pytest tests/test_voyage_prompt_context.py -v`

Expected: PASS — **26 passed** (Task 1's 11 + Task 2's 7 + the 8 above, four of which are the parametrised `test_an_unvalidated_portrait_sends_only_session_zero`).

Note the decorator order on that parametrised test: `@pytest.mark.parametrize` **outside**, `@patch` **inside**. `@patch` injects its mock as the first positional argument and pytest strips exactly one argument when it sees `patchings` on the innermost wrapper. Swapping them makes pytest try to resolve `_start` as a fixture and fail with `fixture '_start' not found`.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/routes/analyses.py backend/tests/test_voyage_prompt_context.py
git commit -F - <<'MSG'
feat(voyage): hold the analysis to the restitution the counselor owes

After session 5 the app drafts a portrait, but nobody has read it to anyone.
Between that draft and the counselor's restitution, an analysis quoting it
would perform the conversation first — in writing, badly, with no one in the
room to answer what it raises. So the fold stays at session 0 until
portrait_status is validated, and only then widens.

Every state short of validated is narrow, `error` included: the failure mode
of a broken generation must be silence, not a half-portrait.

The reduction is a snapshot taken at creation, so validating later does not
retroactively rewrite a report already delivered. A test pins that.
MSG
```

---

### Task 4: The reduction invariants — no numbers, no framework words

A guard task. **These tests are expected to pass on their first run**: they assert properties of `scoring.prompt_context()`, which phase 0 owns. The usual red-green order is inverted on purpose — the value is in catching a future edit to the bank, the scoring tables or the reducer that lets a score or a trait name through. Phase 5 owns them because phase 5 is where those strings reach a model.

**Files:**
- Test: `backend/tests/test_voyage_prompt_context.py` (append)
- Modify: none, unless Step 2 goes red (Step 3 says exactly what to do then)

**Interfaces:**
- Consumes: `scoring.prompt_context(synthesis: dict, micro_phrase: str | None, stage: str) -> list[str]` (contracts § B.6); `scoring.synthesize(responses: dict) -> dict` (§ B.5); `scoring.LEVEL_HIGH / LEVEL_MID / LEVEL_LOW` (§ B.1); `generation.leak_check(sections: dict[str, str]) -> list[str]` and `generation.LEAK_PATTERNS` (§ G.5); `bank.AXES` (§ A.2); `bank.BIG5` (§ A.1)
- Produces: nothing consumed by later tasks.

---

- [ ] **Step 1: Write the test**

Append to `backend/tests/test_voyage_prompt_context.py`. Uses the Task 1 preamble — `PHRASE`, `ALL_LABELS`, `S0_LABELS`, `BAN_LIST`, `VOYAGE_HEADER`, `_labels()`, `_voyage_block()`.

`SYNTHESIS` below is the literal `synthesize()` return value pinned in contracts § B.5, transcribed. Hand-written rather than computed on purpose: these are the safety net under the reducer, and a net woven from the thing it is meant to catch catches nothing.

```python
# ── the reduction: what a model is allowed to be told ────────────────────────

SYNTHESIS = {
    "scoring_version": "cahier-2026-09",
    "s0": {
        "axes": {
            "A1": {"oui": 0, "non": 1, "resultant": -1, "n_items": 1, "tension": False},
            "A2": {"oui": 1, "non": 2, "resultant": -1, "n_items": 3, "tension": True},
            "A3": {"oui": 1, "non": 1, "resultant": 0, "n_items": 2, "tension": True},
            "A4": {"oui": 3, "non": 1, "resultant": 2, "n_items": 4, "tension": True},
            "A5": {"oui": 2, "non": 2, "resultant": 1, "n_items": 4, "tension": True},
            "A6": {"oui": 3, "non": 2, "resultant": 1, "n_items": 5, "tension": True},
            "A7": {"oui": 4, "non": 0, "resultant": 4, "n_items": 4, "tension": False},
            "A8": {"oui": 1, "non": 1, "resultant": 0, "n_items": 2, "tension": True},
            "A9": {"oui": 2, "non": 0, "resultant": 2, "n_items": 2, "tension": True},
            "A10": {"oui": 2, "non": 0, "resultant": 2, "n_items": 2, "tension": True},
        },
        "tensions": [
            {"axis": "A2", "resultant": -1, "label": "Visibilité",
             "tension": "discrétion vs reconnaissance"},
            {"axis": "A3", "resultant": 0, "label": "Rapport au collectif",
             "tension": "solo vs collectif"},
            {"axis": "A4", "resultant": 2, "label": "Échelle d'impact",
             "tension": "impact local vs impact global"},
            {"axis": "A5", "resultant": 1, "label": "Sécurité vs risque",
             "tension": "sécurité vs risque"},
            {"axis": "A6", "resultant": 1, "label": "Type de création",
             "tension": "méthode vs expression libre"},
            {"axis": "A8", "resultant": 0, "label": "Temporalité de l'impact",
             "tension": "impact différé vs impact immédiat"},
            {"axis": "A9", "resultant": 2, "label": "Rapport au corps",
             "tension": "bureau vs terrain"},
            {"axis": "A10", "resultant": 2, "label": "Transmission vs expertise",
             "tension": "expertise vs transmission"},
        ],
        "top3": [
            {"axis": "A7", "resultant": 4, "pole": "pos",
             "label": "Lien humain direct", "plain": "le lien avec les gens"},
            {"axis": "A4", "resultant": 2, "pole": "pos",
             "label": "Impact global / systémique", "plain": "un impact visible"},
            {"axis": "A9", "resultant": 2, "pole": "pos",
             "label": "Terrain / action physique", "plain": "le terrain et l'action"},
        ],
    },
    "riasec": {
        "scores": {"R": 8, "I": 5, "A": 3, "S": 4, "E": 7, "C": 6},
        "maxima": {"R": 12, "I": 11, "A": 10, "S": 10, "E": 11, "C": 9},
        "normalized": {"R": 0.667, "I": 0.455, "A": 0.3, "S": 0.4,
                       "E": 0.636, "C": 0.667},
        "top3": [
            {"letter": "R", "univers": "Réaliste", "score": 8, "normalized": 0.667},
            {"letter": "C", "univers": "Conventionnel", "score": 6, "normalized": 0.667},
            {"letter": "E", "univers": "Entreprenant", "score": 7, "normalized": 0.636},
        ],
    },
    "s2": {
        "sdt": {"autonomie": 3, "appartenance": 2, "competence": 1},
        "sdt_dominant": ["autonomie"],
        "schwartz": {"autodirection": 2, "stimulation": 0, "hedonisme": 0,
                     "reussite": 1, "pouvoir": 0, "securite": 0, "conformite": 1,
                     "bienveillance": 3, "universalisme": 2, "integrite": 0,
                     "conservation": 0},
        "schwartz_dominant": ["bienveillance"],
        "ambivalences": {"item_id": "S2-7", "letter": "F",
                         "label": "Liberté / Indépendance",
                         "plain": "tu veux que ta vie t'appartienne"},
    },
    "s3": {
        "big5": {"ouverture": 3, "conscienciosite": -1, "extraversion": 2,
                 "agreabilite": 0, "nevrotisme": -2},
        "levels": {"ouverture": "Élevé", "conscienciosite": "Moyen",
                   "extraversion": "Élevé", "agreabilite": "Moyen",
                   "nevrotisme": "Faible"},
        "style": {"holistique": 2, "sequentiel": 1, "adaptatif": 1, "consultatif": 3},
        "style_dominant": ["consultatif"],
        "intro_extra": "plutôt tourné(e) vers les autres",
    },
    "s4": {
        "espace": "bureau fermé et calme",
        "rythme": "cycles courts",
        "equipe": "petite équipe soudée",
        "manager": "confiance et droit à l'essai",
        "irritant": "les interruptions constantes",
        "vendredi": "besoin de calme",
    },
    "s5": {
        "risque": "Calculé",
        "rapport_echec": "elle analyse et recommence",
        "rapport_flou": "elle crée son propre cadre",
        "valeur_centrale": "l'injustice",
        "trace": "une trace dans les gens",
        "sacrifice": "le temps",
        "vivant": "elle crée",
    },
    "completeness": {"0": True, "1": True, "2": True, "3": True,
                     "4": True, "5": True},
}

EMPTY_SYNTHESIS = {
    "scoring_version": "cahier-2026-09",
    "s0": None, "riasec": None, "s2": None, "s3": None, "s4": None, "s5": None,
    "completeness": {n: False for n in ("0", "1", "2", "3", "4", "5")},
}


def _lines(stage, phrase=PHRASE, synthesis=None):
    return scoring.prompt_context(synthesis or SYNTHESIS, phrase, stage)


def test_the_fixture_has_the_shape_synthesize_really_returns():
    """This file asserts against a hand-written synthesis. Keep it honest: if
    synthesize() grows or loses a top-level section, these guards are watching
    a shape that no longer exists."""
    real = scoring.synthesize({"answers": {}, "billets": {}})
    assert set(real) == set(SYNTHESIS)


def test_the_block_never_contains_a_digit():
    """Rule 3. The synthesis is full of numbers — resultants, RIASEC scores,
    normalised ratios. None of them may cross into the prompt: a number is a
    score, and the person is never shown a score."""
    for stage in (scoring.STAGE_S0, scoring.STAGE_VALIDATED):
        block = "\n".join(_voyage_block({"_voyage": _lines(stage)}))
        assert not re.search(r"[0-9]", block), block


def test_the_block_never_contains_a_framework_word():
    """Held to the exact check the generated portrait is held to. If a
    framework word can reach the model from this side, the model can hand it
    back to the person and the cahier's rule — « jamais "score" », « jamais
    "faible" » — is broken from the other end."""
    for stage in (scoring.STAGE_S0, scoring.STAGE_VALIDATED):
        block = "\n".join(_voyage_block({"_voyage": _lines(stage)}))
        assert generation.leak_check({"voyage": block}) == []


def test_the_block_never_names_a_big_five_trait_or_a_level():
    """`big5` and `levels` are counselor-sheet vocabulary. « Faible » attached
    to a person is precisely the word the manual forbids."""
    block = "\n".join(_lines(scoring.STAGE_VALIDATED)).lower()
    for trait in bank.BIG5:
        assert not re.search(rf"\b{trait}\b", block), trait
    for level in (scoring.LEVEL_HIGH, scoring.LEVEL_MID, scoring.LEVEL_LOW):
        assert not re.search(rf"\b{level.lower()}\b", block), level


def test_the_block_never_names_an_axis_the_counselor_sheet_names():
    """AXES label/pos/neg are the manual's own vocabulary (« Mobilité
    territoriale », « Impact global / systémique »). Only plain_pos, plain_neg
    and tension may travel — contracts § A.2. Note this is case-sensitive:
    « Sécurité vs risque » is the axis label, « sécurité vs risque » is the
    tension phrase, and only the second one is allowed."""
    block = "\n".join(_lines(scoring.STAGE_VALIDATED))
    for axis_id, axis in bank.AXES.items():
        for key in ("label", "pos", "neg"):
            assert axis[key] not in block, f"{axis_id}.{key}"


def test_the_block_avoids_the_projects_banned_words():
    """CLAUDE.md's ban list. The header « CE QUE LE VOYAGE A RÉVÉLÉ » and the
    label « Phrase révélée » share a root with « révélation » and are kept on
    purpose (contracts § H): they are model-facing prompt text, not UI chrome.
    The ban is on the words, and none of them appears."""
    block = "\n".join(_voyage_block({
        "_voyage": _lines(scoring.STAGE_VALIDATED)
    })).lower()
    for word in BAN_LIST:
        assert not re.search(rf"\b{re.escape(word)}\b", block), word
    assert VOYAGE_HEADER.lower() in block


def test_the_session_zero_stage_stops_at_what_the_person_has_already_read():
    lines = _lines(scoring.STAGE_S0)
    assert _labels(lines) == S0_LABELS


def test_the_validated_stage_emits_the_nine_labels_in_order():
    assert _labels(_lines(scoring.STAGE_VALIDATED)) == ALL_LABELS


def test_an_unknown_stage_is_treated_as_session_zero():
    """Fail closed. A typo in a caller must under-disclose, never over-."""
    assert _labels(_lines("validated_ish")) == S0_LABELS
    assert _labels(_lines("")) == S0_LABELS
    assert _labels(_lines(None)) == S0_LABELS


def test_a_voyage_with_no_phrase_still_reduces_what_it_has():
    """A line with nothing after the colon is never emitted."""
    assert _labels(_lines(scoring.STAGE_S0, phrase=None)) == \
        ["Ce qui l'attire le plus dans dix ans"]


def test_an_empty_synthesis_says_nothing_rather_than_labelling_nothing():
    assert _lines(scoring.STAGE_VALIDATED, phrase=None,
                  synthesis=EMPTY_SYNTHESIS) == []
    assert _voyage_block({
        "_voyage": _lines(scoring.STAGE_S0, phrase=None, synthesis=EMPTY_SYNTHESIS)
    }) == []


def test_the_reducer_does_not_mutate_the_synthesis_it_reads():
    """prompt_context() is pure over its input — the synthesis it reads is the
    same object the portrait stores as its snapshot."""
    import copy
    before = copy.deepcopy(SYNTHESIS)
    _lines(scoring.STAGE_VALIDATED)
    assert SYNTHESIS == before
```

- [ ] **Step 2: Run the test — it must PASS**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && venv/bin/python -m pytest tests/test_voyage_prompt_context.py -v`

Expected: PASS — 38 passed.

This task inverts the red-green order because the code under test already exists (phase 0). If anything is red, do **not** patch it in `routes/analyses.py` or in the test — the defect is in `backend/app/services/voyage/scoring.py::prompt_context`. Step 3 says what the fix looks like.

- [ ] **Step 3: If Step 2 went red — fix `scoring.prompt_context`, not the test**

The three failures phase 0 can plausibly produce, and the fix for each:

**(a) `test_the_block_never_names_an_axis_the_counselor_sheet_names` fails** — the reducer read the counselor label instead of the plain one. In `scoring.prompt_context`, the attractions line must read `top["plain"]`, never `top["label"]`:

```python
    attractions = [t["plain"] for t in (s0.get("top3") or []) if t.get("plain")]
    if attractions:
        lines.append("Ce qui l'attire le plus dans dix ans : " + ", ".join(attractions))
```

and the ambivalences line must read `t["tension"]`, never `t["label"]`:

```python
    tensions = [t["tension"] for t in (s0.get("tensions") or []) if t.get("tension")]
    if tensions:
        lines.append("Ambivalences relevées : " + " · ".join(tensions))
```

**(b) `test_the_block_never_contains_a_digit` fails** — a numeric value was interpolated. Every line must be built from a string field of the synthesis; nothing from `axes`, `scores`, `normalized`, `maxima`, `sdt`, `schwartz`, `style` or `big5` may be formatted into a line. Those seven keys are counts and belong to the counselor sheet only.

**(c) `test_an_unknown_stage_is_treated_as_session_zero` fails** — the stage check tested for the narrow value instead of the wide one. Fail closed:

```python
    if stage != STAGE_VALIDATED:
        return lines[:2]
```

Re-run Step 2 after the fix. Commit the `scoring.py` change together with the tests, and say in the commit body that the defect was in phase 0.

- [ ] **Step 4: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/tests/test_voyage_prompt_context.py
git commit -F - <<'MSG'
test(voyage): pin what the model may be told about a person

The reducer sits between a psychometric synthesis and a prompt. Everything on
its left is numbers and framework vocabulary — resultants, RIASEC ratios,
névrotisme, « Faible ». Everything on its right is plain French a person could
read over someone's shoulder without learning they had been scored.

These assert that boundary from the far side: no digit, none of the seventeen
words the portrait's leak check bans, no Big Five trait, no level, and no axis
name the counselor sheet uses. The synthesis they run against is written out
by hand rather than computed — a net woven from the thing it is meant to catch
catches nothing.

An unknown stage string reduces to session 0. A caller's typo has to
under-disclose.
MSG
```

---

### Task 5: Type the three fields phase 5 puts on the wire

No test runner here. Verification is `npm run lint` and `npm run build`, plus the TEST-PLAN rows in Task 6.

**Files:**
- Modify: `frontend/src/types/index.ts:61-70` (the `AnalysisInputs` discriminator block), `:104-125` (the `Analysis` interface)
- Test: none — `next build` type-checks, and § 10.9.3 in `TEST-PLAN.md` is the manual check

**Interfaces:**
- Consumes: `Analysis.to_dict()["voyage_id"]` (Task 2); `inputs["_voyage"]`, `inputs["_voyage_id"]` (Task 2)
- Produces: `AnalysisInputs._voyage?: string[]`, `AnalysisInputs._voyage_id?: string`, `Analysis.voyage_id?: string | null`

---

- [ ] **Step 1: Read the local Next.js guidance before touching anything under `frontend/`**

`frontend/AGENTS.md` says: *"This is NOT the Next.js you know. This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code."*

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && cat AGENTS.md && ls node_modules/next/dist/docs/01-app/01-getting-started/
```
Then read `frontend/node_modules/next/dist/docs/01-app/01-getting-started/02-project-structure.md`.

This task edits a plain `.ts` type module and touches **no** Next.js API — no route file, no `proxy.ts`, no `params`, no metadata, no caching directive. Read it anyway: `npm run build` runs `next build`, which type-checks the whole app, so a wrong assumption here surfaces as a build failure with a Next.js-shaped error message.

- [ ] **Step 2: Add the three fields**

**2a.** In `frontend/src/types/index.ts`, replace lines 67–69 (the `_tier` field, the last entry in `AnalysisInputs`):

```ts
  /** Plan the analysis was generated on. "haiku"/"sonnet" on rows written
   *  before the plan-name migration — see backend services/tiers.py. */
  _tier?: "free" | "paid" | "premium" | "haiku" | "sonnet"
```

with:

```ts
  /** Plan the analysis was generated on. "haiku"/"sonnet" on rows written
   *  before the plan-name migration — see backend services/tiers.py. */
  _tier?: "free" | "paid" | "premium" | "haiku" | "sonnet"
  /** Le voyage, reduced to plain French lines at merge time — no number, no
   *  trait name, no framework name. Two lines until a counselor validates the
   *  portrait, up to nine after. Model-facing only: neither the report nor
   *  /c/<token> renders it, and neither should anything added later. */
  _voyage?: string[]
  /** Which voyage the lines above were reduced from. Mirrored onto
   *  Analysis.voyage_id. Absent when the person has no voyage — every
   *  parcours runs identically without one. */
  _voyage_id?: string
```

**2b.** In the same file, replace line 116 (inside `interface Analysis`):

```ts
  prompt_version_id: string | null
```

with:

```ts
  prompt_version_id: string | null
  /** The voyage that fed this analysis. Traceability, like
   *  prompt_version_id. Absent on responses from an older backend. */
  voyage_id?: string | null
```

- [ ] **Step 3: Lint**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`

Expected: exits 0, no new warnings mentioning `types/index.ts`.

- [ ] **Step 4: Build**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run build`

Expected: `✓ Compiled successfully`, then the route table, exit 0. Both fields are optional, so no existing call site has to change.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/types/index.ts
git commit -F - <<'MSG'
chore(voyage): type the three fields the injection puts on the wire

_voyage, _voyage_id and Analysis.voyage_id now travel on every analysis
payload. All three are optional: an account with no voyage sends none of them,
and that is the normal case.

The doc comment on _voyage says out loud that it is model-facing. Nothing
renders inputs generically today — every page reads named keys — and the
comment is there so the next person adding a « Vue conseiller » row does not
make it the first.
MSG
```

---

### Task 6: `TEST-PLAN.md` § 10 · Le voyage

**Files:**
- Modify: `TEST-PLAN.md:193-211` (renumber the two trailing sections) and insert the new § 10
- Test: none — this file *is* the manual test

**Interfaces:**
- Consumes: the behaviour shipped by Tasks 1–5
- Produces: rows `10.9.1` … `10.9.8`

Subsection **10.9** is deliberate. Phases 3 and 4 own the candidate and counselor UI rows and will take 10.1 … 10.5; starting at 10.9 means the two plans cannot collide on a row number whichever lands first.

---

- [ ] **Step 1: Find out whether phase 3 or 4 already created the section**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer && grep -n "^## " TEST-PLAN.md`

- Output contains `## 10 · Le voyage` → the section exists. Do **Step 2a** only.
- Output shows `## 10 · Print / PDF` and `## 11 · Security spot-check` with no voyage section → do **Step 2b** first, then Step 2a.

- [ ] **Step 2b: Make room for § 10 (only if the section does not exist yet)**

Renumber the two trailing sections so « Le voyage » can take § 10, matching the contract's « § 10 · Le voyage ».

Four edits in `TEST-PLAN.md`:

1. Line 193 — `## 10 · Print / PDF` → `## 11 · Print / PDF`
2. Lines 197–200 — row ids `10.1` `10.2` `10.3` `10.4` → `11.1` `11.2` `11.3` `11.4`
3. Line 204 — `## 11 · Security spot-check (optional but worth one minute)` → `## 12 · Security spot-check (optional but worth one minute)`
4. Lines 208–209 — row ids `11.1` `11.2` → `12.1` `12.2`

Then insert, immediately after line 191 (the `---` that closes § 9 Admin) and before the renumbered `## 11 · Print / PDF`:

```markdown
## 10 · Le voyage

Six sessions digitised from the paper cahier. Session 0 is 5 minutes and
self-serve; sessions 1 to 5 need a counselor code. What it finds feeds every
later analysis.

**You need to be logged in.** A counselor code is needed from § 10.9.5 on.

---
```

- [ ] **Step 2a: Add the injection rows**

Append, at the end of the `## 10 · Le voyage` section and before the `---` that closes it:

```markdown
### 10.9 Ce que le voyage change dans une analyse

The voyage never appears on a page. It reaches the model and stops there — so
most of these rows are read in the browser's Network tab, on the response to
`GET /api/analyses/<id>`. Open devtools (F12) → Network → click the request.

| # | Do | Expect |
|---|---|---|
| 10.9.1 | With a brand-new account that has **no** voyage, run a parcours 3 analysis | Runs and completes exactly as before. Nothing anywhere mentions a voyage, a session or a phrase. The voyage is never required |
| 10.9.2 | Same response in the Network tab, look at `inputs` | **No** `_voyage` key and **no** `_voyage_id` key at all. `voyage_id` is `null` |
| 10.9.3 | Now play session 0 to the end, wait for the phrase, run a parcours 1 analysis, and look at `inputs._voyage` in the response | A list of **exactly 2** short French lines: « Phrase révélée : … » and « Ce qui l'attire le plus dans dix ans : … ». `inputs._voyage_id` and `voyage_id` are the same id |
| 10.9.4 | Read those two lines carefully | **No digit anywhere.** No « score », « névrotisme », « RIASEC », « Big Five », « extraversion », « conscienciosité ». No « Élevé » / « Moyen » / « Faible ». Plain French only — if any of those appears, stop and report it, it is the one bug in this section that matters |
| 10.9.5 | Open the report itself, the « Vue conseiller » tab, and the `/c/<token>` share link | The voyage lines are rendered **nowhere**. They exist in the payload and on no page |
| 10.9.6 | Complete sessions 1 to 5 with a counselor code. **Before** the counselor validates the portrait, run a new analysis and check `inputs._voyage` | Still **exactly 2 lines**. Nothing from sessions 1–5 travels while the portrait is a draft — the person has not been restituted yet |
| 10.9.7 | Have the counselor validate the portrait, then run **another** new analysis | `inputs._voyage` now has up to 9 lines (« Univers dominants », « Besoin dominant », « Cadre où elle donne le meilleur », « Ce qui l'épuise »…). Still no digit, still no framework word |
| 10.9.8 | Re-open the analysis from § 10.9.6 and unlock it with a counselor code | It regenerates with its **own** 2 lines, not the 9 from § 10.9.7. A report already delivered is not rewritten by a later validation |
```

- [ ] **Step 3: Check the numbering is consistent**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer && grep -n "^## \|^### " TEST-PLAN.md
```
Expected: sections run `1 · Entry and navigation` … `9 · Admin`, then `10 · Le voyage`, `11 · Print / PDF`, `12 · Security spot-check`, then `What to report back`. No duplicate number.

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer && grep -n "| 10\.\|| 11\.\|| 12\." TEST-PLAN.md
```
Expected: every `10.x` row sits under § 10, every `11.x` under § 11, every `12.x` under § 12.

- [ ] **Step 4: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add TEST-PLAN.md
git commit -F - <<'MSG'
docs(voyage): manual checks for what the voyage sends to an analysis

The injection is invisible by design — it reaches the model and stops there —
so the rows read the analysis payload in the Network tab rather than a page.

10.9.4 is the one that matters: a digit or a framework word in those lines
means the person can be handed back a vocabulary the cahier spends two pages
forbidding. 10.9.6 is the second: two lines while the portrait is a draft, or
the report performs a restitution the counselor has not given yet.

Print / PDF and the security spot-check move to 11 and 12 so « Le voyage »
takes 10, as the contracts document assigns it.
MSG
```

---

### Task 7: `CLAUDE.md` — the voyage section, and which line not to delete

**Files:**
- Modify: `CLAUDE.md` — insert a new section immediately before `## Out of scope` (line 148)
- Test: none

**Interfaces:**
- Consumes: everything Tasks 1–5 shipped
- Produces: the `## Le voyage` section future sessions read as project instructions

---

- [ ] **Step 1: Read the three out-of-scope statements this section must protect**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer && sed -n '7p;43p' README.md && sed -n '246,248p' plan.md && sed -n '148,152p' CLAUDE.md
```

Expected output, in order:
- `README.md:7` — "The second module (Portrait, a guided exploration of aspirations & values) is out of scope for this implementation…"
- `README.md:43` — `| Portrait module | Out of scope |`
- `plan.md:246-248` — the `## Out of scope` heading and its paragraph, which names « Le voyage » and « le portrait »
- `CLAUDE.md:148-151` — `## Out of scope` with `- Portrait module`

**None of these four is edited by this phase.** They are read here so the section written in Step 2 names them correctly.

- [ ] **Step 2: Insert the section**

In `CLAUDE.md`, insert immediately before line 148 (`## Out of scope`):

```markdown
## Le voyage

Six sessions (S0–S5) digitised from the PM's paper cahier and its counselor
scoring manual. Session 0 is five minutes and self-serve; sessions 1–5 need a
counselor code. Scoring is arithmetic in Python — no model call — and **the
person never sees a score, a trait name or a framework name**.

- Route `/voyage`, API `/api/voyage`, tables `voyages` / `voyage_notes`
- Answers, phrase and portrait are Fernet-encrypted at rest, same util as bloc 5
- Two prompt slots in `PromptVersion.path`: `voyage_micro`, `voyage_portrait`
- Spec: `docs/superpowers/specs/2026-09-09-voyage-design.md`
- Contracts (names, types, shapes): `docs/superpowers/plans/2026-09-09-voyage-contracts.md`

### What reaches an analysis

`routes/analyses._merge_voyage()` folds the voyage into every new analysis,
beside the Profil de base fold and independent of it — session 0 requires no
profile:

- `inputs["_voyage"]` — 2 to 9 plain-French lines. No digit, no trait name, no
  framework name. Model-facing only: no page renders it.
- `inputs["_voyage_id"]` and `Analysis.voyage_id` — which voyage fed which
  analysis, recoverable afterwards. Same discipline as `prompt_version_id`.
- `anthropic_service._voyage_block()` wraps the lines under
  `--- CE QUE LE VOYAGE A RÉVÉLÉ ---` inside `_common_tail()`, so all three
  parcours carry it from one place.

Two rules hold this together, and both have tests in
`backend/tests/test_voyage_prompt_context.py`:

1. **Never required.** No voyage → no key, no block, no placeholder. Every
   parcours runs identically without one.
2. **The stage rule.** Until `portrait_status == "validated"`, an analysis
   receives only session 0's phrase and its three attractions. The full
   reduction travels only after a counselor validates — an analysis must never
   perform a restitution the counselor has not given yet.

The reduction is computed once, at merge time, and stored on the row. Unlocking
an analysis regenerates it from the same lines the first run sent, so a report
already delivered is never rewritten by a later validation.

`--- CE QUE LE VOYAGE A RÉVÉLÉ ---` and « Phrase révélée » share a root with the
banned « révélation ». They are model-facing prompt text, not UI chrome, and the
ban list does not reach them. It does reach every page: the hub says « Votre
phrase », never « Votre révélation ».

### Le voyage is not le portrait

**Do not touch these four lines.** Le portrait (Parcours doc §8) is the paid
synthesis of CV + form + voyage. It is still unbuilt, so it stays out of scope:

- `README.md:7` — the "second module (Portrait …) is out of scope" paragraph
- `README.md:43` — `| Portrait module | Out of scope |`
- `plan.md:248` — the out-of-scope paragraph of the CDC v1.2 build. It also
  names « Le voyage », because that was true of *that* build; it is a snapshot
  of a finished scope, not a live statement about this one.
- `CLAUDE.md`'s own `## Out of scope` below — `- Portrait module` stays

The six-section text a counselor validates *inside* a voyage is also called a
portrait (`portrait_status`, `/voyage/portrait`). Same French word, different
object. Deleting an out-of-scope line because "the portrait is built now" would
be deleting the wrong one.
```

- [ ] **Step 3: Verify the three protected files are untouched**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer && git status --porcelain README.md plan.md && sed -n '148,152p' CLAUDE.md
```

Expected: `git status --porcelain` prints **nothing** for `README.md` and `plan.md`, and `CLAUDE.md:148-152` still reads:

```
## Out of scope
- Portrait module
- CV-per-job adaptation
- Guided application / personal assistant
```

(The `## Out of scope` heading has moved down by the length of the inserted section; its content is unchanged.)

- [ ] **Step 4: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add CLAUDE.md
git commit -F - <<'MSG'
docs(voyage): document the module and the line nobody should delete

Two rules are worth a future session's attention before it touches this code:
the voyage is never required, and nothing from sessions 1-5 reaches an analysis
until a counselor has validated the portrait. Both have tests; neither is
obvious from reading _merge_voyage alone.

The section also names the four out-of-scope lines that stay. Le portrait is
Parcours doc §8, the paid synthesis of CV + form + voyage, and it is unbuilt —
but the six-section text a counselor validates inside a voyage carries the same
French word, so "the portrait is built now, delete the line" is a mistake
waiting to be made.
MSG
```

---

### Task 8: Verification — the whole suite, the whole frontend, nothing else moved

**Files:**
- Modify: none
- Test: the full backend suite and the frontend build

---

- [ ] **Step 1: Run the full backend suite**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && venv/bin/python -m pytest`

Expected: `N passed` with **zero failures and zero errors**. The baseline before phase 5 was `145 passed`; phase 5 adds 38 tests in `tests/test_voyage_prompt_context.py`, on top of whatever phases 0–4 added. Every pre-existing test must still pass — in particular `tests/test_parcours_inputs.py` (which asserts the message format), `tests/test_analysis_model.py` (which asserts `to_dict()`), and `tests/test_unlock.py` (which asserts regeneration keeps the stored inputs).

If a pre-existing test went red, the cause is one of two things and neither is fixed by editing that test:
- `tests/test_analysis_model.py` builds transient `Analysis` objects; the new `voyage_id` column defaults to `None` on those, and `to_dict()` must return `None` rather than raise.
- `tests/test_parcours_inputs.py` asserts on messages built from dicts with no `_voyage` key; `_voyage_block` must return `[]` for them.

- [ ] **Step 2: Run the frontend checks**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint && npm run build`

Expected: lint exits 0; build prints `✓ Compiled successfully` and the route table, exits 0.

- [ ] **Step 3: Confirm the phase touched exactly the seven files it claims**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer && git diff --name-only $(git log --format=%H -n 1 --grep="carry the voyage into every parcours message")^ HEAD
```

Expected, exactly these seven and nothing else:
```
CLAUDE.md
TEST-PLAN.md
backend/app/models/analysis.py
backend/app/routes/analyses.py
backend/app/services/anthropic_service.py
backend/tests/test_voyage_prompt_context.py
frontend/src/types/index.ts
```

`README.md` and `plan.md` must **not** appear. Neither must anything under `backend/migrations/` — this phase adds no migration.

- [ ] **Step 4: Confirm this phase created no migration**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && venv/bin/python -m flask db heads
```

Expected: a single head, `f2a3b4c5d6e7` — the one phase 1 left behind (contracts § D). Phase 5 adds no migration, so this must be identical to what it was before Task 1.

If `flask db heads` cannot run (it needs `FLASK_APP` and a reachable database), fall back to reading the chain:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && grep -h "^revision\|^down_revision" migrations/versions/*.py
```
Expected: `f2a3b4c5d6e7` appears as a `revision` and never as a `down_revision` — it is the head, and nothing in this phase's diff added a file under `migrations/versions/`.

- [ ] **Step 5: Commit the verification record**

Nothing to add — Tasks 1–7 committed their own work and Step 3 proves the set is closed. Confirm the tree is clean:

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer && git status --porcelain`

Expected: no output.

If anything is uncommitted, it belongs to whichever task produced it; commit it there with that task's message rather than in a catch-all.

- [ ] **Step 6: Deploy**

`initial` is the deploy branch: pushing builds the images and rolls them onto the VPS.

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer && git push`

Expected: GitHub Actions builds `ghcr.io/alltoft/neoori-backend` and `ghcr.io/alltoft/neoori-frontend`, syncs config and runs `docker compose up -d` on the VPS. Then check `https://neoori.tech/api/health` returns `{"status": "ok"}`.

Rollback, if the deploy misbehaves: `IMAGE_TAG=<previous-commit-sha> docker compose -f docker-compose.prod.yml up -d` on the VPS (see `DOCKER.md`).
