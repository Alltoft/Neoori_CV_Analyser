# Retire parcours 2 and 3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove parcours 2 « Je cherche ma direction » and parcours 3 « Je pars de zéro » from the code, the copy, the prompts and the production data, plus the leftovers of the retired Vercel/Render/TiDB hosting. Parcours 1 and le voyage stay as they are.

**Architecture:** The section registry keeps its shape with a single parcours ("1"). The server stamps every new analysis `_path: "1"`, and any other stored value reads as parcours 1. A temporary script, dry-run first, deletes the P2/P3 rows and prompts after the deploy. No schema migration.

**Tech Stack:** Flask 3 + SQLAlchemy 2.0 (pytest on SQLite with foreign keys enforced), Next.js 16.2 App Router + TypeScript, MySQL 8.4 in production.

**Spec:** `docs/superpowers/specs/2026-10-08-remove-parcours-2-3-design.md`

## Global Constraints

- **Where to work.** Only in the worktree `WT=/Users/imran/Downloads/design_handoff_cv_analyzer/.claude/worktrees/remove-parcours`, on branch `feat/remove-parcours-2-3` (cut from `initial`). Never touch the main checkout, which holds `feat/social-sign-in`.
- **Backend tests.**
  - The worktree has no venv. Run `PY=/Users/imran/Downloads/design_handoff_cv_analyzer/backend/venv/bin/python` as `$PY -m pytest` from `$WT/backend`.
  - Baseline before Task 1: **1201 passed**.
- **Frontend checks.**
  - Run from `$WT/frontend`, after the `npm ci` in Task 2, Step 1: `npx tsc --noEmit`, `npm run lint`, `npm run build`.
  - `frontend/AGENTS.md` applies: read the guide in `node_modules/next/dist/docs/` before using any Next.js API.
- **Language.** UI copy is French; code comments and commit messages are English.
- **Copy.** The spec's copy table is approved verbatim — no other wording change. These words are banned from UI copy: boussole, copilote, miroir, révélation, épanouissement, alignement, excellence, talent unique, vous vous démarquez.
- **Apostrophes.** Keep each file's style:
  - `’` (U+2019) in `app/page.tsx` and `AuthLayout.tsx`;
  - ASCII `'` in `app/layout.tsx`;
  - `&apos;` in the legal pages.
  - Guillemets « » in these files use plain spaces.
- **Migrations.** No schema migration. Never edit or delete a migration: `c3d4e5f6a7b8` and `a7b8c9d0e1f2` sit mid-chain.
- **Kept on purpose.** The legacy `_path` "A" → "1" mapping, and `pool_pre_ping`.
- **Commits.** One per task, conventional message, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **STOP gates.** Never do any of these without the developer's explicit go for that step: push, merge into `initial`, deploy, SSH to the VPS, run anything against production, or start/stop the shared dev Docker stack. Tasks 7–9 mark each gate with **STOP**.

## Review Focus

1. **A stale browser tab** still showing the old P2/P3 form posts `_path: "2"` or `"3"` with P2/P3 fields after the deploy. Expected: a 400 with parcours 1's French errors, no run started, never a 500. (Test: Task 1.)
2. **Leftover P2/P3/"B" rows read before the purge** — the report page, the `/espace` list, `/api/c/<token>`. Expected: served as parcours 1, never a 500 or `KeyError`. (Test: Task 2.)
3. **An admin publishing to a retired slot** ("2", "3", "B", with `activate: true`). Expected: a 400, with the live parcours 1 prompt still active and unchanged. (Test: Task 2.)
4. **The purge meeting inconsistent data** — a kept analysis pointing at a prompt marked for deletion. Expected: the run aborts and nothing is deleted. (Test: Task 3.)
5. **Odd `_path` values in the purge** — `" 2"`, the integer `2`, `["2"]`, `"b"`. Expected: only what the old code really treated as P2/P3 is deleted; a parcours 1 row never is. (Test: Task 3.)

---

### Task 1: New analyses are always parcours 1

**Files:**
- Modify: `backend/app/routes/analyses.py`
- Modify: `backend/app/services/anthropic_service.py`
- Modify: `backend/tests/test_parcours_inputs.py`
- Modify: `backend/tests/test_voyage_prompt_context.py`
- Modify: `CLAUDE.md` (section « What reaches an analysis »)
- Modify: `docs/superpowers/specs/2026-09-09-voyage-design.md`, `docs/superpowers/plans/2026-09-09-voyage-contracts.md` (one dated note each)

**Interfaces:**
- Consumes (existing):
  - `registry.DEFAULT_PARCOURS == "1"`
  - `_validate_inputs(inputs: dict) -> list[str]`
  - `_format_user_message_p1(inputs: dict) -> str`
- Produces:
  - `create_analysis` always stores `_path == "1"`. `save_draft` stores "1" when the body carries a `_path`, and stores nothing otherwise.
  - Gone: `VALIDATORS`, `_missing`, `_validate_inputs_p2`, `_validate_inputs_p3`, `_format_user_message_p2`, `_format_user_message_p3`, `_FORMATTERS`.
  - `_format_user_message(inputs)` always returns the parcours 1 message.

- [ ] **Step 1: Write the failing tests in `backend/tests/test_parcours_inputs.py`**

1. Line 1: replace `"""Per-parcours message formatting and validation."""` with `"""Parcours 1 — message formatting and validation."""`.
2. Replace `from app.routes.analyses import VALIDATORS` with `from app.routes.analyses import _validate_inputs`.
3. Replace every `VALIDATORS["1"](` with `_validate_inputs(`. There are 5 occurrences; `grep -c 'VALIDATORS\["1"\]'` before = 5, after = 0.
4. Delete these 8 tests entirely:
   - `test_p2_asks_three_questions_not_four`
   - `test_p3_runs_off_the_life_questionnaire`
   - `test_p3_accepts_an_optional_partial_cv`
   - `test_p2_requires_a_cv_and_all_three_answers`
   - `test_p2_accepts_a_complete_submission`
   - `test_p3_needs_no_cv`
   - `test_p3_thresholds_are_lower_than_p2`
   - `test_create_leaves_parcours_2_and_3_without_a_chemin`
5. Replace the whole `test_legacy_path_codes_still_format` function with:

```python
@pytest.mark.parametrize("stored", ["1", "A", "2", "3", "B", None])
def test_every_stored_path_builds_the_parcours_1_message(stored):
    """Rows written before the migration carry 'A'; a retired '2', '3' or 'B'
    row still in the database before the purge reads as parcours 1 too."""
    inputs = {"cv_text": "x", "cible_visee": "y"}
    if stored is not None:
        inputs["_path"] = stored
    assert "--- CV DU CANDIDAT ---" in _format_user_message(inputs)
```

6. Append at the end of the file:

```python
# ── parcours 2 and 3 are retired: every new analysis is parcours 1 ───────────

P1_TARGET = "Chargé de recrutement dans une PME industrielle du bassin lyonnais"


@pytest.mark.parametrize("posted", ["2", "3", "B", "b", ["2"], None])
def test_create_stamps_parcours_1_whatever_the_body_says(posted, app, client, candidate_headers):
    """The stored id is the server's: a stale page posting a retired parcours
    still gets a parcours 1 analysis, with its chemin."""
    from unittest.mock import patch

    inputs = {"cv_text": "c" * 300, "cible_visee": P1_TARGET}
    if posted is not None:
        inputs["_path"] = posted
    with patch("app.routes.analyses.start_analysis"):
        res = client.post("/api/analyses/", json={"inputs": inputs}, headers=candidate_headers)
    assert res.status_code == 201, res.data
    stored = json.loads(res.data)["analysis"]["inputs"]
    assert stored["_path"] == "1"
    assert stored["_chemin"] == "A"


def test_a_stale_parcours_3_form_gets_the_parcours_1_errors(app, client, candidate_headers):
    """Review Focus 1. The old P3 form sent no CV and no target: it now meets
    parcours 1's validation — a 400 in French, no run, never a 500."""
    from unittest.mock import patch

    with patch("app.routes.analyses.start_analysis") as start:
        res = client.post("/api/analyses/", json={"inputs": {
            "_path": "3",
            "experiences": "bénévolat au club de foot pendant six ans",
            "aime_faire": "organiser, réparer des choses",
            "refus": "le travail de nuit",
            "contraintes": "pas de permis",
            "bon_travail": "une équipe, dehors",
        }}, headers=candidate_headers)
    assert res.status_code == 400
    assert json.loads(res.data)["errors"] == [
        "CV trop court (minimum 200 caractères).",
        "Cible visée trop courte (minimum 50 caractères).",
    ]
    start.assert_not_called()


@pytest.mark.parametrize("posted", ["2", "3", "B"])
def test_a_draft_carrying_a_retired_parcours_is_stamped_1(posted, app, client, candidate_headers):
    res = client.post("/api/analyses/draft", json={"inputs": {"_path": posted, "cv_text": "x"}},
                      headers=candidate_headers)
    assert res.status_code == 201, res.data
    assert json.loads(res.data)["analysis"]["inputs"]["_path"] == "1"


def test_a_draft_without_a_parcours_stays_without_one(app, client, candidate_headers):
    """An absent _path already means parcours 1; test_malformed_bodies.py also
    pins that an empty draft stays {}."""
    res = client.post("/api/analyses/draft", json={"inputs": {"cv_text": "x"}},
                      headers=candidate_headers)
    assert res.status_code == 201, res.data
    assert "_path" not in json.loads(res.data)["analysis"]["inputs"]
```

- [ ] **Step 2: Update `backend/tests/test_voyage_prompt_context.py`**

1. In the import from `app.services.anthropic_service`, delete the two lines `_format_user_message_p2,` and `_format_user_message_p3,`.
2. Delete the `P2 = {...}` and `P3 = {...}` dict literals (the 5 lines after `P1 = {...}`). Change the comment above `P1` from `# The minimum each parcours' formatter needs to produce a message.` to `# The minimum the parcours 1 formatter needs to produce a message.`
3. Replace both parametrized tests, from the first `@pytest.mark.parametrize("formatter, inputs", [` through the end of `test_no_parcours_carries_the_block_without_a_voyage`, with:

```python
def test_the_analysis_message_carries_the_block():
    """The block is appended by _common_tail, so it closes the message
    whatever else the inputs carry."""
    msg = _format_user_message_p1({**P1, "_voyage": S0_LINES})
    assert VOYAGE_HEADER in msg
    for line in S0_LINES:
        assert line in msg


def test_no_block_without_a_voyage():
    assert VOYAGE_HEADER not in _format_user_message_p1(P1)
```

4. In `test_a_legacy_path_code_still_gets_the_block`:
   - change the docstring to `"""Analyses written before the parcours migration carry '_path': 'A'."""`;
   - delete the second `assert` (the one with `"_path": "B"`).
5. In the module docstring, replace:

```
  anthropic_service._voyage_block() those lines -> one block in every parcours
                                    message
```
with
```
  anthropic_service._voyage_block() those lines -> one block in the analysis
                                    message
```
and replace
```
1. « Never required ». No voyage means no key and no block. Every parcours
   runs identically without one — parcours 3 exists to remove barriers, and a
   six-session game would be the largest barrier in the product.
```
with
```
1. « Never required ». No voyage means no key and no block. An analysis runs
   identically without one — a six-session game would be the largest barrier
   in the product.
```

- [ ] **Step 3: Run the tests and watch them fail**

Run: `cd $WT/backend && $PY -m pytest tests/test_parcours_inputs.py tests/test_voyage_prompt_context.py -q`

