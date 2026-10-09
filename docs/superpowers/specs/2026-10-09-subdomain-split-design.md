# Le découpage en sous-domaines — Design Spec
Date: 2026-10-09
Status: design approved in conversation 2026-10-09, one section at a time;
written spec approved by the developer the same day (no changes asked).
Decisions made while writing, which the conversation did not cover, are
marked **Claude's call** and listed again at the end. Refinements found while
writing the plan are folded in and listed under « Amendments while planning ».

## Overview

neoori moves from one address to three:

| Host | What it is | Day one |
|---|---|---|
| `DOMAIN` (today `neoori.tech`) | today's landing, nothing else | the landing; every other path redirects |
| `cv.DOMAIN` | « J'ai une cible », the CV analysis | `/` opens the analysis form |
| `voyage.DOMAIN` | le voyage | `/` opens the voyage hub |

Still one Next.js app, one backend, one database, one account, and one login
that works on every host. The base domain is written in exactly one setting,
`DOMAIN`, read when the containers start, so changing it needs no rebuild.

This is sub-project 3 of 3 (2026-10-08 app split):

1. Retire parcours 2 and 3 — merged and deployed.
2. Four doors at submit — `docs/superpowers/specs/2026-10-08-four-doors-design.md`,
   merged and deployed (0825e27).
3. **This spec.**

**Base.** Written against `initial` at fd2f47f plus the four-doors spec and
plan; four doors then merged (0825e27), this branch was rebased on it, and the
plan (`docs/superpowers/plans/2026-10-09-subdomain-split.md`) reads its line
numbers from that code. Four doors changed `proxy.ts`, the mails and the
report pages, and added `/rapport`, `/analyse/envoyee`,
`/conseiller/analyses/[id]` and the `neoori_hold` cookie.

**Not in this spec:** the two landings (designed later — each one replaces its
subdomain's day-one redirect), and keeping old links alive when the domain is
swapped some day (see « Out of scope »).

## What the code does today (initial fd2f47f)

- **Every cookie belongs to one host.** The session uses flask-jwt-extended's
  defaults: `access_token_cookie` and `refresh_token_cookie`, no
  `JWT_COOKIE_DOMAIN` (`config.py:25-31`). The Google/Microsoft state lives
  in Flask's session cookie, `Path=/api/auth` (`config.py:54-58`). The signup
  ticket is host-only too (`services/sign_in.py:32-33`), and four doors adds
  `neoori_hold` (`Path=/api`). A session opened on `cv.` would not exist on
  `voyage.`.
- **`APP_URL`** (`config.py:40`) builds every mail link
  (`services/email_service.py:20-21`, eight call sites) and the
  Google/Microsoft callback URL (`routes/auth_oauth.py:135-137`).
- **Stripe's return URLs** take the first entry of `FRONTEND_URL`
  (`routes/payments.py:55-58`), which is also the CORS allow-list
  (`config.py:59-62`, `app/__init__.py:148, 195`).
- **A provider sign-in started on a second host fails**: `/start` writes the
  state cookie on that host, the provider sends the browser back to
  `APP_URL`'s host, the cookie is not there, and the callback answers
  « echec ».
- **`next` / `redirect` accept local paths only** (`utils/auth_links.safe_next`,
  `lib/safe-redirect.ts`). That stays exactly as it is.
- **The domain is written in five places**: `DOMAIN` (nginx), `APP_URL`,
  `FRONTEND_URL`, `MAIL_FROM`, and the GitHub variable `SITE_URL`, baked into
  the frontend image as `NEXT_PUBLIC_SITE_URL` (`frontend/Dockerfile:13-15`,
  `.github/workflows/deploy.yml:54`, `app/layout.tsx:27-32, 49`). The frontend
  has no hardcoded domain and the database stores none.
- **nginx** (https template) answers `DOMAIN` in its app block. An unknown
  name on 443 falls into the www block, on 80 into the redirect block. The
  http template and `dev.conf` catch every name.
- **The frontend container gets no runtime environment**
  (`docker-compose.prod.yml`).
- **Same-host redirects from `proxy.ts` carry a relative `Location`** — checked
  on the dev stack: `location: /connexion?redirect=%2Fespace`.
- **Nothing records which host a request came from**: no analytics, and the
  access-log format four doors introduces (`neoori_paths`) leaves the host out.
- **Spike** (2026-10-09, Chrome 154, throwaway): a cookie set with
  `Domain=neoori.localhost` on `cv.neoori.localhost` is sent to
  `voyage.neoori.localhost`, and one set on `neoori.localhost` reaches `cv.`;
  a cookie with `Domain=localhost` is refused.

## Decisions

### Rulings (developer)

1. **Two subdomains**, `cv.<domain>` and `voyage.<domain>`; the base domain may
   change at any time, so it is one setting. (2026-10-08)
2. **Each subdomain gets its own landing**, presenting its product as a
   separate app — designed later. (2026-10-08)
3. **One database, one backend, one account.** (Leaning on 2026-10-08,
   confirmed 2026-10-09.)
4. **One login for both subdomains.** Rejected: separate logins on the same
   account — a person going from the voyage to the analysis, and every
   counselor, would be asked to sign in again.
5. **The root shows today's landing and nothing else**; every other path
   redirects to the subdomain that owns it. Rejected: keeping the whole app on
   the root too — every page at three addresses, and the split's outcome harder
   to read.
6. **Until its landing is designed, each subdomain's `/` goes straight into its
   product.** Rejected: a cut of today's landing (work the real landing
   replaces); waiting for the landings (the plumbing sits unmerged).
