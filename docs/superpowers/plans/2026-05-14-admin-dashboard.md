# Admin Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full admin dashboard — 6 multi-page routes with shared layout, 5 new/updated backend endpoints, and a new `CounselorCode` model.

**Architecture:** Flat Next.js App Router routes under `/admin/` share a single `layout.tsx` nav bar. Each page is a `"use client"` component fetching its own data. Flask backend gains new endpoints on the existing `admin_bp` blueprint plus a new `CounselorCode` SQLAlchemy model with migration.

**Tech Stack:** Next.js 16 (App Router, `"use client"`), Flask 3, Flask-SQLAlchemy, Flask-JWT-Extended, shadcn/ui, Tailwind CSS, pytest + SQLite (tests)

---

## File Map

### Backend — new/modified
| Action | Path | Responsibility |
|---|---|---|
| Create | `backend/tests/conftest.py` | pytest fixtures: in-memory app, admin JWT headers |
| Create | `backend/tests/test_admin.py` | tests for all new/updated admin endpoints |
| Create | `backend/requirements-dev.txt` | pytest + pytest-flask |
| Modify | `backend/app/config.py` | add `TestingConfig` (SQLite in-memory, JWT via headers) |
| Create | `backend/app/models/counselor_code.py` | `CounselorCode` model + `to_dict()` |
| Modify | `backend/app/__init__.py` | import `counselor_code` model for Alembic detection |
| Modify | `backend/app/routes/admin.py` | add 5 endpoints; update analyses filter |

### Frontend — new/modified
| Action | Path | Responsibility |
|---|---|---|
| Create | `frontend/src/app/admin/layout.tsx` | shared nav bar with active-link routing |
| Modify | `frontend/src/app/admin/page.tsx` | condensed overview: KPIs + sparklines + mini panels |
| Create | `frontend/src/app/admin/prompts/page.tsx` | full prompt editor + version history |
| Create | `frontend/src/app/admin/analyses/page.tsx` | paginated log + status/date/search filters |
| Create | `frontend/src/app/admin/utilisateurs/page.tsx` | read-only user table |
| Create | `frontend/src/app/admin/conseillers/page.tsx` | counselor list + code generator |
| Create | `frontend/src/app/admin/couts/page.tsx` | daily cost breakdown + SVG bar chart |

---

## Task 1: Test infrastructure

**Files:**
- Create: `backend/requirements-dev.txt`
- Modify: `backend/app/config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Create `requirements-dev.txt`**

```text
pytest==8.3.4
pytest-flask==1.3.0
```

- [ ] **Step 2: Add `TestingConfig` to `backend/app/config.py`**

Add after the `ProductionConfig` class (before the `config` dict):

```python
class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_COOKIE_SECURE = False
    JWT_TOKEN_LOCATION = ["headers"]   # no cookies in tests
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"
```

And update the `config` dict at the bottom:

```python
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
```

- [ ] **Step 3: Create `backend/tests/__init__.py`** (empty file)

- [ ] **Step 4: Create `backend/tests/conftest.py`**

```python
import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from flask_jwt_extended import create_access_token


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_headers(app):
    with app.app_context():
        admin = User(
            email="admin@test.com",
            password_hash="x",
            role="admin",
            plan="free",
        )
        _db.session.add(admin)
        _db.session.commit()
        token = create_access_token(
            identity=str(admin.id),
            additional_claims={"role": "admin"},
        )
        return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 5: Install dev dependencies and verify pytest runs**

```bash
cd backend
source venv/bin/activate
pip install pytest==8.3.4 pytest-flask==1.3.0
pytest tests/ -v
```

Expected: `no tests ran` (0 errors, collection works)

- [ ] **Step 6: Commit**

```bash
git add backend/requirements-dev.txt backend/app/config.py backend/tests/
git commit -m "test: add pytest infrastructure with SQLite in-memory config"
```

---

## Task 2: CounselorCode model + migration

**Files:**
- Create: `backend/app/models/counselor_code.py`
- Modify: `backend/app/__init__.py`

- [ ] **Step 1: Write failing test for `CounselorCode.to_dict()`**

Create `backend/tests/test_admin.py`:

```python
import pytest
from app.extensions import db
from app.models.counselor_code import CounselorCode


def test_counselor_code_to_dict(app):
    with app.app_context():
        code = CounselorCode(label="Cap Emploi Test")
        db.session.add(code)
        db.session.commit()

        d = code.to_dict()
        assert d["label"] == "Cap Emploi Test"
        assert len(d["code"]) == 8
        assert d["is_active"] is True
        assert d["uses_count"] == 0
        assert "id" in d
        assert "created_at" in d
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd backend && source venv/bin/activate
pytest tests/test_admin.py::test_counselor_code_to_dict -v
```

Expected: `ModuleNotFoundError: No module named 'app.models.counselor_code'`

- [ ] **Step 3: Create `backend/app/models/counselor_code.py`**

```python
import random
import string
from uuid import uuid4
from datetime import datetime
from ..extensions import db


def _generate_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


class CounselorCode(db.Model):
    __tablename__ = "counselor_codes"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    code = db.Column(db.String(8), unique=True, nullable=False, default=_generate_code)
    label = db.Column(db.String(255), nullable=False)
    created_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    uses_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    created_by = db.relationship("User", foreign_keys=[created_by_id])

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "label": self.label,
            "is_active": self.is_active,
            "uses_count": self.uses_count,
            "created_at": self.created_at.isoformat(),
        }
```

- [ ] **Step 4: Register model in `backend/app/__init__.py`**

Change line 24 from:
```python
from .models import user, analysis, prompt_version, counselor_note  # noqa: F401
```
to:
```python
from .models import user, analysis, prompt_version, counselor_note, counselor_code  # noqa: F401
```

- [ ] **Step 5: Run test — expect PASS**

```bash
pytest tests/test_admin.py::test_counselor_code_to_dict -v
```

Expected: `PASSED`

- [ ] **Step 6: Generate and apply migration**

```bash
cd backend && source venv/bin/activate
flask db migrate -m "add counselor_codes table"
flask db upgrade
```

Expected: migration file created in `migrations/versions/`, `upgrade` succeeds with no errors.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/counselor_code.py backend/app/__init__.py \
        backend/migrations/versions/ backend/tests/test_admin.py
git commit -m "feat: add CounselorCode model and migration"
```

---

## Task 3: Backend — counselor code endpoints

**Files:**
- Modify: `backend/app/routes/admin.py`
- Modify: `backend/tests/test_admin.py`

- [ ] **Step 1: Add failing tests for counselor code endpoints**

Append to `backend/tests/test_admin.py`:

```python
def test_list_counselor_codes_empty(client, admin_headers):
    res = client.get("/api/admin/counselor-codes", headers=admin_headers)
    assert res.status_code == 200
    assert res.get_json()["codes"] == []