Expected: FAIL in these tests:
- `test_every_stored_path_builds_the_parcours_1_message[2|3|B]`
- `test_create_stamps_parcours_1_whatever_the_body_says[2|3|B|b]`
- `test_a_stale_parcours_3_form_gets_the_parcours_1_errors` (today it returns 201)
- `test_a_draft_carrying_a_retired_parcours_is_stamped_1[2|3|B]`

Everything else passes.

- [ ] **Step 4: Implement in `backend/app/routes/analyses.py`**

1. In `create_analysis`, replace

```python
    # normalize() maps the legacy 'A'/'B' codes onto parcours ids and falls
    # back to parcours 1 for anything unrecognised.
    path = registry.normalize(inputs.get("_path"))
    inputs["_path"] = path
    # Only parcours 1 has chemins; carrying the key elsewhere would be noise in
    # the stored inputs and in every prompt built from them.
    if path == "1":
        inputs["_chemin"] = _normalize_chemin(inputs.get("_chemin"))
```
with
```python
    # Parcours 1 is the only parcours (2 and 3 were retired on 2026-10-08).
    # The stored id is the server's, whatever the body says: a stale page
    # posting "2" or "3" gets a parcours 1 analysis, validated as one.
    inputs["_path"] = registry.DEFAULT_PARCOURS
    inputs["_chemin"] = _normalize_chemin(inputs.get("_chemin"))
```

2. Replace

```python
    if _FORCE_TIER:
        # TEMPORARY — see _FORCE_TIER above. Delete the default to restore
        # normal tier selection.
        inputs["_tier"] = _FORCE_TIER
    elif path == "3":
        # Parcours 3 runs on the paid model for everyone — it serves the
        # populations the free tier exists to reach.
        inputs["_tier"] = tiers.PAID
    else:
```
with
```python
    if _FORCE_TIER:
        # TEMPORARY — see _FORCE_TIER above. Delete the default to restore
        # normal tier selection.
        inputs["_tier"] = _FORCE_TIER
    else:
```

3. Replace `    errors = VALIDATORS[path](inputs)` with `    errors = _validate_inputs(inputs)`.
4. Replace

```python
    # Fold in the Profil de base so the parcours forms never re-ask what the
    # profile already knows, and pre-shape bloc 5 into the three lists the
    # report may use — the raw answers never reach the model.
```
with
```python
    # Fold in the Profil de base so the form never re-asks what the profile
    # already knows, and pre-shape bloc 5 into the three lists the report may
    # use — the raw answers never reach the model.
```

5. In `save_draft`, directly after the line `    inputs = dict_field(data, "inputs")`, insert:

```python
    # Same rule as create_analysis: a draft that names a parcours names
    # parcours 1. An absent _path already means parcours 1, so an empty draft
    # stays empty.
    if "_path" in inputs:
        inputs["_path"] = registry.DEFAULT_PARCOURS
```

6. In the `get_analysis` docstring, replace `    name, location, and the health context parcours 3 collects.` with `    name, location, and the bloc 5 context folded in from the profile.`
7. In the `_merge_voyage` docstring, replace `    No voyage: no key. Every parcours runs identically without one, and an` with `    No voyage: no key. An analysis runs identically without one, and an`.
8. Delete everything from the line `# ── per-parcours validation ──────────────────────────────────────────────────` to the end of the file: `_missing`, `_validate_inputs_p2`, `_validate_inputs_p3` and `VALIDATORS`. The file must then end with `_validate_inputs`'s `    return errors` and a single newline.

- [ ] **Step 5: Implement in `backend/app/services/anthropic_service.py`**

1. Replace the `_profile_block` docstring

```python
    """The Profil de base, shared by all three parcours.

    Filled once and never re-asked (Parcours doc §1: "une information, une
    seule fois"), so every parcours message opens with the same block.
    """
```
with
```python
    """The Profil de base block of the analysis message.

    Filled once and never re-asked (Parcours doc §1: "une information, une
    seule fois").
    """
```

2. In `_voyage_block`'s docstring, replace

```python
    No voyage means no block and no header. Every parcours runs identically
    without one; the voyage is never required.
```
with
```python
    No voyage means no block and no header. An analysis runs identically
    without one; the voyage is never required.
```

3. Delete the functions `_format_user_message_p2` and `_format_user_message_p3` and the `_FORMATTERS` dict. Replace `_format_user_message` with:

```python
def _format_user_message(inputs: dict) -> str:
    # One parcours left: every stored row ("1", the legacy "A", or a retired
    # id still waiting for the purge) gets the parcours 1 message.
    return _format_user_message_p1(inputs or {})
```

4. In `_run_analysis`, replace

```python
        # Chemin B is free + Sonnet for all users (decision 4.6 / 4.7).
        # Parcours 3 runs on the paid model for everyone (free for the
        # vulnerable populations it serves).
        tier = tiers.PAID if path == "3" else tiers.normalize(inputs.get("_tier"))
```
with
```python
        tier = tiers.normalize(inputs.get("_tier"))
```
The old "Chemin B" comment named the pre-v1.2 path B, which became parcours 3.

- [ ] **Step 6: Update docs that describe the message**

1. In `CLAUDE.md`, replace

```
- `anthropic_service._voyage_block()` wraps the lines under
  `--- CE QUE LE VOYAGE A RÉVÉLÉ ---` inside `_common_tail()`, so all three
  parcours carry it from one place.
```
with
```
- `anthropic_service._voyage_block()` wraps the lines under
  `--- CE QUE LE VOYAGE A RÉVÉLÉ ---` inside `_common_tail()`, which closes
  the analysis message.
```
and replace
```
1. **Never required.** No voyage → no key, no block, no placeholder. Every
   parcours runs identically without one.
```
with
```
1. **Never required.** No voyage → no key, no block, no placeholder. An
   analysis runs identically without one.
```

2. Insert this note in `docs/superpowers/specs/2026-09-09-voyage-design.md`, after the `Status:` line (line 3), with a blank line before it:

```
> **2026-10-08:** parcours 2 and 3 were retired
> (`docs/superpowers/specs/2026-10-08-remove-parcours-2-3-design.md`). The
> P2/P3 mentions below describe the app as it was designed on 2026-09-09.
```

3. Insert the same note in `docs/superpowers/plans/2026-09-09-voyage-contracts.md`, after the `Source of truth:` line (line 5), with a blank line before it.

- [ ] **Step 7: Run the tests, then the whole suite**

Run: `cd $WT/backend && $PY -m pytest tests/test_parcours_inputs.py tests/test_voyage_prompt_context.py -q`
Expected: all pass.

Run: `$PY -m pytest -q`
Expected: 0 failed. The P2/P3 rendering tests in `test_anthropic_service.py` still pass at this point: the registry is unchanged until Task 2.

- [ ] **Step 8: Commit**

```bash
cd $WT
git add backend/app/routes/analyses.py backend/app/services/anthropic_service.py \
        backend/tests/test_parcours_inputs.py backend/tests/test_voyage_prompt_context.py \
        CLAUDE.md docs/superpowers/specs/2026-09-09-voyage-design.md \
        docs/superpowers/plans/2026-09-09-voyage-contracts.md
git commit -m "feat(analyses): every new analysis is parcours 1

The server stamps _path \"1\" whatever the body says; the P2/P3 validators
and message builders go.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The registry and the prompt slots know only parcours 1

**Files:**
- Modify:
  - `backend/app/services/section_registry.py`
  - `backend/app/services/prompt_slots.py`
  - `backend/app/routes/prompts.py`
  - `backend/app/services/unlock_service.py`
  - `backend/app/routes/payments.py`
  - `backend/app/models/analysis.py`
  - `backend/app/services/anthropic_service.py` (two docstrings)
- Modify, comments only: `backend/app/models/prompt_version.py`, `backend/app/models/profile.py`, `backend/app/routes/profile.py`, `backend/app/routes/admin.py`
- Delete: `backend/seed_prompt_v10_p2.py`, `backend/seed_prompt_v11_p3.py`
- Modify: `.github/workflows/seed.yml`, `DOCKER.md` (seed loop)
- Modify: `frontend/src/app/admin/prompts/page.tsx`, `frontend/src/types/index.ts` (prompt slot types only)
- Tests:
  - `test_prompt_slots.py`
  - `test_analysis_model.py`
  - `test_anthropic_service.py`
  - `test_stream_progress.py`
  - `test_unlock.py`
  - `test_seed_scripts.py`
  - `test_prompt_section_keys.py`
  - `test_admin_selector_labels.py`
  - `test_analysis_access.py`
  - `test_auth_links.py`

**Interfaces:**
- Consumes: from Task 1, no new P2/P3 row can be created.
- Produces:
  - `registry.PARCOURS` has the single key "1", and `registry.normalize(x) == "1"` for any `x`.
  - `prompt_slots.valid() == ("1", "voyage_micro", "voyage_portrait")`.
  - `_read_path` accepts "", "1", "A" and the voyage slots; anything else gets a 400.
  - Frontend: `PromptSlot = "1" | "voyage_micro" | "voyage_portrait"`; `toSlot(raw) -> PromptSlot | null`.

- [ ] **Step 1: Install the frontend dependencies in the worktree** (needed from this task on)

Run: `cd $WT/frontend && npm ci`
Expected: `added … packages`, exit 0.

- [ ] **Step 2: Write the failing backend tests**

**`backend/tests/test_prompt_slots.py`**

1. Add `import pytest` as the first import.
2. Replace `test_the_five_slots_are_the_parcours_plus_the_two_voyage_prompts` with:

```python
def test_the_three_slots_are_parcours_1_plus_the_two_voyage_prompts():
    assert prompt_slots.valid() == ("1", "voyage_micro", "voyage_portrait")
```

3. In `test_parcours_ids_come_first`, replace the assert with `assert prompt_slots.valid()[:len(registry.PARCOURS)] == tuple(registry.PARCOURS)`.
4. Replace `test_legacy_path_codes_still_fold_onto_parcours` with:

```python
def test_the_legacy_path_code_still_folds_onto_parcours_1():
    """Rows written before the 3-parcours migration carry 'A'."""
    assert prompt_slots.normalize("A") == "1"
    assert prompt_slots.normalize("a") == "1"


def test_retired_parcours_ids_read_as_parcours_1():
    """A stored '2', '3' or 'B' (before the purge) is coerced, never kept."""
    for retired in ("2", "3", "B", "b"):
        assert prompt_slots.normalize(retired) == "1"
```

5. In `test_choices_are_selector_ready`, delete the two dict lines for "2" and "3".
6. Replace `test_legacy_codes_resolve_to_correct_parcours` with:

```python
def test_the_legacy_code_a_still_resolves_to_parcours_1(client, admin_headers):
    res = client.post("/api/prompts/", headers=admin_headers, json={
        "version_label": "v-legacy-a",
        "system_prompt_text": "Legacy A",
        "path": "A",
    })
    assert res.status_code == 201
    assert res.get_json()["prompt"]["path"] == "1"


@pytest.mark.parametrize("retired", ["2", "3", "B"])
def test_a_retired_slot_is_refused_and_leaves_the_live_prompt_alone(retired, client, admin_headers):
    """Review Focus 3. Without the 'B' mapping, 'B' would fall through to slot
    '1' and, with activate, silently replace the live parcours 1 prompt."""
    from app.extensions import db
    from app.models.prompt_version import PromptVersion
    live = PromptVersion(version_label="v1-live", system_prompt_text="Live P1",
                         path="1", is_active=True)
    db.session.add(live)
    db.session.commit()

    res = client.post("/api/prompts/", headers=admin_headers, json={
        "version_label": "v-retired",
        "system_prompt_text": "Retired",
        "path": retired,
        "activate": True,
    })
    assert res.status_code == 400
    assert "'1', 'voyage_micro', 'voyage_portrait'" in res.get_json()["error"]

    still = PromptVersion.query.filter_by(is_active=True, path="1").one()
    assert still.id == live.id
    assert still.system_prompt_text == "Live P1"
    assert client.get(f"/api/prompts/active?path={retired}").status_code == 400