7. **Cross-links stay**, now pointing to the other subdomain: the app bar's
   « Mon voyage » and « Nouvelle analyse », the voyage strip on `/espace`, the
   form's mention of the voyage, the voyage pages' way back to `/espace`.
   Rejected: each app shows only itself; a menu link only.
8. **Approach A: one Next.js app that knows which host it serves.** Rejected:
   two Next.js apps (two builds and two containers on a 2-vCPU VPS, shared
   pages duplicated); a split done in nginx alone (rules nobody can unit-test,
   in three files, while the app needs to know its host anyway).
9. **Sections 1–6 of the design** (decisions 10–38 below, except those marked
   Claude's call) were approved one by one on 2026-10-09.

### Who serves what

10. **Every page path has an owner:**

    | Owner | Paths |
    |---|---|
    | cv | `/analyse`, `/analyse/*`, `/rapport`, `/espace` |
    | voyage | `/voyage`, `/voyage/*` |
    | shared | `/connexion*`, `/inscription*`, `/mot-de-passe-oublie`, `/reinitialiser-mot-de-passe`, `/verifier-email`, `/inscription-conseiller`, `/profil`, `/conseiller`, `/conseiller/*`, `/admin`, `/admin/*`, `/cgv`, `/confidentialite`, `/mentions-legales` |
    | root | `/` |

    *Claude's call:* prefixes match on a segment boundary (`/voyage/…`, never
    `/voyageur`), and a path in no row — a 404 — counts as shared.
11. **A page path asked on the wrong host is redirected to its owner**, keeping
    the path and the query; the browser keeps any `#fragment` by itself, which
    is where four doors keeps a no-login report's key. On the root, every path
    except `/` (and files, decision 17) goes to its owner; shared and unlisted
    paths go to **cv, the default host**. Shared paths are served wherever they are asked on cv and
    voyage.
12. *Claude's call — refines Section 1, which said 308.* **Host redirects are
    temporary (307).** Browsers cache a permanent redirect with no expiry, and
    the root's role is provisional by ruling 5 (« until the outcome is
    seen »): a cached 308 would keep sending returning visitors to cv after the
    root changes. It costs nothing — the redirect only runs for old links and
    bookmarks.
13. **Day one:** `cv./` redirects to `/analyse/nouveau`, `voyage./` to
    `/voyage` (307). A designed landing later takes over its subdomain's `/`
    through an internal rewrite, so the address stays `cv.DOMAIN/`.
14. **Signed out on the voyage hub** (`/voyage`, exact path) → `/inscription`,
    with the hub as `redirect`, as the analysis form did before four doors: new
    people arrive there. Deeper voyage pages keep sending to `/connexion`.
15. **Home per host**: a candidate's home is `/espace` on cv and `/voyage` on
    voyage; a counselor's is `/conseiller`, an admin's `/admin`, on whichever
    host they are. It drives the app bar's logo, where sign-in lands without a
    `redirect` (frontend `homeFor`), and where a Google/Microsoft sign-in lands
    (backend `_home_path`). The two keep saying the same thing, as today.
