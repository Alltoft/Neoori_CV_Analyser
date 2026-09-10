# Le voyage — Phase 2 · Prompt slots, seeds and generation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the voyage its two AI calls — the one-sentence phrase after session 0 and the six-section portrait after session 5 — with DB-held prompts, a JSON-schema-enforced portrait shape, and a vocabulary leak check that retries once and then flags.

**Architecture:** `PromptVersion.path` becomes a *slot* id (`1` | `2` | `3` | `voyage_micro` | `voyage_portrait`), validated by a new `app/services/prompt_slots.py` that the admin route and the admin UI both read. `app/services/voyage/generation.py` runs the two calls in daemon threads copied step for step from `anthropic_service._run_analysis`: build the message and the schema first, `db.session.remove()` before the stream, re-acquire a fresh session to write the result, status → `error` with the message on failure. Two seed scripts put the French prompt text in the DB, active, so the feature works the first time someone plays.

**Tech Stack:** Flask 3 · Flask-SQLAlchemy · Anthropic Python SDK (streaming, `extra_body` output_config) · Fernet field encryption · pytest / SQLite in-memory · Next.js 16 App Router + React 19 + Tailwind v4 for the one admin page.

**Spec:** docs/superpowers/specs/2026-09-09-voyage-design.md
**Contracts:** docs/superpowers/plans/2026-09-09-voyage-contracts.md

---

## Global Constraints

- **App UI strings are FRENCH.** Code comments, docstrings and commit messages are **ENGLISH**. (`CLAUDE.md`, "Language rule".)
- **Copy ban list** — never in user-facing French text: `boussole`, `copilote`, `miroir`, `révélation`, `épanouissement`, `alignement`, `excellence`, `talent unique`, `vous vous démarquez`. The ban covers app chrome and every French string in this phase (admin labels, admin help text, seed-prompt instructions). It does **not** cover the cahier text reproduced verbatim inside the sessions (contracts, "Rules that override everything below") — no such text appears in this phase.
- **Tutoiement inside the voyage** (spec decision 15). Both system prompts address the person as *tu*. The admin chrome around them stays vouvoiement.
- **The candidate never sees a score or a trait name** (spec decision 7). Enforced in code, not in prompt prose: the message builders emit only plain French, and `leak_check()` scans what comes back.
- **Never required** — every parcours runs identically with no voyage; nothing in this phase may become a precondition of an analysis (spec decision 11).
- **Prompts live in the DB** (`PromptVersion`), never in code. Structure is enforced by a JSON-schema `output_config` passed via `extra_body`, never by prompt prose.
- **Never hold a DB connection across an Anthropic stream:** `db.session.remove()` before the stream, re-acquire a fresh session after. Precedent and comment: `backend/app/services/anthropic_service.py:463-472`.
- **Statuses are `String(16)` strings, never native enums** — widening a MySQL ENUM is the one migration step this repo cannot rehearse locally.
- **Current alembic head is `b8c9d0e1f2a3`** (`b8c9d0e1f2a3_add_progress_to_analyses.py`). **This phase adds no migration.** The four voyage migrations, ending at head `f2a3b4c5d6e7`, are phase 1's (contracts § D).
- **Tests:** pytest, SQLite in-memory, run from `/Users/imran/Downloads/design_handoff_cv_analyzer/backend` with `pytest`. Fixtures `app`, `client`, `admin_headers` come from `backend/tests/conftest.py`.
- **Frontend has no test runner.** Verification is `cd frontend && npm run lint` and `cd frontend && npm run build`, plus explicit rows in `TEST-PLAN.md`.
- **Next.js caveat** (`frontend/AGENTS.md`): *"This is NOT the Next.js you know — APIs, conventions and file structure may differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code."* Task 11 begins with that read.
- **`git push` on branch `initial` deploys.** Every commit must leave `pytest` green and `npm run build` passing.

### Prerequisites — what this phase stands on

Phase 2 is additive on top of phases 0 and 1. Do not start until these exist on `initial`:

| From | Symbol this phase calls | Contract |
|---|---|---|
| Phase 0 | `app.services.voyage.bank` — `SCORING_VERSION`, `SESSION_IDS`, `KIND_CHECKLIST`, `STYLE_PLAIN`, `session(n)`, `items(n)`, `item(id)`, `item_ids(n)` | § A |
| Phase 0 | `app.services.voyage.scoring` — `synthesize(responses)`, `chosen_option(responses, item_id)` | § B |
| Phase 1 | `app.models.voyage` — `Voyage` with `.responses`, `.micro`, `.portrait`, `.micro_phrase`, `.portrait_sections`, `.synthesis()`, and `PORTRAIT_KEYS` | § C |
| Phase 1 | migration `f2a3b4c5d6e7` widening `prompt_versions.path` to `String(16)` | § D |
| Phase 1 | `app/routes/voyage.py` calling `generation.start_micro(voyage.id, current_app._get_current_object())` and `generation.start_portrait(...)` | § E6, § E12 |

If phase 1 shipped `backend/app/services/voyage/generation.py` as a stub so its routes could import it, Task 3 **replaces the whole file**. If the file is absent, Task 3 creates it. Either way the two public names and their signatures are the ones phase 1 already calls.

---

## File Structure