```

**`backend/tests/test_analysis_model.py`**

1. Replace `test_parcours_resolves_legacy_path_codes` with:

```python
def test_parcours_resolves_the_legacy_path_code():
    assert _analysis("A").parcours == "1"


def test_retired_parcours_read_as_parcours_1():
    for retired in ("2", "3", "B"):
        assert _analysis(retired).parcours == "1"
```

2. Replace the P2 version of `test_sections_meta_is_ordered_and_typed`, and delete `test_sections_meta_roman_order_is_not_lexicographic`, with:

```python
def test_sections_meta_is_ordered_and_typed():
    """Registry order is the contract: the verdict sits between §3 and §4,
    and a string sort would put §10 and §11 before §2."""
    meta = _analysis("1").to_dict()["sections_meta"]
    assert [m["key"] for m in meta] == [
        "1", "2", "3", "verdict", "4", "5", "6", "7", "8", "9", "10", "11",
    ]
    assert meta[0]["title"] == "Lecture stratégique du parcours"
    assert next(m for m in meta if m["key"] == "3")["render"] == "tags"
    assert next(m for m in meta if m["key"] == "1")["render"] == "markdown"
```

3. Delete `test_counselor_view_uses_the_right_set_per_parcours`.
4. Replace the comment above `_RENDERED_INPUT_KEYS`, and the set itself, with:

```python
# Every analysis.inputs.X access in frontend/src/app/c/[token]/page.tsx
# (verified 2026-10-08): the header name and the "key facts" strip.
_RENDERED_INPUT_KEYS = {
    "prenom", "nom", "cible_visee", "type_mobilite",
    "situation_actuelle", "notes_specifiques",
}
```

5. In `_full_inputs`, delete the four lines `"_sub_profile": "b2",`, `"aime": [...]`, `"refuse": [...]`, `"accompagnement": "a distance",`. Keep `"_path": "1"`: it is now a stored key that must not reach the public link.
6. Append at the end of the file:

```python
@pytest.mark.parametrize("retired", ["2", "3", "B"])
def test_a_leftover_retired_row_is_served_as_parcours_1(retired, client):
    """Review Focus 2. Between the deploy and the purge, a P2/P3/'B' row must
    render as parcours 1 — never a 500 — on the owner's view and on the
    public counselor link."""
    row = _persisted_analysis({"_path": retired, "cv_text": "x"},
                              share_token=f"tok-retired-{retired}")
    row.output = {"A": {"title": "Capital", "body_markdown": "b", "items": []}}
    _db.session.commit()

    assert row.to_dict()["sections_meta"][0]["key"] == "1"
    assert client.get(f"/api/c/tok-retired-{retired}").status_code == 200
```

**`backend/tests/test_anthropic_service.py`**

1. Delete these 7 tests:
   - `test_markdown_letter_keys_parcours_2`
   - `test_markdown_roman_keys_parcours_3`
   - `test_roman_vi_not_read_as_v`
   - `test_letter_keyed_json_is_not_rejected`
   - `test_plain_text_falls_back_to_first_key_of_parcours`
   - `test_schema_shape_parcours_2`
   - `test_schema_shape_parcours_3_premium`
2. Replace the section comment `# ── markdown fallback: letter and Roman key sets ─────────────────────────────` with `# ── markdown fallback: two-digit keys ─────────────────────────────────────────` and put this test under it:

```python
def test_two_digit_headings_are_not_read_as_section_1():
    """§10 and §11 land in their own slots, never in §1's (the coverage the
    roman-numeral test gave before parcours 3 was retired)."""
    raw = "## §1 Lecture\ncorps un\n## §10 Entretien\ncorps dix\n## §11 Questions\ncorps onze\n"
    out = _parse_output(raw, "1")
    assert set(out.keys()) == {"1", "10", "11"}
    assert out["1"]["body_markdown"] == "corps un"
    assert out["10"]["body_markdown"] == "corps dix"
    assert out["11"]["body_markdown"] == "corps onze"
```

3. Rename `test_section_keys_per_parcours_tier` to `test_section_keys_per_tier`, and delete its two last asserts (the `"2"` and `"3"` lines).
4. Replace `test_legacy_path_codes_still_resolve` with:

```python
def test_legacy_and_retired_path_codes_resolve_to_parcours_1():
    """'A' predates the 3-parcours migration; '2', '3' and 'B' are retired."""
    for path in ("A", "2", "3", "B"):
        assert _section_keys(path, "sonnet") == _section_keys("1", "sonnet")
```

**`backend/tests/test_stream_progress.py`** — append after `test_fewer_sections_means_bigger_steps`:

```python
def test_two_digit_keys_open_their_own_sections():
    """Premium keys: "10" and "11" are their own sections, never a second "1"."""
    keys = [str(n) for n in range(1, 12)]
    found = [m.group(1) for m in _section_open_re(keys).finditer(_opened("1", "10", "11"))]
    assert found == ["1", "10", "11"]
```

**Smaller test edits**

- `backend/tests/test_unlock.py`: delete `test_unlock_path_b_rejected`.
- `backend/tests/test_seed_scripts.py`: in `SEEDS`, delete the `seed_prompt_v11_p3.py` and `seed_prompt_v10_p2.py` lines.
- `backend/tests/test_prompt_section_keys.py`:
  - Replace the module docstring's first paragraph
    ```
    Parcours 3 shipped for weeks on a prompt that documented sections 1, 2, 3, 8
    and 9 while the registry emitted I, II, III, verdict, IV, V and VI. Nothing
    failed loudly: `_build_output_schema` is built from the registry and the model
    obeys the schema, so the report came back with the right keys and content
    written against instructions for sections that no longer existed.
    ```
    with
    ```
    A prompt once shipped for weeks documenting sections its schema no longer
    asked for. Nothing failed loudly: `_build_output_schema` is built from the
    registry and the model obeys the schema, so the report came back with the
    right keys and content written against instructions for sections that no
    longer existed.
    ```
  - Replace the comment ``# `PATH = "2"` — the parcours a seed script targets.`` with ``# `PATH = "1"` — the parcours a seed script targets.``.
- `backend/tests/test_admin_selector_labels.py`: in the docstring, replace `hard-codes the same five strings` with `hard-codes the same three strings`.
- `backend/tests/test_analysis_access.py`: in the docstring, replace `CV text, name, location, and the health context parcours 3 collects.` with `CV text, name, location, and the bloc 5 context folded in from the profile.`
- `backend/tests/test_auth_links.py`: replace both `"/analyse/nouveau?parcours=2"` on the same line with `"/analyse/nouveau?draft=abc"`.

- [ ] **Step 3: Run the edited tests and watch them fail**

Run: `cd $WT/backend && $PY -m pytest tests/test_prompt_slots.py tests/test_analysis_model.py tests/test_anthropic_service.py -q`

Expected FAIL:
- `test_the_three_slots_are_parcours_1_plus_the_two_voyage_prompts`
- `test_retired_parcours_ids_read_as_parcours_1`
- `test_choices_are_selector_ready`
- `test_a_retired_slot_is_refused_and_leaves_the_live_prompt_alone[2|3|B]`
- `test_retired_parcours_read_as_parcours_1`
- `test_public_share_link_hides_cv_text_and_sensitive_inputs` and `test_an_unknown_input_key_does_not_reach_the_counselor_payload` (today `_path` is still on the allow-list)
- `test_a_leftover_retired_row_is_served_as_parcours_1[2|3|B]`
- `test_legacy_and_retired_path_codes_resolve_to_parcours_1`

- [ ] **Step 4: Implement the registry, slots and API**

**`backend/app/services/section_registry.py`**

1. In the module docstring, replace

```
  * **Order** — list position is the order. Parcours 2 uses letter keys
    (A..G) and parcours 3 Roman numerals (I..VI); neither sorts
    numerically, and `Number("A") - Number("B")` is NaN, which leaves a
    JS sort in insertion order without raising.
```
with
```
  * **Order** — list position is the order. The free-tier "verdict" sits
    between §3 and §4, and a string sort puts "10" and "11" before "2",
    so no consumer may sort keys.
```

2. Delete the `_P2` and `_P3` blocks: from the line `# ── Parcours 2 — « Je cherche ma direction » ─────────` through the closing `]` of `_P3`.
3. Replace the comment above `PARCOURS`, and the dict, with:

```python
# `counselor` is the 5-minute synthesis a Cap Emploi / Mission Locale
# counselor sees at /c/<share_token>, fixed by the spec (§1, §4, §5).
# Parcours 2 and 3 were retired on 2026-10-08; the dict keeps its shape.
PARCOURS = {
    "1": {
        "label": "J'ai une cible",
        "sections": _P1,
        "counselor": ("1", "4", "5"),
    },
}
```

4. Replace `normalize` with:

```python
def normalize(parcours) -> str:
    """Coerce a stored parcours id to a known value.

    Accepts the legacy 'A' path code so rows written before the 3-parcours
    migration keep rendering; anything else — a retired '2', '3' or 'B'
    waiting for the purge, or garbage — falls back to parcours 1.
    `parcours in PARCOURS` needs a hashable value; a hostile value (a list,
    a dict) raised TypeError -- an unhandled 500.
    """
    try:
        if parcours in PARCOURS:
            return parcours
    except TypeError:
        pass  # unhashable (a list, a dict) -- never a valid parcours id
    legacy = {"A": "1"}
    return legacy.get(str(parcours).upper(), DEFAULT_PARCOURS)
```

**`backend/app/services/prompt_slots.py`**

1. In `LABELS`, delete the `"2": …` and `"3": …` lines.
2. `valid()` docstring → `"""('1', 'voyage_micro', 'voyage_portrait') — parcours ids first."""`
3. In the `normalize()` docstring, replace `which still folds the legacy 'A'/'B' path codes onto parcours ids and defaults the unrecognised to parcours 1.` with `which folds the legacy 'A' onto parcours 1 and defaults everything else to parcours 1.` Reflow the docstring lines at 79 columns.

**`backend/app/routes/prompts.py`**

1. Replace `_read_path` with:

```python
def _read_path(raw):
    """Validate a prompt slot from the request, accepting the legacy 'A'.

    Deliberately does NOT go through prompt_slots.normalize(): that function
    coerces *stored* values and defaults anything unrecognised to parcours 1,
    which is right for rendering an old row and wrong for client input — it
    would turn a typo in the admin UI into a silent overwrite of the live
    parcours 1 prompt. Unknown input — the retired '2', '3' and 'B' included
    — is the caller's error and gets a 400.

    Returns (slot, error_response).
    """
    value = str(raw or "").strip()
    if not value:
        return registry.DEFAULT_PARCOURS, None
    if value.lower() in prompt_slots.VOYAGE_SLOTS:
        return value.lower(), None
    if value.upper() == "A":
        return registry.DEFAULT_PARCOURS, None
    if prompt_slots.is_valid(value):
        return value, None
    return None, (jsonify({"error": f"path doit être l'un de {_SLOTS_LABEL}."}), 400)
```