def test_create_counselor_code(client, admin_headers):
    res = client.post(
        "/api/admin/counselor-codes",
        json={"label": "Cap Emploi Lyon"},
        headers=admin_headers,
    )
    assert res.status_code == 201
    data = res.get_json()["code"]
    assert len(data["code"]) == 8
    assert data["label"] == "Cap Emploi Lyon"
    assert data["is_active"] is True
    assert data["uses_count"] == 0


def test_create_counselor_code_missing_label(client, admin_headers):
    res = client.post("/api/admin/counselor-codes", json={}, headers=admin_headers)
    assert res.status_code == 400


def test_deactivate_counselor_code(client, admin_headers, app):
    with app.app_context():
        code = CounselorCode(label="Test")
        db.session.add(code)
        db.session.commit()
        code_id = code.id

    res = client.delete(f"/api/admin/counselor-codes/{code_id}", headers=admin_headers)
    assert res.status_code == 200

    with app.app_context():
        updated = CounselorCode.query.get(code_id)
        assert updated.is_active is False


def test_deactivate_nonexistent_code(client, admin_headers):
    res = client.delete("/api/admin/counselor-codes/nonexistent", headers=admin_headers)
    assert res.status_code == 404
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/test_admin.py -k "counselor_code" -v
```

Expected: `404 NOT FOUND` (routes not registered yet)

- [ ] **Step 3: Add counselor code endpoints to `backend/app/routes/admin.py`**

Add these imports at the top of `admin.py`:

```python
from datetime import datetime, date, timedelta
from flask_jwt_extended import get_jwt_identity
from ..models.counselor_code import CounselorCode
```

Append these routes at the end of `admin.py`:

```python
@admin_bp.get("/counselor-codes")
@admin_required
def list_counselor_codes():
    codes = CounselorCode.query.order_by(CounselorCode.created_at.desc()).all()
    return jsonify({"codes": [c.to_dict() for c in codes]}), 200


@admin_bp.post("/counselor-codes")
@admin_required
def create_counselor_code():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    label = (data.get("label") or "").strip()
    if not label:
        return jsonify({"error": "label requis."}), 400

    code = CounselorCode(label=label, created_by_id=user_id)
    db.session.add(code)
    db.session.commit()
    return jsonify({"code": code.to_dict()}), 201


@admin_bp.delete("/counselor-codes/<code_id>")
@admin_required
def deactivate_counselor_code(code_id):
    code = CounselorCode.query.get_or_404(code_id)
    code.is_active = False
    db.session.commit()
    return jsonify({"code": code.to_dict()}), 200
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_admin.py -k "counselor_code" -v
```

Expected: 5 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/admin.py backend/tests/test_admin.py
git commit -m "feat: add counselor code CRUD endpoints"
```

---

## Task 4: Backend — analyses filter params

**Files:**
- Modify: `backend/app/routes/admin.py`
- Modify: `backend/tests/test_admin.py`

- [ ] **Step 1: Add failing tests for analyses filters**

Append to `backend/tests/test_admin.py`:

```python
from app.models.analysis import Analysis


def _make_analysis(app, status="success", prenom="Alice", cible="Développeur"):
    with app.app_context():
        a = Analysis(
            status=status,
            inputs={"prenom": prenom, "cible_visee": cible},
        )
        db.session.add(a)
        db.session.commit()
        return a.id


def test_analyses_filter_by_status(client, admin_headers, app):
    _make_analysis(app, status="success")
    _make_analysis(app, status="error")

    res = client.get("/api/admin/analyses?status=success", headers=admin_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert all(a["status"] == "success" for a in body["analyses"])


def test_analyses_search_by_prenom(client, admin_headers, app):
    _make_analysis(app, prenom="Alice")
    _make_analysis(app, prenom="Bob")

    res = client.get("/api/admin/analyses?search=alice", headers=admin_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["analyses"]) == 1
    assert body["analyses"][0]["inputs"]["prenom"] == "Alice"


def test_analyses_pagination(client, admin_headers, app):
    for i in range(55):
        _make_analysis(app, prenom=f"User{i}")

    res = client.get("/api/admin/analyses?page=1", headers=admin_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["analyses"]) == 50
    assert body["pages"] == 2
    assert body["total"] == 55
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/test_admin.py -k "analyses" -v
```

Expected: `test_analyses_filter_by_status` FAILS (returns both statuses), search test FAILS.

- [ ] **Step 3: Replace `list_all_analyses` in `backend/app/routes/admin.py`**

Replace the entire existing `list_all_analyses` function (the one decorated with `@admin_bp.get("/analyses")`) with:

```python
@admin_bp.get("/analyses")
@admin_required
def list_all_analyses():
    page = int(request.args.get("page", 1))
    status_filter = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip()
    from_date = request.args.get("from", "").strip()
    to_date = request.args.get("to", "").strip()

    q = Analysis.query

    if status_filter:
        q = q.filter(Analysis.status == status_filter)

    if from_date:
        q = q.filter(Analysis.created_at >= from_date)

    if to_date:
        end = datetime.fromisoformat(to_date) + timedelta(days=1)
        q = q.filter(Analysis.created_at < end)

    if search:
        like = f"%{search}%"
        q = q.filter(
            db.or_(
                Analysis.inputs["prenom"].astext.ilike(like),
                Analysis.inputs["cible_visee"].astext.ilike(like),
            )
        )

    analyses = q.order_by(Analysis.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return jsonify({
        "analyses": [a.to_dict() for a in analyses.items],
        "total": analyses.total,
        "pages": analyses.pages,
        "page": analyses.page,
    }), 200
```

Note: `datetime` and `timedelta` are already imported in Task 3. Make sure the import line at the top of `admin.py` reads:
```python
from datetime import datetime, date, timedelta
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_admin.py -k "analyses" -v
```

Expected: 3 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/admin.py backend/tests/test_admin.py
git commit -m "feat: add status/search/date filters to admin analyses endpoint"
```

---

## Task 5: Backend — timeseries and costs endpoints

**Files:**
- Modify: `backend/app/routes/admin.py`
- Modify: `backend/tests/test_admin.py`

- [ ] **Step 1: Add failing tests**

Append to `backend/tests/test_admin.py`:

```python
def test_stats_timeseries(client, admin_headers):
    res = client.get("/api/admin/stats/timeseries?days=7", headers=admin_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["days"]) == 7
    day = body["days"][0]
    assert "date" in day
    assert "count" in day
    assert "tokens" in day
    assert "free_count" in day
    assert "paid_count" in day