| File | Created / modified | The one thing it is responsible for |
|---|---|---|
| `backend/app/services/prompt_slots.py` | create | The single answer to "what may `PromptVersion.path` hold" — five slot ids, their French labels, and `normalize()`. |
| `backend/app/services/voyage/generation.py` | create (or replace the phase-1 stub) | The two AI calls: threading and connection discipline, the message builders, the six-key schema, `leak_check()` and its one retry. |
| `backend/seed_prompt_v10_voyage_micro.py` | create | Puts the `voyage_micro` system prompt in the DB, **active**, idempotently. |
| `backend/seed_prompt_v10_voyage_portrait.py` | create | Puts the `voyage_portrait` system prompt in the DB, **active**, idempotently. |
| `backend/tests/test_prompt_slots.py` | create | The slot vocabulary, `normalize()`, and the `/api/prompts` round-trip that proves the widened column works. |
| `backend/tests/test_voyage_generation.py` | create | Schema shape, leak check, both message builders, both runners. |
| `backend/app/routes/prompts.py` | modify `:1-24` | `_read_path()` validates against `prompt_slots` instead of `section_registry`. |
| `backend/app/models/prompt_version.py` | modify `:14-17` | Guard: the `path` column must be `String(16)` (phase 1's migration widens the DB; this is the model side). |
| `backend/tests/test_seed_scripts.py` | modify `:11,14-18,20,30-33` | Widened literal regex + the two voyage seeds + the portrait's six-key declaration. |
| `backend/tests/test_prompt_section_keys.py` | modify `:23,33-47` | Skip voyage slots — they are not parcours and have no registry sections. |
| `DOCKER.md` | modify `:55-58` | The VPS seed loop gains the two voyage seeds. |
| `frontend/src/types/index.ts` | modify `:14,127-135` | `PromptSlot` type; `PromptVersion.path` widened to it. |
| `frontend/src/app/admin/prompts/page.tsx` | modify `:21-44,85-113,192-226,310-313` | The prompt selector gains the two voyage slots with their French labels and help text. |
| `TEST-PLAN.md` | modify `:179-190` | Manual rows 9.7–9.11 for the widened selector. |

Decomposition note: everything AI-call-shaped lives in one module (`generation.py`) because the two runners share `_stream_text`, the leak check and the header constants; splitting them by "builders vs runners" would put the shared constants in a third file for no gain. The slot vocabulary is its own module because three unrelated consumers read it (the prompts route, the seed guards, the admin UI).

---

## Task 1: Prompt slot registry

**Files:**
- Create: `backend/app/services/prompt_slots.py`
- Test: `backend/tests/test_prompt_slots.py`

**Interfaces:**
- Consumes: `app.services.section_registry` — `PARCOURS` (dict keyed `"1"`,`"2"`,`"3"`), `DEFAULT_PARCOURS` (`"1"`), `normalize(parcours) -> str` (`backend/app/services/section_registry.py:111-127`).
- Produces: `prompt_slots.VOYAGE_MICRO = "voyage_micro"`, `prompt_slots.VOYAGE_PORTRAIT = "voyage_portrait"`, `VOYAGE_SLOTS`, `LABELS`, `valid() -> tuple[str, ...]`, `is_valid(slot) -> bool`, `is_voyage(slot) -> bool`, `normalize(slot) -> str`, `label(slot) -> str`, `choices() -> list[dict]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_prompt_slots.py`:

```python
"""What PromptVersion.path is allowed to hold.

The column used to be String(1) and to hold a parcours id only. The voyage
needs two more prompts, and calling them "4" and "5" would make them show up as
parcours everywhere the section registry is iterated (spec decision 18). They
are slots instead, and this file is the guard on that vocabulary.
"""
import json

from app.extensions import db
from app.models.prompt_version import PromptVersion
from app.services import prompt_slots
from app.services import section_registry as registry


# ── the vocabulary ───────────────────────────────────────────────────────────

def test_valid_lists_the_three_parcours_then_the_two_voyage_slots():
    assert prompt_slots.valid() == ("1", "2", "3", "voyage_micro", "voyage_portrait")


def test_every_parcours_id_is_a_slot():
    for parcours in registry.PARCOURS:
        assert prompt_slots.is_valid(parcours)


def test_the_voyage_slots_are_valid_and_recognised_as_voyage():
    assert prompt_slots.is_valid("voyage_micro")
    assert prompt_slots.is_valid("voyage_portrait")
    assert prompt_slots.is_voyage("voyage_micro")
    assert prompt_slots.is_voyage("voyage_portrait")


def test_a_parcours_id_is_not_a_voyage_slot():
    for parcours in ("1", "2", "3"):
        assert not prompt_slots.is_voyage(parcours)


def test_unknown_values_are_not_valid():
    for value in ("4", "voyage", "VOYAGE_MICRO", "", None, "voyage_micro "):
        assert not prompt_slots.is_valid(value)


# ── normalize ────────────────────────────────────────────────────────────────

def test_normalize_keeps_a_voyage_slot_verbatim_before_uppercasing():
    """_read_path used to .upper() before validating, and "VOYAGE_MICRO" is not
    a slot. The voyage check has to run first."""
    assert prompt_slots.normalize("voyage_micro") == "voyage_micro"
    assert prompt_slots.normalize("  Voyage_Portrait  ") == "voyage_portrait"


def test_normalize_still_folds_the_legacy_path_codes():
    assert prompt_slots.normalize("A") == "1"
    assert prompt_slots.normalize("b") == "3"


def test_normalize_falls_back_to_parcours_1():
    assert prompt_slots.normalize("") == registry.DEFAULT_PARCOURS
    assert prompt_slots.normalize(None) == registry.DEFAULT_PARCOURS
    assert prompt_slots.normalize("nimporte quoi") == registry.DEFAULT_PARCOURS


# ── labels for the admin selector ────────────────────────────────────────────

def test_labels_are_french_and_cover_every_slot():
    for slot in prompt_slots.valid():
        assert prompt_slots.label(slot)
    assert prompt_slots.label("voyage_micro") == "Voyage · phrase (S0)"
    assert prompt_slots.label("voyage_portrait") == "Voyage · portrait"


def test_choices_feeds_the_admin_selector_in_order():
    assert prompt_slots.choices() == [
        {"value": "1", "label": "Parcours 1 · J'ai une cible"},
        {"value": "2", "label": "Parcours 2 · Je cherche ma direction"},
        {"value": "3", "label": "Parcours 3 · Je pars de zéro"},
        {"value": "voyage_micro", "label": "Voyage · phrase (S0)"},
        {"value": "voyage_portrait", "label": "Voyage · portrait"},
    ]


def test_no_label_uses_a_banned_word():
    """CLAUDE.md's ban list applies to every French string the admin reads."""
    banned = ("boussole", "copilote", "miroir", "révélation", "épanouissement",
              "alignement", "excellence", "talent unique", "vous vous démarquez")
    blob = " ".join(prompt_slots.LABELS.values()).lower()
    for word in banned:
        assert word not in blob


# ── the widened column ───────────────────────────────────────────────────────

def test_the_path_column_holds_the_longest_slot(app):
    """String(1) truncates "voyage_portrait" to "v" on MySQL and the prompt
    lookup then finds nothing. Phase 1's migration f2a3b4c5d6e7 widens the
    column; this is the round-trip that proves the model agrees with it."""
    assert PromptVersion.__table__.c.path.type.length >= len("voyage_portrait")
    db.session.add(PromptVersion(version_label="v0-test", system_prompt_text="x",
                                 is_active=True, path="voyage_portrait"))
    db.session.commit()
    row = PromptVersion.query.filter_by(is_active=True, path="voyage_portrait").first()
    assert row is not None
    assert row.path == "voyage_portrait"
```

Leave `import json` in place — Task 2 adds tests to this same file that use it. (If your linter objects at this step, add the route tests from Task 2 first; nothing else depends on the ordering.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_prompt_slots.py -v`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'app.services.prompt_slots'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/prompt_slots.py`:

```python
"""Valid values for PromptVersion.path — parcours ids plus the voyage prompt slots.

Widened from String(1) to String(16) so the two voyage prompts do not have to
masquerade as parcours "4"/"5" everywhere the section registry is iterated
(spec decision 18). "voyage_portrait" is 15 characters; String(16) is the exact
fit and the reason for that width.

Lives beside section_registry.py and tiers.py because it is the same kind of
thing: one table, so the routes, the seed guards and the admin UI cannot drift.
"""
from . import section_registry as registry

VOYAGE_MICRO = "voyage_micro"
VOYAGE_PORTRAIT = "voyage_portrait"
VOYAGE_SLOTS = (VOYAGE_MICRO, VOYAGE_PORTRAIT)

# French, admin-facing. The ban list in CLAUDE.md applies here.
LABELS = {
    "1": "Parcours 1 · J'ai une cible",
    "2": "Parcours 2 · Je cherche ma direction",
    "3": "Parcours 3 · Je pars de zéro",
    VOYAGE_MICRO: "Voyage · phrase (S0)",
    VOYAGE_PORTRAIT: "Voyage · portrait",
}


def valid() -> tuple[str, ...]:
    """('1', '2', '3', 'voyage_micro', 'voyage_portrait') — parcours ids first."""
    return tuple(registry.PARCOURS) + VOYAGE_SLOTS


def is_valid(slot) -> bool:
    return slot in valid()


def is_voyage(slot) -> bool:
    return slot in VOYAGE_SLOTS


def normalize(slot) -> str:
    """Coerce a stored or client-supplied slot id to a known value.

    The voyage check runs BEFORE any .upper(): routes/prompts._read_path used to
    uppercase first, and "VOYAGE_MICRO" is not a slot. Parcours ids fall through
    to the registry, which still folds the legacy 'A'/'B' path codes.
    """
    value = str(slot or "").strip()
    if not value:
        return registry.DEFAULT_PARCOURS
    lowered = value.lower()
    if lowered in VOYAGE_SLOTS:
        return lowered
    return registry.normalize(value.upper())


def label(slot: str) -> str:
    return LABELS.get(slot, LABELS[registry.DEFAULT_PARCOURS])


def choices() -> list[dict]:
    """[{"value": ..., "label": ...}] for the admin selector, in valid() order."""
    return [{"value": s, "label": LABELS[s]} for s in valid()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_prompt_slots.py -v`
Expected: PASS — 11 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/services/prompt_slots.py backend/tests/test_prompt_slots.py
git commit -m "feat(voyage): name the two prompt slots the voyage needs

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

## Task 2: `/api/prompts` accepts the two slots

**Files:**
- Modify: `backend/app/routes/prompts.py:1-24`
- Modify: `backend/app/models/prompt_version.py:14-17`
- Test: `backend/tests/test_prompt_slots.py` (append)

**Interfaces:**
- Consumes: `prompt_slots.normalize`, `prompt_slots.is_valid`, `prompt_slots.valid` (Task 1).
- Produces: `POST /api/prompts/` and `GET /api/prompts/active?path=…` accept `voyage_micro` / `voyage_portrait`; `_read_path(raw) -> (slot, error_response)` unchanged in shape.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_prompt_slots.py`:

```python
# ── the API round-trip ───────────────────────────────────────────────────────

def test_a_voyage_slot_survives_the_round_trip_through_the_api(client, admin_headers):
    res = client.post("/api/prompts/", headers=admin_headers, json={
        "version_label": "v0-vm",
        "system_prompt_text": "Tu écris une phrase.",
        "path": "voyage_micro",
        "activate": True,
    })
    assert res.status_code == 201
    assert json.loads(res.data)["prompt"]["path"] == "voyage_micro"

    res = client.get("/api/prompts/active?path=voyage_micro")
    assert res.status_code == 200
    assert json.loads(res.data)["prompt"]["version_label"] == "v0-vm"


def test_an_uppercased_slot_no_longer_breaks_the_lookup(client, admin_headers):
    """_read_path used to .upper() before validating, so "VOYAGE_PORTRAIT" would
    have been rejected as an unknown parcours."""
    client.post("/api/prompts/", headers=admin_headers, json={
        "version_label": "v0-vp",
        "system_prompt_text": "Tu écris six sections.",
        "path": "voyage_portrait",
        "activate": True,
    })
    res = client.get("/api/prompts/active?path=VOYAGE_PORTRAIT")
    assert res.status_code == 200
    assert json.loads(res.data)["prompt"]["version_label"] == "v0-vp"


def test_a_voyage_prompt_does_not_deactivate_a_parcours_prompt(client, admin_headers):
    """Activation is scoped per slot. Publishing the portrait prompt must not
    turn off parcours 1's — every analysis would fail on the next run."""
    client.post("/api/prompts/", headers=admin_headers, json={
        "version_label": "v9.9-P1", "system_prompt_text": "p1",
        "path": "1", "activate": True,
    })
    client.post("/api/prompts/", headers=admin_headers, json={
        "version_label": "v0-vp2", "system_prompt_text": "vp",
        "path": "voyage_portrait", "activate": True,
    })
    res = client.get("/api/prompts/active?path=1")
    assert res.status_code == 200
    assert json.loads(res.data)["prompt"]["version_label"] == "v9.9-P1"


def test_an_unknown_path_folds_to_parcours_1(client, admin_headers):
    """Pinned by the contracts doc: _read_path runs prompt_slots.normalize(),
    which folds anything unknown onto the default parcours, so its 400 branch is
    unreachable. Recorded here so the behaviour is a deliberate, visible fact
    rather than a surprise — see the plan's deviations list."""
    res = client.post("/api/prompts/", headers=admin_headers, json={
        "version_label": "v0-unknown", "system_prompt_text": "x", "path": "9",
    })
    assert res.status_code == 201
    assert json.loads(res.data)["prompt"]["path"] == "1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_prompt_slots.py -v`
Expected: FAIL — `test_a_voyage_slot_survives_the_round_trip_through_the_api` fails with `assert 400 == 201` (the current `_read_path` uppercases `"voyage_micro"` to `"VOYAGE_MICRO"` and rejects it with `{"error": "path doit être l'un de '1', '2', '3'."}`).

- [ ] **Step 3: Write minimal implementation**

Replace `backend/app/routes/prompts.py:1-24` (everything from the imports down to the end of `_read_path`) with:

```python
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models.prompt_version import PromptVersion
from ..services import prompt_slots
from ..utils.decorators import admin_required

prompts_bp = Blueprint("prompts", __name__)

_SLOTS_LABEL = ", ".join(f"'{s}'" for s in prompt_slots.valid())


def _read_path(raw):
    """Validate a prompt slot from the request, accepting legacy 'A'/'B'.

    A slot is a parcours id or one of the two voyage prompts (spec decision 18).
    Rows written before the 3-parcours migration still carry the old codes, so
    the admin UI can address them.

    Returns (slot, error_response).
    """
    slot = prompt_slots.normalize(raw)
    if not prompt_slots.is_valid(slot):
        return None, (jsonify({"error": f"path doit être l'un de {_SLOTS_LABEL}."}), 400)
    return slot, None
```

`section_registry` is no longer referenced anywhere in this file (it was used only at the old lines 5, 10 and 19-23), so its import is gone from the block above. Leave the rest of the file (`list_prompts` onwards, old lines 27-114) untouched.

Then open `backend/app/models/prompt_version.py:14-17`. If the `path` column still reads `db.String(1)` — phase 1 widens the DB, and the model has to agree or SQLAlchemy will keep declaring a 1-char VARCHAR on `create_all()` in the test DB — replace those four lines with:

```python
    # Prompt slot — '1' | '2' | '3' | 'voyage_micro' | 'voyage_portrait'.
    # See services/prompt_slots.py. Rows written before the v1.2 migration
    # carried 'A'/'B'; normalize() still accepts those on read. Widened from
    # String(1) by migration f2a3b4c5d6e7 — 'voyage_portrait' is 15 characters.
    path = db.Column(db.String(16), nullable=False, default='1', server_default='1')
```

If it already reads `db.String(16)`, phase 1 did it: change nothing.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_prompt_slots.py -v`
Expected: PASS — 15 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/routes/prompts.py backend/app/models/prompt_version.py backend/tests/test_prompt_slots.py
git commit -m "feat(prompts): accept the voyage slots on PromptVersion.path

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

## Task 3: The generation module and the six-key portrait schema

**Files:**
- Create (or fully replace phase 1's stub): `backend/app/services/voyage/generation.py`
- Test: `backend/tests/test_voyage_generation.py`

**Interfaces:**
- Consumes: `prompt_slots.VOYAGE_MICRO`, `prompt_slots.VOYAGE_PORTRAIT` (Task 1); `app.models.voyage.PORTRAIT_KEYS` (phase 1, contracts § C.1); `tiers.model_for(tier) -> (model, max_tokens)` (`backend/app/services/tiers.py:63-68`).
- Produces: `MICRO_SLOT`, `PORTRAIT_SLOT`, `MICRO_MAX_TOKENS = 200`, `PORTRAIT_MAX_TOKENS = 3000`, `MICRO_WORDS = (15, 25)`, `PORTRAIT_KEYS`, `PORTRAIT_TITLES`, `FLAG_VOCABULAIRE = "vocabulaire"`, `ERROR_MAX_CHARS = 500`, `HEADER_PROFIL`, `HEADER_SESSION_0`, `HEADER_CHOISI`, `HEADER_SYNTHESE`, `WEIGHT_NOTE`, `_portrait_schema() -> dict`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_voyage_generation.py`:

```python
"""The voyage's two AI calls.

Everything the person will read comes out of these two calls, and two things
have to be true of both: the portrait always has its six sections (a JSON
schema, not a sentence in the prompt), and neither call ever hands the model —
or gets back — a score, a trait name or a framework name.
"""
import copy
import json
import re
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import anthropic
import httpx

from app.extensions import db
from app.models.prompt_version import PromptVersion
from app.models.profile import Profile
from app.models.user import User
from app.models.voyage import Voyage
from app.services import prompt_slots, tiers
from app.services.voyage import bank, scoring
from app.services.voyage import generation as gen


# ── fixtures ─────────────────────────────────────────────────────────────────

PROFILE_FIELDS = {
    "prenom": "Marie",
    "tranche_age": "25_34",
    "situation": "en_recherche",
    "projet": "reprendre un travail au contact des gens",
}

# The literal synthesize() return value pinned in the contracts doc § B.5.
# `risque` is deliberately "Calculé": "Faible" is both a risk level and a Big
# Five level word, and the vocabulary assertions below would not be able to
# tell the legitimate one from a leak.
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
        "normalized": {"R": 0.667, "I": 0.455, "A": 0.3, "S": 0.4, "E": 0.636, "C": 0.667},
        "top3": [
            {"letter": "R", "univers": "Réaliste", "score": 8, "normalized": 0.667},
            {"letter": "C", "univers": "Conventionnel", "score": 6, "normalized": 0.667},
            {"letter": "E", "univers": "Entreprenant", "score": 7, "normalized": 0.636},
        ],
    },
    "s2": {
        "sdt": {"autonomie": 3, "appartenance": 2, "competence": 1},
        "sdt_dominant": ["autonomie"],
        "schwartz": {"autodirection": 2, "stimulation": 0, "hedonisme": 0, "reussite": 1,
                     "pouvoir": 0, "securite": 0, "conformite": 1, "bienveillance": 3,
                     "universalisme": 2, "integrite": 0, "conservation": 0},
        "schwartz_dominant": ["bienveillance"],
        "ambivalences": {"item_id": "S2-7", "letter": "F",
                         "label": "Liberté / Indépendance",
                         "plain": "tu veux que ta vie t'appartienne"},
    },
    "s3": {
        "big5": {"ouverture": 3, "conscienciosite": -1, "extraversion": 2,
                 "agreabilite": 0, "nevrotisme": -2},
        "levels": {"ouverture": "Élevé", "conscienciosite": "Moyen", "extraversion": "Élevé",
                   "agreabilite": "Moyen", "nevrotisme": "Faible"},
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
    "completeness": {"0": True, "1": True, "2": True, "3": True, "4": True, "5": True},
}

CLEAN_SECTIONS = {
    "accroche": "Tu cherches des endroits où ce que tu fabriques sert vraiment à quelqu'un.",
    "qui_tu_es": "Tu as tendance à comprendre avant d'agir. Quand on te laisse de la marge, "
                 "tu vas vite. Les journées hachées te demandent plus d'énergie.",
    "vibrer": "Ce qui te met en mouvement, c'est de voir le résultat de ce que tu fais.",
    "besoins": "Tu travailles mieux au calme, avec des cycles courts et une petite équipe.",
    "chemins": "Les endroits où on fabrique, où on répare, où on met en route quelque chose.",
    "pas_encore": "Il reste une question : ce dont tu as besoin pour tenir sur la durée.",
}

LEAKY_SECTIONS = {
    **CLEAN_SECTIONS,
    "qui_tu_es": "Ton score de névrotisme est bas et ton RIASEC est net.",
}


def _full_responses() -> dict:
    """Every one of the 53 items answered: OUI on session 0, the first option
    everywhere else. Built from the bank, so it survives a bank edit."""
    answers = {}
    for n in bank.SESSION_IDS:
        checklist = bank.session(n)["kind"] == bank.KIND_CHECKLIST
        for item in bank.items(n):
            answers[item["id"]] = True if checklist else item["options"][0]["letter"]
    return {"answers": answers, "billets": {}}


def _s0_only_responses() -> dict:
    full = _full_responses()
    s0 = set(bank.item_ids("0"))
    return {"answers": {k: v for k, v in full["answers"].items() if k in s0},
            "billets": {}}


_HEADER_RE = re.compile(r"^---\s.+\s---$", re.MULTILINE)


def _block(message: str, header: str) -> str:
    """The lines under `header`, up to the next --- ... --- header."""
    assert header in message, f"{header} missing from the message"
    rest = message.split(header, 1)[1]
    nxt = _HEADER_RE.search(rest)
    return rest[: nxt.start()] if nxt else rest


def _line(message: str, prefix: str) -> str:
    """The single line starting with `prefix`, with the prefix removed."""
    hits = [ln for ln in message.splitlines() if ln.startswith(prefix)]
    assert len(hits) == 1, f"expected exactly one line starting with {prefix!r}"
    return hits[0][len(prefix):]


# ── the portrait schema ──────────────────────────────────────────────────────

def test_the_portrait_schema_has_exactly_the_six_keys():
    schema = gen._portrait_schema()
    assert schema["type"] == "object"
    assert set(schema["properties"]) == set(gen.PORTRAIT_KEYS)
    assert schema["required"] == list(gen.PORTRAIT_KEYS)
    assert schema["additionalProperties"] is False


def test_every_portrait_property_is_a_described_string():
    """The description is where the per-section length and form rules live —
    the schema, not the prompt prose, is what the model cannot ignore."""
    for key, prop in gen._portrait_schema()["properties"].items():
        assert prop["type"] == "string", key
        assert prop["description"].strip(), key


def test_the_schema_keys_match_the_model_and_the_titles():
    from app.models import voyage as voyage_model
    assert tuple(gen.PORTRAIT_KEYS) == tuple(voyage_model.PORTRAIT_KEYS)
    assert tuple(gen.PORTRAIT_TITLES) == tuple(gen.PORTRAIT_KEYS)


def test_the_two_slots_are_the_ones_the_prompt_registry_knows():
    assert gen.MICRO_SLOT == prompt_slots.VOYAGE_MICRO
    assert gen.PORTRAIT_SLOT == prompt_slots.VOYAGE_PORTRAIT


def test_the_token_budgets_are_the_two_the_spec_pins_not_the_tier_defaults():
    """tiers.model_for() hands back 8000 for both plans. A one-sentence phrase
    does not need 8000, and the portrait is capped at 3000 on purpose."""
    assert gen.MICRO_MAX_TOKENS == 200
    assert gen.PORTRAIT_MAX_TOKENS == 3000
    assert gen.MICRO_WORDS == (15, 25)
    assert gen.PORTRAIT_MAX_TOKENS != tiers.model_for(tiers.PAID)[1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_generation.py -v`
Expected: FAIL at collection with `ImportError: cannot import name 'generation' from 'app.services.voyage'` (or, if phase 1 left a stub, `AttributeError: module 'app.services.voyage.generation' has no attribute 'PORTRAIT_KEYS'`).

- [ ] **Step 3: Write minimal implementation**

Create — or, if a phase-1 stub is there, **replace the whole file** — `backend/app/services/voyage/generation.py`:

```python
"""The voyage's two AI calls: the session-0 phrase and the six-section portrait.

Same discipline as anthropic_service._run_analysis: a daemon thread, the DB
connection released before the stream, a fresh session to write the result,
status -> "error" with the message on failure. The user message and the schema
are built BEFORE db.session.remove(), never from an ORM object held across the
stream.

Two things are enforced in code rather than in prompt prose, because the prompt
text is the PM's to rewrite at any moment from /admin/prompts:

  * structure — the portrait's six keys come from a JSON-schema output_config
    passed via extra_body, exactly as the analysis runner does it;
  * vocabulary — leak_check() scans the returned prose for the framework words
    the person must never read, retries once with a corrective turn, then keeps
    the draft and flags it for the counselor.

Nothing here writes an answer, a score or a portrait sentence to a log.
"""
import json
import re
import threading
import unicodedata

import anthropic
from json_repair import repair_json

from ...extensions import db
from ...models.profile import Profile
from ...models.prompt_version import PromptVersion
from ...models.voyage import Voyage
from .. import prompt_slots
from .. import tiers
from ..anthropic_service import _extract_json_candidate, _get_client
from . import bank
from . import scoring

# ── slots and budgets ────────────────────────────────────────────────────────

MICRO_SLOT = prompt_slots.VOYAGE_MICRO
PORTRAIT_SLOT = prompt_slots.VOYAGE_PORTRAIT

# The tier's own max_tokens (8000) is discarded: one sentence does not need it,
# and the portrait is deliberately capped below it.
MICRO_MAX_TOKENS = 200
PORTRAIT_MAX_TOKENS = 3000
MICRO_WORDS = (15, 25)          # the counselor manual's « 1 phrase, 15-25 mots »

PORTRAIT_KEYS = ("accroche", "qui_tu_es", "vibrer", "besoins", "chemins", "pas_encore")

# The counselor manual's page-20 template, in order. Mirrored in
# frontend/src/types/voyage.ts PORTRAIT_SECTIONS.
PORTRAIT_TITLES = {
    "accroche": "Phrase d'accroche",
    "qui_tu_es": "Qui tu es",
    "vibrer": "Ce qui te fait vibrer",
    "besoins": "Ce dont tu as besoin",
    "chemins": "Les chemins possibles",
    "pas_encore": "Ce que ton portrait ne dit pas encore",
}

FLAG_VOCABULAIRE = "vocabulaire"    # the only value ever written into portrait["flags"]
ERROR_MAX_CHARS = 500               # the encrypted payload's `error` key is capped

# ── user-message section headers ─────────────────────────────────────────────

HEADER_PROFIL = "--- PROFIL DE BASE ---"      # reused from anthropic_service._profile_block
HEADER_SESSION_0 = "--- SESSION 0 ---"
HEADER_CHOISI = "--- CE QUE TU AS CHOISI ---"
HEADER_SYNTHESE = "--- SYNTHÈSE ---"

# The manual weights an ambivalence x1.5 when writing the portrait. It is the
# only figure either message is allowed to carry.
WEIGHT_NOTE = " (à pondérer ×1,5)"


# ── the portrait's output schema ─────────────────────────────────────────────
# Structure is enforced at the API layer, never via the prompt text: the PM
# rewrites the prompt freely and the six sections must survive it.
# See https://platform.claude.com/docs/en/build-with-claude/structured-outputs

def _portrait_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "accroche": {"type": "string",
                         "description": "Une phrase. Une métaphore unique. Jamais « Tu es… ». "
                                        "Jamais un métier nommé."},
            "qui_tu_es": {"type": "string",
                          "description": "5 à 7 phrases de prose. Mode de fonctionnement, énergie. "
                                         "Aucune liste."},
            "vibrer": {"type": "string",
                       "description": "4 à 6 phrases de prose. Motivations, source d'énergie, sens."},
            "besoins": {"type": "string",
                        "description": "5 à 7 phrases de prose. Cadre physique, cognitif et "
                                       "relationnel, formulé en préférences légitimes."},
            "chemins": {"type": "string",
                        "description": "4 à 5 phrases de prose. Familles d'environnements — "
                                       "« les gens qui… », « les endroits où… ». Jamais un métier."},
            "pas_encore": {"type": "string",
                           "description": "1 à 2 phrases. Une question ouverte que les sessions ne "
                                          "tranchent pas."},
        },
        "required": list(PORTRAIT_KEYS),
        "additionalProperties": False,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_generation.py -v`
Expected: PASS — 5 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/services/voyage/generation.py backend/tests/test_voyage_generation.py
git commit -m "feat(voyage): pin the portrait's six sections in a JSON schema

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

## Task 4: `leak_check()` — the vocabulary the person must never read

**Files:**
- Modify: `backend/app/services/voyage/generation.py` (append after `_portrait_schema`)
- Test: `backend/tests/test_voyage_generation.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces: `LEAK_PATTERNS: tuple[str, ...]` (17 entries), `leak_check(sections: dict[str, str]) -> list[str]`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_generation.py`:

```python
# ── leak_check ───────────────────────────────────────────────────────────────

def test_a_clean_portrait_leaks_nothing():
    assert gen.leak_check(CLEAN_SECTIONS) == []


def test_the_word_portrait_does_not_trip_the_trait_pattern():
    """Word boundaries are the whole reason « trait » is safe to ban."""
    assert gen.leak_check({
        "accroche": "Ce portrait te ressemble.",
        "qui_tu_es": "Tu traites les choses une par une.",
    }) == []


def test_framework_words_come_back_lowercased_and_sorted():
    hit = gen.leak_check({"qui_tu_es": "Ton RIASEC est net.",
                          "vibrer": "Un Score élevé en Big Five."})
    assert hit == ["big five", "riasec", "score"]


def test_accents_are_folded_so_one_entry_catches_both_spellings():
    assert gen.leak_check({"a": "névrotisme"}) == ["névrotisme"]
    assert gen.leak_check({"a": "nevrotisme"}) == ["névrotisme"]
    assert gen.leak_check({"a": "CONSCIENCIOSITE"}) == ["conscienciosité"]


def test_the_seventeen_patterns_the_spec_lists_are_all_detected():
    assert len(gen.LEAK_PATTERNS) == 17
    for pattern in gen.LEAK_PATTERNS:
        assert gen.leak_check({"x": f"Une phrase avec {pattern} dedans."}) == [pattern]


def test_empty_and_missing_sections_are_tolerated():
    assert gen.leak_check({}) == []
    assert gen.leak_check(None) == []
    assert gen.leak_check({"accroche": None, "vibrer": ""}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_generation.py -k leak -v`
Expected: FAIL with `AttributeError: module 'app.services.voyage.generation' has no attribute 'leak_check'`

- [ ] **Step 3: Write minimal implementation**

Append to `backend/app/services/voyage/generation.py`:

```python
# ── leak check ───────────────────────────────────────────────────────────────
# Layered, exactly as the spec asks: the prompt forbids these words, this scan
# catches what survives, and a counselor validates before the person reads it.
#
# scoring.INTRO_EXTRA, bank.STYLE_PLAIN and every `plain` / `plain_pos` /
# `plain_neg` / `tension` string in the bank are free of all seventeen — that is
# why intro_extra says « plutôt tourné(e) vers les autres » and not
# « extraversion ». test_voyage_generation.py holds that line for the two
# message builders.

LEAK_PATTERNS = (
    "névrotisme",
    "neuroticisme",
    "big five",
    "riasec",
    "schwartz",
    "sdt",
    "dunn",
    "kahneman",
    "dweck",
    "frankl",
    "logothérapie",
    "conscienciosité",
    "agréabilité",
    "extraversion",
    "introversion",
    "score",
    "trait",
)


def _fold(text: str) -> str:
    """Lowercase and drop combining marks, so « névrotisme » and « nevrotisme »
    are the same string and one pattern catches both."""
    decomposed = unicodedata.normalize("NFD", str(text or "").lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


# Word-boundary matching is what keeps « trait » from firing inside
# « portrait » and « score » from firing inside « scorer ».
_LEAK_RE = tuple(
    (pattern, re.compile(rf"\b{re.escape(_fold(pattern))}\b"))
    for pattern in LEAK_PATTERNS
)


def leak_check(sections) -> list[str]:
    """Framework vocabulary that survived into the portrait.

    Returns the offending words, lowercased, de-duplicated, sorted — [] when
    clean. Matching is word-boundary, case-insensitive and diacritic-folded on
    both the text and the pattern.
    """
    haystack = _fold(" ".join(str(v or "") for v in (sections or {}).values()))
    return sorted({pattern for pattern, rx in _LEAK_RE if rx.search(haystack)})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_generation.py -v`
Expected: PASS — 11 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/services/voyage/generation.py backend/tests/test_voyage_generation.py
git commit -m "feat(voyage): scan the portrait for the vocabulary it must never use

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

## Task 5: `_micro_user_message()` — session 0 in plain words

**Files:**
- Modify: `backend/app/services/voyage/generation.py` (append)
- Test: `backend/tests/test_voyage_generation.py` (append)

**Interfaces:**
- Consumes: `synthesis["s0"]["top3"][*]["plain"]` and `synthesis["s0"]["tensions"][*]["tension"]` (contracts § B.4).
- Produces: `_micro_user_message(synthesis: dict, prenom: str | None) -> str`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_generation.py`:

```python
# ── _micro_user_message ──────────────────────────────────────────────────────

def test_the_micro_message_has_the_two_blocks_in_order():
    msg = gen._micro_user_message(SYNTHESIS, "Marie")
    assert msg.index(gen.HEADER_PROFIL) < msg.index(gen.HEADER_SESSION_0)
    assert "Prénom : Marie" in msg


def test_the_micro_message_names_the_three_strongest_pulls_in_plain_french():
    msg = gen._micro_user_message(SYNTHESIS, "Marie")
    assert _line(msg, "Ce qui l'attire le plus : ") == (
        "le lien avec les gens, un impact visible, le terrain et l'action")


def test_the_micro_message_joins_the_tensions_with_a_middle_dot():
    msg = gen._micro_user_message(SYNTHESIS, "Marie")
    line = _line(msg, "Autant coché des deux côtés sur : ")
    assert line.split(" · ") == [t["tension"] for t in SYNTHESIS["s0"]["tensions"]]


def test_a_voyage_with_no_tension_gets_no_tension_line():
    """A label with nothing after it is worse than no label."""
    synthesis = copy.deepcopy(SYNTHESIS)
    synthesis["s0"]["tensions"] = []
    assert "Autant coché" not in gen._micro_user_message(synthesis, "Marie")


def test_the_profile_block_disappears_when_the_prenom_is_unknown():
    msg = gen._micro_user_message(SYNTHESIS, None)
    assert gen.HEADER_PROFIL not in msg
    assert "Prénom" not in msg
    assert msg.startswith(gen.HEADER_SESSION_0)


def test_an_s0_that_has_not_been_scored_yet_yields_an_empty_message():
    assert gen._micro_user_message({"s0": None}, None) == ""


def test_the_micro_message_carries_no_number_and_no_framework_word():
    msg = gen._micro_user_message(SYNTHESIS, "Marie")
    assert not re.search(r"\d", msg)
    assert gen.leak_check({"message": msg}) == []
    for word in ("Élevé", "Moyen", "Faible", "ouverture", "conscienciosite",
                 "A1", "A9", "A10", "Réaliste"):
        assert word not in msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_generation.py -k micro_message -v`
Expected: FAIL with `AttributeError: module 'app.services.voyage.generation' has no attribute '_micro_user_message'`

- [ ] **Step 3: Write minimal implementation**

Append to `backend/app/services/voyage/generation.py`:

```python
# ── message builders ─────────────────────────────────────────────────────────
# Pure functions, called before db.session.remove(). The reduction discipline is
# models/profile.prompt_context()'s: the model receives only what it is allowed
# to say, so a rule can be enforced by a test rather than hoped for in prose.


def _micro_user_message(synthesis: dict, prenom: str | None) -> str:
    """Session 0 in plain words: the three strongest pulls and the hesitations.

    No number, no axis id, no framework name. `plain` and `tension` come
    straight from the bank's AXES table, which is where that wording has its
    single home (contracts § A.2).
    """
    s0 = (synthesis or {}).get("s0") or {}
    blocks: list[list[str]] = []

    if str(prenom or "").strip():
        blocks.append([HEADER_PROFIL, f"Prénom : {str(prenom).strip()}"])

    session_0: list[str] = []
    attractions = [a.get("plain") for a in s0.get("top3") or [] if a.get("plain")]
    if attractions:
        session_0.append(f"Ce qui l'attire le plus : {', '.join(attractions)}")
    tensions = [t.get("tension") for t in s0.get("tensions") or [] if t.get("tension")]
    if tensions:
        session_0.append(f"Autant coché des deux côtés sur : {' · '.join(tensions)}")
    if session_0:
        blocks.append([HEADER_SESSION_0] + session_0)

    return "\n\n".join("\n".join(block) for block in blocks)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_generation.py -v`
Expected: PASS — 18 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/services/voyage/generation.py backend/tests/test_voyage_generation.py
git commit -m "feat(voyage): reduce session 0 to the words the model may reuse

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

## Task 6: `_portrait_user_message()` — the person's own words plus the sheet

**Files:**
- Modify: `backend/app/services/voyage/generation.py` (append)
- Test: `backend/tests/test_voyage_generation.py` (append)

**Interfaces:**
- Consumes: `bank.items(n)` → scene dicts with `title`; `bank.STYLE_PLAIN` (contracts § A.1); `scoring.chosen_option(responses, item_id) -> dict | None` with the option's `plain` (contracts § B.3).
- Produces: `_portrait_user_message(synthesis: dict, responses: dict, profile_fields: dict) -> str`, plus the private helpers `_profile_lines`, `_choice_lines`, `_synthesis_lines`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_generation.py`:

```python
# ── _portrait_user_message ───────────────────────────────────────────────────

def test_the_three_headers_appear_in_order():
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    assert (msg.index(gen.HEADER_PROFIL)
            < msg.index(gen.HEADER_CHOISI)
            < msg.index(gen.HEADER_SYNTHESE))


def test_the_profile_block_carries_the_four_fields_it_is_given():
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    assert "Prénom : Marie" in msg
    assert "Tranche d'âge : 25_34" in msg
    assert "Situation actuelle : en_recherche" in msg
    assert "Projet : reprendre un travail au contact des gens" in msg


def test_an_empty_profile_field_never_leaves_a_naked_label():
    msg = gen._portrait_user_message(
        SYNTHESIS, _full_responses(),
        {"prenom": "Marie", "tranche_age": None, "situation": "", "projet": None})
    assert "Prénom : Marie" in msg
    assert "Tranche d'âge" not in msg
    assert "Situation actuelle" not in msg
    assert "Projet" not in msg


def test_the_choices_block_has_one_line_per_scene():
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    lines = [ln for ln in _block(msg, gen.HEADER_CHOISI).splitlines() if ln.strip()]
    scenes = [i for n in ("1", "2", "3", "4", "5") for i in bank.item_ids(n)]
    assert len(scenes) == 33
    assert len(lines) == 33


def test_each_choice_line_is_the_scene_title_then_the_persons_own_words():
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    scene = bank.item("S1-1")
    assert f"{scene['title']} : {scene['options'][0]['plain']}" in msg


def test_session_zero_contributes_nothing_to_the_choices_block():
    """S0 reaches the model through the synthesis block only — its twenty
    statements are checkboxes, not scenes."""
    block = _block(
        gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS),
        gen.HEADER_CHOISI)
    for item_id in bank.item_ids("0"):
        assert bank.item(item_id)["text"] not in block


def test_the_synthese_block_is_the_twelve_pinned_lines():
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    lines = [ln for ln in _block(msg, gen.HEADER_SYNTHESE).splitlines() if ln.strip()]
    assert lines == [
        "Univers dominants : Réaliste, Conventionnel, Entreprenant",
        "Ce qui l'attire le plus dans dix ans : le lien avec les gens, un impact "
        "visible, le terrain et l'action",
        "Autant coché des deux côtés sur : discrétion vs reconnaissance · solo vs "
        "collectif · impact local vs impact global · sécurité vs risque · méthode vs "
        "expression libre · impact différé vs impact immédiat · bureau vs terrain · "
        "expertise vs transmission (à pondérer ×1,5)",
        "Besoin dominant : autonomie",
        "Façon de fonctionner : s'appuie sur les autres pour décider",
        "Cadre : bureau fermé et calme · cycles courts · petite équipe soudée · "
        "confiance et droit à l'essai",
        "Ce qui l'épuise : les interruptions constantes",
        "Rapport au risque : Calculé",
        "Ce qui la met en colère : l'injustice",
        "La trace voulue : une trace dans les gens",
        "Prête à sacrifier : le temps",
        "Se sent vivant(e) quand : elle crée",
    ]


def test_an_incomplete_voyage_only_emits_the_lines_it_can_fill():
    synthesis = copy.deepcopy(SYNTHESIS)
    for key in ("riasec", "s2", "s3", "s4", "s5"):
        synthesis[key] = None
    msg = gen._portrait_user_message(synthesis, _s0_only_responses(), PROFILE_FIELDS)
    block = _block(msg, gen.HEADER_SYNTHESE)
    assert "Univers dominants" not in block
    assert "Ce qui l'attire le plus dans dix ans" in block
    assert gen.HEADER_CHOISI not in msg      # no scene answered yet


def test_the_portrait_message_carries_no_score_and_no_framework_word():
    """The profile block is exempt from the digit rule: `25_34` is the age
    bracket the Profil de base already holds, and the contracts doc pins that
    literal shape. Everything derived from the scoring must be digit-free apart
    from the manual's own x1,5 weighting note."""
    msg = gen._portrait_user_message(SYNTHESIS, _full_responses(), PROFILE_FIELDS)
    synth = _block(msg, gen.HEADER_SYNTHESE).replace(gen.WEIGHT_NOTE, "")
    assert not re.search(r"\d", synth)
    assert not re.search(r"\d", _block(msg, gen.HEADER_CHOISI))
    assert gen.leak_check({"message": msg}) == []
    for word in ("Élevé", "Moyen", "ouverture", "conscienciosite",
                 "A1", "A9", "A10", "consultatif", "bienveillance"):
        assert word not in msg


def test_a_real_synthesis_feeds_both_builders_without_a_gap(app):
    """The literal fixture above pins the wording; this one proves the shape
    scoring.synthesize() actually produces is the shape the builders read."""
    responses = _full_responses()
    synthesis = scoring.synthesize(responses)
    micro = gen._micro_user_message(synthesis, "Marie")
    portrait = gen._portrait_user_message(synthesis, responses, PROFILE_FIELDS)
    assert gen.HEADER_SESSION_0 in micro
    assert gen.HEADER_CHOISI in portrait
    assert gen.HEADER_SYNTHESE in portrait
    assert gen.leak_check({"a": micro, "b": portrait}) == []
    assert not re.search(r"\d", _block(portrait, gen.HEADER_CHOISI))
    assert not re.search(
        r"\d", _block(portrait, gen.HEADER_SYNTHESE).replace(gen.WEIGHT_NOTE, ""))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_generation.py -k portrait_message -v`
Expected: FAIL with `AttributeError: module 'app.services.voyage.generation' has no attribute '_portrait_user_message'`

- [ ] **Step 3: Write minimal implementation**

Append to `backend/app/services/voyage/generation.py`:

```python
_PROFILE_LABELS = (
    ("prenom", "Prénom"),
    ("tranche_age", "Tranche d'âge"),
    ("situation", "Situation actuelle"),
    ("projet", "Projet"),
)


def _profile_lines(profile_fields: dict) -> list[str]:
    """The four Profil de base fields, each omitted when empty.

    « une information, une seule fois » (Parcours doc §1): the portrait reuses
    the prénom, the age bracket and the situation the profile already holds, so
    the voyage never asks for them again.
    """
    lines = []
    for key, label in _PROFILE_LABELS:
        value = str((profile_fields or {}).get(key) or "").strip()
        if value:
            lines.append(f"{label} : {value}")
    return lines


def _choice_lines(responses: dict) -> list[str]:
    """One line per scene: the scene's own title, then the person's own words.

    `plain` is the short plain-French descriptor authored beside each option;
    the scoring tag on that option never leaves the server (spec decision 6).
    Session 0 contributes nothing here — it reaches the model through the
    synthesis block only.
    """
    lines = []
    for n in ("1", "2", "3", "4", "5"):
        for item in bank.items(n):
            chosen = scoring.chosen_option(responses, item["id"]) or {}
            plain = chosen.get("plain")
            if plain:
                lines.append(f"{item['title']} : {plain}")
    return lines


def _synthesis_lines(synthesis: dict) -> list[str]:
    """The counselor's page-18 sheet, reduced to plain French.

    Nothing numeric survives: no axis score, no RIASEC point, no level word. The
    universe names (Réaliste, Investigateur…) and the three need words
    (autonomie, appartenance, competence) are the deliberate exceptions — they
    are ordinary French and the restitution guide says them out loud.

    The counselor-only fields (s4["vendredi"], s5["rapport_echec"],
    s5["rapport_flou"], the Big Five levels, Schwartz) are not here on purpose:
    they belong to the synthesis sheet, not to the portrait's raw material.
    """
    synthesis = synthesis or {}
    s0 = synthesis.get("s0") or {}
    riasec = synthesis.get("riasec") or {}
    s2 = synthesis.get("s2") or {}
    s3 = synthesis.get("s3") or {}
    s4 = synthesis.get("s4") or {}
    s5 = synthesis.get("s5") or {}

    lines = []

    univers = [t.get("univers") for t in riasec.get("top3") or [] if t.get("univers")]
    if univers:
        lines.append(f"Univers dominants : {', '.join(univers)}")

    attractions = [a.get("plain") for a in s0.get("top3") or [] if a.get("plain")]
    if attractions:
        lines.append(f"Ce qui l'attire le plus dans dix ans : {', '.join(attractions)}")

    tensions = [t.get("tension") for t in s0.get("tensions") or [] if t.get("tension")]
    if tensions:
        lines.append(
            f"Autant coché des deux côtés sur : {' · '.join(tensions)}{WEIGHT_NOTE}")

    besoins = [b for b in s2.get("sdt_dominant") or [] if b]
    if besoins:
        lines.append(f"Besoin dominant : {', '.join(besoins)}")

    # The tag itself never travels — bank.STYLE_PLAIN is what the model reads.
    styles = [bank.STYLE_PLAIN[s] for s in s3.get("style_dominant") or []
              if s in bank.STYLE_PLAIN]
    if styles:
        lines.append(f"Façon de fonctionner : {' · '.join(styles)}")

    cadre = [s4.get(k) for k in ("espace", "rythme", "equipe", "manager") if s4.get(k)]
    if cadre:
        lines.append(f"Cadre : {' · '.join(cadre)}")
    if s4.get("irritant"):
        lines.append(f"Ce qui l'épuise : {s4['irritant']}")

    for key, label in (("risque", "Rapport au risque"),
                       ("valeur_centrale", "Ce qui la met en colère"),
                       ("trace", "La trace voulue"),
                       ("sacrifice", "Prête à sacrifier"),
                       ("vivant", "Se sent vivant(e) quand")):
        if s5.get(key):
            lines.append(f"{label} : {s5[key]}")

    return lines


def _portrait_user_message(synthesis: dict, responses: dict, profile_fields: dict) -> str:
    """Everything the portrait call is allowed to know, in three blocks.

    A block whose lines are all empty is omitted with its header.
    """
    blocks = []
    for header, lines in ((HEADER_PROFIL, _profile_lines(profile_fields)),
                          (HEADER_CHOISI, _choice_lines(responses)),
                          (HEADER_SYNTHESE, _synthesis_lines(synthesis))):
        if lines:
            blocks.append([header] + lines)
    return "\n\n".join("\n".join(block) for block in blocks)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_generation.py -v`
Expected: PASS — 28 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/services/voyage/generation.py backend/tests/test_voyage_generation.py
git commit -m "feat(voyage): build the portrait message from plain words only

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

## Task 7: `start_micro()` / `_run_micro()`

**Files:**
- Modify: `backend/app/services/voyage/generation.py` (append)
- Test: `backend/tests/test_voyage_generation.py` (append)

**Interfaces:**
- Consumes: `Voyage.responses`, `Voyage.synthesis()`, `Voyage.micro` setter, `Voyage.micro_phrase`, `Voyage.micro_status`, `Voyage.tokens_in/out` (contracts § C); `Profile.prenom`; `tiers.model_for(tiers.FREE)`; `anthropic_service._get_client` (`backend/app/services/anthropic_service.py:17-18`).
- Produces: `start_micro(voyage_id: str, app) -> None`, `_run_micro(voyage_id: str, app) -> None`, `_stream_text(...) -> tuple[str, int, int]`, `_one_sentence(raw) -> str`, `_fail_micro(voyage, message) -> None`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_generation.py`:

```python
# ── mocked Anthropic client ──────────────────────────────────────────────────

def _stream_of(text: str, usage=(300, 900)):
    """One `client.messages.stream(...)` result: a context manager exposing
    `.text_stream` and `.get_final_message()`. Same shape as the stand-in in
    tests/test_stream_progress.py."""
    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.text_stream = iter([text])
    stream.get_final_message.return_value = MagicMock(
        usage=MagicMock(input_tokens=usage[0], output_tokens=usage[1]))
    return stream


def _client(*answers, usage=(300, 900)):
    """An Anthropic stand-in. A str answer is streamed; an Exception is raised."""
    client = MagicMock()
    client.messages.stream.side_effect = [
        a if isinstance(a, BaseException) else _stream_of(a, usage) for a in answers
    ]
    return client


def _bad_request():
    return anthropic.BadRequestError(
        "output_config is not supported",
        response=httpx.Response(
            400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")),
        body=None,
    )


def _voyage(responses, prenom="Marie", **columns):
    """A user with a profile and one voyage carrying `responses`."""
    user = User(email=f"v{uuid4().hex[:8]}@test.com", password_hash="x",
                role="candidate", plan="free")
    db.session.add(user)
    db.session.commit()
    db.session.add(Profile(user_id=user.id, prenom=prenom,
                           tranche_age="25_34", situation="en_recherche",
                           projet="reprendre un travail au contact des gens"))
    row = Voyage(user_id=user.id, consent_at=datetime.utcnow(), age_attested=True,
                 **columns)
    row.responses = responses
    db.session.add(row)
    db.session.commit()
    return row


def _seed(slot, text="Consigne système."):
    db.session.add(PromptVersion(version_label=f"v0-{slot}", system_prompt_text=text,
                                 is_active=True, path=slot))
    db.session.commit()


def _reload(voyage_id):
    """The row as it stands after the runner committed from its own context."""
    db.session.expire_all()
    return db.session.get(Voyage, voyage_id)


# ── _run_micro ───────────────────────────────────────────────────────────────

def test_the_micro_run_writes_the_phrase_and_flips_the_status(app):
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    _seed("voyage_micro", "Tu écris une phrase.")
    voyage_id = voyage.id

    client = _client("  « Tu cherches des endroits où ce que tu fabriques compte. »  ",
                     usage=(120, 40))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "success"
    assert row.micro_phrase == "Tu cherches des endroits où ce que tu fabriques compte."
    assert row.micro["tokens_in"] == 120
    assert row.micro["tokens_out"] == 40
    assert row.micro["error"] is None
    assert row.tokens_in == 120
    assert row.tokens_out == 40


def test_the_micro_run_records_the_prompt_version_it_used(app):
    """B2G traceability: every generated text names the prompt that wrote it."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine")
    _seed("voyage_micro")
    voyage_id = voyage.id
    expected = PromptVersion.query.filter_by(path="voyage_micro").first().id

    with patch.object(gen, "_get_client", return_value=_client("Une phrase.")):
        gen._run_micro(voyage_id, app)

    assert _reload(voyage_id).micro["prompt_version_id"] == expected


def test_the_micro_run_uses_the_free_tier_model_and_a_two_hundred_token_budget(app):
    voyage = _voyage(_s0_only_responses(), status="s0_termine")
    _seed("voyage_micro", "Consigne micro.")
    voyage_id = voyage.id

    client = _client("Une phrase.")
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    kwargs = client.messages.stream.call_args.kwargs
    assert kwargs["model"] == tiers.model_for(tiers.FREE)[0]
    assert kwargs["max_tokens"] == gen.MICRO_MAX_TOKENS
    assert kwargs["system"] == "Consigne micro."
    # Plain text, no schema: the phrase is one sentence, not an object.
    assert "extra_body" not in kwargs
    assert kwargs["messages"] == [
        {"role": "user", "content": gen._micro_user_message(
            scoring.synthesize(_s0_only_responses()), "Marie")}]


def test_a_missing_slot_prompt_puts_the_micro_in_error(app):
    """Without a seeded prompt the feature errors on first use — which is the
    whole reason both seed scripts land ACTIVE."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine", micro_status="generating")
    voyage_id = voyage.id

    gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert row.micro["error"] == "Aucun prompt actif pour le slot voyage_micro."
    assert row.micro_phrase is None


def test_an_api_failure_is_recorded_on_the_row_not_raised(app):
    voyage = _voyage(_s0_only_responses(), status="s0_termine")
    _seed("voyage_micro")
    voyage_id = voyage.id

    client = MagicMock()
    client.messages.stream.side_effect = RuntimeError("connection reset by peer")
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    row = _reload(voyage_id)
    assert row.micro_status == "error"
    assert "connection reset by peer" in row.micro["error"]


def test_the_db_connection_is_released_before_the_stream(app):
    """Holding a pooled connection across the call is what leaves rows stuck
    'generating' — see the comment in anthropic_service._run_analysis."""
    voyage = _voyage(_s0_only_responses(), status="s0_termine")
    _seed("voyage_micro")
    voyage_id = voyage.id

    seen = {}

    def streaming(**_kwargs):
        # db.session.remove() empties the scoped registry; it stays empty until
        # something asks for a session again. That is the observable fact.
        seen["registry_empty"] = not db.session.registry.has()
        return _stream_of("Une phrase.")

    client = MagicMock()
    client.messages.stream.side_effect = streaming
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_micro(voyage_id, app)

    assert seen["registry_empty"] is True
    assert _reload(voyage_id).micro_status == "success"


def test_a_deleted_voyage_is_a_silent_no_op(app):
    gen._run_micro("does-not-exist", app)   # must not raise


def test_start_micro_spawns_a_daemon_thread_and_returns(app):
    with patch.object(gen.threading, "Thread") as Thread:
        gen.start_micro("some-id", app)
    Thread.assert_called_once_with(target=gen._run_micro, args=("some-id", app),
                                   daemon=True)
    Thread.return_value.start.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_generation.py -k micro_run -v`
Expected: FAIL with `AttributeError: module 'app.services.voyage.generation' has no attribute '_run_micro'`

- [ ] **Step 3: Write minimal implementation**

Append to `backend/app/services/voyage/generation.py`:

```python
# ── the streamed call ────────────────────────────────────────────────────────


def _stream_text(model: str, system_prompt: str, messages: list,
                 max_tokens: int, schema: dict | None) -> tuple[str, int, int]:
    """One streamed call. Returns (text, tokens_in, tokens_out).

    Streaming keeps the upstream HTTP request alive for long generations; no SSE
    reaches the client, which polls GET /api/voyage instead. Structured output
    goes through extra_body so it works on any SDK version, and a
    BadRequestError degrades to a plain call — the same fallback
    anthropic_service._run_analysis uses when the API surface refuses
    output_config.
    """
    client = _get_client()
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=list(messages),
    )
    if schema is not None:
        kwargs["extra_body"] = {
            "output_config": {"format": {"type": "json_schema", "schema": schema}}
        }

    def _run(call_kwargs):
        acc = ""
        with client.messages.stream(**call_kwargs) as stream:
            for chunk in stream.text_stream:
                acc += chunk
            final = stream.get_final_message()
        return acc, final.usage.input_tokens, final.usage.output_tokens

    try:
        return _run(kwargs)
    except anthropic.BadRequestError:
        kwargs.pop("extra_body", None)
        return _run(kwargs)


def _one_sentence(raw: str) -> str:
    """Normalise the model's answer to a single line.

    The prompt asks for one sentence and nothing else; this only removes the
    wrapping it sometimes adds anyway (quotes, a leading dash, a trailing
    newline). It never truncates: a phrase that came back too long is the PM's
    signal to edit the prompt, not something to silently cut.
    """
    text = " ".join(str(raw or "").split())
    return text.strip("«»\"“” ").lstrip("-–—").strip()


def _profile_fields(user_id: str) -> dict:
    """The four Profil de base fields, lifted off the ORM before the stream."""
    profile = Profile.query.filter_by(user_id=user_id).first()
    return {
        "prenom": profile.prenom if profile else None,
        "tranche_age": profile.tranche_age if profile else None,
        "situation": profile.situation if profile else None,
        "projet": profile.projet if profile else None,
    }


# ── the S0 phrase ────────────────────────────────────────────────────────────


def _fail_micro(voyage: Voyage, message: str) -> None:
    """Record the failure inside the ciphertext; only the status is plaintext."""
    voyage.micro = {**(voyage.micro or {}), "error": str(message)[:ERROR_MAX_CHARS]}
    voyage.micro_status = "error"
    db.session.commit()


def _run_micro(voyage_id: str, app) -> None:
    """Write the session-0 phrase onto the voyage row.

    Runs inside a background daemon thread spawned by
    POST /api/voyage/sessions/0/complete. No progress reporter: the hub polls
    GET /api/voyage every 2 s while micro_status == "generating", and the free
    model answers in a few seconds.
    """
    with app.app_context():
        voyage = db.session.get(Voyage, voyage_id)
        if not voyage:
            return

        prompt = PromptVersion.query.filter_by(is_active=True, path=MICRO_SLOT).first()
        if not prompt:
            _fail_micro(voyage, f"Aucun prompt actif pour le slot {MICRO_SLOT}.")
            return

        # Everything the call needs, captured as plain values BEFORE the
        # connection is released.
        system_prompt = prompt.system_prompt_text
        prompt_version_id = prompt.id
        user_message = _micro_user_message(
            voyage.synthesis(), _profile_fields(voyage.user_id).get("prenom"))
        model, _ = tiers.model_for(tiers.FREE)

        voyage.micro_status = "generating"
        db.session.commit()

        # Release the pooled connection for the duration of the call: holding
        # one across the stream lets the DB drop it as idle, and the final
        # commit then fails with "Lost connection" on a row stuck 'generating'.
        db.session.remove()

        try:
            raw, tokens_in, tokens_out = _stream_text(
                model, system_prompt,
                [{"role": "user", "content": user_message}],
                MICRO_MAX_TOKENS, None)
        except Exception as exc:            # noqa: BLE001 — recorded on the row
            voyage = db.session.get(Voyage, voyage_id)
            if voyage is not None:
                _fail_micro(voyage, str(exc))
            return

        # Fresh, pre-pinged connection to write the result.
        voyage = db.session.get(Voyage, voyage_id)
        if voyage is None:
            return
        voyage.micro = {
            "phrase": _one_sentence(raw),
            "prompt_version_id": prompt_version_id,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "error": None,
        }
        voyage.micro_status = "success"
        voyage.tokens_in = (voyage.tokens_in or 0) + (tokens_in or 0)
        voyage.tokens_out = (voyage.tokens_out or 0) + (tokens_out or 0)
        db.session.commit()


def start_micro(voyage_id: str, app) -> None:
    """Spawn a daemon thread that writes the session-0 phrase. Returns at once."""
    threading.Thread(target=_run_micro, args=(voyage_id, app), daemon=True).start()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_generation.py -v`
Expected: PASS — 36 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/services/voyage/generation.py backend/tests/test_voyage_generation.py
git commit -m "feat(voyage): write the session 0 phrase in a background thread

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

## Task 8: `start_portrait()` / `_run_portrait()` with the leak retry

**Files:**
- Modify: `backend/app/services/voyage/generation.py` (append)
- Test: `backend/tests/test_voyage_generation.py` (append)

**Interfaces:**
- Consumes: `Voyage.portrait` setter / `portrait_status` / `portrait_sections` (contracts § C.3-C.4); `tiers.model_for(tiers.PAID)`; `anthropic_service._extract_json_candidate` (`backend/app/services/anthropic_service.py:242-254`); `json_repair.repair_json`.
- Produces: `start_portrait(voyage_id: str, app) -> None`, `_run_portrait(voyage_id: str, app) -> None`, `_parse_sections(raw) -> dict[str, str]`, `_leak_retry_message(leaks) -> str`, `_fail_portrait(voyage, message) -> None`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_generation.py`:

```python
# ── _run_portrait ────────────────────────────────────────────────────────────

def _portrait_json(sections):
    return json.dumps(sections, ensure_ascii=False)


def test_the_portrait_run_stores_six_sections_a_snapshot_and_a_draft_status(app):
    voyage = _voyage(_full_responses(), status="termine", portrait_status="generating")
    _seed("voyage_portrait", "Tu écris six sections.")
    voyage_id = voyage.id

    with patch.object(gen, "_get_client",
                      return_value=_client(_portrait_json(CLEAN_SECTIONS))):
        gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "draft"
    assert row.portrait_sections == CLEAN_SECTIONS
    assert row.portrait["flags"] == []
    assert row.portrait["edited"] is False
    assert row.portrait["error"] is None
    assert row.portrait["snapshot"]["scoring_version"] == bank.SCORING_VERSION
    assert row.portrait["tokens_in"] == 300
    assert row.portrait["tokens_out"] == 900
    assert row.tokens_in == 300


def test_the_portrait_call_carries_the_schema_the_paid_model_and_the_budget(app):
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    client = _client(_portrait_json(CLEAN_SECTIONS))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    kwargs = client.messages.stream.call_args.kwargs
    assert kwargs["model"] == tiers.model_for(tiers.PAID)[0]
    assert kwargs["max_tokens"] == gen.PORTRAIT_MAX_TOKENS
    fmt = kwargs["extra_body"]["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert list(fmt["schema"]["properties"]) == list(gen.PORTRAIT_KEYS)


def test_a_refused_output_config_degrades_to_a_plain_call(app):
    """Same fallback as _run_analysis: an old API surface must not cost the
    portrait, only its schema."""
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    client = _client(_bad_request(), "```json\n" + _portrait_json(CLEAN_SECTIONS) + "\n```")
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    first, second = client.messages.stream.call_args_list
    assert "extra_body" in first.kwargs
    assert "extra_body" not in second.kwargs
    row = _reload(voyage_id)
    assert row.portrait_status == "draft"
    assert row.portrait_sections == CLEAN_SECTIONS


def test_a_leaking_draft_is_regenerated_once_with_the_words_quoted(app):
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    client = _client(_portrait_json(LEAKY_SECTIONS), _portrait_json(CLEAN_SECTIONS))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    assert client.messages.stream.call_count == 2
    retry = client.messages.stream.call_args_list[1].kwargs["messages"]
    assert [m["role"] for m in retry] == ["user", "assistant", "user"]
    for word in ("névrotisme", "riasec", "score"):
        assert word in retry[-1]["content"]

    row = _reload(voyage_id)
    assert row.portrait_status == "draft"
    assert row.portrait["flags"] == []
    assert row.portrait_sections["qui_tu_es"] == CLEAN_SECTIONS["qui_tu_es"]
    # Both calls are billed to the row.
    assert row.portrait["tokens_in"] == 600
    assert row.portrait["tokens_out"] == 1800


def test_a_draft_that_still_leaks_is_kept_and_flagged(app):
    """Flag-and-keep, not fail: a counselor validates before the person reads
    it, and a flagged draft is more useful than none."""
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    client = _client(_portrait_json(LEAKY_SECTIONS), _portrait_json(LEAKY_SECTIONS))
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    assert client.messages.stream.call_count == 2      # one retry, never two
    row = _reload(voyage_id)
    assert row.portrait_status == "draft"
    assert row.portrait["flags"] == [gen.FLAG_VOCABULAIRE]
    assert row.portrait_sections["qui_tu_es"] == LEAKY_SECTIONS["qui_tu_es"]


def test_a_missing_slot_prompt_puts_the_portrait_in_error(app):
    voyage = _voyage(_full_responses(), status="termine", portrait_status="generating")
    voyage_id = voyage.id

    gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "error"
    assert row.portrait["error"] == "Aucun prompt actif pour le slot voyage_portrait."
    assert row.portrait_sections == {}


def test_an_unreadable_answer_puts_the_portrait_in_error(app):
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    with patch.object(gen, "_get_client",
                      return_value=_client("Je ne peux pas répondre à cette demande.")):
        gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "error"
    assert row.portrait["error"]


def test_an_api_failure_puts_the_portrait_in_error(app):
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    client = MagicMock()
    client.messages.stream.side_effect = RuntimeError("upstream timeout")
    with patch.object(gen, "_get_client", return_value=client):
        gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "error"
    assert "upstream timeout" in row.portrait["error"]


def test_a_missing_key_comes_back_as_an_empty_section_not_a_crash(app):
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_portrait")
    voyage_id = voyage.id
    partial = {k: v for k, v in CLEAN_SECTIONS.items() if k != "pas_encore"}

    with patch.object(gen, "_get_client", return_value=_client(_portrait_json(partial))):
        gen._run_portrait(voyage_id, app)

    row = _reload(voyage_id)
    assert row.portrait_status == "draft"
    assert set(row.portrait["sections"]) == set(gen.PORTRAIT_KEYS)
    assert row.portrait["sections"]["pas_encore"] == ""


def test_the_generated_texts_are_ciphertext_at_rest(app):
    """A psychometric portrait is more sensitive than bloc 5. The plaintext
    columns hold statuses and timestamps, nothing else."""
    voyage = _voyage(_full_responses(), status="termine")
    _seed("voyage_micro")
    _seed("voyage_portrait")
    voyage_id = voyage.id

    with patch.object(gen, "_get_client", return_value=_client("Une phrase à toi.")):
        gen._run_micro(voyage_id, app)
    with patch.object(gen, "_get_client",
                      return_value=_client(_portrait_json(CLEAN_SECTIONS))):
        gen._run_portrait(voyage_id, app)

    db.session.expire_all()
    raw = db.session.execute(
        db.text("SELECT micro_encrypted, portrait_encrypted FROM voyages WHERE id = :i"),
        {"i": voyage_id}).first()
    blob = f"{raw[0]}{raw[1]}"
    assert "Une phrase à toi." not in blob
    assert CLEAN_SECTIONS["accroche"] not in blob
    assert "accroche" not in blob


def test_start_portrait_spawns_a_daemon_thread_and_returns(app):
    with patch.object(gen.threading, "Thread") as Thread:
        gen.start_portrait("some-id", app)
    Thread.assert_called_once_with(target=gen._run_portrait, args=("some-id", app),
                                   daemon=True)
    Thread.return_value.start.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_generation.py -k portrait_run -v`
Expected: FAIL with `AttributeError: module 'app.services.voyage.generation' has no attribute '_run_portrait'`

- [ ] **Step 3: Write minimal implementation**

Append to `backend/app/services/voyage/generation.py`:

```python
# ── the portrait ─────────────────────────────────────────────────────────────


def _parse_sections(raw: str) -> dict:
    """The six sections out of the model's answer.

    Structured output makes this a plain JSON object; the degraded path
    (extra_body refused) can return a fenced block or prose, so the same
    extract-then-repair ladder the analysis parser uses runs here too. Missing
    keys come back as empty strings rather than absent, so the counselor editor
    always has its six boxes.
    """
    candidate = _extract_json_candidate(str(raw or ""))
    parsed = None
    for text in (candidate, repair_json(candidate)):
        try:
            value = json.loads(text)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if isinstance(value, dict):
            parsed = value
            break
    parsed = parsed or {}
    return {key: str(parsed.get(key) or "").strip() for key in PORTRAIT_KEYS}


def _leak_retry_message(leaks: list) -> str:
    """The corrective turn, in French — the whole exchange is in French."""
    return (
        "Ce texte contient des mots interdits : " + ", ".join(leaks) + ". "
        "Réécris le portrait en entier sans ces mots et sans aucun autre terme "
        "technique de psychologie ou de ressources humaines. Garde les six mêmes "
        "sections, le même fond et la même longueur. Réponds uniquement avec le "
        "JSON des six sections."
    )


def _fail_portrait(voyage: Voyage, message: str) -> None:
    """Record the failure inside the ciphertext; only the status is plaintext."""
    voyage.portrait = {**(voyage.portrait or {}), "error": str(message)[:ERROR_MAX_CHARS]}
    voyage.portrait_status = "error"
    db.session.commit()


def _run_portrait(voyage_id: str, app) -> None:
    """Draft the six-section portrait onto the voyage row.

    Runs inside a background daemon thread spawned by
    POST /api/voyage/sessions/5/complete, or by the counselor's regenerate.
    The result is a DRAFT: a counselor edits and validates it before the person
    can read a word of it.
    """
    with app.app_context():
        voyage = db.session.get(Voyage, voyage_id)
        if not voyage:
            return

        prompt = PromptVersion.query.filter_by(is_active=True, path=PORTRAIT_SLOT).first()
        if not prompt:
            _fail_portrait(voyage, f"Aucun prompt actif pour le slot {PORTRAIT_SLOT}.")
            return

        # Plain values only, captured BEFORE the connection is released.
        system_prompt = prompt.system_prompt_text
        prompt_version_id = prompt.id
        synthesis = voyage.synthesis()
        user_message = _portrait_user_message(
            synthesis, voyage.responses, _profile_fields(voyage.user_id))
        schema = _portrait_schema()
        model, _ = tiers.model_for(tiers.PAID)

        voyage.portrait_status = "generating"
        db.session.commit()

        db.session.remove()

        messages = [{"role": "user", "content": user_message}]
        tokens_in = tokens_out = 0
        flags: list[str] = []
        try:
            raw, t_in, t_out = _stream_text(model, system_prompt, messages,
                                            PORTRAIT_MAX_TOKENS, schema)
            tokens_in += t_in or 0
            tokens_out += t_out or 0
            sections = _parse_sections(raw)

            leaks = leak_check(sections)
            if leaks:
                # One corrective turn quoting the offending words. Whatever
                # comes back is what we keep: still leaking means flagged, not
                # discarded — the counselor sees a banner and fixes the wording
                # in the editor.
                retry = messages + [
                    {"role": "assistant",
                     "content": json.dumps(sections, ensure_ascii=False)},
                    {"role": "user", "content": _leak_retry_message(leaks)},
                ]
                raw, t_in, t_out = _stream_text(model, system_prompt, retry,
                                                PORTRAIT_MAX_TOKENS, schema)
                tokens_in += t_in or 0
                tokens_out += t_out or 0
                sections = _parse_sections(raw)
                if leak_check(sections):
                    flags = [FLAG_VOCABULAIRE]
        except Exception as exc:            # noqa: BLE001 — recorded on the row
            voyage = db.session.get(Voyage, voyage_id)
            if voyage is not None:
                _fail_portrait(voyage, str(exc))
            return

        voyage = db.session.get(Voyage, voyage_id)
        if voyage is None:
            return
        if not any(sections.values()):
            _fail_portrait(voyage, "Le modèle n'a renvoyé aucune section lisible.")
            return

        voyage.portrait = {
            "sections": sections,
            # The synthesis the portrait was written from, kept so a later
            # scoring correction can never make an existing portrait a lie.
            "snapshot": synthesis,
            "flags": flags,
            "edited": False,
            "prompt_version_id": prompt_version_id,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "error": None,
        }
        voyage.portrait_status = "draft"
        voyage.tokens_in = (voyage.tokens_in or 0) + tokens_in
        voyage.tokens_out = (voyage.tokens_out or 0) + tokens_out
        db.session.commit()


def start_portrait(voyage_id: str, app) -> None:
    """Spawn a daemon thread that drafts the portrait. Returns at once."""
    threading.Thread(target=_run_portrait, args=(voyage_id, app), daemon=True).start()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_generation.py -v`
Expected: PASS — 48 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/services/voyage/generation.py backend/tests/test_voyage_generation.py
git commit -m "feat(voyage): draft the portrait, retry once on a vocabulary leak

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

## Task 9: Seed the session-0 phrase prompt

**Files:**
- Create: `backend/seed_prompt_v10_voyage_micro.py`
- Modify: `backend/tests/test_seed_scripts.py:11,14-18,20,30-33`
- Modify: `backend/tests/test_prompt_section_keys.py:23,33-47`

**Interfaces:**
- Consumes: `prompt_slots.is_valid`, `prompt_slots.is_voyage`, `prompt_slots.VOYAGE_SLOTS` (Task 1); `PromptVersion` (`backend/app/models/prompt_version.py`).
- Produces: a `PromptVersion` row `version_label="v1.0-VM"`, `path="voyage_micro"`, `is_active=True`.

- [ ] **Step 1: Write the failing test**

Replace `backend/tests/test_seed_scripts.py` in full:

```python
"""Guards the slot id the seed scripts write into PromptVersion.path.

CDC v1.2 replaced the A/B path codes with parcours ids, and the analysis lookup
filters on that column directly. A stale literal here seeds a prompt no analysis
can ever find — the run fails instantly with "Aucun prompt actif pour le chemin
1", which is what happened on the VPS after a fresh seed.

The voyage widened the column from a parcours id to a slot id, so the literal
regex reads a whole word now, not a single character.
"""
import json
import re
from pathlib import Path

from app.services import prompt_slots
from app.services.voyage import generation

BACKEND = Path(__file__).resolve().parents[1]

# seed script → the slot its prompt belongs to
SEEDS = {
    "seed_prompt_v18.py": "1",                      # ex-path A, « J'ai une cible »
    "seed_prompt_v11_p3.py": "3",                   # ex-path B, « Je pars de zéro »
    "seed_prompt_v10_p2.py": "2",                   # authored after the migration
    "seed_prompt_v10_voyage_micro.py": "voyage_micro",
}

_LITERAL = re.compile(r"""(?:path\s*=|^PATH\s*=)\s*["'](\w+)["']""", re.MULTILINE)
_JSON_BLOCK = re.compile(r"```json\s*\n(\{.*?\n\})\s*\n```", re.DOTALL)


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


def test_there_is_a_seed_script_for_every_voyage_slot():
    """Without an active prompt the voyage errors on first use: session 0 ends
    with micro_status='error' and nothing to show for it."""
    covered = {slot for slot in SEEDS.values() if prompt_slots.is_voyage(slot)}
    assert covered == set(prompt_slots.VOYAGE_SLOTS)


def test_the_voyage_seeds_land_active():
    for name, slot in SEEDS.items():
        if not prompt_slots.is_voyage(slot):
            continue
        source = (BACKEND / name).read_text(encoding="utf-8")
        assert "is_active=True" in source, f"{name}: must seed the prompt ACTIVE"


def test_the_voyage_seeds_are_idempotent():
    """Re-running a seed on the VPS must not duplicate the version."""
    for name, slot in SEEDS.items():
        if not prompt_slots.is_voyage(slot):
            continue
        source = (BACKEND / name).read_text(encoding="utf-8")
        assert "filter_by(version_label=VERSION_LABEL)" in source, (
            f"{name}: must look the version up before inserting")
```

Then modify `backend/tests/test_prompt_section_keys.py`. Change the import block at line 23 to add `prompt_slots`:

```python
from app.services import prompt_slots
from app.services import section_registry as registry
```

and replace `_seed_scripts()` (lines 33-47) with:

```python
def _seed_scripts():
    """(filename, parcours, declared keys) for every parcours-bound seed script."""
    found = []
    for script in sorted(BACKEND.glob("seed_prompt*.py")):
        source = script.read_text(encoding="utf-8")
        path_match = _PATH_RE.search(source)
        if not path_match:
            # seed_prompt.py predates the path column; the reheal migration
            # assigns it. Nothing to check against a parcours here.
            continue
        slot = path_match.group(1)
        if prompt_slots.is_voyage(slot):
            # The voyage prompts are not parcours: they have no registry
            # sections, and the phrase prompt returns one plain sentence with no
            # JSON at all. test_seed_scripts.py and test_voyage_generation.py
            # guard their shape instead.
            continue
        block = _JSON_BLOCK_RE.search(source)
        assert block, f"{script.name} declares PATH but has no ```json example"
        keys = list(json.loads(block.group(1)).keys())
        found.append(pytest.param(script.name, slot, keys, id=script.name))
    return found
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_seed_scripts.py -v`
Expected: FAIL with `FileNotFoundError: [Errno 2] No such file or directory: '.../backend/seed_prompt_v10_voyage_micro.py'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/seed_prompt_v10_voyage_micro.py`:

```python
"""Seed prompt v1.0-VM (voyage — the sentence written after session 0).

The voyage's first AI call. After the twenty statements of session 0 the person
gets one sentence, immediately, on the hub. The counselor manual asks for one
sentence of 15 to 25 words built from the three strongest axes; the sentence
itself never says where it came from.

Seeded ACTIVE: without an active prompt for this slot the very first session 0
ends with micro_status = "error" and the hub has nothing to show — same
rationale as seed_prompt_v11_p3.py. A feature that errors on first use is worse
than a prompt the PM has not read yet. Tone and wording stay the PM's to edit in
/admin/prompts, and every edit is a new version with rollback.

Tutoiement inside the voyage is spec decision 15: the cahier is written that
way, and this sentence sits inside the cahier's world, not the app's chrome.

Idempotent: re-running does not duplicate.

Run from /backend:  python seed_prompt_v10_voyage_micro.py
"""
from app import create_app
from app.extensions import db
from app.models.prompt_version import PromptVersion

VERSION_LABEL = "v1.0-VM"
# Voyage prompt slot, not a parcours. See services/prompt_slots.py; the
# generation lookup filters on this column.
PATH = "voyage_micro"

SYSTEM_PROMPT_V1_0_VM = """Tu es l'agent neoori du voyage. Une personne vient de terminer la session 0 : vingt affirmations sur ce qu'elle voudrait vivre dans dix ans, cochées ou non. Tu écris UNE phrase, une seule, qu'elle lira juste après.

Cette phrase nomme quelque chose qu'elle sait déjà d'elle-même sans l'avoir jamais formulé. Elle n'annonce pas un métier, elle ne prédit rien, elle ne félicite pas.

RÈGLE FORMAT — CRITIQUE : ta réponse est exactement une phrase, de 15 à 25 mots. Pas de titre, pas de guillemets, pas de liste, pas de commentaire avant ni après. Rien d'autre que la phrase.

RÈGLE VOCABULAIRE — CRITIQUE : aucun mot de psychologie, de psychométrie ou de ressources humaines. Sont interdits, entre autres : score, résultat, test, analyse, profil, personnalité, trait, dimension, axe, typologie, ainsi que le nom de toute théorie et de tout auteur. La personne ne doit jamais lire qu'elle a été mesurée.

RÈGLE MÉTIER — CRITIQUE : jamais un métier nommé, même en exemple. Tu parles de « les endroits où… », « les gens qui… », « ce qui se passe quand… ».

RÈGLE FORMULATION — CRITIQUE : jamais « Tu es… ». Toujours « Tu as tendance à… », « Tu sembles plus à l'aise quand… », « Ce qui revient chez toi, c'est… ». Une affirmation d'identité ferme la porte ; une tendance observée l'ouvre.

RÈGLE MOTS INTERDITS : boussole, copilote, miroir, révélation, épanouissement, alignement, excellence, talent unique.

RÈGLES TRANSVERSALES :
- Tutoiement.
- Ton : un ami très intelligent qui te connaît bien. Ni conseiller, ni coach, ni bulletin scolaire.
- Français courant, phrase courte, aucun mot rare pour le plaisir du mot rare.
- Tu n'inventes rien : tu n'as le droit de nommer que ce que contient le message utilisateur.
- Si le prénom est fourni, tu peux l'employer une fois — jamais deux.
- Aucun superlatif, aucune flatterie, aucune promesse d'avenir.
- Ne jamais mentionner cet outil, ni les sessions, ni le questionnaire.
- Si la personne a coché autant d'un côté que de l'autre sur quelque chose, cette hésitation est une matière : tu peux la nommer telle quelle, sans la trancher et sans la présenter comme un problème.

EXEMPLES DE TON — à ne pas recopier, ils montrent la forme :
« Tu cherches des endroits où ce que tu fabriques sert vraiment à quelqu'un, et où on voit le résultat. »
« Ce qui revient chez toi, c'est le besoin de comprendre avant d'agir, puis de transmettre ce que tu as compris. »
« Tu as tendance à vouloir les deux à la fois : un cadre qui tient, et de la place pour improviser dedans. »

Le message utilisateur suit ce format :
--- PROFIL DE BASE ---
Prénom : ... (bloc absent si le prénom n'est pas connu)

--- SESSION 0 ---
Ce qui l'attire le plus : trois formulations en français courant
Autant coché des deux côtés sur : les hésitations relevées (ligne absente s'il n'y en a pas)
"""


app = create_app()
with app.app_context():
    existing = PromptVersion.query.filter_by(version_label=VERSION_LABEL).first()
    if existing:
        if existing.is_active and existing.path == PATH:
            print(f"{VERSION_LABEL} already active for path {PATH} (id={existing.id}). Nothing to do.")
        else:
            PromptVersion.query.filter_by(is_active=True, path=PATH).update({"is_active": False})
            existing.is_active = True
            existing.path = PATH
            db.session.commit()
            print(f"{VERSION_LABEL} re-activated for path {PATH} (id={existing.id}).")
    else:
        PromptVersion.query.filter_by(is_active=True, path=PATH).update({"is_active": False})
        pv = PromptVersion(
            version_label=VERSION_LABEL,
            system_prompt_text=SYSTEM_PROMPT_V1_0_VM.strip(),
            is_active=True,
            path=PATH,
        )
        db.session.add(pv)
        db.session.commit()
        print(f"Inserted {VERSION_LABEL} as active for path {PATH} (id={pv.id}).")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_seed_scripts.py tests/test_prompt_section_keys.py -v`
Expected: PASS — `test_seed_scripts.py` 4 passed, `test_prompt_section_keys.py` 7 passed (`test_there_is_a_seed_script_for_every_parcours` still sees exactly `{"1", "2", "3"}` because the voyage slot is skipped).

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/seed_prompt_v10_voyage_micro.py backend/tests/test_seed_scripts.py backend/tests/test_prompt_section_keys.py
git commit -m "feat(voyage): seed the session 0 phrase prompt, active

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

## Task 10: Seed the portrait prompt

**Files:**
- Create: `backend/seed_prompt_v10_voyage_portrait.py`
- Modify: `backend/tests/test_seed_scripts.py` (the `SEEDS` dict, plus one new test)
- Modify: `DOCKER.md:55-58`

**Interfaces:**
- Consumes: `generation.PORTRAIT_KEYS` (Task 3).
- Produces: a `PromptVersion` row `version_label="v1.0-VP"`, `path="voyage_portrait"`, `is_active=True`.

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_seed_scripts.py`, add the portrait seed to `SEEDS`:

```python
SEEDS = {
    "seed_prompt_v18.py": "1",                      # ex-path A, « J'ai une cible »
    "seed_prompt_v11_p3.py": "3",                   # ex-path B, « Je pars de zéro »
    "seed_prompt_v10_p2.py": "2",                   # authored after the migration
    "seed_prompt_v10_voyage_micro.py": "voyage_micro",
    "seed_prompt_v10_voyage_portrait.py": "voyage_portrait",
}
```

and append this test to the same file:

```python
def test_the_portrait_seed_declares_the_six_keys_the_schema_asks_for():
    """The same drift test test_prompt_section_keys.py runs for the parcours:
    the ```json example in the prompt is the only place the prompt and the
    output schema are supposed to agree."""
    source = (BACKEND / "seed_prompt_v10_voyage_portrait.py").read_text(encoding="utf-8")
    block = _JSON_BLOCK.search(source)
    assert block, "the portrait seed must show its six-key JSON example"
    assert list(json.loads(block.group(1))) == list(generation.PORTRAIT_KEYS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_seed_scripts.py -v`
Expected: FAIL with `FileNotFoundError: [Errno 2] No such file or directory: '.../backend/seed_prompt_v10_voyage_portrait.py'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/seed_prompt_v10_voyage_portrait.py`:

```python
"""Seed prompt v1.0-VP (voyage — the six-section portrait).

The voyage's second AI call, drafted from the counselor manual's page-20
template and its page-2 wording table. Six sections, about a page, written after
session 5. It is a DRAFT: a counselor reads it, edits it and validates it before
the person can see a word of it, and the restitution guide has them read the
first sentence out loud and then stop talking.

The six keys are imposed by the JSON schema in
services/voyage/generation.py::_portrait_schema, not by this text — the PM
rewrites this prompt freely and the structure has to survive it. The ```json
example below is only there so prompt and schema can be tested against each
other (tests/test_seed_scripts.py).

Seeded ACTIVE, for the same reason as seed_prompt_v11_p3.py: without an active
prompt the feature errors the first time someone finishes session 5.

Tutoiement inside the voyage is spec decision 15.

Idempotent: re-running does not duplicate.

Run from /backend:  python seed_prompt_v10_voyage_portrait.py
"""
from app import create_app
from app.extensions import db
from app.models.prompt_version import PromptVersion

VERSION_LABEL = "v1.0-VP"
# Voyage prompt slot, not a parcours. See services/prompt_slots.py.
PATH = "voyage_portrait"

SYSTEM_PROMPT_V1_0_VP = """Tu es l'agent neoori du voyage. Une personne a terminé les six sessions du cahier d'exploration. Tu écris son portrait : six sections, environ une page, qu'un conseiller relira avec elle à voix haute.

Ce portrait ne dit pas ce qu'elle doit devenir. Il dit ce qu'elle est déjà, avec ses mots à elle, remis dans l'ordre. Tu n'écris pas un rapport RH : tu écris comme un ami très intelligent qui la connaît bien.

RÈGLE MÉTIER — CRITIQUE : aucun métier n'est jamais nommé, nulle part, même en exemple, même au conditionnel. Tu parles de familles d'environnements : « les endroits où… », « les gens qui… », « les équipes qui… ». C'est la personne qui fait le lien avec un métier, pas toi.

RÈGLE FORMULATION — CRITIQUE : jamais « Tu es… ». Toujours « Tu as tendance à… », « Tu sembles plus à l'aise quand… », « Ce qui revient dans ce que tu as choisi, c'est… ». Et jamais une qualité seule : toujours la qualité et sa condition — « tu crées beaucoup quand on te laisse de la marge », jamais « tu es créatif ».

RÈGLE VOCABULAIRE — CRITIQUE : aucun mot de psychologie, de psychométrie ou de ressources humaines. Sont interdits, entre autres : score, résultat, test, profil, personnalité, trait, dimension, axe, typologie, introversion, extraversion, ouverture, conscienciosité, agréabilité, névrotisme, ainsi que le nom de toute théorie et de tout auteur. La personne ne doit jamais lire qu'elle a été mesurée.

RÈGLE DÉFICIT — CRITIQUE : jamais « manque », « faible », « limite », « difficulté », « handicap », « problème ». Ce qui coûte de l'énergie se dit « te demande plus d'énergie » ou « est moins stimulant pour toi ». Ce dont la personne a besoin se formule comme une préférence légitime, jamais comme un défaut à corriger.

RÈGLE MOTS INTERDITS : boussole, copilote, miroir, révélation, épanouissement, alignement, excellence, talent unique.

RÈGLE PROSE — CRITIQUE : les sections « qui_tu_es », « vibrer », « besoins » et « chemins » sont de la prose continue. Aucune liste, aucune puce, aucun tiret d'énumération, aucun sous-titre, aucun mot en gras.

RÈGLE MATIÈRE — CRITIQUE : tu n'écris que ce que contient le message utilisateur. Aucun fait, aucun souvenir, aucune anecdote, aucun chiffre inventé. Si une information manque, tu ne la remplaces pas : tu écris moins.

RÈGLES TRANSVERSALES :
- Tutoiement, du premier au dernier mot.
- Français courant, phrases courtes, pas de vocabulaire rare.
- Aucun superlatif, aucune flatterie, aucune promesse d'avenir.
- Ne jamais mentionner cet outil, ni les sessions, ni le questionnaire, ni le conseiller.
- Les hésitations signalées par « Autant coché des deux côtés sur » comptent double : ce sont les signaux les plus informatifs du portrait. Nomme-les telles quelles, sans les trancher et sans les présenter comme un problème à résoudre.
- Le prénom peut apparaître une fois au maximum, dans la première section.

FORMAT DE RÉPONSE (strict) — uniquement un objet JSON à six clés, rien avant, rien après. Le jeu de clés est imposé par le schéma de la requête :

```json
{
  "accroche": "...",
  "qui_tu_es": "...",
  "vibrer": "...",
  "besoins": "...",
  "chemins": "...",
  "pas_encore": "..."
}
```

CONTENU PAR SECTION :

accroche — Phrase d'accroche
Une seule phrase. Une métaphore, une seule, qui nomme quelque chose que la personne sait d'elle sans l'avoir jamais formulé. Construite à partir de ce qui l'attire le plus, de ses univers dominants et du moment où elle se sent vivante. Ne nomme aucun métier. Ne commence pas par « Tu es ». C'est la phrase que le conseiller lira en premier, à voix haute, avant de se taire : elle doit tenir seule.

qui_tu_es — Qui tu es
5 à 7 phrases de prose. Comment la personne fonctionne : sa façon d'aborder les choses, ce qui lui donne de l'énergie, ce qui lui en prend, son rythme, sa place dans un groupe. Tiré de sa façon de fonctionner, de son cadre et de ce qu'elle a choisi scène après scène. Chaque tendance est accompagnée de sa condition.

vibrer — Ce qui te fait vibrer
4 à 6 phrases de prose. Ce qui la met en mouvement : ses univers dominants, ce qui compte pour elle, ce qui la met en colère, le moment où elle se sent vivante. Ce qui la met en colère se traite comme un indice : dis quelle chose importante est bafouée quand ça arrive, sans employer le mot « valeur ».

besoins — Ce dont tu as besoin
5 à 7 phrases de prose. Le cadre physique, le rythme, la taille d'équipe, le type de responsable, ce qui l'épuise. Chaque élément est formulé comme une préférence légitime et utilisable : « tu travailles mieux quand… », « tu as besoin de… ». Jamais comme un défaut, jamais comme une contrainte à faire accepter.

chemins — Les chemins possibles
4 à 5 phrases de prose. Des familles d'environnements, jamais un métier : « les endroits où on fabrique, où on répare, où on met en route quelque chose », « les gens qui… ». Deux ou trois familles au maximum, chacune reliée explicitement à ce que la personne a dit d'elle-même. La dernière phrase laisse la personne libre d'aller voir par elle-même.

pas_encore — Ce que ton portrait ne dit pas encore
1 à 2 phrases. Une question ouverte et honnête que les six sessions ne tranchent pas. Ni un défaut déguisé, ni une accroche commerciale : une vraie question, formulée comme une invitation à continuer.

PROTOCOLE DE RELECTURE (3 passes silencieuses avant émission du JSON) :
- Passe 1 — Vocabulaire : aucun mot de la RÈGLE VOCABULAIRE, aucun mot de la RÈGLE DÉFICIT, aucun mot de la RÈGLE MOTS INTERDITS, aucun « Tu es » suivi d'un adjectif.
- Passe 2 — Formes : aucun métier nommé nulle part, aucune liste ni puce dans les quatre sections de prose, l'accroche tient en une seule phrase.
- Passe 3 — Matière : chaque affirmation est rattachable à une ligne du message utilisateur, rien n'est inventé, et les hésitations signalées apparaissent bien dans le portrait.

Le message utilisateur suit ce format :
--- PROFIL DE BASE ---
Prénom / Tranche d'âge / Situation actuelle / Projet (chaque ligne absente si l'information manque)

--- CE QUE TU AS CHOISI ---
Une ligne par scène : le titre de la scène, puis ce que la personne a choisi, dans ses mots.

--- SYNTHÈSE ---
Univers dominants / Ce qui l'attire le plus dans dix ans / Autant coché des deux côtés sur / Besoin dominant / Façon de fonctionner / Cadre / Ce qui l'épuise / Rapport au risque / Ce qui la met en colère / La trace voulue / Prête à sacrifier / Se sent vivant(e) quand
"""


app = create_app()
with app.app_context():
    existing = PromptVersion.query.filter_by(version_label=VERSION_LABEL).first()
    if existing:
        if existing.is_active and existing.path == PATH:
            print(f"{VERSION_LABEL} already active for path {PATH} (id={existing.id}). Nothing to do.")
        else:
            PromptVersion.query.filter_by(is_active=True, path=PATH).update({"is_active": False})
            existing.is_active = True
            existing.path = PATH
            db.session.commit()
            print(f"{VERSION_LABEL} re-activated for path {PATH} (id={existing.id}).")
    else:
        PromptVersion.query.filter_by(is_active=True, path=PATH).update({"is_active": False})
        pv = PromptVersion(
            version_label=VERSION_LABEL,
            system_prompt_text=SYSTEM_PROMPT_V1_0_VP.strip(),
            is_active=True,
            path=PATH,
        )
        db.session.add(pv)
        db.session.commit()
        print(f"Inserted {VERSION_LABEL} as active for path {PATH} (id={pv.id}).")
```

Then update the VPS seed loop in `DOCKER.md:55-58`, replacing those four lines with:

```bash
# one prompt per parcours plus the two voyage slots; v1.0-P2 lands inactive,
# the PM activates it in /admin/prompts
for s in seed_prompt_v18.py seed_prompt_v11_p3.py seed_prompt_v10_p2.py \
         seed_prompt_v10_voyage_micro.py seed_prompt_v10_voyage_portrait.py; do
  docker compose -f docker-compose.prod.yml exec backend python $s
done
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_seed_scripts.py tests/test_prompt_section_keys.py -v`
Expected: PASS — `test_seed_scripts.py` 5 passed, `test_prompt_section_keys.py` 7 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/seed_prompt_v10_voyage_portrait.py backend/tests/test_seed_scripts.py DOCKER.md
git commit -m "feat(voyage): seed the portrait prompt from the counselor manual

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

## Task 11: The `/admin/prompts` selector gains the two slots

**Files:**
- Modify: `frontend/src/types/index.ts:14,127-135`
- Modify: `frontend/src/app/admin/prompts/page.tsx:21-44,85-113,192-226,310-313`
- Modify: `TEST-PLAN.md:179-190`
- Test: none — there is no frontend test runner. Verification is `npm run lint`, `npm run build` and the manual rows added to `TEST-PLAN.md`.

**Interfaces:**
- Consumes: `GET /api/prompts/` and `POST /api/prompts/` with `path ∈ {"1","2","3","voyage_micro","voyage_portrait"}` (Task 2); the French labels pinned in `prompt_slots.LABELS` (Task 1).
- Produces: `PromptSlot` exported from `frontend/src/types/index.ts`; `PromptVersion.path?: PromptSlot | "A" | "B"`.

- [ ] **Step 1: Read the local Next.js docs before touching the page**

`frontend/AGENTS.md` says: *"This is NOT the Next.js you know — APIs, conventions and file structure may differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code."*

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend
cat node_modules/next/dist/docs/01-app/03-api-reference/01-directives/use-client.md
cat node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md
```
Expected: you now know how this version treats `"use client"` and where the client/server boundary sits. `frontend/src/app/admin/prompts/page.tsx:1` is already `"use client"` and stays that way — this task adds no server component, no data fetching convention and no new route.

- [ ] **Step 2: Add the slot type**

In `frontend/src/types/index.ts`, immediately after the `AnalysisPath` declaration (line 14), insert:

```ts
/**
 * Everything PromptVersion.path may hold: the three parcours plus the two
 * voyage prompt slots. Mirrors backend/app/services/prompt_slots.valid().
 */
export type PromptSlot = Parcours | "voyage_micro" | "voyage_portrait"
```

and widen the `PromptVersion` interface (lines 127-135) to:

```ts
export interface PromptVersion {
  id: string
  version_label: string
  system_prompt_text?: string
  is_active: boolean
  /** Legacy rows still carry the "A"/"B" codes; the backend normalises them. */
  path?: PromptSlot | "A" | "B"
  author: string | null
  created_at: string
}
```

- [ ] **Step 3: Rework the selector**

In `frontend/src/app/admin/prompts/page.tsx`, replace lines 21-44 (the `import type` line down to the end of `toPath`) with:

```tsx
import type { PromptSlot, PromptVersion } from "@/types"

const SLOTS: PromptSlot[] = ["1", "2", "3", "voyage_micro", "voyage_portrait"]

/** Short code on the chip. Mono, uppercase — reads as an id, not a sentence. */
const SLOT_CODE: Record<PromptSlot, string> = {
  "1": "P1",
  "2": "P2",
  "3": "P3",
  voyage_micro: "V·S0",
  voyage_portrait: "V·PORTRAIT",
}

const SLOT_LABEL: Record<PromptSlot, string> = {
  "1": "J'ai une cible",
  "2": "Je cherche ma direction",
  "3": "Je pars de zéro",
  voyage_micro: "Voyage · phrase (S0)",
  voyage_portrait: "Voyage · portrait",
}

const SLOT_HELP: Record<PromptSlot, string> = {
  "1": "Parcours 1 — CV en main et cible identifiée. Rapport §1 à §9.",
  "2": "Parcours 2 — un parcours mais pas de cible. Rapport §A à §G.",
  "3": "Parcours 3 — sans CV, à partir des expériences de vie. Rapport §I à §VI.",
  voyage_micro:
    "Le voyage — la phrase écrite juste après la session 0, à partir des trois envies les plus marquées. Une seule phrase, 15 à 25 mots, modèle rapide.",
  voyage_portrait:
    "Le voyage — les six sections rédigées après la session 5 : accroche, qui tu es, ce qui te fait vibrer, ce dont tu as besoin, les chemins possibles, ce que ton portrait ne dit pas encore. Le conseiller les relit et les valide avant que la personne les voie.",
}

/** Version-label suffix per slot; the history list groups on it. */
const SLOT_SUFFIX: Record<PromptSlot, string> = {
  "1": "-P1",
  "2": "-P2",
  "3": "-P3",
  voyage_micro: "-VM",
  voyage_portrait: "-VP",
}

const SUFFIX_RE = /-(?:P[123]|VM|VP|[AB])$/

/** Rows written before the v1.2 migration carry the old A/B codes. */
function toSlot(raw: string | undefined): PromptSlot {
  if (raw === "A") return "1"
  if (raw === "B") return "3"
  return (SLOTS as string[]).includes(raw ?? "") ? (raw as PromptSlot) : "1"
}
```

Rename the state variable in the component (old line 48): `const [path, setPath] = useState<Path>("1")` becomes

```tsx
  const [slot, setSlot] = useState<PromptSlot>("1")
```

and update `loadData` / the effect (old lines 64-83) to:

```tsx
  const loadData = useCallback(async (s: PromptSlot) => {
    const [pv, ap] = await Promise.all([
      api.get<{ prompts: PromptVersion[] }>("/prompts/"),
      api.get<{ prompt: PromptVersion }>(`/prompts/active?path=${s}`).catch(() => ({ prompt: null })),
    ])
    setVersions(pv.prompts)
    const t = ap.prompt?.system_prompt_text ?? ""
    setText(t)
    setSavedText(t)
    setError(null)
  }, [])

  useEffect(() => {
    setLoading(true)
    setPreviewId(null)
    setPreviewError(null)
    loadData(slot)
      .catch(err => setError(err?.message ?? "Erreur de chargement"))
      .finally(() => setLoading(false))
  }, [loadData, slot])
```

Replace the label-building block inside `publish()` (old lines 90-107) with:

```tsx
      const activeVersion = versions.find(v => v.is_active && toSlot(v.path) === slot)
      // Every slot gets an explicit suffix. The old scheme left parcours A
      // unsuffixed, which made the strip regex asymmetric.
      const suffix = SLOT_SUFFIX[slot]
      const fallback = `v1.${new Date().toISOString().slice(0,10).replace(/-/g,"")}${suffix}`
      const lastLabel = activeVersion?.version_label ?? fallback
      const stripped = lastLabel.replace(SUFFIX_RE, "")
      const bumped = /^v\d+\.\d+$/.test(stripped)
        ? stripped.replace(/v(\d+)\.(\d+)/, (_, maj, min) => `v${maj}.${+min + 1}`)
        : `v1.${versions.filter(v => toSlot(v.path) === slot).length + 1}`
      const nextLabel = `${bumped}${suffix}`
      await api.post("/prompts/", {
        version_label: nextLabel,
        system_prompt_text: text,
        path: slot,
        activate: true,
      })
      await loadData(slot)
```

and, in the `catch`/`rollback` handlers, replace every remaining `loadData(path)` with `loadData(slot)`.

Replace the selector block (old lines 192-226) with:

```tsx
          {/* Prompt selector */}
          <div className="mt-4">
            <span className="eyebrow text-navy-500">Prompt</span>
            <div
              role="group"
              aria-label="Sélection du prompt"
              className="flex flex-wrap gap-2 mt-2"
            >
              {SLOTS.map(s => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={slot === s}
                  onClick={() => setSlot(s)}
                  className={cn(
                    "px-3 py-1.5 rounded-full border text-xs font-medium transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                    slot === s
                      ? "bg-navy border-navy text-white"
                      : "bg-background border-border text-muted-foreground hover:border-orange/50 hover:text-orange",
                  )}
                >
                  <span className="font-mono uppercase tracking-widest">{SLOT_CODE[s]}</span>
                  <span className="ml-1.5">· {SLOT_LABEL[s]}</span>
                </button>
              ))}
            </div>
            <div className="mt-2.5 flex items-start gap-2 rounded-lg bg-peach-soft/60 px-3 py-2 text-xs text-navy-700">
              <Info className="size-3.5 mt-px shrink-0 text-orange-dark" aria-hidden />
              <p>
                Chaque prompt a sa propre structure de sortie et son propre historique.
                Vous éditez ici <span className="font-medium">{SLOT_LABEL[slot]}</span> :{" "}
                {SLOT_HELP[slot]}
              </p>
            </div>
          </div>