2. Replace `    # Scoped to the parcours: the same label may exist once per parcours.` with `    # Scoped to the slot: the same label may exist once per slot.`

**`backend/app/services/unlock_service.py`**
- Delete the import `from . import section_registry as registry`.
- Delete the two lines of the `if registry.normalize(inputs.get("_path")) == "3":` refusal.

**`backend/app/routes/payments.py`**
- Delete the import `from ..services import section_registry as registry`.
- Replace

```python
    analysis = Analysis.query.get_or_404(analysis_id)
    if registry.normalize((analysis.inputs or {}).get("_path")) == "3":
        return jsonify({"error": "Le portrait de potentiel est déjà complet."}), 400
    # unlock_method is the sentinel; the old `"5" in output` test is meaningless
    # for parcours 2 (§A-§G) and 3 (§I-§VI).
    if analysis.unlock_method:
```
with
```python
    analysis = Analysis.query.get_or_404(analysis_id)
    # unlock_method is the sentinel for a report someone already unlocked.
    if analysis.unlock_method:
```

**`backend/app/models/analysis.py`**

1. Replace the allow-list comment and `COUNSELOR_VISIBLE_INPUT_KEYS` with:

```python
# GET /api/c/<share_token> is public and unauthenticated -- anyone holding
# the link gets whatever to_dict(audience="counselor") puts in "inputs".
# This allow-list mirrors every `analysis.inputs.X` access in
# frontend/src/app/c/[token]/page.tsx (verified 2026-10-08): the candidate
# name shown in the header and the "key facts" strip. Anything that page
# does not render -- cv_text, the encrypted-profile-derived _conditions/_oeth
# lines, the _voyage/_voyage_id lines -- must never travel over this public
# link. Add a key here only after confirming that page reads it; this must
# stay an allow-list, never a deny-list, so an unclassified future field
# defaults to hidden.
COUNSELOR_VISIBLE_INPUT_KEYS = frozenset({
    "prenom",
    "nom",
    "cible_visee",
    "type_mobilite",
    "situation_actuelle",
    "notes_specifiques",
})
```

2. Replace `    # and never required: every parcours runs identically with no voyage.` with `    # and never required: an analysis runs identically with no voyage.`
3. Replace

```python
    # Parsed AI output — dict keyed by section key, each a section object.
    # Keys depend on the parcours: '1'..'11' (P1), 'A'..'G' (P2), 'I'..'VI' (P3).
    # See services/section_registry.py.
```
with
```python
    # Parsed AI output — dict keyed by section key ('1'..'11', 'verdict'),
    # each a section object. See services/section_registry.py.
```

4. `parcours` docstring → `"""Registry id for this analysis. Legacy 'A' rows and retired ids read as parcours 1."""`
5. In `to_dict`, replace

```python
        # mode. The client must never sort output keys itself — letter and
        # Roman keys don't sort numerically or lexicographically.
```
with
```python
        # mode. The client must never sort output keys itself — "verdict" sits
        # between "3" and "4", and a string sort puts "10" before "2".
```

**`backend/app/services/anthropic_service.py`**
- `_md_section_re` docstring:

```python
    """Heading matcher for a parcours' key set.

    Matches "## §1 Titre", "### Section 4 : Titre", "**§10 — Titre**".
    The alternation is built from the actual keys rather than a generic
    character class, longest first, so "10" and "11" are never read as "1".
    """
```
- In `_section_open_re`'s docstring, replace `Longest-first, like _md_section_re, so "VI" is never read as "V".` with `Longest-first, like _md_section_re, so "10" is never read as "1".`

**Comments only**
- `backend/app/models/prompt_version.py`:

```python
    # Prompt slot — '1' | 'voyage_micro' | 'voyage_portrait'.
    # See services/prompt_slots.py. Rows written before the v1.2 migration
    # carried 'A'; normalize() still reads it as '1'.
```
- `backend/app/models/profile.py`:
  - line 1 → `"""Profil de base — the 6 blocks filled once, reused by every analysis.`
  - Replace `# variant and gates the youth schemes in parcours 3.` with `# variant of the voyage and gives the analysis prompt its age line.`
- `backend/app/routes/profile.py`: replace `# silently coerced, because these drive routing (parcours 3 youth schemes,` / `# the Académie des Ori variant) and a wrong value is not a cosmetic issue.` with `# silently coerced, because these drive routing (the Académie des Ori` / `# variant, the analysis prompt's age line) and a wrong value is not a` / `# cosmetic issue.`
- `backend/app/routes/admin.py`: replace `    # One active prompt per parcours. This used to be a single unfiltered` with `    # One active prompt per slot. This used to be a single unfiltered`.

**Seeds and runbooks**

```bash
cd $WT && git rm backend/seed_prompt_v10_p2.py backend/seed_prompt_v11_p3.py
```

- `.github/workflows/seed.yml`: replace

```
              SCRIPTS="seed_prompt_v18.py seed_prompt_v11_p3.py seed_prompt_v10_p2.py \
                       seed_prompt_v10_voyage_micro.py seed_prompt_v10_voyage_portrait.py"
```
with
```
              SCRIPTS="seed_prompt_v18.py \
                       seed_prompt_v10_voyage_micro.py seed_prompt_v10_voyage_portrait.py"
```

- `DOCKER.md` (deploy runbook): replace

```
# one prompt per parcours plus the two voyage slots; v1.0-P2 lands inactive,
# the PM activates it in /admin/prompts
for s in seed_prompt_v18.py seed_prompt_v11_p3.py seed_prompt_v10_p2.py \
         seed_prompt_v10_voyage_micro.py seed_prompt_v10_voyage_portrait.py; do
```
with
```
# the parcours 1 prompt plus the two voyage slots
for s in seed_prompt_v18.py \
         seed_prompt_v10_voyage_micro.py seed_prompt_v10_voyage_portrait.py; do
```

- [ ] **Step 5: Implement the frontend prompt-slot side**

`test_admin_selector_labels.py` keeps the two copies of the slot list byte-identical, so this side ships in the same task.

**`frontend/src/types/index.ts`**

1. Replace the `PromptSlot` block with:

```ts
/**
 * Everything PromptVersion.path may hold: parcours 1 plus the two voyage
 * prompt slots. Mirrors backend/app/services/prompt_slots.valid().
 * The voyage slots are prompt slots only — they carry no report sections and
 * an Analysis never holds one.
 */
export type PromptSlot = "1" | "voyage_micro" | "voyage_portrait"
```

2. In `interface PromptVersion`, replace `  /** Legacy rows still carry the "A"/"B" codes; the backend normalises them. */` + `  path?: PromptSlot | "A" | "B"` with `  /** Legacy rows still carry the "A" code; the backend normalises it. */` + `  path?: PromptSlot | "A"`.

**`frontend/src/app/admin/prompts/page.tsx`**

1. `const SLOTS: PromptSlot[] = ["1", "voyage_micro", "voyage_portrait"]`
2. In `SLOT_LABEL`, `SLOT_HELP` and `SLOT_SUFFIX`, delete the `"2"` and `"3"` entries.
3. `const SUFFIX_RE = /-(?:P1|VM|VP|A)$/`
4. Replace `toSlot` and its comment with:

```ts
/** Rows written before the v1.2 migration carry the old "A" code. Any other
 *  value is not a slot this page edits: it is left out, never shown in
 *  parcours 1's history or as its « actif ». */
function toSlot(raw: string | undefined): PromptSlot | null {
  if (raw === undefined || raw === "A") return "1"
  return (SLOTS as string[]).includes(raw) ? (raw as PromptSlot) : null
}
```

Every caller compares `toSlot(v.path) === slot`, so a `null` row matches no slot. No caller changes.

- [ ] **Step 6: Run everything**

```bash
cd $WT/backend && $PY -m pytest -q
cd $WT/frontend && npx tsc --noEmit && npm run lint
```
Expected:
- pytest: 0 failed, including `test_admin_selector_labels.py`, `test_prompt_section_keys.py`, `test_seed_scripts.py` and `test_migration_chain.py`.
- tsc: exit 0.
- lint: no errors.

- [ ] **Step 7: Commit**

```bash
cd $WT
git add -A backend .github/workflows/seed.yml DOCKER.md \
        frontend/src/types/index.ts frontend/src/app/admin/prompts/page.tsx
git commit -m "feat(prompts): the registry and the prompt slots know only parcours 1

Retired ids read as parcours 1; the prompts API refuses \"2\", \"3\" and \"B\"
instead of folding \"B\" onto a live slot. P2/P3 seeds and refusals go.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The purge script

**Files:**
- Create: `backend/purge_retired_parcours.py`
- Create: `backend/tests/test_purge_retired_parcours.py`

**Interfaces:**
- Produces:
  - `retired_kind(path) -> str | None`
  - `census() -> Census`
  - `report(c: Census, out=print) -> None`
  - `purge(apply: bool = False, out=print) -> Census` — returns the census before the run on a dry-run, and the census after deletion on `apply=True`
  - `class PurgeAborted(Exception)`
  - `Census` fields: `analysis_ids: list[str]`, `by_kind: Counter[(kind, status)]`, `unlocked: int`, `notes: int`, `feedback: int`, `redemptions_kept: int`, `prompts: list[PromptVersion]`, `blocking: int`
- Importable with no side effect: `create_app()` runs only under `__main__` (pytest's `pythonpath = .` makes `import purge_retired_parcours` work).

- [ ] **Step 1: Write the failing tests** — create `backend/tests/test_purge_retired_parcours.py`:

```python
"""The one-off purge of parcours 2 and 3 (spec 2026-10-08, « Data purge »).

Temporary, like the script itself: both are removed once production is purged.
"""
import pytest

import purge_retired_parcours as purge_mod
from app.extensions import db
from app.models.analysis import Analysis
from app.models.code_redemption import CodeRedemption
from app.models.counselor_code import CounselorCode
from app.models.counselor_note import CounselorNote
from app.models.price_feedback import PriceFeedback
from app.models.prompt_version import PromptVersion
from app.models.user import User


def _prompt(path, label, active=True):
    p = PromptVersion(version_label=label, system_prompt_text="x", path=path, is_active=active)
    db.session.add(p)
    db.session.commit()
    return p


def _analysis(inputs, status="success", prompt=None, unlock_method=None):
    a = Analysis(inputs=inputs, status=status, unlock_method=unlock_method,
                 prompt_version_id=prompt.id if prompt else None)
    db.session.add(a)
    db.session.commit()
    return a


def _silent(_line):
    pass