def test_costs(client, admin_headers):
    res = client.get("/api/admin/costs?days=7", headers=admin_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["days"]) == 7
    assert "total" in body
    day = body["days"][0]
    for key in ("date", "analyses_count", "haiku_tokens_in", "haiku_tokens_out",
                "sonnet_tokens_in", "sonnet_tokens_out", "cost_eur"):
        assert key in day
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/test_admin.py -k "timeseries or costs" -v
```

Expected: `404 NOT FOUND`

- [ ] **Step 3: Add timeseries and costs endpoints to `backend/app/routes/admin.py`**

Append to `admin.py`:

```python
@admin_bp.get("/stats/timeseries")
@admin_required
def stats_timeseries():
    days_param = int(request.args.get("days", 30))
    today = date.today()
    result = []

    for i in range(days_param - 1, -1, -1):
        d = today - timedelta(days=i)
        start = datetime.combine(d, datetime.min.time())
        end = datetime.combine(d + timedelta(days=1), datetime.min.time())

        row = db.session.query(
            func.count(Analysis.id).label("cnt"),
            (
                func.coalesce(func.sum(Analysis.tokens_in), 0)
                + func.coalesce(func.sum(Analysis.tokens_out), 0)
            ).label("tokens"),
        ).filter(Analysis.created_at >= start, Analysis.created_at < end).first()

        paid_count = (
            db.session.query(func.count(Analysis.id))
            .join(User, Analysis.user_id == User.id)
            .filter(
                Analysis.created_at >= start,
                Analysis.created_at < end,
                User.plan == "paid",
            )
            .scalar()
            or 0
        )

        count = row.cnt or 0
        result.append({
            "date": d.isoformat(),
            "count": count,
            "tokens": row.tokens or 0,
            "free_count": count - paid_count,
            "paid_count": paid_count,
        })

    return jsonify({"days": result}), 200


_HAIKU_IN  = 0.80    # $/MTok
_HAIKU_OUT = 4.00
_SONNET_IN  = 3.00
_SONNET_OUT = 15.00
_USD_TO_EUR = 0.92


@admin_bp.get("/costs")
@admin_required
def costs():
    days_param = int(request.args.get("days", 30))
    today = date.today()
    result = []
    totals = dict(analyses_count=0, haiku_tokens_in=0, haiku_tokens_out=0,
                  sonnet_tokens_in=0, sonnet_tokens_out=0, cost_eur=0.0)

    for i in range(days_param - 1, -1, -1):
        d = today - timedelta(days=i)
        start = datetime.combine(d, datetime.min.time())
        end = datetime.combine(d + timedelta(days=1), datetime.min.time())

        haiku_row = (
            db.session.query(
                func.count(Analysis.id).label("cnt"),
                func.coalesce(func.sum(Analysis.tokens_in), 0).label("tin"),
                func.coalesce(func.sum(Analysis.tokens_out), 0).label("tout"),
            )
            .outerjoin(User, Analysis.user_id == User.id)
            .filter(
                Analysis.created_at >= start,
                Analysis.created_at < end,
                db.or_(User.plan == "free", Analysis.user_id.is_(None)),
            )
            .first()
        )

        sonnet_row = (
            db.session.query(
                func.count(Analysis.id).label("cnt"),
                func.coalesce(func.sum(Analysis.tokens_in), 0).label("tin"),
                func.coalesce(func.sum(Analysis.tokens_out), 0).label("tout"),
            )
            .join(User, Analysis.user_id == User.id)
            .filter(
                Analysis.created_at >= start,
                Analysis.created_at < end,
                User.plan == "paid",
            )
            .first()
        )

        h_in  = haiku_row.tin  if haiku_row  else 0
        h_out = haiku_row.tout if haiku_row  else 0
        s_in  = sonnet_row.tin  if sonnet_row else 0
        s_out = sonnet_row.tout if sonnet_row else 0
        count = (haiku_row.cnt if haiku_row else 0) + (sonnet_row.cnt if sonnet_row else 0)

        cost_usd = (h_in * _HAIKU_IN + h_out * _HAIKU_OUT + s_in * _SONNET_IN + s_out * _SONNET_OUT) / 1_000_000
        cost_eur = round(cost_usd * _USD_TO_EUR, 4)

        totals["analyses_count"]   += count
        totals["haiku_tokens_in"]  += h_in
        totals["haiku_tokens_out"] += h_out
        totals["sonnet_tokens_in"] += s_in
        totals["sonnet_tokens_out"]+= s_out
        totals["cost_eur"]         += cost_eur

        result.append({
            "date": d.isoformat(),
            "analyses_count": count,
            "haiku_tokens_in": h_in,
            "haiku_tokens_out": h_out,
            "sonnet_tokens_in": s_in,
            "sonnet_tokens_out": s_out,
            "cost_eur": cost_eur,
        })

    totals["cost_eur"] = round(totals["cost_eur"], 4)
    return jsonify({"days": result, "total": totals}), 200
```

- [ ] **Step 4: Run all backend tests — expect PASS**

```bash
pytest tests/ -v
```

Expected: all tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/admin.py backend/tests/test_admin.py
git commit -m "feat: add timeseries and costs admin endpoints"
```

---

## Task 6: Frontend — shared admin layout

**Files:**
- Create: `frontend/src/app/admin/layout.tsx`
- Modify: `frontend/src/app/admin/page.tsx` (remove hardcoded nav)

- [ ] **Step 1: Create `frontend/src/app/admin/layout.tsx`**

```tsx
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const NAV = [
  { label: "vue d'ensemble", href: "/admin" },
  { label: "prompts",        href: "/admin/prompts" },
  { label: "analyses",       href: "/admin/analyses" },
  { label: "utilisateurs",   href: "/admin/utilisateurs" },
  { label: "conseillers",    href: "/admin/conseillers" },
  { label: "coûts API",      href: "/admin/couts" },
]

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  return (
    <div className="min-h-screen bg-secondary">
      <div className="bg-background border-b border-border sticky top-0 z-40">
        <div className="max-w-[1280px] mx-auto px-6 h-10 flex items-center gap-4">
          <span className="font-bold text-sm">neoori</span>
          <Badge variant="outline" className="text-[10px]">admin</Badge>
          <nav className="flex gap-5 ml-4">
            {NAV.map(({ label, href }) => {
              const active =
                href === "/admin" ? pathname === "/admin" : pathname.startsWith(href)
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "text-xs pb-0.5 transition-colors",
                    active
                      ? "text-foreground border-b border-primary"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {label}
                </Link>
              )
            })}
          </nav>
          <Button variant="ghost" size="sm" className="ml-auto text-xs h-7">
            déconnexion
          </Button>
        </div>
      </div>
      <div className="max-w-[1280px] mx-auto px-6 py-5">{children}</div>
    </div>
  )
}
```

- [ ] **Step 2: Rewrite `frontend/src/app/admin/page.tsx`**

Replace the entire file with the condensed overview (no nav bar — layout owns it now):