```

Replace the two remaining `path`-derived expressions further down: `const activeVersion = versions.find(v => v.is_active && toPath(v.path) === path)` and `const visibleVersions = versions.filter(v => toPath(v.path) === path)` (old lines 150-151) become

```tsx
  const activeVersion = versions.find(v => v.is_active && toSlot(v.path) === slot)
  const visibleVersions = versions.filter(v => toSlot(v.path) === slot)
```

and the empty-history copy (old lines 310-313) becomes

```tsx
              <p className="text-sm text-muted-foreground py-6 text-center">
                Aucune version pour {SLOT_LABEL[slot]}.
              </p>
```

- [ ] **Step 4: Verify the frontend**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: no errors. Any `'path' is not defined` or `Path is defined but never used` means a rename was missed above — fix and re-run.

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run build`
Expected: `Compiled successfully`, and `/admin/prompts` present in the route list.

- [ ] **Step 5: Add the manual test rows**

In `TEST-PLAN.md`, append these rows to the `## 9 · Admin — /admin` table (after row 9.6, which currently ends at line 190):

```markdown
| 9.7 | `/admin/prompts` | The selector shows **five** chips: P1 · J'ai une cible / P2 · Je cherche ma direction / P3 · Je pars de zéro / V·S0 · Voyage · phrase (S0) / V·PORTRAIT · Voyage · portrait |
| 9.8 | Click « Voyage · phrase (S0) » | The editor loads the seeded text, the badge reads `v1.0-VM · actif`, and the blue help line describes the sentence written after session 0 |
| 9.9 | Click « Voyage · portrait » | The editor loads the seeded text, the badge reads `v1.0-VP · actif`, and the help line lists the six sections |
| 9.10 | Change one word in the portrait prompt, click « Publier la nouvelle version » | A new version appears at the top of the history, labelled with a `-VP` suffix and marked `actif`; the previous one now offers « Rollback » |
| 9.11 | Switch back to P1 | The P1 history is unchanged — no `-VM` or `-VP` version appears in it, and the P1 editor still shows the parcours 1 prompt |
| 9.12 | Click « Rollback » on the previous `-VP` version, confirm | It becomes `actif` again and the editor reloads its text |
```