16. *Claude's call.* **In links, `/` and `/#anchor` mean the root landing**: the
    marketing nav and footer anchors, the auth pages' logo, where logout lands.
    A visitor reaches `cv./` or `voyage./` only by typing it.
17. *Claude's call.* **Files and Next's own assets are served on every host.**
    `proxy.ts` already skips `_next/static`, `_next/image`, `favicon.ico` and
    `.png`; any other path whose last segment has an extension (svg, jpg, webp,
    ico, txt) passes through without host routing. *Amended while planning:*
    so do `/api` and `/api/*` (nginx sends them to Flask before Next sees
    them, but a direct request to the frontend's port must not be redirected)
    and Next's internal paths, `/_next/*` and `/__nextjs*` (the dev server's
    hot-reload socket, on every host).
18. **An unknown host is treated as the root**: `/` serves the landing there,
    instead of the host being redirected to `DOMAIN`. That covers the container
    health check (`wget http://127.0.0.1:3000/`), access by IP in the http
    phase, and plain `localhost:8080` in dev. In production nginx keeps unknown
    names away from the app (decision 33).

### The one setting

19. **`DOMAIN`** — already in `/srv/neoori/.env`, where nginx reads it — is the
    only place the domain is written. The three origins are built from it:
    `{scheme}://{DOMAIN}{port}`, `{scheme}://cv.{DOMAIN}{port}`,
    `{scheme}://voyage.{DOMAIN}{port}`.
20. **`PUBLIC_SCHEME`** (default `https`) and **`PUBLIC_PORT`** (default empty)
    exist for dev only (`http`, `8080`). Production never sets them.
21. **Read at runtime by both containers.** The backend already loads
    `.env`. The frontend gets `DOMAIN`, `PUBLIC_SCHEME` and `PUBLIC_PORT` through
    `environment:` in both compose files. A domain change is an `.env` edit
    and `up -d`.
22. **Removed:** `APP_URL` and `FRONTEND_URL` (code, `.env.example`,
    `backend/.env.example`, dev compose); the `NEXT_PUBLIC_SITE_URL` build-arg
    and its `Dockerfile` lines; the GitHub variable `SITE_URL`, deleted after the
    deploy. Left in the prod `.env`, `APP_URL` and `FRONTEND_URL` are ignored;
    the runbook deletes them.
23. **`MAIL_FROM` stays its own setting, on purpose.** Resend refuses a sender
    on a domain it has not verified, and a refused mail fails silently
    (fail-soft by design). Derived from `DOMAIN`, a domain swap would quietly
    stop every mail — signup confirmations included, so nobody could sign up.
    Swap order: verify the new domain in Resend, then change `MAIL_FROM`; until
    then mails leave from the old address and link to the new domain.
24. **Page metadata is built per request from the host**: `metadataBase` and
    `og:url` are the origin, built from `DOMAIN`, of the app the host maps to
    (decision 18 for an unknown host) — never the raw Host header. Each
    subdomain's social preview names itself. Every page is then rendered per
    request instead of at build time — negligible at this traffic.

### Sign-in and cookies

25. **The session cookies cover the whole domain and get new names**:
    `Domain=DOMAIN`, `neoori_access` and `neoori_refresh`
    (`JWT_ACCESS_COOKIE_NAME`, `JWT_REFRESH_COOKIE_NAME`, `JWT_COOKIE_DOMAIN`).
    Logout clears them the same way, so it signs out of every host. Why the
    rename: today's cookies belong to the root alone; under the same names the
    root would receive an old and a new cookie for one name, and Flask would
    read whichever comes first — on a shared computer, possibly someone else's
    old session. Under new names the old cookies are never read and end with
    the browser session. `proxy.ts` checks the new name. **Everyone signs in
    once more after the deploy** — on `cv.` and `voyage.` they would have to
    anyway, since their old cookie exists only on the root.
26. *Claude's call.* **A single-label `DOMAIN` (`localhost`) gets host-only
    cookies**: browsers refuse `Domain=localhost` (spike), so the attribute
    would only lose the cookie. The test suite runs on that path unless a test
    sets a dotted `DOMAIN`.
27. **Three cookies stay on one host**, because each round trip starts and ends
    on the same host: the Google/Microsoft state (Flask session), the signup
    ticket, and four doors' `neoori_hold` (cv only).
