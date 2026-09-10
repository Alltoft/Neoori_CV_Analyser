# Le voyage — Phase 1 (Models, migrations, encryption, routes) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give « le voyage » a persistent, encrypted, server-gated backend — two models, four migrations, sixteen HTTP handlers, the prompt-slot vocabulary and the admin role endpoint — with no AI call and no UI.

**Architecture:** A `Voyage` row is one attempt at the cahier's six sessions; everything the person actually said (answers, exit tickets, the S0 phrase, the portrait) lives in Fernet ciphertext columns, exactly as `SensitiveProfile` holds bloc 5, while plaintext columns carry only status, timestamps and foreign keys. `backend/app/routes/voyage.py` serves two audiences from one blueprint: candidate handlers are owner-scoped and resolve the caller's own voyage, counselor handlers need the counselor/admin role **and** the share token. Session locking (S0 needs the voyage; S1–S5 need a counselor code plus a Profil de base with prénom + tranche d'âge; S(n) needs S(n−1)) is enforced server-side by `models.voyage.session_lock()`, and the two generation spawn points are called through a seam that phase 2 fills in.

**Tech Stack:** Flask 3, Flask-SQLAlchemy, Flask-JWT-Extended, Flask-Migrate (Alembic), Fernet via `app/utils/crypto.py`, pytest on SQLite in-memory. MySQL 8.4 in production.

**Spec:** docs/superpowers/specs/2026-09-09-voyage-design.md
**Contracts:** docs/superpowers/plans/2026-09-09-voyage-contracts.md

---

## Global Constraints

- App-facing strings are **French** — every `error` / `errors` / `message` string in a response included. Code comments, docstrings and commit messages are **English**.
- Copy ban list, never in user-facing French chrome: **boussole, copilote, miroir, révélation, épanouissement, alignement, excellence, talent unique, vous vous démarquez**. Nothing in this phase is chrome, but the French error strings below were written to respect it — do not reword them.
- **The candidate never sees a score, a trait name or a framework name.** The only derived thing a candidate endpoint may return is `micro_phrase` and the six portrait sections once validated. `synthesis()` output is counselor-facing only.
- **Never required.** Every parcours runs identically with no voyage; `analyses.voyage_id` is nullable and no existing flow may start depending on a voyage in this phase.
- Statuses are `db.String(16)` / `sa.String(length=16)` — **never** `db.Enum` / `sa.Enum`. Widening a MySQL ENUM is the one migration step this repo cannot rehearse locally.
- Current alembic head before this phase: **`b8c9d0e1f2a3`** (`b8c9d0e1f2a3_add_progress_to_analyses.py`). New head after it: **`f2a3b4c5d6e7`**. Revision ids are hand-written, pinned by the contract § D — do not generate new ones.
- Every migration must round-trip **up and down on SQLite**. Task 2 makes that possible; from then on the rehearsal is three commands.
- Encryption goes through `backend/app/utils/crypto.py` (`encrypt_json` / `decrypt_json`, Fernet + MultiFernet rotation). `crypto.DecryptionError` **propagates** — it is never swallowed, exactly as `SensitiveProfile.conditions` lets it.
- Never hold a DB connection across an Anthropic stream (`db.session.remove()` before, re-acquire after — `app/services/anthropic_service.py:463-472`). This phase opens no stream; the seam it installs hands the work to phase 2, which must keep that discipline.
- Prompts live in the DB (`PromptVersion`), never in code. Structure comes from a JSON-schema `output_config` via `extra_body`, never from prompt prose. This phase only widens the column that names the prompt slot.
- Tests: `pytest`, SQLite in-memory, run from `/Users/imran/Downloads/design_handoff_cv_analyzer/backend`. Fixtures `app`, `client`, `admin_headers` come from `backend/tests/conftest.py`; a logged-in candidate is built the way `tests/test_profile.py:160-168` does (`create_access_token(identity=str(user.id), additional_claims={"role": "candidate"})` — `TestingConfig` puts the JWT in headers, not cookies).
- **Next.js caveat** (`frontend/AGENTS.md:2-4`): "This is NOT the Next.js you know. This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices." **Phase 1 touches no frontend file**, so no task here needs that step; phases 3 and 4 do. There is no frontend test runner in this repo — verification there is `cd frontend && npm run lint` / `npm run build` plus TEST-PLAN.md rows. Neither applies to this phase.
- `git push` on branch `initial` deploys: every commit must leave `pytest` green.
- Commit messages: Conventional Commits, English, lowercase subject, no trailing period, scope `voyage` (or `prompts` / `admin` where the change is there). The repo's house style is a real explanatory body — say *why*, not *what*. Append whatever `Co-Authored-By` trailer your session's attribution rules require.

---

## Preconditions — run this before Task 1

Phase 0 (the question bank and the scoring functions) must already be merged. This phase imports it and cannot be built without it.

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend
./venv/bin/python -c "
from app.services.voyage import bank, scoring
print(bank.SCORING_VERSION, len(bank.all_item_ids()), bank.SESSION_IDS)
print(sorted(scoring.synthesize({'answers': {}, 'billets': {}})))
"
./venv/bin/pytest -q | tail -1
```

Expected: `cahier-2026-09 53 ('0', '1', '2', '3', '4', '5')`, then
`['completeness', 'riasec', 's0', 's2', 's3', 's4', 's5', 'scoring_version']`, then `232 passed`.

If the first command raises `ModuleNotFoundError: No module named 'app.services.voyage'`, **stop**: phase 0 has not landed, and every task from Task 3 on will fail on import.

Names this phase consumes from phase 0 (contract § A and § B — do not re-derive them):

```python
bank.SCORING_VERSION            # "cahier-2026-09"
bank.SESSION_IDS                # ("0", "1", "2", "3", "4", "5")
bank.public()      -> dict      # {"scoring_version": str, "sessions": list[dict]}, no weight key at any depth
bank.items(n)      -> list[dict]
bank.item(item_id) -> dict | None
bank.billet_keys(n)-> list[str]
bank.validate_answer(item_id, value) -> bool
scoring.synthesize(responses)          -> dict
scoring.missing_items(responses, n)    -> list[str]
```

---

## File Structure

| File | Responsibility (one per file) |
|---|---|
| `backend/app/services/prompt_slots.py` | **create** — the single answer to "what may `PromptVersion.path` hold": parcours ids ∪ `{voyage_micro, voyage_portrait}`, plus their admin labels. |
| `backend/app/models/voyage.py` | **create** — `Voyage` + `VoyageNote`: columns, Fernet payload properties, `to_dict()`, `micro_phrase`, `synthesis()`, the lookups, and the module-level `session_lock()` gate. |
| `backend/app/routes/voyage.py` | **create** — the 16 HTTP handlers over 12 paths, the owner/counselor access rules, and the generation seam. |
| `backend/migrations/versions/c9d0e1f2a3b4_add_voyages_table.py` | **create** — create `voyages`. |
| `backend/migrations/versions/d0e1f2a3b4c5_add_voyage_notes_table.py` | **create** — create `voyage_notes`. |
| `backend/migrations/versions/e1f2a3b4c5d6_add_voyage_id_to_analyses.py` | **create** — add `analyses.voyage_id` + FK + index. |
| `backend/migrations/versions/f2a3b4c5d6e7_widen_prompt_version_path.py` | **create** — widen `prompt_versions.path` `String(1)` → `String(16)`. |
| `backend/migrations/versions/fd6e96d0d77c_nullable_user_id_on_analyses.py` | **modify** — dialect guard so the chain is rehearsable on SQLite at all. |
| `backend/app/__init__.py` | **modify** — import the voyage model, register `voyage_bp` at `/api/voyage`. |
| `backend/app/models/analysis.py` | **modify** — `voyage_id` column + `"voyage_id"` in `to_dict()`. |
| `backend/app/models/prompt_version.py` | **modify** — `path` becomes `String(16)`; the comment stops saying "parcours id". |
| `backend/app/routes/prompts.py` | **modify** — `_read_path()` validates against `prompt_slots`, not `section_registry`. |
| `backend/app/routes/admin.py` | **modify** — `PUT /users/<id>/role`, and the `voyages` KPI block on `GET /stats`. |
| `backend/tests/test_prompt_slots.py` | **create** — § F: the five slot ids, `normalize()` on legacy A/B and on the two slots, the column width, and the prompts route accepting a slot. |
| `backend/tests/test_voyage_routes.py` | **create** — § C and § E: the model's guarantees (ciphertext at rest, `to_dict()` key set, lookups, `session_lock`) and every endpoint's happy path and refusal. |
| `backend/tests/test_seed_scripts.py` | **modify** — literal regex `(\w)` → `(\w+)`, validation switches to `prompt_slots`. |
| `backend/tests/test_analysis_model.py` | **modify** — `to_dict()` carries `voyage_id`. |
| `backend/tests/test_admin.py` | **modify** — the role endpoint and the voyage KPIs. |

Not in this phase, cited only so nothing is invented locally: `app/services/voyage/generation.py` (§ G, phase 2 — this phase calls `generation.start_micro(voyage_id, app)` / `generation.start_portrait(voyage_id, app)` through a seam), `routes/analyses._merge_profile()`'s voyage fold and `anthropic_service._voyage_block()` (§ H, phase 5), everything under `frontend/` (phases 3–4).

---

### Task 1: Prompt slots

`PromptVersion.path` stops meaning "parcours id" and starts meaning "prompt slot". This module is the only place that knows the five legal values. Nothing else in the codebase changes yet — the route switches over in Task 7, once the column is wide enough to hold a slot (Task 6).

**Files:**
- Create: `backend/app/services/prompt_slots.py`
- Create: `backend/tests/test_prompt_slots.py`
- Test: `backend/tests/test_prompt_slots.py`

**Interfaces:**
- Consumes: `app.services.section_registry.PARCOURS` (dict keyed `"1"`,`"2"`,`"3"`), `section_registry.DEFAULT_PARCOURS == "1"`, `section_registry.normalize(value) -> str` (`app/services/section_registry.py:93-127`).
- Produces: `prompt_slots.VOYAGE_MICRO = "voyage_micro"`, `prompt_slots.VOYAGE_PORTRAIT = "voyage_portrait"`, `VOYAGE_SLOTS: tuple[str, str]`, `LABELS: dict[str, str]`, `valid() -> tuple[str, ...]`, `is_valid(slot) -> bool`, `is_voyage(slot) -> bool`, `normalize(slot) -> str`, `label(slot: str) -> str`, `choices() -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_prompt_slots.py
"""PromptVersion.path holds a prompt *slot*, not a parcours id.

The voyage adds two prompts that are not parcours. Numbering them "4" and "5"
would make them appear as parcours everywhere the section registry is iterated
— the admin selector, the cost dashboard, the report renderer — so they get
names instead, and this module is the only place that knows the legal set.
"""
from app.services import prompt_slots
from app.services import section_registry as registry


def test_the_five_slots_are_the_parcours_plus_the_two_voyage_prompts():
    assert prompt_slots.valid() == ("1", "2", "3", "voyage_micro", "voyage_portrait")


def test_parcours_ids_come_first():
    """The admin selector renders valid() in order; parcours are the daily job."""
    assert prompt_slots.valid()[:3] == tuple(registry.PARCOURS)


def test_every_slot_fits_the_column():
    """prompt_versions.path is String(16); 'voyage_portrait' is 15 characters."""
    assert max(len(s) for s in prompt_slots.valid()) <= 16


def test_legacy_path_codes_still_fold_onto_parcours():
    """Rows written before the 3-parcours migration carry 'A'/'B'."""
    assert prompt_slots.normalize("A") == "1"
    assert prompt_slots.normalize("B") == "3"
    assert prompt_slots.normalize("a") == "1"


def test_empty_and_unknown_fall_back_to_parcours_one():
    assert prompt_slots.normalize(None) == "1"
    assert prompt_slots.normalize("") == "1"
    assert prompt_slots.normalize("   ") == "1"
    assert prompt_slots.normalize("nonsense") == registry.DEFAULT_PARCOURS


def test_voyage_slots_survive_normalisation_whatever_the_case():
    """The old _read_path uppercased before validating, and 'VOYAGE_MICRO' is
    not a slot — the voyage check has to happen before any .upper()."""
    assert prompt_slots.normalize("voyage_micro") == "voyage_micro"
    assert prompt_slots.normalize("VOYAGE_MICRO") == "voyage_micro"
    assert prompt_slots.normalize("  Voyage_Portrait  ") == "voyage_portrait"


def test_is_valid_and_is_voyage():
    assert prompt_slots.is_valid("voyage_portrait") is True
    assert prompt_slots.is_valid("4") is False
    assert prompt_slots.is_valid(None) is False
    assert prompt_slots.is_voyage("voyage_micro") is True
    assert prompt_slots.is_voyage("1") is False


def test_labels_are_french_and_cover_every_slot():
    for slot in prompt_slots.valid():
        assert prompt_slots.label(slot) != slot, f"{slot} has no label"
    assert prompt_slots.label("voyage_micro") == "Voyage · phrase (S0)"
    assert prompt_slots.label("voyage_portrait") == "Voyage · portrait"


def test_choices_are_selector_ready():
    assert prompt_slots.choices() == [
        {"value": "1", "label": "Parcours 1 · J'ai une cible"},
        {"value": "2", "label": "Parcours 2 · Je cherche ma direction"},
        {"value": "3", "label": "Parcours 3 · Je pars de zéro"},
        {"value": "voyage_micro", "label": "Voyage · phrase (S0)"},
        {"value": "voyage_portrait", "label": "Voyage · portrait"},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_prompt_slots.py -q`
Expected: FAIL — collection error `ModuleNotFoundError: No module named 'app.services.prompt_slots'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/prompt_slots.py
"""Valid values for PromptVersion.path — parcours ids plus the voyage prompt slots.

Widened from String(1) to String(16) so the two voyage prompts do not have to
masquerade as parcours "4"/"5" everywhere the registry is iterated (spec 18).
A slot is what the generation path looks a prompt up by:

    PromptVersion.query.filter_by(is_active=True, path=<slot>)

so a wrong value here seeds a prompt nothing can ever find.
"""
from . import section_registry as registry

VOYAGE_MICRO = "voyage_micro"
VOYAGE_PORTRAIT = "voyage_portrait"
VOYAGE_SLOTS = (VOYAGE_MICRO, VOYAGE_PORTRAIT)

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
    """Coerce a stored or client-supplied value to a slot.

    The voyage slots are matched *before* any .upper(): the admin route used to
    uppercase before validating, and "VOYAGE_MICRO" is not a slot. Anything
    else falls through to the registry, which still folds the legacy 'A'/'B'
    path codes onto parcours ids and defaults the unrecognised to parcours 1.
    """
    value = str(slot or "").strip()
    if not value:
        return registry.DEFAULT_PARCOURS
    if value.lower() in VOYAGE_SLOTS:
        return value.lower()
    return registry.normalize(value.upper())


def label(slot: str) -> str:
    """French label for the admin selector. Falls back to the raw id."""
    return LABELS.get(slot, slot)


def choices() -> list[dict]:
    """[{"value": "1", "label": "Parcours 1 · J'ai une cible"}, ...]."""
    return [{"value": slot, "label": label(slot)} for slot in valid()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_prompt_slots.py -q`
Expected: PASS — `9 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/services/prompt_slots.py backend/tests/test_prompt_slots.py
git commit -m "feat(prompts): name the prompt slots instead of numbering them

The voyage adds two prompts that are not parcours. Calling them '4' and '5'
would make them show up as parcours everywhere the section registry is
iterated. One module now owns the legal set of PromptVersion.path values, and
normalize() matches the voyage slots before uppercasing so the admin route's
existing .upper() cannot mangle them."
```

---

### Task 2: Make the migration chain rehearsable on SQLite

The contract's acceptance test for every migration is "round-trips up and down on SQLite". Today that is impossible: `fd6e96d0d77c` queries `INFORMATION_SCHEMA.KEY_COLUMN_USAGE` and emits `ALTER TABLE … MODIFY COLUMN`, so `flask db upgrade` against SQLite dies on the second revision with `sqlite3.OperationalError: no such table: INFORMATION_SCHEMA.KEY_COLUMN_USAGE`. Every migration task after this one depends on this fix.

The MySQL branch is untouched — production has been past this revision for months, so the guard only ever runs on a database being built from scratch, which today can only be a rehearsal.

**Files:**
- Modify: `backend/migrations/versions/fd6e96d0d77c_nullable_user_id_on_analyses.py:19-36` (both `upgrade()` and `downgrade()`)

**Interfaces:**
- Consumes: `alembic.op.get_bind()`, `op.batch_alter_table`.
- Produces: a working `flask db upgrade` / `flask db downgrade base` on SQLite — the rehearsal loop every later migration task uses.

- [ ] **Step 1: Prove the chain is broken on SQLite**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend
rm -f /tmp/voyage-mig.db
DATABASE_URL="sqlite:////tmp/voyage-mig.db" FLASK_APP=run.py ./venv/bin/flask db upgrade 2>&1 | tail -3
```
Expected: FAIL with `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: INFORMATION_SCHEMA.KEY_COLUMN_USAGE`.

(`app/config.py:6` calls `load_dotenv()`, which does **not** override an env var already set, so the inline `DATABASE_URL` wins over `.env`'s TiDB URL. Never point this at `.env`'s database.)

- [ ] **Step 2: Add the dialect guard**

Replace the bodies of `upgrade()` and `downgrade()` in `backend/migrations/versions/fd6e96d0d77c_nullable_user_id_on_analyses.py` with:

```python
def upgrade():
    conn = op.get_bind()
    if conn.dialect.name != "mysql":
        # SQLite has neither INFORMATION_SCHEMA nor ALTER COLUMN; batch mode
        # rebuilds the table instead. Reached only when the chain is replayed
        # from scratch — i.e. a local migration rehearsal, never production.
        with op.batch_alter_table("analyses") as batch_op:
            batch_op.alter_column("user_id", existing_type=sa.String(length=36), nullable=True)
        return
    result = conn.execute(sa.text(
        "SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE"
        " WHERE TABLE_NAME='analyses' AND TABLE_SCHEMA=DATABASE()"
        " AND COLUMN_NAME='user_id' AND REFERENCED_TABLE_NAME='users' LIMIT 1"
    ))
    fk_name = result.scalar()
    if fk_name:
        conn.execute(sa.text(f"ALTER TABLE analyses DROP FOREIGN KEY `{fk_name}`"))
    op.execute("ALTER TABLE analyses MODIFY COLUMN user_id VARCHAR(36) NULL")
    op.execute("ALTER TABLE analyses ADD CONSTRAINT fk_analyses_user_id FOREIGN KEY (user_id) REFERENCES users(id)")


def downgrade():
    if op.get_bind().dialect.name != "mysql":
        with op.batch_alter_table("analyses") as batch_op:
            batch_op.alter_column("user_id", existing_type=sa.String(length=36), nullable=False)
        return
    op.execute("ALTER TABLE analyses DROP FOREIGN KEY fk_analyses_user_id")
    op.execute("ALTER TABLE analyses MODIFY COLUMN user_id VARCHAR(36) NOT NULL")
    op.execute("ALTER TABLE analyses ADD CONSTRAINT fk_analyses_user_id FOREIGN KEY (user_id) REFERENCES users(id)")
```

- [ ] **Step 3: Run the full chain up on SQLite**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend
rm -f /tmp/voyage-mig.db
DATABASE_URL="sqlite:////tmp/voyage-mig.db" FLASK_APP=run.py ./venv/bin/flask db upgrade 2>&1 | grep "Running upgrade" | tail -2
```
Expected:
```
INFO  [alembic.runtime.migration] Running upgrade a7b8c9d0e1f2 -> b8c9d0e1f2a3, add progress to analyses
```
with 12 `Running upgrade` lines in total and no traceback.

- [ ] **Step 4: Run the full chain down, then up again**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend
export DATABASE_URL="sqlite:////tmp/voyage-mig.db" FLASK_APP=run.py
./venv/bin/flask db downgrade base 2>&1 | grep -c "Running downgrade"
./venv/bin/flask db upgrade 2>&1 | grep -c "Running upgrade"
./venv/bin/pytest -q | tail -1
unset DATABASE_URL
```
Expected: `12`, then `12`, then `232 passed` (the suite uses SQLite in-memory from `db.create_all()`, so it is unaffected — this step only proves nothing regressed).

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/migrations/versions/fd6e96d0d77c_nullable_user_id_on_analyses.py
git commit -m "fix(migrations): let the chain replay on sqlite

fd6e96d0d77c reads INFORMATION_SCHEMA and emits MODIFY COLUMN, so replaying
the chain from base against SQLite died on the second revision. That made the
house rule — every migration round-trips up and down on SQLite — impossible to
check for any migration written since. The MySQL branch is byte-identical;
the guard only fires on a database built from scratch, which production never
is."
```

---

### Task 3: The Voyage and VoyageNote models

The data half of the feature: columns, the Fernet payload properties, the candidate-safe `to_dict()`, the lookups the routes and phase 5 use, and the session gate. `tests/conftest.py` builds the schema with `db.create_all()`, so the model is fully testable before its migration exists.

**Files:**
- Create: `backend/app/models/voyage.py`
- Create: `backend/tests/test_voyage_routes.py`
- Modify: `backend/app/__init__.py:57` (add `voyage` to the model import list)
- Test: `backend/tests/test_voyage_routes.py`

**Interfaces:**
- Consumes: `app.extensions.db`; `app.utils.crypto.encrypt_json/decrypt_json/DecryptionError` (`app/utils/crypto.py:96-110`); `bank.SCORING_VERSION`, `scoring.synthesize(responses)` (phase 0).
- Produces: `CONSENT_VERSION`, `STATUS_EN_COURS`, `STATUS_S0`, `STATUS_TERMINE`, `STATUSES`, `OPEN_STATUSES`, `MICRO_STATUSES`, `PORTRAIT_STATUSES`, `PORTRAIT_KEYS`, `LOCK_CODE`, `LOCK_PROFILE`, `LOCK_ORDER`; `class Voyage` with `responses`/`micro`/`portrait` properties, `micro_phrase`, `portrait_sections`, `is_open`, `has_code`, `synthesis()`, `open_for/current_for/latest_for/by_token/for_prompt`, `to_dict()`; `class VoyageNote` with `to_dict()`; `session_lock(voyage, profile, n) -> str | None`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_voyage_routes.py
"""Le voyage — what the model guarantees and what the API will and won't do.

Model and routes live in one file, the way test_profile.py keeps bloc 5's
encryption, its validation and its endpoints together: each guarantee only
means something end to end — a route writes, the column holds ciphertext, and
the payload never carries it back.
"""
from datetime import datetime

import pytest

from app.extensions import db as _db
from app.models.user import User
from app.models.profile import Profile
from app.models.voyage import (
    CONSENT_VERSION,
    LOCK_CODE,
    LOCK_ORDER,
    LOCK_PROFILE,
    PORTRAIT_KEYS,
    STATUS_EN_COURS,
    STATUS_S0,
    STATUS_TERMINE,
    Voyage,
    VoyageNote,
    session_lock,
)
from app.services.voyage import bank


# ── helpers, used by every task in this file ─────────────────────────────────

def _user(email, role="candidate"):
    user = User(email=email, password_hash="x", role=role)
    _db.session.add(user)
    _db.session.commit()
    return user


def _headers(user):
    """Bearer headers — TestingConfig reads the JWT from headers, not cookies."""
    from flask_jwt_extended import create_access_token
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return {"Authorization": f"Bearer {token}"}


def _voyage(user, **overrides):
    """A row with the fields POST /api/voyage always sets, plus overrides."""
    fields = {
        "user_id": user.id,
        "status": STATUS_EN_COURS,
        "sessions_completed": [],
        "consent_at": datetime.utcnow(),
        "consent_version": CONSENT_VERSION,
        "age_attested": True,
    }
    fields.update(overrides)
    voyage = Voyage(**fields)
    _db.session.add(voyage)
    _db.session.commit()
    return voyage


def _answers_for(n):
    """One valid answer per item of session n: True for the S0 checklist, the
    first option letter for a scene."""
    return {
        item["id"]: True if n == "0" else item["options"][0]["letter"]
        for item in bank.items(n)
    }


@pytest.fixture
def candidate(app):
    return _user("voyageur@test.fr")


@pytest.fixture
def auth(candidate):
    return _headers(candidate)


# ── the encrypted payloads ───────────────────────────────────────────────────

def test_a_new_voyage_starts_empty_and_silent(app, candidate):
    voyage = _voyage(candidate)
    assert voyage.status == STATUS_EN_COURS
    assert voyage.responses == {"answers": {}, "billets": {}}
    assert voyage.micro == {}
    assert voyage.portrait == {}
    assert voyage.micro_status == "none"
    assert voyage.portrait_status == "none"
    assert voyage.micro_phrase is None
    assert voyage.portrait_sections == {}
    assert voyage.has_code is False
    assert voyage.is_open is True


def test_responses_round_trip_through_the_property(app, candidate):
    voyage = _voyage(candidate)
    voyage.responses = {"answers": {"S0-01": True, "S1-1": "A"},
                        "billets": {"0": {"surprise": "je déteste le bureau"}}}
    _db.session.commit()

    stored = Voyage.query.get(voyage.id).responses
    assert stored["answers"] == {"S0-01": True, "S1-1": "A"}
    assert stored["billets"]["0"]["surprise"] == "je déteste le bureau"


def test_both_response_keys_always_exist(app, candidate):
    """Scoring reads responses["answers"] without a guard — the model owes it
    the shape whatever was stored."""
    voyage = _voyage(candidate)
    voyage.responses = {"answers": {"S0-01": True}}
    _db.session.commit()
    assert Voyage.query.get(voyage.id).responses["billets"] == {}


def test_columns_hold_ciphertext_not_plaintext(app, candidate):
    """The guarantee that makes a psychometric read-out storable at all: a DB
    export, an admin query or a log shipper sees nothing."""
    voyage = _voyage(candidate)
    voyage.responses = {"answers": {"S0-01": True},
                        "billets": {"0": {"surprise": "je déteste le bureau"}}}
    voyage.micro = {"phrase": "Tu cherches des endroits où ce que tu fabriques sert."}
    _db.session.commit()

    row = _db.session.execute(_db.text(
        "SELECT responses_encrypted, micro_encrypted FROM voyages"
    )).first()
    assert "S0-01" not in row[0]
    assert "bureau" not in row[0]
    assert "endroits" not in row[1]


def test_portrait_sections_needs_all_six_keys(app, candidate):
    voyage = _voyage(candidate)
    voyage.portrait = {"sections": {"accroche": "une phrase"}}
    _db.session.commit()
    assert voyage.portrait_sections == {}

    voyage.portrait = {"sections": {k: f"texte {k}" for k in PORTRAIT_KEYS}}
    _db.session.commit()
    assert set(voyage.portrait_sections) == set(PORTRAIT_KEYS)


# ── to_dict: the only thing a candidate ever sees of the row ─────────────────

TO_DICT_KEYS = {
    "id", "status", "sessions_completed", "consent_at", "age_attested",
    "has_code", "micro_status", "micro_phrase", "portrait_status",
    "share_token", "created_at", "completed_at",
}


def test_to_dict_carries_exactly_twelve_keys(app, candidate):
    voyage = _voyage(candidate)
    voyage.responses = {"answers": {"S0-01": True}, "billets": {}}
    voyage.portrait = {"sections": {k: "x" for k in PORTRAIT_KEYS}, "snapshot": {"s0": {}},
                       "flags": ["vocabulaire"], "edited": True}
    _db.session.commit()

    payload = voyage.to_dict()
    assert set(payload) == TO_DICT_KEYS
    flat = str(payload)
    for forbidden in ("S0-01", "snapshot", "vocabulaire", "edited", "user_id"):
        assert forbidden not in flat


def test_the_phrase_is_the_one_derived_thing_a_candidate_may_see(app, candidate):
    voyage = _voyage(candidate)
    voyage.micro = {"phrase": "Tu avances mieux quand le résultat se voit.",
                    "prompt_version_id": "pv-1", "tokens_in": 40, "tokens_out": 20}
    voyage.micro_status = "success"
    _db.session.commit()
    payload = voyage.to_dict()
    assert payload["micro_phrase"] == "Tu avances mieux quand le résultat se voit."
    assert "prompt_version_id" not in payload
    assert "tokens_in" not in payload


def test_share_token_stays_hidden_until_the_voyage_is_finished(app, candidate):
    voyage = _voyage(candidate, status=STATUS_S0, share_token="tok-early")
    assert voyage.to_dict()["share_token"] is None

    voyage.status = STATUS_TERMINE
    _db.session.commit()
    assert voyage.to_dict()["share_token"] == "tok-early"


# ── lookups ──────────────────────────────────────────────────────────────────

def test_open_current_and_latest(app, candidate):
    finished = _voyage(candidate, status=STATUS_TERMINE)
    assert Voyage.open_for(candidate.id) is None
    assert Voyage.current_for(candidate.id).id == finished.id

    open_one = _voyage(candidate, status=STATUS_S0)
    assert Voyage.open_for(candidate.id).id == open_one.id
    assert Voyage.current_for(candidate.id).id == open_one.id
    assert Voyage.latest_for(candidate.id).id == open_one.id


def test_lookups_are_none_for_a_user_who_never_played(app, candidate):
    assert Voyage.current_for(candidate.id) is None
    assert Voyage.latest_for(None) is None
    assert Voyage.by_token("") is None
    assert Voyage.by_token("unknown") is None
    assert Voyage.for_prompt(None) is None


def test_for_prompt_prefers_a_validated_portrait_then_a_phrase(app, candidate):
    """Spec § Injection: before validation an analysis must not tell the person
    what the counselor has not restituted yet — but S0's phrase may travel."""
    assert Voyage.for_prompt(candidate.id) is None

    with_phrase = _voyage(candidate, status=STATUS_S0, micro_status="success")
    assert Voyage.for_prompt(candidate.id).id == with_phrase.id

    validated = _voyage(candidate, status=STATUS_TERMINE,
                        micro_status="success", portrait_status="validated")
    assert Voyage.for_prompt(candidate.id).id == validated.id


def test_a_draft_portrait_is_not_enough_for_for_prompt(app, candidate):
    _voyage(candidate, status=STATUS_TERMINE, portrait_status="draft")
    assert Voyage.for_prompt(candidate.id) is None


# ── notes ────────────────────────────────────────────────────────────────────

def test_deleting_a_voyage_erases_its_notes(app, candidate):
    counselor = _user("note-cascade@test.fr", role="counselor")
    voyage = _voyage(candidate)
    _db.session.add(VoyageNote(voyage_id=voyage.id, counselor_id=counselor.id, body="vu"))
    _db.session.commit()

    _db.session.delete(voyage)
    _db.session.commit()
    assert VoyageNote.query.count() == 0


def test_note_to_dict_has_four_keys(app, candidate):
    counselor = _user("note-shape@test.fr", role="counselor")
    voyage = _voyage(candidate)
    note = VoyageNote(voyage_id=voyage.id, counselor_id=counselor.id, body="à revoir")
    _db.session.add(note)
    _db.session.commit()
    assert set(note.to_dict()) == {"id", "voyage_id", "body", "updated_at"}
    assert note.to_dict()["body"] == "à revoir"


# ── the session gate ─────────────────────────────────────────────────────────

def _profile_for(user, **fields):
    profile = Profile(user_id=user.id, **fields)
    _db.session.add(profile)
    _db.session.commit()
    return profile


def test_session_zero_is_open_as_soon_as_the_voyage_exists(app, candidate):
    """S0 is the 5-minute self-serve half: no code, no profile, no counselor."""
    assert session_lock(_voyage(candidate), None, "0") is None


def test_no_voyage_locks_everything(app):
    assert session_lock(None, None, "0") == LOCK_ORDER
    assert session_lock(None, None, "1") == LOCK_ORDER


def test_the_later_sessions_need_a_counselor_code(app, candidate):
    voyage = _voyage(candidate, sessions_completed=["0"])
    assert session_lock(voyage, None, "1") == LOCK_CODE


def test_the_later_sessions_need_a_prenom_and_an_age_bracket(app, candidate):
    """The portrait uses both; « une information, une seule fois » forbids
    asking again inside the voyage."""
    voyage = _voyage(candidate, sessions_completed=["0"], counselor_code_id="code-1")
    assert session_lock(voyage, None, "1") == LOCK_PROFILE
    profile = _profile_for(candidate, prenom="Marie")
    assert session_lock(voyage, profile, "1") == LOCK_PROFILE
    profile.tranche_age = "25_34"
    _db.session.commit()
    assert session_lock(voyage, profile, "1") is None


def test_sessions_come_in_order(app, candidate):
    voyage = _voyage(candidate, sessions_completed=["0"], counselor_code_id="code-1")
    profile = _profile_for(candidate, prenom="Marie", tranche_age="25_34")
    assert session_lock(voyage, profile, "2") == LOCK_ORDER
    voyage.sessions_completed = ["0", "1"]
    _db.session.commit()
    assert session_lock(voyage, profile, "2") is None


def test_the_first_failing_rule_wins(app, candidate):
    """No code *and* no profile *and* out of order still reads « Avec un
    conseiller » — the one the person can actually act on first."""
    voyage = _voyage(candidate)
    assert session_lock(voyage, None, "5") == LOCK_CODE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_voyage_routes.py -q`
Expected: FAIL — collection error `ModuleNotFoundError: No module named 'app.models.voyage'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/models/voyage.py
"""Le voyage — the six-session exploration and the counselor's private notes.

Two models, one file, because they share one lifecycle:

  Voyage      one attempt at the six sessions. Many rows per user — a retake is
              a new row and the old one is kept, because analyses reference it
              — with at most one *open* at a time; POST /api/voyage enforces
              that, not the schema.
  VoyageNote  one counselor's private note on one voyage. Plaintext on purpose:
              it is the counselor's own writing about their own practice, not
              the person's answers.

Encryption follows SensitiveProfile (models/profile.py) exactly: the columns
hold Fernet tokens and are useless to anything that dumps rows, the payload is
reached through properties and decrypted in-process only, and to_dict() never
carries it. A psychometric read-out — what someone fears, what they would
sacrifice — is more sensitive than bloc 5, not less.

Of all of it, one derived thing may reach the candidate: micro_phrase. Never a
score, never an axis, never a trait or a framework name (spec decision 7).
"""
from datetime import datetime
from uuid import uuid4

from ..extensions import db
from ..services.voyage import bank, scoring
from ..utils import crypto

# Stamped on the row at creation, so a consent text change is traceable.
CONSENT_VERSION = "voyage-v1"

STATUS_EN_COURS, STATUS_S0, STATUS_TERMINE = "en_cours", "s0_termine", "termine"
STATUSES = (STATUS_EN_COURS, STATUS_S0, STATUS_TERMINE)
OPEN_STATUSES = (STATUS_EN_COURS, STATUS_S0)

MICRO_STATUSES = ("none", "generating", "success", "error")
PORTRAIT_STATUSES = ("none", "generating", "draft", "validated", "error")

# The counselor manual's page-20 template, in order.
PORTRAIT_KEYS = ("accroche", "qui_tu_es", "vibrer", "besoins", "chemins", "pas_encore")

# The three lock reasons, in French: the API returns them as `error` and the
# hub renders them on the locked card. frontend/src/types/voyage.ts mirrors
# them byte for byte.
LOCK_CODE = "Avec un conseiller"
LOCK_PROFILE = "Complétez votre profil"
LOCK_ORDER = "Terminez la session précédente"


class Voyage(db.Model):
    """One attempt at the six sessions."""

    __tablename__ = "voyages"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)

    # Strings, never a native enum: widening a MySQL ENUM is the one migration
    # step this repo cannot rehearse locally.
    status = db.Column(db.String(16), nullable=False, default=STATUS_EN_COURS, index=True)
    sessions_completed = db.Column(db.JSON, nullable=False, default=list)

    # Psychometric data needs its own consent record — the profile's does not
    # cover it, and the voyage cannot exist without both of these.
    consent_at = db.Column(db.DateTime, nullable=False)
    consent_version = db.Column(db.String(16), nullable=False, default=CONSENT_VERSION)
    age_attested = db.Column(db.Boolean, nullable=False, default=False)

    # Set by POST /api/voyage/unlock. Gates S1-S5.
    counselor_code_id = db.Column(
        db.String(36), db.ForeignKey("counselor_codes.id"), nullable=True
    )

    # Fernet tokens (URL-safe base64), not raw bytes — Text is the right type.
    responses_encrypted = db.Column(db.Text, nullable=True)
    micro_status = db.Column(db.String(16), nullable=False, default="none")
    micro_encrypted = db.Column(db.Text, nullable=True)
    portrait_status = db.Column(db.String(16), nullable=False, default="none")
    portrait_encrypted = db.Column(db.Text, nullable=True)

    portrait_validated_at = db.Column(db.DateTime, nullable=True)
    validated_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)

    # Set when S5 completes; the link the candidate hands to their counselor.
    share_token = db.Column(db.String(64), unique=True, nullable=True, index=True)

    # Which edition of the bank and the scoring tables produced this row.
    scoring_version = db.Column(db.String(16), nullable=False, default=bank.SCORING_VERSION)

    # Sum of both generation calls, for the cost dashboard.
    tokens_in = db.Column(db.Integer, nullable=True)
    tokens_out = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at = db.Column(db.DateTime, nullable=True)

    # Two FKs point at users.id, so both relationships must say which one they
    # travel — otherwise the mapper raises AmbiguousForeignKeysError at
    # configuration time (precedent: PromptVersion.author).
    user = db.relationship("User", foreign_keys=[user_id])
    validated_by = db.relationship("User", foreign_keys=[validated_by_id])
    counselor_code = db.relationship("CounselorCode", foreign_keys=[counselor_code_id])
    notes = db.relationship(
        "VoyageNote", backref="voyage", lazy="dynamic", cascade="all, delete-orphan"
    )

    # ── encrypted payloads ───────────────────────────────────────────────────
    @property
    def responses(self) -> dict:
        """{"answers": {item_id: bool | str}, "billets": {session: {field: str}}}.

        Both keys always present, so scoring can read them without a guard.
        A DecryptionError propagates rather than being swallowed: silently
        returning {} would look like "never answered" and lose a session.
        """
        payload = crypto.decrypt_json(self.responses_encrypted) or {}
        return {
            "answers": payload.get("answers") or {},
            "billets": payload.get("billets") or {},
        }

    @responses.setter
    def responses(self, value: dict | None) -> None:
        value = value or {}
        self.responses_encrypted = crypto.encrypt_json({
            "answers": value.get("answers") or {},
            "billets": value.get("billets") or {},
        })

    @property
    def micro(self) -> dict:
        """{"phrase", "prompt_version_id", "tokens_in", "tokens_out", "error"}."""
        return crypto.decrypt_json(self.micro_encrypted) or {}

    @micro.setter
    def micro(self, value: dict | None) -> None:
        self.micro_encrypted = crypto.encrypt_json(value or {})

    @property
    def portrait(self) -> dict:
        """{"sections", "snapshot", "flags", "edited", "prompt_version_id",
        "tokens_in", "tokens_out", "error"}."""
        return crypto.decrypt_json(self.portrait_encrypted) or {}

    @portrait.setter
    def portrait(self, value: dict | None) -> None:
        self.portrait_encrypted = crypto.encrypt_json(value or {})

    # ── derived, candidate-safe ──────────────────────────────────────────────
    @property
    def micro_phrase(self) -> str | None:
        """The one sentence S0 produces — the only derived value a candidate
        may see before a counselor has validated anything."""
        return (self.micro or {}).get("phrase") or None

    @property
    def portrait_sections(self) -> dict[str, str]:
        """The six sections, or {} while any of them is missing."""
        sections = (self.portrait or {}).get("sections") or {}
        if not all(sections.get(key) for key in PORTRAIT_KEYS):
            return {}
        return {key: sections[key] for key in PORTRAIT_KEYS}

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def has_code(self) -> bool:
        return bool(self.counselor_code_id)

    # ── scoring ──────────────────────────────────────────────────────────────
    def synthesis(self) -> dict:
        """The counselor's page-18 sheet, recomputed from the answers.

        Never stored: a corrected scoring table must not leave stale rows
        behind. The portrait keeps its own snapshot for traceability.
        """
        return scoring.synthesize(self.responses)

    # ── lookups ──────────────────────────────────────────────────────────────
    @classmethod
    def open_for(cls, user_id: str) -> "Voyage | None":
        if not user_id:
            return None
        return (
            cls.query
            .filter(cls.user_id == user_id, cls.status.in_(OPEN_STATUSES))
            .order_by(cls.created_at.desc())
            .first()
        )

    @classmethod
    def latest_for(cls, user_id: str) -> "Voyage | None":
        if not user_id:
            return None
        return (
            cls.query.filter_by(user_id=user_id).order_by(cls.created_at.desc()).first()
        )

    @classmethod
    def current_for(cls, user_id: str) -> "Voyage | None":
        """What GET /api/voyage serves: the open one, else the last one played."""
        return cls.open_for(user_id) or cls.latest_for(user_id)

    @classmethod
    def by_token(cls, token: str) -> "Voyage | None":
        if not token:
            return None
        return cls.query.filter_by(share_token=token).first()

    @classmethod
    def for_prompt(cls, user_id: str | None) -> "Voyage | None":
        """The voyage an analysis may quote from.

        A validated portrait first; failing that, a voyage that has produced
        its S0 phrase. A draft portrait is deliberately not enough — before
        restitution, an analysis must not tell the person what the counselor
        has not said to them yet.
        """
        if not user_id:
            return None
        validated = (
            cls.query
            .filter_by(user_id=user_id, portrait_status="validated")
            .order_by(cls.created_at.desc())
            .first()
        )
        if validated is not None:
            return validated
        return (
            cls.query
            .filter_by(user_id=user_id, micro_status="success")
            .order_by(cls.created_at.desc())
            .first()
        )

    # ── serialisation ────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        """Twelve keys, and no answer, score, portrait text or foreign key
        among them. The sheet and the portrait have their own endpoints with
        their own access rules; anything added here is reachable by the
        candidate on every poll."""
        return {
            "id": self.id,
            "status": self.status,
            "sessions_completed": self.sessions_completed or [],
            "consent_at": self.consent_at.isoformat() if self.consent_at else None,
            "age_attested": bool(self.age_attested),
            # The boolean, never the code or its id.
            "has_code": self.has_code,
            "micro_status": self.micro_status,
            "micro_phrase": self.micro_phrase,
            "portrait_status": self.portrait_status,
            "share_token": self.share_token if self.status == STATUS_TERMINE else None,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class VoyageNote(db.Model):
    """A counselor's private note on one voyage. Never shown to the candidate."""

    __tablename__ = "voyage_notes"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    voyage_id = db.Column(
        db.String(36),
        db.ForeignKey("voyages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    counselor_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=True)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint("voyage_id", "counselor_id", name="uq_voyage_notes_voyage_counselor"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "voyage_id": self.voyage_id,
            "body": self.body,
            "updated_at": self.updated_at.isoformat(),
        }


def session_lock(voyage: "Voyage | None", profile, n: str) -> str | None:
    """The server-side session gate.

    Returns None when session `n` is open, else the exact French string the API
    returns as `error` and the UI renders on the locked card. `profile` is a
    models.profile.Profile or None; `n` is one of bank.SESSION_IDS — callers
    validate that first.

    Rules, in this order, first failure wins:
      * no voyage                      -> LOCK_ORDER
      * n == "0"                       -> open once the voyage exists
      * n in "1".."5" and no code      -> LOCK_CODE
      * n in "1".."5" and the profile lacks prenom or tranche_age -> LOCK_PROFILE
      * S(n-1) not completed           -> LOCK_ORDER

    The order is the order the person can act in: get a code, then complete the
    profile, then play the session before this one.
    """
    if voyage is None:
        return LOCK_ORDER
    if n == "0":
        return None
    if not voyage.has_code:
        return LOCK_CODE
    prenom = (getattr(profile, "prenom", None) or "").strip()
    tranche_age = (getattr(profile, "tranche_age", None) or "").strip()
    if not prenom or not tranche_age:
        return LOCK_PROFILE
    if str(int(n) - 1) not in (voyage.sessions_completed or []):
        return LOCK_ORDER
    return None
```

Then edit `backend/app/__init__.py:57` so the model is imported before `db.create_all()` and before Flask-Migrate looks for it:

```python
    # Models must be imported before migrate can detect them
    from .models import user, analysis, prompt_version, counselor_note, counselor_code, profile, price_feedback, voyage  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_voyage_routes.py -q`
Expected: PASS — `20 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/models/voyage.py backend/app/__init__.py backend/tests/test_voyage_routes.py
git commit -m "feat(voyage): store a voyage the way bloc 5 is stored

Answers, exit tickets, the S0 phrase and the portrait are Fernet ciphertext;
the plaintext columns carry status, timestamps and foreign keys and nothing
else. to_dict() is capped at twelve keys because the candidate polls it, and
micro_phrase is the only derived value it may carry — never a score, an axis
or a trait name.

session_lock() lives here rather than in the route so the API and the hub
answer the same question the same way: a code, then a profile, then the
session before this one."
```

---

### Task 4: Migrations 1 and 2 — the two voyage tables

Make the deployed schema match the models Task 3 wrote. Two revisions, because they are two tables and `voyage_notes` has a foreign key into `voyages`.

**Files:**
- Create: `backend/migrations/versions/c9d0e1f2a3b4_add_voyages_table.py`
- Create: `backend/migrations/versions/d0e1f2a3b4c5_add_voyage_notes_table.py`

**Interfaces:**
- Consumes: alembic head `b8c9d0e1f2a3`; the column set of `Voyage` / `VoyageNote` from Task 3.
- Produces: alembic revisions `c9d0e1f2a3b4` and `d0e1f2a3b4c5`; tables `voyages`, `voyage_notes`.

- [ ] **Step 1: Confirm the starting head**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend
rm -f /tmp/voyage-mig.db
DATABASE_URL="sqlite:////tmp/voyage-mig.db" FLASK_APP=run.py ./venv/bin/flask db upgrade 2>&1 | grep "Running upgrade" | tail -1
```
Expected: `INFO  [alembic.runtime.migration] Running upgrade a7b8c9d0e1f2 -> b8c9d0e1f2a3, add progress to analyses` — i.e. the chain still stops at the pre-phase head.

- [ ] **Step 2: Write both migration files**

```python
# backend/migrations/versions/c9d0e1f2a3b4_add_voyages_table.py
"""Create the voyages table

One row per attempt at the six sessions of « le voyage ». Many per user (a
retake is a new row, and analyses reference the one that fed them), at most one
open at a time — the API enforces that, not the schema.

Everything content-bearing is a Fernet token in a Text column: the answers, the
S0 phrase, the portrait. A psychometric read-out is more sensitive than bloc 5,
so the plaintext columns hold only status, timestamps and foreign keys.

Statuses are String(16), never a native enum — widening a MySQL ENUM is the one
migration step this repo cannot rehearse locally.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa


revision = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'voyages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('sessions_completed', sa.JSON(), nullable=False),
        sa.Column('consent_at', sa.DateTime(), nullable=False),
        sa.Column('consent_version', sa.String(length=16), nullable=False),
        sa.Column('age_attested', sa.Boolean(), nullable=False),
        sa.Column('counselor_code_id', sa.String(length=36), nullable=True),
        # Fernet tokens (URL-safe base64), not raw bytes — Text is the right type.
        sa.Column('responses_encrypted', sa.Text(), nullable=True),
        sa.Column('micro_status', sa.String(length=16), nullable=False),
        sa.Column('micro_encrypted', sa.Text(), nullable=True),
        sa.Column('portrait_status', sa.String(length=16), nullable=False),
        sa.Column('portrait_encrypted', sa.Text(), nullable=True),
        sa.Column('portrait_validated_at', sa.DateTime(), nullable=True),
        sa.Column('validated_by_id', sa.String(length=36), nullable=True),
        sa.Column('share_token', sa.String(length=64), nullable=True),
        sa.Column('scoring_version', sa.String(length=16), nullable=False),
        sa.Column('tokens_in', sa.Integer(), nullable=True),
        sa.Column('tokens_out', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_voyages_user_id'),
        sa.ForeignKeyConstraint(['validated_by_id'], ['users.id'],
                                name='fk_voyages_validated_by_id'),
        sa.ForeignKeyConstraint(['counselor_code_id'], ['counselor_codes.id'],
                                name='fk_voyages_counselor_code_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_voyages_user_id', 'voyages', ['user_id'])
    op.create_index('ix_voyages_status', 'voyages', ['status'])
    # unique=True on the index rather than a separate UniqueConstraint: the
    # model declares share_token unique+index, and SQLAlchemy renders that pair
    # as one unique index. Two would mean two indexes on MySQL.
    op.create_index('ix_voyages_share_token', 'voyages', ['share_token'], unique=True)


def downgrade():
    op.drop_index('ix_voyages_share_token', table_name='voyages')
    op.drop_index('ix_voyages_status', table_name='voyages')
    op.drop_index('ix_voyages_user_id', table_name='voyages')
    op.drop_table('voyages')
```

```python
# backend/migrations/versions/d0e1f2a3b4c5_add_voyage_notes_table.py
"""Create the voyage_notes table

A counselor's private note on one voyage. Plaintext on purpose: it is the
counselor's own writing about their own practice, not the person's answers —
the same call counselor_notes makes for analyses.

One note per (voyage, counselor) pair, and the FK cascades so erasing a voyage
erases the notes written on it.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa


revision = 'd0e1f2a3b4c5'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'voyage_notes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('voyage_id', sa.String(length=36), nullable=False),
        sa.Column('counselor_id', sa.String(length=36), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['voyage_id'], ['voyages.id'],
                                name='fk_voyage_notes_voyage_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['counselor_id'], ['users.id'],
                                name='fk_voyage_notes_counselor_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('voyage_id', 'counselor_id',
                            name='uq_voyage_notes_voyage_counselor'),
    )
    op.create_index('ix_voyage_notes_voyage_id', 'voyage_notes', ['voyage_id'])


def downgrade():
    op.drop_index('ix_voyage_notes_voyage_id', table_name='voyage_notes')
    op.drop_table('voyage_notes')
```

- [ ] **Step 3: Round-trip both on SQLite**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend
export DATABASE_URL="sqlite:////tmp/voyage-mig.db" FLASK_APP=run.py
./venv/bin/flask db upgrade 2>&1 | grep "Running upgrade" | tail -2
./venv/bin/flask db downgrade b8c9d0e1f2a3 2>&1 | grep "Running downgrade"
./venv/bin/flask db upgrade 2>&1 | grep -c "Running upgrade"
unset DATABASE_URL
```
Expected, in order:
```
INFO  [alembic.runtime.migration] Running upgrade b8c9d0e1f2a3 -> c9d0e1f2a3b4, Create the voyages table
INFO  [alembic.runtime.migration] Running upgrade c9d0e1f2a3b4 -> d0e1f2a3b4c5, Create the voyage_notes table
```
then two `Running downgrade` lines (`d0e1f2a3b4c5 -> c9d0e1f2a3b4`, `c9d0e1f2a3b4 -> b8c9d0e1f2a3`), then `2`.

- [ ] **Step 4: Confirm the suite is still green**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest -q | tail -1`
Expected: `261 passed` (232 baseline + 9 from Task 1 + 20 from Task 3).

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/migrations/versions/c9d0e1f2a3b4_add_voyages_table.py backend/migrations/versions/d0e1f2a3b4c5_add_voyage_notes_table.py
git commit -m "feat(voyage): create the voyages and voyage_notes tables

Statuses are String(16) rather than an enum, so a new status is a code change
and not a MySQL ALTER nobody can rehearse. share_token gets one unique index,
matching what the model's unique+index pair renders, so the migration and
db.create_all() agree. Both revisions round-trip up and down on SQLite."
```

---

### Task 5: `analyses.voyage_id`

Traceability, exactly like `prompt_version_id`: a report records which voyage fed it. The column is written by phase 5's `_merge_profile()` fold; this phase only creates it and exposes it, so the two phases can ship independently.

**Files:**
- Modify: `backend/app/models/analysis.py:12` (add the column after `prompt_version_id`), `backend/app/models/analysis.py:68` (add the key after `"prompt_version_id"`)
- Create: `backend/migrations/versions/e1f2a3b4c5d6_add_voyage_id_to_analyses.py`
- Modify: `backend/tests/test_analysis_model.py` (append)
- Test: `backend/tests/test_analysis_model.py`

**Interfaces:**
- Consumes: `Analysis.to_dict(audience)` (`app/models/analysis.py:58-102`); the `voyages` table from Task 4.
- Produces: `Analysis.voyage_id: str | None` and `to_dict()["voyage_id"]` — what phase 5 sets via `Analysis(voyage_id=inputs.get("_voyage_id"))`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_analysis_model.py`:

```python
# ── voyage traceability ──────────────────────────────────────────────────────

def test_to_dict_carries_the_voyage_that_fed_the_analysis():
    """Same tier of data as prompt_version_id: which exploration produced this
    report, kept so a B2G file can be reconstructed after a retake."""
    analysis = _analysis("1")
    analysis.voyage_id = "voy-123"
    assert analysis.to_dict()["voyage_id"] == "voy-123"


def test_voyage_id_is_null_rather_than_absent_when_there_is_no_voyage():
    """The voyage is never required — every parcours runs identically without
    one, and the key must still be there so the client need not branch."""
    payload = _analysis("1").to_dict()
    assert "voyage_id" in payload
    assert payload["voyage_id"] is None


def test_the_counselor_view_carries_it_too():
    analysis = _analysis("1")
    analysis.voyage_id = "voy-456"
    assert analysis.to_dict(audience="counselor")["voyage_id"] == "voy-456"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_analysis_model.py -q`
Expected: FAIL — `AttributeError: 'Analysis' object has no attribute 'voyage_id'` on the first of the three.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/models/analysis.py`, add the column directly under `prompt_version_id` (line 12):

```python
    prompt_version_id = db.Column(db.String(36), db.ForeignKey("prompt_versions.id"), nullable=True)
    # Which voyage fed this analysis, when the person has played one. Nullable
    # and never required: every parcours runs identically with no voyage.
    voyage_id = db.Column(db.String(36), db.ForeignKey("voyages.id"), nullable=True, index=True)
```

and the key in `to_dict()` directly under `"prompt_version_id"` (line 68):

```python
            "prompt_version_id": self.prompt_version_id,
            "voyage_id": self.voyage_id,
```

Then create the migration:

```python
# backend/migrations/versions/e1f2a3b4c5d6_add_voyage_id_to_analyses.py
"""Add analyses.voyage_id

Traceability, exactly like prompt_version_id: an analysis records which voyage
fed it, so a report can be traced back to the exploration behind it even after
the person retakes the voyage. Nullable — the voyage is never required, and
every parcours runs identically without one.

batch_alter_table so the file runs on SQLite, which cannot ADD CONSTRAINT.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa


revision = 'e1f2a3b4c5d6'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('analyses') as batch_op:
        batch_op.add_column(sa.Column('voyage_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_analyses_voyage_id', 'voyages', ['voyage_id'], ['id'])
        batch_op.create_index('ix_analyses_voyage_id', ['voyage_id'])


def downgrade():
    with op.batch_alter_table('analyses') as batch_op:
        batch_op.drop_index('ix_analyses_voyage_id')
        batch_op.drop_constraint('fk_analyses_voyage_id', type_='foreignkey')
        batch_op.drop_column('voyage_id')
```

- [ ] **Step 4: Run test to verify it passes, then round-trip the migration**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend
./venv/bin/pytest tests/test_analysis_model.py -q | tail -1
export DATABASE_URL="sqlite:////tmp/voyage-mig.db" FLASK_APP=run.py
./venv/bin/flask db upgrade 2>&1 | grep "Running upgrade"
./venv/bin/flask db downgrade d0e1f2a3b4c5 2>&1 | grep "Running downgrade"
./venv/bin/flask db upgrade 2>&1 | grep -c "Running upgrade"
unset DATABASE_URL
```
Expected: `10 passed` on the pytest line (7 before this task, 3 added); then `Running upgrade d0e1f2a3b4c5 -> e1f2a3b4c5d6, Add analyses.voyage_id`; then `Running downgrade e1f2a3b4c5d6 -> d0e1f2a3b4c5, Add analyses.voyage_id`; then `1`.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/models/analysis.py backend/migrations/versions/e1f2a3b4c5d6_add_voyage_id_to_analyses.py backend/tests/test_analysis_model.py
git commit -m "feat(voyage): record which voyage fed an analysis

Same tier of data as prompt_version_id, and for the same reason: a B2G file
has to stay reconstructable after the person retakes the voyage. Nullable and
unset for now — phase 5 fills it in from _merge_profile — so the column can
ship on its own without any flow starting to depend on a voyage."
```

---

### Task 6: `prompt_versions.path` becomes `String(16)`

The column stops holding a parcours id and starts holding a prompt slot. `"voyage_portrait"` is 15 characters, so 16 is the exact fit. This is the change that makes Task 7 safe on MySQL.

**Files:**
- Modify: `backend/app/models/prompt_version.py:14-17`
- Create: `backend/migrations/versions/f2a3b4c5d6e7_widen_prompt_version_path.py`
- Modify: `backend/tests/test_prompt_slots.py` (append)
- Test: `backend/tests/test_prompt_slots.py`

**Interfaces:**
- Consumes: `prompt_slots.valid()` from Task 1.
- Produces: alembic head `f2a3b4c5d6e7`; `PromptVersion.path` able to hold any slot.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_prompt_slots.py`:

```python
# ── the column that holds a slot ─────────────────────────────────────────────

def test_the_path_column_is_wide_enough_for_a_slot():
    """'voyage_portrait' is 15 characters. On MySQL a String(1) column would
    have refused it (or truncated it, which is worse: the generation lookup
    filters on this column and would silently find nothing)."""
    from app.models.prompt_version import PromptVersion
    assert PromptVersion.__table__.c.path.type.length == 16


def test_a_voyage_slot_survives_a_round_trip_through_the_column(app):
    from app.extensions import db
    from app.models.prompt_version import PromptVersion
    prompt = PromptVersion(
        version_label="v1.0-VM",
        system_prompt_text="…",
        path=prompt_slots.VOYAGE_PORTRAIT,
        is_active=True,
    )
    db.session.add(prompt)
    db.session.commit()
    found = PromptVersion.query.filter_by(is_active=True, path="voyage_portrait").first()
    assert found is not None
    assert found.to_dict(include_text=False)["path"] == "voyage_portrait"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_prompt_slots.py -q`
Expected: FAIL — `assert 1 == 16` in `test_the_path_column_is_wide_enough_for_a_slot`.

- [ ] **Step 3: Write minimal implementation**

Replace `backend/app/models/prompt_version.py:14-17` with:

```python
    # Prompt slot — '1' | '2' | '3' | 'voyage_micro' | 'voyage_portrait'.
    # See services/prompt_slots.py. Rows written before the v1.2 migration
    # carried 'A'/'B'; normalize() still accepts those on read.
    path = db.Column(db.String(16), nullable=False, default='1', server_default='1')
```

Then create the migration:

```python
# backend/migrations/versions/f2a3b4c5d6e7_widen_prompt_version_path.py
"""Widen prompt_versions.path from String(1) to String(16)

PromptVersion.path stops being a parcours id and becomes a prompt *slot*:
'1' | '2' | '3' | 'voyage_micro' | 'voyage_portrait' (services/prompt_slots.py).
Using '4'/'5' for the two voyage prompts would make them show up as parcours
everywhere the section registry is iterated. 'voyage_portrait' is 15 characters,
so 16 is the exact fit.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa


revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('prompt_versions') as batch_op:
        batch_op.alter_column(
            'path',
            existing_type=sa.String(length=1),
            type_=sa.String(length=16),
            existing_nullable=False,
            existing_server_default='1',
        )


def downgrade():
    # Narrowing first would truncate or fail outright on MySQL: fold the two
    # voyage slots back onto parcours 1 before the column can hold one char.
    op.execute("UPDATE prompt_versions SET path = '1' WHERE LENGTH(path) > 1")
    with op.batch_alter_table('prompt_versions') as batch_op:
        batch_op.alter_column(
            'path',
            existing_type=sa.String(length=16),
            type_=sa.String(length=1),
            existing_nullable=False,
            existing_server_default='1',
        )
```

- [ ] **Step 4: Run test to verify it passes, then round-trip the migration**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend
./venv/bin/pytest tests/test_prompt_slots.py -q | tail -1
export DATABASE_URL="sqlite:////tmp/voyage-mig.db" FLASK_APP=run.py
./venv/bin/flask db upgrade 2>&1 | grep "Running upgrade"
./venv/bin/flask db downgrade e1f2a3b4c5d6 2>&1 | grep "Running downgrade"
./venv/bin/flask db upgrade 2>&1 | grep -c "Running upgrade"
./venv/bin/flask db current 2>&1 | tail -1
unset DATABASE_URL
```
Expected: `11 passed`; then `Running upgrade e1f2a3b4c5d6 -> f2a3b4c5d6e7, Widen prompt_versions.path from String(1) to String(16)`; then the matching downgrade line; then `1`; then `f2a3b4c5d6e7 (head)`.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/models/prompt_version.py backend/migrations/versions/f2a3b4c5d6e7_widen_prompt_version_path.py backend/tests/test_prompt_slots.py
git commit -m "feat(prompts): widen path to hold a slot name

The generation path looks a prompt up by this column, so a truncated value
does not raise — it silently finds nothing. 16 characters is the exact fit for
'voyage_portrait'. The downgrade folds any slot back onto parcours 1 before
narrowing, because MySQL refuses to shrink a column whose data would not fit."
```

---

### Task 7: The prompts route validates against slots

Wire Task 1's module into the two places that decide what `path` may be. Nothing about parcours behaviour changes: `normalize()` still folds `'A'`/`'B'`, and `list_prompts` still only validates when a `path` query arg was actually supplied (`app/routes/prompts.py:33-36`).

**Files:**
- Modify: `backend/app/routes/prompts.py:1-24`
- Modify: `backend/tests/test_seed_scripts.py:11,20,29-33`
- Modify: `backend/tests/test_prompt_slots.py` (append)
- Test: `backend/tests/test_prompt_slots.py`, `backend/tests/test_seed_scripts.py`

**Interfaces:**
- Consumes: `prompt_slots.normalize/is_valid/valid` (Task 1); `admin_headers` fixture (`tests/conftest.py:26-41`).
- Produces: `POST /api/prompts` and `GET /api/prompts/active` accept `path="voyage_micro"` / `"voyage_portrait"`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_prompt_slots.py`:

```python
# ── the admin route that writes the column ───────────────────────────────────

def test_the_prompts_route_accepts_a_voyage_slot(client, admin_headers):
    """Without this the PM cannot publish either voyage prompt from
    /admin/prompts, and the feature errors on first use."""
    res = client.post("/api/prompts/", headers=admin_headers, json={
        "version_label": "v1.0-VM",
        "system_prompt_text": "Tu écris une phrase.",
        "path": "voyage_micro",
        "activate": True,
    })
    assert res.status_code == 201
    assert res.get_json()["prompt"]["path"] == "voyage_micro"

    active = client.get("/api/prompts/active?path=voyage_micro")
    assert active.status_code == 200
    assert active.get_json()["prompt"]["version_label"] == "v1.0-VM"


def test_the_same_label_may_exist_once_per_slot(client, admin_headers):
    """The uniqueness check is scoped to the slot, so 'v1.0' can belong to a
    parcours and to a voyage prompt at once."""
    body = {"version_label": "v1.0", "system_prompt_text": "x"}
    assert client.post("/api/prompts/", headers=admin_headers,
                       json={**body, "path": "1"}).status_code == 201
    assert client.post("/api/prompts/", headers=admin_headers,
                       json={**body, "path": "voyage_portrait"}).status_code == 201
    assert client.post("/api/prompts/", headers=admin_headers,
                       json={**body, "path": "voyage_portrait"}).status_code == 409


def test_activating_a_voyage_prompt_leaves_the_parcours_prompts_alone(client, admin_headers):
    """Activation deactivates the others *for that slot* only — activating the
    portrait prompt must not silently disable parcours 1."""
    from app.models.prompt_version import PromptVersion
    client.post("/api/prompts/", headers=admin_headers, json={
        "version_label": "v9-P1", "system_prompt_text": "x", "path": "1", "activate": True})
    client.post("/api/prompts/", headers=admin_headers, json={
        "version_label": "v9-VP", "system_prompt_text": "x",
        "path": "voyage_portrait", "activate": True})
    assert PromptVersion.query.filter_by(is_active=True, path="1").count() == 1
    assert PromptVersion.query.filter_by(is_active=True, path="voyage_portrait").count() == 1
```

And rewrite the guard in `backend/tests/test_seed_scripts.py` — line 11 (the import), line 20 (the regex) and lines 29-33 (the assertion):

```python
from app.services import prompt_slots
```

```python
# (\w+), not (\w): a slot id is a name now, not a single character.
_LITERAL = re.compile(r"""(?:path\s*=|^PATH\s*=)\s*["'](\w+)["']""", re.MULTILINE)
```

```python
            assert prompt_slots.is_valid(value), (
                f"{name}: path={value!r} is not a prompt slot "
                f"({list(prompt_slots.valid())})"
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_prompt_slots.py tests/test_seed_scripts.py -q`
Expected: FAIL — `assert 400 == 201` in `test_the_prompts_route_accepts_a_voyage_slot` (the route still uppercases and validates against `section_registry`, so `"voyage_micro"` is rejected with `path doit être l'un de '1', '2', '3'.`).

- [ ] **Step 3: Write minimal implementation**

Replace `backend/app/routes/prompts.py:1-24` with:

```python
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models.prompt_version import PromptVersion
from ..services import prompt_slots
from ..utils.decorators import admin_required

prompts_bp = Blueprint("prompts", __name__)

_SLOTS_LABEL = ", ".join(f"'{slot}'" for slot in prompt_slots.valid())


def _read_path(raw):
    """Validate a prompt slot from the request, accepting legacy 'A'/'B'.

    Slots are the parcours ids plus the two voyage prompts; see
    services/prompt_slots.py. normalize() matches the voyage slots before
    uppercasing, because this function used to uppercase first and
    'VOYAGE_MICRO' is not a slot.

    Returns (slot, error_response).
    """
    slot = prompt_slots.normalize(raw)
    if not prompt_slots.is_valid(slot):
        return None, (jsonify({"error": f"path doit être l'un de {_SLOTS_LABEL}."}), 400)
    return slot, None
```

(`section_registry` is no longer imported here — `prompt_slots` re-exports what this file needed from it.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_prompt_slots.py tests/test_seed_scripts.py -q | tail -1`
Expected: PASS — `15 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/routes/prompts.py backend/tests/test_prompt_slots.py backend/tests/test_seed_scripts.py
git commit -m "feat(prompts): let the admin dashboard publish a voyage prompt

_read_path uppercased before validating, so a slot name could never survive
it. It now normalises through prompt_slots, which matches the voyage slots
first and still folds the legacy A/B codes. The seed-script guard reads a
whole slot name instead of a single character, for the same reason."
```

---

### Task 8: The voyage blueprint — bank, read, create, erase

The first four handlers, plus registration on the app factory. Creation is where consent and the age attestation are enforced: the voyage cannot exist without both, and one open voyage per user is a 409, not a second row.

**Files:**
- Create: `backend/app/routes/voyage.py`
- Modify: `backend/app/__init__.py:60-67` (import), `backend/app/__init__.py:69-76` (register)
- Modify: `backend/tests/test_voyage_routes.py` (append)
- Test: `backend/tests/test_voyage_routes.py`

**Interfaces:**
- Consumes: `bank.public()`; `Voyage.current_for/open_for`, `Voyage.to_dict()`, `CONSENT_VERSION`, `STATUS_EN_COURS` (Task 3); `bank.SCORING_VERSION`.
- Produces: blueprint `voyage_bp` at `/api/voyage`; handlers `get_bank`, `get_voyage`, `create_voyage`, `delete_voyage`; helpers `_current()`, `_profile()`, and the module constant `NO_VOYAGE = "Aucun voyage en cours."`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_routes.py` (the helpers `_user`, `_headers`, `_voyage`, `_answers_for` and the fixtures `candidate` / `auth` are already defined at the top of the file by Task 3):

```python
# ── GET /api/voyage/bank ─────────────────────────────────────────────────────

WEIGHT_KEYS = {"riasec", "axes", "sdt", "schwartz", "big5", "style", "env",
               "risk", "sens", "plain"}


def _walk(node):
    """Every dict in a nested JSON payload."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def test_the_bank_serves_text_and_no_weights(client, auth):
    """Decision 6: the option→trait mapping is the product and the counselor
    manual is marked confidential. It never leaves the server."""
    res = client.get("/api/voyage/bank", headers=auth)
    assert res.status_code == 200
    payload = res.get_json()["bank"]
    assert payload["scoring_version"] == bank.SCORING_VERSION
    assert [s["n"] for s in payload["sessions"]] == list(bank.SESSION_IDS)
    for node in _walk(payload):
        leaked = WEIGHT_KEYS & set(node)
        assert not leaked, f"scoring key(s) {leaked} reached the client"


def test_the_bank_needs_an_account(client):
    assert client.get("/api/voyage/bank").status_code == 401


# ── GET / POST /api/voyage ───────────────────────────────────────────────────

def test_a_user_who_never_played_has_no_voyage(client, auth):
    res = client.get("/api/voyage", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["voyage"] is None


def test_creation_requires_consent_and_the_age_attestation(client, auth):
    """Decision 13: psychometric data needs its own consent record, and 15 is
    the French digital-consent age."""
    res = client.post("/api/voyage", json={}, headers=auth)
    assert res.status_code == 400
    errors = res.get_json()["errors"]
    assert "Le consentement est requis." in errors
    assert "Vous devez attester avoir 15 ans ou plus." in errors

    res = client.post("/api/voyage", json={"consent": True, "age_attested": False}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["errors"] == ["Vous devez attester avoir 15 ans ou plus."]

    assert Voyage.query.count() == 0


def test_creation_stamps_the_consent_and_the_scoring_version(client, auth):
    res = client.post("/api/voyage", json={"consent": True, "age_attested": True}, headers=auth)
    assert res.status_code == 201
    payload = res.get_json()["voyage"]
    assert payload["status"] == STATUS_EN_COURS
    assert payload["sessions_completed"] == []
    assert payload["consent_at"] is not None
    assert payload["age_attested"] is True

    row = Voyage.query.one()
    assert row.consent_version == CONSENT_VERSION
    assert row.scoring_version == bank.SCORING_VERSION


def test_only_one_open_voyage_at_a_time(client, auth):
    client.post("/api/voyage", json={"consent": True, "age_attested": True}, headers=auth)
    res = client.post("/api/voyage", json={"consent": True, "age_attested": True}, headers=auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Un voyage est déjà en cours."
    assert Voyage.query.count() == 1


def test_a_retake_is_allowed_once_the_previous_one_is_finished(client, auth, candidate):
    """Decision 3: the old row is kept, because analyses reference it."""
    _voyage(candidate, status=STATUS_TERMINE, share_token="tok-old")
    res = client.post("/api/voyage", json={"consent": True, "age_attested": True}, headers=auth)
    assert res.status_code == 201
    assert Voyage.query.count() == 2


def test_a_voyage_is_only_ever_the_callers_own(client, auth, candidate):
    """No candidate endpoint takes an id from the client, so there is nothing
    to enumerate — but the neighbour must still see their own state."""
    _voyage(candidate, status=STATUS_S0)
    neighbour = _headers(_user("voisin@test.fr"))
    assert client.get("/api/voyage", headers=neighbour).get_json()["voyage"] is None


# ── DELETE /api/voyage ───────────────────────────────────────────────────────

def test_erasure_is_independent_of_the_profile(client, auth, candidate):
    """Decision 14 — the two-speed argument to a prescriber: « vous gardez le
    contrôle de ce qu'on garde »."""
    _db.session.add(Profile(user_id=candidate.id, prenom="Marie", tranche_age="25_34"))
    _db.session.commit()
    client.post("/api/voyage", json={"consent": True, "age_attested": True}, headers=auth)

    res = client.delete("/api/voyage", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["message"] == "Voyage supprimé."
    assert Voyage.query.count() == 0
    assert Profile.query.filter_by(user_id=candidate.id).count() == 1


def test_erasing_nothing_is_not_an_error(client, auth):
    """Mirrors DELETE /api/profile: the person asked for nothing to be left,
    and nothing is left."""
    res = client.delete("/api/voyage", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["message"] == "Aucun voyage à supprimer."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_voyage_routes.py -q`
Expected: FAIL — `assert 404 == 200` in `test_the_bank_serves_text_and_no_weights` (no blueprint is registered at `/api/voyage` yet).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/routes/voyage.py
"""Le voyage — the candidate's six sessions and the counselor's sheet.

Two audiences, two access rules, one blueprint:

  * candidate handlers are owner-scoped. They resolve the caller's own current
    voyage and never take an id from the client, so there is nothing to
    enumerate and no ownership check to forget.
  * counselor handlers need the counselor/admin role **and** the share token.
    That is deliberately stricter than /api/c/<token> for analyses: the
    synthesis sheet is a psychometric read-out, so a leaked link alone must
    not open it (spec § Security).

Session locking is enforced here and not only in the UI — see
models.voyage.session_lock: S0 needs the voyage to exist, S1-S5 need a
counselor code and a Profil de base with prénom + tranche d'âge, and every
session needs the one before it.
"""
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models.profile import Profile
from ..models.voyage import (
    CONSENT_VERSION,
    STATUS_EN_COURS,
    Voyage,
)
from ..services.voyage import bank

voyage_bp = Blueprint("voyage", __name__)

# The API's fixed French strings. app.url_map.strict_slashes is False globally,
# so "" also answers "/" — do not add per-route slash handling.
NO_VOYAGE = "Aucun voyage en cours."


def _current() -> Voyage | None:
    """The caller's own voyage: the open one, else the last one played."""
    return Voyage.current_for(get_jwt_identity())


def _profile() -> Profile | None:
    return Profile.query.filter_by(user_id=get_jwt_identity()).first()


# ── candidate ────────────────────────────────────────────────────────────────

@voyage_bp.get("/bank")
@jwt_required()
def get_bank():
    """The question bank, text only.

    bank.public() strips every scoring key at every depth. The mapping from an
    option to a trait is the product and the counselor manual is confidential,
    so it never crosses this line.
    """
    return jsonify({"bank": bank.public()}), 200


@voyage_bp.get("")
@jwt_required()
def get_voyage():
    voyage = _current()
    return jsonify({"voyage": voyage.to_dict() if voyage else None}), 200


@voyage_bp.post("")
@jwt_required()
def create_voyage():
    """Start a voyage. Both boxes are mandatory and both are recorded.

    Consent is a separate record from the profile's: a psychometric profile is
    not covered by consent given for a CV analysis. The age attestation is the
    French digital-consent floor; under-15 parental consent is out of scope for
    v1 (spec decision 13).
    """
    data = request.get_json(silent=True) or {}
    errors = []
    if data.get("consent") is not True:
        errors.append("Le consentement est requis.")
    if data.get("age_attested") is not True:
        errors.append("Vous devez attester avoir 15 ans ou plus.")
    if errors:
        return jsonify({"errors": errors}), 400

    user_id = get_jwt_identity()
    if Voyage.open_for(user_id) is not None:
        return jsonify({"error": "Un voyage est déjà en cours."}), 409

    voyage = Voyage(
        user_id=user_id,
        status=STATUS_EN_COURS,
        sessions_completed=[],
        consent_at=datetime.utcnow(),
        consent_version=CONSENT_VERSION,
        age_attested=True,
        scoring_version=bank.SCORING_VERSION,
    )
    db.session.add(voyage)
    db.session.commit()
    return jsonify({"voyage": voyage.to_dict()}), 201


@voyage_bp.delete("")
@jwt_required()
def delete_voyage():
    """RGPD erasure, independent of the profile in both directions.

    Not a 404 when there is nothing: the person asked for nothing to be left,
    and nothing is left (mirrors delete_profile).
    """
    voyage = _current()
    if voyage is None:
        return jsonify({"message": "Aucun voyage à supprimer."}), 200
    db.session.delete(voyage)
    db.session.commit()
    return jsonify({"message": "Voyage supprimé."}), 200
```

Then register it in `backend/app/__init__.py` — add the import after line 66 and the registration after line 76:

```python
    from .routes.profile import profile_bp
    from .routes.voyage import voyage_bp
    from .routes.payments import payments_bp
```

```python
    app.register_blueprint(profile_bp, url_prefix="/api/profile")
    app.register_blueprint(voyage_bp, url_prefix="/api/voyage")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_voyage_routes.py -q | tail -1`
Expected: PASS — `30 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/routes/voyage.py backend/app/__init__.py backend/tests/test_voyage_routes.py
git commit -m "feat(voyage): open the voyage behind consent and an age attestation

The row cannot exist without both boxes, and both are stamped with a consent
version so a wording change stays traceable. One open voyage per user: a
second POST is a 409, and a retake only starts once the previous one is
finished, because analyses reference the old row.

GET /bank serves the cahier's text with every scoring key stripped — a test
walks the served JSON and fails on any of the ten."
```

---

### Task 9: Answers and exit tickets

Merge semantics, so a lost connection costs one scene rather than a session. Unknown ids are dropped rather than rejected — a stale client must not lose a whole save over one item that moved — but a *known* id with a bad value is a 400, and any id belonging to a locked session is a 403 before anything is written.

**Files:**
- Modify: `backend/app/routes/voyage.py` (append the two handlers and `_session_of`)
- Modify: `backend/tests/test_voyage_routes.py` (append)
- Test: `backend/tests/test_voyage_routes.py`

**Interfaces:**
- Consumes: `bank.item(item_id)`, `bank.validate_answer(item_id, value)`, `bank.billet_keys(n)`, `bank.SESSION_IDS`; `session_lock(voyage, profile, n)`; `Voyage.responses` property.
- Produces: `GET /api/voyage/responses`, `PUT /api/voyage/responses`; helper `_session_of(item_id) -> str`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_routes.py`:

```python
# ── GET / PUT /api/voyage/responses ──────────────────────────────────────────

def _open_voyage(client, auth):
    client.post("/api/voyage", json={"consent": True, "age_attested": True}, headers=auth)
    return Voyage.query.one()


def test_responses_start_empty_and_come_back_whole(client, auth):
    _open_voyage(client, auth)
    res = client.get("/api/voyage/responses", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["responses"] == {"answers": {}, "billets": {}}


def test_responses_without_a_voyage_are_a_404(client, auth):
    assert client.get("/api/voyage/responses", headers=auth).status_code == 404
    res = client.put("/api/voyage/responses", json={"answers": {}}, headers=auth)
    assert res.status_code == 404
    assert res.get_json()["error"] == "Aucun voyage en cours."


def test_a_put_merges_rather_than_replaces(client, auth):
    """Every « Suivant » saves; a lost connection must cost one scene, not the
    whole session."""
    _open_voyage(client, auth)
    client.put("/api/voyage/responses", json={"answers": {"S0-01": True}}, headers=auth)
    res = client.put("/api/voyage/responses", json={"answers": {"S0-02": False}}, headers=auth)
    assert res.status_code == 200
    assert res.get_json()["responses"]["answers"] == {"S0-01": True, "S0-02": False}


def test_a_put_returns_the_full_merged_set(client, auth):
    """So the player can reconcile after a reconnection without a second call."""
    _open_voyage(client, auth)
    client.put("/api/voyage/responses", json={"answers": _answers_for("0")}, headers=auth)
    res = client.put("/api/voyage/responses",
                     json={"billets": {"0": {"surprise": "je n'aime pas le bureau"}}},
                     headers=auth)
    body = res.get_json()["responses"]
    assert len(body["answers"]) == len(bank.items("0"))
    assert body["billets"]["0"]["surprise"] == "je n'aime pas le bureau"


def test_an_unknown_item_id_is_dropped_not_rejected(client, auth):
    _open_voyage(client, auth)
    res = client.put("/api/voyage/responses",
                     json={"answers": {"S0-01": True, "S9-99": "Z"}}, headers=auth)
    assert res.status_code == 200
    assert res.get_json()["responses"]["answers"] == {"S0-01": True}


def test_a_known_item_with_a_bad_value_is_rejected(client, auth):
    """A checklist row is a boolean and a scene is one of its own letters;
    anything else means the client and the bank have drifted."""
    _open_voyage(client, auth)
    res = client.put("/api/voyage/responses", json={"answers": {"S0-01": "oui"}}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["errors"] == ["Réponse invalide pour S0-01."]
    assert Voyage.query.one().responses["answers"] == {}


def test_billet_fields_outside_the_session_are_dropped(client, auth):
    _open_voyage(client, auth)
    res = client.put("/api/voyage/responses", json={
        "billets": {"0": {"surprise": "ok", "inventé": "x"}, "9": {"a": "b"}},
    }, headers=auth)
    assert res.status_code == 200
    billets = res.get_json()["responses"]["billets"]
    assert billets == {"0": {"surprise": "ok"}}


def test_an_empty_put_is_a_no_op(client, auth):
    _open_voyage(client, auth)
    res = client.put("/api/voyage/responses", json={}, headers=auth)
    assert res.status_code == 200
    assert res.get_json()["responses"] == {"answers": {}, "billets": {}}


def test_answers_for_a_locked_session_are_refused_before_anything_is_written(client, auth):
    _open_voyage(client, auth)
    res = client.put("/api/voyage/responses",
                     json={"answers": {"S0-01": True, "S1-1": "A"}}, headers=auth)
    assert res.status_code == 403
    assert res.get_json()["error"] == LOCK_CODE
    assert Voyage.query.one().responses["answers"] == {}


def test_the_answers_column_holds_ciphertext_after_a_real_save(client, auth):
    """The route-level half of the guarantee: what the API writes is what the
    DB export cannot read."""
    _open_voyage(client, auth)
    client.put("/api/voyage/responses", json={
        "answers": {"S0-01": True},
        "billets": {"0": {"surprise": "je déteste le bureau"}},
    }, headers=auth)
    row = _db.session.execute(_db.text("SELECT responses_encrypted FROM voyages")).first()
    assert "S0-01" not in row[0]
    assert "bureau" not in row[0]
    assert Voyage.query.one().responses["answers"]["S0-01"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_voyage_routes.py -q`
Expected: FAIL — `assert 405 == 200` in `test_responses_start_empty_and_come_back_whole` (the URL resolves to the blueprint but no `/responses` rule exists).

- [ ] **Step 3: Write minimal implementation**

Add to the imports at the top of `backend/app/routes/voyage.py`:

```python
from ..models.voyage import (
    CONSENT_VERSION,
    STATUS_EN_COURS,
    Voyage,
    session_lock,
)
```

and append the handlers:

```python
def _session_of(item_id: str) -> str:
    """"S0-01" -> "0", "S3-7" -> "3". Every bank id is S<n>-<k>."""
    return item_id[1]


@voyage_bp.get("/responses")
@jwt_required()
def get_responses():
    """The person's own answers, for resuming a session or re-rendering it."""
    voyage = _current()
    if voyage is None:
        return jsonify({"error": NO_VOYAGE}), 404
    return jsonify({"responses": voyage.responses}), 200


@voyage_bp.put("/responses")
@jwt_required()
def put_responses():
    """Merge answers and exit tickets into the voyage.

    Merge, not replace: the player saves on every « Suivant », so a lost
    connection costs one scene rather than a session. Unknown ids are dropped
    silently — a client one deploy behind must not lose a whole save over an
    item that moved — but a known id carrying a value the bank rejects is a
    400, because that means the two have genuinely drifted.
    """
    voyage = _current()
    if voyage is None:
        return jsonify({"error": NO_VOYAGE}), 404

    data = request.get_json(silent=True) or {}
    raw_answers = data.get("answers")
    raw_billets = data.get("billets")
    answers = raw_answers if isinstance(raw_answers, dict) else {}
    billets = raw_billets if isinstance(raw_billets, dict) else {}

    known = {i: v for i, v in answers.items() if bank.item(i) is not None}

    # Locks are checked over every session the request touches, before any
    # merge — a refusal must leave the row exactly as it was.
    touched = {_session_of(i) for i in known}
    touched |= {n for n in billets if n in bank.SESSION_IDS}
    profile = _profile()
    for n in sorted(touched):
        lock = session_lock(voyage, profile, n)
        if lock:
            return jsonify({"error": lock}), 403

    invalid = [
        f"Réponse invalide pour {i}."
        for i, value in sorted(known.items())
        if not bank.validate_answer(i, value)
    ]
    if invalid:
        return jsonify({"errors": invalid}), 400

    merged = voyage.responses
    merged["answers"].update(known)
    for n, fields in billets.items():
        if n not in bank.SESSION_IDS or not isinstance(fields, dict):
            continue
        allowed = set(bank.billet_keys(n))
        target = dict(merged["billets"].get(n) or {})
        for key, value in fields.items():
            if key in allowed:
                target[key] = "" if value is None else str(value)
        merged["billets"][n] = target

    voyage.responses = merged
    db.session.commit()
    return jsonify({"responses": voyage.responses}), 200
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_voyage_routes.py -q | tail -1`
Expected: PASS — `40 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/routes/voyage.py backend/tests/test_voyage_routes.py
git commit -m "feat(voyage): save answers as the player goes

Merge semantics, because the player PUTs on every « Suivant » and a dropped
connection should cost one scene. Unknown ids are dropped rather than
rejected: a client one deploy behind would otherwise lose a whole session over
an item that moved. A known id with a value the bank refuses is still a 400 —
that is real drift, not staleness — and a locked session is a 403 checked
before anything is written."
```

---

### Task 10: Completing a session

The state machine. Completing S0 flips the status to `s0_termine` and asks for the phrase; completing S5 finishes the voyage, mints the share token and asks for the portrait. Sessions 1–4 change no status. Both generation calls go through a seam so this phase ships without the generation service and phase 2 lands without touching this file.

**Files:**
- Modify: `backend/app/routes/voyage.py` (append the handler and the two seam functions)
- Modify: `backend/tests/test_voyage_routes.py` (append)
- Test: `backend/tests/test_voyage_routes.py`

**Interfaces:**
- Consumes: `scoring.missing_items(responses, n)`; `session_lock`; `generate_share_token()` (`app/utils/tokens.py:5-9`, 32 chars); `LOCK_ORDER`, `STATUS_S0`, `STATUS_TERMINE`.
- Produces: `POST /api/voyage/sessions/<n>/complete`; the seam `_spawn_micro(voyage_id)` / `_spawn_portrait(voyage_id)` in `app.routes.voyage` — **the names phase 2's tests and this phase's tests monkeypatch**, mirroring how `tests/test_unlock.py:26` patches `app.services.unlock_service.start_analysis`. Phase 2 only has to create `app/services/voyage/generation.py` with `start_micro(voyage_id, app)` / `start_portrait(voyage_id, app)` (contract § G.2); the seam then calls it with no edit here.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_routes.py`:

```python
# ── POST /api/voyage/sessions/<n>/complete ───────────────────────────────────

from unittest.mock import patch  # noqa: E402  (kept beside the tests that use it)


def _play_session_zero(client, auth):
    client.put("/api/voyage/responses", json={"answers": _answers_for("0")}, headers=auth)
    with patch("app.routes.voyage._spawn_micro") as spawn:
        res = client.post("/api/voyage/sessions/0/complete", headers=auth)
    return res, spawn


def test_an_unknown_session_is_rejected(client, auth):
    _open_voyage(client, auth)
    res = client.post("/api/voyage/sessions/9/complete", headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Session inconnue."


def test_completing_needs_every_item_of_the_session(client, auth):
    _open_voyage(client, auth)
    first, second = bank.items("0")[0]["id"], bank.items("0")[1]["id"]
    client.put("/api/voyage/responses", json={"answers": {first: True}}, headers=auth)

    res = client.post("/api/voyage/sessions/0/complete", headers=auth)
    assert res.status_code == 400
    errors = res.get_json()["errors"]
    assert errors[0] == "Réponses manquantes."
    assert second in errors[1:]
    assert first not in errors[1:]


def test_completing_session_zero_flips_the_status_and_asks_for_the_phrase(client, auth):
    _open_voyage(client, auth)
    res, spawn = _play_session_zero(client, auth)
    assert res.status_code == 200
    payload = res.get_json()["voyage"]
    assert payload["status"] == STATUS_S0
    assert payload["sessions_completed"] == ["0"]
    assert payload["micro_status"] == "generating"
    assert payload["share_token"] is None
    spawn.assert_called_once_with(Voyage.query.one().id)


def test_a_session_cannot_be_completed_twice(client, auth):
    _open_voyage(client, auth)
    _play_session_zero(client, auth)
    res = client.post("/api/voyage/sessions/0/complete", headers=auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Cette session est déjà terminée."
    assert Voyage.query.one().sessions_completed == ["0"]


def test_session_one_needs_the_code_then_the_profile(client, auth, candidate):
    _open_voyage(client, auth)
    _play_session_zero(client, auth)

    res = client.post("/api/voyage/sessions/1/complete", headers=auth)
    assert res.status_code == 403
    assert res.get_json()["error"] == LOCK_CODE

    voyage = Voyage.query.one()
    voyage.counselor_code_id = "code-1"
    _db.session.commit()
    res = client.post("/api/voyage/sessions/1/complete", headers=auth)
    assert res.status_code == 403
    assert res.get_json()["error"] == LOCK_PROFILE


def test_sessions_must_be_completed_in_order(client, auth, candidate):
    _open_voyage(client, auth)
    _play_session_zero(client, auth)
    voyage = Voyage.query.one()
    voyage.counselor_code_id = "code-1"
    _db.session.add(Profile(user_id=candidate.id, prenom="Marie", tranche_age="25_34"))
    _db.session.commit()

    client.put("/api/voyage/responses", json={"answers": _answers_for("2")}, headers=auth)
    res = client.post("/api/voyage/sessions/2/complete", headers=auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == LOCK_ORDER


def _play_to_the_end(client, auth, candidate):
    """Consent → S0 → code + profile → S1..S5. Returns the S5 response and the
    patched portrait spawn."""
    _open_voyage(client, auth)
    _play_session_zero(client, auth)
    voyage = Voyage.query.one()
    voyage.counselor_code_id = "code-1"
    _db.session.add(Profile(user_id=candidate.id, prenom="Marie", tranche_age="25_34"))
    _db.session.commit()

    for n in ("1", "2", "3", "4"):
        client.put("/api/voyage/responses", json={"answers": _answers_for(n)}, headers=auth)
        assert client.post(f"/api/voyage/sessions/{n}/complete", headers=auth).status_code == 200

    client.put("/api/voyage/responses", json={"answers": _answers_for("5")}, headers=auth)
    with patch("app.routes.voyage._spawn_portrait") as spawn:
        res = client.post("/api/voyage/sessions/5/complete", headers=auth)
    return res, spawn


def test_the_middle_sessions_change_no_status(client, auth, candidate):
    _open_voyage(client, auth)
    _play_session_zero(client, auth)
    voyage = Voyage.query.one()
    voyage.counselor_code_id = "code-1"
    _db.session.add(Profile(user_id=candidate.id, prenom="Marie", tranche_age="25_34"))
    _db.session.commit()

    client.put("/api/voyage/responses", json={"answers": _answers_for("1")}, headers=auth)
    res = client.post("/api/voyage/sessions/1/complete", headers=auth)
    assert res.status_code == 200
    payload = res.get_json()["voyage"]
    assert payload["status"] == STATUS_S0
    assert payload["sessions_completed"] == ["0", "1"]
    assert payload["portrait_status"] == "none"


def test_completing_session_five_finishes_the_voyage(client, auth, candidate):
    res, spawn = _play_to_the_end(client, auth, candidate)
    assert res.status_code == 200
    payload = res.get_json()["voyage"]
    assert payload["status"] == STATUS_TERMINE
    assert payload["sessions_completed"] == ["0", "1", "2", "3", "4", "5"]
    assert payload["completed_at"] is not None
    assert payload["portrait_status"] == "generating"
    assert len(payload["share_token"]) == 32
    spawn.assert_called_once_with(Voyage.query.one().id)


def test_completing_without_a_voyage_is_a_404(client, auth):
    res = client.post("/api/voyage/sessions/0/complete", headers=auth)
    assert res.status_code == 404
    assert res.get_json()["error"] == "Aucun voyage en cours."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_voyage_routes.py -q`
Expected: FAIL — `AttributeError: <module 'app.routes.voyage'> does not have the attribute '_spawn_micro'` (raised by `patch` in `_play_session_zero`), and `assert 404 == 400` in `test_an_unknown_session_is_rejected`.

- [ ] **Step 3: Write minimal implementation**

Extend the import block at the top of `backend/app/routes/voyage.py` — `scoring` for the missing-items check, `generate_share_token` for S5, and three more names from the model:

```python
from ..models.voyage import (
    CONSENT_VERSION,
    LOCK_ORDER,
    STATUS_EN_COURS,
    STATUS_S0,
    STATUS_TERMINE,
    Voyage,
    session_lock,
)
from ..services.voyage import bank, scoring
from ..utils.tokens import generate_share_token
```

and append:

```python
# ── generation seam ──────────────────────────────────────────────────────────
# The two spawn points live behind these two functions for two reasons: tests
# monkeypatch them by name (app.routes.voyage._spawn_micro), the way
# test_unlock.py patches app.services.unlock_service.start_analysis; and the
# import is late, so this phase ships before services/voyage/generation.py
# exists. Phase 2 creates that module with start_micro(voyage_id, app) /
# start_portrait(voyage_id, app) and nothing here changes.

def _spawn_micro(voyage_id: str) -> None:
    try:
        from ..services.voyage import generation
    except ImportError:
        current_app.logger.info("voyage: generation service absent, micro not spawned")
        return
    generation.start_micro(voyage_id, current_app._get_current_object())


def _spawn_portrait(voyage_id: str) -> None:
    try:
        from ..services.voyage import generation
    except ImportError:
        current_app.logger.info("voyage: generation service absent, portrait not spawned")
        return
    generation.start_portrait(voyage_id, current_app._get_current_object())


@voyage_bp.post("/sessions/<n>/complete")
@jwt_required()
def complete_session(n):
    """Close a session.

    Everything the session asks must be answered — the billet is optional, the
    items are not. S0 flips the status and asks for the phrase; S5 finishes the
    voyage, mints the share token the person hands to their counselor, and asks
    for the portrait. Sessions 1-4 change no status.
    """
    if n not in bank.SESSION_IDS:
        return jsonify({"error": "Session inconnue."}), 400

    voyage = _current()
    if voyage is None:
        return jsonify({"error": NO_VOYAGE}), 404

    done = list(voyage.sessions_completed or [])
    if n in done:
        return jsonify({"error": "Cette session est déjà terminée."}), 409

    lock = session_lock(voyage, _profile(), n)
    if lock == LOCK_ORDER:
        # Out of order is a state conflict, not a permission problem.
        return jsonify({"error": LOCK_ORDER}), 409
    if lock:
        return jsonify({"error": lock}), 403

    missing = scoring.missing_items(voyage.responses, n)
    if missing:
        return jsonify({"errors": ["Réponses manquantes.", *missing]}), 400

    # JSON column: reassign a new list. Appending in place leaves SQLAlchemy
    # unaware of the change (the same trap as unlock_service's dict(inputs)).
    voyage.sessions_completed = done + [n]

    spawn = None
    if n == "0":
        voyage.status = STATUS_S0
        voyage.micro_status = "generating"
        spawn = "micro"
    elif n == "5":
        voyage.status = STATUS_TERMINE
        voyage.completed_at = datetime.utcnow()
        voyage.share_token = generate_share_token()
        voyage.portrait_status = "generating"
        spawn = "portrait"

    db.session.commit()

    # After the commit: the background run re-queries the row on its own
    # connection, so it must already be there to find.
    if spawn == "micro":
        _spawn_micro(voyage.id)
    elif spawn == "portrait":
        _spawn_portrait(voyage.id)

    return jsonify({"voyage": voyage.to_dict()}), 200
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_voyage_routes.py -q | tail -1`
Expected: PASS — `49 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/routes/voyage.py backend/tests/test_voyage_routes.py
git commit -m "feat(voyage): close a session server-side

The lock is enforced here, not only on the hub: S0 is self-serve, S1-S5 need a
counselor code and a profile with prénom + tranche d'âge, and every session
needs the one before it. Out of order is a 409 because it is a state conflict;
a missing code is a 403 because it is a permission the person can go and get.

The two generation calls go through a seam so this ships without the
generation service — phase 2 adds the module and nothing here moves."
```

---

### Task 11: Unlock and the candidate's portrait

The counselor code is the free-access mechanism for Cap Emploi / Mission Locale / France Travail beneficiaries; redeeming it here is what opens S1–S5. The portrait endpoint holds the other half of the human rule: the candidate sees the six sections only once a counselor has validated them.

**Files:**
- Modify: `backend/app/routes/voyage.py` (append two handlers)
- Modify: `backend/tests/test_voyage_routes.py` (append)
- Test: `backend/tests/test_voyage_routes.py`

**Interfaces:**
- Consumes: `CounselorCode` (`app/models/counselor_code.py`), the normalisation from `analyses.unlock_with_code` (`app/routes/analyses.py:174-182`); `Voyage.portrait_sections`, `Voyage.portrait_validated_at`.
- Produces: `POST /api/voyage/unlock`, `GET /api/voyage/portrait`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_routes.py`:

```python
# ── POST /api/voyage/unlock ──────────────────────────────────────────────────

def _code(active=True, label="Cap Emploi test"):
    from app.models.counselor_code import CounselorCode
    code = CounselorCode(label=label, is_active=active)
    _db.session.add(code)
    _db.session.commit()
    return code


def test_a_valid_code_unlocks_the_later_sessions(client, auth):
    _open_voyage(client, auth)
    code = _code()
    res = client.post("/api/voyage/unlock", json={"code": code.code}, headers=auth)
    assert res.status_code == 200
    assert res.get_json()["voyage"]["has_code"] is True
    # Assert the FK the handler is supposed to write, not the absence of a key
    # to_dict() can never emit: test_to_dict_carries_exactly_twelve_keys already
    # pins the payload shape, so an absence check here passes on a broken handler.
    assert Voyage.query.one().counselor_code_id == code.id
    _db.session.refresh(code)
    assert code.uses_count == 1


def test_the_code_is_normalised_like_an_analysis_unlock(client, auth):
    _open_voyage(client, auth)
    code = _code()
    spaced = f" {code.code[:4].lower()}-{code.code[4:]} "
    assert client.post("/api/voyage/unlock", json={"code": spaced},
                       headers=auth).status_code == 200


def test_an_empty_or_unknown_or_disabled_code_is_refused(client, auth):
    _open_voyage(client, auth)
    res = client.post("/api/voyage/unlock", json={"code": "  "}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Code requis."

    res = client.post("/api/voyage/unlock", json={"code": "NOPE1234"}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Code invalide ou désactivé."

    disabled = _code(active=False, label="désactivé")
    res = client.post("/api/voyage/unlock", json={"code": disabled.code}, headers=auth)
    assert res.status_code == 400
    assert Voyage.query.one().has_code is False


def test_unlocking_twice_does_not_burn_a_second_use(client, auth):
    _open_voyage(client, auth)
    first, second = _code(), _code(label="deuxième")
    client.post("/api/voyage/unlock", json={"code": first.code}, headers=auth)
    res = client.post("/api/voyage/unlock", json={"code": second.code}, headers=auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Ce voyage est déjà débloqué."
    _db.session.refresh(second)
    assert second.uses_count == 0


def test_unlocking_without_a_voyage_is_a_404(client, auth):
    code = _code()
    res = client.post("/api/voyage/unlock", json={"code": code.code}, headers=auth)
    assert res.status_code == 404


# ── GET /api/voyage/portrait ─────────────────────────────────────────────────

def test_the_portrait_waits_for_a_counselor(client, auth, candidate):
    """Decision 9: the human step the paper protocol protects — restitution —
    stays human. A draft is not a portrait."""
    voyage = _voyage(candidate, status=STATUS_TERMINE, portrait_status="draft",
                     share_token="tok-draft")
    voyage.portrait = {"sections": {k: f"texte {k}" for k in PORTRAIT_KEYS},
                       "flags": [], "edited": False}
    _db.session.commit()

    res = client.get("/api/voyage/portrait", headers=auth)
    assert res.status_code == 409
    body = res.get_json()
    assert body["error"] == "Votre portrait est en attente de validation."
    assert body["status"] == "draft"
    assert "texte accroche" not in str(body)


def test_a_validated_portrait_is_served_with_its_six_sections(client, auth, candidate):
    voyage = _voyage(candidate, status=STATUS_TERMINE, portrait_status="validated",
                     share_token="tok-ok", portrait_validated_at=datetime(2026, 9, 12, 10, 4))
    voyage.portrait = {"sections": {k: f"texte {k}" for k in PORTRAIT_KEYS},
                       "snapshot": {"s0": {"axes": {}}}, "flags": ["vocabulaire"],
                       "edited": True}
    _db.session.commit()

    res = client.get("/api/voyage/portrait", headers=auth)
    assert res.status_code == 200
    portrait = res.get_json()["portrait"]
    assert set(portrait) == {"sections", "validated_at"}
    assert set(portrait["sections"]) == set(PORTRAIT_KEYS)
    assert portrait["validated_at"] == "2026-09-12T10:04:00"
    # The counselor's working material stays on the counselor's side.
    assert "snapshot" not in str(portrait)
    assert "vocabulaire" not in str(portrait)


def test_the_portrait_without_a_voyage_is_a_404(client, auth):
    assert client.get("/api/voyage/portrait", headers=auth).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_voyage_routes.py -q`
Expected: FAIL — `assert 404 == 200` in `test_a_valid_code_unlocks_the_later_sessions` (no `/unlock` rule).

- [ ] **Step 3: Write minimal implementation**

Replace the import block at the top of `backend/app/routes/voyage.py` with this one — `re` for the code normalisation, `CounselorCode` for the lookup:

```python
import re
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models.counselor_code import CounselorCode
from ..models.profile import Profile
from ..models.voyage import (
    CONSENT_VERSION,
    LOCK_ORDER,
    STATUS_EN_COURS,
    STATUS_S0,
    STATUS_TERMINE,
    Voyage,
    session_lock,
)
from ..services.voyage import bank, scoring
from ..utils.tokens import generate_share_token
```

then append:

```python
@voyage_bp.post("/unlock")
@jwt_required()
def unlock_voyage():
    """Redeem a counselor code: it opens S1-S5.

    Free access for Cap Emploi / Mission Locale / France Travail beneficiaries,
    the same mechanism that unlocks a paid analysis. If the voyage is ever
    sold, the gate moves to this one function.

    The « already unlocked » check runs first so a second redemption cannot
    burn a use off a second code.
    """
    voyage = _current()
    if voyage is None:
        return jsonify({"error": NO_VOYAGE}), 404
    if voyage.counselor_code_id:
        return jsonify({"error": "Ce voyage est déjà débloqué."}), 409

    data = request.get_json(silent=True) or {}
    # Accept "ABCD1234", "abcd 1234", "ABCD-1234"… — same normalisation as
    # analyses.unlock_with_code, because it is the same code on the same card.
    code_str = re.sub(r"[^A-Za-z0-9]", "", (data.get("code") or "").strip()).upper()
    if not code_str:
        return jsonify({"error": "Code requis."}), 400

    code = CounselorCode.query.filter_by(code=code_str).first()
    if not code or not code.is_active:
        return jsonify({"error": "Code invalide ou désactivé."}), 400

    voyage.counselor_code_id = code.id
    code.uses_count += 1
    db.session.commit()
    return jsonify({"voyage": voyage.to_dict()}), 200


@voyage_bp.get("/portrait")
@jwt_required()
def get_portrait():
    """The six sections — only once a counselor has validated them.

    Before that the person sees « en attente de validation » and keeps S0's
    phrase. The draft, the synthesis snapshot and the leak flags are the
    counselor's working material and never cross to this side.
    """
    voyage = _current()
    if voyage is None:
        return jsonify({"error": NO_VOYAGE}), 404
    if voyage.portrait_status != "validated":
        return jsonify({
            "error": "Votre portrait est en attente de validation.",
            "status": voyage.portrait_status,
        }), 409
    return jsonify({"portrait": {
        "sections": voyage.portrait_sections,
        "validated_at": (
            voyage.portrait_validated_at.isoformat()
            if voyage.portrait_validated_at else None
        ),
    }}), 200
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_voyage_routes.py -q | tail -1`
Expected: PASS — `57 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/routes/voyage.py backend/tests/test_voyage_routes.py
git commit -m "feat(voyage): redeem a counselor code, and hold the portrait back

Same code and same normalisation as an analysis unlock, because it is the same
card in the same hand. Redeeming twice is a 409 checked before the lookup, so
a second code cannot lose a use to it.

The portrait endpoint is the other half of the ruling: the candidate sees the
six sections only once a counselor has validated them, and never the draft,
the snapshot or the leak flags."
```

---

### Task 12: The counselor endpoints

Six handlers behind one rule the analyses side does not have: role **and** token. `/api/c/<token>` for an analysis is public by design — a counselor opens a link without an account. A synthesis sheet is a psychometric read-out, so a leaked link alone must not open it, and that difference is what the first test here pins.

**Files:**
- Modify: `backend/app/routes/voyage.py` (append the counselor block)
- Modify: `backend/tests/test_voyage_routes.py` (append)
- Test: `backend/tests/test_voyage_routes.py`

**Interfaces:**
- Consumes: `role_required("counselor", "admin")` (`app/utils/decorators.py:6-19`, which answers `{"error": "Accès non autorisé."}` with 403 and lets a missing JWT fall through to the app's 401 handler); `Voyage.by_token`, `Voyage.synthesis()`, `Voyage.portrait`, `VoyageNote`; `PORTRAIT_KEYS`.
- Produces: `GET /api/voyage/c/<token>`, `PUT /api/voyage/c/<token>/portrait`, `POST /api/voyage/c/<token>/portrait/regenerate`, `POST /api/voyage/c/<token>/validate`, `GET|PUT /api/voyage/c/<token>/notes`; helper `_counselor_portrait(voyage) -> dict` (the five-key `CounselorPortrait` shape).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_voyage_routes.py`:

```python
# ── counselor: role AND token ────────────────────────────────────────────────

@pytest.fixture
def counselor_auth(app):
    return _headers(_user("conseiller@test.fr", role="counselor"))


@pytest.fixture
def sheet(candidate):
    """A finished voyage with a portrait draft, built directly: walking six
    sessions through the API again would test the player, not the gate."""
    voyage = _voyage(
        candidate,
        status=STATUS_TERMINE,
        sessions_completed=["0", "1", "2", "3", "4", "5"],
        share_token="tok-conseiller",
        portrait_status="draft",
        completed_at=datetime.utcnow(),
    )
    voyage.responses = {"answers": _answers_for("0"), "billets": {}}
    voyage.portrait = {
        "sections": {k: f"texte {k}" for k in PORTRAIT_KEYS},
        "snapshot": {}, "flags": [], "edited": False,
        "prompt_version_id": "pv-1", "tokens_in": 10, "tokens_out": 20, "error": None,
    }
    _db.session.add(Profile(user_id=candidate.id, prenom="Marie",
                            tranche_age="25_34", situation="en_recherche"))
    _db.session.commit()
    return voyage


def test_the_sheet_is_never_reachable_by_link_alone(client, sheet, auth, counselor_auth):
    """Unlike /api/c/<token> for an analysis. Deliberate: this is a
    psychometric read-out, not a report the person already has."""
    assert client.get("/api/voyage/c/tok-conseiller").status_code == 401
    res = client.get("/api/voyage/c/tok-conseiller", headers=auth)
    assert res.status_code == 403
    assert res.get_json()["error"] == "Accès non autorisé."
    assert client.get("/api/voyage/c/tok-conseiller", headers=counselor_auth).status_code == 200


def test_an_unknown_token_is_a_404(client, counselor_auth):
    res = client.get("/api/voyage/c/nope", headers=counselor_auth)
    assert res.status_code == 404
    assert res.get_json()["error"] == "Voyage introuvable."


def test_the_sheet_carries_the_profile_the_synthesis_and_the_draft(client, sheet, counselor_auth):
    res = client.get("/api/voyage/c/tok-conseiller", headers=counselor_auth)
    body = res.get_json()["voyage"]
    assert set(body) == {"id", "status", "prenom", "tranche_age", "situation",
                         "synthesis", "portrait"}
    assert body["prenom"] == "Marie"
    assert body["synthesis"]["scoring_version"] == bank.SCORING_VERSION
    assert body["synthesis"]["s0"] is not None
    assert body["synthesis"]["riasec"] is None          # sessions 1-5 unanswered
    assert set(body["portrait"]) == {"status", "sections", "flags", "edited", "validated_at"}
    assert body["portrait"]["status"] == "draft"


def test_the_sheet_never_carries_the_generation_bookkeeping(client, sheet, counselor_auth):
    body = client.get("/api/voyage/c/tok-conseiller", headers=counselor_auth).get_data(as_text=True)
    assert "prompt_version_id" not in body
    assert "tokens_in" not in body


# ── editing, regenerating, validating ────────────────────────────────────────

def _sections(**overrides):
    sections = {k: f"nouveau {k}" for k in PORTRAIT_KEYS}
    sections.update(overrides)
    return sections


def test_editing_replaces_all_six_sections_and_marks_the_draft_edited(client, sheet, counselor_auth):
    res = client.put("/api/voyage/c/tok-conseiller/portrait",
                     json={"sections": _sections()}, headers=counselor_auth)
    assert res.status_code == 200
    portrait = res.get_json()["portrait"]
    assert portrait["edited"] is True
    assert portrait["sections"]["accroche"] == "nouveau accroche"


def test_editing_refuses_a_missing_blank_or_unknown_section(client, sheet, counselor_auth):
    res = client.put("/api/voyage/c/tok-conseiller/portrait",
                     json={"sections": _sections(accroche="   ")}, headers=counselor_auth)
    assert res.status_code == 400
    assert res.get_json()["errors"] == ["Section manquante ou vide : accroche."]

    partial = _sections()
    partial.pop("chemins")
    partial["intro"] = "x"
    res = client.put("/api/voyage/c/tok-conseiller/portrait",
                     json={"sections": partial}, headers=counselor_auth)
    assert res.status_code == 400
    errors = res.get_json()["errors"]
    assert "Section inconnue : intro." in errors
    assert "Section manquante ou vide : chemins." in errors


def test_editing_a_portrait_that_does_not_exist_yet_is_a_409(client, candidate, counselor_auth):
    _voyage(candidate, status=STATUS_TERMINE, share_token="tok-vide",
            portrait_status="generating")
    res = client.put("/api/voyage/c/tok-vide/portrait",
                     json={"sections": _sections()}, headers=counselor_auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Aucun portrait à modifier."


def test_regenerating_a_draft_spawns_the_run(client, sheet, counselor_auth):
    with patch("app.routes.voyage._spawn_portrait") as spawn:
        res = client.post("/api/voyage/c/tok-conseiller/portrait/regenerate",
                          headers=counselor_auth)
    assert res.status_code == 202
    assert res.get_json()["portrait"] == {"status": "generating", "sections": {},
                                          "flags": [], "edited": False, "validated_at": None}
    spawn.assert_called_once_with(sheet.id)
    assert Voyage.query.one().portrait_status == "generating"


def test_a_validated_portrait_is_not_regenerated(client, sheet, counselor_auth):
    client.post("/api/voyage/c/tok-conseiller/validate", headers=counselor_auth)
    res = client.post("/api/voyage/c/tok-conseiller/portrait/regenerate", headers=counselor_auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Le portrait ne peut plus être régénéré."


def test_validating_records_who_did_it(client, sheet, counselor_auth):
    res = client.post("/api/voyage/c/tok-conseiller/validate", headers=counselor_auth)
    assert res.status_code == 200
    portrait = res.get_json()["portrait"]
    assert portrait["status"] == "validated"
    assert portrait["validated_at"] is not None

    row = Voyage.query.one()
    assert row.validated_by_id is not None
    assert row.portrait_validated_at is not None


def test_a_portrait_is_validated_once(client, sheet, counselor_auth):
    client.post("/api/voyage/c/tok-conseiller/validate", headers=counselor_auth)
    res = client.post("/api/voyage/c/tok-conseiller/validate", headers=counselor_auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Aucun portrait à valider."


def test_validation_is_what_opens_the_candidate_endpoint(client, sheet, auth, counselor_auth):
    assert client.get("/api/voyage/portrait", headers=auth).status_code == 409
    client.post("/api/voyage/c/tok-conseiller/validate", headers=counselor_auth)
    res = client.get("/api/voyage/portrait", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["portrait"]["sections"]["accroche"] == "texte accroche"


def test_an_edit_is_still_allowed_after_validation(client, sheet, counselor_auth):
    """A correction made during the restitution session must not require
    un-validating the portrait in front of the person."""
    client.post("/api/voyage/c/tok-conseiller/validate", headers=counselor_auth)
    res = client.put("/api/voyage/c/tok-conseiller/portrait",
                     json={"sections": _sections()}, headers=counselor_auth)
    assert res.status_code == 200
    assert res.get_json()["portrait"]["status"] == "validated"


# ── private notes ────────────────────────────────────────────────────────────

def test_notes_start_empty_and_upsert(client, sheet, counselor_auth):
    assert client.get("/api/voyage/c/tok-conseiller/notes",
                      headers=counselor_auth).get_json()["note"] is None

    res = client.put("/api/voyage/c/tok-conseiller/notes",
                     json={"body": "à revoir en RDV 2"}, headers=counselor_auth)
    assert res.status_code == 200
    assert res.get_json()["note"]["body"] == "à revoir en RDV 2"

    res = client.put("/api/voyage/c/tok-conseiller/notes",
                     json={"body": ""}, headers=counselor_auth)
    assert res.get_json()["note"]["body"] == ""
    assert VoyageNote.query.count() == 1


def test_a_note_belongs_to_the_counselor_who_wrote_it(client, sheet, counselor_auth, app):
    client.put("/api/voyage/c/tok-conseiller/notes",
               json={"body": "note A"}, headers=counselor_auth)
    other = _headers(_user("conseiller-2@test.fr", role="counselor"))
    assert client.get("/api/voyage/c/tok-conseiller/notes",
                      headers=other).get_json()["note"] is None
    client.put("/api/voyage/c/tok-conseiller/notes", json={"body": "note B"}, headers=other)
    assert VoyageNote.query.count() == 2


def test_a_candidate_cannot_read_counselor_notes(client, sheet, auth):
    assert client.get("/api/voyage/c/tok-conseiller/notes", headers=auth).status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_voyage_routes.py -q`
Expected: FAIL — `assert 404 == 401` in `test_the_sheet_is_never_reachable_by_link_alone` (no `/c/<token>` rule exists, so Flask answers 404 before any auth check).

- [ ] **Step 3: Write minimal implementation**

Replace the import block at the top of `backend/app/routes/voyage.py` with its final form — `PORTRAIT_KEYS` and `VoyageNote` for the portrait and the notes, `role_required` for the gate:

```python
import re
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models.counselor_code import CounselorCode
from ..models.profile import Profile
from ..models.voyage import (
    CONSENT_VERSION,
    LOCK_ORDER,
    PORTRAIT_KEYS,
    STATUS_EN_COURS,
    STATUS_S0,
    STATUS_TERMINE,
    Voyage,
    VoyageNote,
    session_lock,
)
from ..services.voyage import bank, scoring
from ..utils.decorators import role_required
from ..utils.tokens import generate_share_token
```

then append:

```python
# ── counselor ────────────────────────────────────────────────────────────────
# Role AND token. /api/c/<token> for an analysis is public by design — a
# counselor opens the link without an account. The synthesis sheet is a
# psychometric read-out, so a leaked link alone must not open it.

NOT_FOUND = "Voyage introuvable."


def _counselor_portrait(voyage: Voyage) -> dict:
    """The five-key shape every counselor portrait response returns.

    Deliberately narrow: the snapshot, the token counts, the prompt version and
    the stored error stay inside the ciphertext where they were written.
    """
    payload = voyage.portrait or {}
    sections = payload.get("sections") or {}
    return {
        "status": voyage.portrait_status,
        "sections": {k: v for k, v in sections.items() if k in PORTRAIT_KEYS},
        "flags": list(payload.get("flags") or []),
        "edited": bool(payload.get("edited")),
        "validated_at": (
            voyage.portrait_validated_at.isoformat()
            if voyage.portrait_validated_at else None
        ),
    }


@voyage_bp.get("/c/<token>")
@role_required("counselor", "admin")
def counselor_sheet(token):
    """The page-18 synthesis sheet plus the portrait draft.

    The synthesis is recomputed from the answers on every read, so a corrected
    scoring table takes effect without a migration. The 5-phase restitution
    guide is static frontend content and is not served here.
    """
    voyage = Voyage.by_token(token)
    if voyage is None:
        return jsonify({"error": NOT_FOUND}), 404

    profile = Profile.query.filter_by(user_id=voyage.user_id).first()
    return jsonify({"voyage": {
        "id": voyage.id,
        "status": voyage.status,
        "prenom": getattr(profile, "prenom", None),
        "tranche_age": getattr(profile, "tranche_age", None),
        "situation": getattr(profile, "situation", None),
        "synthesis": voyage.synthesis(),
        "portrait": _counselor_portrait(voyage),
    }}), 200


@voyage_bp.put("/c/<token>/portrait")
@role_required("counselor", "admin")
def counselor_edit_portrait(token):
    """Replace all six sections. Allowed while draft or validated — a
    correction made during the restitution session must not force the
    counselor to un-validate the portrait in front of the person."""
    voyage = Voyage.by_token(token)
    if voyage is None:
        return jsonify({"error": NOT_FOUND}), 404
    if voyage.portrait_status not in ("draft", "validated"):
        return jsonify({"error": "Aucun portrait à modifier."}), 409

    data = request.get_json(silent=True) or {}
    raw = data.get("sections")
    sections = raw if isinstance(raw, dict) else {}

    errors = [f"Section inconnue : {key}." for key in sorted(sections)
              if key not in PORTRAIT_KEYS]
    errors += [f"Section manquante ou vide : {key}." for key in PORTRAIT_KEYS
               if not str(sections.get(key) or "").strip()]
    if errors:
        return jsonify({"errors": errors}), 400

    payload = dict(voyage.portrait or {})
    payload["sections"] = {key: str(sections[key]).strip() for key in PORTRAIT_KEYS}
    payload["edited"] = True
    voyage.portrait = payload
    db.session.commit()
    return jsonify({"portrait": _counselor_portrait(voyage)}), 200


@voyage_bp.post("/c/<token>/portrait/regenerate")
@role_required("counselor", "admin")
def counselor_regenerate_portrait(token):
    """Re-run the portrait call. Draft only: a validated portrait has been
    restituted and must not change under the person's feet."""
    voyage = Voyage.by_token(token)
    if voyage is None:
        return jsonify({"error": NOT_FOUND}), 404
    if voyage.portrait_status != "draft":
        return jsonify({"error": "Le portrait ne peut plus être régénéré."}), 409

    voyage.portrait_status = "generating"
    db.session.commit()
    _spawn_portrait(voyage.id)
    # The stored sections are about to be overwritten, so the response reports
    # the run rather than the text that is on its way out.
    return jsonify({"portrait": {
        "status": "generating", "sections": {}, "flags": [],
        "edited": False, "validated_at": None,
    }}), 202


@voyage_bp.post("/c/<token>/validate")
@role_required("counselor", "admin")
def counselor_validate_portrait(token):
    """« Valider et transmettre » — the step that opens the portrait to the
    candidate. Who did it and when are both recorded."""
    voyage = Voyage.by_token(token)
    if voyage is None:
        return jsonify({"error": NOT_FOUND}), 404
    if voyage.portrait_status != "draft":
        return jsonify({"error": "Aucun portrait à valider."}), 409

    voyage.portrait_status = "validated"
    voyage.portrait_validated_at = datetime.utcnow()
    voyage.validated_by_id = get_jwt_identity()
    db.session.commit()
    return jsonify({"portrait": _counselor_portrait(voyage)}), 200


@voyage_bp.get("/c/<token>/notes")
@role_required("counselor", "admin")
def get_voyage_note(token):
    """This counselor's own note. Never shown to the candidate."""
    voyage = Voyage.by_token(token)
    if voyage is None:
        return jsonify({"error": NOT_FOUND}), 404
    note = VoyageNote.query.filter_by(
        voyage_id=voyage.id, counselor_id=get_jwt_identity()
    ).first()
    return jsonify({"note": note.to_dict() if note else None}), 200


@voyage_bp.put("/c/<token>/notes")
@role_required("counselor", "admin")
def upsert_voyage_note(token):
    voyage = Voyage.by_token(token)
    if voyage is None:
        return jsonify({"error": NOT_FOUND}), 404

    counselor_id = get_jwt_identity()
    note = VoyageNote.query.filter_by(voyage_id=voyage.id, counselor_id=counselor_id).first()
    if note is None:
        note = VoyageNote(voyage_id=voyage.id, counselor_id=counselor_id)
        db.session.add(note)
    # "" is a valid body: it clears the note without deleting the row.
    note.body = (request.get_json(silent=True) or {}).get("body", "")
    db.session.commit()
    return jsonify({"note": note.to_dict()}), 200
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_voyage_routes.py -q | tail -1`
Expected: PASS — `73 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/routes/voyage.py backend/tests/test_voyage_routes.py
git commit -m "feat(voyage): give the counselor the sheet, the draft and the pen

Role and token, not token alone. /api/c/<token> for an analysis is public
because a counselor opens the link without an account and the report is
something the person already has; a synthesis sheet is a psychometric
read-out, so a forwarded link must not be enough. A test pins the difference.

The synthesis is recomputed on every read rather than stored, so a corrected
scoring table takes effect without touching a row. Validation is what opens
the portrait to the candidate, and it records who did it."
```

---

### Task 13: The admin role endpoint and the voyage KPIs

Nothing in the product can grant the `counselor` role today, so nobody could validate a portrait — the feature would ship with its last step unreachable. The KPI block is four counts on a model that already exists, and the admin dashboard's tile lands in a later phase.

**Files:**
- Modify: `backend/app/routes/admin.py:1-12` (imports), `backend/app/routes/admin.py:47-59` (the stats payload), `backend/app/routes/admin.py:106-110` (append the new handler after `list_users`)
- Modify: `backend/tests/test_admin.py` (append)
- Test: `backend/tests/test_admin.py`

**Interfaces:**
- Consumes: `admin_required` (`app/utils/decorators.py:22-23`), `User.to_dict()` (`app/models/user.py:28-36`), `Voyage`, `STATUS_S0`, `STATUS_TERMINE`.
- Produces: `PUT /api/admin/users/<user_id>/role`; `GET /api/admin/stats` key `voyages: {started, s0_done, completed, validated}`; module constant `ROLES = ("candidate", "counselor", "admin")`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_admin.py`:

```python
# ── roles ────────────────────────────────────────────────────────────────────

from app.models.user import User  # noqa: E402
from app.models.voyage import STATUS_S0, STATUS_TERMINE, Voyage  # noqa: E402
from datetime import datetime as _dt  # noqa: E402


def _plain_user(email="candidat@test.fr", role="candidate"):
    user = User(email=email, password_hash="x", role=role)
    _db.session.add(user)
    _db.session.commit()
    return user


def test_an_admin_can_grant_the_counselor_role(client, admin_headers, app):
    """Without this nobody can validate a voyage portrait, and the feature
    ships with its last step unreachable."""
    user = _plain_user()
    res = client.put(f"/api/admin/users/{user.id}/role",
                     json={"role": "counselor"}, headers=admin_headers)
    assert res.status_code == 200
    assert res.get_json()["user"]["role"] == "counselor"
    assert _db.session.get(User, user.id).role == "counselor"


def test_an_unknown_role_is_refused(client, admin_headers, app):
    user = _plain_user("autre@test.fr")
    res = client.put(f"/api/admin/users/{user.id}/role",
                     json={"role": "superviseur"}, headers=admin_headers)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Rôle invalide."
    assert _db.session.get(User, user.id).role == "candidate"


def test_an_unknown_user_is_a_404(client, admin_headers):
    assert client.put("/api/admin/users/nobody/role",
                      json={"role": "counselor"}, headers=admin_headers).status_code == 404


def test_the_last_admin_cannot_demote_itself(client, admin_headers, app):
    """Locking every admin out of the dashboard is not recoverable from the UI."""
    last_admin = User.query.filter_by(role="admin").one()
    res = client.put(f"/api/admin/users/{last_admin.id}/role",
                     json={"role": "candidate"}, headers=admin_headers)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Impossible de retirer le dernier rôle administrateur."
    assert _db.session.get(User, last_admin.id).role == "admin"


def test_an_admin_can_be_demoted_once_another_one_exists(client, admin_headers, app):
    first = User.query.filter_by(role="admin").one()
    _plain_user("admin-2@test.fr", role="admin")
    res = client.put(f"/api/admin/users/{first.id}/role",
                     json={"role": "counselor"}, headers=admin_headers)
    assert res.status_code == 200
    # Status alone would pass on a handler that returns 200 without committing.
    assert res.get_json()["user"]["role"] == "counselor"
    assert _db.session.get(User, first.id).role == "counselor"


def test_the_role_endpoint_is_admin_only(client, app):
    from flask_jwt_extended import create_access_token
    user = _plain_user("pas-admin@test.fr")
    token = create_access_token(identity=str(user.id), additional_claims={"role": "candidate"})
    res = client.put(f"/api/admin/users/{user.id}/role", json={"role": "admin"},
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


# ── voyage KPIs ──────────────────────────────────────────────────────────────

def _voyage_row(user, **overrides):
    fields = {"user_id": user.id, "status": "en_cours", "sessions_completed": [],
              "consent_at": _dt.utcnow(), "consent_version": "voyage-v1",
              "age_attested": True}
    fields.update(overrides)
    row = Voyage(**fields)
    _db.session.add(row)
    _db.session.commit()
    return row


def test_stats_counts_voyages_by_stage(client, admin_headers, app):
    user = _plain_user("kpi@test.fr")
    _voyage_row(user)
    _voyage_row(user, status=STATUS_S0)
    _voyage_row(user, status=STATUS_TERMINE, share_token="kpi-1")
    _voyage_row(user, status=STATUS_TERMINE, share_token="kpi-2",
                portrait_status="validated")

    stats = client.get("/api/admin/stats", headers=admin_headers).get_json()
    assert stats["voyages"] == {"started": 4, "s0_done": 3, "completed": 2, "validated": 1}


def test_stats_reports_zeros_rather_than_omitting_the_block(client, admin_headers):
    stats = client.get("/api/admin/stats", headers=admin_headers).get_json()
    assert stats["voyages"] == {"started": 0, "s0_done": 0, "completed": 0, "validated": 0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_admin.py -q`
Expected: FAIL — `assert 404 == 200` in `test_an_admin_can_grant_the_counselor_role`, and `KeyError: 'voyages'` in `test_stats_reports_zeros_rather_than_omitting_the_block`.

- [ ] **Step 3: Write minimal implementation**

Add to the imports at the top of `backend/app/routes/admin.py`:

```python
from ..models.voyage import STATUS_S0, STATUS_TERMINE, Voyage
```

and a module constant under the blueprint definition:

```python
# The three values User.role may hold. PUT /users/<id>/role is the only way to
# change one: without it nobody can be made a counselor, and nobody can
# validate a voyage portrait.
ROLES = ("candidate", "counselor", "admin")
```

In `stats()`, build the block before the return and add one key to the payload (after `"active_prompt"`, line 58):

```python
    voyages = {
        "started": Voyage.query.count(),
        # A voyage past S0 is either s0_termine or termine — the status
        # carries what "0" in sessions_completed says, without a JSON read.
        "s0_done": Voyage.query.filter(Voyage.status.in_((STATUS_S0, STATUS_TERMINE))).count(),
        "completed": Voyage.query.filter_by(status=STATUS_TERMINE).count(),
        "validated": Voyage.query.filter_by(portrait_status="validated").count(),
    }
```

```python
            "active_prompt": by_path.get(registry.DEFAULT_PARCOURS),
            "voyages": voyages,
        }), 200
```

Then append the handler after `list_users` (line 110):

```python
@admin_bp.put("/users/<user_id>/role")
@admin_required
def set_user_role(user_id):
    """Grant or revoke a role.

    The only way to make a counselor, and therefore the only way anyone can
    ever validate a voyage portrait. Demoting the last admin is refused: it
    locks every admin out of the dashboard, and nothing in the UI recovers
    from that.
    """
    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "").strip()
    if role not in ROLES:
        return jsonify({"error": "Rôle invalide."}), 400

    user = User.query.get_or_404(user_id)
    if user.role == "admin" and role != "admin":
        others = User.query.filter(User.role == "admin", User.id != user.id).count()
        if others == 0:
            return jsonify({
                "error": "Impossible de retirer le dernier rôle administrateur."
            }), 409

    user.role = role
    db.session.commit()
    return jsonify({"user": user.to_dict()}), 200
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest tests/test_admin.py -q | tail -1`
Expected: PASS — `22 passed` (14 before this task, 8 added).

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/routes/admin.py backend/tests/test_admin.py
git commit -m "feat(admin): let an admin grant the counselor role

Nothing in the product could grant it, so the voyage would have shipped with
its last step — a counselor validating a portrait — unreachable. Demoting the
last admin is a 409: it locks everyone out of the dashboard and no screen
recovers from that.

GET /stats gains the four voyage counts off the same model, so whichever phase
renders the KPI row has them waiting."
```

---

### Task 14: Phase verification

Phase 1 ships on its own: the API is complete and testable, the schema is migrated, and no UI or AI work is required to deploy it. This task proves it before the push that deploys it.

**Files:**
- Modify: none — verification only.

**Interfaces:**
- Consumes: everything above.
- Produces: a green suite, a rehearsed migration chain, and the phase-1 commit history.

- [ ] **Step 1: Run the full backend suite**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/pytest -q | tail -1`
Expected: `330 passed` — the 232 that passed before this phase, plus 14 in the new `test_prompt_slots.py`, 3 added to `test_analysis_model.py`, 8 added to `test_admin.py` and 73 in the new `test_voyage_routes.py`. Any `F` or `E` is a blocker: this branch deploys on push.

- [ ] **Step 2: Rehearse the whole migration chain, up and down**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend
rm -f /tmp/voyage-mig.db
export DATABASE_URL="sqlite:////tmp/voyage-mig.db" FLASK_APP=run.py
./venv/bin/flask db upgrade 2>&1 | grep -c "Running upgrade"
./venv/bin/flask db current 2>&1 | tail -1
./venv/bin/flask db downgrade base 2>&1 | grep -c "Running downgrade"
./venv/bin/flask db upgrade 2>&1 | grep -c "Running upgrade"
unset DATABASE_URL
rm -f /tmp/voyage-mig.db
```
Expected: `16`, then `f2a3b4c5d6e7 (head)`, then `16`, then `16`. Sixteen is the twelve pre-existing revisions plus this phase's four.

- [ ] **Step 3: Check the API surface is what the contract pinned**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend
./venv/bin/python -c "
from app import create_app
app = create_app('testing')
rules = sorted((r.rule, ','.join(sorted(r.methods - {'HEAD', 'OPTIONS'})))
               for r in app.url_map.iter_rules() if r.rule.startswith('/api/voyage'))
for rule, methods in rules: print(f'{methods:12} {rule}')
print(len(rules), 'paths')
"
```
Expected — these eleven lines, in this order (the script sorts by rule), and nothing else:
```
DELETE,GET,POST /api/voyage
GET          /api/voyage/bank
GET          /api/voyage/c/<token>
GET,PUT      /api/voyage/c/<token>/notes
PUT          /api/voyage/c/<token>/portrait
POST         /api/voyage/c/<token>/portrait/regenerate
POST         /api/voyage/c/<token>/validate
GET          /api/voyage/portrait
GET,PUT      /api/voyage/responses
POST         /api/voyage/sessions/<n>/complete
POST         /api/voyage/unlock
11 paths
```
Eleven rules under the prefix; the twelfth pinned path, `PUT /api/admin/users/<user_id>/role`, lives on the admin blueprint. Fifteen handlers here plus that one is the sixteen the contract § E pins. (Column alignment shifts on the `DELETE,GET,POST` line — the padding is 12 characters and that string is longer. Only the pairs matter.)

- [ ] **Step 4: Confirm nothing sensitive is reachable**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend
./venv/bin/pytest -q \
  "tests/test_voyage_routes.py::test_columns_hold_ciphertext_not_plaintext" \
  "tests/test_voyage_routes.py::test_the_answers_column_holds_ciphertext_after_a_real_save" \
  "tests/test_voyage_routes.py::test_to_dict_carries_exactly_twelve_keys" \
  "tests/test_voyage_routes.py::test_the_bank_serves_text_and_no_weights" \
  "tests/test_voyage_routes.py::test_the_sheet_is_never_reachable_by_link_alone" \
  "tests/test_voyage_routes.py::test_the_portrait_waits_for_a_counselor" \
  | tail -1
```
Expected: `6 passed` — the five privacy guarantees this phase owes, named one by one: answers are ciphertext at rest (twice: at the model and after a real save through the API), `to_dict()` is capped at twelve keys, the bank ships no weights, the synthesis sheet is unreachable by link alone, and the portrait stays shut until a counselor validates it.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git status --short
git log --oneline -13
```
Expected: a clean tree apart from files that were already untracked before this phase (`AUTOMATION-PLAN.md`, the PDFs, the docs), and thirteen new commits from Tasks 1–13. There is nothing to commit in this task; if `git status` shows a modified tracked file, it belongs to one of the tasks above and must be committed there — every commit on `initial` deploys, so a stray edit deploys with it.

---

## What phase 1 hands to the phases after it

| Consumer | Name it uses | Where it comes from |
|---|---|---|
| Phase 2 (generation) | `prompt_slots.VOYAGE_MICRO`, `VOYAGE_PORTRAIT`, `is_valid`, `label`, `choices` | `app/services/prompt_slots.py` |
| Phase 2 | `app.routes.voyage._spawn_micro` / `_spawn_portrait` already call `generation.start_micro(voyage_id, app)` / `start_portrait(voyage_id, app)` — creating `app/services/voyage/generation.py` is the whole wiring | `app/routes/voyage.py` |
| Phase 2 | `Voyage.micro` / `Voyage.portrait` setters, `micro_status` / `portrait_status`, `PORTRAIT_KEYS` | `app/models/voyage.py` |
| Phase 2 | `tests/test_seed_scripts.py` reads a whole slot name — add the two seeds to its `SEEDS` map when they exist | `tests/test_seed_scripts.py` |
| Phases 3–4 (UI) | `GET /api/voyage`, `/bank`, `/responses`, `/sessions/<n>/complete`, `/unlock`, `/portrait`, `/c/<token>*`; `LOCK_CODE` / `LOCK_PROFILE` / `LOCK_ORDER` for `frontend/src/types/voyage.ts` and `test_voyage_parity.py` | `app/routes/voyage.py`, `app/models/voyage.py` |
| Phase 5 (injection) | `Voyage.for_prompt(user_id)`, `Voyage.synthesis()`, `Voyage.micro_phrase`, `Analysis.voyage_id` | `app/models/voyage.py`, `app/models/analysis.py` |

Left undone on purpose, and owned elsewhere: `scoring.prompt_context()` and the `_voyage` block (phase 5), the two seed scripts and the leak check (phase 2), `frontend/src/types/voyage.ts` and every page (phases 3–4), `TEST-PLAN.md § 10` and the `CLAUDE.md` voyage section (phase 5).

## Interim states this phase deploys with, deliberately

- **`micro_status` / `portrait_status` sit at `generating`.** Until phase 2 lands `app/services/voyage/generation.py`, the seam logs one line and returns. No candidate can reach it: the spec's phase table makes phase 1 API-only and `/voyage` does not exist in the frontend before phase 3. Phase 2 needs no edit here.
- **`analyses.voyage_id` is always null.** The column and the `to_dict()` key ship now so phase 5 is a two-line fold rather than a migration; nothing reads it yet.
- **No prompt exists for either voyage slot.** `POST /api/prompts` accepts them from Task 7; the seeds arrive in phase 2. A generation attempt before then would set `*_status = "error"` with « Aucun prompt actif pour le slot … » — which is phase 2's contract (§ G.2 step 2), not a phase-1 bug.