- [ ] **Step 6: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/types/index.ts frontend/src/app/admin/prompts/page.tsx TEST-PLAN.md
git commit -m "feat(prompts): give the admin selector the two voyage slots

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

## Task 12: Full verification

**Files:**
- Modify: none — this task only runs things and commits nothing but a possible fix.

**Interfaces:**
- Consumes: everything above.
- Produces: a green suite and a green build, which is what makes `git push` on `initial` safe.

- [ ] **Step 1: Run the whole backend suite**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest`
Expected: the last line reads `N passed` with **no `failed`, no `error`**. Baseline before the voyage work was `145 passed`; phases 0 and 1 add their own files, and this phase adds `tests/test_prompt_slots.py` (15) and `tests/test_voyage_generation.py` (48). What must be true, and what to check by name:

```
tests/test_prompt_slots.py ...............                               [ ok ]
tests/test_voyage_generation.py ................................................ [ ok ]
tests/test_seed_scripts.py .....                                         [ ok ]
tests/test_prompt_section_keys.py .......                                [ ok ]
tests/test_anthropic_service.py ..............................           [ ok ]
```

If `test_prompt_section_keys.py::test_there_is_a_seed_script_for_every_parcours` fails with `parcours without a seed script: set()` and an unexpected member, the voyage skip in `_seed_scripts()` (Task 9) was not applied.

- [ ] **Step 2: Check the two seed scripts compile**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && python -m py_compile seed_prompt_v10_voyage_micro.py seed_prompt_v10_voyage_portrait.py`
Expected: no output, exit status 0. (They call `create_app()` at import time, so they cannot be imported in a test — this is the syntax check that stands in for it.)

