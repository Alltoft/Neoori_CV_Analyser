# Le découpage en sous-domaines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve neoori on three hosts built from one setting, `DOMAIN` — the
root (today's landing, nothing else), `cv.DOMAIN` (the CV analysis) and
`voyage.DOMAIN` (le voyage) — with one sign-in that works on all three.

**Architecture:** One Next.js app routes by host in `proxy.ts`, through pure
functions in `lib/site.ts` (who owns which path, what a request gets, where a
link points); the root layout hands the host to a client context (`useSite`,
`AppLink`, `go`). Flask builds every absolute URL — mail links, the
Google/Microsoft callback, Stripe's return URLs, the CORS list — from `DOMAIN`
in `utils/site.py`; the request's host only picks one of the three origins and
is never copied. The session cookies move to `Domain=DOMAIN` under new names.
nginx answers the four names (root, www, cv, voyage) and refuses the rest.

**Tech Stack:** Flask 3.1, flask-jwt-extended 4.7, Authlib 1.8, pytest;
Next.js 16.2.6 App Router (`proxy.ts` on the Node runtime), TypeScript, Node's
built-in test runner (`node --test`, no new package); nginx 1.29; Docker
compose.

**Spec:** `docs/superpowers/specs/2026-10-09-subdomain-split-design.md` (this
branch, `feat/subdomain-split`). « Decision N » below refers to it. Read it
first, including « Amendments while planning » near its end.

## Before you start (mandatory)

1. Work in the worktree
   `/Users/imran/Downloads/design_handoff_cv_analyzer/.claude/worktrees/subdomain-split`,
   branch `feat/subdomain-split`. It is already rebased on `initial` at
   0825e27 (four doors merged); every file and line reference below was read
   from that code on 2026-10-09. Run every command from the worktree. Never
   `cd` to the main checkout, and never run a bare `git stash`: the stash is
   shared with the main checkout and other worktrees.
2. Python: the worktree has no virtualenv. Use the main checkout's:
   ```bash
   PY=/Users/imran/Downloads/design_handoff_cv_analyzer/backend/venv/bin/python
   ```
   Backend tests: `cd backend && $PY -m pytest tests/<file> -q`. Baseline on
   2026-10-09: `cd backend && $PY -m pytest -q` → **1813 passed**. Every task
   ends with the full suite green.

   Every command block below starts from the worktree root and is meant to
   run as one command. If your shell keeps its directory between commands,
   wrap each `cd` in parentheses — `(cd backend && $PY -m pytest -q)` — and if
   it forgets variables and functions between commands, put the `PY=…`
   assignment in front of each command that uses `$PY`.
3. Frontend: `frontend/node_modules` is installed (`npm ci` ran on
   2026-10-09; run it again if the folder is missing). Checks:
   `cd frontend && npx tsc --noEmit && npm run lint && npm run build`.
   Baseline: tsc clean, lint **11 problems (4 errors, 7 warnings)** — no task
   may add to that count. From Task 7 on, `npm test` runs the frontend's unit
   tests (Node ≥ 22.18 strips TypeScript by itself; this machine has 25.8).
4. Docker: Tasks 6, 8, 10 and 12 use containers. The dev stack's compose
   project is named `neoori`, the same as the main checkout's: `docker compose
   up` from this worktree **replaces** a running dev stack with this branch's
   code and keeps its database volume (this plan adds no migration). Running
   `docker compose up -d` from the main checkout afterwards puts it back. The
   dev compose file reads `backend/.env`, which git does not carry into a
   worktree; link the main checkout's (a link, so the local keys are not
   copied; `.gitignore` covers the name):
   ```bash
   ln -s /Users/imran/Downloads/design_handoff_cv_analyzer/backend/.env backend/.env
   ```
   Its `RESEND_API_KEY` is empty, so dev mails are not sent: the backend log
   prints each account mail's link instead.
5. Never push, deploy, or touch the VPS. Every rollout step (DNS, certificate,
   push) waits for the developer's go (spec, « Rollout »).

## Global Constraints

- `DOMAIN` is the one place the domain is written. The three origins are
  `{PUBLIC_SCHEME}://{prefix}{DOMAIN}{:PUBLIC_PORT}` with prefixes `""`, `"cv."`,
  `"voyage."`; `PUBLIC_SCHEME` defaults to `https`, `PUBLIC_PORT` to empty, and
  both exist for dev only (decisions 19–20).
- An absolute URL is built from the settings, never from the request's Host
  header. The host only selects one of the three origins (decisions 28, 31).
- Session cookies: `neoori_access` / `neoori_refresh`, `Domain=DOMAIN`, no
  `Domain` for a single-label `DOMAIN` such as `localhost` (decisions 25–26).
  The Google/Microsoft state, the signup ticket and `neoori_hold` stay
  host-only (decision 27).
- Host redirects are 307, never 308 (decision 12).
- No route is renamed; `next` / `redirect` keep their checks
  (`utils/auth_links.safe_next`, `lib/safe-redirect.ts`), untouched (decision 29).
- `MAIL_FROM` stays its own setting (decision 23).
- No French UI string is added or changed. Code comments and commit messages
  are in English (CLAUDE.md).
- No new package, frontend or backend.
- Never publish an AAAA record; no subdomain of `DOMAIN` may point anywhere
  but this stack (decision 30).
- Do not touch the four « Portrait out of scope » lines CLAUDE.md lists
  (`README.md:7`, `README.md:43`, `plan.md:248`, CLAUDE.md's
  `## Out of scope` « - Portrait module »).

## Review Focus

1. **Hosts as browsers, proxies and tools really send them** — uppercase, a
   port, a trailing dot, `www.`, an IP, a lookalike such as
   `cv.neoori.tech.evil.example`: the same app as the plain name, otherwise
   the root (frontend routing) or cv (backend mails and callback). Pinned in
   Task 1 (backend) and Task 7 (frontend).
2. **Links already sent, opened on the root after the deploy**, with a token
   in a percent-encoded query: they arrive on cv with the query byte for
   byte. Pinned in Task 7 (`route` keeps an encoded query untouched).
3. **A `next` / `redirect` owned by the other app after a sign-in**: the
   person ends on that page, signed in, through a full page load, query
   kept. Pinned in Task 7 (`resolveHref` with a query) and Task 9 (`go`
   rests on it); walked in Task 12.
4. **A forged Host on an endpoint that sends a mail**: the link names cv,
   never the forged name. Pinned in Task 3, on the mail builders and through
   `POST /api/auth/forgot-password`.
5. **Signing out on one host while another host's page is open**: the other
   host is signed out at its next request. Pinned in Task 2 (logout clears
   both session cookies on the domain).

---

## File structure

| File | Responsibility | Task |
|---|---|---|
| `backend/app/utils/site.py` (new) | The three origins from `DOMAIN`; which app a host is; the requesting origin; the cookie domain | 1 |
| `backend/app/config.py` | `DOMAIN`, `PUBLIC_SCHEME`, `PUBLIC_PORT`; cookie names; `APP_URL` and `FRONTEND_ORIGINS` removed | 1, 2, 5 |
| `backend/app/__init__.py` | `JWT_COOKIE_DOMAIN` from `DOMAIN`; CORS from the three origins | 2, 5 |
| `backend/app/services/email_service.py` | Each mail's link host (decision 31) | 3 |
| `backend/app/routes/auth_oauth.py` | Callback per host; `/start` elsewhere goes to cv; home per host | 4 |
| `backend/app/routes/payments.py` | Stripe returns to cv | 5 |
| `nginx/templates-https/default.conf.template` | Four names; default servers refuse the rest; `$host` logged | 6 |
| `nginx/templates-http/default.conf.template`, `nginx/dev.conf` | Catch-all kept; `$host` logged | 6 |
| `docker-compose.yml`, `docker-compose.prod.yml` | `DOMAIN` (+ dev's `PUBLIC_*`) for backend and frontend | 6 |
| `.env.example`, `backend/.env.example` | `DOMAIN` documented as the one setting | 6 |
| `frontend/next.config.ts` | `allowedDevOrigins` for the dev subdomains | 6 |
| `frontend/src/lib/site.ts` (new) | Ownership table and routing, as pure functions | 7 |
| `frontend/src/lib/sign-in-gate.ts` (new) | The proxy's sign-in gate, as a pure function | 7 |
| `frontend/src/lib/site.test.ts`, `home.test.ts` (new) | `node --test` unit tests | 7, 9 |
| `frontend/src/proxy.ts` | Host routing first, then the gate | 2, 7 |
| `frontend/src/lib/site-server.ts` (new) | `currentSite()` for server components | 8 |
| `frontend/src/lib/site-context.tsx` (new) | `SiteProvider`, `useSite()` (`app`, `href`, `go`), `AppLink` | 8 |
| `frontend/src/app/layout.tsx` | Per-request metadata; wraps the app in `SiteProvider` | 8 |
| `frontend/Dockerfile`, `.github/workflows/deploy.yml` | `NEXT_PUBLIC_SITE_URL` build-arg removed | 8 |
| `frontend/src/lib/home.ts` | `homeFor(role, app)` | 9 |
| `AppBar.tsx`, `admin/layout.tsx`, five `(auth)` pages | Home per host, logout to the root, `go()` after sign-in | 9 |
| `SiteNav.tsx`, `SiteFooter.tsx`, `AuthLayout.tsx`, `app/page.tsx`, `espace`, `analyse/nouveau`, `analyse/envoyee`, `c/[token]`, `voyage/c/[token]` | Cross-host links through `AppLink` | 10 |
| `CLAUDE.md`, `DOCKER.md`, `TEST-PLAN.md`, `AUTOMATION-PLAN.md`, `handoff.md`, `frontend/README.md` | Docs | 11 |

---

### Task 1: The one setting and the backend's site helpers

**Files:**
- Modify: `backend/app/config.py` (helper after `_addresses`, lines 8–10; block after `MAIL_FROM`, line 37; `TestingConfig`, lines 94–103)
- Create: `backend/app/utils/site.py`
- Test: `backend/tests/test_site.py` (new)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `app.config._domain(raw: str) -> str` — trimmed, lowercased, no trailing dot; blank → `"localhost"`.
  - Config keys `DOMAIN: str`, `PUBLIC_SCHEME: str`, `PUBLIC_PORT: str`.
  - `app.utils.site.APPS = ("root", "cv", "voyage")`
  - `site.origin(app: str, config=None) -> str` — `config` defaults to `current_app.config`.
  - `site.origins(config=None) -> list[str]` — the three origins, root first.
  - `site.cookie_domain(domain: str) -> str | None`
  - `site.app_of_host(host: str | None, domain: str) -> str | None`
  - `site.request_app() -> str | None` — `None` outside a request.
  - `site.request_origin() -> str` — cv's or voyage's origin, cv's for anything else.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_site.py`:

```python
"""DOMAIN, the one setting, and what is built from it (subdomain split spec,
decisions 19–20, 26 and 31)."""
import pytest

from app.config import _domain
from app.utils import site


@pytest.fixture
def neoori(app):
    app.config.update(DOMAIN="neoori.tech", PUBLIC_SCHEME="https", PUBLIC_PORT="")
    return app


@pytest.mark.parametrize("raw, expected", [
    ("neoori.tech", "neoori.tech"),
    (" Neoori.Tech. ", "neoori.tech"),
    ("", "localhost"),
    ("   ", "localhost"),
])
def test_domain_is_read_trimmed_and_lowercased(raw, expected):
    assert _domain(raw) == expected


def test_the_tests_run_on_a_single_label_domain(app):
    assert app.config["DOMAIN"] == "localhost"
    assert app.config["PUBLIC_SCHEME"] == "https"
    assert app.config["PUBLIC_PORT"] == ""


def test_the_three_origins_come_from_domain(neoori):
    assert site.origin("root") == "https://neoori.tech"
    assert site.origin("cv") == "https://cv.neoori.tech"
    assert site.origin("voyage") == "https://voyage.neoori.tech"
    assert site.origins() == [
        "https://neoori.tech", "https://cv.neoori.tech", "https://voyage.neoori.tech",
    ]


def test_dev_adds_its_scheme_and_port(app):
    app.config.update(DOMAIN="neoori.localhost", PUBLIC_SCHEME="http", PUBLIC_PORT="8080")
    assert site.origin("cv") == "http://cv.neoori.localhost:8080"


def test_an_explicit_config_needs_no_app_context():
    config = {"DOMAIN": "example.fr", "PUBLIC_SCHEME": "https", "PUBLIC_PORT": ""}
    assert site.origins(config) == [
        "https://example.fr", "https://cv.example.fr", "https://voyage.example.fr",
    ]


@pytest.mark.parametrize("host, expected", [
    ("neoori.tech", "root"),
    ("cv.neoori.tech", "cv"),
    ("voyage.neoori.tech", "voyage"),
    ("CV.Neoori.Tech", "cv"),
    ("cv.neoori.tech:8080", "cv"),
    ("voyage.neoori.tech.", "voyage"),
    ("www.neoori.tech", None),
    ("attacker.example", None),
    ("cv.neoori.tech.evil.example", None),
    ("cv.neoori.techx", None),
    ("x@cv.neoori.tech", None),
    ("186.240.157.26", None),
    ("[::1]:5000", None),
    ("", None),
    (None, None),
])
def test_which_app_a_host_is(host, expected):
    assert site.app_of_host(host, "neoori.tech") == expected


def test_outside_a_request_there_is_no_app_and_the_origin_is_cv(neoori):
    assert site.request_app() is None
    assert site.request_origin() == "https://cv.neoori.tech"


@pytest.mark.parametrize("host, expected", [
    ("cv.neoori.tech", "https://cv.neoori.tech"),
    ("voyage.neoori.tech", "https://voyage.neoori.tech"),
    ("Voyage.Neoori.Tech:8080", "https://voyage.neoori.tech"),
    ("neoori.tech", "https://cv.neoori.tech"),
    ("attacker.example", "https://cv.neoori.tech"),
])
def test_the_requesting_origin_is_cv_or_voyage_never_the_host_itself(neoori, host, expected):
    with neoori.test_request_context("/", base_url=f"http://{host}"):
        assert site.request_origin() == expected


@pytest.mark.parametrize("domain, expected", [
    ("neoori.tech", "neoori.tech"),
    ("neoori.localhost", "neoori.localhost"),
    ("localhost", None),
])
def test_the_cookie_domain(domain, expected):
    assert site.cookie_domain(domain) == expected
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && $PY -m pytest tests/test_site.py -q`
Expected: collection error, `ImportError: cannot import name '_domain' from 'app.config'`.

- [ ] **Step 3: Add the settings to `config.py`**

In `backend/app/config.py`, after the `_addresses` function (line 10), add:

```python


def _domain(raw: str) -> str:
    """DOMAIN as the code compares it: trimmed, lowercased, no trailing dot.
    Blank is localhost, like the frontend's fallback (lib/site.ts)."""
    return raw.strip().lower().rstrip(".") or "localhost"
```

Replace:

```python
    # Resend refuses a From on an unverified domain, so neoori.tech must carry
    # the DNS records before the first mail goes out.
    MAIL_FROM = os.environ.get("MAIL_FROM", "neoori <bonjour@neoori.tech>")
```

with:

```python
    # Resend refuses a From on an unverified domain, so neoori.tech must carry
    # the DNS records before the first mail goes out. Not derived from DOMAIN
    # on purpose (subdomain split spec, decision 23): a refused mail fails
    # silently, so a domain swap would quietly stop every mail. Verify the new
    # domain in Resend first, then change this.
    MAIL_FROM = os.environ.get("MAIL_FROM", "neoori <bonjour@neoori.tech>")
    # The base domain, written here and nowhere else (subdomain split spec,
    # decision 19). The app answers on DOMAIN (the landing), cv.DOMAIN and
    # voyage.DOMAIN; app/utils/site.py builds every absolute URL from it.
    # nginx and the frontend read the same line of /srv/neoori/.env.
    DOMAIN = _domain(os.environ.get("DOMAIN", ""))
    # Dev only (decision 20): the local stack is http on :8080. Production
    # sets neither.
    PUBLIC_SCHEME = os.environ.get("PUBLIC_SCHEME", "").strip() or "https"
    PUBLIC_PORT = os.environ.get("PUBLIC_PORT", "").strip()
```

(`APP_URL` stays below it until Task 5.)

In `TestingConfig`, after `BCRYPT_LOG_ROUNDS = 4`, add:

```python
    # Whatever a developer's .env says. Single-label on purpose: the session
    # cookies stay host-only (spec decision 26), so the test client's cookie
    # jar, which runs on localhost, keeps working. A test that needs the
    # Domain attribute builds an app with a dotted DOMAIN itself.
    DOMAIN = "localhost"
    PUBLIC_SCHEME = "https"
    PUBLIC_PORT = ""
```

- [ ] **Step 4: Create `backend/app/utils/site.py`**

```python
"""Which host a request is on, and the three public origins (subdomain split
spec, decisions 19–31).

DOMAIN is the one setting the domain is written in. Every absolute URL the
backend writes — a mail link, the Google/Microsoft callback, Stripe's return
URLs, the CORS allow-list — is built here from it. The request's Host header
only ever *selects* one of the three origins: it is never copied into a URL,
so a forged Host cannot put its own name into a reset link.
"""
from flask import current_app, has_request_context, request

# The root shows the landing, cv is « J'ai une cible », voyage is le voyage.
APPS = ("root", "cv", "voyage")
_PREFIX = {"root": "", "cv": "cv.", "voyage": "voyage."}


def origin(app: str, config=None) -> str:
    """`{scheme}://{prefix}{DOMAIN}{:port}` for "root", "cv" or "voyage".
    `config` defaults to the current app's; create_app passes its own,
    before an app context exists."""
    cfg = current_app.config if config is None else config
    port = f":{cfg['PUBLIC_PORT']}" if cfg["PUBLIC_PORT"] else ""
    return f"{cfg['PUBLIC_SCHEME']}://{_PREFIX[app]}{cfg['DOMAIN']}{port}"


def origins(config=None) -> list[str]:
    """The three origins, root first: the CORS allow-list (decision 32)."""
    return [origin(app, config) for app in APPS]


def cookie_domain(domain: str) -> str | None:
    """The session cookies' Domain: the whole DOMAIN, so one sign-in covers
    every host (decision 25). None for a single-label name such as
    localhost, which browsers refuse as a cookie domain: the attribute would
    only lose the cookie (decision 26)."""
    return domain if "." in domain else None


def app_of_host(host: str | None, domain: str) -> str | None:
    """"root", "cv" or "voyage" for a Host header value, None for any other
    name. Case, the port and a trailing dot are ignored."""
    name = (host or "").strip().lower().partition(":")[0].rstrip(".")
    for app in APPS:
        if name == _PREFIX[app] + domain:
            return app
    return None


def request_app() -> str | None:
    """The app of the request being served. None outside a request (a
    background run, a CLI command) and on any other name."""
    if not has_request_context():
        return None
    return app_of_host(request.host, current_app.config["DOMAIN"])


def request_origin() -> str:
    """The origin of cv or voyage when the request is on one of them, cv's
    otherwise: the root (it serves no sign-in page), an unknown or forged
    name, no request at all (decision 31)."""
    app = request_app()
    return origin(app if app in ("cv", "voyage") else "cv")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && $PY -m pytest tests/test_site.py -q`
Expected: all pass (32 tests).

- [ ] **Step 6: Run the full suite**

Run: `cd backend && $PY -m pytest -q`
Expected: 1845 passed (1813 + 32), nothing else changed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/config.py backend/app/utils/site.py backend/tests/test_site.py
git commit -m "$(cat <<'EOF'
feat(site): DOMAIN is the one setting; the backend builds its origins from it

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: One sign-in on every host

**Files:**
- Modify: `backend/app/config.py` (after `JWT_COOKIE_CSRF_PROTECT`, line 31)
- Modify: `backend/app/__init__.py` (imports, lines 4–6; `create_app`, line 200)
- Modify: `frontend/src/proxy.ts:27`
- Modify (rename only): `backend/tests/test_admin_email_verification.py`, `test_auth_gate.py`, `test_auth_link_routes.py`, `test_counselor_apply.py`, `test_demande_mail.py`, `test_email_link_routes.py`, `test_held_drafts.py`, `test_oauth_routes.py`, `test_signup_ticket_routes.py`
- Test: `backend/tests/test_session_cookies.py` (new)

**Interfaces:**
- Consumes: Task 1's `site.cookie_domain`, config `DOMAIN`.
- Produces: config `JWT_ACCESS_COOKIE_NAME = "neoori_access"`,
  `JWT_REFRESH_COOKIE_NAME = "neoori_refresh"`, `JWT_COOKIE_DOMAIN` (set in
  `create_app`). The frontend's gate reads cookie `neoori_access` (Task 7 keeps
  that name in `lib/sign-in-gate.ts`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_session_cookies.py`:

```python
"""One sign-in for every host (subdomain split spec, decisions 25–27)."""
from datetime import datetime

import pytest
from flask_jwt_extended import create_refresh_token

from app import create_app
from app.config import TestingConfig
from app.extensions import bcrypt, db
from app.models.user import User
from app.utils import auth_links


def _set_cookie(res, name: str) -> str:
    """The Set-Cookie line of one cookie."""
    return next(c for c in res.headers.getlist("Set-Cookie") if c.startswith(f"{name}="))


def _names(res) -> set[str]:
    return {c.split("=", 1)[0] for c in res.headers.getlist("Set-Cookie")}


def _user(email="marie@test.fr", password="motdepasse1") -> User:
    user = User(
        email=email, role="candidate", email_verified_at=datetime.utcnow(),
        password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
    )
    db.session.add(user)
    db.session.commit()
    return user


def _login(client):
    return client.post("/api/auth/login", json={"email": "marie@test.fr", "password": "motdepasse1"})


@pytest.fixture
def dotted_app(monkeypatch):
    """An app built with a dotted DOMAIN. Built from scratch rather than by
    editing the shared fixture's config: create_app derives the cookie domain
    once, when it builds the app."""
    monkeypatch.setattr(TestingConfig, "DOMAIN", "neoori.test")
    application = create_app("testing")
    application.config["RESEND_API_KEY"] = None
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def test_the_session_cookies_have_new_names(app, client):
    _user()
    res = _login(client)
    assert res.status_code == 200
    assert {"neoori_access", "neoori_refresh"} <= _names(res)
    assert not {"access_token_cookie", "refresh_token_cookie"} & _names(res)


def test_a_single_label_domain_keeps_them_on_one_host(app, client):
    assert app.config["JWT_COOKIE_DOMAIN"] is None
    _user()
    res = _login(client)
    assert "Domain=" not in _set_cookie(res, "neoori_access")
    assert "Domain=" not in _set_cookie(res, "neoori_refresh")


def test_a_dotted_domain_puts_them_on_every_host(dotted_app):
    assert dotted_app.config["JWT_COOKIE_DOMAIN"] == "neoori.test"
    _user()
    res = _login(dotted_app.test_client())
    assert "Domain=neoori.test" in _set_cookie(res, "neoori_access")
    assert "Domain=neoori.test" in _set_cookie(res, "neoori_refresh")


def test_refresh_reissues_the_access_cookie_on_the_domain(dotted_app):
    user = _user()
    token = create_refresh_token(
        identity=user.id,
        additional_claims={"pwv": auth_links.password_fingerprint(user.password_hash)},
    )
    res = dotted_app.test_client().post(
        "/api/auth/refresh", headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "Domain=neoori.test" in _set_cookie(res, "neoori_access")


def test_logout_clears_the_session_everywhere_and_the_hold_on_its_host(dotted_app):
    # Review Focus 5: a tab left open on the other host is signed out at its
    # next request, because the cookies it would send are gone domain-wide.
    res = dotted_app.test_client().post("/api/auth/logout")
    assert res.status_code == 200
    for name in ("neoori_access", "neoori_refresh"):
        line = _set_cookie(res, name)
        assert "Domain=neoori.test" in line
        assert "Expires=Thu, 01 Jan 1970" in line
    assert "Domain=" not in _set_cookie(res, "neoori_hold")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && $PY -m pytest tests/test_session_cookies.py -q`
Expected: 5 failed — `StopIteration` wherever `neoori_access` is looked for
(the cookies are still `access_token_cookie`), and `assert None == 'neoori.test'`
(flask-jwt-extended defaults `JWT_COOKIE_DOMAIN` to `None`, so nothing sets it
yet).

- [ ] **Step 3: Rename the cookies and derive their domain**

In `backend/app/config.py`, after `JWT_COOKIE_CSRF_PROTECT = False` (line 31), add:

```python
    # Subdomain split spec, decision 25: one session for every host. The
    # cookies carry Domain=DOMAIN (create_app sets JWT_COOKIE_DOMAIN from
    # site.cookie_domain), under new names: browsers still hold the old
    # host-only `access_token_cookie` on the root, and under the same name the
    # root would receive two cookies and Flask would read whichever came
    # first. frontend/src/lib/sign-in-gate.ts SESSION_COOKIE names the access
    # cookie too: keep the two in step.
    JWT_ACCESS_COOKIE_NAME = "neoori_access"
    JWT_REFRESH_COOKIE_NAME = "neoori_refresh"
```

In `backend/app/__init__.py`, replace:

```python
from .config import config
from .extensions import db, migrate, jwt, bcrypt, cors
```

with:

```python
from .config import config
from .extensions import db, migrate, jwt, bcrypt, cors
from .utils import site
```

and replace:

```python
    app.config.from_object(config.get(env, config["default"]))
    app.url_map.strict_slashes = False
```

with:

```python
    app.config.from_object(config.get(env, config["default"]))
    # The session cookies span every host of DOMAIN (subdomain split spec,
    # decisions 25–26). Derived here, so DOMAIN stays the one setting.
    app.config["JWT_COOKIE_DOMAIN"] = site.cookie_domain(app.config["DOMAIN"])
    app.url_map.strict_slashes = False
```

In `frontend/src/proxy.ts`, replace:

```ts
  const hasToken = req.cookies.has("access_token_cookie")
```

with:

```ts
  // backend/app/config.py JWT_ACCESS_COOKIE_NAME (subdomain split spec,
  // decision 25).
  const hasToken = req.cookies.has("neoori_access")
```

(Task 7 rewrites this file; the name must change now, or a gated page would
send every signed-in person to /connexion until then.)

- [ ] **Step 4: Move the existing assertions to the new names**

```bash
cd backend/tests && perl -pi -e 's/access_token_cookie/neoori_access/g; s/refresh_token_cookie/neoori_refresh/g' \
  test_admin_email_verification.py test_auth_gate.py test_auth_link_routes.py \
  test_counselor_apply.py test_demande_mail.py test_email_link_routes.py \
  test_held_drafts.py test_oauth_routes.py test_signup_ticket_routes.py
grep -rn "access_token_cookie\|refresh_token_cookie" . ; echo "grep exit: $?"
```

Expected: no matches, `grep exit: 1`. (25 assertions, plus the
`REFRESH_COOKIE` regex in `test_admin_email_verification.py:10`.)

- [ ] **Step 5: Run the new and the renamed tests**

Run: `cd backend && $PY -m pytest tests/test_session_cookies.py tests/test_auth_gate.py tests/test_held_drafts.py tests/test_admin_email_verification.py -q`
Expected: all pass.

- [ ] **Step 6: Run the full suite and the frontend type check**

Run: `cd backend && $PY -m pytest -q` → 1850 passed (1845 + 5).
Run: `cd frontend && npx tsc --noEmit` → no output.

- [ ] **Step 7: Commit**

```bash
git add backend/app/config.py backend/app/__init__.py frontend/src/proxy.ts backend/tests
git commit -m "$(cat <<'EOF'
feat(auth): one session on every host — neoori_access / neoori_refresh on Domain=DOMAIN

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Each mail links to the right host

**Files:**
- Modify: `backend/app/services/email_service.py` (docstring, lines 1–7; imports, line 15; `_app_url`, lines 20–21; call sites at lines 82, 198, 220, 244, 285, 314, 335, 353, 371, 425)
- Modify: `backend/tests/test_login_link_mail.py:32,38`, `test_transactional_mails.py:107,116,118,167,176,212,228`, `test_email_service.py:66-71`, `test_auth_mail.py:23,30`
- Test: `backend/tests/test_mail_hosts.py` (new)

**Interfaces:**
- Consumes: Task 1's `site.origin("cv")`, `site.request_origin()`.
- Produces: no new names. `email_service._app_url` is gone.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_mail_hosts.py`:

```python
"""Where each mail links (subdomain split spec, decision 31): an account mail
to the host it was asked from, every other mail to cv, and never to a name
the request made up."""
from contextlib import nullcontext
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.services import email_service

SEND = "app.services.email_service.resend.Emails.send"


@pytest.fixture
def mailer(app):
    app.config.update(RESEND_API_KEY="re_test", DOMAIN="neoori.tech")
    return app


def _sent(mock_send) -> dict:
    return mock_send.call_args[0][0]


ACCOUNT_MAILS = {
    "verification": (lambda user: email_service.send_verification(user), "/verifier-email?token="),
    "reset": (lambda user: email_service.send_password_reset(user), "/reinitialiser-mot-de-passe?token="),
    "sign-in link": (lambda user: email_service.send_login_link(user.email, "", "tok"), "/connexion/lien?token=tok"),
    "password changed": (lambda user: email_service.send_password_changed(user), "/mot-de-passe-oublie"),
}


@pytest.mark.parametrize("mail", ACCOUNT_MAILS)
@pytest.mark.parametrize("host, origin", [
    ("cv.neoori.tech", "https://cv.neoori.tech"),
    ("voyage.neoori.tech", "https://voyage.neoori.tech"),
    ("neoori.tech", "https://cv.neoori.tech"),
    ("attacker.example", "https://cv.neoori.tech"),
])
def test_an_account_mail_links_to_the_host_it_was_asked_from(mailer, make_user, mail, host, origin):
    send, path = ACCOUNT_MAILS[mail]
    user = make_user(verified=False)
    with mailer.test_request_context("/api/auth/x", base_url=f"https://{host}"), \
            patch(SEND, return_value={"id": "1"}) as mock_send:
        assert send(user) is True
    sent = _sent(mock_send)
    assert f'href="{origin}{path}' in sent["html"]
    assert f"{origin}{path}" in sent["text"]
    # Review Focus 4: a forged Host never reaches a mail body.
    assert "attacker.example" not in sent["html"] + sent["text"]


@pytest.mark.parametrize("host, origin", [
    ("voyage.neoori.tech", "https://voyage.neoori.tech"),
    ("attacker.example", "https://cv.neoori.tech"),
])
def test_a_reset_asked_through_the_route_links_to_its_host(mailer, client, make_user, host, origin):
    make_user(email="marie@test.fr")
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        res = client.post("/api/auth/forgot-password", json={"email": "marie@test.fr"},
                          base_url=f"https://{host}")
    assert res.status_code == 200
    html = _sent(mock_send)["html"]
    assert f'href="{origin}/reinitialiser-mot-de-passe?token=' in html
    assert "attacker.example" not in html


CV_MAILS = {
    "analysis ready": (
        lambda: email_service.send_analysis_ready("m@test.fr", "", unlocked=False),
        "https://cv.neoori.tech/espace",
    ),
    "analysis failed": (
        lambda: email_service.send_analysis_failed("m@test.fr", "", unlocked=False, analysis_id="a-1"),
        "https://cv.neoori.tech/espace",
    ),
    "counselor analysis ready": (
        lambda: email_service.send_counselor_analysis_ready("c@test.fr"),
        "https://cv.neoori.tech/conseiller",
    ),
    "counselor analysis failed": (
        lambda: email_service.send_counselor_analysis_failed("c@test.fr"),
        "https://cv.neoori.tech/conseiller",
    ),
    "new demande": (
        lambda: email_service.send_new_demande("a@test.fr", ""),
        "https://cv.neoori.tech/admin/conseillers",
    ),
}


@pytest.mark.parametrize("mail", CV_MAILS)
@pytest.mark.parametrize("host", [None, "voyage.neoori.tech"])
def test_every_other_mail_links_to_cv(mailer, mail, host):
    send, link = CV_MAILS[mail]
    context = mailer.test_request_context("/", base_url=f"https://{host}") if host else nullcontext()
    with context, patch(SEND, return_value={"id": "1"}) as mock_send:
        assert send() is True
    assert f'href="{link}"' in _sent(mock_send)["html"]


def test_the_approval_mail_links_to_cv_even_when_approved_from_voyage(mailer, make_user):
    user = make_user(email="claire@capemploi.fr")
    profile = CounselorProfile(user_id=user.id, structure="Cap Emploi 31",
                               fonction="Conseillère", telephone="0561000000", status="approved")
    db.session.add(profile)
    db.session.commit()
    with mailer.test_request_context("/", base_url="https://voyage.neoori.tech"), \
            patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_counselor_approved(profile) is True
    assert 'href="https://cv.neoori.tech/conseiller"' in _sent(mock_send)["html"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && $PY -m pytest tests/test_mail_hosts.py -q`
Expected: FAIL — every link still reads `https://neoori.tech/...` (the
`APP_URL` default), so each `href="https://cv.…"` / `href="https://voyage.…"`
assertion fails.

- [ ] **Step 3: Build each link from the site helpers**

In `backend/app/services/email_service.py`:

Replace the module docstring:

```python
"""Transactional email. The app's first — resend was in requirements and
RESEND_API_KEY in config, with nothing calling either.

Fail-soft by contract: send() returns False and logs, and never raises. It is
called after the decision has already committed, and a provider outage must not
turn a successful approval into a 500 the admin retries.
"""
```

with:

```python
"""Transactional email. The app's first — resend was in requirements and
RESEND_API_KEY in config, with nothing calling either.

Fail-soft by contract: send() returns False and logs, and never raises. It is
called after the decision has already committed, and a provider outage must not
turn a successful approval into a 500 the admin retries.

Links (subdomain split spec, decision 31): an account mail — verification,
reset, sign-in link, password changed — links to the host it was asked from,
site.request_origin(); every other mail links to cv. Neither copies the
request's Host header.
"""
```

Replace `from ..utils import auth_links` with `from ..utils import auth_links, site`.

Delete:

```python
def _app_url() -> str:
    return current_app.config["APP_URL"]


```

Then replace each call site (left: current text; right: new text):

| Line | Current | New |
|---|---|---|
| 82 | `f'<p><a href="{_app_url()}/conseiller" '` | `f'<p><a href="{site.origin("cv")}/conseiller" '` |
| 198 | `link = f"{_app_url()}/verifier-email?token={auth_links.make_verify_token(user, next_path)}"` | `link = f"{site.request_origin()}/verifier-email?token={auth_links.make_verify_token(user, next_path)}"` |
| 220 | `link = f"{_app_url()}/reinitialiser-mot-de-passe?token={auth_links.make_reset_token(user)}"` | `link = f"{site.request_origin()}/reinitialiser-mot-de-passe?token={auth_links.make_reset_token(user)}"` |
| 244 | `link = f"{_app_url()}/connexion/lien?token={token}"` | `link = f"{site.request_origin()}/connexion/lien?token={token}"` |
| 285 | `button=("Ouvrir mon espace", f"{_app_url()}/espace"),` | `button=("Ouvrir mon espace", f"{site.origin('cv')}/espace"),` |
| 314 | `button=("Ouvrir mon espace", f"{_app_url()}/espace"),` | `button=("Ouvrir mon espace", f"{site.origin('cv')}/espace"),` |
| 335 | `button=("Ouvrir mon espace conseiller", f"{_app_url()}/conseiller"),` | `button=("Ouvrir mon espace conseiller", f"{site.origin('cv')}/conseiller"),` |
| 353 | `button=("Ouvrir mon espace conseiller", f"{_app_url()}/conseiller"),` | `button=("Ouvrir mon espace conseiller", f"{site.origin('cv')}/conseiller"),` |
| 371 | `button=("Voir les demandes", f"{_app_url()}/admin/conseillers"),` | `button=("Voir les demandes", f"{site.origin('cv')}/admin/conseillers"),` |
| 425 | `button=("Choisir un nouveau mot de passe", f"{_app_url()}/mot-de-passe-oublie"),` | `button=("Choisir un nouveau mot de passe", f"{site.request_origin()}/mot-de-passe-oublie"),` |

(Line 82's double quotes inside a single-quoted f-string are valid from
Python 3.12; the venv and the production image run 3.14.) Then confirm
nothing is left:

```bash
grep -n "_app_url\|APP_URL" backend/app/services/email_service.py ; echo "grep exit: $?"
```

Expected: `grep exit: 1`.

- [ ] **Step 4: Move the existing mail tests to `DOMAIN`**

```bash
cd backend/tests && perl -pi -e 's/app\.config\["APP_URL"\] = "https:\/\/neoori\.tech"/app.config["DOMAIN"] = "neoori.tech"/g; s#https://neoori\.tech/#https://cv.neoori.tech/#g' \
  test_login_link_mail.py test_transactional_mails.py test_auth_mail.py
```

In `backend/tests/test_email_service.py`, replace:

```python
def test_the_approval_link_follows_app_url(app):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["APP_URL"] = "http://localhost:8080"
    with patch("app.services.email_service.resend.Emails.send") as mock_send:
        email_service.send_counselor_approved(_profile())
    assert "http://localhost:8080/conseiller" in mock_send.call_args[0][0]["html"]
```

with:

```python
def test_the_approval_link_goes_to_cv(app):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config.update(DOMAIN="neoori.localhost", PUBLIC_SCHEME="http", PUBLIC_PORT="8080")
    with patch("app.services.email_service.resend.Emails.send") as mock_send:
        email_service.send_counselor_approved(_profile())
    assert "http://cv.neoori.localhost:8080/conseiller" in mock_send.call_args[0][0]["html"]
```

Then:

```bash
grep -rn "APP_URL" backend/tests ; echo "grep exit: $?"
```

Expected: only `test_oauth_routes.py:149` (Task 4 moves it).

- [ ] **Step 5: Run the mail tests**

Run: `cd backend && $PY -m pytest tests/test_mail_hosts.py tests/test_login_link_mail.py tests/test_transactional_mails.py tests/test_email_service.py tests/test_auth_mail.py -q`
Expected: all pass.

- [ ] **Step 6: Run the full suite**

Run: `cd backend && $PY -m pytest -q`
Expected: 1879 passed (1850 + 29).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/email_service.py backend/tests
git commit -m "$(cat <<'EOF'
feat(mail): account mails link to the host they were asked from, the rest to cv

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Google / Microsoft sign-in on the host it started on

**Files:**
- Modify: `backend/app/routes/auth_oauth.py` (import line 17; `start`, lines 38–45; landing, line 112; `_redirect_uri`, lines 135–137; `_home_path`, lines 150–157)
- Modify: `backend/tests/test_oauth_routes.py` (after the `providers` fixture, line 51; `_start`, `_callback`, `_sign_in`, lines 58–101; the start test, lines 148–155; new tests at the end)

**Interfaces:**
- Consumes: Task 1's `site.request_app()`, `site.request_origin()`, `site.origin()`.
- Produces: `auth_oauth._home_path(role: str, app: str | None = None) -> str`
  — the frontend's `homeFor(role, app)` (Task 9) must say the same.

- [ ] **Step 1: Put the OAuth tests on cv by default**

In `backend/tests/test_oauth_routes.py`, after the `providers` fixture (it
ends at line 51, `lambda self: dict(METADATA[self.name]))`), add:

```python


# Every request in this file is made on cv.localhost unless a test names
# another host: /start anywhere else hands the sign-in over to cv first, and
# the state cookie lives on the host that set it (subdomain split spec,
# decision 28). TestingConfig's DOMAIN is localhost.
CV = "https://cv.localhost"


class _OnCv:
    """The test client, on cv.localhost by default."""

    def __init__(self, client):
        self._client = client

    def get(self, *args, **kwargs):
        kwargs.setdefault("base_url", CV)
        return self._client.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        kwargs.setdefault("base_url", CV)
        return self._client.post(*args, **kwargs)

    def get_cookie(self, key, domain="cv.localhost", path="/"):
        return self._client.get_cookie(key, domain=domain, path=path)

    def __getattr__(self, name):
        return getattr(self._client, name)


@pytest.fixture
def client(app):
    return _OnCv(app.test_client())
```

Replace:

```python
def _start(client, provider, next_path=None):
    path = f"/api/auth/{provider}/start"
    if next_path is not None:
        path += "?next=" + quote(next_path, safe="")
    return client.get(path)
```

with:

```python
def _start(client, provider, next_path=None, **request_kwargs):
    path = f"/api/auth/{provider}/start"
    if next_path is not None:
        path += "?next=" + quote(next_path, safe="")
    return client.get(path, **request_kwargs)
```

Replace `def _callback(client, provider, claims, *, state, seen=None):` with
`def _callback(client, provider, claims, *, state, seen=None, **request_kwargs):`
and, at the end of that function, replace

```python
        return client.get(f"/api/auth/{provider}/callback?code=the-code&state={state}")
```

with

```python
        return client.get(f"/api/auth/{provider}/callback?code=the-code&state={state}",
                          **request_kwargs)
```

Replace:

```python
def _sign_in(client, provider, next_path=None, **claims):
    q = _query(_start(client, provider, next_path))
    return _callback(client, provider, _id_claims(provider, q["nonce"], **claims), state=q["state"])
```

with:

```python
def _sign_in(client, provider, next_path=None, *, base_url=CV, **claims):
    q = _query(_start(client, provider, next_path, base_url=base_url))
    return _callback(client, provider, _id_claims(provider, q["nonce"], **claims),
                     state=q["state"], base_url=base_url)
```

Replace:

```python
def test_google_start_asks_for_an_account_with_pkce_and_a_nonce(client, app, providers):
    app.config["APP_URL"] = "https://neoori.tech"
    res = _start(client, "google")
    assert res.status_code == 302
    assert res.headers["Location"].startswith(METADATA["google"]["authorization_endpoint"])
    q = _query(res)
    assert q["client_id"] == "google-client"
    assert q["redirect_uri"] == "https://neoori.tech/api/auth/google/callback"
```

with:

```python
def test_google_start_asks_for_an_account_with_pkce_and_a_nonce(client, app, providers):
    app.config["DOMAIN"] = "neoori.tech"
    res = _start(client, "google", base_url="https://cv.neoori.tech")
    assert res.status_code == 302
    assert res.headers["Location"].startswith(METADATA["google"]["authorization_endpoint"])
    q = _query(res)
    assert q["client_id"] == "google-client"
    assert q["redirect_uri"] == "https://cv.neoori.tech/api/auth/google/callback"
```

- [ ] **Step 2: Add the failing host tests**

Append to `backend/tests/test_oauth_routes.py`:

```python


# ── hosts (subdomain split spec, decisions 15 and 28) ─────────────────────────

def test_each_subdomain_gets_its_own_callback(client, app, providers):
    app.config["DOMAIN"] = "neoori.tech"
    for host in ("cv.neoori.tech", "voyage.neoori.tech"):
        q = _query(_start(client, "google", base_url=f"https://{host}"))
        assert q["redirect_uri"] == f"https://{host}/api/auth/google/callback"


@pytest.mark.parametrize("host", ["neoori.tech", "www.neoori.tech", "attacker.example"])
def test_start_anywhere_else_hands_over_to_cv_before_writing_any_state(client, app, providers, host):
    app.config["DOMAIN"] = "neoori.tech"
    res = _start(client, "google", "/voyage?a=b", base_url=f"https://{host}")
    assert res.status_code == 302
    assert res.headers["Location"] == (
        "https://cv.neoori.tech/api/auth/google/start?next=%2Fvoyage%3Fa%3Db"
    )
    assert "session=" not in _cookies(res)


def test_a_start_without_next_hands_over_without_a_query(client, app, providers):
    app.config["DOMAIN"] = "neoori.tech"
    res = _start(client, "microsoft", base_url="https://neoori.tech")
    assert res.headers["Location"] == "https://cv.neoori.tech/api/auth/microsoft/start"


@pytest.mark.parametrize("role, home", [
    ("admin", "/admin"), ("counselor", "/conseiller"), ("candidate", "/voyage"),
])
def test_on_voyage_a_candidate_lands_on_the_hub(client, providers, make_user, role, home):
    make_user(email="marie@gmail.com", role=role)
    res = _sign_in(client, "google", base_url="https://voyage.localhost",
                   sub="g-1", email="marie@gmail.com", email_verified=True)
    assert res.headers["Location"] == home
```

- [ ] **Step 3: Run the OAuth tests to see what fails**

Run: `cd backend && $PY -m pytest tests/test_oauth_routes.py -q`
Expected: the new tests and the rewritten start test fail — `redirect_uri`
reads `https://neoori.tech/api/auth/google/callback` (the `APP_URL` default),
the root's `/start` goes straight to the provider instead of cv, and a
candidate on voyage lands on `/espace`. Every other test still passes, now on
cv.localhost.

- [ ] **Step 4: Route the sign-in by host**

In `backend/app/routes/auth_oauth.py`, replace `from ..utils import auth_links`
with `from ..utils import auth_links, site`.

In `start`, replace:

```python
    if provider not in PROVIDERS:
        abort(404)
    client = oauth_clients.client(provider)
    next_path = auth_links.safe_next(request.args.get("next"))
```

with:

```python
    if provider not in PROVIDERS:
        abort(404)
    # A sign-in ends on the host it started on: the callback is registered for
    # cv and voyage, and the state cookie stays on one host (subdomain split
    # spec, decision 28). Anywhere else — the root has no sign-in page — goes
    # to cv's /start, `next` kept, before any state is written.
    if site.request_app() not in ("cv", "voyage"):
        target = f"{site.origin('cv')}/api/auth/{provider}/start"
        if request.args.get("next") is not None:
            target += "?next=" + quote(request.args["next"], safe="")
        return redirect(target)
    client = oauth_clients.client(provider)
    next_path = auth_links.safe_next(request.args.get("next"))
```

In `callback`, replace:

```python
            landing = _landing(outcome.user, {"next": next_path}) or _home_path(outcome.user.role)
```

with:

```python
            landing = (
                _landing(outcome.user, {"next": next_path})
                or _home_path(outcome.user.role, site.request_app())
            )
```

Replace:

```python
def _redirect_uri(provider: str) -> str:
    """From APP_URL, never the request: behind nginx, Flask sees backend:5000."""
    return f"{current_app.config['APP_URL']}/api/auth/{provider}/callback"
```

with:

```python
def _redirect_uri(provider: str) -> str:
    """On the host the sign-in started on, rebuilt from DOMAIN — never the
    Host header itself (subdomain split spec, decision 28). Both callbacks
    are registered with each provider."""
    return f"{site.request_origin()}/api/auth/{provider}/callback"
```

Replace:

```python
def _home_path(role: str) -> str:
    """The role's home. frontend/src/lib/home.ts homeFor says the same:
    keep the two in step."""
    if role == "admin":
        return "/admin"
    if role == "counselor":
        return "/conseiller"
    return "/espace"
```

with:

```python
def _home_path(role: str, app: str | None = None) -> str:
    """The role's home on this host: a candidate's is the voyage hub on
    voyage and /espace anywhere else; a counselor's and an admin's are the
    same everywhere (subdomain split spec, decision 15).
    frontend/src/lib/home.ts homeFor says the same: keep the two in step."""
    if role == "admin":
        return "/admin"
    if role == "counselor":
        return "/conseiller"
    return "/voyage" if app == "voyage" else "/espace"
```

`current_app` is still used by the route's logging; leave the import alone.

- [ ] **Step 5: Run the OAuth tests**

Run: `cd backend && $PY -m pytest tests/test_oauth_routes.py -q`
Expected: all pass.

- [ ] **Step 6: Run the full suite**

Run: `cd backend && $PY -m pytest -q`
Expected: 1887 passed (1879 + 8).

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/auth_oauth.py backend/tests/test_oauth_routes.py
git commit -m "$(cat <<'EOF'
feat(oauth): the callback is on the host the sign-in started on; the root hands /start to cv

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Stripe, CORS, and the end of `APP_URL` / `FRONTEND_URL`

**Files:**
- Modify: `backend/app/routes/payments.py` (imports, lines 17–25; `_frontend_base`, lines 61–64; checkout, line 111)
- Modify: `backend/app/__init__.py` (CORS, lines 210–214; `_cors_error_response`, line 263)
- Modify: `backend/app/config.py` (remove `APP_URL`, lines 38–40; remove `FRONTEND_ORIGINS`, lines 59–63)
- Test: `backend/tests/test_one_domain_setting.py` (new)

**Interfaces:**
- Consumes: Task 1's `site.origin("cv")`, `site.origins(config)`.
- Produces: config keys `APP_URL` and `FRONTEND_ORIGINS` no longer exist.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_one_domain_setting.py`:

```python
"""DOMAIN is the one URL setting (subdomain split spec, decisions 19, 22
and 32): Stripe's return URLs and the CORS list are built from it, and
nothing reads the settings it replaced."""
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models.analysis import Analysis
from tests.helpers_doors import bearer, user

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_nothing_reads_the_retired_url_settings():
    readers = sorted(
        p.relative_to(APP_DIR).as_posix() for p in APP_DIR.rglob("*.py")
        if re.search(r"APP_URL|FRONTEND_URL|FRONTEND_ORIGINS", p.read_text(encoding="utf-8"))
    )
    assert readers == []


@patch("app.routes.payments._stripe")
def test_stripe_returns_to_cv_whichever_host_paid(stripe_factory, client, app):
    app.config["DOMAIN"] = "neoori.tech"
    stripe = MagicMock()
    stripe.checkout.Session.create.return_value = MagicMock(url="https://stripe.test/s")
    stripe_factory.return_value = stripe
    owner = user()
    analysis = Analysis(user_id=owner.id, door="account", inputs={"_path": "1", "_tier": "free"},
                        status="success", output={"1": {}})
    db.session.add(analysis)
    db.session.commit()
    res = client.post("/api/payments/checkout", json={"analysis_id": analysis.id, "tier": "paid"},
                      headers=bearer(owner), base_url="https://voyage.neoori.tech")
    assert res.status_code == 200
    kwargs = stripe.checkout.Session.create.call_args.kwargs
    assert kwargs["success_url"] == (
        f"https://cv.neoori.tech/analyse/{analysis.id}/debloquer?session_id={{CHECKOUT_SESSION_ID}}"
    )
    assert kwargs["cancel_url"] == f"https://cv.neoori.tech/analyse/{analysis.id}/debloquer?canceled=1"


def test_cors_answers_the_three_origins_only(client):
    for origin in ("https://localhost", "https://cv.localhost", "https://voyage.localhost"):
        res = client.get("/api/health", headers={"Origin": origin})
        assert res.headers.get("Access-Control-Allow-Origin") == origin
    for origin in ("https://attacker.example", "http://localhost:3000", "https://www.localhost"):
        res = client.get("/api/health", headers={"Origin": origin})
        assert "Access-Control-Allow-Origin" not in res.headers


def test_an_auth_refusal_answers_cors_for_the_three_origins_only(client):
    res = client.get("/api/auth/me", headers={"Origin": "https://voyage.localhost"})
    assert res.status_code == 401
    assert res.headers.get("Access-Control-Allow-Origin") == "https://voyage.localhost"
    res = client.get("/api/auth/me", headers={"Origin": "https://attacker.example"})
    assert res.status_code == 401
    assert "Access-Control-Allow-Origin" not in res.headers
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && $PY -m pytest tests/test_one_domain_setting.py -q`
Expected: FAIL — `readers == ['__init__.py', 'config.py', 'routes/payments.py']`;
`success_url` starts with `http://localhost:3000`; CORS answers
`http://localhost:3000` and refuses `https://cv.localhost`.

- [ ] **Step 3: Return Stripe to cv**

In `backend/app/routes/payments.py`, after
`from ..services.unlock_service import unlock_analysis`, add
`from ..utils import site`. Delete:

```python
def _frontend_base() -> str:
    # FRONTEND_URL may be a comma-separated list (CORS config) — take the first
    raw = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return raw.split(",")[0].strip().rstrip("/")


```

and replace `    base = _frontend_base()` with:

```python
    # The unlock page is cv's, whichever host the payment started on
    # (subdomain split spec, decision 32).
    base = site.origin("cv")
```

(`os` stays imported: the Stripe keys and prices still read it.)

- [ ] **Step 4: Build CORS from the three origins**

In `backend/app/__init__.py`, replace:

```python
    cors.init_app(
        app,
        resources={r"/api/.*": {"origins": app.config["FRONTEND_ORIGINS"]}},
        supports_credentials=True,  # required for httpOnly cookie auth
    )
```

with:

```python
    cors.init_app(
        app,
        # The three origins (subdomain split spec, decision 32). Browser calls
        # stay same-origin — each host serves its own /api — so this list is
        # a backstop.
        resources={r"/api/.*": {"origins": site.origins(app.config)}},
        supports_credentials=True,  # required for httpOnly cookie auth
    )
```

and, in `_cors_error_response`, replace
`        if origin in app.config["FRONTEND_ORIGINS"]:` with
`        if origin in site.origins(app.config):`.

- [ ] **Step 5: Remove the retired settings from `config.py`**

In `backend/app/config.py`, delete:

```python
    # Public origin every account mail links to (verification, reset,
    # conseiller). The dev compose file points it at http://localhost:8080.
    APP_URL = os.environ.get("APP_URL", "https://neoori.tech").rstrip("/")
```

and:

```python
    FRONTEND_ORIGINS = [
        o.strip()
        for o in os.environ.get("FRONTEND_URL", "http://localhost:3000,http://localhost:3001").split(",")
        if o.strip()
    ]
```

- [ ] **Step 6: Run the tests**

Run: `cd backend && $PY -m pytest tests/test_one_domain_setting.py tests/test_checkout_owner.py -q`
Expected: all pass.

Run: `cd backend && $PY -m pytest -q`
Expected: 1891 passed (1887 + 4).

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/payments.py backend/app/__init__.py backend/app/config.py backend/tests/test_one_domain_setting.py
git commit -m "$(cat <<'EOF'
feat(site): Stripe returns to cv, CORS lists the three origins; APP_URL and FRONTEND_URL retired

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: nginx, compose, env examples, dev origins

**Files:**
- Modify: `nginx/templates-https/default.conf.template` (header, lines 1–2; log format, lines 48–52; new servers before line 56; port-80 `server_name`, line 58; app `server_name`, line 90)
- Modify: `nginx/templates-http/default.conf.template` (log format, lines 50–54; catch-all comment, line 59)
- Modify: `nginx/dev.conf` (header, lines 1–2; log format, lines 53–57)
- Modify: `docker-compose.yml` (header, lines 1–9; backend environment, lines 35–39; frontend environment, lines 54–57)
- Modify: `docker-compose.prod.yml` (frontend service, lines 48–52)
- Modify: `.env.example` (lines 35–38, 61–65), `backend/.env.example` (lines 11–12, 25)
- Modify: `frontend/next.config.ts`

**Interfaces:**
- Consumes: the backend now reads `DOMAIN`, `PUBLIC_SCHEME`, `PUBLIC_PORT` (Tasks 1–5).
- Produces: in dev, both containers get `DOMAIN=neoori.localhost`,
  `PUBLIC_SCHEME=http`, `PUBLIC_PORT=8080`; in prod the frontend gets
  `DOMAIN` from `/srv/neoori/.env` (the backend already loads that file).
  The access-log line carries the host.

- [ ] **Step 1: The https template**

In `nginx/templates-https/default.conf.template`, replace the first two lines:

```
# Phase 2 (NGINX_MODE=https): TLS termination once the ${DOMAIN} certificate
# has been issued (see DOCKER.md). HTTP only answers ACME + redirects.
```

with:

```
# Phase 2 (NGINX_MODE=https): TLS termination once the ${DOMAIN} certificate
# has been issued (see DOCKER.md). HTTP only answers ACME + redirects.
# Four names reach a server block (subdomain split spec, decision 33):
# ${DOMAIN}, cv.${DOMAIN} and voyage.${DOMAIN}, proxied alike (the app routes
# by host), and www.${DOMAIN}, which redirects to the apex. Every other name
# is turned away by the two default servers below.
```

Replace the log format block (same text in all three nginx files):

```
# Four-doors spec, decision 42: log the path, never the query string or the
# Referer. Verification and reset tokens, `next` paths and Stripe session ids
# travel in query strings, and the Referer repeats them.
log_format neoori_paths '$remote_addr [$time_local] "$request_method $uri" '
                        '$status $body_bytes_sent $request_time';
```

with:

```
# Four-doors spec, decision 42: log the path, never the query string or the
# Referer. Verification and reset tokens, `next` paths and Stripe session ids
# travel in query strings, and the Referer repeats them. The host goes in
# (subdomain split spec, decision 38): requests per host are counted from it.
log_format neoori_paths '$remote_addr [$time_local] $host "$request_method $uri" '
                        '$status $body_bytes_sent $request_time';
```

Replace:

```
limit_req_status 429;

server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
```

with:

```
limit_req_status 429;

# Any name not listed below (subdomain split spec, decision 33). On 80 the
# connection is closed (444) — except the ACME challenge, answered for any
# name, so a certificate for a new domain can be issued before DOMAIN changes
# (DOCKER.md, « Swapping the domain later »); it serves only what certbot
# itself wrote. On 443 the TLS handshake is refused, which needs no
# certificate.
server {
    listen 80 default_server;
    server_name _;
    access_log /var/log/nginx/access.log neoori_paths;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 444;
    }
}

server {
    listen 443 ssl default_server;
    server_name _;
    ssl_reject_handshake on;
}

server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN} cv.${DOMAIN} voyage.${DOMAIN};
```

In the app block, replace:

```
    http2 on;
    server_name ${DOMAIN};
```

with:

```
    http2 on;
    # The landing and both apps: one Next.js app and one Flask behind them,
    # which decide per host (subdomain split spec, decisions 8 and 33).
    server_name ${DOMAIN} cv.${DOMAIN} voyage.${DOMAIN};
```

- [ ] **Step 2: The http template and the dev config**

In `nginx/templates-http/default.conf.template`, replace the log format block
exactly as in Step 1, then replace:

```
server {
    listen 80 default_server;
    server_name ${DOMAIN};
```

with:

```
server {
    # A catch-all on purpose (subdomain split spec, decision 34): this phase
    # serves IP smoke tests. The app routes by host itself and treats a name
    # it does not know as the root.
    listen 80 default_server;
    server_name ${DOMAIN};
```

In `nginx/dev.conf`, replace the first two lines:

```
# Dev proxy: mirrors production routing on http://localhost.
# / -> Next.js dev server (3001, websocket for HMR), /api -> Flask (5001).
```

with:

```
# Dev proxy: mirrors production routing on http://neoori.localhost:8080 (the
# landing), http://cv.neoori.localhost:8080 and
# http://voyage.neoori.localhost:8080 — Chrome resolves *.localhost to the
# loopback by itself. Any other name, plain localhost:8080 included, is served
# too: the app treats it as the root (subdomain split spec, decision 34).
# / -> Next.js dev server (3001, websocket for HMR), /api -> Flask (5001).
```

and replace its log format block exactly as in Step 1.

- [ ] **Step 3: Check the https template in a throwaway nginx**

One command block: a self-signed certificate for the throwaway, `nginx -t`,
then the template answering each kind of name.

```bash
T=$(mktemp -d) && mkdir -p "$T/live/neoori.tech"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=neoori.tech \
  -keyout "$T/live/neoori.tech/privkey.pem" -out "$T/live/neoori.tech/fullchain.pem" 2>/dev/null
docker run --rm -e DOMAIN=neoori.tech --add-host backend:127.0.0.1 --add-host frontend:127.0.0.1 \
  -v "$PWD/nginx/templates-https:/etc/nginx/templates:ro" -v "$T:/etc/letsencrypt:ro" \
  nginx:1.29-alpine nginx -t 2>&1 | tail -2
docker run -d --name nginx-split -e DOMAIN=neoori.tech \
  --add-host backend:127.0.0.1 --add-host frontend:127.0.0.1 \
  -p 127.0.0.1:18080:80 -p 127.0.0.1:18443:443 \
  -v "$PWD/nginx/templates-https:/etc/nginx/templates:ro" -v "$T:/etc/letsencrypt:ro" nginx:1.29-alpine
sleep 2
for h in neoori.tech cv.neoori.tech voyage.neoori.tech www.neoori.tech evil.example; do
  printf '%-20s 80:%s ' "$h" "$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $h" http://127.0.0.1:18080/x)"
  printf '443:%s\n' "$(curl -sk -o /dev/null -w '%{http_code}' --resolve "$h:18443:127.0.0.1" "https://$h:18443/")"
done
printf 'evil.example ACME: %s\n' "$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: evil.example' http://127.0.0.1:18080/.well-known/acme-challenge/x)"
docker logs nginx-split 2>/dev/null | grep -E '"GET' | tail -2
docker rm -f nginx-split && rm -rf "$T"
```

Expected:

```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
neoori.tech          80:301 443:502
cv.neoori.tech       80:301 443:502
voyage.neoori.tech   80:301 443:502
www.neoori.tech      80:301 443:301
evil.example         80:000 443:000
evil.example ACME: 404
```

(502: the app block answered and found no upstream, as intended in this
throwaway. 000 on 80: the connection was closed, 444. 000 on 443: the
handshake was refused. 404 for the challenge: the default server answered it
from the empty webroot instead of closing the connection.) The two log lines
show the host right after the time, e.g. `[...] evil.example "GET /.well-known/acme-challenge/x" 404 ...`.

- [ ] **Step 4: Compose files**

In `docker-compose.yml`, replace the header lines 1–9:

```yaml
# Local development stack: MySQL + Flask (hot reload) + Next.js (hot reload)
# behind nginx on http://localhost:8080 (port 80 is taken by the TaifOr dev
# stack on this machine). Source is bind-mounted; images only need a rebuild
# when requirements.txt / package-lock.json change.
#
#   docker compose up -d
#   open http://localhost:8080     (nginx: / -> frontend, /api -> backend)
#
# Direct access (matches the old non-docker ports): frontend :3001, backend :5001.
```

with:

```yaml
# Local development stack: MySQL + Flask (hot reload) + Next.js (hot reload)
# behind nginx on port 8080 (port 80 is taken by the TaifOr dev stack on this
# machine). Source is bind-mounted; images only need a rebuild when
# requirements.txt / package-lock.json change.
#
#   docker compose up -d
#   open http://neoori.localhost:8080           the landing
#        http://cv.neoori.localhost:8080        « J'ai une cible »
#        http://voyage.neoori.localhost:8080    le voyage
#   (nginx: / -> frontend, /api -> backend). Chrome resolves *.localhost to
#   the loopback by itself; Safari does not. Plain localhost:8080 shows the
#   landing too, and its links lead to the three names above.
#
# Direct access (matches the old non-docker ports): frontend :3001, backend :5001.
```

In the `backend` service, replace:

```yaml
      FRONTEND_URL: http://localhost:8080,http://localhost:3001
      APP_URL: http://localhost:8080
```

with:

```yaml
      # The one setting and the two dev-only ones (subdomain split spec,
      # decisions 19–20). The frontend gets the same three.
      DOMAIN: neoori.localhost
      PUBLIC_SCHEME: http
      PUBLIC_PORT: "8080"
```

In the `frontend` service, replace:

```yaml
      BACKEND_URL: http://backend:5001
```

with:

```yaml
      BACKEND_URL: http://backend:5001
      # Same three as the backend: the proxy routes by host with them.
      DOMAIN: neoori.localhost
      PUBLIC_SCHEME: http
      PUBLIC_PORT: "8080"
```

In `docker-compose.prod.yml`, replace:

```yaml
  frontend:
    image: ghcr.io/alltoft/neoori-frontend:${IMAGE_TAG:-latest}
    restart: unless-stopped
    depends_on:
```

with:

```yaml
  frontend:
    image: ghcr.io/alltoft/neoori-frontend:${IMAGE_TAG:-latest}
    restart: unless-stopped
    # Read per request (subdomain split spec, decision 21): a domain change is
    # an .env edit and a recreate, never a rebuild.
    environment:
      DOMAIN: ${DOMAIN}
    depends_on:
```

Check both render:

```bash
docker compose config | grep -E 'DOMAIN|PUBLIC_|APP_URL|FRONTEND_URL'
# The prod file reads an .env beside it; an empty one is enough to render it
# (gitignored, removed right after).
if [ ! -e .env ]; then touch .env; made=1; fi
DOMAIN=neoori.tech docker compose -f docker-compose.prod.yml config | grep -B2 -A2 'DOMAIN: neoori.tech'
[ -n "$made" ] && rm .env
```

Expected: the dev config shows `DOMAIN: neoori.localhost`, `PUBLIC_SCHEME: http`
and `PUBLIC_PORT: "8080"` twice each, and no `APP_URL`. A `FRONTEND_URL` line
may still show under the backend: it comes from the developer's local
`backend/.env`, and nothing reads it any more. The prod config shows
`DOMAIN: neoori.tech` under both `frontend` and `nginx`.

- [ ] **Step 5: Env examples**

In `.env.example`, replace:

```
# Sender shown to recipients. The domain must be verified in Resend.
MAIL_FROM=neoori <bonjour@neoori.tech>
# Public origin the account mails link to (verification, reset, conseiller).
APP_URL=https://app.example.fr
```

with:

```
# Sender shown to recipients. The domain must be verified in Resend.
# Deliberately not derived from DOMAIN: Resend refuses a sender on an
# unverified domain and mails fail silently by design, so a domain swap would
# stop every mail. Swap order: DOCKER.md, « Swapping the domain later ».
MAIL_FROM=neoori <bonjour@neoori.tech>
```

and replace:

```
# ---- URLs / TLS ----
# Public origin of the app (used for CORS allow-list + Stripe return URLs).
FRONTEND_URL=https://app.example.fr
# Bare domain for nginx server_name + Let's Encrypt paths.
DOMAIN=app.example.fr
```

with:

```
# ---- Domain / TLS ----
# The one place the domain is written (subdomain split spec, decision 19):
# nginx, the backend and the frontend read it when their containers start.
# The app answers on DOMAIN (the landing), cv.DOMAIN and voyage.DOMAIN; the
# certificate covers those three and www (DOCKER.md, « TLS »). Every mail
# link, the Google/Microsoft callbacks and Stripe's return URLs are built
# from it. PUBLIC_SCHEME and PUBLIC_PORT exist for the local stack only:
# never set them here.
DOMAIN=app.example.fr
```

In `backend/.env.example`, replace:

```
MAIL_FROM=neoori <bonjour@neoori.tech>
APP_URL=http://localhost:8080
```

with:

```
MAIL_FROM=neoori <bonjour@neoori.tech>
# DOMAIN, PUBLIC_SCHEME and PUBLIC_PORT (subdomain split spec):
# docker-compose.yml sets them for the local stack (neoori.localhost, http,
# 8080). Only needed here when Flask runs outside it.
```

and delete the line `FRONTEND_URL=http://localhost:3001`.

- [ ] **Step 6: Dev origins for the Next dev server**

In `frontend/next.config.ts`, replace:

```ts
  output: "standalone",
  skipTrailingSlashRedirect: true,
```

with:

```ts
  output: "standalone",
  skipTrailingSlashRedirect: true,
  // Dev only. Next refuses its dev resources (the hot-reload socket) to an
  // origin it does not know, and its default `*.localhost` matches one label:
  // neoori.localhost, not cv.neoori.localhost (subdomain split spec,
  // « Frontend »). The dev compose file sets DOMAIN; a production build
  // ignores this key.
  allowedDevOrigins: process.env.DOMAIN ? [`*.${process.env.DOMAIN}`] : [],
```

Run: `cd frontend && npx tsc --noEmit` → no output.

- [ ] **Step 7: Commit**

```bash
git add nginx docker-compose.yml docker-compose.prod.yml .env.example backend/.env.example frontend/next.config.ts
git commit -m "$(cat <<'EOF'
feat(infra): nginx answers the root, cv. and voyage. and refuses other names; DOMAIN reaches both containers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Host routing in the proxy

**Files:**
- Create: `frontend/src/lib/site.ts`
- Create: `frontend/src/lib/sign-in-gate.ts`
- Create: `frontend/src/lib/site.test.ts`
- Modify: `frontend/src/proxy.ts` (whole file)
- Modify: `frontend/package.json` (`scripts`), `frontend/tsconfig.json` (`compilerOptions`)

**Interfaces:**
- Consumes: cookie name `neoori_access` (Task 2); `DOMAIN` / `PUBLIC_*` in the frontend container (Task 6).
- Produces (`@/lib/site`):
  - `type AppName = "root" | "cv" | "voyage"`, `type Owner = AppName | "shared"`
  - `interface SiteSettings { domain: string; scheme: string; port: string }`
  - `interface Site { settings: SiteSettings; app: AppName }`
  - `type Route = { kind: "serve" } | { kind: "redirect"; location: string }`
  - `settingsFromEnv(env: { DOMAIN?: string; PUBLIC_SCHEME?: string; PUBLIC_PORT?: string }): SiteSettings`
  - `origin(app: AppName, settings: SiteSettings): string`
  - `appOfHost(host: string | null | undefined, domain: string): AppName`
  - `ownerOf(path: string): Owner`
  - `passesThrough(pathname: string): boolean`
  - `route(host: string | null | undefined, pathname: string, search: string, settings: SiteSettings): Route`
  - `resolveHref(path: string, site: Site): string`
- Produces (`@/lib/sign-in-gate`): `SESSION_COOKIE = "neoori_access"`,
  `signInRedirect(pathname: string, search: string, signedIn: boolean): string | null`.

- [ ] **Step 1: Wire up the test runner**

In `frontend/package.json`, replace:

```json
    "lint": "eslint"
```

with:

```json
    "lint": "eslint",
    "test": "node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --test src/lib/*.test.ts"
```

In `frontend/tsconfig.json`, replace `    "noEmit": true,` with:

```json
    "noEmit": true,
    "allowImportingTsExtensions": true,
```

(The tests import `./site.ts`: Node needs the extension, and TypeScript allows
it only with this flag. `noEmit` is already on, which the flag requires. The
`--disable-warning` silences Node's note that `package.json` names no module
type; adding `"type": "module"` instead would change how Next loads its
configs.)

- [ ] **Step 2: Write the failing tests**

Create `frontend/src/lib/site.test.ts`:

```ts
import { test } from "node:test"
import assert from "node:assert/strict"
import {
  appOfHost, origin, ownerOf, passesThrough, resolveHref, route, settingsFromEnv,
  type AppName, type Site, type SiteSettings,
} from "./site.ts"
import { signInRedirect } from "./sign-in-gate.ts"

const PROD: SiteSettings = { domain: "neoori.tech", scheme: "https", port: "" }
const DEV: SiteSettings = { domain: "neoori.localhost", scheme: "http", port: "8080" }
const serve = { kind: "serve" }
const to = (location: string) => ({ kind: "redirect", location })
const on = (app: AppName): Site => ({ settings: PROD, app })

test("the settings come from DOMAIN, PUBLIC_SCHEME and PUBLIC_PORT", () => {
  assert.deepEqual(settingsFromEnv({ DOMAIN: "neoori.tech" }), PROD)
  assert.deepEqual(
    settingsFromEnv({ DOMAIN: " Neoori.Localhost. ", PUBLIC_SCHEME: "http", PUBLIC_PORT: "8080" }),
    DEV,
  )
  assert.deepEqual(settingsFromEnv({}), { domain: "localhost", scheme: "https", port: "" })
})

test("the three origins", () => {
  assert.equal(origin("root", PROD), "https://neoori.tech")
  assert.equal(origin("cv", PROD), "https://cv.neoori.tech")
  assert.equal(origin("voyage", DEV), "http://voyage.neoori.localhost:8080")
})

test("which app a host is; any other name is the root", () => {
  // Review Focus 1.
  const cases: [string | null, AppName][] = [
    ["neoori.tech", "root"], ["cv.neoori.tech", "cv"], ["voyage.neoori.tech", "voyage"],
    ["CV.Neoori.Tech:443", "cv"], ["voyage.neoori.tech.", "voyage"],
    ["www.neoori.tech", "root"], ["127.0.0.1:3000", "root"], ["localhost:8080", "root"],
    ["cv.neoori.tech.evil.example", "root"], ["[::1]:3000", "root"], [null, "root"],
  ]
  for (const [host, app] of cases) assert.equal(appOfHost(host, "neoori.tech"), app, String(host))
})

test("owners match on segment boundaries; a path in no row is shared", () => {
  const cases: [string, string][] = [
    ["/", "root"], ["/?x=1", "root"], ["/#rapport", "root"],
    ["/analyse", "cv"], ["/analyse/nouveau?reprendre=compte", "cv"], ["/analyse/abc/rapport", "cv"],
    ["/rapport", "cv"], ["/espace", "cv"], ["/espace?garder=1", "cv"],
    ["/voyage", "voyage"], ["/voyage/session/2", "voyage"], ["/voyage/c/tok", "voyage"],
    ["/voyageur", "shared"], ["/analyses", "shared"], ["/espaces", "shared"],
    ["/connexion", "shared"], ["/profil", "shared"], ["/conseiller/analyses/1", "shared"],
    ["/admin", "shared"], ["/cgv", "shared"], ["/c/tok", "shared"], ["/nimporte", "shared"],
  ]
  for (const [path, owner] of cases) assert.equal(ownerOf(path), owner, path)
})

test("files, Next's own paths and the API pass through", () => {
  for (const path of [
    "/icon.svg", "/img/og-cover.png", "/robots.txt", "/brand/logo.webp",
    "/_next/static/x.js", "/_next/webpack-hmr", "/__nextjs_original-stack-frame",
    "/api", "/api/auth/me",
  ]) assert.equal(passesThrough(path), true, path)
  for (const path of ["/", "/voyage", "/analyse/nouveau", "/apiary"]) {
    assert.equal(passesThrough(path), false, path)
  }
})

test("the root serves the landing and sends everything else to its owner", () => {
  const r = (path: string, search = "") => route("neoori.tech", path, search, PROD)
  assert.deepEqual(r("/"), serve)
  assert.deepEqual(r("/espace"), to("https://cv.neoori.tech/espace"))
  assert.deepEqual(r("/voyage/session/2", "?x=1"), to("https://voyage.neoori.tech/voyage/session/2?x=1"))
  assert.deepEqual(r("/rapport"), to("https://cv.neoori.tech/rapport"))
  assert.deepEqual(r("/connexion"), to("https://cv.neoori.tech/connexion"))
  assert.deepEqual(r("/nimporte"), to("https://cv.neoori.tech/nimporte"))
  assert.deepEqual(r("/icon.svg"), serve)
})

test("an old link keeps its encoded query byte for byte", () => {
  // Review Focus 2.
  const search = "?token=a.b-c_d%2Fe%3D&next=%2Fvoyage%3Fx%3D1"
  assert.deepEqual(
    route("neoori.tech", "/verifier-email", search, PROD),
    to(`https://cv.neoori.tech/verifier-email${search}`),
  )
})

test("cv serves its own and the shared paths, and hands the voyage over", () => {
  const r = (path: string, search = "") => route("cv.neoori.tech", path, search, PROD)
  assert.deepEqual(r("/"), to("/analyse/nouveau"))
  assert.deepEqual(r("/analyse/nouveau"), serve)
  assert.deepEqual(r("/espace"), serve)
  assert.deepEqual(r("/connexion", "?redirect=%2Fvoyage"), serve)
  assert.deepEqual(r("/voyage"), to("https://voyage.neoori.tech/voyage"))
  assert.deepEqual(r("/voyage/etape/parcours", "?a=b"), to("https://voyage.neoori.tech/voyage/etape/parcours?a=b"))
})

test("voyage serves its own and the shared paths, and hands cv's over", () => {
  const r = (path: string, search = "") => route("voyage.neoori.tech", path, search, PROD)
  assert.deepEqual(r("/"), to("/voyage"))
  assert.deepEqual(r("/voyage"), serve)
  assert.deepEqual(r("/profil"), serve)
  assert.deepEqual(r("/espace", "?garder=1"), to("https://cv.neoori.tech/espace?garder=1"))
  assert.deepEqual(r("/analyse/abc/rapport"), to("https://cv.neoori.tech/analyse/abc/rapport"))
})

test("an unknown host is the root, and dev origins carry the scheme and the port", () => {
  assert.deepEqual(route("127.0.0.1:3000", "/", "", PROD), serve)
  assert.deepEqual(route("localhost:8080", "/espace", "", DEV), to("http://cv.neoori.localhost:8080/espace"))
})

test("a link stays relative on the host that serves it, absolute otherwise", () => {
  assert.equal(resolveHref("/espace", on("cv")), "/espace")
  assert.equal(resolveHref("/voyage", on("cv")), "https://voyage.neoori.tech/voyage")
  assert.equal(resolveHref("/espace", on("voyage")), "https://cv.neoori.tech/espace")
  // Review Focus 3: a destination keeps its query when it changes host.
  assert.equal(resolveHref("/espace?garder=1", on("voyage")), "https://cv.neoori.tech/espace?garder=1")
  assert.equal(resolveHref("/profil", on("voyage")), "/profil")
  assert.equal(resolveHref("/#rapport", on("root")), "/#rapport")
  assert.equal(resolveHref("/#rapport", on("cv")), "https://neoori.tech/#rapport")
  assert.equal(resolveHref("/", on("voyage")), "https://neoori.tech/")
  assert.equal(resolveHref("/inscription-conseiller", on("root")), "https://cv.neoori.tech/inscription-conseiller")
  assert.equal(resolveHref("/analyse", on("root")), "https://cv.neoori.tech/analyse")
  assert.equal(resolveHref("mailto:a@b.fr", on("root")), "mailto:a@b.fr")
  assert.equal(resolveHref("https://stripe.test/s", on("cv")), "https://stripe.test/s")
})

test("the sign-in gate: four doors' open paths, signup first on the report and the voyage hub", () => {
  assert.equal(signInRedirect("/analyse/nouveau", "", false), null)
  assert.equal(signInRedirect("/analyse/envoyee", "", false), null)
  assert.equal(signInRedirect("/rapport", "", false), null)
  assert.equal(signInRedirect("/connexion", "", false), null)
  assert.equal(signInRedirect("/analyse/abc/rapport", "", false), "/inscription?redirect=%2Fanalyse%2Fabc%2Frapport")
  assert.equal(signInRedirect("/voyage", "", false), "/inscription?redirect=%2Fvoyage")
  assert.equal(signInRedirect("/voyage/session/2", "", false), "/connexion?redirect=%2Fvoyage%2Fsession%2F2")
  assert.equal(signInRedirect("/espace", "?garder=1", false), "/connexion?redirect=%2Fespace%3Fgarder%3D1")
  assert.equal(signInRedirect("/espace", "", true), null)
  assert.equal(signInRedirect("/voyage", "", true), null)
})
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd frontend && npm test`
Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `./site.ts`.

- [ ] **Step 4: Create `frontend/src/lib/site.ts`**

```ts
/**
 * Which host serves which page (subdomain split spec, decisions 10–18 and 37).
 *
 * neoori answers on three hosts built from one setting, DOMAIN: the root
 * (today's landing, nothing else), cv.DOMAIN (« J'ai une cible ») and
 * voyage.DOMAIN (le voyage). Plain functions with no Next.js import, so
 * `node --test` loads this file as it is (site.test.ts).
 *
 * A new page that belongs to one app needs a row in OWNERS. A path in no row
 * is shared: served on cv and on voyage, and sent from the root to cv.
 */

export type AppName = "root" | "cv" | "voyage"
export type Owner = AppName | "shared"

/** DOMAIN and the two dev-only settings, read at runtime (decisions 19–21). */
export interface SiteSettings {
  domain: string
  scheme: string
  port: string
}

/** What the root layout hands to client components: the settings, and the
 *  app this request's host is. */
export interface Site {
  settings: SiteSettings
  app: AppName
}

export type Route = { kind: "serve" } | { kind: "redirect"; location: string }

const PREFIX: Record<AppName, string> = { root: "", cv: "cv.", voyage: "voyage." }

/** Matched on a segment boundary: /voyage and /voyage/…, never /voyageur. */
const OWNERS: ReadonlyArray<readonly [string, "cv" | "voyage"]> = [
  ["/analyse", "cv"],
  ["/rapport", "cv"],
  ["/espace", "cv"],
  ["/voyage", "voyage"],
]

/** Each subdomain's "/" until its landing is designed (decision 13). A
 *  designed landing will take over its "/" through an internal rewrite. */
const DAY_ONE: Record<"cv" | "voyage", string> = {
  cv: "/analyse/nouveau",
  voyage: "/voyage",
}

export function settingsFromEnv(env: {
  DOMAIN?: string
  PUBLIC_SCHEME?: string
  PUBLIC_PORT?: string
}): SiteSettings {
  return {
    domain: (env.DOMAIN ?? "").trim().toLowerCase().replace(/\.$/, "") || "localhost",
    scheme: (env.PUBLIC_SCHEME ?? "").trim() || "https",
    port: (env.PUBLIC_PORT ?? "").trim(),
  }
}

export function origin(app: AppName, settings: SiteSettings): string {
  const port = settings.port ? `:${settings.port}` : ""
  return `${settings.scheme}://${PREFIX[app]}${settings.domain}${port}`
}

/** The app a Host header names. Case, the port and a trailing dot are
 *  ignored; any other name — www, an IP, the container's health check — is
 *  treated as the root (decision 18). */
export function appOfHost(host: string | null | undefined, domain: string): AppName {
  const name = (host ?? "").trim().toLowerCase().split(":")[0].replace(/\.$/, "")
  if (name === `cv.${domain}`) return "cv"
  if (name === `voyage.${domain}`) return "voyage"
  return "root"
}

/** Which app owns a path; "/" alone is the root's landing. Query and
 *  fragment are ignored. */
export function ownerOf(path: string): Owner {
  const pathname = path.split(/[?#]/, 1)[0] || "/"
  if (pathname === "/") return "root"
  for (const [prefix, app] of OWNERS) {
    if (pathname === prefix || pathname.startsWith(`${prefix}/`)) return app
  }
  return "shared"
}

/** Served on every host, never redirected (decision 17): files (a last
 *  segment with a dot), Next's own paths and the API. */
export function passesThrough(pathname: string): boolean {
  if (pathname.startsWith("/_next/") || pathname.startsWith("/__nextjs")) return true
  if (pathname === "/api" || pathname.startsWith("/api/")) return true
  return pathname.slice(pathname.lastIndexOf("/") + 1).includes(".")
}

/** The app that serves a page owned by `owner`, asked for on `app`. */
function servedBy(owner: Owner, app: AppName): AppName {
  if (owner === "shared") return app === "root" ? "cv" : app
  return owner
}

/**
 * What a page request gets (spec, « How a page request is routed »). A
 * redirect to another host is absolute and built from the settings, never
 * from the Host header; the day-one redirect stays on its host and is
 * relative.
 */
export function route(
  host: string | null | undefined,
  pathname: string,
  search: string,
  settings: SiteSettings,
): Route {
  if (passesThrough(pathname)) return { kind: "serve" }
  const app = appOfHost(host, settings.domain)
  const owner = ownerOf(pathname)
  if (owner === "root") {
    return app === "root" ? { kind: "serve" } : { kind: "redirect", location: DAY_ONE[app] }
  }
  const target = servedBy(owner, app)
  if (target === app) return { kind: "serve" }
  return { kind: "redirect", location: origin(target, settings) + pathname + search }
}

/**
 * A link target for a page served on `site`: the path itself when this host
 * serves it, the serving host's absolute URL otherwise. "/" and "/#…" are the
 * root landing (decision 16). Anything that is not a site path — mailto:, an
 * absolute URL — comes back as given.
 */
export function resolveHref(path: string, site: Site): string {
  if (!path.startsWith("/") || path.startsWith("//")) return path
  const target = servedBy(ownerOf(path), site.app)
  return target === site.app ? path : origin(target, site.settings) + path
}
```

- [ ] **Step 5: Create `frontend/src/lib/sign-in-gate.ts`**

```ts
/**
 * The proxy's sign-in gate, as a pure function (moved out of proxy.ts by the
 * subdomain split so `node --test` can load it). Presence only: the
 * signature and the role are enforced server-side.
 */

/** The session cookie: backend/app/config.py JWT_ACCESS_COOKIE_NAME. Keep
 *  the two in step. */
export const SESSION_COOKIE = "neoori_access"

/** Routes that need an account. Gated at the edge so no page ever renders a
 *  screen the visitor cannot use without a session. Inside /analyse only the
 *  exact paths in PUBLIC are open. */
const PROTECTED = ["/admin", "/conseiller", "/profil", "/voyage", "/espace", "/analyse"]

/** Where a signed-out visitor on these lands instead of /connexion. A report,
 *  its waiting page and its unlock page are where new people arrive from a
 *  link or a mail, so they open on signup — and the redirect survives the
 *  confirmation email, because it travels inside the link. */
const SIGNUP_FIRST = ["/analyse"]

/** The voyage hub, exact: voyage.DOMAIN/ lands there, so new people arrive on
 *  it, as they did on the analysis form before four doors (subdomain split
 *  spec, decision 14). Deeper voyage pages keep /connexion. */
const SIGNUP_FIRST_EXACT = ["/voyage"]

/** Open to signed-out visitors inside /analyse (four-doors spec, ruling 1):
 *  the form, the advisor-door confirmation, and /analyse itself (a redirect
 *  to the form). Exact paths: /analyse/<id>/* stays the owner's. */
const PUBLIC = ["/analyse", "/analyse/nouveau", "/analyse/envoyee"]

/** Where to send a request, or null to let it through. `redirect` carries
 *  pathname + search exactly as requested, never decoded or rebuilt: the
 *  value is only ever used as a navigation target, and the pages that read it
 *  back check it as given. */
export function signInRedirect(pathname: string, search: string, signedIn: boolean): string | null {
  if (signedIn || PUBLIC.includes(pathname)) return null
  if (!PROTECTED.some((p) => pathname.startsWith(p))) return null
  const signupFirst =
    SIGNUP_FIRST.some((p) => pathname.startsWith(p)) || SIGNUP_FIRST_EXACT.includes(pathname)
  const query = new URLSearchParams({ redirect: pathname + search })
  return `${signupFirst ? "/inscription" : "/connexion"}?${query}`
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npm test`
Expected: `ℹ tests 12`, `ℹ pass 12`, `ℹ fail 0`.

- [ ] **Step 7: Rewrite `frontend/src/proxy.ts`**

Replace the whole file with:

```ts
import { NextRequest, NextResponse } from "next/server"
import { SESSION_COOKIE, signInRedirect } from "@/lib/sign-in-gate"
import { route, settingsFromEnv } from "@/lib/site"

export function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl

  // Which host serves the path comes first (subdomain split spec, decision
  // 37). DOMAIN is read per request from the container's environment, so a
  // domain change needs no rebuild (decision 21).
  const routed = route(req.headers.get("host"), pathname, search, settingsFromEnv(process.env))
  if (routed.kind === "redirect") {
    // 307, never 308: browsers keep a permanent redirect for ever, and the
    // root's role is provisional (decision 12). A same-host target goes out
    // as a relative Location.
    return NextResponse.redirect(new URL(routed.location, req.url), 307)
  }

  const to = signInRedirect(pathname, search, req.cookies.has(SESSION_COOKIE))
  if (to) return NextResponse.redirect(new URL(to, req.url))

  return NextResponse.next()
}

// Next 16 reads `config`, not `proxyConfig` — under the old name this matcher
// was ignored, so the proxy ran on every request including static assets.
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.png$).*)"],
}
```

- [ ] **Step 8: Type check, lint, build**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected: tsc silent; lint 11 problems (4 errors, 7 warnings), as at baseline;
build succeeds (checked while planning: `next build` 16.2.6 accepts
`allowImportingTsExtensions` and a test file that imports `./x.ts`).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/site.ts frontend/src/lib/sign-in-gate.ts frontend/src/lib/site.test.ts frontend/src/proxy.ts frontend/package.json frontend/tsconfig.json
git commit -m "$(cat <<'EOF'
feat(proxy): route each page to the host that owns it; signup first on the voyage hub

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: The site context and per-host metadata

**Files:**
- Create: `frontend/src/lib/site-server.ts`
- Create: `frontend/src/lib/site-context.tsx`
- Modify: `frontend/src/app/layout.tsx` (lines 1–5, 27–64, 70–83)
- Modify: `frontend/Dockerfile` (lines 12–16), `.github/workflows/deploy.yml` (lines 53–54)

**Interfaces:**
- Consumes: Task 7's `Site`, `origin`, `appOfHost`, `settingsFromEnv`, `resolveHref`.
- Produces:
  - `currentSite(): Promise<Site>` (`@/lib/site-server`, server components only).
  - `SiteProvider({ site, children })`, `useSite(): SiteTools` with
    `SiteTools = { app: AppName; href(path: string): string; go(path: string, options?: { replace?: boolean }): void }`,
    and `AppLink` — `next/link`'s props with `href: string` (`@/lib/site-context`).

- [ ] **Step 1: Create `frontend/src/lib/site-server.ts`**

```ts
import { headers } from "next/headers"
import { appOfHost, settingsFromEnv, type Site } from "./site"

/** This request's app and the settings, read at request time (subdomain
 *  split spec, decisions 21 and 24): DOMAIN comes from the container's
 *  environment, so changing it needs no rebuild. Server components only. */
export async function currentSite(): Promise<Site> {
  const settings = settingsFromEnv(process.env)
  return { settings, app: appOfHost((await headers()).get("host"), settings.domain) }
}
```

- [ ] **Step 2: Create `frontend/src/lib/site-context.tsx`**

```tsx
"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { createContext, useContext, useMemo, type ComponentProps, type ReactNode } from "react"
import { resolveHref, type AppName, type Site } from "./site"

const SiteContext = createContext<Site | null>(null)

/** Hands the app this page was served on, and the settings, to every client
 *  component (subdomain split spec, decision 37). The root layout reads both
 *  per request. */
export function SiteProvider({ site, children }: { site: Site; children: ReactNode }) {
  return <SiteContext.Provider value={site}>{children}</SiteContext.Provider>
}

export interface SiteTools {
  app: AppName
  /** The path itself when this host serves it, the owner's absolute URL
   *  otherwise. */
  href: (path: string) => string
  /** The router on this host; a full page load to another host, which is
   *  where the shared session cookie keeps the person signed in. */
  go: (path: string, options?: { replace?: boolean }) => void
}

export function useSite(): SiteTools {
  const site = useContext(SiteContext)
  if (!site) throw new Error("useSite must be used inside SiteProvider")
  const router = useRouter()
  return useMemo<SiteTools>(() => ({
    app: site.app,
    href: (path) => resolveHref(path, site),
    go: (path, options) => {
      const target = resolveHref(path, site)
      if (target !== path) {
        if (options?.replace) window.location.replace(target)
        else window.location.assign(target)
      } else if (options?.replace) {
        router.replace(path)
      } else {
        router.push(path)
      }
    },
  }), [site, router])
}

/** next/link, with the href resolved for this host. next/link already hands
 *  an other-origin href to the browser — a full page load, never prefetched
 *  (next/dist/client/app-dir/link.js, linkClicked) — so one component covers
 *  both cases. A client component: the server-rendered footer, auth layout
 *  and landing can render it. */
export function AppLink({ href, ...props }: Omit<ComponentProps<typeof Link>, "href"> & { href: string }) {
  const site = useSite()
  return <Link href={site.href(href)} {...props} />
}
```

- [ ] **Step 3: Read the host in the root layout**

Replace `frontend/src/app/layout.tsx` with the file below. Only four things
change: the imports, `metadata` becomes `generateMetadata()` (its
`metadataBase` and `openGraph.url` come from the host), the layout becomes
`async`, and `SiteProvider` wraps the app. Every French string is the current
one, character for character.

```tsx
import type { Metadata, Viewport } from "next"
import { Inter, JetBrains_Mono, Plus_Jakarta_Sans } from "next/font/google"
import "./globals.css"
import { AuthProvider } from "@/lib/auth"
import { origin } from "@/lib/site"
import { SiteProvider } from "@/lib/site-context"
import { currentSite } from "@/lib/site-server"

// Display — neoori charter face (Plus Jakarta Sans): humanist geometric sans, brand-aligned.
const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin", "latin-ext"],
  variable: "--font-jakarta",
  display: "swap",
})

// Body — clean, legible workhorse for dense French copy.
const inter = Inter({
  subsets: ["latin", "latin-ext"],
  variable: "--font-inter",
  display: "swap",
})

// Data / eyebrows — technical precision (section markers, B2G traceability).
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
})

// Per request (subdomain split spec, decision 24): metadataBase and og:url
// name the host the page is served on — its origin rebuilt from DOMAIN, never
// the raw Host header — so each subdomain's preview names itself. Reading the
// host makes every page dynamic; at this traffic that costs nothing.
export async function generateMetadata(): Promise<Metadata> {
  const { settings, app } = await currentSite()
  const url = origin(app, settings)
  return {
    metadataBase: new URL(url),
    title: {
      default: "neoori — Orientation et analyse de CV",
      template: "%s · neoori",
    },
    description:
      "Faites le point sur votre parcours : l'analyse de votre CV face au poste que vous visez, et le voyage, six sessions pour poser ce que vous savez déjà de vous. Conçu pour les conseillers, les organisations de l'emploi et les candidats.",
    keywords: [
      "orientation professionnelle", "analyse de CV", "projet professionnel", "reconversion",
      "insertion professionnelle", "conseiller en évolution professionnelle", "Cap Emploi",
      "France Travail", "Mission Locale", "RGPD", "bilan de compétences",
    ],
    applicationName: "neoori",
    authors: [{ name: "neoori" }],
    openGraph: {
      type: "website",
      locale: "fr_FR",
      url,
      siteName: "neoori",
      title: "neoori — Orientation et analyse de CV",
      description:
        "L'analyse de votre CV face à votre cible, et le voyage en six sessions. Pour les conseillers, les organisations de l'emploi et les candidats.",
      images: [{ url: "/img/og-cover.png", width: 1200, height: 630, alt: "neoori" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "neoori — Orientation et analyse de CV",
      description:
        "L'analyse de votre CV face à votre cible, et le voyage en six sessions pour faire le point sur votre parcours.",
      images: ["/img/og-cover.png"],
    },
    icons: { icon: "/icon.svg" },
  }
}

export const viewport: Viewport = {
  themeColor: "#1c3561",
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const site = await currentSite()
  return (
    <html
      lang="fr"
      suppressHydrationWarning
      className={`${jakarta.variable} ${inter.variable} ${jetbrains.variable}`}
    >
      <body className="antialiased min-h-screen bg-background text-foreground">
        <script dangerouslySetInnerHTML={{ __html: "document.documentElement.classList.add('js')" }} />
        <SiteProvider site={site}>
          <AuthProvider>{children}</AuthProvider>
        </SiteProvider>
      </body>
    </html>
  )
}
```

Check that only the intended words changed (indentation does not count as a
word change):

```bash
git diff --word-diff=plain -U0 frontend/src/app/layout.tsx | grep -E '\[-|\{\+'
```

Expected: only the new imports, the comment, `generateMetadata` / `return {`,
`metadataBase`, `url`, `async` / `currentSite`, and the `SiteProvider` lines —
no French word.

- [ ] **Step 4: Drop the build-time site URL**

In `frontend/Dockerfile`, replace:

```dockerfile
# Public site origin baked into the bundle (metadata/OG URLs). CI passes the
# SITE_URL repo variable; empty -> localhost fallback in layout.tsx.
ARG NEXT_PUBLIC_SITE_URL
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_TELEMETRY_DISABLED=1
```

with:

```dockerfile
# No site URL is baked in: the frontend reads DOMAIN at request time
# (subdomain split spec, decision 21).
ENV NEXT_TELEMETRY_DISABLED=1
```

In `.github/workflows/deploy.yml`, delete these two lines of the
« Build & push frontend » step:

```yaml
          build-args: |
            NEXT_PUBLIC_SITE_URL=${{ vars.SITE_URL }}
```

Then confirm nothing else reads it:

```bash
grep -rn "SITE_URL" frontend/src frontend/Dockerfile .github ; echo "grep exit: $?"
```

Expected: `grep exit: 1`.

- [ ] **Step 5: Type check, lint, build, unit tests**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm test && npm run build`
Expected: tsc silent; lint still 11 problems; 12 tests pass; the build
succeeds and its route table marks every page `ƒ` (dynamic) — expected, the
layout reads the host (decision 24).

- [ ] **Step 6: Check the metadata through the dev stack**

```bash
docker compose up -d --force-recreate --renew-anon-volumes backend frontend nginx
sleep 30
og() { printf '%-26s %-6s ' "$1" "$2"; curl -s -H "Host: $1" "http://127.0.0.1:8080$2" | grep -o '<meta property="og:url" content="[^"]*"'; }
og neoori.localhost /
og cv.neoori.localhost /cgv
og voyage.neoori.localhost /cgv
```

Expected:

```
neoori.localhost           /      <meta property="og:url" content="http://neoori.localhost:8080"
cv.neoori.localhost        /cgv   <meta property="og:url" content="http://cv.neoori.localhost:8080"
voyage.neoori.localhost    /cgv   <meta property="og:url" content="http://voyage.neoori.localhost:8080"
```

(`--renew-anon-volumes` gives the frontend a fresh `.next` cache instead of the
one the main checkout's dev server left; `node_modules` comes back from the
image. The first page compiles slowly in dev: if a line is empty, wait and run
it again.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/site-server.ts frontend/src/lib/site-context.tsx frontend/src/app/layout.tsx frontend/Dockerfile .github/workflows/deploy.yml
git commit -m "$(cat <<'EOF'
feat(site): the layout hands the host to a client context; metadata names each host

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Home per host and the navigation after sign-in

**Files:**
- Modify: `frontend/src/lib/home.ts` (whole file)
- Create: `frontend/src/lib/home.test.ts`
- Modify: `frontend/src/components/layout/AppBar.tsx` (whole file)
- Modify: `frontend/src/app/admin/layout.tsx` (lines 3–5, 25–31, 70)
- Modify: `frontend/src/app/(auth)/connexion/page.tsx` (lines 4, 39, 62), `connexion/lien/page.tsx` (lines 4, 33, 75, 79), `inscription/finaliser/page.tsx` (lines 4, 44, 80), `verifier-email/page.tsx` (lines 4, 30, 88), `reinitialiser-mot-de-passe/page.tsx` (lines 4, 36, 55)

**Interfaces:**
- Consumes: Task 8's `useSite()` (`app`, `go`) and `AppLink`; Task 7's `AppName`.
- Produces: `homeFor(role: User["role"] | undefined, app: AppName): string` —
  says what Task 4's `_home_path(role, app)` says.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/home.test.ts`:

```ts
import { test } from "node:test"
import assert from "node:assert/strict"
import { homeFor } from "./home.ts"

test("a candidate's home is the espace on cv and the hub on voyage", () => {
  assert.equal(homeFor("candidate", "cv"), "/espace")
  assert.equal(homeFor("candidate", "voyage"), "/voyage")
  assert.equal(homeFor(undefined, "voyage"), "/voyage")
  assert.equal(homeFor("candidate", "root"), "/espace")
})

test("a counselor's and an admin's home are the same on every host", () => {
  for (const app of ["root", "cv", "voyage"] as const) {
    assert.equal(homeFor("counselor", app), "/conseiller")
    assert.equal(homeFor("admin", app), "/admin")
  }
})
```

Run: `cd frontend && npm test`
Expected: FAIL — `homeFor("candidate", "voyage")` is `/espace`.

- [ ] **Step 2: Give `homeFor` the host**

Replace `frontend/src/lib/home.ts` with:

```ts
import type { AppName } from "./site"
import type { User } from "@/types"

/**
 * Where a signed-in person belongs, on the host they are on. Two places rely
 * on this agreeing: the app bar's logo, and where the sign-in pages send
 * someone who did not arrive with a ?redirect=. An admin or an approved
 * conseiller has no use for the candidate espace, and their menu is trimmed
 * to match — so the logo has to lead home, or they land somewhere with no
 * way back.
 *
 * A candidate's home is /espace on cv and the voyage hub on voyage (subdomain
 * split spec, decision 15). backend/app/routes/auth_oauth.py _home_path says
 * the same for a Google/Microsoft sign-in: keep the two in step.
 *
 * A pending, rejected or revoked conseiller is role "candidate" by design and
 * correctly gets the candidate home.
 */
export function homeFor(role: User["role"] | undefined, app: AppName): string {
  if (role === "admin") return "/admin"
  if (role === "counselor") return "/conseiller"
  return app === "voyage" ? "/voyage" : "/espace"
}
```

Run: `cd frontend && npm test` → 14 pass.

- [ ] **Step 3: The app bar**

Replace `frontend/src/components/layout/AppBar.tsx` with:

```tsx
"use client"

import { useAuth } from "@/lib/auth"
import { homeFor } from "@/lib/home"
import { AppLink, useSite } from "@/lib/site-context"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDown, LogOut, LayoutDashboard, Map as MapIcon, PlusCircle, Shield, UserRound } from "lucide-react"
import { Logo } from "@/components/brand/Logo"

/** Authed-app top bar (espace + analysis flow).
 *
 *  The menu is cut to the role. An admin and an approved conseiller do not use
 *  the candidate surfaces, so they are not offered them; each keeps only the
 *  one entry that is theirs, plus Déconnexion. Because their menu no longer
 *  leads anywhere, the logo carries them home instead of to /espace — without
 *  that, clicking it would drop them into the candidate space with no route
 *  back. A pending or revoked conseiller is role "candidate" and keeps the
 *  full candidate menu, which is correct: that is what they are until approval.
 *
 *  The bar sits on cv, voyage and shared pages alike, so every entry goes
 *  through AppLink: « Nouvelle analyse » or « Mon voyage » may be on the other
 *  host (subdomain split spec, decision 7).
 */
export function AppBar() {
  const { user, logout } = useAuth()
  const { app, go } = useSite()

  const handleLogout = async () => {
    await logout()
    // The root landing (decision 16). The session ended on every host.
    go("/")
  }

  const isCandidate = !user || user.role === "candidate"

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/85 backdrop-blur-md no-print">
      <div className="mx-auto flex h-20 max-w-6xl items-center justify-between px-5 sm:px-8">
        <AppLink
          href={user ? homeFor(user.role, app) : "/"}
          className="text-[24px] transition-opacity hover:opacity-80"
          aria-label="neoori — accueil"
        >
          <Logo />
        </AppLink>

        <div className="flex items-center gap-2">
          {isCandidate && (
            <Button render={<AppLink href="/analyse" />} size="lg">
              <PlusCircle />
              <span className="hidden sm:inline">Nouvelle analyse</span>
              <span className="sm:hidden">Analyse</span>
            </Button>
          )}

          {user && (
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button variant="ghost" size="lg" className="gap-1.5" />}>
                <span className="hidden max-w-[14rem] truncate sm:inline">{user.email}</span>
                <ChevronDown className="size-4" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                {user.role === "candidate" && (
                  <>
                    <DropdownMenuItem render={<AppLink href="/espace" />}>
                      <LayoutDashboard />
                      Mon espace
                    </DropdownMenuItem>
                    <DropdownMenuItem render={<AppLink href="/profil" />}>
                      <UserRound />
                      Mes informations
                    </DropdownMenuItem>
                    <DropdownMenuItem render={<AppLink href="/voyage" />}>
                      <MapIcon />
                      Mon voyage
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                  </>
                )}

                {user.role === "admin" && (
                  <>
                    <DropdownMenuItem render={<AppLink href="/admin" />}>
                      <Shield />
                      Administration
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                  </>
                )}

                <DropdownMenuItem onClick={handleLogout} variant="destructive">
                  <LogOut />
                  Déconnexion
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
    </header>
  )
}
```

- [ ] **Step 4: The admin layout**

In `frontend/src/app/admin/layout.tsx`, replace:

```tsx
import { useAuth } from "@/lib/auth"
```

with:

```tsx
import { useAuth } from "@/lib/auth"
import { AppLink, useSite } from "@/lib/site-context"
```

Replace:

```tsx
  const { user, loading, logout } = useAuth()

  const handleLogout = async () => {
    await logout()
    router.push("/")
  }
```

with:

```tsx
  const { user, loading, logout } = useAuth()
  const { go } = useSite()

  const handleLogout = async () => {
    await logout()
    // The root landing (subdomain split spec, decision 16).
    go("/")
  }
```

Replace:

```tsx
          <Button render={<Link href="/espace" />} size="lg" className="mt-4">
```

with:

```tsx
          <Button render={<AppLink href="/espace" />} size="lg" className="mt-4">
```

(`router` still drives the signed-out redirect at line 38 and `Link` the
admin nav: keep both imports.)

- [ ] **Step 5: The five sign-in pages**

Each page swaps the router for `useSite()` and sends the person through
`go()`, so a destination the other app owns is a full page load (decision 29).

`frontend/src/app/(auth)/connexion/page.tsx`:
- Replace `import { useRouter, useSearchParams } from "next/navigation"` with `import { useSearchParams } from "next/navigation"`.
- Replace `import { homeFor } from "@/lib/home"` with:
  ```tsx
  import { homeFor } from "@/lib/home"
  import { useSite } from "@/lib/site-context"
  ```
- Replace `  const router = useRouter()` with `  const { app, go } = useSite()`.
- Replace `      router.push(redirect ?? homeFor(signedIn.role))` with `      go(redirect ?? homeFor(signedIn.role, app))`.

`frontend/src/app/(auth)/connexion/lien/page.tsx`:
- Replace `import { useRouter, useSearchParams } from "next/navigation"` with `import { useSearchParams } from "next/navigation"`.
- Replace `import { homeFor } from "@/lib/home"` with:
  ```tsx
  import { homeFor } from "@/lib/home"
  import { useSite } from "@/lib/site-context"
  ```
- Replace `  const router = useRouter()` with `  const { app, go } = useSite()`.
- Replace `        router.replace("/inscription/finaliser")` with `        go("/inscription/finaliser", { replace: true })`.
- Replace `      router.replace(res.next ?? homeFor(res.user.role))` with `      go(res.next ?? homeFor(res.user.role, app), { replace: true })`.

`frontend/src/app/(auth)/inscription/finaliser/page.tsx`:
- Delete the line `import { useRouter } from "next/navigation"`.
- Replace `import { homeFor } from "@/lib/home"` with:
  ```tsx
  import { homeFor } from "@/lib/home"
  import { useSite } from "@/lib/site-context"
  ```
- Replace `  const router = useRouter()` with `  const { app, go } = useSite()`.
- Replace `      router.replace(res.next ?? homeFor(res.user.role))` with `      go(res.next ?? homeFor(res.user.role, app), { replace: true })`.

`frontend/src/app/(auth)/verifier-email/page.tsx`:
- Replace `import { useRouter, useSearchParams } from "next/navigation"` with `import { useSearchParams } from "next/navigation"`.
- Replace `import { homeFor } from "@/lib/home"` with:
  ```tsx
  import { homeFor } from "@/lib/home"
  import { useSite } from "@/lib/site-context"
  ```
- Replace `  const router = useRouter()` with `  const { app, go } = useSite()`.
- Replace `      router.replace(res.next ?? homeFor(res.user.role))` with `      go(res.next ?? homeFor(res.user.role, app), { replace: true })`.

`frontend/src/app/(auth)/reinitialiser-mot-de-passe/page.tsx`:
- Replace `import { useRouter, useSearchParams } from "next/navigation"` with `import { useSearchParams } from "next/navigation"`.
- Replace `import { homeFor } from "@/lib/home"` with:
  ```tsx
  import { homeFor } from "@/lib/home"
  import { useSite } from "@/lib/site-context"
  ```
- Replace `  const router = useRouter()` with `  const { app, go } = useSite()`.
- Replace `      router.replace(homeFor(res.user.role))` with `      go(homeFor(res.user.role, app), { replace: true })`.

`res.next` is the path the server signed into the link, passed on verbatim as
before: `go` either hands it to the router unchanged or prefixes one of the
three origins, and a path that starts with `/` and not `//` (the server's
`safe_next`) stays on that origin.

Check nothing else calls `homeFor` with one argument or leaves a router
behind:

```bash
cd frontend/src && grep -rn "homeFor(" . | grep -v "homeFor(.*, " ; grep -n "useRouter\|router\." "app/(auth)/connexion/page.tsx" "app/(auth)/connexion/lien/page.tsx" "app/(auth)/inscription/finaliser/page.tsx" "app/(auth)/verifier-email/page.tsx" "app/(auth)/reinitialiser-mot-de-passe/page.tsx"; echo "grep exit: $?"
```

Expected: no output at all, `grep exit: 1` (every `homeFor(` call, and the
definition itself, now has a second argument).

- [ ] **Step 6: Type check, lint, tests, build**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm test && npm run build`
Expected: tsc silent; lint 11 problems; 14 tests pass; build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/home.ts frontend/src/lib/home.test.ts frontend/src/components/layout/AppBar.tsx frontend/src/app/admin/layout.tsx "frontend/src/app/(auth)"
git commit -m "$(cat <<'EOF'
feat(site): home per host; logout lands on the root; sign-in goes to the other app by a page load

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Cross-host links

**Files:**
- Modify (every `Link` becomes `AppLink`): `frontend/src/components/layout/SiteNav.tsx`, `SiteFooter.tsx`, `AuthLayout.tsx`, `frontend/src/app/page.tsx`, `frontend/src/app/analyse/envoyee/page.tsx`, `frontend/src/app/c/[token]/page.tsx`, `frontend/src/app/voyage/c/[token]/page.tsx`
- Modify (two links): `frontend/src/app/espace/page.tsx:129-133,150,170`
- Modify (one link): `frontend/src/app/analyse/nouveau/page.tsx:406`

**Interfaces:**
- Consumes: Task 8's `AppLink`.
- Produces: nothing new. `app/conseiller/page.tsx` and
  `app/conseiller/analyses/[id]/page.tsx` link only to shared paths and stay as
  they are (spec, « Frontend »).

- [ ] **Step 1: Files whose every link may cross hosts**

These seven files use `next/link` only for links that may point at another
host — the root's anchors and logo, the landing's CTAs, « Retour à
l'accueil », the voyage counselor view's « Mon espace ». In each, the import
becomes `AppLink` and every `<Link` / `</Link>` becomes `<AppLink` / `</AppLink>`:

```bash
cd frontend/src && for f in components/layout/SiteNav.tsx components/layout/SiteFooter.tsx \
    components/layout/AuthLayout.tsx app/page.tsx app/analyse/envoyee/page.tsx \
    'app/c/[token]/page.tsx' 'app/voyage/c/[token]/page.tsx'; do
  perl -pi -e 's#^import Link from "next/link"$#import { AppLink } from "\@/lib/site-context"#; s#<Link\b#<AppLink#g; s#</Link>#</AppLink>#g' "$f"
  printf '%-34s AppLink tags: %s, leftovers: %s\n' "$f" "$(grep -c '<AppLink' "$f")" "$(grep -c 'next/link\|<Link\b' "$f")"
done
```

Expected:

```
components/layout/SiteNav.tsx      AppLink tags: 7, leftovers: 0
components/layout/SiteFooter.tsx   AppLink tags: 1, leftovers: 0
components/layout/AuthLayout.tsx   AppLink tags: 2, leftovers: 0
app/page.tsx                       AppLink tags: 8, leftovers: 0
app/analyse/envoyee/page.tsx       AppLink tags: 1, leftovers: 0
app/c/[token]/page.tsx             AppLink tags: 1, leftovers: 0
app/voyage/c/[token]/page.tsx      AppLink tags: 2, leftovers: 0
```

Each import line now reads `import { AppLink } from "@/lib/site-context"`.
`SiteFooter.tsx`, `AuthLayout.tsx`, `app/page.tsx`, `envoyee` and `c/[token]`
stay server components: they render `AppLink`, a client component, as they
rendered `Link`.

- [ ] **Step 2: The espace's voyage links**

In `frontend/src/app/espace/page.tsx`, replace:

```tsx
import Link from "next/link"
```

with:

```tsx
import Link from "next/link"
import { AppLink } from "@/lib/site-context"
```

Replace:

```tsx
                render={
                  <Link
                    href={voyage.portrait_status === "validated" ? "/voyage/portrait" : "/voyage"}
                  />
                }
```

with:

```tsx
                render={
                  <AppLink
                    href={voyage.portrait_status === "validated" ? "/voyage/portrait" : "/voyage"}
                  />
                }
```

Replace:

```tsx
        {voyageLoaded && !voyage && (
          <Link
            href="/voyage"
```

with:

```tsx
        {voyageLoaded && !voyage && (
          <AppLink
            href="/voyage"
```

and that card's closing tag:

```tsx
            </div>
          </Link>
        )}

        {garder && claimed && (
```

with:

```tsx
            </div>
          </AppLink>
        )}

        {garder && claimed && (
```

The espace's other links (`/analyse`, its reports) are cv's own: they stay
`Link`.

- [ ] **Step 3: The form's voyage link**

In `frontend/src/app/analyse/nouveau/page.tsx`, replace:

```tsx
import Link from "next/link"
```

with:

```tsx
import Link from "next/link"
import { AppLink } from "@/lib/site-context"
```

and:

```tsx
              <Link href="/voyage" className="link-underline text-navy">voyage</Link> ; vous
```

with:

```tsx
              <AppLink href="/voyage" className="link-underline text-navy">voyage</AppLink> ; vous
```

(`/profil` and `/connexion` are shared: cv serves them, they stay `Link`.)

- [ ] **Step 4: Type check, lint, tests, build**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm test && npm run build`
Expected: tsc silent; lint 11 problems; 14 tests pass; build succeeds.

- [ ] **Step 5: See the links resolve on the dev stack**

The dev stack from Task 8 hot-reloads. Then:

```bash
curl -s -H "Host: neoori.localhost" http://127.0.0.1:8080/ | grep -o 'href="http://[a-z.]*localhost:8080/[a-z/#-]*"' | sort | uniq -c
curl -s -H "Host: voyage.neoori.localhost" http://127.0.0.1:8080/cgv | grep -o 'href="[^"]*#[a-z-]*"' | sort -u
```

Expected: the landing's links name `http://cv.neoori.localhost:8080/analyse`,
`http://cv.neoori.localhost:8080/connexion`,
`http://cv.neoori.localhost:8080/inscription-conseiller` and
`http://voyage.neoori.localhost:8080/voyage` (its own anchors such as
`/#rapport` stay relative); the CGV page on voyage links its footer anchors to
`http://neoori.localhost:8080/#voyage`, `/#module`, `/#rapport`, `/#tarifs`,
`/#pour-qui` on the root.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "$(cat <<'EOF'
feat(site): links that cross hosts go through AppLink

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Docs

**Files:**
- Modify: `CLAUDE.md` (lines 116–117, 164, 176, 187, 192, 368; new section after line 195)
- Modify: `DOCKER.md` (lines 9–21, 81–82, 84–111, after 150, 155–158, after 175)
- Modify: `TEST-PLAN.md` (lines 3, 165, 218; new § 14 before « What to report back »)
- Modify: `AUTOMATION-PLAN.md` (line 160), `handoff.md` (line 30), `frontend/README.md` (line 10)

**Interfaces:**
- Consumes: everything above.
- Produces: docs only.

- [ ] **Step 1: CLAUDE.md**

Replace:

```
- Access logs (nginx, gunicorn) record the path only — no query string, no
  Referer.
```

with:

```
- Access logs (nginx, gunicorn) record the path only — no query string, no
  Referer; nginx's line also carries the host.
```

Replace:

```
Live at **https://neoori.tech** (www redirects to the apex). Everything runs as Docker containers on one Hostinger VPS (KVM 2, Ubuntu 24.04, IP `186.240.157.26`). Full runbook: `DOCKER.md`.
```

with:

```
Live at **https://neoori.tech** (the landing), **https://cv.neoori.tech** (« J'ai une cible ») and **https://voyage.neoori.tech** (le voyage); www redirects to the apex. The domain is one setting, `DOMAIN` (see « Sous-domaines »). Everything runs as Docker containers on one Hostinger VPS (KVM 2, Ubuntu 24.04, IP `186.240.157.26`). Full runbook: `DOCKER.md`.
```

Replace:

```
nginx serves both apps from one origin, so everything stays same-origin from the browser's perspective. JWT cookies are `SameSite=Lax` because of this.
```

with:

```
nginx serves both apps on each host, so every page's API calls stay same-origin. The session cookies are `SameSite=Lax` and span the whole domain (`Domain=DOMAIN`): one sign-in for the landing, `cv.` and `voyage.` (« Sous-domaines »).
```

Replace:

```
Local dev mirrors prod routing: `docker compose up -d` → http://localhost:8080
```

with:

```
Local dev mirrors prod routing: `docker compose up -d` → http://neoori.localhost:8080 (the landing), http://cv.neoori.localhost:8080, http://voyage.neoori.localhost:8080 — in Chrome, which resolves `*.localhost` by itself.
```

Replace:

```
- Frontend `NEXT_PUBLIC_*` values are baked at image build time (CI build-args), not read from VPS runtime env.
```

with:

```
- The frontend reads `DOMAIN` at request time (`environment:` in both compose files): no site URL is baked into the image. `NEXT_PUBLIC_API_URL`, unset everywhere, is the one build-time value left, and like any `NEXT_PUBLIC_*` value it would need a rebuild.
```

Replace:

```
- Mail: Resend, From `MAIL_FROM`, links from `APP_URL`. With no key in dev the
  link is printed in the backend log.
```

with:

```
- Mail: Resend, From `MAIL_FROM`, links built from `DOMAIN` (`utils/site.py`):
  an account mail names the host it was asked from, every other mail cv. With
  no key in dev the link is printed in the backend log.
```

After the « Known gotchas » list of « Live deployment (VPS) » (it ends with the
`FORCE_ANALYSIS_TIER` bullet, just before `## Le voyage`), add:

```markdown

## Sous-domaines

One Next.js app, one backend, one database and one sign-in, on three hosts
built from one setting, `DOMAIN` (`/srv/neoori/.env`, read when the containers
start: changing it needs no rebuild).

| Host | Serves |
|---|---|
| `DOMAIN` | today's landing at `/`, nothing else: every other path redirects (307) to the host that serves it |
| `cv.DOMAIN` | « J'ai une cible »: `/analyse/*`, `/rapport`, `/espace`; `/` → `/analyse/nouveau` until its landing exists |
| `voyage.DOMAIN` | le voyage: `/voyage/*`; `/` → `/voyage` |

Every other page — the sign-in pages, `/profil`, `/conseiller`, `/admin`, the
legal pages — is shared: served on cv and voyage, and sent from the root to
cv. The table lives in `frontend/src/lib/site.ts`: **a new page that belongs
to one app needs a row there**, or it is shared. A link that may cross hosts
uses `AppLink`, `useSite().href` or `go()` (`lib/site-context.tsx`).

- **One sign-in.** The session cookies are `neoori_access` / `neoori_refresh`
  with `Domain=DOMAIN` (`config.py`, `app/__init__.py`). The Google/Microsoft
  state, the signup ticket and `neoori_hold` stay on one host: each of their
  round trips starts and ends there.
- **Absolute URLs come from `DOMAIN`, never from the Host header**
  (`backend/app/utils/site.py`). An account mail links to the host it was
  asked from — cv when that is any other name — and every other mail to cv;
  the Google/Microsoft callback is on the host the sign-in started on (both
  are registered with each provider); Stripe returns to cv.
- **No subdomain of `DOMAIN` may be served by anything but this stack** — no
  blog, status page, click-tracking domain, staging copy or CNAME to an
  outside service. It would receive every session cookie, and `SameSite=Lax`
  does not stop a sibling subdomain from sending signed-in requests (CSRF
  protection is off). DOCKER.md, « No subdomain may point anywhere else ».
- `MAIL_FROM` is deliberately separate from `DOMAIN`: Resend silently refuses
  an unverified sender. The order for a domain swap is in DOCKER.md,
  « Swapping the domain later ».

Spec: `docs/superpowers/specs/2026-10-09-subdomain-split-design.md`
```

- [ ] **Step 2: DOCKER.md**

Replace:

```bash
docker compose up -d          # first run builds images (a few minutes)
open http://localhost:8080    # nginx: / -> Next.js, /api -> Flask
```

with:

```bash
docker compose up -d                       # first run builds images (a few minutes)
open http://neoori.localhost:8080          # the landing; nginx: / -> Next.js, /api -> Flask
open http://cv.neoori.localhost:8080       # « J'ai une cible »
open http://voyage.neoori.localhost:8080   # le voyage
```

and, in the bullet list under it, after `- Port 80 is left to the TaifOr dev stack; neoori dev uses **8080**.`, add:

```
- The three dev hosts work in Chrome, which resolves `*.localhost` to the
  loopback by itself (Safari does not). One sign-in covers the three: the
  session cookie is set on `neoori.localhost`. Plain `http://localhost:8080`
  shows the landing too, and its links lead to the three names.
```

After `Not to a commit below the four-doors migration, though: that takes four commands in a fixed order, see « Rolling back below the four-doors migration » under Purge.`, add:

```

Rolling back below the subdomain split works the same way, with one
condition: if `APP_URL` and `FRONTEND_URL` were already deleted from
`/srv/neoori/.env`, put `FRONTEND_URL=https://neoori.tech` back first — the
earlier image builds Stripe's return URL from it, and its fallback is
`http://localhost:3000`. Everyone signs in once more (the earlier image reads
the old cookie names).
```

Replace the TLS section's opening paragraph:

```
**Done 23/08** — `neoori.tech` + `www.neoori.tech`, cert expires 21/11/2026.
The site is live at https://neoori.tech; www 301s to the apex; plain http 301s
to https. Steps kept for a re-issue or a second domain:
```

with:

```
**Done 23/08** — `neoori.tech` + `www.neoori.tech`, cert expires 21/11/2026.
The site is live at https://neoori.tech; www 301s to the apex; plain http 301s
to https. The subdomain split adds `cv.` and `voyage.` to the same
certificate (« Adding cv. and voyage. », below). Steps kept for a re-issue or
a second domain:
```

Replace:

```bash
docker compose -f docker-compose.prod.yml run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot -d neoori.tech -d www.neoori.tech \
  --email nneoori@proton.me --agree-tos --no-eff-email

# 3. Switch nginx to the TLS template (and point FRONTEND_URL at the domain —
#    it drives the backend CORS allow-list and Stripe return URLs)
sed -i 's|^FRONTEND_URL=.*|FRONTEND_URL=https://neoori.tech|; s/^NGINX_MODE=.*/NGINX_MODE=https/' .env
docker compose -f docker-compose.prod.yml up -d
```

with:

```bash
docker compose -f docker-compose.prod.yml run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot \
  -d neoori.tech -d www.neoori.tech -d cv.neoori.tech -d voyage.neoori.tech \
  --email nneoori@proton.me --agree-tos --no-eff-email

# 3. Switch nginx to the TLS template
sed -i 's/^NGINX_MODE=.*/NGINX_MODE=https/' .env
docker compose -f docker-compose.prod.yml up -d
```

Delete the paragraph:

```
The GitHub repo **variable** `SITE_URL=https://neoori.tech` is set; it bakes
into the frontend image as `NEXT_PUBLIC_SITE_URL` (metadata/OG URLs), so it
only takes effect on the next image build.
```

and put this subsection in its place:

````
### Adding cv. and voyage. (the subdomain split)

Done once, **before** the deploy that ships the split: without it `cv.` and
`voyage.` show a certificate warning.

```bash
# 1. DNS: A records cv and voyage -> 186.240.157.26. No AAAA (below). Wait
#    until both resolve: dig +short cv.neoori.tech voyage.neoori.tech
# 2. Expand the certificate. It keeps its name (--cert-name), so the
#    template's paths and the renew loop do not change. Today's port-80
#    server is the only one, so it answers the challenge for the new names.
#    --dry-run first: Let's Encrypt rate-limits failures.
docker compose -f docker-compose.prod.yml run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot --cert-name neoori.tech --expand \
  -d neoori.tech -d www.neoori.tech -d cv.neoori.tech -d voyage.neoori.tech \
  --email nneoori@proton.me --agree-tos --no-eff-email --dry-run
# then the same command without --dry-run, and:
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

After the deploy, delete `APP_URL` and `FRONTEND_URL` from
`/srv/neoori/.env` and the GitHub repo variable `SITE_URL` — but only once
no rollback below the split is expected (« CI/CD », rollback).
````

After the « Do not publish an AAAA record (rate limits) » subsection (it ends
with the paragraph that closes `...would draw on one 10 r/min bucket.`), add:

```

### No subdomain may point anywhere else

The session cookies carry `Domain=neoori.tech`: one sign-in for the landing,
`cv.` and `voyage.`, so every host under the domain receives them. A
subdomain served by anything but this stack — a blog, a status page, a Resend
click-tracking domain, any CNAME to an outside service, a staging copy of the
app — would receive every visitor's session. And because `cv.` and `voyage.`
count as one site to a browser, `SameSite=Lax` would not stop such a host from
sending signed-in requests either (CSRF protection is off). The zone holds the
apex, `www`, `cv`, `voyage` and the mail records Resend needs, and nothing else
that serves HTTP. A staging stack gets a domain of its own.
```

In « Access logs record the path only », replace
`An access line carries the address, the time, the method, the` with
`An access line carries the address, the time, the host, the method, the`.

Before `## Google / Microsoft sign-in keys`, add:

````
## Swapping the domain later

The domain is written in one place: `DOMAIN` in `/srv/neoori/.env` (nginx,
the backend and the frontend read it when their containers start). Each time
it changes:

1. DNS for the new domain: A records for the apex, `www`, `cv` and `voyage`
   → 186.240.157.26. No AAAA.
2. A certificate for the new domain's four names: the command in « TLS »
   with the new names and `--cert-name <new domain>`. nginx's port-80 default
   server answers the challenge for names it does not serve yet.
3. `DOMAIN=<new domain>` in `/srv/neoori/.env`, then
   ```bash
   docker compose -f docker-compose.prod.yml up -d --force-recreate backend frontend nginx
   ```
   nginx re-renders its template; nothing is rebuilt.
4. Google and Microsoft: add `https://cv.<new>/api/auth/<provider>/callback`
   and `https://voyage.<new>/api/auth/<provider>/callback`.
5. Stripe: the webhook URL, `https://<new>/api/payments/webhook`.
6. Resend: verify the new domain, then change `MAIL_FROM`. Until then mails
   leave from the old address and link to the new domain — never the other
   way round: an unverified sender is refused, silently.

Links to the old domain (mails already sent, bookmarks) stop working once its
DNS moves away.

````

In « Google / Microsoft sign-in keys », after the command block
`docker compose -f docker-compose.prod.yml up -d --force-recreate backend`
(the one that follows « After editing `.env`: »), add:

```

Each provider registers two redirect URIs, one per subdomain, because a
sign-in ends on the host it started on:
`https://cv.neoori.tech/api/auth/<provider>/callback` and
`https://voyage.neoori.tech/api/auth/<provider>/callback`. The spec's
appendices A and B predate the split and name the root's; use these two.
```

- [ ] **Step 3: TEST-PLAN.md**

Replace line 3:

```
Test environment: http://localhost:8080 (docker dev), or production (see DOCKER.md)
```

with:

```
Test environment: the docker dev stack — http://neoori.localhost:8080 (the landing), http://cv.neoori.localhost:8080 and http://voyage.neoori.localhost:8080, in Chrome (§ 14) — or production (see DOCKER.md). A row that names a bare path such as `/analyse/nouveau` works from any of them: the app sends each path to the host that serves it.
```

Replace `here goes through nginx, http://localhost:8080.` with
`here goes through nginx (§ 14 lists the dev addresses).`

In row 8.2.5, replace `` replace `access_token_cookie` with an expired token `` with
`` replace `neoori_access` with an expired token ``.

Before `## What to report back`, add:

```markdown
## 14 · Sous-domaines

One app on three hosts (CLAUDE.md, « Sous-domaines »). Locally:
`neoori.localhost:8080` (the landing), `cv.neoori.localhost:8080`,
`voyage.neoori.localhost:8080`, in Chrome. Start signed out.

| # | Do | Expect |
|---|---|---|
| 14.1 | Open `http://neoori.localhost:8080` | The landing; the address stays `neoori.localhost:8080` |
| 14.2 | Click « Lancer mon analyse »; go back; click « Commencer le voyage » | The form at `cv.neoori.localhost:8080/analyse/nouveau`; then signup at `voyage.neoori.localhost:8080/inscription?redirect=%2Fvoyage` |
| 14.3 | Open `http://neoori.localhost:8080/verifier-email?token=abc#x` | `cv.neoori.localhost:8080/verifier-email?token=abc#x` — path, query and fragment kept; the page says the link is not valid |
| 14.4 | Open `http://cv.neoori.localhost:8080/`, then `http://voyage.neoori.localhost:8080/` | The form; then signup, with the voyage hub as `redirect` |
| 14.5 | Sign in on `cv.…/connexion`, then open `voyage.…/voyage` | The hub, signed in, no second sign-in |
| 14.6 | On voyage, app bar menu → « Déconnexion »; then reload a cv tab on `/espace` | Logout lands on the landing at `neoori.localhost:8080`; the cv tab goes to `/connexion` |
| 14.7 | Signed out, on `voyage.…/connexion`: « Recevoir un lien de connexion » with any address; then `docker compose logs backend --since 2m` | The link printed starts `http://voyage.neoori.localhost:8080/connexion/lien?token=` |
| 14.8 | The same from `cv.…/connexion`, and « Mot de passe oublié » for an existing account on voyage | Each link names the host it was asked from |
| 14.9 | Signed out on cv: fill the form, « Avec mon compte », sign up, open the confirmation link from the backend log | Back on the form on cv with the draft (four doors' hold stays on cv) |
| 14.10 | Signed in as a candidate: app bar « Mon voyage » on cv; « Nouvelle analyse » on voyage; the voyage strip on `/espace`; the form's « voyage » link | Each crosses to the other host, still signed in |
| 14.11 | Signed out, open `voyage.…/connexion?redirect=%2Fespace` and sign in | `cv.neoori.localhost:8080/espace`, signed in |
| 14.12 | A candidate signs in on `voyage.…/connexion` with no `redirect` | The voyage hub, not `/espace` |
| 14.13 | `curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: voyage.neoori.localhost' http://127.0.0.1:8080/icon.svg` | `200`: files are served on every host |
| 14.14 | `docker compose exec frontend wget -qO- http://127.0.0.1:3001/ \| head -c 60` | The landing's HTML: an unknown host is the root |
| 14.15 | `docker compose logs nginx --since 5m \| tail -3` | Each access line carries the host after the time |

After the deploy, on production:

| # | Do | Expect |
|---|---|---|
| 14.16 | `curl -sI https://neoori.tech https://cv.neoori.tech https://voyage.neoori.tech https://www.neoori.tech \| grep -iE '^(HTTP\|location)'` | `200`; `307` → `/analyse/nouveau`; `307` → `/voyage`; `301` → `https://neoori.tech/` |
| 14.17 | `curl -sI --resolve x.neoori.tech:443:186.240.157.26 https://x.neoori.tech` | Fails at the TLS handshake: an unknown name is refused |
| 14.18 | One real sign-in on each subdomain (the email link) | Signed in; the mail's link names the host it was asked from |
```

- [ ] **Step 4: The other three files**

In `AUTOMATION-PLAN.md`, replace:

```
- `staging.neoori.tech`, added to the existing certificate, own nginx server block
```

with:

```
- A domain of its own — **not** a subdomain of neoori.tech: since the
  subdomain split, the session cookies span every host of the domain, and a
  staging stack running unreviewed branches would receive every visitor's
  production session (CLAUDE.md, « Sous-domaines »). Its own certificate and
  nginx server block
```

and replace `` `staging.neoori.tech`, basic auth, test-mode Stripe, email off. PMs get the link. `` with
`` a staging domain of its own, basic auth, test-mode Stripe, email off. PMs get the link. ``

In `handoff.md`, replace
`` - Dev (docker): `http://localhost:8080` — nginx routes `/` → Next.js, `/api/*` → Flask `` with
`` - Dev (docker): `http://neoori.localhost:8080` (the landing), `http://cv.neoori.localhost:8080`, `http://voyage.neoori.localhost:8080`, in Chrome — nginx routes `/` → Next.js, `/api/*` → Flask ``.

In `frontend/README.md`, replace
`docker compose up -d          # http://localhost:8080` with
`docker compose up -d          # http://neoori.localhost:8080 (+ cv. and voyage.)`.

- [ ] **Step 5: Check the docs name nothing retired**

```bash
grep -n "APP_URL\|FRONTEND_URL\|SITE_URL\|access_token_cookie\|localhost:8080\b" CLAUDE.md DOCKER.md TEST-PLAN.md handoff.md frontend/README.md | grep -v "neoori.localhost:8080\|127.0.0.1:8080"
```

Expected: only deliberate mentions — DOCKER.md's rollback paragraph and
« Adding cv. and voyage. » (`APP_URL`, `FRONTEND_URL`, `SITE_URL`), the lines
saying plain `localhost:8080` still shows the landing, and TEST-PLAN's curl
rows on `http://localhost:8080/api/...` (the API answers on any dev name).
Then confirm the four « Portrait out of scope » lines are untouched:

```bash
git diff initial -- README.md plan.md | head -1 ; git diff -U0 initial -- CLAUDE.md | grep -n "Portrait"
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md DOCKER.md TEST-PLAN.md AUTOMATION-PLAN.md handoff.md frontend/README.md
git commit -m "$(cat <<'EOF'
docs: the three hosts, DOMAIN as the one setting, the certificate, the swap runbook

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: Final verification and handoff

**Files:** none changed (unless a check fails: fix in the task it belongs to, with its own commit).

**Interfaces:** consumes everything above.

- [ ] **Step 1: Both test suites**

Run: `cd backend && $PY -m pytest -q` → 1891 passed (1813 at baseline + 78).
Run: `cd frontend && npm test && npx tsc --noEmit && npm run lint && npm run build`
→ 14 tests pass; tsc silent; lint 11 problems (4 errors, 7 warnings); build
succeeds with every route `ƒ`.

- [ ] **Step 2: The production image reads `DOMAIN` at runtime**

Decision 21 rests on this: a standalone build must read `DOMAIN` when it
starts, not when it was built.

```bash
docker build -t neoori-frontend:split-check frontend
docker run -d --name split-check -p 127.0.0.1:3999:3000 \
  -e DOMAIN=neoori.localhost -e PUBLIC_SCHEME=http -e PUBLIC_PORT=8080 neoori-frontend:split-check
sleep 5
H() { printf '%-26s %-28s -> ' "$1" "$2"; curl -s -o /dev/null -D - -H "Host: $1" "http://127.0.0.1:3999$2" | tr -d '\r' | awk 'NR==1{printf "%s ", $2} tolower($1)=="location:"{printf "%s", $2} END{print ""}'; }
H neoori.localhost /
H neoori.localhost '/espace?garder=1'
H cv.neoori.localhost /
H voyage.neoori.localhost /voyage/session/2
H voyage.neoori.localhost /espace
curl -s -o /dev/null -w 'health check: %{http_code}\n' http://127.0.0.1:3999/
docker rm -f split-check
docker run -d --name split-check -p 127.0.0.1:3999:3000 -e DOMAIN=example.test neoori-frontend:split-check
sleep 5
H example.test /espace
docker rm -f split-check
```

Expected:

```
neoori.localhost           /                            -> 200
neoori.localhost           /espace?garder=1             -> 307 http://cv.neoori.localhost:8080/espace?garder=1
cv.neoori.localhost        /                            -> 307 /analyse/nouveau
voyage.neoori.localhost    /voyage/session/2            -> 307 /connexion?redirect=%2Fvoyage%2Fsession%2F2
voyage.neoori.localhost    /espace                      -> 307 http://cv.neoori.localhost:8080/espace
health check: 200
example.test               /espace                      -> 307 https://cv.example.test/espace
```

(The same image, restarted with another `DOMAIN`, names the new domain: no
rebuild.) If a cross-host `Location` reads `localhost` instead, the build
inlined `process.env` somewhere: stop and report, do not ship.

- [ ] **Step 3: The dev stack through nginx**

```bash
docker compose up -d --force-recreate --renew-anon-volumes backend frontend nginx
sleep 30
H() { printf '%-26s %-28s -> ' "$1" "$2"; curl -s -o /dev/null -D - -H "Host: $1" "http://127.0.0.1:8080$2" | tr -d '\r' | awk 'NR==1{printf "%s ", $2} tolower($1)=="location:"{printf "%s", $2} END{print ""}'; }
H neoori.localhost /
H neoori.localhost '/verifier-email?token=abc'
H cv.neoori.localhost /
H voyage.neoori.localhost /
H voyage.neoori.localhost /voyage
H cv.neoori.localhost /voyage/session/2
H voyage.neoori.localhost /espace
H cv.neoori.localhost /icon.svg
H localhost /
curl -s -X POST -H 'Host: voyage.neoori.localhost' -H 'Content-Type: application/json' \
  -d '{"email":"split-check@test.fr"}' http://127.0.0.1:8080/api/auth/email-link ; echo
sleep 1; docker compose logs backend --since 1m | grep -o 'http://[a-z.]*:8080/connexion/lien' | tail -1
docker compose logs nginx --since 1m | tail -2
```

Expected:

```
neoori.localhost           /                            -> 200
neoori.localhost           /verifier-email?token=abc    -> 307 http://cv.neoori.localhost:8080/verifier-email?token=abc
cv.neoori.localhost        /                            -> 307 /analyse/nouveau
voyage.neoori.localhost    /                            -> 307 /voyage
voyage.neoori.localhost    /voyage                      -> 307 /inscription?redirect=%2Fvoyage
cv.neoori.localhost        /voyage/session/2            -> 307 http://voyage.neoori.localhost:8080/voyage/session/2
voyage.neoori.localhost    /espace                      -> 307 http://cv.neoori.localhost:8080/espace
cv.neoori.localhost        /icon.svg                    -> 200
localhost                  /                            -> 200
(a JSON body with "mail_sent": true)
http://voyage.neoori.localhost:8080/connexion/lien
```

(The first request after the restart compiles the page in dev: if a line
reads `000`, run it again.)

and the two nginx lines carry the host after the time.

- [ ] **Step 4: The browser walk**

Walk TEST-PLAN.md § 14, rows 14.1–14.15, in Chrome on the dev stack (with
browser automation if it is available to you; otherwise list these rows as
« not walked » in the report for the developer). Record each row's result.
Then leave the dev stack running this branch, and say so in the report.

- [ ] **Step 5: Report to the developer**

Report: the branch `feat/subdomain-split` and its commits; both test counts;
the walk's results; the spec amendments (spec, « Amendments while
planning »); and the rollout, **each step waiting for their go**:

1. DNS: A records `cv` and `voyage` → 186.240.157.26 (no AAAA).
2. Certificate: expand to the four names, `--dry-run` first (DOCKER.md,
   « Adding cv. and voyage. »), then reload nginx. The live site keeps
   working throughout.
3. Provider consoles: nothing today — prod has no Google/Microsoft keys. When
   they are created, register the two callbacks per provider.
4. Merge into `initial` and push — that deploys. Everyone is signed out once;
   the root keeps only the landing; old links land on the right host.
5. Afterwards, once no rollback below the split is expected: delete
   `APP_URL` and `FRONTEND_URL` from `/srv/neoori/.env`, and the GitHub
   variable `SITE_URL`.

Also flag: open item 1 (how the outcome will be read — today only the host in
the access log); `AUTOMATION-PLAN.md`'s staging now needs a domain of its own.
