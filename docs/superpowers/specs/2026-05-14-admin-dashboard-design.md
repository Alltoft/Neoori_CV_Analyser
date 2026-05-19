# Admin Dashboard — Design Spec
Date: 2026-05-14  
Status: approved

## Overview

Build out the full admin dashboard for neoori CV analyzer. Existing `/admin/page.tsx` is a skeleton with KPIs, a prompt editor, and a 10-item analyses log — all wired to real APIs but with non-functional nav tabs. This spec defines the complete multi-page admin using Next.js App Router flat routes with a shared layout.

---

## Route Structure

```
frontend/src/app/admin/
  layout.tsx                ← shared nav bar
  page.tsx                  ← vue d'ensemble (KPIs + sparklines, condensed panels)
  prompts/page.tsx          ← full prompt editor + version history
  analyses/page.tsx         ← full log: pagination + filters + search
  utilisateurs/page.tsx     ← read-only user table
  conseillers/page.tsx      ← counselor list + counselor code management
  couts/page.tsx            ← daily token cost chart, Haiku vs Sonnet split
```

All pages are `"use client"` components. Auth guard already handled by `proxy.ts` (checks `access_token_cookie`).

---

## 1. Shared Layout — `/admin/layout.tsx`

Fixed top bar identical to current design, extracted into layout so it renders once across all admin pages:

- `neoori` wordmark + `admin` badge
- 6 `<Link>` nav items: vue d'ensemble (`/admin`), prompts (`/admin/prompts`), analyses (`/admin/analyses`), utilisateurs (`/admin/utilisateurs`), conseillers (`/admin/conseillers`), coûts API (`/admin/couts`)
- Active state: `pathname.startsWith("/admin/X")` → `border-b border-primary text-foreground`; vue d'ensemble active only on exact `/admin`
- Déconnexion button (right-aligned)
- `children` rendered below bar in `max-w-[1280px] mx-auto px-6 py-5`

Existing `page.tsx` nav bar (currently hardcoded `<span>` elements) is removed and replaced by this layout.

---

## 2. Vue d'ensemble — `/admin/page.tsx`

Refactored from current page. Keeps:
- 5-KPI strip (unchanged)
- Condensed prompt panel: active version label + "gérer les prompts →" link to `/admin/prompts`
- Condensed analyses log: last 10 items + "voir toutes les analyses →" link to `/admin/analyses`

Adds:
- Real sparkline data replacing fake static SVGs
- Sparklines fetch from `GET /admin/stats/timeseries?days=30` → `[{date, count}]` per day
- 3 sparklines: analyses 30j, tokens 30j, gratuit vs payant (free vs paid analyses count per day)
- Pure SVG rendering (no charting lib), consistent with existing fake-SVG approach

Data fetched: `/admin/stats` (existing) + `/admin/stats/timeseries?days=30` (new).

---

## 3. Prompts — `/admin/prompts/page.tsx`

Full prompt management, moved from `page.tsx`:

**Left panel — editor:**
- Textarea with active prompt text (editable)
- Publish button: inactive until text changes; on click → `POST /prompts/` with auto-incremented version label + `activate: true`
- Cancel / annuler button resets text to the active prompt text fetched on page load
- Traceability note: "traçabilité B2G : chaque analyse stocke la version utilisée"

**Right panel — version history:**
- Full version list (all versions, not capped at 5)
- Each row: version label, author name, date, active badge (if is_active), rollback button (disabled on active version)
- Rollback: `POST /prompts/<id>/rollback`
- Versions fetched from `GET /prompts/` (existing)

---

## 4. Analyses — `/admin/analyses/page.tsx`

Full paginated log with filtering:

**Filter bar (top):**
- Status dropdown: tous / success / error / timeout
- Date range: two `<input type="date">` fields (from / to)
- Search input: matches prénom or cible_visee (backend `ILIKE`)
- Reset filters button

**Table:**
- Columns: heure, prénom, cible (30-char truncated), statut badge (colored), prompt version label, tokens in+out
- 50 rows per page
- Pagination controls: previous / next + current page / total pages
- Empty state: "aucune analyse trouvée"