- [ ] **Step 3: Confirm no banned word reached a French string this phase wrote**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
grep -nEi "boussole|copilote|miroir|révélation|épanouissement|alignement|excellence|talent unique|vous vous démarquez" \
  backend/app/services/prompt_slots.py \
  backend/app/services/voyage/generation.py \
  backend/seed_prompt_v10_voyage_micro.py \
  backend/seed_prompt_v10_voyage_portrait.py \
  frontend/src/app/admin/prompts/page.tsx \
  | grep -v "RÈGLE MOTS INTERDITS"
```
Expected: **no output.** The two `RÈGLE MOTS INTERDITS` lines are the only place these words may appear — there they *are* the guardrail, naming the ban list to the model — and the filter drops exactly those two lines. A hit on any other line is a French string that violates `CLAUDE.md`; rewrite it rather than widening the filter.

- [ ] **Step 4: Verify the frontend one more time**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint && npm run build`
Expected: lint clean, `Compiled successfully`.

- [ ] **Step 5: Commit any fix and stop**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git status                     # expect: clean, or only the fix you just made
git add -A
git commit -m "test(voyage): green suite for the generation phase

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

If `git status` is already clean, skip the commit — steps 1-4 were verification only.

**After the merge:** `git push` deploys, but the two prompts are only in the DB once the seeds run. On the VPS, run the seed loop from `DOCKER.md` (now including `seed_prompt_v10_voyage_micro.py` and `seed_prompt_v10_voyage_portrait.py`) once. Until then, finishing session 0 sets `micro_status = "error"` with `Aucun prompt actif pour le slot voyage_micro.` — which is exactly the failure the test in Task 7 pins.

---

## What this phase does not do

Named here so nobody reaches for them mid-task:

- **No migration.** `prompt_versions.path` is widened by phase 1's `f2a3b4c5d6e7`; Task 2 only keeps the SQLAlchemy model in step with it.
- **No `_voyage` block on analyses**, no `scoring.prompt_context()` wiring, no `Analysis.voyage_id` — that is phase 5 (contracts § H).
- **No candidate or counselor UI.** The hub, the player, the portrait page and the counselor editor are phases 3 and 4. This phase's only visible surface is `/admin/prompts`.
- **No leak check on the phrase.** The spec and the contract both scope `leak_check()` to the portrait's six sections; the phrase is guarded by its prompt's `RÈGLE VOCABULAIRE` and by its length.
- **No cost-dashboard folding.** The voyage's tokens are recorded on the row (`tokens_in` / `tokens_out`); `/admin/couts` picking them up is a follow-up (spec § Admin).