@pytest.fixture
def world(app):
    """Parcours 1 rows in every shape the old code read as parcours 1, retired
    rows in every shape it read as parcours 2 or 3, and what hangs off them."""
    counselor = User(email="conseil@test.fr", password_hash="x", role="counselor")
    db.session.add(counselor)
    db.session.commit()

    p1 = _prompt("1", "v1.8")
    micro = _prompt("voyage_micro", "v1.0-VM")
    p2 = _prompt("2", "v1.1-P2")
    p3 = _prompt("3", "v1.1-P3")
    p3_old = _prompt("3", "v1.0-B", active=False)
    legacy_b = _prompt("B", "v0.9-B", active=False)  # defensive: migrated to "3" long ago

    kept = [
        _analysis({"_path": "1", "cv_text": "x"}, prompt=p1),
        _analysis({"_path": "A", "cv_text": "x"}, prompt=p1),
        _analysis({"cv_text": "x"}, prompt=p1),            # no _path at all
        _analysis({"_path": " 2", "cv_text": "x"}),         # the old normalize()
        _analysis({"_path": 2, "cv_text": "x"}),            # read these three
        _analysis({"_path": ["2"], "cv_text": "x"}),        # as parcours 1
        _analysis(None, status="draft"),
    ]
    retired = [
        _analysis({"_path": "2", "cv_text": "x"}, prompt=p2, unlock_method="payment"),
        _analysis({"_path": "3", "experiences": "x"}, prompt=p3),
        _analysis({"_path": "B", "aime": ["x"]}, prompt=p3_old),
        _analysis({"_path": "b"}, status="draft"),
    ]

    db.session.add(CounselorNote(analysis_id=retired[0].id, counselor_id=counselor.id, body="n"))
    db.session.add(CounselorNote(analysis_id=kept[0].id, counselor_id=counselor.id, body="n"))
    db.session.add(PriceFeedback(analysis_id=retired[1].id, bucket="5_10"))
    db.session.add(PriceFeedback(analysis_id=kept[0].id, bucket="5_10"))
    code = CounselorCode(label="Cap Emploi test")
    db.session.add(code)
    db.session.commit()
    db.session.add(CodeRedemption(code_id=code.id, target_type="analysis",
                                  target_id=retired[0].id))
    db.session.commit()

    return {
        "kept": [a.id for a in kept],
        "retired": [a.id for a in retired],
        "kept_prompts": {p1.id, micro.id},
        "retired_prompts": {p2.id, p3.id, p3_old.id, legacy_b.id},
        "counselor": counselor.id,
    }


def test_retired_kind_mirrors_the_old_normalize():
    """Review Focus 5: exactly what the old normalize() sent to parcours 2/3."""
    assert purge_mod.retired_kind("2") == "2"
    assert purge_mod.retired_kind("3") == "3"
    assert purge_mod.retired_kind("B") == "B"
    assert purge_mod.retired_kind("b") == "B"
    for kept in ("1", "A", None, " 2", "2 ", 2, 3, ["2"], {"x": 1}, "", "nonsense"):
        assert purge_mod.retired_kind(kept) is None, kept


def test_the_dry_run_changes_nothing(world):
    lines = []
    census = purge_mod.purge(apply=False, out=lines.append)

    assert sorted(census.analysis_ids) == sorted(world["retired"])
    assert census.by_kind == {("2", "success"): 1, ("3", "success"): 1,
                              ("B", "success"): 1, ("B", "draft"): 1}
    assert census.unlocked == 1
    assert census.notes == 1
    assert census.feedback == 1
    assert census.redemptions_kept == 1
    assert {p.id for p in census.prompts} == world["retired_prompts"]
    assert census.blocking == 0

    assert Analysis.query.count() == len(world["kept"]) + len(world["retired"])
    assert CounselorNote.query.count() == 2
    assert PriceFeedback.query.count() == 2
    assert PromptVersion.query.count() == 6
    assert any("--apply" in line for line in lines)


def test_apply_deletes_exactly_the_retired_rows(world):
    after = purge_mod.purge(apply=True, out=_silent)

    assert {a.id for a in Analysis.query.all()} == set(world["kept"])
    assert {n.analysis_id for n in CounselorNote.query.all()} == {world["kept"][0]}
    assert {f.analysis_id for f in PriceFeedback.query.all()} == {world["kept"][0]}
    assert {p.id for p in PromptVersion.query.all()} == world["kept_prompts"]
    # Kept on purpose (spec, decision 5).
    assert CodeRedemption.query.count() == 1
    assert db.session.get(User, world["counselor"]) is not None
    # The census taken after the run finds nothing left.
    assert after.analysis_ids == []
    assert after.prompts == []


def test_a_second_run_deletes_nothing(world):
    purge_mod.purge(apply=True, out=_silent)
    second = purge_mod.purge(apply=True, out=_silent)
    assert second.analysis_ids == []
    assert second.prompts == []
    assert Analysis.query.count() == len(world["kept"])


def test_a_kept_analysis_on_a_retired_prompt_aborts_everything(world):
    """Review Focus 4: inconsistent data stops the run before anything goes —
    never half a purge."""
    p2 = PromptVersion.query.filter_by(path="2").one()
    _analysis({"_path": "1", "cv_text": "x"}, prompt=p2)
    before = Analysis.query.count()

    with pytest.raises(purge_mod.PurgeAborted):
        purge_mod.purge(apply=True, out=_silent)

    assert Analysis.query.count() == before
    assert PromptVersion.query.count() == 6
    assert CounselorNote.query.count() == 2
    assert PriceFeedback.query.count() == 2
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd $WT/backend && $PY -m pytest tests/test_purge_retired_parcours.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'purge_retired_parcours'`.

- [ ] **Step 3: Write the script** — create `backend/purge_retired_parcours.py`:

```python
"""One-off: delete every trace of parcours 2 and 3 from the database.

Spec: docs/superpowers/specs/2026-10-08-remove-parcours-2-3-design.md,
« Data purge ». Temporary: removed from the repo, with its tests, once the
production purge is confirmed.

    python purge_retired_parcours.py            # dry-run: counts, changes nothing
    python purge_retired_parcours.py --apply    # deletes, in one transaction

Which analyses: those the old section_registry.normalize() sent to parcours 2
or 3 -- an inputs._path of exactly "2" or "3", or any value whose str()
upper-cases to "B" (the old Chemin B, which became parcours 3). Everything that
code read as parcours 1 stays, whatever its _path looks like. Drafts included.

Order, for the foreign keys: counselor notes, price feedback, analyses, then
the prompt versions of slots "2", "3" and "B". A kept analysis that still
points at one of those prompts aborts the run before anything is deleted.
Users and code redemptions are kept (spec, decision 5).
"""
import sys
from collections import Counter
from dataclasses import dataclass, field

from app.extensions import db
from app.models.analysis import Analysis
from app.models.code_redemption import CodeRedemption
from app.models.counselor_note import CounselorNote
from app.models.price_feedback import PriceFeedback
from app.models.prompt_version import PromptVersion

RETIRED_SLOTS = ("2", "3", "B")


class PurgeAborted(Exception):
    """A kept analysis references a prompt version marked for deletion."""


def retired_kind(path) -> str | None:
    """'2', '3' or 'B' when the old normalize() routed `path` to parcours 2
    or 3, else None. It matched an exact '2'/'3' before any coercion, then
    folded str(path).upper() == 'B' onto parcours 3."""
    if isinstance(path, str) and path in ("2", "3"):
        return path
    return "B" if str(path).upper() == "B" else None


@dataclass
class Census:
    analysis_ids: list = field(default_factory=list)
    by_kind: Counter = field(default_factory=Counter)  # (kind, status) -> count
    unlocked: int = 0
    notes: int = 0
    feedback: int = 0
    redemptions_kept: int = 0
    prompts: list = field(default_factory=list)  # PromptVersion rows to delete
    blocking: int = 0  # kept analyses pointing at one of those prompts


def census() -> Census:
    """What a purge would delete, and what it keeps. Changes nothing."""
    c = Census()
    rows = Analysis.query.with_entities(
        Analysis.id, Analysis.inputs, Analysis.status, Analysis.unlock_method
    ).all()
    for row in rows:
        inputs = row.inputs if isinstance(row.inputs, dict) else {}
        kind = retired_kind(inputs.get("_path"))
        if kind is None:
            continue
        c.analysis_ids.append(row.id)
        c.by_kind[(kind, row.status)] += 1
        if row.unlock_method:
            c.unlocked += 1

    ids = c.analysis_ids
    c.notes = CounselorNote.query.filter(CounselorNote.analysis_id.in_(ids)).count()
    c.feedback = PriceFeedback.query.filter(PriceFeedback.analysis_id.in_(ids)).count()
    c.redemptions_kept = CodeRedemption.query.filter(
        CodeRedemption.target_type == "analysis", CodeRedemption.target_id.in_(ids)
    ).count()
    c.prompts = (
        PromptVersion.query.filter(PromptVersion.path.in_(RETIRED_SLOTS))
        .order_by(PromptVersion.path, PromptVersion.created_at)
        .all()
    )
    c.blocking = Analysis.query.filter(
        Analysis.prompt_version_id.in_([p.id for p in c.prompts]),
        Analysis.id.notin_(ids),
    ).count()
    return c


def report(c: Census, out=print) -> None:
    out(f"Analyses to delete: {len(c.analysis_ids)}")
    for (kind, status), n in sorted(c.by_kind.items()):
        out(f"  _path {kind!r} · {status}: {n}")
    out(f"  of which unlocked (paid or code): {c.unlocked}")
    out(f"Counselor notes to delete: {c.notes}")
    out(f"Price feedback rows to delete: {c.feedback}")
    out(f"Code redemptions pointing at them (kept): {c.redemptions_kept}")
    out(f"Prompt versions to delete: {len(c.prompts)}")
    for p in c.prompts:
        state = "active" if p.is_active else "inactive"
        out(f"  path {p.path!r} · {p.version_label} · {state} · {p.created_at:%Y-%m-%d}")
    if c.blocking:
        out(f"BLOCKING: {c.blocking} kept analysis(es) reference one of those prompts.")