```tsx
"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { PromptVersion } from "@/types"

interface Stats {
  total_analyses: number; success_count: number; error_count: number
  timeout_count: number; success_rate: number; conversion_rate: number
  total_tokens_in: number; total_tokens_out: number
  active_prompt: PromptVersion | null
}
interface LogEntry {
  id: string; created_at: string
  inputs: { prenom?: string; cible_visee?: string } | null
  status: string
}
interface TimeseriesDay { date: string; count: number; tokens: number; free_count: number; paid_count: number }

function MiniSparkline({ data, color = "var(--n-ink)" }: { data: number[]; color?: string }) {
  if (!data.length) return <div className="h-10 w-full" />
  const max = Math.max(...data, 1)
  const W = 240, H = 40
  const pts = data
    .map((v, i) => `${(i / (data.length - 1)) * W},${H - (v / max) * (H - 4) - 2}`)
    .join(" ")
  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`}>
      <polyline points={pts} stroke={color} strokeWidth="1.5" fill="none" strokeLinecap="round" />
    </svg>
  )
}

export default function AdminPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [timeseries, setTimeseries] = useState<TimeseriesDay[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get<Stats>("/admin/stats"),
      api.get<{ analyses: LogEntry[] }>("/admin/analyses"),
      api.get<{ days: TimeseriesDay[] }>("/admin/stats/timeseries?days=30"),
    ])
      .then(([s, al, ts]) => {
        setStats(s)
        setLogs(al.analyses.slice(0, 10))
        setTimeseries(ts.days)
      })
      .finally(() => setLoading(false))
  }, [])

  const kpis = stats
    ? [
        ["analyses générées", String(stats.total_analyses), "total"],
        ["taux de succès", `${stats.success_rate} %`, `${stats.error_count} erreurs · ${stats.timeout_count} timeouts`],
        ["tokens consommés", `${(stats.total_tokens_in + stats.total_tokens_out).toLocaleString("fr")}`, "entrée + sortie"],
        ["conversion → payant", `${stats.conversion_rate} %`, "sur tous les candidats"],
        ["prompt actif", stats.active_prompt?.version_label ?? "—",
          stats.active_prompt ? `actif depuis le ${new Date(stats.active_prompt.created_at).toLocaleDateString("fr")}` : "aucun"],
      ]
    : []

  return (
    <>
      {/* KPI strip */}
      <div className="grid grid-cols-5 gap-3 mb-5">
        {loading
          ? Array(5).fill(0).map((_, i) => <Skeleton key={i} className="h-20 rounded-lg" />)
          : kpis.map(([k, v, d], i) => (
              <div key={String(k)} className="rounded-lg border border-border bg-card p-3">
                <p className="text-[10px] font-mono uppercase text-muted-foreground">{k}</p>
                <p className={cn("text-2xl font-bold mt-1", i === 4 && "text-primary")}>{v}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{d}</p>
              </div>
            ))}
      </div>

      <div className="grid grid-cols-[1.4fr_1fr] gap-4">
        {/* Condensed prompt panel */}
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="font-semibold text-sm">prompt système</h2>
              <p className="text-[10px] text-muted-foreground">versionné · rollback possible</p>
            </div>
            {stats?.active_prompt && (
              <Badge className="bg-primary text-primary-foreground text-[10px]">
                {stats.active_prompt.version_label} · ACTIF
              </Badge>
            )}
          </div>
          <Link href="/admin/prompts" className="text-xs text-primary hover:underline">
            gérer les prompts →
          </Link>
        </div>

        {/* Condensed analyses log */}
        <div className="rounded-lg border border-border bg-card p-4 overflow-hidden">
          <div className="flex items-baseline justify-between mb-3">
            <h2 className="font-semibold text-sm">analyses récentes</h2>
            <Link href="/admin/analyses" className="text-[10px] text-primary hover:underline">
              voir toutes →
            </Link>
          </div>
          <div className="space-y-0">
            {loading
              ? Array(5).fill(0).map((_, i) => (
                  <div key={i} className="py-1.5 border-b border-dashed border-border">
                    <Skeleton className="h-5" />
                  </div>
                ))
              : logs.map(log => (
                  <div key={log.id} className="grid grid-cols-[36px_1fr_52px] gap-2 py-1.5 border-b border-dashed border-border items-center last:border-0">
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {new Date(log.created_at).toLocaleTimeString("fr", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                    <p className="text-xs truncate">
                      {log.inputs?.prenom ?? "—"} — {log.inputs?.cible_visee?.slice(0, 25) ?? "—"}
                    </p>
                    <Badge
                      variant="outline"
                      className={cn("text-[9px] px-1.5",
                        log.status === "success" ? "bg-green-50 border-green-200 text-green-700" :
                        log.status === "timeout" ? "bg-yellow-50 border-yellow-200 text-yellow-700" :
                        "bg-red-50 border-red-200 text-red-700"
                      )}
                    >
                      {log.status}
                    </Badge>
                  </div>
                ))}
          </div>
        </div>
      </div>

      <Separator className="my-4" />

      {/* Sparklines */}
      <div className="rounded-lg border border-border bg-card p-4 grid grid-cols-3 gap-6">
        {loading
          ? Array(3).fill(0).map((_, i) => <Skeleton key={i} className="h-14" />)
          : (
            <>
              <div>
                <p className="text-[10px] font-mono uppercase text-muted-foreground mb-2">analyses · 30j</p>
                <MiniSparkline data={timeseries.map(d => d.count)} />
              </div>
              <div>
                <p className="text-[10px] font-mono uppercase text-muted-foreground mb-2">tokens · 30j</p>
                <MiniSparkline data={timeseries.map(d => d.tokens)} color="var(--n-accent)" />
              </div>
              <div>
                <p className="text-[10px] font-mono uppercase text-muted-foreground mb-2">plans · gratuit vs payant</p>
                <MiniSparkline data={timeseries.map(d => d.paid_count)} color="var(--n-ink-2)" />
              </div>
            </>
          )}
      </div>
    </>
  )
}
```

- [ ] **Step 3: Start dev server and verify layout nav renders, active link highlights on `/admin`**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000/admin` in browser. Verify:
- Top nav bar shows all 6 links
- "vue d'ensemble" link has `border-b border-primary` (active state)
- KPI strip renders (skeletons then data)
- Sparklines render with real SVG paths (not static points)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/admin/layout.tsx frontend/src/app/admin/page.tsx
git commit -m "feat: add shared admin layout and refactor overview page with real sparklines"
```

---

## Task 7: Frontend — prompts page

**Files:**
- Create: `frontend/src/app/admin/prompts/page.tsx`

- [ ] **Step 1: Create `frontend/src/app/admin/prompts/page.tsx`**

```tsx
"use client"

import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { PromptVersion } from "@/types"

export default function PromptsPage() {
  const [versions, setVersions] = useState<PromptVersion[]>([])
  const [text, setText] = useState("")
  const [savedText, setSavedText] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const dirty = text !== savedText

  const loadData = async () => {
    const [pv, ap] = await Promise.all([
      api.get<{ prompts: PromptVersion[] }>("/prompts/"),
      api.get<{ prompt: PromptVersion }>("/prompts/active").catch(() => ({ prompt: null })),
    ])
    setVersions(pv.prompts)
    const t = ap.prompt?.system_prompt_text ?? ""
    setText(t)
    setSavedText(t)
  }

  useEffect(() => {
    loadData().finally(() => setLoading(false))
  }, [])

  const publish = async () => {
    if (!text.trim() || !dirty) return
    setSaving(true)
    try {
      const lastLabel = versions[0]?.version_label ?? "v1.0"
      const nextLabel = lastLabel.replace(
        /v(\d+)\.(\d+)/,
        (_, maj, min) => `v${maj}.${+min + 1}`
      )
      await api.post("/prompts/", {
        version_label: nextLabel,
        system_prompt_text: text,
        activate: true,
      })
      await loadData()
    } finally {
      setSaving(false)
    }
  }

  const rollback = async (id: string) => {
    await api.post(`/prompts/${id}/rollback`)
    await loadData()
  }

  const activeVersion = versions.find(v => v.is_active)

  return (
    <div className="grid grid-cols-[1.4fr_1fr] gap-4">
      {/* Editor */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h2 className="font-semibold text-sm">prompt système</h2>
            <p className="text-[10px] text-muted-foreground">
              éditable sans redéploiement · versionné · rollback possible
            </p>
          </div>
          {activeVersion && (
            <Badge className="bg-primary text-primary-foreground text-[10px]">
              {activeVersion.version_label} · ACTIF
            </Badge>
          )}
        </div>

        {loading ? (
          <Skeleton className="h-72" />
        ) : (
          <Textarea
            value={text}
            onChange={e => setText(e.target.value)}
            className="min-h-[320px] font-mono text-xs bg-secondary resize-none"
            placeholder="Collez ici le texte complet du system prompt…"
          />
        )}

        <div className="flex gap-2 mt-3 items-center">
          <Button
            size="sm"
            className="text-xs h-7 bg-primary hover:bg-primary/90 text-primary-foreground"
            disabled={!dirty || saving || loading}
            onClick={publish}
          >
            {saving ? "publication…" : "publier nouvelle version"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-xs h-7"
            disabled={!dirty}
            onClick={() => setText(savedText)}
          >
            annuler
          </Button>
          <span className="text-[10px] text-muted-foreground ml-auto">
            traçabilité B2G : chaque analyse stocke la version utilisée
          </span>
        </div>
      </div>

      {/* Version history */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="font-semibold text-sm mb-3">historique des versions</h2>
        {loading ? (
          Array(4).fill(0).map((_, i) => <Skeleton key={i} className="h-10 mb-2" />)
        ) : versions.length === 0 ? (
          <p className="text-xs text-muted-foreground">aucune version</p>
        ) : (
          <div className="space-y-0">
            {versions.map(v => (
              <div
                key={v.id}
                className="flex items-center gap-2 py-2 border-b border-dashed border-border last:border-0"
              >
                <span className="font-mono text-xs font-medium w-12">{v.version_label}</span>
                {v.is_active && (
                  <Badge className="bg-primary text-primary-foreground text-[9px] px-1.5">
                    ACTIF
                  </Badge>
                )}
                <span className="text-[10px] text-muted-foreground flex-1">
                  {v.author} · {new Date(v.created_at).toLocaleDateString("fr")}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-[10px] h-6 px-2"
                  disabled={v.is_active}
                  onClick={() => rollback(v.id)}
                >
                  {v.is_active ? "actif" : "rollback"}
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify in browser**

Navigate to `http://localhost:3000/admin/prompts`. Verify:
- "prompts" nav link is active (underlined)
- Prompt textarea shows active prompt text
- Publish button disabled until text changes
- Annuler button disabled until text changes
- Version history shows all versions with rollback buttons (disabled on active)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/admin/prompts/page.tsx
git commit -m "feat: add admin prompts page with full version history"
```

---

## Task 8: Frontend — analyses page

**Files:**
- Create: `frontend/src/app/admin/analyses/page.tsx`

- [ ] **Step 1: Create `frontend/src/app/admin/analyses/page.tsx`**

```tsx
"use client"

import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { PromptVersion } from "@/types"

interface LogEntry {
  id: string; created_at: string
  inputs: { prenom?: string; cible_visee?: string } | null
  status: string; prompt_version_id: string | null
  tokens_in: number | null; tokens_out: number | null
}
interface ListResponse {
  analyses: LogEntry[]; total: number; pages: number; page: number
}

export default function AnalysesPage() {
  const [data, setData] = useState<ListResponse | null>(null)
  const [versions, setVersions] = useState<PromptVersion[]>([])
  const [loading, setLoading] = useState(true)

  const [page, setPage] = useState(1)
  const [status, setStatus] = useState("")
  const [searchInput, setSearchInput] = useState("")
  const [appliedSearch, setAppliedSearch] = useState("")
  const [from, setFrom] = useState("")
  const [to, setTo] = useState("")

  const load = async (p: number, s: string, q: string, f: string, t: string) => {
    setLoading(true)
    const params = new URLSearchParams({ page: String(p) })
    if (s) params.set("status", s)
    if (q) params.set("search", q)
    if (f) params.set("from", f)
    if (t) params.set("to", t)
    try {
      const res = await api.get<ListResponse>(`/admin/analyses?${params}`)
      setData(res)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    api.get<{ prompts: PromptVersion[] }>("/prompts/").then(r => setVersions(r.prompts))
    load(1, "", "", "", "")
  }, [])

  const apply = () => {
    setPage(1)
    setAppliedSearch(searchInput)
    load(1, status, searchInput, from, to)
  }

  const reset = () => {
    setPage(1); setStatus(""); setSearchInput(""); setAppliedSearch(""); setFrom(""); setTo("")
    load(1, "", "", "", "")
  }

  const goPage = (p: number) => {
    setPage(p)
    load(p, status, appliedSearch, from, to)
  }

  const versionLabel = (id: string | null) =>
    versions.find(v => v.id === id)?.version_label ?? "—"

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      {/* Filter bar */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <h2 className="font-semibold text-sm mr-2">analyses</h2>
        <Select
          value={status || "tous"}
          onValueChange={v => setStatus(v === "tous" ? "" : v)}
        >
          <SelectTrigger className="h-7 text-xs w-36">
            <SelectValue placeholder="tous statuts" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="tous">tous</SelectItem>
            <SelectItem value="success">success</SelectItem>
            <SelectItem value="error">error</SelectItem>
            <SelectItem value="timeout">timeout</SelectItem>
          </SelectContent>
        </Select>
        <Input
          type="date"
          value={from}
          onChange={e => setFrom(e.target.value)}
          className="h-7 text-xs w-36"
        />
        <Input
          type="date"
          value={to}
          onChange={e => setTo(e.target.value)}
          className="h-7 text-xs w-36"
        />
        <Input
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && apply()}
          placeholder="prénom ou cible…"
          className="h-7 text-xs w-44"
        />
        <Button size="sm" className="h-7 text-xs" onClick={apply}>
          filtrer
        </Button>
        <Button size="sm" variant="outline" className="h-7 text-xs" onClick={reset}>
          réinitialiser
        </Button>
        {data && (
          <span className="text-[10px] text-muted-foreground ml-auto">
            {data.total} résultat{data.total !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Table */}
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-[10px] font-mono uppercase">
            <th className="text-left pb-2 pr-3 font-normal">heure</th>
            <th className="text-left pb-2 pr-3 font-normal">prénom</th>
            <th className="text-left pb-2 pr-3 font-normal">cible</th>
            <th className="text-left pb-2 pr-3 font-normal">statut</th>
            <th className="text-left pb-2 pr-3 font-normal">prompt</th>
            <th className="text-left pb-2 font-normal">tokens</th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array(10).fill(0).map((_, i) => (
                <tr key={i} className="border-b border-dashed border-border">
                  <td colSpan={6} className="py-2">
                    <Skeleton className="h-5" />
                  </td>
                </tr>
              ))
            : data?.analyses.map(a => (
                <tr key={a.id} className="border-b border-dashed border-border last:border-0">
                  <td className="py-2 pr-3 font-mono text-[10px] text-muted-foreground whitespace-nowrap">
                    {new Date(a.created_at).toLocaleString("fr", {
                      day: "2-digit", month: "2-digit",
                      hour: "2-digit", minute: "2-digit",
                    })}
                  </td>
                  <td className="py-2 pr-3">{a.inputs?.prenom ?? "—"}</td>
                  <td className="py-2 pr-3 max-w-[180px] truncate text-muted-foreground">
                    {a.inputs?.cible_visee ?? "—"}
                  </td>
                  <td className="py-2 pr-3">
                    <Badge
                      variant="outline"
                      className={cn("text-[9px] px-1.5",
                        a.status === "success" ? "bg-green-50 border-green-200 text-green-700" :
                        a.status === "timeout" ? "bg-yellow-50 border-yellow-200 text-yellow-700" :
                        a.status === "running" ? "bg-blue-50 border-blue-200 text-blue-700" :
                        "bg-red-50 border-red-200 text-red-700"
                      )}
                    >
                      {a.status}
                    </Badge>
                  </td>
                  <td className="py-2 pr-3 font-mono text-[10px]">
                    {versionLabel(a.prompt_version_id)}
                  </td>
                  <td className="py-2 font-mono text-[10px] text-muted-foreground">
                    {a.tokens_in != null
                      ? (a.tokens_in + (a.tokens_out ?? 0)).toLocaleString("fr")
                      : "—"}
                  </td>
                </tr>
              ))}
        </tbody>
      </table>

      {/* Empty state */}
      {!loading && data?.analyses.length === 0 && (
        <p className="text-center text-xs text-muted-foreground py-8">
          aucune analyse trouvée
        </p>
      )}

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center gap-2 mt-4 justify-end">
          <Button
            size="sm" variant="outline" className="h-7 text-xs"
            disabled={page <= 1}
            onClick={() => goPage(page - 1)}
          >
            précédent
          </Button>
          <span className="text-[10px] text-muted-foreground">
            {page} / {data.pages}
          </span>
          <Button
            size="sm" variant="outline" className="h-7 text-xs"
            disabled={page >= data.pages}
            onClick={() => goPage(page + 1)}
          >
            suivant
          </Button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify in browser**

Navigate to `http://localhost:3000/admin/analyses`. Verify:
- Filter bar renders; status dropdown has 4 options
- Table loads data (or shows empty state if DB empty)
- Entering text in search input and pressing Enter re-fetches

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/admin/analyses/page.tsx
git commit -m "feat: add admin analyses page with pagination and filters"
```

---

## Task 9: Frontend — utilisateurs page

**Files:**
- Create: `frontend/src/app/admin/utilisateurs/page.tsx`

- [ ] **Step 1: Create `frontend/src/app/admin/utilisateurs/page.tsx`**

```tsx
"use client"

import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { User } from "@/types"

export default function UtilisateursPage() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get<{ users: User[] }>("/admin/users")
      .then(r => setUsers(r.users))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-semibold text-sm">utilisateurs</h2>
        <span className="text-[10px] text-muted-foreground">
          lecture seule · {users.length} compte{users.length !== 1 ? "s" : ""}
        </span>
      </div>

      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-[10px] font-mono uppercase">
            <th className="text-left pb-2 pr-4 font-normal">email</th>
            <th className="text-left pb-2 pr-4 font-normal">rôle</th>
            <th className="text-left pb-2 pr-4 font-normal">plan</th>
            <th className="text-left pb-2 pr-4 font-normal">crédits</th>
            <th className="text-left pb-2 font-normal">inscrit le</th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array(8).fill(0).map((_, i) => (
                <tr key={i} className="border-b border-dashed border-border">
                  <td colSpan={5} className="py-2">
                    <Skeleton className="h-5" />
                  </td>
                </tr>
              ))
            : users.map(u => (
                <tr key={u.id} className="border-b border-dashed border-border last:border-0">
                  <td className="py-2 pr-4">{u.email}</td>
                  <td className="py-2 pr-4">
                    <Badge
                      variant="outline"
                      className={cn("text-[9px] px-1.5",
                        u.role === "admin"     ? "bg-red-50 border-red-200 text-red-700" :
                        u.role === "counselor" ? "bg-blue-50 border-blue-200 text-blue-700" :
                        "bg-secondary"
                      )}
                    >
                      {u.role}
                    </Badge>
                  </td>
                  <td className="py-2 pr-4">
                    <Badge
                      variant="outline"
                      className={cn("text-[9px] px-1.5",
                        u.plan === "paid"
                          ? "bg-primary/10 border-primary/30 text-primary"
                          : "bg-secondary"
                      )}
                    >
                      {u.plan}
                    </Badge>
                  </td>
                  <td className="py-2 pr-4 font-mono text-[10px] text-muted-foreground">
                    {u.credits_remaining}
                  </td>
                  <td className="py-2 text-[10px] text-muted-foreground">
                    {new Date(u.created_at).toLocaleDateString("fr")}
                  </td>
                </tr>
              ))}
        </tbody>
      </table>

      {!loading && users.length === 0 && (
        <p className="text-center text-xs text-muted-foreground py-8">
          aucun utilisateur
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify in browser**

Navigate to `http://localhost:3000/admin/utilisateurs`. Verify:
- Table renders with role and plan badges correctly colored
- "utilisateurs" nav link is active

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/admin/utilisateurs/page.tsx
git commit -m "feat: add admin utilisateurs read-only page"
```

---

## Task 10: Frontend — conseillers page

**Files:**
- Create: `frontend/src/app/admin/conseillers/page.tsx`

- [ ] **Step 1: Create `frontend/src/app/admin/conseillers/page.tsx`**

```tsx
"use client"

import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { User } from "@/types"

interface CounselorCode {
  id: string; code: string; label: string
  is_active: boolean; uses_count: number; created_at: string
}

export default function ConseillersPage() {
  const [counselors, setCounselors] = useState<User[]>([])
  const [codes, setCodes] = useState<CounselorCode[]>([])
  const [loading, setLoading] = useState(true)
  const [newLabel, setNewLabel] = useState("")
  const [creating, setCreating] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      api.get<{ users: User[] }>("/admin/users"),
      api.get<{ codes: CounselorCode[] }>("/admin/counselor-codes"),
    ])
      .then(([usersRes, codesRes]) => {
        setCounselors(usersRes.users.filter(u => u.role === "counselor"))
        setCodes(codesRes.codes)
      })
      .finally(() => setLoading(false))
  }, [])

  const generate = async () => {
    if (!newLabel.trim()) return
    setCreating(true)
    try {
      const res = await api.post<{ code: CounselorCode }>("/admin/counselor-codes", {
        label: newLabel.trim(),
      })
      setCodes(prev => [res.code, ...prev])
      setNewLabel("")
      setShowForm(false)
    } finally {
      setCreating(false)
    }
  }

  const deactivate = async (id: string) => {
    await api.delete(`/admin/counselor-codes/${id}`)
    setCodes(prev => prev.map(c => c.id === id ? { ...c, is_active: false } : c))
  }

  const copy = (code: string, id: string) => {
    navigator.clipboard.writeText(code)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  return (
    <div className="grid grid-cols-[1fr_1.4fr] gap-4">
      {/* Counselor users */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="font-semibold text-sm mb-3">conseillers inscrits</h2>
        {loading ? (
          Array(3).fill(0).map((_, i) => <Skeleton key={i} className="h-8 mb-2" />)
        ) : counselors.length === 0 ? (
          <p className="text-xs text-muted-foreground">aucun conseiller inscrit</p>
        ) : (
          counselors.map(u => (
            <div
              key={u.id}
              className="flex items-center justify-between py-2 border-b border-dashed border-border last:border-0"
            >
              <span className="text-xs">{u.email}</span>
              <span className="text-[10px] text-muted-foreground">
                {new Date(u.created_at).toLocaleDateString("fr")}
              </span>
            </div>
          ))
        )}
      </div>

      {/* Code manager */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="font-semibold text-sm">codes d'accès conseiller</h2>
          <Button size="sm" className="h-7 text-xs" onClick={() => setShowForm(!showForm)}>
            + générer un code
          </Button>
        </div>

        {showForm && (
          <div className="flex gap-2 mb-3">
            <Input
              value={newLabel}
              onChange={e => setNewLabel(e.target.value)}
              onKeyDown={e => e.key === "Enter" && generate()}
              placeholder="ex : Cap Emploi Lyon — Lot 3"
              className="h-7 text-xs flex-1"
              autoFocus
            />
            <Button
              size="sm" className="h-7 text-xs"
              disabled={creating || !newLabel.trim()}
              onClick={generate}
            >
              {creating ? "…" : "créer"}
            </Button>
            <Button
              size="sm" variant="outline" className="h-7 text-xs"
              onClick={() => { setShowForm(false); setNewLabel("") }}
            >
              annuler
            </Button>
          </div>
        )}

        {loading ? (
          Array(3).fill(0).map((_, i) => <Skeleton key={i} className="h-10 mb-2" />)
        ) : codes.length === 0 ? (
          <p className="text-xs text-muted-foreground">aucun code généré</p>
        ) : (
          codes.map(c => (
            <div
              key={c.id}
              className="flex items-center gap-2 py-2 border-b border-dashed border-border last:border-0"
            >
              <span className="font-mono text-xs font-bold tracking-widest">{c.code}</span>
              <span className="text-[10px] text-muted-foreground flex-1 truncate">{c.label}</span>
              <Badge
                variant="outline"
                className={cn("text-[9px] px-1.5 shrink-0",
                  c.is_active
                    ? "bg-green-50 border-green-200 text-green-700"
                    : "bg-secondary text-muted-foreground"
                )}
              >
                {c.is_active ? "actif" : "inactif"}
              </Badge>
              <span className="text-[10px] text-muted-foreground shrink-0">{c.uses_count}×</span>
              <Button
                size="sm" variant="outline" className="h-6 text-[10px] px-2 shrink-0"
                onClick={() => copy(c.code, c.id)}
              >
                {copiedId === c.id ? "copié ✓" : "copier"}
              </Button>
              {c.is_active && (
                <Button
                  size="sm" variant="outline"
                  className="h-6 text-[10px] px-2 shrink-0 text-red-600 border-red-200 hover:bg-red-50"
                  onClick={() => deactivate(c.id)}
                >
                  désactiver
                </Button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify in browser**

Navigate to `http://localhost:3000/admin/conseillers`. Verify:
- "conseillers inscrits" panel shows counselor-role users (or empty state)
- "+ générer un code" button opens inline form
- Creating a code adds it to the list immediately (optimistic update)
- "copier" button copies code to clipboard, changes to "copié ✓" for 2s
- "désactiver" button changes badge to "inactif" and hides itself

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/admin/conseillers/page.tsx
git commit -m "feat: add admin conseillers page with code generator"
```

---

## Task 11: Frontend — coûts API page

**Files:**
- Create: `frontend/src/app/admin/couts/page.tsx`

- [ ] **Step 1: Create `frontend/src/app/admin/couts/page.tsx`**

```tsx
"use client"

import { useEffect, useState } from "react"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"

interface CostDay {
  date: string; analyses_count: number
  haiku_tokens_in: number; haiku_tokens_out: number
  sonnet_tokens_in: number; sonnet_tokens_out: number
  cost_eur: number
}
interface CostsResponse {
  days: CostDay[]
  total: {
    analyses_count: number
    haiku_tokens_in: number; haiku_tokens_out: number
    sonnet_tokens_in: number; sonnet_tokens_out: number
    cost_eur: number
  }
}

function BarChart({ data }: { data: CostDay[] }) {
  const maxCost = Math.max(...data.map(d => d.cost_eur), 0.0001)
  const W = 600, H = 72
  const barW = Math.max(1, W / data.length - 2)

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
      {data.map((d, i) => {
        const totalH = Math.min((d.cost_eur / maxCost) * (H - 4), H - 2)
        const sonnetCost =
          (d.sonnet_tokens_in * 3 + d.sonnet_tokens_out * 15) / 1_000_000 * 0.92
        const sonnetH = Math.min((sonnetCost / maxCost) * (H - 4), totalH)
        const x = i * (W / data.length) + 1

        return (
          <g key={d.date}>
            <rect
              x={x} y={H - totalH} width={barW} height={totalH}
              fill="var(--n-ink)" opacity={0.12} rx={1}
            />
            <rect
              x={x} y={H - sonnetH} width={barW} height={sonnetH}
              fill="var(--n-accent)" opacity={0.65} rx={1}
            />
          </g>
        )
      })}
    </svg>
  )
}

export default function CoutsPage() {
  const [data, setData] = useState<CostsResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get<CostsResponse>("/admin/costs?days=30")
      .then(setData)
      .finally(() => setLoading(false))
  }, [])

  const fmt = (n: number) => n.toLocaleString("fr")

  return (
    <div className="space-y-4">
      {/* Summary strip */}
      <div className="grid grid-cols-4 gap-3">
        {loading
          ? Array(4).fill(0).map((_, i) => <Skeleton key={i} className="h-20 rounded-lg" />)
          : data && [
              ["coût estimé · 30j",    `${data.total.cost_eur.toFixed(2)} €`,  "USD → EUR ×0.92 (approx)"],
              ["analyses",             String(data.total.analyses_count),       "total période"],
              ["tokens haiku",         fmt(data.total.haiku_tokens_in + data.total.haiku_tokens_out),   "plan gratuit"],
              ["tokens sonnet",        fmt(data.total.sonnet_tokens_in + data.total.sonnet_tokens_out), "plan payant"],
            ].map(([k, v, d]) => (
              <div key={String(k)} className="rounded-lg border border-border bg-card p-3">
                <p className="text-[10px] font-mono uppercase text-muted-foreground">{k}</p>
                <p className="text-2xl font-bold mt-1">{v}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{d}</p>
              </div>
            ))}
      </div>

      {/* Bar chart */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center gap-4 mb-3">
          <h2 className="font-semibold text-sm">coût quotidien · 30j</h2>
          <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <span
              className="w-3 h-2 rounded-sm inline-block"
              style={{ background: "var(--n-accent)", opacity: 0.65 }}
            />
            sonnet (payant)
          </span>
          <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <span
              className="w-3 h-2 rounded-sm inline-block"
              style={{ background: "var(--n-ink)", opacity: 0.12 }}
            />
            haiku (gratuit)
          </span>
        </div>
        {loading ? <Skeleton className="h-20" /> : data && <BarChart data={data.days} />}
      </div>

      {/* Daily breakdown table */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="font-semibold text-sm mb-3">détail par jour</h2>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border text-muted-foreground text-[10px] font-mono uppercase">
              <th className="text-left pb-2 pr-4 font-normal">date</th>
              <th className="text-right pb-2 pr-4 font-normal">analyses</th>
              <th className="text-right pb-2 pr-4 font-normal">tok. haiku</th>
              <th className="text-right pb-2 pr-4 font-normal">tok. sonnet</th>
              <th className="text-right pb-2 font-normal">coût €</th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array(7).fill(0).map((_, i) => (
                  <tr key={i}><td colSpan={5} className="py-2"><Skeleton className="h-4" /></td></tr>
                ))
              : data?.days.map(d => (
                  <tr key={d.date} className="border-b border-dashed border-border last:border-0">
                    <td className="py-1.5 pr-4 font-mono text-[10px]">
                      {new Date(d.date).toLocaleDateString("fr", { day: "2-digit", month: "2-digit" })}
                    </td>
                    <td className="py-1.5 pr-4 text-right">{d.analyses_count}</td>
                    <td className="py-1.5 pr-4 text-right font-mono text-[10px]">
                      {fmt(d.haiku_tokens_in + d.haiku_tokens_out)}
                    </td>
                    <td className="py-1.5 pr-4 text-right font-mono text-[10px]">
                      {fmt(d.sonnet_tokens_in + d.sonnet_tokens_out)}
                    </td>
                    <td className="py-1.5 text-right font-mono text-[10px]">
                      {d.cost_eur.toFixed(4)}
                    </td>
                  </tr>
                ))}
            {/* Totals row */}
            {data && (
              <tr className="border-t-2 border-border font-semibold">
                <td className="pt-2 pr-4 text-[10px]">total</td>
                <td className="pt-2 pr-4 text-right">{data.total.analyses_count}</td>
                <td className="pt-2 pr-4 text-right font-mono text-[10px]">
                  {fmt(data.total.haiku_tokens_in + data.total.haiku_tokens_out)}
                </td>
                <td className="pt-2 pr-4 text-right font-mono text-[10px]">
                  {fmt(data.total.sonnet_tokens_in + data.total.sonnet_tokens_out)}
                </td>
                <td className="pt-2 text-right font-mono text-[10px]">
                  {data.total.cost_eur.toFixed(4)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify in browser**

Navigate to `http://localhost:3000/admin/couts`. Verify:
- 4 KPI cards render (cost, analyses, haiku tokens, sonnet tokens)
- Bar chart renders with SVG bars (all zero is fine in dev with no data)
- Table shows 30 rows + totals row

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/admin/couts/page.tsx
git commit -m "feat: add admin costs page with SVG bar chart and daily breakdown"
```

---

## Task 12: Final verification

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && source venv/bin/activate
pytest tests/ -v
```

Expected: all tests `PASSED`, no warnings about missing imports.

- [ ] **Step 2: Check all nav links work end-to-end**

With both `npm run dev` (frontend) and `python run.py` (backend) running:

| URL | Expected |
|---|---|
| `/admin` | KPIs + condensed panels + sparklines |
| `/admin/prompts` | Prompt editor + version history |
| `/admin/analyses` | Table with filters, pagination |
| `/admin/utilisateurs` | Read-only user table |
| `/admin/conseillers` | Counselor list + code form |
| `/admin/couts` | Cost KPIs + chart + table |

Each page: "active" nav link underlined, `border-b border-primary`.

- [ ] **Step 3: Test counselor code flow**

1. Go to `/admin/conseillers`
2. Click "+ générer un code", enter label "Test Cap Emploi", press Enter
3. New code appears in list with 8-char uppercase code
4. Click "copier" — button changes to "copié ✓" for 2s
5. Click "désactiver" — badge changes to "inactif", button disappears

- [ ] **Step 4: Test analyses filters**

1. Go to `/admin/analyses`
2. Select "error" from status dropdown, click "filtrer"
3. All visible rows should have status "error"
4. Click "réinitialiser" — all rows return

- [ ] **Step 5: Final commit (if any loose files)**

```bash
git status
# commit any remaining changes
```