**Backend update:** `GET /admin/analyses` gains query params: `page`, `status`, `search` (name OR cible ILIKE), `from` (ISO date), `to` (ISO date). Returns existing shape + `total`, `pages`, `page`.

---

## 5. Utilisateurs — `/admin/utilisateurs/page.tsx`

Read-only user list:

- Table columns: email, rôle (badge: candidate / counselor / admin), plan (badge: free / paid), crédits restants, créé le
- Sorted by `created_at DESC`
- No pagination (acceptable — user count small for MVP)
- Sourced from existing `GET /admin/users`

---

## 6. Conseillers — `/admin/conseillers/page.tsx`

Two panels side-by-side:

**Left — Counselor users:**
- List of users with `role = "counselor"`
- Columns: email, créé le
- Filtered client-side from `GET /admin/users` response (no new endpoint)

**Right — Code manager:**
- List of counselor codes: code string (monospace), label, statut (actif/inactif badge), uses_count, créé le
- Copy-to-clipboard button on each code row
- "Désactiver" button (one-way, sets `is_active = false`; no reactivation from UI)
- "Générer un code" button → inline dialog: label text input + confirm button → `POST /admin/counselor-codes`
- Generated code displayed immediately with copy prompt

**New DB model — `CounselorCode`:**
```
id              UUID PK
code            VARCHAR(8) UNIQUE NOT NULL   (random alphanum, uppercase)
label           VARCHAR(255) NOT NULL        (e.g. "Cap Emploi Lyon - Lot 3")
created_by_id   FK → User.id
is_active       BOOLEAN DEFAULT TRUE
uses_count      INTEGER DEFAULT 0
created_at      DATETIME
```

**New backend endpoints:**
- `GET /admin/counselor-codes` → list all codes
- `POST /admin/counselor-codes` body: `{label}` → generates 8-char code, returns new record
- `DELETE /admin/counselor-codes/<id>` → sets `is_active = False` (soft delete)

---

## 7. Coûts API — `/admin/couts/page.tsx`

**Summary strip (top):**
- Total cost (€) this month
- Total tokens Haiku / Sonnet split
- Total analyses count

**Daily breakdown table (30 days):**
- Columns: date, analyses, tokens Haiku in/out, tokens Sonnet in/out, coût estimé (€)
- Totals row at bottom

**Bar chart:**
- Pure SVG bar chart, daily cost bars, Haiku vs Sonnet colored segments (stacked)
- No external charting library

**Cost constants (backend config):**
```python
HAIKU_PRICE_IN  = 0.80   # $/MTok
HAIKU_PRICE_OUT = 4.00   # $/MTok
SONNET_PRICE_IN  = 3.00  # $/MTok
SONNET_PRICE_OUT = 15.00 # $/MTok
```

Model derivation: `free` plan user → Haiku, `paid` plan user → Sonnet (via `Analysis.user` join).

**New endpoint:** `GET /admin/costs?days=30` → `{days: [{date, analyses_count, haiku_tokens_in, haiku_tokens_out, sonnet_tokens_in, sonnet_tokens_out, cost_eur}], total: {...}}`.

---

## Backend Changes Summary

| File | Change |
|---|---|
| `routes/admin.py` | Update `GET /admin/analyses` — add `status`, `search`, `from`, `to` query params |
| `routes/admin.py` | Add `GET /admin/stats/timeseries?days=30` |
| `routes/admin.py` | Add `GET /admin/costs?days=30` |
| `routes/admin.py` | Add `GET /POST /admin/counselor-codes` |
| `routes/admin.py` | Add `DELETE /admin/counselor-codes/<id>` |
| `models/counselor_code.py` | New model: `CounselorCode` |
| `models/__init__.py` | Register `CounselorCode` |

One new DB table. No changes to existing tables.

---

## Out of Scope

- Admin editing user role or plan (read-only)
- Email notifications
- Export (CSV/PDF) of any admin data
- Real-time updates / websockets