def purge(apply: bool = False, out=print) -> Census:
    """Dry-run by default. With apply=True, delete in one transaction and
    return the census taken afterwards — empty when everything went."""
    before = census()
    report(before, out)
    if not apply:
        out("Dry-run: nothing deleted. Run again with --apply to delete.")
        return before
    if before.blocking:
        raise PurgeAborted(
            f"{before.blocking} kept analysis(es) reference a prompt version "
            "marked for deletion. Nothing deleted."
        )
    ids = before.analysis_ids
    prompt_ids = [p.id for p in before.prompts]
    try:
        CounselorNote.query.filter(CounselorNote.analysis_id.in_(ids)).delete(
            synchronize_session=False)
        PriceFeedback.query.filter(PriceFeedback.analysis_id.in_(ids)).delete(
            synchronize_session=False)
        Analysis.query.filter(Analysis.id.in_(ids)).delete(synchronize_session=False)
        PromptVersion.query.filter(PromptVersion.id.in_(prompt_ids)).delete(
            synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    after = census()
    out("Deleted. What is left to delete now:")
    report(after, out)
    return after


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    with app.app_context():
        try:
            purge(apply="--apply" in sys.argv[1:])
        except PurgeAborted as exc:
            print(f"ABORTED: {exc}")
            sys.exit(1)
```

- [ ] **Step 4: Run the tests, then the whole suite**

Run: `$PY -m pytest tests/test_purge_retired_parcours.py -v` → 5 passed.
Run: `$PY -m pytest -q` → 0 failed.

- [ ] **Step 5: Commit**

```bash
cd $WT
git add backend/purge_retired_parcours.py backend/tests/test_purge_retired_parcours.py
git commit -m "feat(data): one-off purge of parcours 2 and 3, dry-run first

Temporary: removed once production is purged.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The frontend knows only parcours 1

**Files:**
- Delete: `frontend/src/app/analyse/direction/page.tsx`, `frontend/src/app/analyse/depart/page.tsx`
- Replace: `frontend/src/app/analyse/page.tsx`
- Modify:
  - `frontend/src/types/index.ts`
  - `frontend/src/app/analyse/[id]/rapport/page.tsx`
  - `frontend/src/app/c/[token]/page.tsx`
  - `frontend/src/app/analyse/[id]/debloquer/page.tsx`
  - `frontend/src/app/espace/page.tsx` (code and comment only; its copy is Task 5)
  - `frontend/src/components/report/ReportSection.tsx` and `frontend/src/app/analyse/nouveau/page.tsx` (comments)
  - `frontend/src/app/page.tsx` (structure only: the `PARCOURS` data, the `#parcours` section and two icon imports)
  - `frontend/src/components/layout/SiteNav.tsx`, `frontend/src/components/layout/SiteFooter.tsx` (`/#parcours` links)
  - `frontend/src/app/globals.css`
  - `TEST-PLAN.md`

**Interfaces:**
- Consumes: Task 2's `PromptSlot`. Task 2 removed `_path` from the counselor allow-list, so the `/c/` page no longer receives `_path`.
- Produces:
  - `AnalysisPath = "1" | "A"`.
  - Gone: `Parcours`, `normalizeParcours`, `SubProfile`, `AnalysisInputsB`, `PAID_SECTIONS`.

- [ ] **Step 1: Write the failing check**

Run:
```bash
cd $WT/frontend && grep -rn -E "normalizeParcours|_sub_profile|AnalysisInputsB|PAID_SECTIONS|SubProfile|Portrait de potentiel|analyse/(direction|depart)|#parcours|--teal|color-teal|bg-teal|ring-teal|text-teal" src
```
Expected now: about 20 matches. After this task: none.

- [ ] **Step 2: Delete the forms and turn `/analyse` into a redirect**

```bash
cd $WT && git rm frontend/src/app/analyse/direction/page.tsx frontend/src/app/analyse/depart/page.tsx
```

Read `node_modules/next/dist/docs/01-app/03-api-reference/04-functions/redirect.md`. It confirms that `redirect()` in a Server Component answers 307. Then replace the whole content of `frontend/src/app/analyse/page.tsx` with:

```tsx
import { redirect } from "next/navigation"

/**
 * Parcours 2 and 3 were retired on 2026-10-08, so there is nothing left to
 * choose: every « Lancer mon analyse » lands on the parcours 1 form. A
 * temporary redirect, because the four-door submit flow (sub-project 2)
 * changes this entry again.
 */
export default function AnalysePage() {
  redirect("/analyse/nouveau")
}
```

- [ ] **Step 3: Types** — in `frontend/src/types/index.ts`

1. Replace

```ts
/** Parcours id. Legacy rows carry "A"/"B"; the backend normalises them. */
export type Parcours = "1" | "2" | "3"

/** Superset accepted on the wire, so legacy analyses still type-check. */
export type AnalysisPath = Parcours | "A" | "B"
```
with
```ts
/** The parcours id an analysis carries. Parcours 1 is the only one left
 *  (2 and 3 were retired on 2026-10-08); rows written before the v1.2
 *  migration carry "A", which the backend reads as "1". */
export type AnalysisPath = "1" | "A"
```

2. Delete `normalizeParcours` with its doc comment, and the line `export type SubProfile = "b1" | "b2" | "b3"`.
3. Replace the `SectionMeta` doc comment with:

```ts
/**
 * Render instructions for one report section, supplied by the backend in
 * registry order. The client must never sort output keys itself — "verdict"
 * sits between "3" and "4", and a string sort puts "10" and "11" before "2".
 */
```

4. Replace the head of `AnalysisInputs`, from `  // Chemin A` through the `_chemin` field, with:

```ts
  cv_text?: string
  cible_visee?: string
  prenom?: string
  nom?: string
  tranche_age?: string
  localisation?: string
  situation_actuelle?: string
  type_mobilite?: string | string[]
  notes_specifiques?: string
  // Discriminators (echoed from backend)
  _path?: AnalysisPath
  /** "A" the employer's job ad, "B" the person's own description of a
   *  target. Absent on rows written before the split. */
  _chemin?: "A" | "B"
```

   This drops the legacy Chemin B fields, which nothing reads: `aime`, `competent`, `refuse`, `pause_activite`, `contraintes_pratiques`, `contraintes_b3`, `accompagnement`, `cv_b3`, `_sub_profile`.
5. In the `_voyage_id` doc comment, replace `Absent when the person has no voyage — every` / `   *  parcours runs identically without one.` with `Absent when the person has no voyage — an` / `   *  analysis runs identically without one.`
6. Delete `export interface AnalysisInputsB { … }`.
7. `counselor_keys` comment → `  /** Section keys the counselor synthesis shows (§1, §4, §5). */`
8. Delete the comment block that starts `// Section membership now comes from` and the line `export const PAID_SECTIONS = ["5", "6", "7", "8", "9"] as const`. `SECTION_TITLES` below them stays.

- [ ] **Step 4: Report, counselor view, unlock page, espace**

**`frontend/src/app/analyse/[id]/rapport/page.tsx`**

1. Delete `import { normalizeParcours } from "@/types"`.
2. Replace

```tsx
  const output = analysis?.output ?? {}
  const path = normalizeParcours(analysis?.inputs?._path)
  const hasOutput = Object.keys(output).length > 0

  // Order and titles come from the backend section registry. Never sort output
  // keys here: parcours 2 uses letter keys and parcours 3 Roman numerals, and
  // Number("A") - Number("B") is NaN, which silently leaves insertion order.
```
with
```tsx
  const output = analysis?.output ?? {}
  const hasOutput = Object.keys(output).length > 0

  // Order and titles come from the backend section registry. Never sort output
  // keys here: "verdict" sits between "3" and "4", and a string sort puts
  // "10" and "11" before "2".
```

3. Replace

```tsx
                  {path === "3"
                    ? `Portrait de potentiel · ${monthLabel}`
                    : `Cible : ${analysis?.inputs?.cible_visee?.slice(0, 60) ?? "—"} · ${monthLabel}`}
```
with
```tsx
                  {`Cible : ${analysis?.inputs?.cible_visee?.slice(0, 60) ?? "—"} · ${monthLabel}`}
```

4. Replace

```tsx
                {(path === "3"
                  ? [
                      ["Sous-profil", analysis.inputs._sub_profile?.toUpperCase() ?? "—"],
                      ["Aime", (analysis.inputs.aime ?? []).join(", ").slice(0, 60) || "—"],
                      ["Refus", (analysis.inputs.refuse ?? []).join(", ").slice(0, 60) || "—"],
                      ["Accompagnement", analysis.inputs.accompagnement ?? "—"],
                    ]
                  : [
                      ["Cible visée", analysis.inputs.cible_visee?.slice(0, 40)],
                      ["Mobilité", Array.isArray(analysis.inputs.type_mobilite) ? analysis.inputs.type_mobilite.join(" + ") : analysis.inputs.type_mobilite],
                      ["Posture actuelle", analysis.inputs.situation_actuelle],
                      ["Points sensibles", analysis.inputs.notes_specifiques || "—"],
                    ]
                ).map(([k, v]) => (
```
with
```tsx
                {[
                  ["Cible visée", analysis.inputs.cible_visee?.slice(0, 40)],
                  ["Mobilité", Array.isArray(analysis.inputs.type_mobilite) ? analysis.inputs.type_mobilite.join(" + ") : analysis.inputs.type_mobilite],
                  ["Posture actuelle", analysis.inputs.situation_actuelle],
                  ["Points sensibles", analysis.inputs.notes_specifiques || "—"],
                ].map(([k, v]) => (
```

5. Replace

```tsx
            {/* Free-plan CTA — Chemin A only */}
            {view === "rapport" && path === "1" && hasOutput && !isPaid && (
```
with
```tsx
            {/* Free-plan CTA */}
            {view === "rapport" && hasOutput && !isPaid && (
```

**`frontend/src/app/c/[token]/page.tsx`**

1. Delete `import { normalizeParcours } from "@/types"`.
2. Replace

```tsx
  const output = analysis?.output ?? {}
  const path = normalizeParcours(analysis?.inputs?._path)
  // The backend already filtered this response to the counselor set for this
  // parcours (audience=counselor) and shipped it in registry order.
```
with
```tsx
  const output = analysis?.output ?? {}
  // The backend already filtered this response to the counselor set
  // (audience=counselor: §1, §4, §5) and shipped it in registry order.
```

3. Replace the key-facts fork the same way as in the report: keep only the four-item parcours 1 array, here with `cible_visee?.slice(0, 50)`. The result is:

```tsx
                {[
                  ["Cible visée", analysis.inputs.cible_visee?.slice(0, 50)],
                  ["Mobilité", Array.isArray(analysis.inputs.type_mobilite) ? analysis.inputs.type_mobilite.join(" + ") : analysis.inputs.type_mobilite],
                  ["Posture actuelle", analysis.inputs.situation_actuelle],
                  ["Points sensibles", analysis.inputs.notes_specifiques || "—"],
                ].map(([k, v]) => (
```

**`frontend/src/app/analyse/[id]/debloquer/page.tsx`**

1. Delete `import { normalizeParcours } from "@/types"`.
2. Delete the line `  const path = normalizeParcours(analysis?.inputs?._path)`.
3. Replace

```tsx
  const alreadyComplete =
    path === "3" || analysis?.unlock_method != null || paidSectionsPresent
```
with
```tsx
  const alreadyComplete = analysis?.unlock_method != null || paidSectionsPresent
```

4. Replace `  // ── Unlock UI (Chemin A, not yet paid) ──` with `  // ── Unlock UI (not yet paid) ──`.

**`frontend/src/app/espace/page.tsx`**

1. Delete `import { normalizeParcours } from "@/types"`.
2. In `cardTitle`, replace the last line with `  return a.inputs?.cible_visee?.slice(0, 60) || "Analyse"`.
3. Replace

```tsx
        {/* Le voyage — the fourth scenario, on the charter's inverted surface so
            it does not read as a fourth parcours card. */}
```
with
```tsx
        {/* Le voyage — on the charter's inverted surface, so it does not read
            as one of the analysis cards below. */}
```

**Comments**

- `frontend/src/components/report/ReportSection.tsx`: replace

```tsx
  // Keys run "1".."11", "A".."G" and "I".."VI" depending on the parcours. The
  // free-tier verdict has no ordinal, so it gets no chip rather than "§verdict".
```
with
```tsx
  // Keys run "1".."11". The free-tier verdict has no ordinal, so it gets no
  // chip rather than "§verdict".
```
- `frontend/src/app/analyse/nouveau/page.tsx`: replace

```tsx
      {/* Same accent as this parcours' card on the landing — the colour is
          how someone knows they are still in the scenario they picked. */}
```
with
```tsx
      {/* The analysis' accent: orange, like the report rule. */}
```

- [ ] **Step 5: Landing structure, nav, footer, colour tokens**

**`frontend/src/app/page.tsx`**

1. In the `lucide-react` import, delete the line `  Compass, Sprout,`. `Target` stays: the « Comment ça marche » steps use it.
2. Delete the `const PARCOURS = [ … ]` declaration: from `const PARCOURS = [` through its closing `]`, and the blank line after it. The next line is then the `/* Le voyage — described by its shape` comment.
3. Delete the whole « Choose your scenario » block: from the line `      {/* ───────────────────── Choose your scenario ───────────────────── */}` through the `      </section>` that closes `<section id="parcours" …>`, and the blank line after it.

**Nav and footer**
- `frontend/src/components/layout/SiteNav.tsx`: delete the line `  { href: "/#parcours", label: "Parcours" },`.
- `frontend/src/components/layout/SiteFooter.tsx`: delete the line `      { href: "/#parcours", label: "Les parcours" },`.

**`frontend/src/app/globals.css`**

1. Delete `  --color-teal:        var(--teal);`.
2. Delete `  --teal:        #2e8b6e;   /* charter teal — third accent */`.
3. Replace `  --success:     #2e8b6e;   /* the charter teal doubles as the success tone */` with `  --success:     #2e8b6e;   /* charter teal, kept as the success tone */`.
4. Replace

```css
/* ── Le voyage ──
   The three parcours own the charter's three full-weight hues (orange, navy,
   teal). The voyage is a fourth scenario, not a fourth parcours, so instead of
   a fourth hue it takes the charter's inverted pairing: peach on navy, 6.81:1,
   the same pair the report header and the landing preview already use. */
```
with
```css
/* ── Le voyage ──
   The analysis owns the charter orange. The voyage is a separate product, so
   instead of a hue of its own it takes the charter's inverted pairing: peach
   on navy, 6.81:1, the same pair the report header and the landing preview
   already use. */
```

- [ ] **Step 6: TEST-PLAN.md**

1. Replace the block from `**Two things will fail until the PM acts, and that's expected — not a bug:**` through `navigation) — only the generation step is blocked.` with:

```
**One thing will fail until the PM acts, and that's expected — not a bug:**

| What | Why | Symptom |
|---|---|---|
| Free-tier "verdict" quality | The current P1 prompt predates the verdict section | The section will exist and be filled, but the wording may be off — the schema forces the key, the prompt never described what belongs in it |
```

2. Row 1.2 → `| 1.2 | Click any "Lancer mon analyse" / "Démarrer" CTA | Lands on the parcours 1 form **\`/analyse/nouveau\`** (\`/analyse\` redirects there since parcours 2 and 3 were retired) |`
3. Replace the whole « ## 2 · The chooser » section, from its heading through row 2.4, with:

```
## 2 · `/analyse`

Parcours 2 and 3 were retired on 2026-10-08; the chooser went with them.

| # | Do | Expect |
|---|---|---|
| 2.1 | Open `/analyse` | Redirected to `/analyse/nouveau` |
| 2.2 | Open `/analyse/direction`, then `/analyse/depart` | The 404 page, both times |
```

4. Replace everything from `## 5 · Parcours 2 — \`/analyse/direction\`` through the row `| 6.4 | Submit | Same expected prompt error as 5.5 |` with:

```
## 5–6 · Parcours 2 and 3

Retired on 2026-10-08 (`docs/superpowers/specs/2026-10-08-remove-parcours-2-3-design.md`). The section numbers stay so the references in this plan still hold.
```

5. Row 8.2 → `| 8.2 | Check the sections | Shows the counselor set only (§1, §4, §5), **and every section has content** |`
6. Row 9.1 → `| 9.1 | \`/admin/prompts\` | The selector shows **three** prompts, in this order: Parcours 1 · J'ai une cible / Voyage · phrase (S0) / Voyage · portrait |`
7. Row 12.1.1: delete `, **above** the three scenario cards`.
8. Row 12.1.3 → `| 12.1.3 | Open \`/analyse\` | Redirected to the parcours 1 form; the voyage is reached from the landing, \`/espace\` and the account menu |`
9. Row 12.9.1: replace `run any parcours analysis` with `run an analysis`.

- [ ] **Step 7: Run the checks**

```bash
cd $WT/frontend
grep -rn -E "normalizeParcours|_sub_profile|AnalysisInputsB|PAID_SECTIONS|SubProfile|Portrait de potentiel|analyse/(direction|depart)|#parcours|--teal|color-teal|bg-teal|ring-teal|text-teal" src
npx tsc --noEmit
npm run lint
npm run build
```

Expected:
- grep: no output.
- tsc: exit 0.
- lint: no errors.
- build: succeeds. The route list shows `/analyse` and `/analyse/nouveau`, and neither `/analyse/direction` nor `/analyse/depart`.

- [ ] **Step 8: Commit**

```bash
cd $WT && git add -A frontend TEST-PLAN.md
git commit -m "feat(frontend): parcours 1 only — no chooser, no P2/P3 pages or forks

/analyse redirects to the form; the report, counselor and unlock pages lose
their parcours 3 branches; the teal accent goes with the P3 card.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Copy — the approved rewrites

**Files:**
- Modify:
  - `frontend/src/app/page.tsx`
  - `frontend/src/components/layout/SiteFooter.tsx`
  - `frontend/src/components/layout/AuthLayout.tsx`
  - `frontend/src/app/layout.tsx`
  - `frontend/src/app/espace/page.tsx`
  - `frontend/src/app/(legal)/cgv/page.tsx`
  - `frontend/src/app/(legal)/confidentialite/page.tsx`

**Interfaces:**
- Consumes: Task 4's landing without the `#parcours` section.
- Produces: no UI string names P2/P3 or promises an analysis without a CV.

- [ ] **Step 1: Write the failing check**

```bash
cd $WT/frontend && grep -rn -E "avec ou sans CV|[Tt]rois parcours|Je cherche ma direction|Je pars de zéro|direction à trouver|départ de zéro|repartez de zéro|parcours « J’ai une cible »|parcours « J&apos;ai une|parcours choisi|questions du parcours|questions de votre parcours|trouver votre direction|si vous en avez un|text-muted-foreground\">parcours<" src
```
Expected now: 15+ matches. After: none.

- [ ] **Step 2: Apply the rewrites** — each is an exact replacement. Leading indentation is unchanged unless shown. The row numbers refer to the spec's copy table.

**`frontend/src/app/page.tsx`**
- **Row 1 (hero subtitle).** Replace `Vous visez un poste, vous cherchez votre direction ou vous repartez de zéro : neoori lit votre parcours — avec ou sans CV — et vous dit ce qui fait votre force, ce qui freine, et par où avancer.` with `Vous visez un poste : neoori lit votre parcours et votre CV face à cette cible, et vous dit ce qui fait votre force, ce qui freine, et par où avancer. Pas encore de cible ? Le voyage vous aide à faire le point.`
- **Row 2 (hero chip).** Delete these four lines:

```tsx
            <div className="absolute -right-4 top-6 hidden rounded-xl bg-white px-3.5 py-2.5 shadow-float ring-1 ring-foreground/10 sm:block">
              <p className="font-display text-xl font-bold leading-none text-navy">3</p>
              <p className="eyebrow mt-1 text-muted-foreground">parcours</p>
            </div>
```
- **Row 3 (step 02).** Replace the line `  { icon: Target, n: "02", title: "Votre point de départ", desc: "Une cible précise, une direction à trouver, ou un départ de zéro. Votre CV si vous en avez un — sinon, quelques questions suffisent." },` with `  { icon: Target, n: "02", title: "Votre cible", desc: "Une offre d’emploi en main, ou le poste que vous visez décrit avec vos mots. Et votre CV, en PDF ou copié-collé." },`
- **Row 4 (step 03).** Replace `desc: "neoori lit votre parcours du point de vue des recruteurs — et votre CV, si vous en avez un, en tenant compte des ATS." },` with `desc: "neoori lit votre parcours et votre CV du point de vue des recruteurs, en tenant compte des ATS." },`
- **Row 6 (#rapport intro).** Replace `Ci-dessous, celui du parcours « J’ai une cible ».` with `Ci-dessous, un exemple.`
- **Row 7 (free offer).** Replace `Vous découvrez ce que votre parcours montre déjà — face au poste que vous visez, ou pour trouver votre direction.` with `Vous découvrez ce que votre parcours montre déjà face au poste que vous visez.`
- **Row 8 (paid offer).** Replace `Pour le parcours « J’ai une cible », en plus des 3 premières sections, vous accédez à :` with `En plus des 3 premières sections, vous accédez à :`
- **Row 9 (FAQ cost).** Replace `Le rapport complet est à 9 € — pour le parcours « J’ai une cible », neuf sections, dont la proposition de CV retravaillé.` with `Le rapport complet est à 9 € : neuf sections, dont la proposition de CV retravaillé.`
- **Row 10 (FAQ time).** Replace `a: "Quelques minutes. Le temps de répondre aux questions de votre parcours, l’analyse est déjà en cours."` with `a: "Quelques minutes après l’envoi de votre CV et de votre cible."`
- **Row 11 (FAQ formats).** Replace `a: "Un PDF jusqu’à 10 Mo, ou un copier-coller de votre texte directement dans l’interface. Pas de CV ? Le parcours « Je pars de zéro » s’en passe : cinq questions suffisent."` with `a: "Un PDF jusqu’à 10 Mo, ou un copier-coller de votre texte directement dans l’interface."`

**Chrome**
- **Row 12.** `SiteFooter.tsx`: replace `Une lecture de votre parcours, avec ou sans CV, au service de votre projet professionnel.` with `Une lecture de votre parcours, au service de votre projet professionnel.`
- **Row 13.** `AuthLayout.tsx`: replace `  "Trois parcours d’analyse et le voyage",` with `  "L’analyse de votre CV et le voyage",`
- **Row 14.** `AuthLayout.tsx`: replace `Une lecture claire de votre parcours, avec ou sans CV.` with `Une lecture claire de votre parcours.`

**`frontend/src/app/layout.tsx`** (ASCII apostrophes)
- **Row 15.** Replace `"Faites le point sur votre parcours, avec ou sans CV : trois parcours d'analyse et le voyage, six sessions pour poser ce que vous savez déjà de vous. Conçu pour les conseillers, les organisations de l'emploi et les candidats.",` with `"Faites le point sur votre parcours : l'analyse de votre CV face au poste que vous visez, et le voyage, six sessions pour poser ce que vous savez déjà de vous. Conçu pour les conseillers, les organisations de l'emploi et les candidats.",`
- **Row 16.** Replace `"Trois parcours d'analyse, avec ou sans CV, et le voyage en six sessions. Pour les conseillers, les organisations de l'emploi et les candidats.",` with `"L'analyse de votre CV face à votre cible, et le voyage en six sessions. Pour les conseillers, les organisations de l'emploi et les candidats.",`
- **Row 17.** Replace `"Trois parcours d'analyse, avec ou sans CV, et le voyage en six sessions pour faire le point sur votre parcours.",` with `"L'analyse de votre CV face à votre cible, et le voyage en six sessions pour faire le point sur votre parcours.",`

**`frontend/src/app/espace/page.tsx`**
- **Row 18.** Replace `<p className="text-sm text-muted-foreground">~2 min · avec ou sans CV</p>` with `<p className="text-sm text-muted-foreground">~2 min</p>`

**`frontend/src/app/(legal)/cgv/page.tsx`**
- **Row 19.** Replace the whole §2 paragraph:

```tsx
      <p>
        L&apos;offre gratuite comprend les trois premières sections du rapport d&apos;analyse,
        ainsi qu&apos;un verdict de diagnostic. L&apos;offre payante débloque le rapport complet
        du parcours choisi, ainsi que l&apos;export conseiller. Pour le parcours « J&apos;ai une
        cible », il compte 9 sections, incluant les points à renforcer, les préconisations
        terrain, un exemple de réécriture, la synthèse, les pistes d&apos;évolution et une
        proposition de CV retravaillé. Le rapport est généré par intelligence artificielle à
        partir des informations fournies par l&apos;utilisateur ; il constitue une aide à la décision
        et non un conseil professionnel individualisé.
      </p>
```
with
```tsx
      <p>
        L&apos;offre gratuite comprend les trois premières sections du rapport d&apos;analyse,
        ainsi qu&apos;un verdict de diagnostic. L&apos;offre payante débloque le rapport complet,
        ainsi que l&apos;export conseiller. Il compte 9 sections, incluant les points à renforcer,
        les préconisations terrain, un exemple de réécriture, la synthèse, les pistes
        d&apos;évolution et une proposition de CV retravaillé. Le rapport est généré par
        intelligence artificielle à partir des informations fournies par l&apos;utilisateur ; il
        constitue une aide à la décision et non un conseil professionnel individualisé.
      </p>
```

**`frontend/src/app/(legal)/confidentialite/page.tsx`**
- **Row 20.** Replace

```tsx
          <strong>Analyses</strong> : selon le parcours choisi, le contenu de votre CV, la cible
          visée (offre d&apos;emploi ou description) et vos réponses aux questions du parcours
          (pouvant inclure des informations sensibles que vous choisissez de communiquer).
```
with
```tsx
          <strong>Analyses</strong> : le contenu de votre CV et la cible visée (offre
          d&apos;emploi ou description), pouvant inclure des informations sensibles que vous
          choisissez de communiquer.
```

- [ ] **Step 3: Run the checks**

```bash
cd $WT/frontend
grep -rn -E "avec ou sans CV|[Tt]rois parcours|Je cherche ma direction|Je pars de zéro|direction à trouver|départ de zéro|repartez de zéro|parcours « J’ai une cible »|parcours « J&apos;ai une|parcours choisi|questions du parcours|questions de votre parcours|trouver votre direction|si vous en avez un|text-muted-foreground\">parcours<" src
cd $WT && git diff -U0 frontend | grep '^+' | grep -i -E "boussole|copilote|miroir|révélation|épanouissement|alignement|excellence|talent unique|vous vous démarquez"
cd $WT/frontend && npx tsc --noEmit && npm run lint && npm run build
```
Expected: both greps print nothing; tsc, lint and build succeed.

- [ ] **Step 4: Commit**

```bash
cd $WT && git add frontend
git commit -m "feat(copy): the site stops naming parcours 2 and 3

The rewrites approved with the spec's copy table; nothing else on the
landing changes.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Legacy hosting leftovers

**Files:**
- Modify: `CLAUDE.md`, `DOCKER.md`, `TEST-PLAN.md`
- Modify: `.gitignore`, `frontend/.gitignore`, `frontend/.dockerignore`
- Modify: `.github/workflows/deploy.yml`, `backend/app/config.py`, `backend/app/routes/analyses.py`
- Delete: `frontend/vercel.json`

**Interfaces:** none. Comments, docs and ignore files only; no runtime behaviour changes.

- [ ] **Step 1: Write the failing check**

```bash
cd $WT && git grep -n -E "vercel|Vercel|TiDB|tidb|on Render|cutover" -- . ':!docs/' ':!*.pdf' ':!plan.md' ':!SESSION-LOG.md' ':!handoff.md' ':!backend/migrations/' ':!AUTOMATION-PLAN.md'
```
Case-sensitive on purpose: with `-i`, "on Render" matches every `<Button render=…>`.

Expected now: exactly 12 lines:
- `.github/workflows/deploy.yml:2`
- `.gitignore:30`
- `CLAUDE.md:146`
- `DOCKER.md:138`, `DOCKER.md:141`
- `TEST-PLAN.md:3`, `TEST-PLAN.md:34`
- `backend/app/config.py:17`
- `backend/app/routes/analyses.py:27`
- `frontend/.dockerignore:8`
- `frontend/.gitignore:36`, `frontend/.gitignore:37`

After this task: none.

- [ ] **Step 2: Remove and reword**

1. `CLAUDE.md`: delete the line ``- The legacy Vercel/Render/TiDB test env keeps serving its last deploy until cutover — data migration steps in `DOCKER.md`.``
2. `DOCKER.md`: delete the section from the heading `## Data migration (TiDB Cloud → VPS MySQL, at cutover)` up to, but not including, `## Backups`. That covers its bash block, the sentence ``The alembic version table travels with the dump, so `flask db upgrade` stays consistent.``, and the blank line.
3. Delete `frontend/vercel.json`:

```bash
git rm frontend/vercel.json
```

4. Ignore files:
   - `.gitignore`: delete the line `.vercel`.
   - `frontend/.gitignore`: delete the lines `# vercel` and `.vercel`, and the blank line left between their neighbours.
   - `frontend/.dockerignore`: delete the line `.vercel`.
5. `backend/app/config.py`: replace

```python
    # TiDB Cloud closes idle connections; without pre-ping the first request
    # after an idle period hits a stale pooled connection and 500s.
```
with
```python
    # MySQL closes connections idle past wait_timeout; without pre-ping the
    # first request after an idle period hits a stale pooled connection and
    # 500s.
```
Keep `SQLALCHEMY_ENGINE_OPTIONS` itself unchanged.
6. `backend/app/routes/analyses.py`: replace `# FORCE_ANALYSIS_TIER="" on Render). The paywall, the unlock flow and the` with `# FORCE_ANALYSIS_TIER="" in /srv/neoori/.env). The paywall, the unlock flow and the`
7. `TEST-PLAN.md`:
   - Replace `Test environment: http://localhost:8080 (docker dev) — VPS domain after cutover (see DOCKER.md)` with `Test environment: http://localhost:8080 (docker dev), or production (see DOCKER.md)`.
   - Replace ``Reverting is one env var: `FORCE_ANALYSIS_TIER=""` on Render.`` with ``Reverting is one env var: `FORCE_ANALYSIS_TIER=""` in `/srv/neoori/.env` on the VPS.``
8. `.github/workflows/deploy.yml`: replace `` # Replaces the Vercel/Render auto-deploys: `git push` stays the whole workflow.`` with `` # `git push` is the whole workflow.``

- [ ] **Step 3: Run the checks**

Run the Step 1 grep again → no output.
Run `cd $WT/backend && $PY -m pytest -q` → 0 failed.

- [ ] **Step 4: Commit**

```bash
cd $WT && git add -A CLAUDE.md DOCKER.md TEST-PLAN.md .gitignore frontend .github backend
git commit -m "chore: drop the Vercel/Render/TiDB leftovers

That environment is gone; nothing in the repo describes it as current.
pool_pre_ping stays — MySQL drops idle connections too.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Whole-branch verification

**Files:** none changed, except fixes for what this task finds; commit those separately.

- [ ] **Step 1: Full checks**

```bash
cd $WT/backend && $PY -m pytest -q
cd $WT/frontend && npx tsc --noEmit && npm run lint && npm run build
```
Expected: pytest 0 failed (report the count); tsc, lint and build succeed.

- [ ] **Step 2: Repo-wide sweep**

```bash
cd $WT && git grep -n -i -E "je cherche ma direction|je pars de z[ée]ro|parcours ?2|parcours ?3|_P2\b|_P3\b|portrait de potentiel|avec ou sans cv|trois parcours|three parcours|analyse/(direction|depart)" -- . ':!docs/' ':!plan.md' ':!SESSION-LOG.md' ':!handoff.md' ':!backend/migrations/' ':!*.pdf' ':!backend/purge_retired_parcours.py' ':!backend/tests/test_purge_retired_parcours.py' ':!wireframes/' ':!spec/' ':!reports/'
```

Only two kinds of hit are allowed:
- (a) retirement notes this plan writes, which say "retired" and/or "2026-10-08":
  - `TEST-PLAN.md` (row 1.2, §2, §5–6);
  - the `PARCOURS` comment in `section_registry.py`;
  - `frontend/src/app/analyse/page.tsx`;
  - the section comment in `test_parcours_inputs.py`;
  - the docstring of `test_two_digit_headings_are_not_read_as_section_1`.
- (b) the historical bug list in `backend/tests/test_no_500_on_hostile_input.py`'s docstring.

Any other hit is a miss: fix it, and add it to the task it belongs to.

- [ ] **Step 3: Local Docker walkthrough and dev rehearsal — STOP: ask the developer first.**

The dev compose pins the project name `neoori` and the DB volume `backend_neoori_mysql_data`. Running it from the worktree takes over the containers currently started from the main checkout, and deletes P2/P3 rows from the shared dev database.

After the go:

```bash
docker compose ls                       # note whether "neoori" runs, and from where
cd $WT && docker compose up -d --build
```

At http://localhost:8080, signed in:
- Landing: no « 3 parcours » chip, no « Trois situations » section, the new hero subtitle, no « Parcours » link in the nav or the footer.
- « Lancer mon analyse » → `/analyse/nouveau`.
- `/analyse/direction` and `/analyse/depart` → 404 page.
- An existing parcours 1 report renders. Its « Vue conseiller » tab shows §1, §4, §5 and the key-facts strip.
- `/c/<token>` for that report renders.
- `/admin/prompts` shows three chips. `/espace` lists the analyses.

Dev database rehearsal:

```bash
docker compose exec -T backend python purge_retired_parcours.py           # read the counts
docker compose exec -T backend python purge_retired_parcours.py --apply   # STOP: show the counts, wait for the go
docker compose exec -T backend python purge_retired_parcours.py           # every count at 0
```

Then give the developer their stack back, if it was running before:

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer && docker compose up -d
```

- [ ] **Step 4: Final review** of the whole branch diff against the spec (fresh reviewer, per the execution skill).

---

### Task 8: Production rollout — every step waits for the developer

- [ ] **Step 1 — STOP.** Ask whether the PM has copied the P2/P3 prompt texts from `/admin/prompts`. This is optional; slots 2 and 3 disappear from the admin at deploy.
- [ ] **Step 2 — STOP. Merge and deploy.**

```bash
cd $WT
git checkout initial
git merge --ff-only feat/remove-parcours-2-3
git log --oneline origin/initial..initial   # also lists the 2 social-sign-in doc commits (cef2dec, d7cf8e5)
git push origin initial                     # CI builds the images and deploys
gh run watch                                # wait for the deploy workflow to succeed
```

If `--ff-only` refuses because `initial` moved, stop and ask.

- [ ] **Step 3 — STOP. Production dry-run.**

```bash
ssh-add --apple-load-keychain   # only if the agent is empty: the key passphrase is in the keychain
ssh neoori 'cd /srv/neoori && docker compose -f docker-compose.prod.yml exec -T backend python purge_retired_parcours.py'
```
Show the output to the developer verbatim, and wait for the go.

- [ ] **Step 4 — STOP. Fresh dump.**

```bash
ssh neoori /usr/local/bin/neoori-backup.sh   # → "backup: wrote /backups/neoori-<date>.sql.gz (…)"
```

- [ ] **Step 5 — STOP. Apply.**

```bash
ssh neoori 'cd /srv/neoori && docker compose -f docker-compose.prod.yml exec -T backend python purge_retired_parcours.py --apply'
```

- [ ] **Step 6: Verify**

```bash
ssh neoori 'cd /srv/neoori && docker compose -f docker-compose.prod.yml exec -T backend python purge_retired_parcours.py'   # every count at 0
curl -s https://neoori.tech/api/health                                                     # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" "https://neoori.tech/api/prompts/active?path=3"   # 400
```

---

### Task 9: Remove the purge script — after the developer confirms the production purge

- [ ] **Step 1 — STOP.** Wait for the developer to confirm Task 8 Step 6 (every count at 0).
- [ ] **Step 2: Remove the script and its tests; mark the spec done**

```bash
cd $WT
git checkout -b chore/drop-parcours-purge initial
git rm backend/purge_retired_parcours.py backend/tests/test_purge_retired_parcours.py
```

In the spec, replace the `Status:` line with: `Status: implemented; production purged <date of Task 8 Step 5>; purge script removed`.

```bash
cd $WT/backend && $PY -m pytest -q   # 0 failed
cd $WT && git add -A && git commit -m "chore(data): drop the parcours 2/3 purge script

Production is purged; the script and its tests have nothing left to do.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 3 — STOP. Ship it.**

```bash
cd $WT
git checkout initial
git merge --ff-only chore/drop-parcours-purge
git push origin initial
```