28. **The Google/Microsoft callback is on the host the sign-in started on**:
    `https://cv.DOMAIN/api/auth/<provider>/callback` or the `voyage.`
    equivalent, both registered in both provider consoles. `/start` reached on
    any other host (only by typing the URL — the root has no sign-in page) is
    redirected to cv's `/start` with the same query before any state is
    written. The target is built from the settings, never from the Host header.
29. **`next` / `redirect` do not change**: local paths only, same checks. When
    sign-in returns to a path the other app owns, the frontend goes there with a
    full page load (decision 37's `go`), decision 11 hands it to the owner, and
    the shared cookie means the person is already signed in.
30. **Standing rule: no subdomain of `DOMAIN` may be served by anything but this
    stack** — no blog, status page, Resend click-tracking domain, or any CNAME to
    an outside service. *Amended while planning:* nor a staging copy of the
    app, which would run unreviewed branches with every visitor's production
    session in hand; `AUTOMATION-PLAN.md` proposes `staging.neoori.tech` and
    gets a note to use a separate domain. Such a host would receive the session cookie, and since
    `cv.` and `voyage.` count as the same site to a browser, `SameSite=Lax`
    would not stop it from sending signed-in requests either (CSRF protection is
    off: `config.py:31`). Written into CLAUDE.md and DOCKER.md beside the AAAA
    rule.

### Mails, Stripe, CORS

31. **Where each mail links:**

    | Mail | Link host |
    |---|---|
    | Confirmez votre adresse (signup, conseiller demande, resend) | the requesting host |
    | Réinitialiser votre mot de passe | the requesting host |
    | Votre lien de connexion | the requesting host |
    | Votre mot de passe a été modifié | the requesting host |
    | Votre analyse est prête / n'a pas abouti | cv (`/espace`) |
    | Nouvelle demande de compte conseiller | cv (`/admin/conseillers`) |
    | Compte activé, and four doors' counselor mails | cv (`/conseiller`) |
    | Demande non retenue / accès retiré | no link, as today |

    « The requesting host » is the request's host name matched against
    `cv.DOMAIN` and `voyage.DOMAIN`. Anything else — the root, an unknown or
    forged name, no request at all (a background run, a CLI command) — means
    cv. The Host header is never copied into a mail, which is what makes the
    classic poisoned reset link impossible.
32. **Stripe** returns to `https://cv.DOMAIN/analyse/<id>/debloquer…`. The
    webhook (`/api/payments/webhook`) answers on every host, so the URL in
    Stripe's dashboard keeps working unchanged. **CORS** allows the three
    origins; browser calls stay same-origin (each host serves its own `/api`),
    so the list is a backstop.

### nginx, certificate, DNS

33. **https template:** the app block answers `DOMAIN`, `cv.DOMAIN` and
    `voyage.DOMAIN`, proxied identically — the app decides. The port-80 block
    (ACME, redirect to https) names all four hosts. New default servers turn
    away every other name: on 80, `return 444` (closes the connection); on 443,
    `ssl_reject_handshake on` (refuses the TLS handshake, no certificate
    needed). The rate-limit zones are untouched: they key on the visitor's
    address and are shared across hosts. *Amended while planning (Claude's
    call):* the port-80 default server still answers the ACME challenge, for
    any name, and closes the connection for everything else. Without that, a
    certificate for a new domain could not be issued before `DOMAIN` changes
    (« Swapping the domain later », step 2). It serves only the files certbot
    itself writes, so a stranger pointing a name at the VPS gains nothing.
34. *Claude's call.* **The http template and `dev.conf` keep their catch-all**:
    the http phase exists for IP smoke tests, and dev is reached by
    `localhost:8080` too. The app's own host check (decisions 18, 31) covers
    them.
35. **One certificate for the four names** (root, www, cv, voyage), expanded
    once with `certbot certonly --expand`. The certificate keeps its name, so
    the paths in the template and the 12-hour renew loop do not change. It is
    expanded **before** the deploy, or `cv.` and `voyage.` would show a
    certificate warning.
36. **DNS:** two A records, `cv` and `voyage`, to the VPS. No AAAA record, for
    the reason DOCKER.md already gives (« Do not publish an AAAA record »).

### The frontend's host helpers

37. **`lib/site.ts`** holds the ownership table and decisions 10–18 as plain
    functions with no Next.js import, so a Node test can load it: which app a
    host is, which app owns a path, what a request gets (serve, or redirect
    to an absolute URL), and `homeFor(role, app)`. `proxy.ts` asks it first,
    then runs the existing sign-in gate. The root layout reads `DOMAIN` and the
    host at request time and hands them to a small client context, which gives
    components `href(path)` — absolute when another host owns the path — and
    `go(path)` — the router for this host, a full page load otherwise. An
    `AppLink` component renders `next/link` or a plain `<a>` accordingly. Every
    link and post-sign-in navigation listed in « Frontend » uses them.
    *Amended while planning:* `AppLink` always renders `next/link` with the
    resolved href — `next/link` already hands an other-origin href to the
    browser, a full page load that is never prefetched
    (`next/dist/client/app-dir/link.js`, `linkClicked`) — and it is a client
    component, so the server-rendered footer, auth layout and landing can use
    it. `homeFor` stays in `lib/home.ts`. The proxy's sign-in gate moves,
    unchanged except for decision 14, into `lib/sign-in-gate.ts`, a pure
    function the same tests load.

### Measuring the outcome

38. *Claude's call.* **The access log carries the host**: `$host` joins four
    doors' `neoori_paths` format, so requests per host can be counted from the
    logs. Nothing else is recorded here; how the outcome will be read is open
    item 1.

## How a page request is routed

```
proxy(request)
  path is a file or a Next asset            → serve (every host)
  app = cv | voyage | root   (from the host name; unknown → root)
  root:   path == "/"                       → serve the landing
          otherwise                         → 307 to owner origin + path + query
                                              (shared or unlisted → cv)
  cv:     path == "/"                       → 307 /analyse/nouveau
          owner == voyage                   → 307 voyage origin + path + query
  voyage: path == "/"                       → 307 /voyage
          owner == cv                       → 307 cv origin + path + query
  then the sign-in gate, as today (four doors' public paths; signup-first
  for the voyage hub; presence of neoori_access)
```

Absolute URLs come from the settings, never from the request's Host; same-host
redirects stay relative, as Next writes them today.

## Backend

| File | Change |
|---|---|
| `app/config.py` | Add `DOMAIN`, `PUBLIC_SCHEME`, `PUBLIC_PORT`, `JWT_ACCESS_COOKIE_NAME = "neoori_access"`, `JWT_REFRESH_COOKIE_NAME = "neoori_refresh"`. Remove `APP_URL` and `FRONTEND_ORIGINS`. `TestingConfig` uses `DOMAIN = "localhost"` (host-only cookies, decision 26). |
| `app/utils/site.py` (new) | `origin(app)`, `request_app()` (host name → `"cv"`, `"voyage"`, `"root"` or `None`, port ignored), `request_origin()` (decision 31's fallback to cv), `cookie_domain()` (`None` for a single-label `DOMAIN`). Reads `current_app.config` on each call, so a test can change `DOMAIN`. |
| `app/__init__.py` | CORS origins and `_cors_error_response` take `site` origins; `JWT_COOKIE_DOMAIN` set from `site.cookie_domain()` after the config loads. |
| `routes/auth_oauth.py` | `_redirect_uri` from `site.request_origin()`; `/start` on a host other than cv or voyage redirects to cv's `/start` (decision 28); `_home_path(role)` gives `/voyage` to a candidate on voyage. |
| `services/email_service.py` | `_app_url()` goes; each mail names its origin per decision 31 (`site.request_origin()` or `site.origin("cv")`), including the counselor mails four doors adds. |
| `routes/payments.py` | `_frontend_base()` becomes `site.origin("cv")`. |
| Tests | The ~25 assertions on `access_token_cookie` / `refresh_token_cookie` move to the new names; the seven fixtures that set `APP_URL` set `DOMAIN` instead. New tests below. |

## Frontend

| File | Change |
|---|---|
| `src/lib/site.ts` (new) | Decision 37's pure functions. |
| `src/lib/sign-in-gate.ts` (new) | The proxy's sign-in gate as a pure function; `/voyage` exact joins signup-first. |
| `src/lib/site.test.ts`, `src/lib/home.test.ts` (new) | Node's built-in runner (`node --test`, no new package); `package.json` gets a `test` script, `tsconfig.json` `allowImportingTsExtensions` (the tests import `./site.ts`). |
| `src/lib/site-context.tsx` (new) | The client context: `useSite()`, `href`, `go`; `AppLink`. |
| `src/lib/site-server.ts` (new) | `currentSite()`: runtime `DOMAIN` + the request's host, for the root layout. |
| `src/proxy.ts` | Decision 37: `route()` first, then the sign-in gate on `neoori_access`. |
| `src/app/layout.tsx` | `generateMetadata()` from runtime `DOMAIN` + host; wraps children in the site context. `NEXT_PUBLIC_SITE_URL` goes. |
| `src/lib/home.ts` | `homeFor(role, app)`; every caller passes the app. |
| `components/layout/AppBar.tsx`, `SiteNav.tsx`, `SiteFooter.tsx`, `AuthLayout.tsx` | Links through `AppLink`; landing anchors and the logo go to the root (decision 16). |
| `app/page.tsx` (the root landing) | CTAs go straight to `cv.` / `voyage.` (`/analyse`, `/voyage`), anchors stay local. |
| `app/espace/page.tsx`, `app/analyse/nouveau/page.tsx`, `app/voyage/c/[token]/page.tsx`, `app/admin/layout.tsx` (logout, « Retour à mon espace »), `app/analyse/envoyee/page.tsx` and `app/c/[token]/page.tsx` (« Retour à l'accueil ») | Cross-links through `AppLink` / `go`. `app/conseiller/page.tsx` and four doors' counselor page link only to shared paths: unchanged (checked while planning). |
| `app/(auth)/connexion`, `connexion/lien`, `inscription/finaliser`, `verifier-email`, `reinitialiser-mot-de-passe` | Post-sign-in navigation through `go()`, so a `next` owned by the other app is a full page load. |
| `next.config.ts` | `allowedDevOrigins` from `DOMAIN`: Next 16 refuses its dev resources (the hot-reload socket) to an origin it does not know, and its default `*.localhost` covers one label, not `cv.neoori.localhost`. |

Share links built from `window.location.origin` (the voyage's counselor link,
four doors' « Copier le lien ») already name the right host: they are built on
the page that owns them.

## Infra

| File | Change |
|---|---|
| `nginx/templates-https/default.conf.template` | Decision 33; `$host` in the log format (decision 38). |
| `nginx/dev.conf`, `nginx/templates-http/default.conf.template` | Catch-all kept (decision 34); `$host` in the log format; comments name the dev hosts. |
| `docker-compose.yml` | Backend and frontend get `DOMAIN=neoori.localhost`, `PUBLIC_SCHEME=http`, `PUBLIC_PORT=8080`; `APP_URL` and `FRONTEND_URL` go; the header comment names the three dev addresses. |
| `docker-compose.prod.yml` | Frontend gets `environment: DOMAIN: ${DOMAIN}`. |
| `frontend/Dockerfile`, `.github/workflows/deploy.yml` | The `NEXT_PUBLIC_SITE_URL` build-arg goes. |
| `.env.example`, `backend/.env.example` | `DOMAIN` documented as the one setting, `PUBLIC_*` as dev-only, `MAIL_FROM` as deliberately separate (decision 23); `APP_URL` and `FRONTEND_URL` go. |

## Errors and edge cases

- **Links already sent** (`neoori.tech/verifier-email?token=…`,
  `/reinitialiser-mot-de-passe?token=…`, `/connexion/lien?token=…`, `/espace`,
  a four-doors `/rapport#…`): the root redirects them to cv with the query; the
  fragment rides along; the tokens are stateless or single-use as today.
- **Signed in before the deploy**: the old cookies are never read; the person
  signs in once.
- **Shared computer**: one session for the whole domain, so signing out on one
  host signs out of all — intended.
- **A sign-in round trip cannot change host**: the callback is registered for
  the host that started it, and the state cookie lives there.
- **An email sign-in link opened in another browser** behaves as today; the
  link names the host it was asked from.
- **A mail sent without a request** (a background run, `flask purge-expired`,
  an admin script) links to cv.
- **Four doors' hold round trip** stays on cv from start to claim; « Garder »
  returns to `/espace?garder=1`, which cv owns.
- **A Next client-side navigation to another host's path that bypassed
  `AppLink`**: the proxy answers a cross-origin 307 to a router fetch. Checked
  in Next 16.2.6's source while planning
  (`next/dist/client/components/router-reducer/fetch-server-response.js`):
  the fetch fails the cross-origin check and the router falls back to a full
  page load of the same URL, which the proxy then redirects. Every known
  cross-link uses `AppLink` / `go`, so this is a safety net only.
- **`/api/*` on the root** still reaches Flask: the landing asks `/auth/me` for
  its nav, and the Stripe webhook URL is on the root.

## Testing

**Backend (pytest):**
- origins from `DOMAIN`, with and without `PUBLIC_SCHEME` / `PUBLIC_PORT`;
- `request_app()` for each host, a port, the root, an unknown name and a forged
  one; a forged Host never appears in any mail body;
- each mail of decision 31 links to its host, from cv, from voyage and from no
  request;
- the callback URL per host; `/start` on the root redirects to cv's `/start`,
  with the query, and sets no state;
- `_home_path` per host and role;
- Stripe's success and cancel URLs name cv;
- `Set-Cookie` on login, refresh and logout carries the new names and, with a
  dotted `DOMAIN`, `Domain=`; none with `DOMAIN=localhost`.

**Frontend (`node --test`):** `lib/site.ts` over every owner × every host:
serve, or the exact redirect target; `/`, files, unknown hosts, query strings,
segment-boundary prefixes; `homeFor` per role and app.

**Local walkthrough through nginx** on `neoori.localhost:8080`,
`cv.neoori.localhost:8080`, `voyage.neoori.localhost:8080` (Chrome):
- the root shows the landing; its buttons open cv and voyage; an old-style
  path on the root lands on the right host with path, query and `#fragment`;
- `cv./` opens the form, `voyage./` the hub (signup first when signed out);
- sign in on cv → signed in on voyage; sign out on voyage → signed out on cv;
- each account mail, printed in the backend log in dev, links to the host it
  was asked from; the analysis mail links to cv;
- four doors' account and promo doors, signed out, keep their draft through the
  sign-in round trip on cv;
- the app bar, the espace strip and the form's voyage link cross hosts and stay
  signed in;
- `docker compose exec frontend wget -qO- http://127.0.0.1:3000/` answers 200.

**After the deploy:** `curl -I` the three hosts, `www.`, and an unknown name
(refused); one real sign-in on each subdomain.

## Rollout

Each step outside the repo waits for the developer's go.

1. **DNS:** A records `cv` and `voyage` → 186.240.157.26. Wait until both
   resolve.
2. **Certificate:** expand it to the four names, then reload nginx. Today's
   port-80 block is the only server on port 80, so it already answers the ACME
   challenge for the new names. Run it once with `--dry-run` first (Let's
   Encrypt rate-limits failures); DOCKER.md carries the same command:

   ```bash
   docker compose -f docker-compose.prod.yml run --rm --entrypoint certbot certbot certonly \
     --webroot -w /var/www/certbot --cert-name neoori.tech --expand \
     -d neoori.tech -d www.neoori.tech -d cv.neoori.tech -d voyage.neoori.tech \
     --email nneoori@proton.me --agree-tos --no-eff-email
   docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
   ```

   The current site keeps working throughout.
3. **Provider consoles**, only if Google/Microsoft keys are live by then: add
   the two callback URLs for each provider. Prod has no provider keys today.
4. **Push**, which deploys. What people notice: they are signed out once; the
   root shows the landing and every other page moves to `cv.` or `voyage.`;
   links in mails already sent keep working through the redirects.
5. **Afterwards, once no rollback below this deploy is expected:** delete
   `APP_URL` and `FRONTEND_URL` from `/srv/neoori/.env`, and the GitHub
   variable `SITE_URL`.

**Rollback:** `IMAGE_TAG=<previous sha>`. The old app then answers on all three
names, each with its own sign-in, as before the split. The new nginx config
and the expanded certificate work with the old image. *Amended while
planning:* the previous image still reads `APP_URL` and `FRONTEND_URL` — the
latter for Stripe's return URL, whose fallback is `http://localhost:3000` — so
a rollback after step 5 also puts `FRONTEND_URL=https://neoori.tech` back in
`/srv/neoori/.env`.

## Swapping the domain later

Each time the base domain changes:

1. DNS for the new root, `www`, `cv` and `voyage` (A records only).
2. A certificate for the new domain, four names. The port-80 default server
   answers the ACME challenge for names nginx does not serve yet (decision 33).
3. `DOMAIN=<new>` in `/srv/neoori/.env`, then recreate the backend, frontend
   and nginx containers (`up -d --force-recreate backend frontend nginx`) —
   nginx re-renders, nothing is rebuilt.
4. Google and Microsoft: the new callback URLs.
5. Stripe: the webhook URL.
6. Resend: verify the new domain, then change `MAIL_FROM` (decision 23).

Links to the old domain stop working once its DNS moves (« Out of scope »).
DOCKER.md carries this list.

## Docs

- **CLAUDE.md:** « Live deployment » names the three hosts and `DOMAIN` as the
  one setting; the dev address becomes the three `*.neoori.localhost:8080`
  addresses; the « `NEXT_PUBLIC_*` baked at build time » gotcha goes (no such
  value is left); a short « Sous-domaines » section: the ownership table, the
  cookie names, rule 30, and that a new page needs a row in `lib/site.ts`.
- **DOCKER.md:** the TLS section with four names and the `--expand` command;
  the `SITE_URL` paragraph goes; rule 30 beside « Do not publish an AAAA
  record »; « Swapping the domain later ».
- **TEST-PLAN.md:** the walkthrough above.

## Out of scope

- The two landings, per-host titles and descriptions, `robots.txt` / sitemap.
- Shorter voyage paths (`voyage.DOMAIN/session/2` instead of
  `/voyage/session/2`). *Claude's call:* paths stay as they are — no route is
  renamed, so no link or bookmark breaks.
- Keeping old-domain links alive after a swap: it would need the old domain
  kept pointing here with a redirect server block and its own certificate.
- Turning on flask-jwt-extended's CSRF tokens, which would remove rule 30's
  dependency on `SameSite`.
- Analytics, or any record of which host a person came from beyond the log
  line (open item 1).
- Safari in dev: it does not resolve `*.localhost`; dev is checked in Chrome.
- A real Google/Microsoft sign-in in dev: the providers only promise to accept
  `http` callbacks on plain `localhost`; whether they take
  `cv.neoori.localhost` is unchecked. If they refuse, the real-provider
  walkthrough runs on the VPS, or before the split ships (the social sign-in
  checklist already plans it on `localhost:8080`); tests mock the provider, as
  today.

## Open items

1. **How will the outcome be read?** This spec puts the host in the access log
   (decision 38) and nothing more. Alternatives, each its own decision: a
   column recording which host an account, an analysis or a voyage started on
   (a small migration); an analytics tool (a consent question under CNIL rules,
   and possibly a cost).
2. ~~**Timing:** the build waits for four doors to merge.~~ Merged 2026-10-09
   (0825e27).
3. **Provider keys before the split:** if they go live first, register the
   root's callback URLs then, add cv and voyage at the split, and remove the
   root's afterwards.

## Amendments while planning (2026-10-09)

Found while reading the merged code for the plan; each is folded into the
decision it touches, and each is open to reversal:

- 17 — `/api/*` and Next's internal paths pass through on every host, like
  files.
- 30 — a staging copy of the app counts as « anything but this stack ».
- 33 — the port-80 default server answers the ACME challenge for any name
  (Claude's call), so a domain swap can issue its certificate first.
- 37 — `AppLink` always renders `next/link`; the sign-in gate becomes
  `lib/sign-in-gate.ts`; `homeFor` stays in `lib/home.ts`.
- « Errors and edge cases » — Next 16's fallback for a cross-origin redirect
  during a client navigation, checked in its source: a full page load.
- « Frontend » — the counselor pages need no change; the admin layout,
  `/analyse/envoyee` and `/c/[token]` do; `next.config.ts` gets
  `allowedDevOrigins`.
- « Rollout » — `FRONTEND_URL` stays in the prod `.env` until no rollback below
  the split is expected: the previous image builds Stripe's return URL from it.

## Claude's calls

Made while writing, not covered in the conversation; each is open to reversal:

- 10 — prefixes match on segment boundaries; a path in no row counts as shared.
- 12 — host redirects are temporary (307), refining Section 1's 308.
- 16 — `/` and `/#anchor` in links mean the root landing.
- 17 — files and Next assets are served on every host.
- 26 — a single-label `DOMAIN` gets host-only cookies.
- 34 — the http template and `dev.conf` keep their catch-all.
- 37 — the helper shapes: `lib/site.ts`, the client context, `AppLink`, `go`.
- 38 — `$host` in the access log.
- Paths stay as they are (« Out of scope »).
- Cookie names `neoori_access` / `neoori_refresh` (the rename was approved; the
  names were not discussed).
