# Le voyage — Phase 4 · Counselor UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a counselor one page — `/voyage/c/<token>` — that reproduces the counselor manual's page-18 synthesis sheet and its five-phase restitution guide, lets them edit, regenerate and validate the portrait draft, keep a private note, and gives the admin the two controls the flow needs (a role select and a voyage KPI row).

**Architecture:** One `"use client"` Next.js page under `frontend/src/app/voyage/c/[token]/page.tsx` fetches `GET /api/voyage/c/<token>` (phase 1) and renders three focused components — `SynthesisSheet` (the page-18 sheet), `RiasecBars` (the manual's bar block) and `RestitutionGuide` (static manual text). The scoring vocabulary arrives as ASCII snake_case, so one new module `frontend/src/lib/voyage-labels.ts` holds the accented French, guarded against drift by a pytest text-parity test in the style of `backend/tests/test_conditions_parity.py`. The only backend change is four counters added to `GET /api/admin/stats`.

**Tech Stack:** Next.js 16 (App Router, `"use client"`), React 19, Tailwind v4 (CSS-first), shadcn/ui over `@base-ui/react`, Flask 3 + Flask-SQLAlchemy, pytest + SQLite in-memory.

**Spec:** docs/superpowers/specs/2026-09-09-voyage-design.md
**Contracts:** docs/superpowers/plans/2026-09-09-voyage-contracts.md

---

## Global Constraints

- **App UI strings are FRENCH.** Code comments, docstrings and commit messages are ENGLISH (`CLAUDE.md` § Language rule).
- **Copy ban list — never in user-facing French chrome:** boussole, copilote, miroir, révélation, épanouissement, alignement, excellence, talent unique, vous vous démarquez. The ban governs chrome we write. It does **not** reach the cahier / counselor-manual text reproduced verbatim (contracts, *Rules that override everything below*) — session 4's own title « Le cadre qui te permet de te révéler » and PHASE 04's « des adultes … qui semblent épanouis » ship as written.
- **The candidate never sees a score or a trait name.** Spec decision 7: « The person never sees a score, a trait name, or a framework name. » `/voyage/c/<token>` is the **only** surface in the app that may. Every task below states that boundary explicitly, and Task 3 enforces it with a test that fails if `lib/voyage-labels.ts` is imported anywhere else.
- **Never required.** Spec decision 11: « Every parcours runs identically with no voyage; the block is simply absent. » Nothing in this phase may make a voyage a precondition for anything.
- **Counselor endpoints need the role AND the token.** Spec § Security: « Counselor endpoints: role **and** token. The synthesis sheet is never reachable by link alone. » Phase 1 enforces this server-side with `@role_required("counselor", "admin")`; Task 7 refuses to fetch client-side for anyone else.
- **Statuses are `String(16)` strings, never native enums** — widening a MySQL ENUM is the one migration step this repo cannot rehearse locally.
- **Current alembic head is `b8c9d0e1f2a3`** (`b8c9d0e1f2a3_add_progress_to_analyses.py`). **This phase adds no migration and must not move the head.** Phases 1's four migrations (`c9d0e1f2a3b4` → `d0e1f2a3b4c5` → `e1f2a3b4c5d6` → `f2a3b4c5d6e7`) are the only ones in this feature.
- **Backend tests:** `pytest`, SQLite in-memory, run from `/Users/imran/Downloads/design_handoff_cv_analyzer/backend` with `pytest`. Fixtures `app`, `client`, `admin_headers` come from `backend/tests/conftest.py`.
- **Next.js caveat** — `frontend/AGENTS.md`: « This is NOT the Next.js you know — APIs, conventions and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. » Every task that touches a Next.js API opens the local doc first. Do not read nextjs.org.
- **No frontend test runner.** Verification is `cd frontend && npm run lint` and `cd frontend && npm run build`, plus manual rows in `TEST-PLAN.md`.
- **Apostrophes.** `react/no-unescaped-entities` is an error in this repo (`eslint-config-next/core-web-vitals`). Two rules, applied without exception:
  1. Chrome we write → typographic `’`, safe as bare JSX text (`d’entretien`).
  2. Verbatim manual / cahier text and anything a pytest parity test compares to Python → keep the source's straight `'`, and put it in a TS string constant or a `{"…"}` expression, never in bare JSX text.
- **Prompts live in the DB (`PromptVersion`), never in code.** This phase writes no prompt text.
- **Never hold a DB connection across an Anthropic stream.** This phase adds no generation code; `POST /portrait/regenerate` (phase 1/2) already spawns the thread.
- **Deploy:** branch `initial` is the deploy branch — `git push` builds images and deploys to https://neoori.tech. Each commit must leave `pytest` green and `npm run build` passing.

### What this phase consumes from earlier phases (cite, do not re-derive)

| From | Signature / shape | Used by |
|---|---|---|
| Phase 0 | `backend/app/services/voyage/bank.py` — `AXES`, `RIASEC_LETTERS`, `RIASEC_UNIVERS`, `BIG5`, `SDT`, `SCHWARTZ`, `STYLES`, `S4_SLOTS` (contracts § A.1–A.2) | Task 3 parity test |
| Phase 1 | `backend/app/models/voyage.py` — `Voyage`, `STATUS_EN_COURS`, `STATUS_S0`, `STATUS_TERMINE`, `CONSENT_VERSION` (contracts § C.1–C.2) | Task 1 |
| Phase 1 | `GET /api/voyage/c/<token>` → `{"voyage": {id, status, prenom, tranche_age, situation, synthesis, portrait}}` (contracts § E10) | Task 7 |
| Phase 1 | `PUT /api/voyage/c/<token>/portrait` `{sections}` → `{"portrait": CounselorPortrait}` (§ E11) | Task 8 |
| Phase 1 | `POST /api/voyage/c/<token>/portrait/regenerate` → `202 {"portrait": …}` (§ E12) | Task 8 |
| Phase 1 | `POST /api/voyage/c/<token>/validate` → `{"portrait": …}` (§ E13) | Task 8 |
| Phase 1 | `GET|PUT /api/voyage/c/<token>/notes` → `{"note": VoyageNote | null}` (§ E14/E15) | Task 9 |
| Phase 1 | `PUT /api/admin/users/<user_id>/role` `{role}` → `{"user": User}` (§ E16) | Task 10 |
| Phase 2 | `generation.PORTRAIT_TITLES` and `FLAG_VOCABULAIRE = "vocabulaire"` (contracts § G.1) | Tasks 2, 8 |
| Phase 3 | `frontend/src/types/voyage.ts` (contracts § I) | Task 2 verifies, creates the counselor half if absent |

### Out of this phase

Candidate hub / player / portrait page, the bank endpoint, generation, prompt slots, migrations, `Analysis.voyage_id`, `_merge_profile()`, `CLAUDE.md`. If one of those looks missing, it belongs to phase 0, 1, 2, 3 or 5 — cite its contract line and move on.

---

## File Structure

| Action | Path | The ONE responsibility |
|---|---|---|
| Modify | `backend/app/routes/admin.py:1-12`, `:24-59` | `GET /api/admin/stats` gains `voyages: {started, s0_done, completed, validated}` |
| Modify | `backend/tests/test_admin.py:1-5`, append at `:182` | the four voyage counters are counted from the right rows |
| Create | `backend/tests/test_voyage_counselor_labels.py` | Python ↔ TypeScript parity for the counselor vocabulary, and the import boundary |
| Create | `frontend/src/lib/voyage-labels.ts` | the accented French for the scoring keys — counselor surface only |
| Modify | `frontend/src/types/voyage.ts` | the counselor half of the API types (only if phase 3 has not landed the file) |
| Create | `frontend/src/components/voyage/RiasecBars.tsx` | the manual's six RIASEC bars, filled to score / computed max |
| Create | `frontend/src/components/voyage/SynthesisSheet.tsx` | the page-18 sheet: all-dimensions table, S0 axes + tensions, S2–S5 boxes |
| Create | `frontend/src/components/voyage/RestitutionGuide.tsx` | the manual's five-phase guide, wording rules, phrases utiles, note prompts |
| Create | `frontend/src/app/voyage/c/[token]/page.tsx` | the counselor surface: role gate, chrome, sheet, portrait editor, notes, guide |
| Modify | `frontend/src/proxy.ts:5` | `/voyage` in `PROTECTED` (idempotent — phase 3 may already have added it) |
| Modify | `frontend/src/app/admin/utilisateurs/page.tsx` | per-row role select wired to `PUT /api/admin/users/<id>/role` |
| Modify | `frontend/src/app/admin/page.tsx:17-22`, `:110-145` | the voyage KPI row |
| Modify | `TEST-PLAN.md` (before « ## What to report back ») | manual rows for the counselor view |

Decomposition rationale: the three components split by **responsibility**, not by layer — `RiasecBars` is the one place a score becomes a width, `RestitutionGuide` is pure static manual text with no props, `SynthesisSheet` is the data-to-sheet mapping. `lib/voyage-labels.ts` is separate from both so exactly one file can be guarded by the boundary test.

---

### Task 1: Voyage stage counters on `GET /api/admin/stats`

**Files:**
- Modify: `backend/app/routes/admin.py:1-12` (imports), `backend/app/routes/admin.py:24-59` (`stats()`)
- Test: `backend/tests/test_admin.py` (append after line 182)

**Interfaces:**
- Consumes: `backend/app/models/voyage.py` — `Voyage`, `STATUS_EN_COURS`, `STATUS_S0`, `STATUS_TERMINE`, `CONSENT_VERSION` (contracts § C.1, phase 1).
- Produces: `GET /api/admin/stats` response gains exactly one key —
  `"voyages": {"started": int, "s0_done": int, "completed": int, "validated": int}` (contracts § E, *Admin*). Task 11 renders it.

**Boundary:** this endpoint returns **counts of rows**, never a score, a trait name or any voyage content. Nothing from `responses_encrypted`, `micro_encrypted` or `portrait_encrypted` may reach it.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_admin.py`, and add the four imports it needs at the top of the file (after line 5):

```python
from uuid import uuid4

from app.models.user import User
from app.models.voyage import (
    CONSENT_VERSION,
    STATUS_EN_COURS,
    STATUS_S0,
    STATUS_TERMINE,
    Voyage,
)
```

```python
# ── Le voyage — the four dashboard counters ──────────────────────────────────
# One Voyage row is one attempt, and a user may have several over time
# (spec decision 3), so "started" counts rows and never people.


def _make_voyage(status=STATUS_EN_COURS, portrait_status="none", sessions=None):
    """A voyage row parked at one stage. The model is phase 1's (contracts § C)."""
    user = User(email=f"voyage-{uuid4().hex[:8]}@test.fr", password_hash="x")
    _db.session.add(user)
    _db.session.commit()

    voyage = Voyage(
        user_id=user.id,
        status=status,
        sessions_completed=sessions if sessions is not None else [],
        consent_at=datetime.utcnow(),
        consent_version=CONSENT_VERSION,
        age_attested=True,
        portrait_status=portrait_status,
    )
    _db.session.add(voyage)
    _db.session.commit()
    return voyage.id


def test_stats_reports_zero_voyages_when_none_exist(client, admin_headers):
    res = client.get("/api/admin/stats", headers=admin_headers)
    assert res.status_code == 200
    assert res.get_json()["voyages"] == {
        "started": 0,
        "s0_done": 0,
        "completed": 0,
        "validated": 0,
    }


def test_stats_counts_each_voyage_stage(client, admin_headers, app):
    with app.app_context():
        _make_voyage(status=STATUS_EN_COURS)
        _make_voyage(status=STATUS_S0, sessions=["0"])
        _make_voyage(
            status=STATUS_TERMINE,
            sessions=["0", "1", "2", "3", "4", "5"],
            portrait_status="draft",
        )
        _make_voyage(
            status=STATUS_TERMINE,
            sessions=["0", "1", "2", "3", "4", "5"],
            portrait_status="validated",
        )

    body = client.get("/api/admin/stats", headers=admin_headers).get_json()
    assert body["voyages"] == {
        "started": 4,     # every row, whatever its stage
        "s0_done": 3,     # s0_termine and termine both mean session 0 is behind them
        "completed": 2,   # status == termine
        "validated": 1,   # portrait_status == validated
    }


def test_stats_voyage_counters_never_carry_content(client, admin_headers, app):
    """The dashboard counts rows. Answers, scores and portrait text stay out."""
    with app.app_context():
        _make_voyage(status=STATUS_TERMINE, portrait_status="validated")

    body = client.get("/api/admin/stats", headers=admin_headers).get_json()
    assert set(body["voyages"]) == {"started", "s0_done", "completed", "validated"}
    assert all(isinstance(v, int) for v in body["voyages"].values())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_admin.py::test_stats_reports_zero_voyages_when_none_exist -v`
Expected: FAIL with `KeyError: 'voyages'`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/routes/admin.py`, add the import after line 9 (`from ..models.counselor_code import CounselorCode`):

```python
from ..models.voyage import STATUS_S0, STATUS_TERMINE, Voyage
```

In `stats()`, insert this block after the `active_prompts` / `by_path` lines (currently lines 44-45) and before `return jsonify({`:

```python
    # Le voyage — one row per attempt (spec decision 3), so "started" is every
    # row. s0_done counts everyone past session 0, which is both the still-open
    # s0_termine rows and the finished ones.
    voyages = {
        "started": Voyage.query.count(),
        "s0_done": Voyage.query.filter(
            Voyage.status.in_((STATUS_S0, STATUS_TERMINE))
        ).count(),
        "completed": Voyage.query.filter_by(status=STATUS_TERMINE).count(),
        "validated": Voyage.query.filter_by(portrait_status="validated").count(),
    }
```

Then add one line to the returned dict, after `"total_tokens_out": total_tokens_out,`:

```python
        "voyages": voyages,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_admin.py -v`
Expected: PASS — every test in the file, including the three new ones.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add backend/app/routes/admin.py backend/tests/test_admin.py
git commit -m "feat(voyage): count the voyage stages on the admin dashboard

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 2: The counselor half of `frontend/src/types/voyage.ts`

**Files:**
- Modify (or create if phase 3 has not landed): `frontend/src/types/voyage.ts`

**Interfaces:**
- Consumes: contracts § I, verbatim.
- Produces, for Tasks 4–9: `CounselorVoyage`, `CounselorVoyageResponse`, `CounselorPortrait`, `CounselorPortraitResponse`, `VoyageSynthesis`, `S0Score`, `RiasecScore`, `S2Score`, `S3Score`, `S4Score`, `S5Score`, `AxisScore`, `AxisTension`, `AxisTop`, `RiasecTop`, `PortraitSections`, `PortraitKey`, `PortraitStatus`, `VoyageStatus`, `SessionId`, `VoyageNote`, `VoyageNoteResponse`, `PORTRAIT_SECTIONS`.

**Boundary:** these are counselor-response types. `S3Score.levels` carries « Élevé / Moyen / Faible » and `S0Score`/`RiasecScore` carry numbers — no candidate page may render a value typed by them.

- [ ] **Step 1: Find out whether phase 3 already shipped the file**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && grep -c "CounselorVoyage" src/types/voyage.ts 2>&1`

- If it prints `1` or more, phase 3 landed the contract's § I file. **Change nothing.** Skip to Step 3.
- If it prints `0` or `No such file or directory`, continue with Step 2.

- [ ] **Step 2: Write the counselor half**

If the file does not exist, create `frontend/src/types/voyage.ts` with exactly this content. If it exists but the grep printed `0`, append everything below the `── counselor` divider and add only the base types it is missing.

```ts
/**
 * Le voyage — API types.
 *
 * Mirrors backend/app/models/voyage.py and backend/app/routes/voyage.py. Bank
 * shapes come from GET /api/voyage/bank; nothing in the cahier is re-typed here.
 */

export type VoyageStatus = "en_cours" | "s0_termine" | "termine"
export type MicroStatus = "none" | "generating" | "success" | "error"
export type PortraitStatus = "none" | "generating" | "draft" | "validated" | "error"
export type SessionId = "0" | "1" | "2" | "3" | "4" | "5"
export type PortraitKey =
  | "accroche" | "qui_tu_es" | "vibrer" | "besoins" | "chemins" | "pas_encore"

// ── voyage (GET/POST /api/voyage) ────────────────────────────────────────────
export interface Voyage {
  id: string
  status: VoyageStatus
  sessions_completed: SessionId[]
  consent_at: string | null
  age_attested: boolean
  has_code: boolean
  micro_status: MicroStatus
  micro_phrase: string | null
  portrait_status: PortraitStatus
  share_token: string | null
  created_at: string
  completed_at: string | null
}
export interface VoyageResponse { voyage: Voyage | null }

// ── portrait (GET /api/voyage/portrait) ──────────────────────────────────────
export type PortraitSections = Record<PortraitKey, string>
export interface CandidatePortrait {
  sections: PortraitSections
  validated_at: string | null
}
export interface CandidatePortraitResponse { portrait: CandidatePortrait }

// ── counselor (GET /api/voyage/c/[token] and friends) ────────────────────────
export interface CounselorPortrait {
  status: PortraitStatus
  sections: Partial<PortraitSections>
  flags: string[]
  edited: boolean
  validated_at: string | null
}
export interface CounselorPortraitResponse { portrait: CounselorPortrait }

export interface AxisScore {
  oui: number; non: number; resultant: number; n_items: number; tension: boolean
}
export interface AxisTension {
  axis: string; resultant: number; label: string; tension: string
}
export interface AxisTop {
  axis: string; resultant: number; pole: "pos" | "neg"; label: string; plain: string
}
export interface RiasecTop {
  letter: string; univers: string; score: number; normalized: number
}
export interface S0Score {
  axes: Record<string, AxisScore>
  tensions: AxisTension[]
  top3: AxisTop[]
}
export interface RiasecScore {
  scores: Record<string, number>
  maxima: Record<string, number>
  normalized: Record<string, number>
  top3: RiasecTop[]
}
export interface S2Score {
  sdt: Record<string, number>
  sdt_dominant: string[]
  schwartz: Record<string, number>
  schwartz_dominant: string[]
  ambivalences: { item_id: string; letter: string; label: string; plain: string }
}
export interface S3Score {
  big5: Record<string, number>
  levels: Record<string, string>
  style: Record<string, number>
  style_dominant: string[]
  intro_extra: string
}
export interface S4Score {
  espace: string; rythme: string; equipe: string
  manager: string; irritant: string; vendredi: string
}
export interface S5Score {
  risque: string; rapport_echec: string; rapport_flou: string
  valeur_centrale: string; trace: string; sacrifice: string; vivant: string
}
export interface VoyageSynthesis {
  scoring_version: string
  s0: S0Score | null
  riasec: RiasecScore | null
  s2: S2Score | null
  s3: S3Score | null
  s4: S4Score | null
  s5: S5Score | null
  completeness: Record<SessionId, boolean>
}

export interface CounselorVoyage {
  id: string
  status: VoyageStatus
  prenom: string | null
  tranche_age: string | null
  situation: string | null
  synthesis: VoyageSynthesis
  portrait: CounselorPortrait
}
export interface CounselorVoyageResponse { voyage: CounselorVoyage }

export interface VoyageNote {
  id: string
  voyage_id: string
  body: string | null
  updated_at: string
}
export interface VoyageNoteResponse { note: VoyageNote | null }

/** Section keys + titles for the portrait, in order. Mirrors
 *  backend/app/services/voyage/generation.py PORTRAIT_TITLES — the API returns the
 *  six bodies keyed but untitled, and both the candidate page and the counselor
 *  editor need the headings. test_voyage_parity.py asserts the two lists match. */
export const PORTRAIT_SECTIONS: { key: PortraitKey; title: string }[] = [
  { key: "accroche",   title: "Phrase d'accroche" },
  { key: "qui_tu_es",  title: "Qui tu es" },
  { key: "vibrer",     title: "Ce qui te fait vibrer" },
  { key: "besoins",    title: "Ce dont tu as besoin" },
  { key: "chemins",    title: "Les chemins possibles" },
  { key: "pas_encore", title: "Ce que ton portrait ne dit pas encore" },
]
```

- [ ] **Step 3: Verify the types compile**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: `✔ No ESLint warnings or errors`

- [ ] **Step 4: Commit (skip if Step 1 said phase 3 already landed the file)**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/types/voyage.ts
git commit -m "feat(voyage): type the counselor responses the sheet reads

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 3: The counselor vocabulary and the boundary that guards it

**Files:**
- Create: `frontend/src/lib/voyage-labels.ts`
- Test: `backend/tests/test_voyage_counselor_labels.py`

**Interfaces:**
- Consumes: `backend/app/services/voyage/bank.py` — `AXES`, `RIASEC_LETTERS`, `RIASEC_UNIVERS`, `BIG5`, `SDT`, `SCHWARTZ`, `STYLES`, `S4_SLOTS` (contracts § A.1–A.2, phase 0). `S4Score` / `S5Score` from `@/types/voyage` (Task 2).
- Produces, for Tasks 4, 5 and 7: `AXIS_ROWS`, `RIASEC_ROWS`, `BIG5_ROWS`, `SDT_ROWS`, `SCHWARTZ_LABELS`, `STYLE_LABELS`, `S4_ROWS`, `S5_ROWS`, `TRANCHE_LABELS`, `SITUATION_LABELS`.

**Boundary:** every string in this module is a framework name, a trait name or a pole label. The last test in this task fails the build if any file outside the three counselor files imports it. That test **is** the boundary, in code.

**Why the file exists at all:** the API returns `"conscienciosite"`, `"autonomie"`, `"A7"` (contracts § B.5) while the manual prints « Conscienciosité », « Autonomie », « Nature du lien ». `S0Score.axes` carries no labels — only `tensions[]` and `top3[]` do — so the ten-axis block on page 18 cannot be rendered from the payload alone.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_voyage_counselor_labels.py`:

```python
"""The counselor sheet's French labels are written twice — keep them honest.

`backend/app/services/voyage/bank.py` owns the scoring vocabulary. The API hands
it to the frontend as ASCII snake_case keys and bare axis ids (contracts § B.5),
so `frontend/src/lib/voyage-labels.ts` carries the accented French the counselor
manual prints. A drift there mislabels a column on the one page in the app
allowed to show scores at all — the counselor would read « Ouverture » over the
névrotisme figure and say the wrong thing out loud in a restitution.

The last test is the other half of the job: spec decision 7 says the person
never sees a score, a trait name or a framework name, so this module may only be
imported by the counselor surface.

There is no JS test runner in this repo, so this reads the TypeScript as text —
the same approach as test_conditions_parity.py.
"""
import re
from pathlib import Path

import pytest

from app.services.voyage import bank

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


def test_the_five_big_five_keys_match(source):
    rows = _entries(_block(source, "BIG5_ROWS"), "key", "label")
    assert [r[0] for r in rows] == list(bank.BIG5)


def test_the_three_sdt_keys_match(source):
    rows = _entries(_block(source, "SDT_ROWS"), "key", "label")
    assert [r[0] for r in rows] == list(bank.SDT)


def test_the_eleven_schwartz_values_match(source):
    assert _record_keys(_block(source, "SCHWARTZ_LABELS", "\n}")) == list(bank.SCHWARTZ)


def test_the_four_styles_match(source):
    assert _record_keys(_block(source, "STYLE_LABELS", "\n}")) == list(bank.STYLES)


def test_the_six_environment_slots_match(source):
    rows = _entries(_block(source, "S4_ROWS"), "key", "label")
    assert sorted(r[0] for r in rows) == sorted(bank.S4_SLOTS)


def test_the_vocabulary_never_leaves_the_counselor_surface():
    """Spec decision 7 — the person never sees a trait name or a framework name."""
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_counselor_labels.py -v`
Expected: FAIL — every test errors on the fixture with
`AssertionError: missing /Users/imran/Downloads/design_handoff_cv_analyzer/frontend/src/lib/voyage-labels.ts`
(the last test fails separately with an empty `importers` set only after the file exists; at this point it passes vacuously).

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/lib/voyage-labels.ts`. The strings use **straight apostrophes**, byte-identical to `bank.py` — the parity test compares them literally:

```ts
/**
 * French display labels for the counselor synthesis sheet.
 *
 * The scoring API returns its vocabulary as ASCII snake_case keys and bare axis
 * ids (contracts § B.5: "conscienciosite", "autonomie", "A7"), and S0Score.axes
 * carries no labels at all — only tensions[] and top3[] do. The counselor
 * manual prints accented French for every one of them, so this file is that
 * display map.
 *
 * Mirrors backend/app/services/voyage/bank.py — AXES, RIASEC_UNIVERS, BIG5,
 * SDT, SCHWARTZ, STYLES, S4_SLOTS. backend/tests/test_voyage_counselor_labels.py
 * reads this file as text and fails when the two drift.
 *
 * COUNSELOR SURFACE ONLY. Every string below is a framework name, a trait name
 * or a pole label. Spec decision 7: the person never sees a score, a trait name
 * or a framework name — so /voyage, /voyage/session/[n] and /voyage/portrait may
 * never import this module. The same test enforces that.
 */
import type { S4Score, S5Score } from "@/types/voyage"

/** The ten S0 bipolar axes, in axis-id order. Mirrors bank.AXES. */
export const AXIS_ROWS: { id: string; label: string; neg: string; pos: string }[] = [
  { id: "A1", label: "Mobilité territoriale", neg: "Ancrage local", pos: "Mobilité / international" },
  { id: "A2", label: "Visibilité", neg: "Discrétion", pos: "Reconnaissance publique" },
  { id: "A3", label: "Rapport au collectif", neg: "Indépendance / solo", pos: "Collectif / équipe" },
  { id: "A4", label: "Échelle d'impact", neg: "Impact local", pos: "Impact global / systémique" },
  { id: "A5", label: "Sécurité vs risque", neg: "Stabilité / salariat", pos: "Risque / entrepreneuriat" },
  { id: "A6", label: "Type de création", neg: "Organisation / méthode", pos: "Expression libre" },
  { id: "A7", label: "Nature du lien", neg: "Systèmes / idées", pos: "Lien humain direct" },
  { id: "A8", label: "Temporalité de l'impact", neg: "Long terme / différé", pos: "Impact immédiat / visible" },
  { id: "A9", label: "Rapport au corps", neg: "Sédentaire / bureau", pos: "Terrain / action physique" },
  { id: "A10", label: "Transmission vs expertise", neg: "Expertise individuelle", pos: "Transmission / enseigner" },
]

/** Tie-break order R I A S E C. Mirrors bank.RIASEC_LETTERS + RIASEC_UNIVERS. */
export const RIASEC_ROWS: { letter: string; univers: string }[] = [
  { letter: "R", univers: "Réaliste" },
  { letter: "I", univers: "Investigateur" },
  { letter: "A", univers: "Artistique" },
  { letter: "S", univers: "Social" },
  { letter: "E", univers: "Entreprenant" },
  { letter: "C", univers: "Conventionnel" },
]

/** Mirrors bank.BIG5, in that order — the manual prints them left to right. */
export const BIG5_ROWS: { key: string; label: string }[] = [
  { key: "ouverture", label: "Ouverture" },
  { key: "conscienciosite", label: "Conscienciosité" },
  { key: "extraversion", label: "Extraversion" },
  { key: "agreabilite", label: "Agréabilité" },
  { key: "nevrotisme", label: "Névrotisme" },
]

/** Mirrors bank.SDT. */
export const SDT_ROWS: { key: string; label: string }[] = [
  { key: "autonomie", label: "Autonomie" },
  { key: "appartenance", label: "Appartenance" },
  { key: "competence", label: "Compétence" },
]

/** Mirrors bank.SCHWARTZ — the eleven values the manual's Dimension column uses. */
export const SCHWARTZ_LABELS: Record<string, string> = {
  autodirection: "Auto-direction",
  stimulation: "Stimulation",
  hedonisme: "Hédonisme",
  reussite: "Réussite",
  pouvoir: "Pouvoir",
  securite: "Sécurité",
  conformite: "Conformité",
  bienveillance: "Bienveillance",
  universalisme: "Universalisme",
  integrite: "Intégrité",
  conservation: "Conservation",
}

/** Mirrors bank.STYLES. */
export const STYLE_LABELS: Record<string, string> = {
  holistique: "Holistique",
  sequentiel: "Séquentiel",
  adaptatif: "Adaptatif",
  consultatif: "Consultatif",
}

/** The manual's « Synthèse environnementale » box. Its four printed cells come
 *  first (S4-1, S4-2, S4-3, S4-5); S4-4 and S4-6 follow, because the paper sheet
 *  has no room for them and the scorer returns all six. */
export const S4_ROWS: { key: keyof S4Score; label: string }[] = [
  { key: "espace", label: "Espace physique idéal (S4-1)" },
  { key: "rythme", label: "Rythme & chronotype (S4-2)" },
  { key: "equipe", label: "Configuration d'équipe (S4-3)" },
  { key: "irritant", label: "Ce qui épuise (S4-5)" },
  { key: "manager", label: "Le manager idéal (S4-4)" },
  { key: "vendredi", label: "Le vendredi soir (S4-6)" },
]

/** The manual's « Synthèse Risque & Sens » box, S5-1 through S5-7. */
export const S5_ROWS: { key: keyof S5Score; label: string }[] = [
  { key: "risque", label: "Appétence au risque (S5-1)" },
  { key: "rapport_echec", label: "L'échec possible (S5-2)" },
  { key: "rapport_flou", label: "Le flou (S5-3)" },
  { key: "valeur_centrale", label: "Valeur centrale (S5-4)" },
  { key: "trace", label: "Type d'impact voulu (S5-5)" },
  { key: "sacrifice", label: "Sacrifice accepté (S5-6)" },
  { key: "vivant", label: "Moment où le jeune se sent vivant(e) (S5-7)" },
]

/** Profile brackets, for the counselor sheet's key-facts strip. Mirrors
 *  backend/app/models/profile.py AGE_BRACKETS / SITUATIONS and the labels
 *  frontend/src/app/profil/page.tsx:36-52 already shows the candidate. */
export const TRANCHE_LABELS: Record<string, string> = {
  moins_25: "Moins de 25 ans",
  "25_34": "25 – 34 ans",
  "35_44": "35 – 44 ans",
  "45_54": "45 – 54 ans",
  "55_plus": "55 ans et plus",
}

export const SITUATION_LABELS: Record<string, string> = {
  en_recherche: "En recherche d'emploi",
  en_reconversion: "En reconversion",
  en_poste_evolution: "En poste, souhaite évoluer",
  premiere_insertion: "Première insertion",
  reprise_apres_pause: "En reprise après une pause",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_counselor_labels.py -v`
Expected: PASS — eight tests.

If `test_the_ten_axes_match` fails, the mismatch is a transcription slip in the TS file, **not** in `bank.py`: `bank.AXES` is the contract's § A.2 and wins.

- [ ] **Step 5: Verify the frontend still compiles**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: `✔ No ESLint warnings or errors`

- [ ] **Step 6: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/lib/voyage-labels.ts backend/tests/test_voyage_counselor_labels.py
git commit -m "feat(voyage): name the scoring vocabulary the counselor sheet prints

The API answers in snake_case; the manual prints accented French. Keep the two
in step with a text-parity test, and fail the suite if the vocabulary is ever
imported outside the counselor surface.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 4: `RiasecBars` — the manual's bar block

**Files:**
- Create: `frontend/src/components/voyage/RiasecBars.tsx`

**Interfaces:**
- Consumes: `RiasecScore` from `@/types/voyage` (Task 2); `RIASEC_ROWS` from `@/lib/voyage-labels` (Task 3); `cn` from `@/lib/utils`.
- Produces: `export function RiasecBars({ riasec }: { riasec: RiasecScore }): JSX.Element` — used by Task 5.

**Boundary:** this component renders a **score** and a **framework letter**. It is one of the three files the Task 3 test allows to import `voyage-labels`. Never import it from a candidate page.

- [ ] **Step 1: Read the local Next.js doc for client components**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && sed -n '1,80p' node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md`
This is the repo's rule from `frontend/AGENTS.md`: read the local guide before writing Next.js code, never nextjs.org. Confirm that `"use client"` at the top of the file is still how a component opts into the client bundle in this version.

- [ ] **Step 2: Write the component**

Create `frontend/src/components/voyage/RiasecBars.tsx`:

```tsx
"use client"

import { cn } from "@/lib/utils"
import { RIASEC_ROWS } from "@/lib/voyage-labels"
import type { RiasecScore } from "@/types/voyage"

/**
 * The counselor manual's page-18 block « Profil RIASEC — Barres de
 * visualisation »: one bar per letter, filled to score / max.
 *
 * The maxima come from the payload, never from a literal. The manual prints
 * E 10 and C 10; the bank computes them from the option table and gets E 11 and
 * C 9 (spec erratum 17), which is what the bar has to divide by. The top three
 * letters are marked because the restitution guide's phase 4 asks the counselor
 * to name exactly those three out loud.
 *
 * COUNSELOR SURFACE ONLY — this draws scores and framework letters.
 */
export function RiasecBars({ riasec }: { riasec: RiasecScore }) {
  const top = new Set(riasec.top3.map((t) => t.letter))

  return (
    <ol className="space-y-1.5">
      {RIASEC_ROWS.map(({ letter, univers }) => {
        const score = riasec.scores[letter] ?? 0
        const max = riasec.maxima[letter] ?? 0
        const pct = max > 0 ? Math.round((score / max) * 100) : 0
        const isTop = top.has(letter)

        return (
          <li
            key={letter}
            className="grid grid-cols-[1.25rem_6.5rem_1fr_3.25rem] items-center gap-2"
          >
            <span
              className={cn(
                "font-mono text-xs font-bold",
                isTop ? "text-orange-dark" : "text-muted-foreground",
              )}
            >
              {letter}
            </span>
            <span
              className={cn(
                "truncate text-xs",
                isTop ? "font-semibold text-navy" : "text-muted-foreground",
              )}
            >
              {univers}
            </span>
            <span
              className="block h-2 w-full overflow-hidden rounded-full bg-secondary"
              aria-hidden="true"
            >
              <span
                className={cn(
                  "block h-full rounded-full",
                  isTop ? "bg-orange" : "bg-navy-500/45",
                )}
                style={{ width: `${pct}%` }}
              />
            </span>
            <span className="text-right font-mono text-xs tabular-nums text-navy">
              {score} / {max}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
```

- [ ] **Step 3: Verify it lints**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: `✔ No ESLint warnings or errors`

- [ ] **Step 4: Verify the boundary test still passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_counselor_labels.py::test_the_vocabulary_never_leaves_the_counselor_surface -v`
Expected: PASS — `components/voyage/RiasecBars.tsx` is in the allowed set.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/components/voyage/RiasecBars.tsx
git commit -m "feat(voyage): draw the RIASEC bars off the computed maxima

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 5: `SynthesisSheet` — the page-18 sheet

#### Binding requirement — marking AI-written text (PM ruling, 2026-09-12)

Decided 2026-09-12 (`docs/superpowers/2026-09-11-voyage-phase-3-handoff.md` §
What phase 4 must know; contracts § E10's amendment note): the counselor
sheet now receives `micro_phrase` / `micro_status` (E10 is nine keys, not
seven). Nobody trained to spot an off-protocol sentence reviews the session-0
phrase before the candidate reads it, and it is weaker-guarded than the
portrait. Phase 4 **must** meet the following — this is a requirement on
this task, not a suggestion:

- **What is marked.** Every block of AI-written text on the counselor sheet:
  the session-0 phrase and the six portrait sections. Nothing else — the
  synthesis table, the RIASEC bars and the S0–S5 boxes are the manual's own
  scoring, not generated prose, and stay unmarked.
- **How.** `border-l-4 border-peach` plus `bg-peach-soft/40` (this repo's
  Tailwind vocabulary — the voyage's accent is peach, used on navy elsewhere
  in the app; peach-on-white here is a tint, never a text colour, so body
  text inside a marked block stays `text-navy` / `text-navy-700` and keeps
  its contrast). One `.ai-block` class in `frontend/src/app/globals.css`,
  beside `.voyage-rule` in the "── Le voyage ──" section, instead of
  repeating the utility string at every call site.
- **The legend**, once, at the top of the sheet — French, vouvoiement,
  sober, no CLAUDE.md ban-list word. Copy it verbatim; do not redraft it:

  > Les blocs teintés sont rédigés par l'IA. La phrase a déjà été montrée à
  > la personne, sans relecture préalable. Le portrait est un brouillon : il
  > ne lui parvient qu'une fois que vous l'avez validé.

- **The phrase block** additionally carries the marker « Déjà affichée à la
  personne » (this exact string), and, when `micro_status !== "success"`,
  the sheet says the phrase could not be written — « La phrase n'a pas pu
  être rédigée. » — rather than rendering an empty tinted block.
- **Why it exists.** The phrase is the only candidate-facing generated text
  with no human gate, and the micro prompt lacks the portrait's `RÈGLE
  DÉFICIT` (`docs/superpowers/2026-09-11-voyage-phase-2-handoff.md`, "Open,
  needing the PM" item 1 — still open). The counselor is the only reviewer
  of it, and the only one who can correct the wording face to face if it
  reads wrong.

**Files:**
- Create: `frontend/src/components/voyage/SynthesisSheet.tsx`

**Interfaces:**
- Consumes: `VoyageSynthesis` from `@/types/voyage` (Task 2); `AXIS_ROWS`, `BIG5_ROWS`, `S4_ROWS`, `S5_ROWS`, `SCHWARTZ_LABELS`, `SDT_ROWS`, `STYLE_LABELS` from `@/lib/voyage-labels` (Task 3); `RiasecBars` (Task 4); `Badge` from `@/components/ui/badge`; `cn` from `@/lib/utils`.
- Produces: `export function SynthesisSheet({ synthesis }: { synthesis: VoyageSynthesis }): JSX.Element` — used by Task 7.

**Boundary:** the whole component is scores, trait names and framework names — the manual's own sheet. It exists for one page. No candidate surface may render it, and the Task 3 test fails the suite if it is imported anywhere else.

**Layout being reproduced** (counselor manual, page 18 « SYNTHÈSE Vue d'ensemble — Profil complet du jeune »), in order:
1. « Tableau de synthèse — Toutes dimensions » — 4 columns × 11 rows.
2. « Profil RIASEC — Barres de visualisation ».
3. The ten S0 axes with their tension marks (the manual's session-0 grid, « Axes en tension (score entre −2 et +2) — à reporter dans la synthèse »).
4. « Tensions S0 — Ambivalences à explorer », with the manual's ×1.5 note.
5. « Synthèse — Besoins SDT dominants ».
6. « Synthèse Big Five — Profil cognitif ».
7. « Synthèse environnementale ».
8. « Synthèse Risque & Sens ».
9. « Phrase d'accroche provisoire du portrait (1 phrase — cf. top 3 axes + S5-7) ».

Every section value can be `null` (contracts § B.5: sections for incomplete sessions are `None`). A `share_token` only exists once S5 is done, so in practice they are filled — but the types say otherwise and the sheet renders « Session N non terminée. » rather than crashing.

- [ ] **Step 1: Write the component**

Create `frontend/src/components/voyage/SynthesisSheet.tsx`:

```tsx
"use client"

import type { ReactNode } from "react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
  AXIS_ROWS,
  BIG5_ROWS,
  S4_ROWS,
  S5_ROWS,
  SCHWARTZ_LABELS,
  SDT_ROWS,
  STYLE_LABELS,
} from "@/lib/voyage-labels"
import type { VoyageSynthesis } from "@/types/voyage"

import { RiasecBars } from "./RiasecBars"

const DASH = "—"

const join = (parts: (string | undefined)[], sep = " · ") =>
  parts.filter(Boolean).join(sep) || DASH

const signed = (n: number) => (n > 0 ? `+${n}` : String(n))

const sdtLabel = (key: string) => SDT_ROWS.find((r) => r.key === key)?.label ?? key
const big5Label = (key: string) => BIG5_ROWS.find((r) => r.key === key)?.label ?? key

/** The values just under the dominant one — the manual's « Secondaire » cell. */
function secondary(counts: Record<string, number>, dominant: string[]): string[] {
  const top = dominant.length > 0 ? counts[dominant[0]] ?? 0 : 0
  const below = Object.entries(counts).filter(([, n]) => n > 0 && n < top)
  if (below.length === 0) return []
  const best = Math.max(...below.map(([, n]) => n))
  return below.filter(([, n]) => n === best).map(([key]) => key)
}

function Block({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: ReactNode
}) {
  return (
    <section className="print-break mt-5 rounded-lg border border-border p-4">
      <h3 className="font-display text-sm font-semibold text-navy">{title}</h3>
      {subtitle ? <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p> : null}
      <div className="mt-3">{children}</div>
    </section>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="eyebrow text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-medium text-navy">{value || DASH}</p>
    </div>
  )
}

function Missing({ n }: { n: string }) {
  return <p className="text-sm text-muted-foreground">{`Session ${n} non terminée.`}</p>
}

/**
 * The counselor manual's page-18 sheet, filled from the API instead of by hand:
 * the all-dimensions table, the RIASEC bars, the ten S0 axes with their tension
 * marks, the sessions 2-5 synthesis boxes and the accroche ingredients.
 *
 * Section values are null when a session is unfinished (contracts § B.5), so
 * every block renders a « non terminée » line rather than assuming.
 *
 * COUNSELOR SURFACE ONLY (spec decision 7): scores, trait names and framework
 * names appear here and nowhere else in the app.
 */
export function SynthesisSheet({ synthesis }: { synthesis: VoyageSynthesis }) {
  const { s0, riasec, s2, s3, s4, s5 } = synthesis

  const highLevel = (level: string) =>
    s3 ? BIG5_ROWS.filter((r) => s3.levels[r.key] === level).map((r) => big5Label(r.key)) : []

  const rows: { dimension: string; session: string; resultat: string; signal: string }[] = [
    {
      dimension: "Axes bipolaires (S0)",
      session: "Session 0",
      resultat: s0 ? join(s0.top3.map((t) => t.label), " / ") : DASH,
      signal: s0 ? `Tensions : ${s0.tensions.length}` : DASH,
    },
    {
      dimension: "RIASEC top 3",
      session: "Session 1",
      resultat: riasec ? riasec.top3.map((t) => `${t.univers} ${t.score}`).join(" / ") : DASH,
      signal: riasec ? `Combinaison : ${riasec.top3.map((t) => t.letter).join("")}` : DASH,
    },
    {
      dimension: "Valeurs Schwartz",
      session: "Session 2",
      resultat: s2 ? join(s2.schwartz_dominant.map((k) => SCHWARTZ_LABELS[k] ?? k)) : DASH,
      signal: s2
        ? `Secondaire : ${join(
            secondary(s2.schwartz, s2.schwartz_dominant).map((k) => SCHWARTZ_LABELS[k] ?? k),
          )}`
        : DASH,
    },
    {
      dimension: "Besoin SDT dominant",
      session: "Session 2",
      resultat: s2 ? join(s2.sdt_dominant.map(sdtLabel)) : DASH,
      signal:
        s2 && s2.sdt_dominant.length > 0
          ? `Score : ${s2.sdt[s2.sdt_dominant[0]] ?? 0}`
          : DASH,
    },
    {
      dimension: "Big Five dominant",
      session: "Session 3",
      resultat: s3 ? `Traits élevés : ${join(highLevel("Élevé"), ", ")}` : DASH,
      signal: s3 ? `Traits faibles : ${join(highLevel("Faible"), ", ")}` : DASH,
    },
    {
      dimension: "Style cognitif",
      session: "Session 3",
      resultat: s3 ? join(s3.style_dominant.map((k) => STYLE_LABELS[k] ?? k)) : DASH,
      signal: s3 ? s3.intro_extra : DASH,
    },
    {
      dimension: "Profil sensoriel",
      session: "Session 4",
      resultat: s4 ? join([s4.espace, s4.rythme, s4.equipe]) : DASH,
      signal: s4 ? `Irritant : ${s4.irritant}` : DASH,
    },
    {
      dimension: "Appétence risque",
      session: "Session 5",
      resultat: s5 ? s5.risque : DASH,
      signal: s5 ? join([s5.rapport_echec, s5.rapport_flou]) : DASH,
    },
    {
      dimension: "Valeur centrale",
      session: "Session 5",
      resultat: s5 ? s5.valeur_centrale : DASH,
      signal: DASH,
    },
    {
      dimension: "Type d'impact",
      session: "Session 5",
      resultat: s5 ? s5.trace : DASH,
      signal: s5 ? `Sacrifice : ${s5.sacrifice}` : DASH,
    },
    {
      dimension: "Sens — Moment vivant",
      session: "Session 5",
      resultat: s5 ? s5.vivant : DASH,
      signal: DASH,
    },
  ]

  return (
    <div>
      <h2 className="eyebrow text-orange-dark">Synthèse · vue d’ensemble</h2>

      <Block title="Tableau de synthèse — Toutes dimensions">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] text-left text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="eyebrow py-1 pr-2 text-muted-foreground">Dimension</th>
                <th className="eyebrow py-1 pr-2 text-muted-foreground">Session</th>
                <th className="eyebrow py-1 pr-2 text-muted-foreground">Résultat</th>
                <th className="eyebrow py-1 text-muted-foreground">Signal fort ?</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.dimension} className="border-b border-border/60 align-top">
                  <td className="py-1.5 pr-2 font-medium text-navy">{r.dimension}</td>
                  <td className="py-1.5 pr-2 text-muted-foreground">{r.session}</td>
                  <td className="py-1.5 pr-2 text-navy">{r.resultat}</td>
                  <td className="py-1.5 text-muted-foreground">{r.signal}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Block>

      <Block title="Profil RIASEC — Barres de visualisation">
        {riasec ? <RiasecBars riasec={riasec} /> : <Missing n="1" />}
      </Block>

      <Block
        title="Axes bipolaires — Session 0"
        subtitle={"Résultante = OUI moins NON sur les affirmations qui chargent l'axe."}
      >
        {s0 ? (
          <ul className="space-y-1.5">
            {AXIS_ROWS.map(({ id, label, neg, pos }) => {
              const axis = s0.axes[id]
              return (
                <li
                  key={id}
                  className="grid grid-cols-[1.75rem_1fr_auto] items-center gap-2 border-b border-border/50 pb-1.5 last:border-0"
                >
                  <span className="font-mono text-[11px] text-muted-foreground">{id}</span>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-medium text-navy">{label}</p>
                    <p className="truncate text-[11px] text-muted-foreground">
                      {`${neg} ← → ${pos}`}
                    </p>
                  </div>
                  <div className="flex items-center justify-end gap-2">
                    <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                      {axis ? `${axis.oui} ✓ / ${axis.non} ✗` : DASH}
                    </span>
                    <span
                      className={cn(
                        "w-8 text-right font-mono text-xs font-bold tabular-nums",
                        axis?.tension ? "text-orange-dark" : "text-navy",
                      )}
                    >
                      {axis ? signed(axis.resultant) : DASH}
                    </span>
                    {axis?.tension ? (
                      <Badge variant="warning">tension</Badge>
                    ) : (
                      <span className="w-[4.25rem]" aria-hidden="true" />
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        ) : (
          <Missing n="0" />
        )}
      </Block>

      <Block
        title="Tensions S0 — Ambivalences à explorer"
        subtitle="Les tensions (score S0 entre −2 et +2) sont les signaux les plus informatifs. Elles pondèrent ×1.5 le portrait."
      >
        {!s0 ? (
          <Missing n="0" />
        ) : s0.tensions.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune tension relevée.</p>
        ) : (
          <ul className="space-y-2">
            {s0.tensions.map((t) => (
              <li key={t.axis} className="rounded-md bg-secondary p-3">
                <p className="text-xs font-semibold text-navy">
                  {t.label}{" "}
                  <span className="font-mono font-normal text-muted-foreground">
                    ({t.axis} · {signed(t.resultant)})
                  </span>
                </p>
                {/* The question is the restitution guide's own phase-03 line,
                    with this axis dropped into the manual's [axe] slot. */}
                <p className="mt-1 text-xs italic text-muted-foreground">
                  {`« J'ai noté une ambivalence sur ${t.tension}. Tu as autant coché des deux côtés. Qu'est-ce que ça t'évoque ? »`}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Block>

      <Block title="Synthèse — Besoins SDT dominants">
        {s2 ? (
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-3">
              {SDT_ROWS.map(({ key, label }) => (
                <div
                  key={key}
                  className={cn(
                    "rounded-md p-3 text-center",
                    s2.sdt_dominant.includes(key) ? "bg-peach-soft" : "bg-secondary",
                  )}
                >
                  <p className="text-xs font-semibold text-navy">{label}</p>
                  <p className="mt-1 font-mono text-lg font-bold tabular-nums text-navy">
                    {s2.sdt[key] ?? 0}
                  </p>
                </div>
              ))}
            </div>
            <Field
              label={"Valeur centrale dominante (Schwartz) du jeune"}
              value={join(s2.schwartz_dominant.map((k) => SCHWARTZ_LABELS[k] ?? k))}
            />
            <Field
              label="Valeurs secondaires"
              value={join(
                secondary(s2.schwartz, s2.schwartz_dominant).map((k) => SCHWARTZ_LABELS[k] ?? k),
              )}
            />
            <Field
              label={"Ambivalences identifiées (S2-7) — à explorer en restitution"}
              value={`${s2.ambivalences.label} — ${s2.ambivalences.plain}`}
            />
          </div>
        ) : (
          <Missing n="2" />
        )}
      </Block>

      <Block title="Synthèse Big Five — Profil cognitif">
        {s3 ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              {BIG5_ROWS.map(({ key, label }) => (
                <div key={key} className="rounded-md bg-secondary p-2 text-center">
                  <p className="text-[11px] font-medium text-muted-foreground">{label}</p>
                  <p className="mt-0.5 text-sm font-semibold text-navy">
                    {s3.levels[key] ?? DASH}
                  </p>
                  <p className="font-mono text-[11px] tabular-nums text-muted-foreground">
                    {signed(s3.big5[key] ?? 0)}
                  </p>
                </div>
              ))}
            </div>
            <Field
              label={"Style cognitif dominant (holistique / séquentiel / adaptatif / consultatif)"}
              value={join(s3.style_dominant.map((k) => STYLE_LABELS[k] ?? k))}
            />
            <Field
              label={"Signaux d'introversion / extraversion à noter pour la restitution"}
              value={s3.intro_extra}
            />
          </div>
        ) : (
          <Missing n="3" />
        )}
      </Block>

      <Block title="Synthèse environnementale">
        {s4 ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {S4_ROWS.map(({ key, label }) => (
              <Field key={key} label={label} value={s4[key]} />
            ))}
          </div>
        ) : (
          <Missing n="4" />
        )}
      </Block>

      <Block title="Synthèse Risque & Sens">
        {s5 ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {S5_ROWS.map(({ key, label }) => (
              <Field key={key} label={label} value={s5[key]} />
            ))}
          </div>
        ) : (
          <Missing n="5" />
        )}
      </Block>

      <Block
        title={"Phrase d'accroche provisoire du portrait"}
        subtitle={"1 phrase — cf. top 3 axes + S5-7"}
      >
        <div className="space-y-3">
          <Field
            label="Top 3 axes"
            value={s0 ? join(s0.top3.map((t) => t.label)) : DASH}
          />
          <Field label={"Se sent vivant(e) quand"} value={s5 ? s5.vivant : DASH} />
        </div>
      </Block>
    </div>
  )
}
```

- [ ] **Step 2: Verify it lints and type-checks**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint && npm run build`
Expected: `✔ No ESLint warnings or errors`, then a successful build ending in `✓ Compiled successfully` and the route table. The component is not yet imported by a page, so no new route appears.

- [ ] **Step 3: Verify the boundary test still passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_counselor_labels.py -v`
Expected: PASS — eight tests. `components/voyage/SynthesisSheet.tsx` is in the allowed set.

- [ ] **Step 4: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/components/voyage/SynthesisSheet.tsx
git commit -m "feat(voyage): reproduce the manual's page-18 synthesis sheet

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 6: `RestitutionGuide` — the manual's five-phase guide

**Files:**
- Create: `frontend/src/components/voyage/RestitutionGuide.tsx`

**Interfaces:**
- Consumes: nothing. Static content, no props, no data, no API call.
- Produces: `export function RestitutionGuide(): JSX.Element` and `export const NOTE_PROMPTS: string[]` — used by Tasks 7 and 9.

**Boundary:** the guide names RIASEC out loud (« Nommer les 3 univers RIASEC »). That is the counselor's script, on the counselor's page. It is never rendered to a candidate.

**Source:** counselor manual page 23, « RESTITUTION Guide de conduite de l'entretien », plus page 2's « Rappel — Principes du wording de restitution » and the closing « Phrases utiles en restitution » list. Reproduced verbatim, including PHASE 05's « Simulateur d'aménagement » — that tool is out of v1 (spec § Out of scope), but the phase is a paper protocol the counselor runs in the room, not an app feature. Also reproduced verbatim: PHASE 04's « des adultes autour de toi qui semblent épanouis dans leur travail », whose root is on the CLAUDE.md ban list. The ban governs chrome we write, not manual text we reproduce (contracts, *Rules that override everything below*).

All strings live in TS constants rather than in JSX text so the manual's straight apostrophes survive untouched — a bare `'` in JSX trips `react/no-unescaped-entities`.

- [ ] **Step 1: Write the component**

Create `frontend/src/components/voyage/RestitutionGuide.tsx`:

```tsx
"use client"

/**
 * The counselor manual's page-23 guide, reproduced verbatim: five phases, the
 * page-2 wording rules and the « Phrases utiles en restitution » list.
 *
 * Static content — no props and no data. Every string sits in a TS constant
 * rather than in JSX text, so the manual's straight apostrophes survive
 * untouched (a bare « ' » in JSX trips react/no-unescaped-entities).
 *
 * Reproduced as written, including PHASE 05's « Simulateur d'aménagement »: the
 * simulator is out of v1 (spec § Out of scope), but this page is a paper
 * protocol the counselor runs in the room, not a feature index.
 *
 * COUNSELOR SURFACE ONLY — the guide names the frameworks out loud.
 */

const GUIDE_TITLE = "Guide de conduite de l'entretien"
const GUIDE_SUBTITLE = "Durée totale recommandée : 40 min · 5 phases"
const WORDING_TITLE = "Rappel — Principes du wording de restitution"
const PHRASES_TITLE = "Phrases utiles en restitution"

const PHASES: { n: string; title: string; duration: string; rows: [string, string][] }[] = [
  {
    n: "01",
    title: "Accueil & posture",
    duration: "5 min",
    rows: [
      [
        "Rappel du cadre",
        "Confidentialité · Pas de bonne réponse · Le portrait dit « ce que tu m'as dit de toi »",
      ],
      [
        "Posture du conseiller",
        "Ami intelligent, pas expert RH. Curiosité, pas jugement. Laisser des silences.",
      ],
      [
        "Ouverture",
        "Demander au jeune : « Qu'est-ce qui t'a surpris dans les questions ? » avant de lire le portrait.",
      ],
    ],
  },
  {
    n: "02",
    title: "Lecture du portrait",
    duration: "10 min",
    rows: [
      [
        "Lire à voix haute",
        "La phrase d'accroche en premier. Pause. Observer la réaction.",
      ],
      [
        "Vérifier la résonance",
        "« Est-ce que tu te reconnais là-dedans ? » — Ne pas argumenter si le jeune dit non.",
      ],
      [
        "Ajuster si besoin",
        "Si un élément ne correspond pas, c'est une donnée. Creuser : « Qu'est-ce qui ne colle pas ? »",
      ],
      [
        "Section 5 (chemins)",
        "Ne pas nommer de métier. Laisser le jeune faire le lien lui-même.",
      ],
    ],
  },
  {
    n: "03",
    title: "Exploration des tensions",
    duration: "10 min",
    rows: [
      [
        "Nommer les tensions S0",
        "« J'ai noté une ambivalence sur [axe]. Tu as autant coché des deux côtés. Qu'est-ce que ça t'évoque ? »",
      ],
      [
        "Questions ouvertes",
        "« À quel moment tu te sens le plus toi-même ? » · « Qu'est-ce qui te manquerait si... ? »",
      ],
      [
        "Valeur centrale (S5-4)",
        "« Ce qui te met en colère, c'est [valeur bafouée]. Comment tu vois ça dans ce qui t'attire professionnellement ? »",
      ],
    ],
  },
  {
    n: "04",
    title: "Les chemins possibles",
    duration: "10 min",
    rows: [
      [
        "Repartir du RIASEC",
        "Nommer les 3 univers RIASEC (ex : « Réaliste, Entreprenant, Investigateur ») et leur traduction concrète.",
      ],
      [
        "Environnement avant métier",
        "Demander : « Dans quel type de lieu tu t'imagines travailler ? » — Taille structure, terrain/bureau, rythme.",
      ],
      [
        "Associations",
        "« Si tu penses à des adultes autour de toi qui semblent épanouis dans leur travail — qu'est-ce qu'ils ont en commun ? »",
      ],
      [
        "3 pistes concrètes",
        "Proposer 3 univers professionnels (pas des métiers) en lien avec le profil. Inviter le jeune à en explorer 1.",
      ],
    ],
  },
  {
    n: "05",
    title: "Clôture & suite",
    duration: "5 min",
    rows: [
      [
        "Résumé en 3 mots",
        "Demander au jeune : « Si tu devais résumer ce que tu retiens en 3 mots, ce serait quoi ? »",
      ],
      [
        "Simulateur d'aménagement",
        "Proposer si pertinent. Expliquer : « Ça va plus loin — ça aide à formuler ce dont tu as besoin pour bien travailler. »",
      ],
      [
        "Action concrète",
        "1 action entre maintenant et la prochaine séance : une recherche, une rencontre, une visite.",
      ],
      [
        "Mot final",
        "Terminer par : « Ce portrait n'est pas ce que tu dois devenir. C'est ce que tu es déjà. »",
      ],
    ],
  },
]

/** Page 2 — what never to say, and what to say instead. */
const WORDING: [string, string][] = [
  ["« Tu es... »", "« Tu as tendance à... » / « Tu sembles plus à l'aise quand... »"],
  [
    "« Tu es créatif. »",
    "« Tu es créatif lorsque tu as une marge de liberté. » — Trait + Condition.",
  ],
  [
    "« manque », « faible », « limite »",
    "« moins stimulant pour toi » / « peut te demander plus d'énergie »",
  ],
  ["« handicap », « difficulté »", "« besoin spécifique », « préférence cognitive »"],
  [
    "« résultats », « score »",
    "« ce que tu m'as dit de toi » / « ce que je lis dans tes choix »",
  ],
]

const PHRASES: string[] = [
  "« Ce n'est pas moi qui te dis qui tu es. C'est toi qui me l'as dit, à travers tes choix. »",
  "« Il n'y a pas de profil idéal. Il y a un profil qui correspond à des environnements. »",
  "« Ce dont tu as besoin n'est pas un problème à résoudre. C'est une information à utiliser. »",
  "« On cherche pas le métier. On cherche d'abord le cadre dans lequel tu te révèles. »",
  "« Ce portrait n'est pas ce que tu dois devenir. C'est ce que tu es déjà. »",
]

/** The manual's « Mes notes de restitution » prompts. The page shows them above
 *  the private note field, which is where the counselor answers them. */
export const NOTE_PROMPTS: string[] = [
  "Réaction du jeune à la phrase d'accroche :",
  "Ce qui l'a le plus surpris / touché :",
  "Ce qu'il/elle a nuancé ou contesté :",
  "Action retenue pour la prochaine séance :",
]

function TwoColumnTable({
  head,
  rows,
}: {
  head: [string, string]
  rows: [string, string][]
}) {
  return (
    <table className="w-full text-left text-xs">
      <thead>
        <tr className="border-b border-border">
          <th className="eyebrow w-1/3 py-1 pr-3 text-muted-foreground">{head[0]}</th>
          <th className="eyebrow py-1 text-muted-foreground">{head[1]}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([left, right]) => (
          <tr key={left} className="border-b border-border/60 align-top">
            <td className="py-1.5 pr-3 font-medium text-navy">{left}</td>
            <td className="py-1.5 leading-relaxed text-muted-foreground">{right}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function RestitutionGuide() {
  return (
    <div className="mt-8">
      <h2 className="eyebrow text-orange-dark">Restitution</h2>
      <h3 className="mt-1 font-display text-lg font-bold text-navy">{GUIDE_TITLE}</h3>
      <p className="mt-0.5 text-xs text-muted-foreground">{GUIDE_SUBTITLE}</p>

      <section className="print-break mt-4 rounded-lg border border-border p-4">
        <h4 className="font-display text-sm font-semibold text-navy">{WORDING_TITLE}</h4>
        <div className="mt-3">
          <TwoColumnTable head={["À ne jamais dire", "À utiliser à la place"]} rows={WORDING} />
        </div>
      </section>

      {PHASES.map((phase) => (
        <section key={phase.n} className="print-break mt-4 rounded-lg border border-border p-4">
          <div className="flex items-baseline justify-between gap-3">
            <h4 className="font-display text-sm font-semibold text-navy">
              {`PHASE ${phase.n} — ${phase.title}`}
            </h4>
            <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
              {phase.duration}
            </span>
          </div>
          <div className="mt-3">
            <TwoColumnTable head={["Point clé", "Comment faire"]} rows={phase.rows} />
          </div>
        </section>
      ))}

      <section className="print-break mt-4 rounded-lg bg-peach-soft p-4">
        <h4 className="font-display text-sm font-semibold text-navy">{PHRASES_TITLE}</h4>
        <ul className="mt-2 space-y-1.5">
          {PHRASES.map((phrase) => (
            <li key={phrase} className="text-xs leading-relaxed text-navy">
              {phrase}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
```

- [ ] **Step 2: Verify it lints and builds**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint && npm run build`
Expected: `✔ No ESLint warnings or errors` then `✓ Compiled successfully`. In particular no `react/no-unescaped-entities` error — every apostrophe is inside a TS string.

- [ ] **Step 3: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/components/voyage/RestitutionGuide.tsx
git commit -m "feat(voyage): reproduce the five-phase restitution guide

Verbatim from the counselor manual, wording rules and phrases utiles included.
The strings live in TS constants so the manual's apostrophes survive the JSX
escaping rule untouched.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 7: The counselor page — role gate, chrome, sheet and guide

**Files:**
- Create: `frontend/src/app/voyage/c/[token]/page.tsx`
- Modify: `frontend/src/proxy.ts:5`

**Interfaces:**
- Consumes: `GET /api/voyage/c/<token>` → `{"voyage": CounselorVoyage}` (contracts § E10, phase 1); `SynthesisSheet` (Task 5); `RestitutionGuide` (Task 6); `TRANCHE_LABELS`, `SITUATION_LABELS` (Task 3); `api`, `ApiError` from `@/lib/api`; `useAuth` from `@/lib/auth`.
- Produces: the route `/voyage/c/[token]`, and the module-level `PORTRAIT_STATUS_LABELS` and `load()` that Tasks 8 and 9 extend.

**Boundary — the whole point of this task.** Two gates stand in front of the only page that may show a score:
1. **Server:** `@role_required("counselor", "admin")` **and** the token (contracts § E, *Counselor endpoints*). A candidate with the right link gets `403 {"error": "Accès non autorisé."}`.
2. **Client:** the block below never calls the API for a user who is not `counselor` or `admin`, so a candidate who opens the URL sees a refusal card and no request is made.
The proxy edit adds a third, coarser gate: no token cookie, no page.

- [ ] **Step 1: Read the local Next.js docs for dynamic routes and the proxy**

Run:
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend
sed -n '1,60p' node_modules/next/dist/docs/01-app/03-api-reference/04-functions/use-params.md
sed -n '1,80p' node_modules/next/dist/docs/01-app/01-getting-started/16-proxy.md
```
`frontend/AGENTS.md` — « This is NOT the Next.js you know … Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. » Confirm from those two files that (a) `useParams<{ token: string }>()` in a `"use client"` component is how this version reads `[token]`, and (b) `src/proxy.ts` exporting `proxy()` plus `config.matcher` is the current convention. Do not read nextjs.org.

- [ ] **Step 2: Add `/voyage` to the protected routes (idempotent)**

Open `frontend/src/proxy.ts`. Line 5 currently reads:

```ts
const PROTECTED = ["/admin", "/profil"]
```

If `/voyage` is already in the list, phase 3 added it — leave the file alone. Otherwise replace that line with:

```ts
const PROTECTED = ["/admin", "/profil", "/voyage"]
```

- [ ] **Step 3: Write the page**

Create `frontend/src/app/voyage/c/[token]/page.tsx`:

```tsx
"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Printer, ShieldAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Logo } from "@/components/brand/Logo"
import { RestitutionGuide } from "@/components/voyage/RestitutionGuide"
import { SynthesisSheet } from "@/components/voyage/SynthesisSheet"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { SITUATION_LABELS, TRANCHE_LABELS } from "@/lib/voyage-labels"
import type {
  CounselorVoyage,
  CounselorVoyageResponse,
  PortraitStatus,
} from "@/types/voyage"

/** The portrait lifecycle in the counselor's words. Chrome, not manual text. */
const PORTRAIT_STATUS_LABELS: Record<PortraitStatus, string> = {
  none: "Pas encore rédigé",
  generating: "Rédaction en cours…",
  draft: "Brouillon à relire",
  validated: "Validé et transmis",
  error: "Échec de la rédaction",
}

/**
 * Counselor surface for le voyage — the synthesis sheet, the portrait draft and
 * the restitution guide.
 *
 * THIS IS THE ONLY PAGE IN THE APP THAT MAY SHOW A SCORE, A TRAIT NAME OR A
 * FRAMEWORK NAME (spec decision 7). Two gates stand in front of it: the API
 * needs the counselor/admin role *and* the token (contracts § E, counselor
 * endpoints), and the guard below refuses to fetch anything for anyone else, so
 * a candidate holding the link never even triggers a request. Nothing here may
 * be copied into /voyage, /voyage/session/[n] or /voyage/portrait.
 */
export default function VoyageCounselorPage() {
  const { token } = useParams<{ token: string }>()
  const { user, loading: authLoading } = useAuth()
  const allowed = user?.role === "counselor" || user?.role === "admin"

  const [data, setData] = useState<CounselorVoyage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await api.get<CounselorVoyageResponse>(`/voyage/c/${token}`)
      setData(res.voyage)
      setError(null)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur de chargement.")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (authLoading) return
    if (!allowed) {
      setLoading(false)
      return
    }
    void load()
  }, [authLoading, allowed, load])

  // ── gate ───────────────────────────────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-secondary px-5">
        <Skeleton className="h-40 w-full max-w-sm rounded-2xl" />
      </div>
    )
  }

  if (!allowed) {
    return (
      <div className="grid min-h-screen place-items-center bg-secondary px-5">
        <div className="max-w-sm rounded-2xl bg-card p-8 text-center ring-1 ring-foreground/10 shadow-card">
          <Logo className="mx-auto text-2xl" />
          <ShieldAlert className="mx-auto mt-6 size-6 text-destructive" aria-hidden="true" />
          <h1 className="mt-3 font-display text-lg font-bold text-navy">Accès non autorisé.</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {user
              ? "Cette fiche est réservée aux conseillers. Votre portrait apparaît sur votre espace dès qu’un conseiller l’a validé."
              : "Connectez-vous avec un compte conseiller pour ouvrir cette fiche."}
          </p>
          <Button
            render={<Link href={user ? "/espace" : `/connexion?redirect=/voyage/c/${token}`} />}
            variant="outline"
            size="lg"
            className="mt-6"
          >
            {user ? "Mon espace" : "Se connecter"}
          </Button>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="grid min-h-screen place-items-center bg-secondary px-5">
        <div className="max-w-sm rounded-2xl bg-card p-8 text-center ring-1 ring-foreground/10 shadow-card">
          <Logo className="mx-auto text-2xl" />
          <h1 className="mt-6 font-display text-lg font-bold text-navy">{error}</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Vérifiez le lien avec la personne qui vous l’a transmis.
          </p>
          <Button render={<Link href="/espace" />} variant="outline" size="lg" className="mt-6">
            Mon espace
          </Button>
        </div>
      </div>
    )
  }

  const prenom = data?.prenom ?? "—"
  const facts: [string, string][] = [
    ["Prénom", prenom],
    [
      "Tranche d’âge",
      data?.tranche_age ? TRANCHE_LABELS[data.tranche_age] ?? data.tranche_age : "—",
    ],
    ["Situation", data?.situation ? SITUATION_LABELS[data.situation] ?? data.situation : "—"],
    ["Portrait", data ? PORTRAIT_STATUS_LABELS[data.portrait.status] : "—"],
  ]

  return (
    <div className="min-h-screen bg-secondary">
      {/* Action bar */}
      <div className="no-print sticky top-0 z-40 flex items-center justify-between gap-3 border-b border-border bg-secondary/95 px-5 py-3 backdrop-blur-sm sm:px-8">
        <Button render={<Link href="/espace" />} variant="ghost" size="sm">
          <ArrowLeft className="size-3.5" /> Mon espace
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={loading}
          onClick={() => setTimeout(() => window.print(), 50)}
        >
          <Printer className="size-3.5" /> PDF fiche
        </Button>
      </div>

      <div className="px-4 py-8">
        <div className="report-shell">
          <div className="report-rule" />

          <div className="bg-navy px-8 pb-6 pt-6 text-white">
            <div className="flex items-center justify-between gap-3">
              <Logo tone="light" className="text-base" />
              <Badge variant="peach">VERSION CONSEILLER</Badge>
            </div>
            <h1 className="mt-3 font-display text-2xl font-extrabold leading-tight text-white">
              Le voyage · {prenom}
            </h1>
            <p className="mt-1 text-sm text-peach">
              Fiche de synthèse, portrait à relire et guide d’entretien
            </p>
          </div>

          <div className="px-8 py-7">
            {/* The boundary, said out loud on the page itself. */}
            <p className="mb-6 rounded-lg border border-orange/30 bg-peach-soft px-4 py-3 text-xs leading-relaxed text-navy">
              Document conseiller. Cette fiche porte des résultats chiffrés et des noms de tests :
              elle ne se montre pas au candidat. Le portrait qu’il recevra, lui, est écrit sans ces
              termes.
            </p>

            {loading ? (
              <div className="mb-7 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (
                  <Skeleton key={i} className="h-12" />
                ))}
              </div>
            ) : (
              <div className="mb-7 grid grid-cols-1 gap-3 rounded-lg bg-secondary p-4 text-xs sm:grid-cols-2 lg:grid-cols-4">
                {facts.map(([label, value]) => (
                  <div key={label}>
                    <p className="eyebrow text-muted-foreground">{label}</p>
                    <p className="mt-1 font-semibold text-navy">{value}</p>
                  </div>
                ))}
              </div>
            )}

            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-24" />
                ))}
              </div>
            ) : data ? (
              <SynthesisSheet synthesis={data.synthesis} />
            ) : null}

            <RestitutionGuide />
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Verify it lints and builds**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint && npm run build`
Expected: `✔ No ESLint warnings or errors`, then `✓ Compiled successfully` and a route table that now contains `/voyage/c/[token]`.

- [ ] **Step 5: Verify the boundary test still passes**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_counselor_labels.py -v`
Expected: PASS — eight tests. `app/voyage/c/[token]/page.tsx` is in the allowed set; nothing else imports the vocabulary.

- [ ] **Step 6: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/app/voyage/c/\[token\]/page.tsx frontend/src/proxy.ts
git commit -m "feat(voyage): open the counselor sheet behind the counselor role

The token alone is not enough: the API needs the role too, and the page refuses
to fetch for anyone else, so a candidate holding the link never sees a score.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 8: The portrait draft — leak banner, six-textarea editor, regenerate, validate

**Files:**
- Modify: `frontend/src/app/voyage/c/[token]/page.tsx` (created in Task 7)

**Interfaces:**
- Consumes: `PUT /api/voyage/c/<token>/portrait` `{sections}` → `{"portrait": CounselorPortrait}` (§ E11); `POST /api/voyage/c/<token>/portrait/regenerate` → `202 {"portrait": …}` (§ E12); `POST /api/voyage/c/<token>/validate` → `{"portrait": …}` (§ E13); `PORTRAIT_SECTIONS` and `PortraitSections` from `@/types/voyage` (Task 2); `FLAG_VOCABULAIRE = "vocabulaire"`, the only value the backend writes into `portrait.flags` (contracts § G.1).
- Produces: nothing new for later tasks; Task 9 appends below the guide.

**Boundary:** the portrait itself is the candidate-safe artefact — plain prose, no framework words. The leak banner exists precisely because generation may have failed at that (spec decision 16), and the counselor is the last human check before the candidate sees it. Editing it here does not make this page candidate-facing.

**Two behaviours to get right:**
- **Seeding.** The six fields are filled from the server once per draft. Re-seeding on every poll tick or every save response would wipe what the counselor is typing, so a signature ref guards it and `regenerate` clears the ref deliberately.
- **Blank sections.** `PUT` answers a blank section with `{"errors": [...]}`, and `frontend/src/lib/api.ts:43` only surfaces `body.error ?? body.message`, so an `errors` array degrades to « Erreur inattendue. ». The client checks for blanks first and names the missing sections itself.

- [ ] **Step 1: Extend the imports**

In `frontend/src/app/voyage/c/[token]/page.tsx`, replace the import block written in Task 7 with:

```tsx
import { useCallback, useEffect, useRef, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import {
  ArrowLeft,
  Check,
  Loader2,
  Printer,
  RefreshCw,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { Logo } from "@/components/brand/Logo"
import { RestitutionGuide } from "@/components/voyage/RestitutionGuide"
import { SynthesisSheet } from "@/components/voyage/SynthesisSheet"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { fmtDateTime } from "@/lib/format"
import { SITUATION_LABELS, TRANCHE_LABELS } from "@/lib/voyage-labels"
import {
  PORTRAIT_SECTIONS,
  type CounselorPortraitResponse,
  type CounselorVoyage,
  type CounselorVoyageResponse,
  type PortraitSections,
  type PortraitStatus,
} from "@/types/voyage"
```

- [ ] **Step 2: Add the module-level helpers**

Directly under the `PORTRAIT_STATUS_LABELS` constant, add:

```tsx
/** The flag generation writes when framework vocabulary survived two attempts
 *  (contracts § G.1, FLAG_VOCABULAIRE). */
const FLAG_VOCABULAIRE = "vocabulaire"

const EMPTY_SECTIONS: PortraitSections = {
  accroche: "",
  qui_tu_es: "",
  vibrer: "",
  besoins: "",
  chemins: "",
  pas_encore: "",
}

/** The API may return a partial draft (contracts § I: Partial<PortraitSections>);
 *  the six textareas need all six keys. */
const fillSections = (partial: Partial<PortraitSections>): PortraitSections => ({
  accroche: partial.accroche ?? "",
  qui_tu_es: partial.qui_tu_es ?? "",
  vibrer: partial.vibrer ?? "",
  besoins: partial.besoins ?? "",
  chemins: partial.chemins ?? "",
  pas_encore: partial.pas_encore ?? "",
})
```

- [ ] **Step 3: Add the editor state, the two effects and the three handlers**

Inside the component, directly after the `useEffect` that calls `load()`, insert:

```tsx
  // ── portrait draft ─────────────────────────────────────────────────────────
  const [sections, setSections] = useState<PortraitSections>(EMPTY_SECTIONS)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [regenerating, setRegenerating] = useState(false)
  const [confirmRegen, setConfirmRegen] = useState(false)
  const [validating, setValidating] = useState(false)
  const seededRef = useRef("")

  const portraitStatus = data?.portrait.status

  useEffect(() => {
    if (!data || data.portrait.status === "generating") return
    // Seed the six fields once per draft. Re-seeding on every poll tick or on
    // every save response would wipe what the counselor is typing.
    const signature = `${data.portrait.status}:${data.portrait.validated_at ?? ""}`
    if (seededRef.current === signature) return
    seededRef.current = signature
    setSections(fillSections(data.portrait.sections))
  }, [data])

  useEffect(() => {
    if (portraitStatus !== "generating") return
    // Same cadence as the candidate hub (spec § Frontend): poll every 2 s while
    // the model is writing. The interval clears itself when the status moves.
    const id = setInterval(() => {
      void load()
    }, 2000)
    return () => clearInterval(id)
  }, [portraitStatus, load])

  const saveDraft = async () => {
    const missing = PORTRAIT_SECTIONS.filter(({ key }) => !sections[key].trim())
    if (missing.length > 0) {
      // The API answers a blank section with {"errors": [...]}, and lib/api.ts
      // only surfaces `error`/`message` — so name the gap here rather than let
      // the counselor read "Erreur inattendue.".
      setActionError(
        `À compléter avant d’enregistrer : ${missing.map((m) => m.title).join(", ")}.`,
      )
      return
    }
    setSaving(true)
    setActionError(null)
    try {
      const res = await api.put<CounselorPortraitResponse>(
        `/voyage/c/${token}/portrait`,
        { sections },
      )
      setData((current) => (current ? { ...current, portrait: res.portrait } : current))
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Échec de l’enregistrement.")
    } finally {
      setSaving(false)
    }
  }

  const regenerate = async () => {
    // Two-click confirmation: regeneration replaces the text in the fields.
    if (!confirmRegen) {
      setConfirmRegen(true)
      return
    }
    setConfirmRegen(false)
    setRegenerating(true)
    setActionError(null)
    seededRef.current = "" // let the new draft repopulate the fields
    try {
      const res = await api.post<CounselorPortraitResponse>(
        `/voyage/c/${token}/portrait/regenerate`,
        {},
      )
      setData((current) => (current ? { ...current, portrait: res.portrait } : current))
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Échec de la régénération.")
    } finally {
      setRegenerating(false)
    }
  }

  const validate = async () => {
    setValidating(true)
    setActionError(null)
    try {
      const res = await api.post<CounselorPortraitResponse>(
        `/voyage/c/${token}/validate`,
        {},
      )
      setData((current) => (current ? { ...current, portrait: res.portrait } : current))
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Échec de la validation.")
    } finally {
      setValidating(false)
    }
  }
```

- [ ] **Step 4: Render the portrait section**

In the JSX, find the block Task 7 wrote:

```tsx
            ) : data ? (
              <SynthesisSheet synthesis={data.synthesis} />
            ) : null}

            <RestitutionGuide />
```

Replace it with:

```tsx
            ) : data ? (
              <SynthesisSheet synthesis={data.synthesis} />
            ) : null}

            {/* ── Portrait ───────────────────────────────────────────────── */}
            {data ? (
              <section className="mt-8">
                <h2 className="eyebrow text-orange-dark">Portrait</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {PORTRAIT_STATUS_LABELS[data.portrait.status]}
                  {data.portrait.edited ? " · modifié par un conseiller" : ""}
                  {data.portrait.validated_at
                    ? ` · validé le ${fmtDateTime(data.portrait.validated_at)}`
                    : ""}
                </p>

                {data.portrait.flags.includes(FLAG_VOCABULAIRE) ? (
                  <div className="no-print mt-3 flex gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-xs leading-relaxed text-destructive">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                    <p>
                      Vocabulaire à vérifier : la rédaction a gardé des termes techniques — noms de
                      tests, de traits ou de résultats — après une seconde tentative. Relisez et
                      réécrivez les passages concernés avant de valider.
                    </p>
                  </div>
                ) : null}

                {data.portrait.status === "generating" ? (
                  <p className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                    Rédaction en cours. Cette page se met à jour toute seule.
                  </p>
                ) : (
                  <>
                    {/* Editor — screen only */}
                    <div className="no-print mt-4 space-y-4">
                      {PORTRAIT_SECTIONS.map(({ key, title }) => (
                        <div key={key}>
                          <label
                            htmlFor={`portrait-${key}`}
                            className="text-sm font-semibold text-navy"
                          >
                            {title}
                          </label>
                          <Textarea
                            id={`portrait-${key}`}
                            value={sections[key]}
                            onChange={(e) =>
                              setSections((current) => ({ ...current, [key]: e.target.value }))
                            }
                            className="mt-1 min-h-24 bg-background text-sm"
                          />
                        </div>
                      ))}

                      {actionError ? (
                        <p className="text-xs text-destructive">{actionError}</p>
                      ) : null}

                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {data.portrait.status === "draft" ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={regenerating}
                            onClick={regenerate}
                          >
                            <RefreshCw className="size-3.5" />
                            {confirmRegen ? "Confirmer : réécrire le brouillon" : "Régénérer"}
                          </Button>
                        ) : null}
                        <Button variant="outline" size="sm" disabled={saving} onClick={saveDraft}>
                          {saved ? (
                            <>
                              <Check className="size-3.5 text-success" /> Enregistré
                            </>
                          ) : saving ? (
                            "Enregistrement…"
                          ) : (
                            "Enregistrer"
                          )}
                        </Button>
                        {data.portrait.status === "draft" ? (
                          <Button
                            variant="navy"
                            size="sm"
                            disabled={validating}
                            onClick={validate}
                          >
                            {validating ? "Transmission…" : "Valider et transmettre"}
                          </Button>
                        ) : null}
                      </div>

                      {data.portrait.status === "validated" ? (
                        <p className="text-right text-xs text-success">
                          Transmis au candidat. Vos corrections restent enregistrables.
                        </p>
                      ) : null}
                    </div>

                    {/* Print mirror — what the counselor carries into the room */}
                    <div className="hidden print:block">
                      {PORTRAIT_SECTIONS.map(({ key, title }) => (
                        <div key={key} className="print-break mt-4">
                          <h3 className="font-display text-sm font-semibold text-navy">{title}</h3>
                          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                            {sections[key] || "—"}
                          </p>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </section>
            ) : null}

            <RestitutionGuide />
```

- [ ] **Step 5: Verify it lints and builds**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint && npm run build`
Expected: `✔ No ESLint warnings or errors`, then `✓ Compiled successfully`.
If `react-hooks/exhaustive-deps` complains about the polling effect, the fix is the `portraitStatus` local from Step 3 — do not silence the rule with a disable comment.

- [ ] **Step 6: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/app/voyage/c/\[token\]/page.tsx
git commit -m "feat(voyage): let the counselor edit, regenerate and validate the portrait

The draft seeds the six fields once so a poll tick never eats what is being
typed, and blank sections are named client-side because the API's errors array
does not survive lib/api.ts.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 9: The counselor's private note

**Files:**
- Modify: `frontend/src/app/voyage/c/[token]/page.tsx`

**Interfaces:**
- Consumes: `GET /api/voyage/c/<token>/notes` → `{"note": VoyageNote | null}` (§ E14); `PUT /api/voyage/c/<token>/notes` `{body}` → `{"note": VoyageNote}` (§ E15); `NOTE_PROMPTS` from `@/components/voyage/RestitutionGuide` (Task 6).
- Produces: nothing later tasks consume.

**Boundary:** the note is the counselor's own text, kept per `(voyage_id, counselor_id)` (contracts § C.7), never shown to the candidate and never printed — the block carries `no-print`, exactly like `frontend/src/app/c/[token]/page.tsx:158`.

- [ ] **Step 1: Extend the imports**

In the import block, add `NOTE_PROMPTS` to the `RestitutionGuide` import and `VoyageNoteResponse` to the types import:

```tsx
import { NOTE_PROMPTS, RestitutionGuide } from "@/components/voyage/RestitutionGuide"
```

```tsx
import {
  PORTRAIT_SECTIONS,
  type CounselorPortraitResponse,
  type CounselorVoyage,
  type CounselorVoyageResponse,
  type PortraitSections,
  type PortraitStatus,
  type VoyageNoteResponse,
} from "@/types/voyage"
```

- [ ] **Step 2: Add the note state, its loader and its saver**

Inside the component, after the `validate` handler from Task 8, insert:

```tsx
  // ── private note ───────────────────────────────────────────────────────────
  const [note, setNote] = useState("")
  const [noteSaving, setNoteSaving] = useState(false)
  const [noteSaved, setNoteSaved] = useState(false)
  const [noteError, setNoteError] = useState(false)

  useEffect(() => {
    if (authLoading || !allowed) return
    // One note per (voyage, counselor) — contracts § C.7. A miss is silent: an
    // empty field is the right starting state either way.
    api
      .get<VoyageNoteResponse>(`/voyage/c/${token}/notes`)
      .then((res) => {
        if (res.note?.body) setNote(res.note.body)
      })
      .catch(() => {})
  }, [authLoading, allowed, token])

  const saveNote = async () => {
    setNoteSaving(true)
    setNoteError(false)
    try {
      await api.put(`/voyage/c/${token}/notes`, { body: note })
      setNoteSaved(true)
      setTimeout(() => setNoteSaved(false), 2000)
    } catch {
      setNoteError(true)
    } finally {
      setNoteSaving(false)
    }
  }
```

- [ ] **Step 3: Render the note block**

In the JSX, replace the closing lines:

```tsx
            <RestitutionGuide />
          </div>
        </div>
      </div>
    </div>
  )
}
```

with:

```tsx
            <RestitutionGuide />

            {/* Counselor notes — private, and never printed into the fiche */}
            <div className="no-print mt-8 rounded-lg border border-dashed border-border bg-card p-5">
              <h3 className="font-display text-sm font-semibold text-navy">
                Mes notes de restitution
              </h3>
              <p className="mt-1 text-xs italic text-muted-foreground">
                Champ libre · enregistré sur votre espace conseiller — non partagé avec le candidat.
              </p>
              <ul className="mt-3 space-y-0.5 text-xs text-muted-foreground">
                {NOTE_PROMPTS.map((prompt) => (
                  <li key={prompt}>{prompt}</li>
                ))}
              </ul>
              <Textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Ce que vous retenez de l’entretien…"
                className="mt-3 min-h-[120px] bg-background text-sm"
              />
              {noteError ? (
                <p className="mt-2 text-xs text-destructive">
                  Échec de l’enregistrement. Réessayez.
                </p>
              ) : null}
              <div className="mt-3 flex justify-end">
                <Button size="sm" variant="outline" onClick={saveNote} disabled={noteSaving}>
                  {noteSaved ? (
                    <>
                      <Check className="size-3.5 text-success" /> Enregistré
                    </>
                  ) : noteSaving ? (
                    "Enregistrement…"
                  ) : (
                    "Enregistrer"
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Verify it lints and builds**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint && npm run build`
Expected: `✔ No ESLint warnings or errors`, then `✓ Compiled successfully`.

- [ ] **Step 5: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/app/voyage/c/\[token\]/page.tsx
git commit -m "feat(voyage): keep the counselor's restitution notes on the voyage

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 10: The role select on `/admin/utilisateurs`

**Files:**
- Modify: `frontend/src/app/admin/utilisateurs/page.tsx:1-23` (imports and helpers), `:26-37` (state), `:59-61` (subtitle), `:132-136` (the role cell)

**Interfaces:**
- Consumes: `PUT /api/admin/users/<user_id>/role` `{"role": "counselor"}` → `200 {"user": User}`; `400 {"error": "Rôle invalide."}`; `409 {"error": "Impossible de retirer le dernier rôle administrateur."}` (contracts § E16, phase 1). `roleLabel` from `@/lib/format`.
- Produces: nothing later tasks consume.

**Why it exists:** spec decision 19 — « No endpoint today gives a user the `counselor` role; without one nobody can validate a portrait. » This select is the only way to create the counselor who uses Task 7's page.

**Boundary:** roles only. This page shows no voyage content of any kind.

- [ ] **Step 1: Swap the read-only role badge for a select**

In `frontend/src/app/admin/utilisateurs/page.tsx`:

**a.** Replace the import block at lines 1-18 with:

```tsx
"use client"

import { useEffect, useMemo, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { api, ApiError } from "@/lib/api"
import { fmtDate, planLabel, roleLabel } from "@/lib/format"
import type { User } from "@/types"
import { Search, Users } from "lucide-react"
```

**b.** Replace `roleVariant` (lines 20-21) with the role list. `roleVariant` becomes unused once the badge is gone, and an unused const fails `npm run lint` — delete it, do not comment it out:

```tsx
/** The three values the API accepts (contracts § E16). */
const ROLE_OPTIONS: User["role"][] = ["candidate", "counselor", "admin"]
```

**c.** After the `query` state (line 29), add:

```tsx
  const [savingId, setSavingId] = useState<string | null>(null)
  const [rowError, setRowError] = useState<Record<string, string>>({})

  const changeRole = async (id: string, role: string) => {
    setSavingId(id)
    setRowError((current) => ({ ...current, [id]: "" }))
    try {
      const res = await api.put<{ user: User }>(`/admin/users/${id}/role`, { role })
      setUsers((list) => list.map((u) => (u.id === res.user.id ? res.user : u)))
    } catch (err) {
      // The API refuses to demote the last admin with a 409 and a French
      // sentence — show it on the row rather than swallowing it.
      setRowError((current) => ({
        ...current,
        [id]: err instanceof ApiError ? err.message : "Échec de la modification.",
      }))
    } finally {
      setSavingId(null)
    }
  }
```

**d.** Replace the page subtitle at lines 59-61:

```tsx
        <p className="mt-1 text-sm text-muted-foreground">
          Liste des comptes. Le rôle est modifiable : un conseiller peut ouvrir les fiches de
          synthèse et valider les portraits du voyage.
        </p>
```

**e.** Replace the role cell at lines 132-136:

```tsx
                    <TableCell>
                      <Select
                        value={u.role}
                        onValueChange={(v) => {
                          if (typeof v === "string" && v !== u.role) void changeRole(u.id, v)
                        }}
                      >
                        <SelectTrigger
                          size="sm"
                          className="w-36"
                          disabled={savingId === u.id}
                          aria-label={`Rôle de ${u.email}`}
                        >
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLE_OPTIONS.map((role) => (
                            <SelectItem key={role} value={role}>
                              {roleLabel(role)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {rowError[u.id] ? (
                        <p className="mt-1 text-[11px] text-destructive">{rowError[u.id]}</p>
                      ) : null}
                    </TableCell>
```

`Badge` stays imported — the plan column at lines 137-141 still uses it.

- [ ] **Step 2: Verify it lints and builds**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint && npm run build`
Expected: `✔ No ESLint warnings or errors`, then `✓ Compiled successfully`.
A `'roleVariant' is assigned a value but never used` error means step 1b was skipped.

- [ ] **Step 3: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/app/admin/utilisateurs/page.tsx
git commit -m "feat(admin): change a user's role from the users table

Nobody could be made a counselor before this, so nobody could validate a
portrait.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 11: The voyage KPI row on `/admin`

**Files:**
- Modify: `frontend/src/app/admin/page.tsx:17-22` (the `Stats` interface), `:110-145` (after the KPI strip)

**Interfaces:**
- Consumes: `GET /api/admin/stats` → `voyages: {started, s0_done, completed, validated}` (Task 1).
- Produces: nothing later tasks consume.

**Boundary:** four integers. No voyage content reaches this page.

- [ ] **Step 1: Widen the `Stats` interface**

In `frontend/src/app/admin/page.tsx`, replace lines 17-22 with:

```tsx
interface Stats {
  total_analyses: number; success_count: number; error_count: number
  timeout_count: number; success_rate: number; conversion_rate: number
  total_tokens_in: number; total_tokens_out: number
  active_prompt: PromptVersion | null
  /** Optional so a frontend build that lands ahead of the backend still renders
   *  the rest of the dashboard — same reasoning as the active_prompt fallback in
   *  backend/app/routes/admin.py:57. */
  voyages?: { started: number; s0_done: number; completed: number; validated: number }
}
```

- [ ] **Step 2: Add the KPI row**

Immediately after the KPI strip's closing `</div>` (currently line 145) and before the `<div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.4fr_1fr]">` that opens the two panels, insert:

```tsx
      {/* Le voyage — one row per attempt (spec decision 3), so "commencés"
          counts attempts, not people. */}
      {!loading && stats?.voyages ? (
        <div>
          <p className="eyebrow mb-2 text-muted-foreground">Le voyage</p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard
              label="Voyages commencés"
              value={fmtInt(stats.voyages.started)}
              hint="Tous statuts confondus"
            />
            <StatCard
              label="Session 0 terminée"
              value={fmtInt(stats.voyages.s0_done)}
              hint="Phrase générée"
            />
            <StatCard
              label="Voyages terminés"
              value={fmtInt(stats.voyages.completed)}
              hint="Les six sessions"
            />
            <StatCard
              label="Portraits validés"
              value={fmtInt(stats.voyages.validated)}
              hint="Transmis au candidat"
            />
          </div>
        </div>
      ) : null}
```

- [ ] **Step 3: Verify it lints and builds**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint && npm run build`
Expected: `✔ No ESLint warnings or errors`, then `✓ Compiled successfully`.

- [ ] **Step 4: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/app/admin/page.tsx
git commit -m "feat(admin): show the voyage stages on the overview

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 12: Manual test rows for the counselor view

**Files:**
- Modify: `TEST-PLAN.md` (a new top-level section, inserted before « ## What to report back »)

**Interfaces:**
- Consumes: everything Tasks 1 and 7–11 shipped.
- Produces: the PM-facing acceptance rows. There is no frontend test runner, so these rows **are** the regression suite for this phase.

**Boundary:** rows 3, 4 and 5 below exist to prove the boundary in the browser: a candidate holding a valid token must see no score, no trait name and no portrait text.

- [ ] **Step 1: Pick the section number**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer && grep -oE '^## [0-9]+' TEST-PLAN.md | tail -1`
Expected today: `## 11`. The new section is that number **+ 1** — so `12` as the file stands. If phase 3 already added a voyage section (`## 12 · Le voyage`), this grep returns `## 12` and the new section is `13`; renumber every row below from `12.x` to `13.x`.

- [ ] **Step 2: Insert the section**

Insert immediately before the line `## What to report back` (currently line 213):

```markdown
## 12 · Le voyage — vue conseiller

Prerequisites: one candidate account that has finished the five sessions (its
voyage row is `termine` with `portrait_status` = `draft`) and its `share_token`;
one second account to promote; one admin account.

| # | Do | Expect |
|---|---|---|
| 12.1 | Logged out, open `/voyage/c/<token>` | Redirected to `/connexion?redirect=/voyage/c/<token>`. The fiche never renders |
| 12.2 | Log in as the **candidate who played**, open `/voyage/c/<token>` | A card saying « Accès non autorisé. » — no numbers, no trait names, no portrait text anywhere on the page. Open the network tab: no request to `/api/voyage/c/...` was made |
| 12.3 | As admin, open `/admin/utilisateurs`, set the second account's role select to « conseiller » | The select shows « conseiller » straight away, no page reload, no error under the row |
| 12.4 | Still in `/admin/utilisateurs`, try to set the **only** admin account to « candidat » | The row shows « Impossible de retirer le dernier rôle administrateur. » and the select goes back to « administrateur » on reload |
| 12.5 | Log in as the new conseiller, open `/voyage/c/<token>` | The fiche renders: navy band, badge « VERSION CONSEILLER », title « Le voyage · <prénom> », then the warning strip « Document conseiller… » |
| 12.6 | Read the key-facts strip | Prénom, tranche d'âge and situation are in French words (« 25 – 34 ans », « En recherche d'emploi »), not `25_34` / `en_recherche` |
| 12.7 | Read « Tableau de synthèse — Toutes dimensions » | Eleven rows, from « Axes bipolaires (S0) » to « Sens — Moment vivant », each with a session and a result |
| 12.8 | Read « Profil RIASEC — Barres de visualisation » | Six bars, R I A S E C in that order, each labelled `n / max`. The maxima read **R 12 · I 11 · A 10 · S 10 · E 11 · C 9** — not 10/10 for E and C. The top three are orange |
| 12.9 | Read « Axes bipolaires — Session 0 » | Ten rows A1…A10, each with its French name, its two poles, its ✓/✗ counts and its resultant. Only rows with a « tension » badge are between −2 and +2 — and **A1 never carries one** |
| 12.10 | Read « Tensions S0 — Ambivalences à explorer » | The ×1.5 note, then one card per tension with the question « J'ai noté une ambivalence sur … » |
| 12.11 | Read the four session boxes | « Besoins SDT dominants » with three counters, « Big Five — Profil cognitif » with five Élevé/Moyen/Faible cells, « Synthèse environnementale » with six lines, « Synthèse Risque & Sens » with seven |
| 12.12 | Scroll to « Restitution » | The wording rappel table, then PHASE 01 to PHASE 05 with their durations (5/10/10/10/5 min), then « Phrases utiles en restitution » with five quotes |
| 12.13 | Edit « Phrase d'accroche », click « Enregistrer » | Button flips to « Enregistré » with a green check. Reload the page: the edit is still there and the status line now says « · modifié par un conseiller » |
| 12.14 | Empty one textarea, click « Enregistrer » | An inline red line « À compléter avant d'enregistrer : <section>. » — nothing is sent to the server |
| 12.15 | Click « Régénérer », then « Confirmer : réécrire le brouillon » | The editor is replaced by « Rédaction en cours. Cette page se met à jour toute seule. » and, within a few seconds and with no reload, a new draft fills the six fields |
| 12.16 | If the red banner « Vocabulaire à vérifier » appears | Read the draft: it should be the reason — a test name, a trait name or the word « score » survived into the prose. Rewrite that passage before validating |
| 12.17 | Click « Valider et transmettre » | Status becomes « Validé et transmis · validé le <date> ». « Régénérer » and « Valider » disappear; « Enregistrer » stays |
| 12.18 | Log back in as the candidate, open `/voyage/portrait` | The six sections are there — the same text the conseiller validated, and nothing else from the fiche |
| 12.19 | Back on the fiche, type in « Mes notes de restitution », click « Enregistrer », reload | The note comes back. Log in as a *different* conseiller and open the same fiche: the note field is empty (notes are per conseiller) |
| 12.20 | Click « PDF fiche » | The print preview shows the synthesis sheet, the portrait as prose (not as textareas) and the restitution guide. It does **not** show the action bar, the buttons or the notes |
| 12.21 | `/admin` overview | A « Le voyage » row of four tiles: Voyages commencés / Session 0 terminée / Voyages terminés / Portraits validés, with the counts you would expect from the rows you created |

---
```

- [ ] **Step 3: Commit**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add TEST-PLAN.md
git commit -m "docs(voyage): add the counselor-view rows to the manual test plan

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 13: Full verification

**Files:**
- Modify: none expected. This task proves the phase is green end to end and, only if the tree is dirty, commits what is left.

**Interfaces:**
- Consumes: everything above.
- Produces: a green suite and a deployable branch.

**Boundary:** step 2's `test_the_vocabulary_never_leaves_the_counselor_surface` is the machine-checkable form of « the candidate never sees a score or a trait name ». If it fails, stop — do not weaken the allow-list, remove the import.

- [ ] **Step 1: Run the whole backend suite**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest`
Expected: PASS — every test in `backend/tests/`, with no failures, no errors and no new warnings. The run includes the three new admin tests from Task 1 and the eight parity/boundary tests from Task 3.

- [ ] **Step 2: Re-run the boundary test on its own and read the output**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && pytest tests/test_voyage_counselor_labels.py -v`
Expected: PASS — eight tests, ending in `8 passed`. The last one, `test_the_vocabulary_never_leaves_the_counselor_surface`, must pass with the importer set being exactly `app/voyage/c/[token]/page.tsx`, `components/voyage/SynthesisSheet.tsx` and `components/voyage/RiasecBars.tsx`.

- [ ] **Step 3: Confirm the alembic head did not move**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && grep -rl "down_revision = " migrations/versions | wc -l && git -C /Users/imran/Downloads/design_handoff_cv_analyzer status --short backend/migrations`
Expected: the migration count is unchanged from before this phase and `git status` prints nothing for `backend/migrations` — phase 4 adds no migration and must not move the head off phase 1's `f2a3b4c5d6e7` (or `b8c9d0e1f2a3` if phase 1 has not landed yet).

- [ ] **Step 4: Lint and build the frontend**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint && npm run build`
Expected: `✔ No ESLint warnings or errors`, then a successful production build ending in `✓ Compiled successfully` and a route table listing `/voyage/c/[token]` alongside `/admin` and `/admin/utilisateurs`.

- [ ] **Step 5: Confirm the tree is clean**

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer && git status --short && git log --oneline -12`
Expected: `git status --short` prints nothing (`.next/` is git-ignored), and the log shows the phase's commits, newest first:
`docs(voyage): add the counselor-view rows…`, `feat(admin): show the voyage stages…`, `feat(admin): change a user's role…`, `feat(voyage): keep the counselor's restitution notes…`, `feat(voyage): let the counselor edit, regenerate and validate…`, `feat(voyage): open the counselor sheet behind the counselor role`, `feat(voyage): reproduce the five-phase restitution guide`, `feat(voyage): reproduce the manual's page-18 synthesis sheet`, `feat(voyage): draw the RIASEC bars…`, `feat(voyage): name the scoring vocabulary…`, `feat(voyage): count the voyage stages…`.

If anything is uncommitted, commit it now:

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add -A
git commit -m "chore(voyage): finish the counselor UI phase

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

- [ ] **Step 6: Deploy**

`initial` is the deploy branch: pushing builds both images and rolls them out to the VPS.

Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer && git push`
Expected: GitHub Actions builds `ghcr.io/alltoft/neoori-frontend` and `ghcr.io/alltoft/neoori-backend`, syncs the config and runs `docker compose … up -d` on the VPS. Then walk § 12 of `TEST-PLAN.md` against https://neoori.tech.

Rollback, if § 12 fails on the live site: `IMAGE_TAG=<previous-commit-sha> docker compose -f docker-compose.prod.yml up -d` on the VPS (`DOCKER.md`).
