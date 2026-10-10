# Les landings de cv. et voyage. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `cv.DOMAIN/` and `voyage.DOMAIN/` their own designed landings,
served in place by an internal rewrite, with the vector logo across the app,
logo motion, mixed 3D (a still image first, the live three.js scene on capable
desktops), the ∞ wipe into the product, per-host `robots.txt` / `sitemap.xml`,
and the "poste only" wording fixed.

**Architecture:** `lib/site.ts` gains a third answer, `rewrite`: the proxy
serves `/accueil/cv` or `/accueil/voyage` when `/` is asked on cv or voyage,
and redirects anyone who asks for `/accueil/*` directly. Each landing is a
server-rendered page assembled from small components in
`components/landing/`, with every visible string in one copy file per app. The
3D lives in a dynamically imported module; the page always renders a still
image of the same scene, and the live scene replaces it only on capable
desktops. The wipe calls the browser's View Transitions API around a router
push, so it does not depend on React's `<ViewTransition>`.

**Tech Stack:** Next.js 16.4 App Router (or 16.2.6 if Task 1 is rolled back),
React 19.3, TypeScript 5.9, Tailwind 4 plus one landing stylesheet, three.js
0.186 with @types/three 0.186, sharp 0.34 (already installed with Next),
Node's built-in test runner (`node --test`), Docker compose for the dev stack.

**Spec:** `docs/superpowers/specs/2026-10-10-subdomain-landings-design.md`
(this branch). « Decision N » and « Appendix A / B » below refer to it. Read it
first. The round-2 prototype it mentions sits beside it, in
`docs/superpowers/specs/2026-10-10-subdomain-landings/prototype/`
(`python3 build.py && cd out && python3 -m http.server`, then open
`http://127.0.0.1:8000/index-preview.html`): open it to see what the result
should look like.

**Plan-level refinements of the spec** (each one keeps the spec's intent):
- `landing.css` is imported by the route files that render landing components
  (the two landing pages and the legal layout), the documented Next.js
  pattern, rather than by the components themselves.
- The wipe's CSS lives in `app/globals.css`, so it stays loaded while the page
  changes underneath it.
- The voyage. desktop 3D is drawn in a square box above the path's far end,
  rather than a full-width canvas. The still and the live scene then share
  one framing at every screen width (decision 26's "the switch is invisible").
- Still images ship as AVIF plus WebP. The PNG masters stay out of git, and
  the `<img>` fallback is the WebP, which every supported browser reads.
- The spec's `Track` component becomes two CSS patterns (the cv. tiers and the
  voyage. path); no shared component is needed.

## Before you start (mandatory)

1. Work in the worktree
   `/Users/imran/Downloads/design_handoff_cv_analyzer/.claude/worktrees/subdomain-landings`,
   branch `feat/subdomain-landings`, which starts at the spec commit 6231578
   on top of `initial` 2b5b539. Every file and line reference below was read
   from that code on 2026-10-10. Run every command from the worktree root,
   wrapping each `cd` in parentheses — `(cd frontend && npm test)` — and never
   `cd` to the main checkout. Never run a bare `git stash`: the stash is shared
   with the main checkout and other worktrees.
2. Frontend checks. `frontend/node_modules` is installed (`npm ci` ran on
   2026-10-10; run it again if the folder is missing). Baseline on 2026-10-10:
   - `(cd frontend && npm test)` → **14 tests pass**
   - `(cd frontend && npx tsc --noEmit)` → clean
   - `(cd frontend && npm run lint)` → **11 problems (4 errors, 7 warnings)**;
     no task may add to that count
   - `(cd frontend && npm run build)` → succeeds

   Every task that touches code ends with all four green.
3. Unit tests import `.ts` files directly (Node ≥ 22.18 strips types; this
   machine has 25.8). A file that a test imports must import other project
   files **relatively, with the `.ts` extension**, for anything used at runtime
   (`import { origin } from "./site.ts"`). `import type` lines are erased and
   may use `@/`. Only erasable TypeScript is allowed in those files: no `enum`,
   no `namespace`, no constructor parameter properties.
4. Docker. Tasks 1, 2 and 5–10 use the dev stack. Its compose project is named
   `neoori`, the same as the main checkout's: `docker compose up -d` from this
   worktree **replaces** a running dev stack with this branch's code and keeps
   its database volume (this plan adds no migration). `docker compose up -d`
   from the main checkout afterwards puts it back. The dev compose file reads
   `backend/.env`, which git does not carry into a worktree; link the main
   checkout's once:
   ```bash
   ln -s /Users/imran/Downloads/design_handoff_cv_analyzer/backend/.env backend/.env
   ```
   After any change to `frontend/package.json`, rebuild the frontend image and
   renew its anonymous `node_modules` volume:
   `docker compose up -d --build -V frontend`. URLs, in Chrome (it resolves
   `*.localhost` by itself): http://neoori.localhost:8080 (root),
   http://cv.neoori.localhost:8080, http://voyage.neoori.localhost:8080.
   A `curl` check sends the host by hand:
   `curl -s -H 'Host: cv.neoori.localhost' http://127.0.0.1:8080/`.
5. Never push, deploy, or touch the VPS. The merge waits for the PM's approval
   of the sentence list and the developer's go (spec, « Rollout »).
6. The backend does not change in this plan. Its tests need not run, but Task
   6 reads `backend/app/services/section_registry.py` from a frontend test.
7. How this plan was checked (2026-10-10). Every code block was applied to a
   throwaway copy of `initial` 2b5b539, still on Next 16.2.6 (Task 1 not
   applied). Results: 42 tests pass, `tsc` clean, lint 10 problems, the build
   succeeds. The production server, bound to `0.0.0.0` like the Dockerfile,
   answers 200 on all three hosts, with each landing's headline, links, still
   and canonical; `/accueil/cv` answers 307, `/dev/stills` 404, and `robots.txt`
   differs per host. Not checked there: the 16.4 upgrade, the still rendering
   (Task 8 needs a browser), the wipe and everything you have to look at. A
   step whose output differs from its « Expected » is a finding: stop and
   report it rather than bend the code to match.

## Global Constraints

- **No humans in any form:** no photos, drawings, 3D characters, avatars,
  silhouettes or person icons. Lucide's `User*` icons count.
- **Free tools only.**
  - three.js `0.186.x` and `@types/three` `0.186.x`, served by our own server.
  - No React Three Fiber, no drei, no CDN at runtime.
  - No animation library: CSS and the browser's Web Animations API do the work.
  - `sharp` comes with Next; nothing else gets installed.
- **Copy:**
  - All visible text is French. Every landing string lives in
    `components/landing/copy/*.ts` and goes through `typeset()`.
  - None of CLAUDE.md's banned words: boussole, copilote, miroir, révélation,
    épanouissement, alignement, excellence, talent unique, vous vous démarquez.
  - The « cible » is « un métier, une formation, un poste ou un projet », never
    only a job.
  - The copy speaks to advisors and to everyone they accompany.
  - No score is promised, and nothing claims where data is processed.
- **Typography:**
  - U+00A0 before `:` and inside « »
  - U+202F before `;` `!` `?`
  - U+00A0 between a number and `€`, `Mo` or `%`
  - typographic apostrophe `’`
- **Layout:** one breakpoint, 900 px: at 900 px and below, the phone and tablet
  layout. Every landing class starts with `lp-`. Colours, type, spacing, motion
  and 3D values come from the spec's Appendix B.
- **Reduce motion** means:
  - no logo motion, no rise, no section reveal
  - no wipe, no mist drift
  - the 3D stays a still image
- **The live 3D runs only when `canRunLive3D()` is true:**
  - viewport wider than 900 px
  - no « reduce motion »
  - no `saveData`
  - effective type not `slow-2g`, `2g` or `3g`
  - `deviceMemory` at least 4, or unknown
  - `hardwareConcurrency` at least 4, or unknown
  - a WebGL 2 context can be created
- **Budgets:**
  - first visit at most 700 KB compressed, not counting the live 3D
  - landing-specific client JavaScript at most 25 KB compressed
  - AVIF stills at most 90 KB on desktop and 50 KB on phones
  - Lighthouse mobile: LCP ≤ 2.5 s, CLS ≤ 0.05, TBT ≤ 200 ms
- **Root landing:** it changes only by its four sentences (Task 12).
- **Repo hygiene:** lint stays at 11 problems or fewer; `tsc` clean;
  `npm test` and `npm run build` green.

## Review Focus

1. **A visitor whose JavaScript fails or is off** must still get the whole
   landing, server-rendered: headline, sections, still image, and main buttons
   that are plain links. Test: the `curl` checks in Task 6, Step 9 and Task 7,
   Step 5.
2. **Pressing Back after the ∞ wipe** must show the landing intact, never a
   page stuck behind a half-open circle. A wipe must never wait on a
   navigation that does not come. Tests: the `nav-settle` timeout tests and
   the manual Back check in Task 10.
3. **Someone who types `/accueil/cv`** (from an old link, or a search engine
   that saw the rewrite) must land on the landing's real address. Test: the
   `/accueil` route tests in Task 2.
4. **A counselor or an admin opening a landing** must see « Mon espace »
   leading to their own home, not the candidate's `/espace`. Test: the
   `accountLink` tests in Task 5.
5. **Blocked `sessionStorage`** (private windows, in-app browsers) or **WebGL
   turned off** must not break anything: the logo still plays, and the still
   image stays. Tests: `shouldPlayLogo` with a throwing storage (Task 5);
   `canRunLive3D` without WebGL (Task 9); the « WebGL off » manual check
   (Task 14).

## File map

| Task | Creates | Modifies |
|---|---|---|
| 1 | — | `frontend/package.json`, `frontend/package-lock.json` |
| 2 | `app/accueil/cv/page.tsx`, `app/accueil/voyage/page.tsx` (placeholders) | `lib/site.ts`, `lib/site.test.ts`, `lib/site-context.tsx`, `proxy.ts`, `components/layout/AppBar.tsx` |
| 3 | `scripts/gen-logo-paths.mjs`, `components/brand/logo-paths.ts`, `lib/logo-paths.test.ts` | `components/brand/Logo.tsx`, `package.json` |
| 4 | `lib/typeset.ts`, `lib/typeset.test.ts`, `components/landing/copy/{types,cv,voyage,shared}.ts`, `lib/landing-copy.test.ts` | — |
| 5 | `components/landing/landing.css`, `lib/logo-motion.ts` (+test), `lib/landing-nav.ts` (+test), `components/landing/{AnimatedLogo,LandingNav,LandingFooter,WipeLink,Doors}.tsx` | both landing pages, `app/(legal)/layout.tsx` |
| 6 | `lib/report-tiers.ts` (+test), `components/landing/{CvHero,ReportIndex,CardGrid,AdvisorsSection,Pricing,DataSection,Faq,FinalCall}.tsx` | `types/index.ts`, `landing.css`, `app/accueil/cv/page.tsx` |
| 7 | `components/landing/VoyageHero.tsx` | `landing.css`, `app/accueil/voyage/page.tsx` |
| 8 | `components/landing/scenes/{core,sheet,mark,index}.ts`, `app/dev/stills/{page.tsx,StillsStudio.tsx,save/route.ts}`, `scripts/encode-stills.mjs`, `public/landing/*.{avif,webp}`, `public/og/{cv,voyage}.png` | `package.json`, `frontend/.gitignore` |
| 9 | `lib/live-3d.ts` (+test), `components/landing/HeroObject.tsx` | `landing.css`, both landing pages, `CvHero.tsx`, `VoyageHero.tsx` |
| 10 | `lib/wipe.ts` (+test), `lib/nav-settle.ts` (+test), `components/landing/NavigationSettled.tsx` | `components/landing/WipeLink.tsx`, `app/layout.tsx`, `app/globals.css` |
| 11 | `lib/seo.ts` (+test), `app/robots.ts`, `app/sitemap.ts` | — |
| 12 | `lib/wording.test.ts` | `app/layout.tsx`, `app/page.tsx`, `app/analyse/nouveau/page.tsx` |
| 13 | — | `CLAUDE.md`, `TEST-PLAN.md`, `docs/superpowers/specs/2026-10-09-subdomain-split-design.md` |
| 14 | `scripts/landing-weight.mjs` | — (checks only) |

Paths without a prefix are under `frontend/src/`; `scripts/`, `public/` and
`package.json` are under `frontend/`.

---

### Task 1: Upgrade Next.js to 16.4 and React to 19.3

The spec's decision 29. Nothing later depends on it: the wipe calls the
browser API directly. If the upgrade fails, Step 6 rolls it back and the plan
continues on 16.2.6.

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing new; every later task works on either version.

- [ ] **Step 1: See which patches exist**

Run: `(cd frontend && npm view next@~16.4.0 version && npm view react@~19.3.0 version)`
Expected: one or more `16.4.x` lines, then `19.3.x` lines. The last line of
each list is the newest.

- [ ] **Step 2: Install the newest 16.4.x and 19.3.x, pinned exactly like the current ones**

Run: `(cd frontend && npm install --save-exact next@~16.4.0 eslint-config-next@~16.4.0 react@~19.3.0 react-dom@~19.3.0)`
Then: `(cd frontend && npm ls next react react-dom eslint-config-next)`
Expected: every package at the version just installed, with no `invalid` or
`UNMET` line.

- [ ] **Step 3: Read the upgrade notes that ship with the new version**

Run: `ls frontend/node_modules/next/dist/docs/01-app/02-guides/upgrading/`.
Open the 16.x file and read every section newer than 16.2. Compare it with
`frontend/next.config.ts`, which uses `output`, `skipTrailingSlashRedirect`,
`allowedDevOrigins`, `images.qualities` and `rewrites`. Apply any change the
notes require. Expected: none; if one is needed, keep it in this task's commit.

- [ ] **Step 4: Run every check**

Run: `(cd frontend && npm test && npx tsc --noEmit && npm run lint; npm run build)`
Expected: 14 tests pass, `tsc` silent, lint at most 11 problems, build
succeeds.

- [ ] **Step 5: Smoke-test the dev stack**

Run: `docker compose up -d --build -V frontend` and wait for
`docker compose logs frontend --since 2m` to show `Ready`. Then, in Chrome
with DevTools open:
- http://neoori.localhost:8080/ shows the root landing.
- http://cv.neoori.localhost:8080/analyse/nouveau shows the form.
- Sign in at http://cv.neoori.localhost:8080/connexion with a dev account
  (`/admin/utilisateurs` « Marquer comme vérifié » unlocks a fresh one), then
  http://voyage.neoori.localhost:8080/voyage shows the hub.

Expected: all three render, and the console shows no error that 16.2.6 did
not show.

- [ ] **Step 6: Only if Step 4 or 5 fails and the cause cannot be fixed in this task, roll back**

Run: `(cd frontend && git checkout -- package.json package-lock.json && npm ci) && docker compose up -d --build -V frontend`
Then skip Step 7, and write « Next.js stays on 16.2.6: <one-line reason> » in
the commit message of Task 2.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): next 16.4 and react 19.3

Spec decision 29. Nothing else changes; the wipe (task 10) does not depend
on it.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Routing — `/` is each subdomain's landing, `/accueil/*` is internal

Decisions 8, 9 and 12. After this task, `cv./` and `voyage./` answer 200 with
a placeholder page at their own address. In links, `/` means the current
host's own landing.

**Files:**
- Modify: `frontend/src/lib/site.ts` (whole file below)
- Modify: `frontend/src/lib/site.test.ts`
- Modify: `frontend/src/lib/site-context.tsx`
- Modify: `frontend/src/proxy.ts`
- Modify: `frontend/src/components/layout/AppBar.tsx:34` (comment only)
- Create: `frontend/src/app/accueil/cv/page.tsx`, `frontend/src/app/accueil/voyage/page.tsx`

**Interfaces:**
- Consumes: nothing new.
- Produces (later tasks rely on these exact names):
  - `type Route = { kind: "serve" } | { kind: "redirect"; location: string } | { kind: "rewrite"; path: string }`
  - `const LANDING: Record<"cv" | "voyage", string>` = `{ cv: "/accueil/cv", voyage: "/accueil/voyage" }`
  - `function isInternalLanding(pathname: string): boolean`
  - `function landingHref(app: AppName, site: Site): string`, which returns `"/"`
    on that app's host and `origin(app) + "/"` elsewhere
  - `useSite().landing(app: AppName): string`, the same function bound to the
    current site
  - `resolveHref("/", site)` and `resolveHref("/#x", site)` now return the path
    itself on every host

- [ ] **Step 1: Write the failing tests**

In `frontend/src/lib/site.test.ts`:

(a) Extend the import at the top to:

```ts
import {
  appOfHost, isInternalLanding, landingHref, origin, ownerOf, passesThrough, resolveHref, route,
  settingsFromEnv, type AppName, type Site, type SiteSettings,
} from "./site.ts"
```

(b) Under `const to = …`, add:

```ts
const rewrite = (path: string) => ({ kind: "rewrite", path })
```

(c) In the test « cv serves its own and the shared paths… », replace
`assert.deepEqual(r("/"), to("/analyse/nouveau"))` with
`assert.deepEqual(r("/"), rewrite("/accueil/cv"))`.

(d) In the test « voyage serves its own and the shared paths… », replace
`assert.deepEqual(r("/"), to("/voyage"))` with
`assert.deepEqual(r("/"), rewrite("/accueil/voyage"))`.

(e) In the test « a link stays relative on the host that serves it… », replace
these two lines:

```ts
  assert.equal(resolveHref("/#rapport", on("cv")), "https://neoori.tech/#rapport")
  assert.equal(resolveHref("/", on("voyage")), "https://neoori.tech/")
```

with:

```ts
  // Landings spec, decision 12: "/" and "/#…" are this host's own landing.
  assert.equal(resolveHref("/#rapport", on("cv")), "/#rapport")
  assert.equal(resolveHref("/", on("voyage")), "/")
```

(f) Add these three tests before the sign-in gate test:

```ts
test("each subdomain's / is its landing, served in place (landings spec, decision 8)", () => {
  assert.deepEqual(route("cv.neoori.tech", "/", "", PROD), rewrite("/accueil/cv"))
  assert.deepEqual(route("voyage.neoori.tech", "/", "?utm_source=x", PROD), rewrite("/accueil/voyage"))
  assert.deepEqual(route("cv.neoori.localhost:8080", "/", "", DEV), rewrite("/accueil/cv"))
  assert.deepEqual(route("neoori.tech", "/", "", PROD), serve)
  assert.deepEqual(route("127.0.0.1:3000", "/", "", PROD), serve)
})

test("the /accueil paths are never an address of their own (decision 9)", () => {
  // Review Focus 3.
  assert.deepEqual(route("cv.neoori.tech", "/accueil/cv", "", PROD), to("/"))
  assert.deepEqual(route("voyage.neoori.tech", "/accueil/voyage", "?x=1", PROD), to("/"))
  assert.deepEqual(route("cv.neoori.tech", "/accueil/voyage", "", PROD), to("https://voyage.neoori.tech/"))
  assert.deepEqual(route("voyage.neoori.tech", "/accueil/cv", "", PROD), to("https://cv.neoori.tech/"))
  assert.deepEqual(route("neoori.tech", "/accueil", "", PROD), to("https://cv.neoori.tech/"))
  assert.deepEqual(route("neoori.tech", "/accueil/voyage/x", "", PROD), to("https://voyage.neoori.tech/"))
  assert.equal(isInternalLanding("/accueillir"), false)
  assert.equal(isInternalLanding("/accueil"), true)
})

test("a link to an app's landing, from any host (decision 12)", () => {
  assert.equal(landingHref("cv", on("cv")), "/")
  assert.equal(landingHref("voyage", on("cv")), "https://voyage.neoori.tech/")
  assert.equal(landingHref("cv", on("root")), "https://cv.neoori.tech/")
  assert.equal(landingHref("root", on("voyage")), "https://neoori.tech/")
})
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `(cd frontend && npm test)`
Expected: FAIL. `isInternalLanding` and `landingHref` are not exported yet, so
the file fails at import with a `SyntaxError: The requested module './site.ts'
does not provide an export named 'isInternalLanding'`.

- [ ] **Step 3: Rewrite `frontend/src/lib/site.ts`**

Replace the whole file with:

```ts
/**
 * Which host serves which page (subdomain split spec, decisions 10–18 and 37;
 * landings spec, decisions 8, 9 and 12).
 *
 * neoori answers on three hosts built from one setting, DOMAIN: the root
 * (today's landing, nothing else), cv.DOMAIN (« J'ai une cible ») and
 * voyage.DOMAIN (le voyage). Each subdomain's "/" is its own landing, served
 * in place from an internal path. Plain functions with no Next.js import, so
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

export type Route =
  | { kind: "serve" }
  | { kind: "redirect"; location: string }
  | { kind: "rewrite"; path: string }

const PREFIX: Record<AppName, string> = { root: "", cv: "cv.", voyage: "voyage." }

/** Matched on a segment boundary: /voyage and /voyage/…, never /voyageur. */
const OWNERS: ReadonlyArray<readonly [string, "cv" | "voyage"]> = [
  ["/analyse", "cv"],
  ["/rapport", "cv"],
  ["/espace", "cv"],
  ["/voyage", "voyage"],
]

/** Where each subdomain's landing lives (landings spec, decision 8). The
 *  proxy serves it in place of "/", so the address stays cv.DOMAIN/. */
export const LANDING: Record<"cv" | "voyage", string> = {
  cv: "/accueil/cv",
  voyage: "/accueil/voyage",
}

const INTERNAL = "/accueil"

/** The landings' own paths are never an address (decision 9). */
export function isInternalLanding(pathname: string): boolean {
  return pathname === INTERNAL || pathname.startsWith(`${INTERNAL}/`)
}

/** Takes `process.env` whole. The index signature is what lets it: Next types
 *  NODE_ENV on ProcessEnv, and TypeScript refuses a value that shares no key
 *  with a type of optional keys only (TS2559). */
export function settingsFromEnv(env: {
  DOMAIN?: string
  PUBLIC_SCHEME?: string
  PUBLIC_PORT?: string
  [name: string]: string | undefined
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

/** The app that serves a page owned by `owner`, asked for on `app`. Every
 *  host serves its own "/" (landings spec, decision 12). */
function servedBy(owner: Owner, app: AppName): AppName {
  if (owner === "root") return app
  if (owner === "shared") return app === "root" ? "cv" : app
  return owner
}

/** The landing an internal path belongs to: voyage's, or cv's for anything
 *  else under /accueil. */
function landingOf(pathname: string): "cv" | "voyage" {
  return pathname === LANDING.voyage || pathname.startsWith(`${LANDING.voyage}/`) ? "voyage" : "cv"
}

/**
 * What a page request gets (split spec, « How a page request is routed »;
 * landings spec, decisions 8–9). A redirect to another host is absolute and
 * built from the settings, never from the Host header; a same-host redirect
 * is relative.
 */
export function route(
  host: string | null | undefined,
  pathname: string,
  search: string,
  settings: SiteSettings,
): Route {
  if (passesThrough(pathname)) return { kind: "serve" }
  const app = appOfHost(host, settings.domain)
  if (isInternalLanding(pathname)) {
    const owner = landingOf(pathname)
    return { kind: "redirect", location: owner === app ? "/" : `${origin(owner, settings)}/` }
  }
  const owner = ownerOf(pathname)
  if (owner === "root") {
    return app === "root" ? { kind: "serve" } : { kind: "rewrite", path: LANDING[app] }
  }
  const target = servedBy(owner, app)
  if (target === app) return { kind: "serve" }
  return { kind: "redirect", location: origin(target, settings) + pathname + search }
}

/**
 * A link target for a page served on `site`: the path itself when this host
 * serves it, the serving host's absolute URL otherwise. "/" and "/#…" are
 * this host's own landing (landings spec, decision 12). Anything that is not
 * a site path — mailto:, an absolute URL — comes back as given.
 */
export function resolveHref(path: string, site: Site): string {
  if (!path.startsWith("/") || path.startsWith("//")) return path
  const target = servedBy(ownerOf(path), site.app)
  return target === site.app ? path : origin(target, site.settings) + path
}

/** A link to an app's landing from any host (decision 12): "/" on that app's
 *  own host, its absolute "/" everywhere else. */
export function landingHref(app: AppName, site: Site): string {
  return app === site.app ? "/" : `${origin(app, site.settings)}/`
}
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `(cd frontend && npm test)`
Expected: PASS, 17 tests (14 before, plus 3).

- [ ] **Step 5: Serve the rewrite in the proxy**

In `frontend/src/proxy.ts`, directly after the closing `}` of the
`if (routed.kind === "redirect") { … }` block, add:

```ts
  if (routed.kind === "rewrite") {
    // Each subdomain's landing lives at an internal path and is public: serve
    // it in place of "/", so the address stays cv.DOMAIN/ (landings spec,
    // decision 8). Next keeps a rewrite internal only while its target has
    // the server's own origin; otherwise it proxies it, and this proxy runs
    // again for /accueil/… and answers 307. req.url carries that origin when
    // the server binds 0.0.0.0, as the Dockerfile does. Bound to 127.0.0.1,
    // Next renames the host "localhost" in req.url alone, and every landing
    // turns into a 307.
    return NextResponse.rewrite(new URL(routed.path, req.url))
  }
```

- [ ] **Step 6: Give client components `landing()`**

In `frontend/src/lib/site-context.tsx`:

(a) Change the import from `./site` to:

```ts
import { landingHref, resolveHref, type AppName, type Site } from "./site"
```

(b) In `interface SiteTools`, after `go: …`, add:

```ts
  /** "/" when `app` is this host's, that app's absolute "/" otherwise
   *  (landings spec, decision 12). */
  landing: (app: AppName) => string
```

(c) In the object `useSite()` returns, after the `go: …` entry, add:

```ts
    landing: (target) => landingHref(target, site),
```

- [ ] **Step 7: Correct the logout comment in `AppBar.tsx`**

In `frontend/src/components/layout/AppBar.tsx`, replace the line
`    // The root landing (decision 16). The session ended on every host.` with:

```ts
    // This app's own landing (landings spec, decision 12). The session ended
    // on every host.
```

- [ ] **Step 8: Add the two placeholder pages**

`frontend/src/app/accueil/cv/page.tsx`:

```tsx
// The cv. landing, served at cv.DOMAIN/ by the proxy's rewrite (landings spec,
// decision 8). Task 6 of the plan replaces this placeholder.
export default function CvLandingPage() {
  return (
    <main>
      <h1>J’ai une cible</h1>
    </main>
  )
}
```

`frontend/src/app/accueil/voyage/page.tsx`:

```tsx
// The voyage. landing, served at voyage.DOMAIN/ by the proxy's rewrite
// (landings spec, decision 8). Task 7 of the plan replaces this placeholder.
export default function VoyageLandingPage() {
  return (
    <main>
      <h1>Le voyage</h1>
    </main>
  )
}
```

- [ ] **Step 9: Run every check**

Run: `(cd frontend && npm test && npx tsc --noEmit && npm run lint; npm run build)`
Expected: 17 tests pass, `tsc` silent, lint at most 11 problems, build
succeeds.

- [ ] **Step 10: Check the routing through nginx**

Run: `docker compose up -d`, then:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: cv.neoori.localhost' http://127.0.0.1:8080/
curl -s -H 'Host: cv.neoori.localhost' http://127.0.0.1:8080/ | grep -o 'J’ai une cible' | head -1
curl -s -H 'Host: voyage.neoori.localhost' http://127.0.0.1:8080/ | grep -o 'Le voyage' | head -1
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' -H 'Host: cv.neoori.localhost' http://127.0.0.1:8080/accueil/cv
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' -H 'Host: cv.neoori.localhost' http://127.0.0.1:8080/accueil/voyage
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: neoori.localhost' http://127.0.0.1:8080/
```

Expected, line by line:
1. `200`
2. `J’ai une cible`
3. `Le voyage`
4. `307`, with a URL ending in `/`
5. `307 http://voyage.neoori.localhost:8080/`
6. `200`, the root landing, unchanged

- [ ] **Step 11: Commit**

```bash
git add frontend/src/lib/site.ts frontend/src/lib/site.test.ts frontend/src/lib/site-context.tsx \
  frontend/src/proxy.ts frontend/src/components/layout/AppBar.tsx frontend/src/app/accueil
git commit -m "feat(routing): / on cv. and voyage. is the landing; /accueil is internal

Landings spec decisions 8, 9 and 12. The proxy rewrites / to /accueil/cv or
/accueil/voyage, a direct /accueil request is redirected to the landing's
own /, and in links / now means the current host's landing. Placeholder
pages for now.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The vector logo across the app

Decision 27. Every `<Logo>` becomes the inline vector wordmark: one line, no
English tagline, white letters on dark backgrounds instead of a white plate.
`variant="mark"` draws the oo mark; today it points at a file that does not
exist.

**Files:**
- Create: `frontend/scripts/gen-logo-paths.mjs`
- Create (generated, committed): `frontend/src/components/brand/logo-paths.ts`
- Create: `frontend/src/lib/logo-paths.test.ts`
- Modify: `frontend/src/components/brand/Logo.tsx` (the part above the `Brand motif` comment)
- Modify: `frontend/package.json` (one script)

**Interfaces:**
- Consumes: `public/brand/neoori-logo.svg`, `public/brand/neoori-mark.svg`
  (in the repo since fd2f47f).
- Produces (from `@/components/brand/logo-paths`):
  - `LOGO_VIEWBOX` = `{ w: 627, h: 175 }`
  - `LOGO_NAVY` = `"#213a68"`
  - `LOGO_LETTERS` = `{ n, e, r, i }` (path strings)
  - `LOGO_OO` (path string)
  - `LOGO_OO_GRADIENT` = `{ x1, x2, stops: [offset, colour][] }`
  - `MARK_VIEWBOX` = `{ w: 225, h: 131 }`
  - `MARK_PATH`
  - `MARK_GRADIENT`

  `<Logo>` keeps its props (`variant`, `tone`, `onDark`, `className`,
  `priority`, `animate`). `InfinityMark` and `BrandMark` are unchanged.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/logo-paths.test.ts`:

```ts
import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import {
  LOGO_LETTERS, LOGO_NAVY, LOGO_OO, LOGO_VIEWBOX, MARK_PATH, MARK_VIEWBOX,
} from "../components/brand/logo-paths.ts"

const svg = (name: string) => readFileSync(new URL(`../../public/brand/${name}`, import.meta.url), "utf8")

test("the logo paths are the vector files' own (run `npm run gen:logo` after changing them)", () => {
  const logo = svg("neoori-logo.svg")
  for (const d of Object.values(LOGO_LETTERS)) assert.ok(logo.includes(`d="${d}"`), d.slice(0, 20))
  assert.ok(logo.includes(`d="${LOGO_OO}"`))
  assert.ok(logo.includes(`fill="${LOGO_NAVY}"`))
  assert.deepEqual(LOGO_VIEWBOX, { w: 627, h: 175 })
  assert.ok(svg("neoori-mark.svg").includes(`d="${MARK_PATH}"`))
  assert.deepEqual(MARK_VIEWBOX, { w: 225, h: 131 })
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `(cd frontend && npm test)`
Expected: FAIL with `Cannot find module …/components/brand/logo-paths.ts`.

- [ ] **Step 3: Write the generator and run it**

`frontend/scripts/gen-logo-paths.mjs`:

```js
// Writes src/components/brand/logo-paths.ts from the vector logo files in
// public/brand/ (landings spec, decision 27). Run: npm run gen:logo
import { readFileSync, writeFileSync } from "node:fs"

const read = (name) => readFileSync(new URL(`../public/brand/${name}`, import.meta.url), "utf8")
const logo = read("neoori-logo.svg")
const mark = read("neoori-mark.svg")

function gradient(svg) {
  const g = svg.match(/<linearGradient[^>]*\bx1="([\d.]+)"[^>]*\bx2="([\d.]+)"[^>]*>([\s\S]*?)<\/linearGradient>/)
  if (!g) throw new Error("no gradient")
  const stops = [...g[3].matchAll(/offset="([\d.]+)" stop-color="(#[0-9a-fA-F]{6})"/g)].map((m) => [m[1], m[2]])
  return { x1: Number(g[1]), x2: Number(g[2]), stops }
}

function viewBox(svg) {
  const v = svg.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/)
  if (!v) throw new Error("no viewBox")
  return { w: Number(v[1]), h: Number(v[2]) }
}

const paths = [...logo.matchAll(/<path([^>]*?)\sd="([^"]+)"/g)].map((m) => ({ attrs: m[1], d: m[2] }))
const letters = paths.filter((p) => !p.attrs.includes("url(#")).map((p) => p.d)
const oo = paths.find((p) => p.attrs.includes("url(#"))?.d
const navy = logo.match(/<g fill="(#[0-9a-fA-F]{6})"/)?.[1]
const markPath = mark.match(/<path[^>]*\sd="([^"]+)"/)?.[1]
if (letters.length !== 4 || !oo || !navy || !markPath) throw new Error("unexpected logo SVG structure")

const out = `// Generated by scripts/gen-logo-paths.mjs from public/brand/neoori-logo.svg
// and public/brand/neoori-mark.svg. Do not edit by hand: run \`npm run gen:logo\`.
export const LOGO_VIEWBOX = ${JSON.stringify(viewBox(logo))} as const
export const LOGO_NAVY = ${JSON.stringify(navy)}
export const LOGO_LETTERS = ${JSON.stringify({ n: letters[0], e: letters[1], r: letters[2], i: letters[3] })} as const
export const LOGO_OO = ${JSON.stringify(oo)}
export const LOGO_OO_GRADIENT = ${JSON.stringify(gradient(logo))} as const
export const MARK_VIEWBOX = ${JSON.stringify(viewBox(mark))} as const
export const MARK_PATH = ${JSON.stringify(markPath)}
export const MARK_GRADIENT = ${JSON.stringify(gradient(mark))} as const
`
writeFileSync(new URL("../src/components/brand/logo-paths.ts", import.meta.url), out)
console.log("wrote src/components/brand/logo-paths.ts")
```

In `frontend/package.json`, add to `"scripts"`, after `"test"`:

```json
    "gen:logo": "node scripts/gen-logo-paths.mjs"
```

(Add a comma after the `"test"` line.)

Run: `(cd frontend && npm run gen:logo)`
Expected: `wrote src/components/brand/logo-paths.ts`.

- [ ] **Step 4: Run the test and watch it pass**

Run: `(cd frontend && npm test)`
Expected: PASS (18 tests).

- [ ] **Step 5: Draw `<Logo>` from the paths**

In `frontend/src/components/brand/Logo.tsx`, replace everything from the first
line down to (but **not** including) the line
`/* ── Brand motif: the interlocking "oo" / ∞ rings (orange + navy). ──` with:

```tsx
import { useId } from "react"
import { cn } from "@/lib/utils"
import {
  LOGO_LETTERS, LOGO_NAVY, LOGO_OO, LOGO_OO_GRADIENT, LOGO_VIEWBOX,
  MARK_GRADIENT, MARK_PATH, MARK_VIEWBOX,
} from "./logo-paths"

/* The neoori logo, drawn from the vector files in public/brand/ (landings
   spec, decision 27): one line and no tagline, so every visible word is
   French. Size it with font-size: the wordmark is 1.05em tall, about the
   width the old two-line PNG had. On dark surfaces (`tone="light"` /
   `onDark`) the letters turn white and the oo keeps its gradient; there is
   no white plate any more. The SVG ring/figure marks further down are brand
   MOTIFS (decorative accents that echo the oo), not the logo. */

type Tone = "navy" | "light"

export function Logo({
  variant = "full",
  tone = "navy",
  onDark,
  className,
}: {
  variant?: "full" | "mark" | "wordmark"
  tone?: Tone
  onDark?: boolean
  /** Legacy no-op: the logo is inline SVG, nothing to preload. */
  priority?: boolean
  className?: string
  /** Legacy no-op, kept for back-compat. */
  animate?: boolean
}) {
  // One gradient per logo: two logos on a page (AuthLayout has two) must not
  // share an id, or hiding the first would blank the second's gradient.
  const id = `lg${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`

  if (variant === "mark") {
    return (
      <svg
        viewBox={`0 0 ${MARK_VIEWBOX.w} ${MARK_VIEWBOX.h}`}
        role="img"
        aria-label="neoori"
        className={cn("inline-block shrink-0 select-none", className)}
        style={{ height: "1em", width: "auto" }}
      >
        <defs>
          <linearGradient id={id} x1={MARK_GRADIENT.x1} y1="0" x2={MARK_GRADIENT.x2} y2="0" gradientUnits="userSpaceOnUse">
            {MARK_GRADIENT.stops.map(([offset, color]) => <stop key={offset} offset={offset} stopColor={color} />)}
          </linearGradient>
        </defs>
        <path d={MARK_PATH} fill={`url(#${id})`} />
      </svg>
    )
  }

  const light = onDark ?? tone === "light"
  return (
    <svg
      viewBox={`0 0 ${LOGO_VIEWBOX.w} ${LOGO_VIEWBOX.h}`}
      role="img"
      aria-label="neoori"
      className={cn("inline-block shrink-0 select-none", className)}
      style={{ height: "1.05em", width: "auto" }}
    >
      <defs>
        <linearGradient id={id} x1={LOGO_OO_GRADIENT.x1} y1="0" x2={LOGO_OO_GRADIENT.x2} y2="0" gradientUnits="userSpaceOnUse">
          {LOGO_OO_GRADIENT.stops.map(([offset, color]) => <stop key={offset} offset={offset} stopColor={color} />)}
        </linearGradient>
      </defs>
      <g fill={light ? "#ffffff" : LOGO_NAVY}>
        <path d={LOGO_LETTERS.n} />
        <path d={LOGO_LETTERS.e} />
        <path d={LOGO_LETTERS.r} />
        <path d={LOGO_LETTERS.i} />
      </g>
      <path d={LOGO_OO} fill={`url(#${id})`} />
    </svg>
  )
}

```

(`useId` is allowed in Server Components; `Logo` stays one, so it adds no
client JavaScript. `public/neoori-logo.png` stays on disk; nothing in the UI
uses it any more.)

- [ ] **Step 6: Run every check**

Run: `(cd frontend && npm test && npx tsc --noEmit && npm run lint; npm run build)`
Expected: 18 tests pass, `tsc` silent, lint at most 11 problems (one fewer
than before: the old unused `_animate` warning is gone), build succeeds. If
`tsc` complains that `next/image` is unused, the old `Image` import was not
removed: the replacement above starts at line 1.

- [ ] **Step 7: Look at the logo where it lives**

Run: `docker compose up -d`. In Chrome, check every `<Logo>` you can reach in
the dev data. Each should be crisp; on navy it should be white letters with
the orange oo and no white plate; and it should be about as wide as before.

| Where | Call site |
|---|---|
| http://neoori.localhost:8080/ (menu, line 32, footer) | `SiteNav.tsx:26`, `app/page.tsx:32`, `SiteFooter.tsx:47` |
| http://cv.neoori.localhost:8080/connexion, desktop and 390 px | `AuthLayout.tsx:25` (on the photo), `AuthLayout.tsx:50` (phone) |
| http://cv.neoori.localhost:8080/espace (signed in) | `AppBar.tsx:48` |
| http://cv.neoori.localhost:8080/admin (admin) | `app/admin/layout.tsx:90` |
| http://cv.neoori.localhost:8080/c/x | `app/c/[token]/page.tsx:11` |
| http://cv.neoori.localhost:8080/analyse/envoyee | `app/analyse/envoyee/page.tsx:12` |
| a report, `/analyse/<id>/rapport`, and its print preview (⌘P) | `ReportDocument.tsx:53` |
| a running analysis, `/analyse/en-cours/<id>` | `RunProgress.tsx:227` |
| voyage pages, if a validated portrait or a counselor link exists | `voyage/portrait/page.tsx:179`, `voyage/c/[token]/page.tsx:390, 417, 464` |

If one is clearly too large or too small next to its old size, adjust only
that call site's `text-*` class. Do not change `Logo.tsx`.
(`components/auth/SocialSignIn.tsx` has its own local `Logo` for the Google
and Microsoft icons: leave it alone.)

- [ ] **Step 8: Commit**

```bash
git add frontend/scripts/gen-logo-paths.mjs frontend/src/components/brand frontend/src/lib/logo-paths.test.ts frontend/package.json
git commit -m "feat(brand): the vector logo everywhere

Landings spec decision 27. <Logo> draws the inline wordmark from
public/brand/ (paths generated into logo-paths.ts and checked by a test):
one line, no English tagline, white letters on dark backgrounds instead of
a white plate. variant=\"mark\" draws the oo mark.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(Add any call-site files you adjusted in Step 7 to the `git add`.)

---

### Task 4: The landing copy, its French typography, and its rules

Decisions 31–33 and Appendix A. Every visible string of both landings lives in
`components/landing/copy/`, written with plain spaces. `typeset()` sets the
French no-break spaces, and a test enforces CLAUDE.md's copy rules. This is the
file set the PM reviews.

**Files:**
- Create: `frontend/src/lib/typeset.ts`, `frontend/src/lib/typeset.test.ts`
- Create: `frontend/src/components/landing/copy/types.ts`
- Create: `frontend/src/components/landing/copy/cv.ts`
- Create: `frontend/src/components/landing/copy/voyage.ts`
- Create: `frontend/src/components/landing/copy/shared.ts`
- Create: `frontend/src/lib/landing-copy.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `fr(text: string): string`
  - `typeset<T>(value: T): T`
  - `cvCopy: CvCopy`, `voyageCopy: VoyageCopy`, `footerCopy: FooterCopy`
  - the types in `copy/types.ts`: `LandingApp`, `LinkCopy`, `AppLinkCopy`,
    `DoorCopy`, `ItemCopy`, `FaqItemCopy`, `NavCopy`, `HeroCopy`,
    `AdvisorsCopy`, `DataCopy`, `FaqCopy`, `FinalCopy`, `MetaCopy`, `CvCopy`,
    `VoyageCopy`, `FooterCopy`

  Field names used by later tasks:
  - `cvCopy.showPrices`
  - `.nav.links[].{href,label,pricesOnly}`
  - `.hero.{label,title,sub,primary,secondary}`
  - `.report.{title,intro,tiers}`
  - `.how.items`, `.ways.{title,intro,items}`
  - `.advisors.{label,title,points,signup,signin}`
  - `.prices.{title,intro,plans,note}`
  - `.data.{title,points,link}`
  - `.faq.{title,items[].{q,a,link?}}`
  - `.final.{title,bridge}`
  - `voyageCopy.hero.{steps,stepsLabel}`, `.take.{title,items,note}`,
    `.how.{title,items[].link?,note}`

- [ ] **Step 1: Write the failing typography test**

`frontend/src/lib/typeset.test.ts`:

```ts
import { test } from "node:test"
import assert from "node:assert/strict"
import { fr, typeset } from "./typeset.ts"

test("fr() sets the French no-break spaces (landings spec, decision 31)", () => {
  assert.equal(fr("Pour toute cible : un métier"), "Pour toute cible : un métier")
  assert.equal(fr("Une offre en main ? Collez-la ; merci !"), "Une offre en main ? Collez-la ; merci !")
  assert.equal(fr("oui, non ou « – »"), "oui, non ou « – »")
  assert.equal(fr("Complet · 9 € et 10 Mo"), "Complet · 9 € et 10 Mo")
  assert.equal(fr("/analyse/nouveau"), "/analyse/nouveau")
})

test("typeset() keeps the shape and leaves anything but strings alone", () => {
  assert.deepEqual(
    typeset({ a: "x : y", b: ["Et ? ", { c: false, d: 3 }] }),
    { a: "x : y", b: ["Et ? ", { c: false, d: 3 }] },
  )
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `(cd frontend && npm test)`
Expected: FAIL with `Cannot find module …/lib/typeset.ts`.

- [ ] **Step 3: Write `frontend/src/lib/typeset.ts`**

```ts
const NBSP = " "
const NNBSP = " "

/** French typography for UI copy (landings spec, decision 31): a no-break
 *  space before « : » and inside guillemets, a narrow no-break space before
 *  « ; ! ? », and a no-break space between a number and its unit. Copy files
 *  are written with plain spaces; this function sets them. */
export function fr(text: string): string {
  return text
    .replace(/ +:/g, `${NBSP}:`)
    .replace(/ +([;!?])/g, `${NNBSP}$1`)
    .replace(/« +/g, `«${NBSP}`)
    .replace(/ +»/g, `${NBSP}»`)
    .replace(/(\d) +(€|Mo|%)/g, `$1${NBSP}$2`)
}

/** fr() on every string inside a copy object; anything else is kept as is. */
export function typeset<T>(value: T): T {
  if (typeof value === "string") return fr(value) as T
  if (Array.isArray(value)) return value.map((item) => typeset(item)) as T
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, typeset(item)])) as T
  }
  return value
}
```

- [ ] **Step 4: Run it and watch it pass**

Run: `(cd frontend && npm test)`
Expected: PASS (20 tests).

- [ ] **Step 5: Write the failing copy-rules test**

`frontend/src/lib/landing-copy.test.ts`:

```ts
import { test } from "node:test"
import assert from "node:assert/strict"
import { cvCopy } from "../components/landing/copy/cv.ts"
import { voyageCopy } from "../components/landing/copy/voyage.ts"
import { footerCopy } from "../components/landing/copy/shared.ts"

function strings(value: unknown, out: string[] = []): string[] {
  if (typeof value === "string") out.push(value)
  else if (Array.isArray(value)) value.forEach((item) => strings(item, out))
  else if (value !== null && typeof value === "object") Object.values(value).forEach((item) => strings(item, out))
  return out
}

// Visible text only: hrefs start with "/" or "#".
const TEXT = [...strings(cvCopy), ...strings(voyageCopy), ...strings(footerCopy)]
  .filter((s) => !s.startsWith("/") && !s.startsWith("#"))

// CLAUDE.md, « UI copy rules ».
const BANNED = [
  "boussole", "copilote", "miroir", "révélation", "épanouissement",
  "alignement", "excellence", "talent unique", "vous vous démarquez",
]

test("no word from CLAUDE.md's banned list", () => {
  for (const s of TEXT) for (const word of BANNED) assert.ok(!s.toLowerCase().includes(word), `« ${word} » in « ${s} »`)
})

test("the cible is never only a job (landings spec, ruling 4)", () => {
  for (const s of TEXT) assert.doesNotMatch(s, /poste que vous visez|vous visez un poste|offre d['’]emploi/i, s)
})

test("French typography: typographic apostrophes and no-break spaces (decision 31)", () => {
  for (const s of TEXT) {
    assert.ok(!s.includes("'"), `straight apostrophe in « ${s} »`)
    assert.doesNotMatch(s, / [:;!?»]/, `plain space before punctuation in « ${s} »`)
    assert.doesNotMatch(s, /« /, `plain space after « in « ${s} »`)
  }
})

test("no score is promised and nothing claims where data is processed (decision 32)", () => {
  for (const s of TEXT) {
    if (/\bscore\b/i.test(s)) assert.match(s, /(ni|pas de) score/i, s)
    assert.doesNotMatch(s, /union européenne|\bUE\b|hébergée?s? en france/i, s)
  }
})

test("prices stay hidden until the PM agrees (decision 16)", () => {
  assert.equal(cvCopy.showPrices, false)
  assert.ok(cvCopy.nav.links.some((link) => link.pricesOnly))
})

test("the two doors and the advisors anchor line up (ruling 5)", () => {
  for (const copy of [cvCopy, voyageCopy]) {
    assert.equal(copy.hero.secondary.label, "Je suis conseiller")
    assert.equal(copy.hero.secondary.href, "#conseillers")
    assert.ok(copy.nav.links.some((link) => link.href === "/#conseillers"))
  }
  assert.equal(cvCopy.hero.primary.href, "/analyse/nouveau")
  assert.equal(voyageCopy.hero.primary.href, "/voyage")
})
```

- [ ] **Step 6: Run it and watch it fail**

Run: `(cd frontend && npm test)`
Expected: FAIL with `Cannot find module …/components/landing/copy/cv.ts`.

- [ ] **Step 7: Write the copy types**

`frontend/src/components/landing/copy/types.ts`:

```ts
/** Shapes of the landing copy files (landings spec, decision 32). */

export type LandingApp = "cv" | "voyage"

export interface LinkCopy {
  href: string
  label: string
  /** Shown only while prices are (decision 16). */
  pricesOnly?: boolean
}

/** A link to an app's landing, resolved per host by landingHref(). */
export interface AppLinkCopy {
  app: LandingApp
  label: string
}

export interface DoorCopy {
  label: string
  note: string
  href: string
}

export interface ItemCopy {
  title: string
  text: string
}

export interface FaqItemCopy {
  q: string
  a: string
  link?: AppLinkCopy
}

export interface NavCopy {
  links: LinkCopy[]
  signIn: string
  myHome: string
  cross: AppLinkCopy
  openMenu: string
  closeMenu: string
  home: string
}

export interface HeroCopy {
  label: string
  title: string
  sub: string
  primary: DoorCopy
  secondary: DoorCopy
}

export interface AdvisorsCopy {
  label: string
  title: string
  points: string[]
  signup: LinkCopy
  signin: LinkCopy
}

export interface DataCopy {
  title: string
  points: string[]
  link: LinkCopy
}

export interface FaqCopy {
  title: string
  items: FaqItemCopy[]
}

export interface FinalCopy {
  title: string
  bridge: { text: string; link: AppLinkCopy }
}

export interface MetaCopy {
  title: string
  description: string
  ogAlt: string
}

export interface CvCopy {
  showPrices: boolean
  meta: MetaCopy
  nav: NavCopy
  hero: HeroCopy
  report: {
    title: string
    intro: string
    tiers: Record<"free" | "complet" | "premium", { name: string; tag: string }>
  }
  how: { title: string; items: ItemCopy[] }
  ways: { title: string; intro: string; items: ItemCopy[] }
  advisors: AdvisorsCopy
  prices: { title: string; intro: string; plans: { name: string; price: string; text: string }[]; note: string }
  data: DataCopy
  faq: FaqCopy
  final: FinalCopy
}

export interface VoyageCopy {
  meta: MetaCopy
  nav: NavCopy
  hero: HeroCopy & { stepsLabel: string; steps: { name: string; caption?: string }[] }
  take: { title: string; items: ItemCopy[]; note: string }
  how: { title: string; items: (ItemCopy & { link?: AppLinkCopy })[]; note: string }
  advisors: AdvisorsCopy
  data: DataCopy
  faq: FaqCopy
  final: FinalCopy
}

export interface FooterCopy {
  label: string
  tagline: string
  apps: AppLinkCopy[]
  links: LinkCopy[]
  signIn: LinkCopy
  copyright: string
}
```

- [ ] **Step 8: Write the cv. copy**

`frontend/src/components/landing/copy/cv.ts`:

```ts
import { typeset } from "../../../lib/typeset.ts"
import type { CvCopy } from "./types"

/** Every visible string of the cv. landing (landings spec, decision 32). The
 *  PM reviews this file; the spec's Appendix A was its first version. Write
 *  plain spaces and typographic apostrophes (’): typeset() sets the French
 *  no-break spaces. */
export const cvCopy = typeset<CvCopy>({
  // « Tarifs » stays hidden, in the page and in the menu, until the PM agrees (decision 16).
  showPrices: false,
  meta: {
    title: "Analyse de CV face à une cible",
    description:
      "Un métier, une formation, un poste ou un projet : neoori lit le CV face à ce qui est visé et montre les forces, ce qui reste à renforcer et par où avancer. Gratuit pour commencer.",
    ogAlt: "J’ai une cible · Lire un parcours face à sa cible.",
  },
  nav: {
    links: [
      { href: "/#comment", label: "Comment ça marche" },
      { href: "/#conseillers", label: "Pour les conseillers" },
      { href: "/#tarifs", label: "Tarifs", pricesOnly: true },
      { href: "/#questions", label: "Questions" },
    ],
    signIn: "Se connecter",
    myHome: "Mon espace",
    cross: { app: "voyage", label: "Le voyage" },
    openMenu: "Ouvrir le menu",
    closeMenu: "Fermer le menu",
    home: "neoori, accueil",
  },
  hero: {
    label: "J’ai une cible",
    title: "Lire un parcours face à sa cible.",
    sub: "Un métier, une formation, un poste, un projet : neoori lit le CV face à ce qui est visé, et montre les forces, ce qui reste à renforcer et par où avancer.",
    primary: { label: "Analyser mon CV", note: "Gratuit pour commencer, avec ou sans compte.", href: "/analyse/nouveau" },
    secondary: { label: "Je suis conseiller", note: "Vos codes, et les rapports qui vous reviennent.", href: "#conseillers" },
  },
  report: {
    title: "Ce que contient le rapport",
    intro: "Commencez gratuitement : §1 à §3 et un verdict. Le reste s’ajoute quand vous le souhaitez.",
    tiers: {
      free: { name: "Pour commencer", tag: "Gratuit" },
      complet: { name: "Rapport complet", tag: "Complet" },
      premium: { name: "En plus", tag: "Premium" },
    },
  },
  how: {
    title: "Comment ça marche",
    items: [
      { title: "Votre CV", text: "En PDF (10 Mo au plus) ou en texte collé." },
      {
        title: "Votre cible",
        text: "Un métier, une formation, un poste ou un projet, décrit avec vos mots. Une offre, une fiche métier ou un programme en main ? Collez-le.",
      },
      { title: "Votre lecture", text: "En quelques minutes : vos forces, ce qui reste à renforcer, et par où avancer." },
    ],
  },
  ways: {
    title: "Quatre façons de commencer",
    intro: "Vous choisissez au moment de lancer l’analyse.",
    items: [
      { title: "Avec votre compte", text: "La version gratuite, puis le rapport complet si vous le souhaitez. Vos analyses restent dans votre espace." },
      { title: "Avec un code promo", text: "Le rapport complet, une fois par compte." },
      {
        title: "Avec un code conseiller",
        text: "Le rapport complet, sans créer de compte. Il est remis à votre conseiller, et vous le découvrez ensemble.",
      },
      { title: "Sans compte", text: "La version gratuite, sur un lien privé valable 30 jours." },
    ],
  },
  advisors: {
    label: "Pour les conseillers",
    title: "Proposez l’analyse aux personnes que vous accompagnez.",
    points: [
      "Des codes à remettre, pour une analyse ou pour un voyage.",
      "Avec votre code, le rapport complet arrive dans votre espace conseiller, et nulle part ailleurs.",
      "Une note privée sur chaque analyse, visible de vous uniquement.",
      "Pour toute cible : un métier, une formation, un poste, un projet.",
    ],
    signup: { href: "/inscription-conseiller", label: "Créer un compte conseiller" },
    signin: { href: "/connexion", label: "Se connecter" },
  },
  prices: {
    title: "Tarifs",
    intro: "Paiement unique, sans abonnement.",
    plans: [
      { name: "Gratuit", price: "0 €", text: "§1 à §3 et un verdict." },
      { name: "Complet", price: "9 €", text: "Le rapport complet, §1 à §9." },
      { name: "Premium", price: "24 €", text: "Le rapport complet, plus la préparation à l’entretien (§10 et §11)." },
    ],
    note: "Vous passez au rapport complet depuis votre rapport gratuit, quand vous le souhaitez.",
  },
  data: {
    title: "Vos données",
    points: [
      "Votre CV et vos réponses servent à produire votre analyse.",
      "L’analyse est rédigée par une IA, à partir de votre CV et de votre cible.",
      "Vous pouvez supprimer une analyse à tout moment, depuis votre espace.",
      "Sans compte, le rapport s’efface de lui-même au bout de 30 jours.",
    ],
    link: { href: "/confidentialite", label: "Lire la politique de confidentialité" },
  },
  faq: {
    title: "Questions",
    items: [
      {
        q: "Ma cible n’est pas un poste précis. Est-ce que ça marche ?",
        a: "Oui. Une cible peut être un métier, une formation, un poste ou un projet. Décrivez-la avec vos mots ; une offre, une fiche métier ou un programme de formation aide aussi.",
      },
      {
        q: "Faut-il créer un compte ?",
        a: "Non. Sans compte, vous recevez la version gratuite sur un lien privé valable 30 jours. Avec un compte, vos analyses restent dans votre espace et vous pouvez passer au rapport complet.",
      },
      {
        q: "Que se passe-t-il avec un code conseiller ?",
        a: "Le rapport complet est remis à votre conseiller, pas à vous. Vous le découvrez ensemble, en rendez-vous.",
      },
      { q: "Combien de temps faut-il ?", a: "Quelques minutes pour remplir le formulaire, puis quelques minutes pour l’analyse." },
      {
        q: "Qui rédige l’analyse ?",
        a: "Une IA, à partir de votre CV, de votre cible et de vos réponses. Elle ne remplace pas un conseiller : elle prépare l’échange.",
      },
      {
        q: "Puis-je supprimer mon analyse ?",
        a: "Oui, depuis votre espace, à tout moment. Sans compte, elle s’efface d’elle-même au bout de 30 jours.",
      },
      {
        q: "Je n’ai pas encore de cible.",
        a: "Commencez par le voyage : six étapes pour poser ce que vous savez déjà de vous.",
        link: { app: "voyage", label: "Découvrir le voyage" },
      },
    ],
  },
  final: {
    title: "Votre parcours a des choses à dire.",
    bridge: { text: "Pas encore de cible ? Le voyage vous aide à la trouver.", link: { app: "voyage", label: "Découvrir le voyage" } },
  },
})
```

- [ ] **Step 9: Write the voyage. copy**

`frontend/src/components/landing/copy/voyage.ts`:

```ts
import { typeset } from "../../../lib/typeset.ts"
import type { VoyageCopy } from "./types"

/** Every visible string of the voyage. landing (landings spec, decision 32).
 *  The PM reviews this file; the spec's Appendix A was its first version.
 *  Write plain spaces and typographic apostrophes (’): typeset() sets the
 *  French no-break spaces. */
export const voyageCopy = typeset<VoyageCopy>({
  meta: {
    title: "Le voyage, du brouillard à la clarté",
    description:
      "Six étapes pour poser ce que vous savez déjà de vous : la première en cinq minutes, en autonomie, les cinq suivantes avec un conseiller. Puis un portrait, relu ensemble.",
    ogAlt: "Le voyage · Du brouillard à la clarté, une étape après l’autre.",
  },
  nav: {
    links: [
      { href: "/#etapes", label: "Les six étapes" },
      { href: "/#conseillers", label: "Pour les conseillers" },
      { href: "/#questions", label: "Questions" },
    ],
    signIn: "Se connecter",
    myHome: "Mon espace",
    cross: { app: "cv", label: "J’ai une cible" },
    openMenu: "Ouvrir le menu",
    closeMenu: "Fermer le menu",
    home: "neoori, accueil",
  },
  hero: {
    label: "Le voyage",
    title: "Du brouillard à la clarté, une étape après l’autre.",
    sub: "Six étapes pour poser ce que vous savez déjà de vous. La première se fait en cinq minutes, en autonomie ; les cinq suivantes, avec un conseiller.",
    primary: { label: "Commencer le voyage", note: "Session 0 : cinq minutes, en autonomie.", href: "/voyage" },
    secondary: { label: "Je suis conseiller", note: "Vos codes, les séances, le portrait à valider.", href: "#conseillers" },
    stepsLabel: "Les six étapes du voyage",
    steps: [
      { name: "Session 0", caption: "Dans 10 ans · cinq minutes, en autonomie" },
      { name: "Session 1", caption: "avec votre conseiller" },
      { name: "Session 2" },
      { name: "Session 3" },
      { name: "Session 4" },
      { name: "Session 5", caption: "puis le portrait, relu ensemble" },
    ],
  },
  take: {
    title: "Ce que vous emportez",
    items: [
      { title: "Votre phrase", text: "Dès la session 0, une première phrase sur vous, tirée de vos 20 réponses." },
      {
        title: "Votre portrait",
        text: "Après la session 5, un portrait en six parties : ce qui vous fait vibrer, ce dont vous avez besoin, les chemins possibles… Votre conseiller le relit et le valide avec vous avant de vous le remettre.",
      },
    ],
    note: "Ni note, ni score : le voyage décrit, il ne classe pas.",
  },
  how: {
    title: "Comment ça se passe",
    items: [
      { title: "Session 0, en autonomie", text: "Dans 10 ans : 20 affirmations, oui, non ou « – ». Cinq minutes." },
      {
        title: "Sessions 1 à 5, avec votre conseiller",
        text: "Votre conseiller vous donne un code qui ouvre les séances. Vous avancez d’une séance à l’autre, à votre rythme.",
      },
      { title: "Le portrait", text: "Rédigé à partir de vos réponses, relu et validé par votre conseiller, puis remis." },
      {
        title: "Et vos analyses",
        text: "Le voyage peut ensuite enrichir vos analyses de CV.",
        link: { app: "cv", label: "Découvrir J’ai une cible" },
      },
    ],
    note: "Un compte gratuit garde vos réponses d’une séance à l’autre.",
  },
  advisors: {
    label: "Pour les conseillers",
    title: "Accompagnez chaque voyage, séance après séance.",
    points: [
      "Votre code ouvre les sessions 1 à 5.",
      "Une fiche de suivi par voyage, visible de vous uniquement.",
      "Le portrait se relit ensemble et n’est remis qu’après votre validation.",
      "Le voyage peut ensuite nourrir les analyses de CV.",
    ],
    signup: { href: "/inscription-conseiller", label: "Créer un compte conseiller" },
    signin: { href: "/connexion", label: "Se connecter" },
  },
  data: {
    title: "Vos données",
    points: [
      "Vos réponses, votre phrase et votre portrait sont chiffrés.",
      "Votre phrase et le premier jet du portrait sont rédigés par une IA ; le portrait n’est remis qu’après la relecture de votre conseiller.",
      "Vous pouvez effacer votre voyage à tout moment. L’effacement retire aussi ce que vos analyses de CV en avaient repris.",
    ],
    link: { href: "/confidentialite", label: "Lire la politique de confidentialité" },
  },
  faq: {
    title: "Questions",
    items: [
      {
        q: "Faut-il un conseiller ?",
        a: "Pas pour la session 0 : elle se fait en autonomie, en cinq minutes. Les sessions 1 à 5 se font avec un conseiller, qui vous donne un code.",
      },
      {
        q: "Je n’ai pas de conseiller.",
        a: "Commencez par la session 0. Pour la suite, parlez-en à la structure qui vous accompagne : Mission Locale, Cap Emploi, France Travail ou un conseil en évolution professionnelle.",
      },
      {
        q: "Est-ce un test de personnalité ?",
        a: "Non. Le voyage ne vous classe pas et ne vous donne pas de score. Il vous aide à poser des mots sur ce que vous savez déjà.",
      },
      {
        q: "Combien de temps ça prend ?",
        a: "Cinq minutes pour la session 0. Pour les suivantes, le rythme se décide avec votre conseiller.",
      },
      { q: "Faut-il un compte ?", a: "Oui, pour garder vos réponses d’une séance à l’autre. La création du compte est gratuite." },
      {
        q: "Puis-je tout effacer ?",
        a: "Oui, à tout moment. L’effacement retire aussi ce que vos analyses de CV en avaient repris.",
      },
    ],
  },
  final: {
    title: "Votre parcours a des choses à dire. Aidez-le à les dire.",
    bridge: { text: "Vous avez déjà une cible ?", link: { app: "cv", label: "Analyser mon CV" } },
  },
})
```

- [ ] **Step 10: Write the shared footer copy**

`frontend/src/components/landing/copy/shared.ts`:

```ts
import { typeset } from "../../../lib/typeset.ts"
import type { FooterCopy } from "./types"

/** The landings' footer, also on the legal pages of cv. and voyage. (landings
 *  spec, decision 13). */
export const footerCopy = typeset<FooterCopy>({
  label: "Liens du pied de page",
  tagline: "Pour les conseillers et les personnes qu’ils accompagnent.",
  apps: [
    { app: "cv", label: "J’ai une cible" },
    { app: "voyage", label: "Le voyage" },
  ],
  links: [
    { href: "/mentions-legales", label: "Mentions légales" },
    { href: "/confidentialite", label: "Confidentialité" },
    { href: "/cgv", label: "CGV" },
  ],
  signIn: { href: "/connexion", label: "Se connecter" },
  copyright: "© 2026 neoori",
})
```

- [ ] **Step 11: Run the tests and watch them pass**

Run: `(cd frontend && npm test)`
Expected: PASS (26 tests). If a typography test fails, the message quotes the
string. Fix it in the copy file (a `'` that should be `’`), never in the test.

- [ ] **Step 12: Run every check, then commit**

Run: `(cd frontend && npx tsc --noEmit && npm run lint; npm run build)`
Expected: `tsc` silent, lint at most 11 problems, build succeeds.

```bash
git add frontend/src/lib/typeset.ts frontend/src/lib/typeset.test.ts frontend/src/lib/landing-copy.test.ts frontend/src/components/landing/copy
git commit -m "feat(landing): the copy of both landings, with French typography

Landings spec decisions 31-33, Appendix A. One file per app (the PM reviews
these), typeset() for the no-break spaces, and a test for CLAUDE.md's copy
rules: banned words, the cible never only a job, no score, no claim about
where data is processed, prices hidden until the PM agrees.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The landing shell — stylesheet, animated logo, menu, footer, and the legal pages

Decisions 11, 13, 16–19 and Appendix B. After this task:
- Both landings show their menu (the logo draws itself the first time in a
  tab), a first block with the two doors, and the footer.
- The legal pages on cv. and voyage. use that app's menu and footer.

**Files:**
- Create: `frontend/src/components/landing/landing.css`
- Create: `frontend/src/lib/logo-motion.ts`, `frontend/src/lib/logo-motion.test.ts`
- Create: `frontend/src/lib/landing-nav.ts`, `frontend/src/lib/landing-nav.test.ts`
- Create: `frontend/src/components/landing/AnimatedLogo.tsx`
- Create: `frontend/src/components/landing/LandingNav.tsx`
- Create: `frontend/src/components/landing/LandingFooter.tsx`
- Create: `frontend/src/components/landing/WipeLink.tsx` (a plain link; Task 10 adds the wipe)
- Create: `frontend/src/components/landing/Doors.tsx`
- Modify: `frontend/src/app/accueil/cv/page.tsx`, `frontend/src/app/accueil/voyage/page.tsx`
- Modify: `frontend/src/app/(legal)/layout.tsx`

**Interfaces:**
- Consumes:
  - `useSite().landing()` and `landingHref()` (Task 2)
  - `LOGO_*` (Task 3)
  - `cvCopy`, `voyageCopy`, `footerCopy`, `NavCopy`, `DoorCopy`, `LandingApp`, `LinkCopy` (Task 4)
  - `homeFor` (existing `lib/home.ts`)
  - `useAuth` (existing `lib/auth.tsx`)
  - `currentSite` (existing `lib/site-server.ts`)
- Produces:
  - `shouldPlayLogo(storage: Pick<Storage, "getItem" | "setItem"> | null, reducedMotion: boolean): boolean`
  - `LOGO_PLAYED_KEY = "neoori:logo-played"`
  - `accountLink(role: "candidate" | "counselor" | "admin" | null, app: AppName): { href: string; kind: "home" | "signin" }`
  - `visibleLinks(links: LinkCopy[], showPrices: boolean): LinkCopy[]`
  - `<AnimatedLogo tone className />`
  - `<LandingNav app copy showPrices? placement />`, with `placement: "hero" | "page"`
  - `<LandingFooter app />` (async server component)
  - `<WipeLink href ring className>`, with `ring: "orange" | "peach"`
  - `<Doors primary secondary ring />`
  - the CSS classes `lp`, `lp-cv`, `lp-voy`, `lp-container`, `lp-label`,
    `lp-sub`, `lp-section`, `lp-section-head`, `lp-text-link`,
    `lp-bg-{white,cool,deep,dusk,dawn}`, `lp-btn`, `lp-btn-{primary,secondary,dark,line}`,
    `lp-doors`, `lp-door`, `lp-door-note`, `lp-rise`, `lp-reveal`, `lp-hero-copy`

- [ ] **Step 1: Write the failing tests for the two helpers**

`frontend/src/lib/logo-motion.test.ts`:

```ts
import { test } from "node:test"
import assert from "node:assert/strict"
import { LOGO_PLAYED_KEY, shouldPlayLogo } from "./logo-motion.ts"

function memory(): Pick<Storage, "getItem" | "setItem"> {
  const data = new Map<string, string>()
  return { getItem: (k) => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v) }
}

test("the logo draws once per tab session (landings spec, decision 19)", () => {
  const storage = memory()
  assert.equal(shouldPlayLogo(storage, false), true)
  assert.equal(storage.getItem(LOGO_PLAYED_KEY), "1")
  assert.equal(shouldPlayLogo(storage, false), false)
})

test("never under reduce motion (decision 23)", () => {
  assert.equal(shouldPlayLogo(memory(), true), false)
})

test("blocked storage still plays, and remembers nothing (Review Focus 5)", () => {
  const blocked = {
    getItem: () => { throw new Error("SecurityError") },
    setItem: () => { throw new Error("SecurityError") },
  }
  assert.equal(shouldPlayLogo(blocked, false), true)
  assert.equal(shouldPlayLogo(null, false), true)
})
```

`frontend/src/lib/landing-nav.test.ts`:

```ts
import { test } from "node:test"
import assert from "node:assert/strict"
import { accountLink, visibleLinks } from "./landing-nav.ts"

test("« Mon espace » leads each role to its own home on this host (Review Focus 4)", () => {
  assert.deepEqual(accountLink(null, "cv"), { href: "/connexion", kind: "signin" })
  assert.deepEqual(accountLink("candidate", "cv"), { href: "/espace", kind: "home" })
  assert.deepEqual(accountLink("candidate", "voyage"), { href: "/voyage", kind: "home" })
  assert.deepEqual(accountLink("counselor", "voyage"), { href: "/conseiller", kind: "home" })
  assert.deepEqual(accountLink("admin", "cv"), { href: "/admin", kind: "home" })
})

test("« Tarifs » leaves the menu while prices are hidden (decision 16)", () => {
  const links = [{ href: "/#a", label: "A" }, { href: "/#tarifs", label: "Tarifs", pricesOnly: true }]
  assert.deepEqual(visibleLinks(links, false).map((l) => l.label), ["A"])
  assert.deepEqual(visibleLinks(links, true).map((l) => l.label), ["A", "Tarifs"])
})
```

- [ ] **Step 2: Run them and watch them fail**

Run: `(cd frontend && npm test)`
Expected: FAIL with `Cannot find module …/lib/logo-motion.ts` and
`…/lib/landing-nav.ts`.

- [ ] **Step 3: Write the two helpers**

`frontend/src/lib/logo-motion.ts`:

```ts
export const LOGO_PLAYED_KEY = "neoori:logo-played"

/** Whether the landing's logo plays motion A now (landings spec, decision
 *  19): once per tab session, never under reduce motion. Blocked storage
 *  (private windows, some in-app browsers) plays and remembers nothing. */
export function shouldPlayLogo(
  storage: Pick<Storage, "getItem" | "setItem"> | null,
  reducedMotion: boolean,
): boolean {
  if (reducedMotion) return false
  if (!storage) return true
  try {
    if (storage.getItem(LOGO_PLAYED_KEY) === "1") return false
    storage.setItem(LOGO_PLAYED_KEY, "1")
  } catch {
    // Storage refused: play, remember nothing.
  }
  return true
}
```

`frontend/src/lib/landing-nav.ts`:

```ts
import type { User } from "@/types"
import type { LinkCopy } from "../components/landing/copy/types"
import type { AppName } from "./site"
import { homeFor } from "./home.ts"

/** The menu's account entry (landings spec, decision 11): « Mon espace »,
 *  leading to the person's home on this host by role, once signed in;
 *  « Se connecter » otherwise. */
export function accountLink(
  role: User["role"] | null,
  app: AppName,
): { href: string; kind: "home" | "signin" } {
  return role ? { href: homeFor(role, app), kind: "home" } : { href: "/connexion", kind: "signin" }
}

/** The menu's section links, without « Tarifs » while prices are hidden
 *  (decision 16). */
export function visibleLinks(links: LinkCopy[], showPrices: boolean): LinkCopy[] {
  return links.filter((link) => showPrices || !link.pricesOnly)
}
```

(`lib/home.ts` has only `import type` lines, so Node can load it through this
file.)

- [ ] **Step 4: Run the tests and watch them pass**

Run: `(cd frontend && npm test)`
Expected: PASS (31 tests).

- [ ] **Step 5: Write the stylesheet's first part**

`frontend/src/components/landing/landing.css`. Later tasks append to this
file.

```css
/* The cv. and voyage. landings (landings spec; values from Appendix B).
   Every class starts with lp- so nothing collides with Tailwind or the app's
   own classes. Imported by the two landing pages and the legal layout. */

.lp {
  --lp-navy: #1c3561;
  --lp-navy-2: #2b4677;
  --lp-ink-2: #56637b;
  --lp-line: rgba(28, 53, 97, 0.12);
  --lp-orange: #ea5624;
  --lp-primary: #c9491e;
  --lp-primary-hover: #b23f18;
  --lp-peach: #f7b394;
  --lp-peach-soft: #fdeee5;
  --lp-cool: #f4f6fa;
  --lp-deep: #22406f;
  --lp-dusk: #3a3f66;
  --lp-dawn: #f8f3ee;
  --lp-display: var(--font-jakarta), "Plus Jakarta Sans", system-ui, sans-serif;
  --lp-body: var(--font-inter), "Inter", system-ui, sans-serif;
  --lp-mono: var(--font-jetbrains), "JetBrains Mono", ui-monospace, monospace;
  --lp-house: cubic-bezier(0.22, 1, 0.36, 1);
  --lp-gutter: clamp(20px, 4vw, 40px);
  --lp-nav-h: 76px;
  font-family: var(--lp-body);
  font-size: 17px;
  line-height: 1.6;
}
.lp-cv { background: #ffffff; color: var(--lp-navy); }
.lp-voy { background: var(--lp-navy); color: #ffffff; }
.lp *, .lp *::before, .lp *::after { box-sizing: border-box; }
.lp a { color: inherit; }
.lp img, .lp canvas { display: block; max-width: 100%; }
.lp h1, .lp h2, .lp h3 { font-family: var(--lp-display); margin: 0; text-wrap: balance; }
.lp h1 { font-weight: 800; letter-spacing: -0.032em; line-height: 1.02; }
.lp h2 { font-weight: 700; letter-spacing: -0.024em; line-height: 1.12; font-size: clamp(1.7rem, 3vw, 2.5rem); }
.lp h3 { font-weight: 700; letter-spacing: -0.01em; line-height: 1.3; font-size: 1.12rem; }
.lp p { margin: 0; }
.lp ul, .lp ol { margin: 0; padding: 0; list-style: none; }
.lp :focus-visible { outline: 2px solid var(--lp-orange); outline-offset: 3px; border-radius: 6px; }

.lp-container { max-width: 1240px; margin-inline: auto; padding-inline: var(--lp-gutter); }
.lp-label { font: 500 0.74rem/1 var(--lp-mono); letter-spacing: 0.16em; text-transform: uppercase; }
.lp-cv .lp-label { color: var(--lp-primary); }
.lp-voy .lp-label { color: var(--lp-peach); }
.lp-sub { font-size: clamp(1.05rem, 1.45vw, 1.2rem); max-width: 46ch; text-wrap: pretty; }
.lp-cv .lp-sub { color: var(--lp-ink-2); }
.lp-voy .lp-sub { color: rgba(255, 255, 255, 0.82); }
.lp-section { padding-block: clamp(64px, 9vw, 112px); }
.lp-section-head { display: grid; gap: 10px; max-width: 60ch; margin-bottom: 32px; }
.lp-text-link { font-weight: 600; text-decoration: underline; text-underline-offset: 3px; }
.lp-hero-copy { position: relative; z-index: 4; display: grid; gap: 24px; justify-items: start; }

/* Section grounds: white and cool on cv.; deep, dusk, then dawn on voyage. */
.lp-bg-white { background: #ffffff; color: var(--lp-navy); }
.lp-bg-cool { background: var(--lp-cool); color: var(--lp-navy); }
.lp-bg-deep { background: var(--lp-deep); color: #ffffff; }
.lp-bg-dusk { background: var(--lp-dusk); color: #ffffff; }
.lp-bg-dawn { background: var(--lp-dawn); color: var(--lp-navy); }
.lp-bg-white .lp-label, .lp-bg-cool .lp-label, .lp-bg-dawn .lp-label { color: var(--lp-primary); }
.lp-voy .lp-bg-dawn .lp-label { color: #b4532a; }
.lp-bg-white .lp-section-head p, .lp-bg-cool .lp-section-head p, .lp-bg-dawn .lp-section-head p { color: var(--lp-ink-2); }
.lp-bg-deep .lp-section-head p, .lp-bg-dusk .lp-section-head p { color: rgba(255, 255, 255, 0.78); }

/* Menu */
.lp-nav { position: relative; z-index: 20; }
.lp-nav--hero.lp-voy { position: absolute; inset: 0 0 auto; background: transparent; }
.lp-nav--page.lp-cv { border-bottom: 1px solid var(--lp-line); }
.lp-nav-in { display: flex; align-items: center; gap: 28px; height: var(--lp-nav-h); }
.lp-logo-link { display: block; flex: none; font-size: 31px; line-height: 0; }
.lp-logo { display: block; height: 32px; width: auto; overflow: visible; }
.lp-nav-links { display: flex; gap: 26px; margin-left: auto; font: 500 0.95rem/1 var(--lp-body); }
.lp-nav-links a { text-decoration: none; opacity: 0.78; transition: opacity 0.2s; }
.lp-nav-links a:hover { opacity: 1; }
.lp-nav-actions { display: flex; align-items: center; gap: 16px; }
.lp-nav-signin { font: 600 0.95rem/1 var(--lp-body); text-decoration: none; padding: 12px 2px; }
.lp-nav-cross { font: 600 0.84rem/1 var(--lp-body); text-decoration: none; padding: 10px 14px; border-radius: 999px; display: inline-flex; gap: 6px; align-items: center; }
.lp-cv .lp-nav-cross { background: var(--lp-cool); color: var(--lp-navy); }
.lp-voy .lp-nav-cross { background: rgba(255, 255, 255, 0.1); color: #ffffff; }
.lp-nav-cross svg { width: 14px; height: 14px; }
.lp-nav-menu { display: none; width: 44px; height: 44px; border-radius: 12px; border: 1px solid var(--lp-line); background: transparent; color: inherit; align-items: center; justify-content: center; cursor: pointer; }
.lp-voy .lp-nav-menu { border-color: rgba(255, 255, 255, 0.25); }
.lp-nav-menu svg { width: 20px; height: 20px; }
.lp-menu { position: absolute; top: var(--lp-nav-h); left: 0; right: 0; display: grid; gap: 2px; padding: 12px var(--lp-gutter) 20px; font: 600 1.02rem/1.2 var(--lp-body); box-shadow: 0 18px 40px -24px rgba(28, 53, 97, 0.45); }
.lp-cv .lp-menu { background: #ffffff; border-top: 1px solid var(--lp-line); }
.lp-voy .lp-menu { background: var(--lp-navy); border-top: 1px solid rgba(255, 255, 255, 0.12); }
.lp-menu a { text-decoration: none; padding: 12px 0; }
@media (max-width: 960px) {
  .lp-nav-links, .lp-nav-cross { display: none; }
  .lp-nav-menu { display: inline-flex; }
  .lp-nav-actions { margin-left: auto; gap: 10px; }
}
@media (min-width: 961px) { .lp-menu { display: none; } }

/* The two doors and the buttons */
.lp-doors { display: grid; grid-template-columns: repeat(2, max-content); gap: 14px 20px; align-items: start; margin-top: 6px; }
.lp-door { display: grid; gap: 10px; justify-items: start; }
.lp-btn { font: 600 1rem/1 var(--lp-body); border-radius: 14px; padding: 17px 22px; min-height: 52px; border: 0; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; gap: 10px; transition: transform 0.2s var(--lp-house), background-color 0.2s, box-shadow 0.2s; }
.lp-btn:hover { transform: translateY(-1px); }
.lp-btn svg { width: 16px; height: 16px; flex: none; }
.lp-door-note { font-size: 0.86rem; line-height: 1.45; max-width: 25ch; }
.lp-cv .lp-door-note { color: var(--lp-ink-2); }
.lp-voy .lp-door-note { color: rgba(255, 255, 255, 0.66); }
.lp-cv .lp-btn-primary { background: var(--lp-primary); color: #ffffff; box-shadow: 0 12px 26px -16px rgba(201, 73, 30, 0.8); }
.lp-cv .lp-btn-primary:hover { background: var(--lp-primary-hover); }
.lp-cv .lp-btn-secondary { background: #ffffff; color: var(--lp-navy); box-shadow: inset 0 0 0 1.5px rgba(28, 53, 97, 0.22); }
.lp-cv .lp-btn-secondary:hover { box-shadow: inset 0 0 0 1.5px rgba(28, 53, 97, 0.5); }
.lp-voy .lp-btn-primary { background: var(--lp-peach); color: var(--lp-navy); box-shadow: 0 14px 30px -16px rgba(247, 179, 148, 0.6); }
.lp-voy .lp-btn-primary:hover { background: #f9c2a8; }
.lp-voy .lp-btn-secondary { background: transparent; color: #ffffff; box-shadow: inset 0 0 0 1.5px rgba(255, 255, 255, 0.38); }
.lp-voy .lp-btn-secondary:hover { box-shadow: inset 0 0 0 1.5px rgba(255, 255, 255, 0.75); }
.lp-voy .lp-bg-dawn .lp-btn-primary { background: var(--lp-navy); color: #ffffff; box-shadow: none; }
.lp-voy .lp-bg-dawn .lp-btn-secondary { color: var(--lp-navy); box-shadow: inset 0 0 0 1.5px rgba(28, 53, 97, 0.25); }
.lp-btn-dark { background: var(--lp-navy); color: #ffffff; }
.lp-btn-line { background: transparent; color: var(--lp-navy); box-shadow: inset 0 0 0 1.5px rgba(28, 53, 97, 0.25); }
@media (max-width: 560px) {
  .lp-doors { grid-template-columns: minmax(0, 1fr); width: 100%; gap: 18px; }
  .lp-door { justify-items: stretch; }
  .lp-door-note { max-width: none; padding-left: 2px; }
}

/* Entrance and reveals (decisions 20–21). No JavaScript: a browser without
   scroll timelines (Firefox) simply shows the sections. */
.lp-rise > * { animation: lp-rise 0.8s var(--lp-house) both; animation-delay: calc(var(--i, 0) * 80ms + 220ms); }
@keyframes lp-rise { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: none; } }
@supports (animation-timeline: view()) {
  @media (prefers-reduced-motion: no-preference) {
    .lp-reveal { animation: lp-reveal linear both; animation-timeline: view(); animation-range: entry 0% cover 28%; }
  }
}
@keyframes lp-reveal { from { opacity: 0; transform: translateY(24px); } to { opacity: 1; transform: none; } }

/* Footer */
.lp-footer { background: var(--lp-navy); color: #ffffff; padding-block: 48px 40px; }
.lp-footer-in { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 24px 40px; align-items: start; }
.lp-footer-brand { display: grid; gap: 14px; font-size: 26px; justify-items: start; }
.lp-footer-brand p { font-size: 0.92rem; line-height: 1.5; color: rgba(255, 255, 255, 0.7); max-width: 36ch; }
.lp-footer-links { display: flex; flex-wrap: wrap; gap: 10px 22px; font-size: 0.92rem; }
.lp-footer-links a { text-decoration: none; color: rgba(255, 255, 255, 0.78); }
.lp-footer-links a:hover { color: #ffffff; }
.lp-footer-copy { grid-column: 1 / -1; font-size: 0.82rem; color: rgba(255, 255, 255, 0.5); border-top: 1px solid rgba(255, 255, 255, 0.12); padding-top: 18px; }
@media (max-width: 760px) { .lp-footer-in { grid-template-columns: minmax(0, 1fr); } }

@media (prefers-reduced-motion: reduce) {
  .lp-rise > * { animation: none; }
}
```

- [ ] **Step 6: Write `AnimatedLogo`**

`frontend/src/components/landing/AnimatedLogo.tsx`:

```tsx
"use client"

import { useEffect, useId, useRef } from "react"
import {
  LOGO_LETTERS, LOGO_NAVY, LOGO_OO, LOGO_OO_GRADIENT, LOGO_VIEWBOX,
} from "@/components/brand/logo-paths"
import { shouldPlayLogo } from "@/lib/logo-motion"

const MID = 47.24 // radius of the oo's mid-circle, in logo units
const C = 2 * Math.PI * MID
const RINGS = [
  { cx: 323.97, rotate: -90 }, // the left ring starts at 12 o'clock
  { cx: 418.45, rotate: 90 }, // the right ring starts at 6 o'clock
] as const

/** The logo with motion A, « Tracé » (landings spec, decision 19): the two
 *  rings draw, then n·e·r·i rise. Once per tab session, never under reduce
 *  motion. The resting state is the plain logo, so nothing is hidden when
 *  JavaScript is off or the motion is skipped. */
export function AnimatedLogo({ tone = "navy", className }: { tone?: "navy" | "light"; className?: string }) {
  const id = `alg${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`
  const ref = useRef<SVGSVGElement>(null)

  useEffect(() => {
    const svg = ref.current
    if (!svg) return
    let storage: Storage | null = null
    try {
      storage = window.sessionStorage
    } catch {
      storage = null
    }
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    if (!shouldPlayLogo(storage, reduced)) return
    const draw = [{ strokeDashoffset: `${C}px` }, { strokeDashoffset: "0px" }]
    const animations: Animation[] = []
    svg.querySelectorAll<SVGCircleElement>("[data-ring]").forEach((ring, i) => {
      animations.push(ring.animate(draw, { duration: 900, delay: i * 160, easing: "cubic-bezier(.65,0,.35,1)", fill: "both" }))
    })
    svg.querySelectorAll<SVGPathElement>("[data-letter]").forEach((letter, i) => {
      animations.push(letter.animate(
        [{ transform: "translateY(28px)", opacity: 0 }, { transform: "none", opacity: 1 }],
        { duration: 620, delay: 560 + i * 70, easing: "cubic-bezier(.16,1,.3,1)", fill: "both" },
      ))
    })
    return () => animations.forEach((a) => a.cancel())
  }, [])

  return (
    <svg ref={ref} viewBox={`0 0 ${LOGO_VIEWBOX.w} ${LOGO_VIEWBOX.h}`} role="img" aria-label="neoori" className={className}>
      <defs>
        <linearGradient id={`${id}-g`} x1={LOGO_OO_GRADIENT.x1} y1="0" x2={LOGO_OO_GRADIENT.x2} y2="0" gradientUnits="userSpaceOnUse">
          {LOGO_OO_GRADIENT.stops.map(([offset, color]) => <stop key={offset} offset={offset} stopColor={color} />)}
        </linearGradient>
        <mask id={`${id}-m`} maskUnits="userSpaceOnUse" x="0" y="-40" width={LOGO_VIEWBOX.w} height="260">
          {RINGS.map((ring) => (
            <circle
              key={ring.cx}
              data-ring=""
              cx={ring.cx}
              cy="108.21"
              r={MID}
              fill="none"
              stroke="#fff"
              strokeWidth="44"
              strokeDasharray={`${C} ${C}`}
              strokeDashoffset="0"
              transform={`rotate(${ring.rotate} ${ring.cx} 108.21)`}
            />
          ))}
        </mask>
      </defs>
      <g fill={tone === "light" ? "#ffffff" : LOGO_NAVY}>
        {(["n", "e", "r", "i"] as const).map((key) => (
          <path key={key} data-letter="" d={LOGO_LETTERS[key]} style={{ transformBox: "view-box" }} />
        ))}
      </g>
      <path d={LOGO_OO} fill={`url(#${id}-g)`} mask={`url(#${id}-m)`} />
    </svg>
  )
}
```

- [ ] **Step 7: Write `LandingNav`**

`frontend/src/components/landing/LandingNav.tsx`:

```tsx
"use client"

import { useState } from "react"
import { ArrowUpRight, Menu, X } from "lucide-react"
import { useAuth } from "@/lib/auth"
import { AppLink, useSite } from "@/lib/site-context"
import { accountLink, visibleLinks } from "@/lib/landing-nav"
import { Logo } from "@/components/brand/Logo"
import { AnimatedLogo } from "./AnimatedLogo"
import type { LandingApp, NavCopy } from "./copy/types"

/** The landings' menu (landings spec, decisions 11, 16, 17). « Mon espace »
 *  replaces « Se connecter » once the session is known. On a landing it sits
 *  on the hero, with the logo's motion (`placement="hero"`); on the legal
 *  pages it is a plain bar (`placement="page"`). */
export function LandingNav({
  app,
  copy,
  showPrices = true,
  placement,
}: {
  app: LandingApp
  copy: NavCopy
  showPrices?: boolean
  placement: "hero" | "page"
}) {
  const { user, loading } = useAuth()
  const site = useSite()
  const [open, setOpen] = useState(false)
  const links = visibleLinks(copy.links, showPrices)
  const account = accountLink(loading ? null : (user?.role ?? null), app)
  const accountLabel = account.kind === "home" ? copy.myHome : copy.signIn
  const tone = app === "voyage" ? "light" : "navy"
  const crossHref = site.landing(copy.cross.app)
  const close = () => setOpen(false)

  return (
    <header className={`lp ${app === "cv" ? "lp-cv" : "lp-voy"} lp-nav lp-nav--${placement}`}>
      <div className="lp-container lp-nav-in">
        <AppLink href="/" className="lp-logo-link" aria-label={copy.home}>
          {placement === "hero" ? <AnimatedLogo tone={tone} className="lp-logo" /> : <Logo tone={tone} />}
        </AppLink>
        <nav className="lp-nav-links" aria-label="Sections">
          {links.map((link) => (
            <AppLink key={link.href} href={link.href}>{link.label}</AppLink>
          ))}
        </nav>
        <div className="lp-nav-actions">
          <AppLink href={account.href} className="lp-nav-signin">{accountLabel}</AppLink>
          <a href={crossHref} className="lp-nav-cross">
            {copy.cross.label} <ArrowUpRight aria-hidden="true" />
          </a>
          <button
            type="button"
            className="lp-nav-menu"
            aria-expanded={open}
            aria-controls={`lp-menu-${app}`}
            aria-label={open ? copy.closeMenu : copy.openMenu}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
          </button>
        </div>
      </div>
      {open ? (
        <div id={`lp-menu-${app}`} className="lp-menu">
          {links.map((link) => (
            <AppLink key={link.href} href={link.href} onClick={close}>{link.label}</AppLink>
          ))}
          <AppLink href={account.href} onClick={close}>{accountLabel}</AppLink>
          <a href={crossHref} onClick={close}>{copy.cross.label}</a>
        </div>
      ) : null}
    </header>
  )
}
```

- [ ] **Step 8: Write `LandingFooter`, `WipeLink` and `Doors`**

`frontend/src/components/landing/LandingFooter.tsx`:

```tsx
import { AppLink } from "@/lib/site-context"
import { currentSite } from "@/lib/site-server"
import { landingHref } from "@/lib/site"
import { Logo } from "@/components/brand/Logo"
import { footerCopy } from "./copy/shared"
import type { LandingApp } from "./copy/types"

/** The landings' footer, also on the legal pages of cv. and voyage.
 *  (landings spec, decision 13). */
export async function LandingFooter({ app }: { app: LandingApp }) {
  const site = await currentSite()
  return (
    <footer className={`lp ${app === "cv" ? "lp-cv" : "lp-voy"} lp-footer`}>
      <div className="lp-container lp-footer-in">
        <div className="lp-footer-brand">
          <Logo tone="light" />
          <p>{footerCopy.tagline}</p>
        </div>
        <nav aria-label={footerCopy.label} className="lp-footer-links">
          {footerCopy.apps.map((item) => (
            <a key={item.app} href={landingHref(item.app, site)}>{item.label}</a>
          ))}
          {footerCopy.links.map((link) => (
            <AppLink key={link.href} href={link.href}>{link.label}</AppLink>
          ))}
          <AppLink href={footerCopy.signIn.href}>{footerCopy.signIn.label}</AppLink>
        </nav>
        <p className="lp-footer-copy">{footerCopy.copyright}</p>
      </div>
    </footer>
  )
}
```

`frontend/src/components/landing/WipeLink.tsx`:

```tsx
"use client"

import type { ReactNode } from "react"
import { AppLink } from "@/lib/site-context"

/** The landing's main button. The ∞ wipe (landings spec, decision 22) comes
 *  on top of this link; without JavaScript it stays a plain link. */
export function WipeLink({
  href,
  ring: _ring,
  className,
  children,
}: {
  href: string
  ring: "orange" | "peach"
  className?: string
  children: ReactNode
}) {
  return <AppLink href={href} className={className}>{children}</AppLink>
}
```

`frontend/src/components/landing/Doors.tsx`:

```tsx
import { ArrowRight } from "lucide-react"
import { WipeLink } from "./WipeLink"
import type { DoorCopy } from "./copy/types"

/** The hero's two doors (landings spec, ruling 5): the person's, with the ∞
 *  wipe, and « Je suis conseiller », which scrolls to the advisors section. */
export function Doors({ primary, secondary, ring }: { primary: DoorCopy; secondary: DoorCopy; ring: "orange" | "peach" }) {
  return (
    <div className="lp-doors">
      <div className="lp-door">
        <WipeLink href={primary.href} ring={ring} className="lp-btn lp-btn-primary">
          {primary.label} <ArrowRight aria-hidden="true" />
        </WipeLink>
        <p className="lp-door-note">{primary.note}</p>
      </div>
      <div className="lp-door">
        <a href={secondary.href} className="lp-btn lp-btn-secondary">{secondary.label}</a>
        <p className="lp-door-note">{secondary.note}</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 9: Put the shell on both landings**

Replace `frontend/src/app/accueil/cv/page.tsx` with:

```tsx
import "@/components/landing/landing.css"
import { LandingNav } from "@/components/landing/LandingNav"
import { LandingFooter } from "@/components/landing/LandingFooter"
import { Doors } from "@/components/landing/Doors"
import { cvCopy } from "@/components/landing/copy/cv"

// The cv. landing, served at cv.DOMAIN/ by the proxy's rewrite (landings spec,
// decision 8). Task 6 of the plan fills in the sections.
export default function CvLandingPage() {
  return (
    <div className="lp lp-cv">
      <LandingNav app="cv" copy={cvCopy.nav} showPrices={cvCopy.showPrices} placement="hero" />
      <main>
        <section className="lp-section">
          <div className="lp-container lp-hero-copy">
            <span className="lp-label">{cvCopy.hero.label}</span>
            <h1>{cvCopy.hero.title}</h1>
            <p className="lp-sub">{cvCopy.hero.sub}</p>
            <Doors primary={cvCopy.hero.primary} secondary={cvCopy.hero.secondary} ring="orange" />
          </div>
        </section>
      </main>
      <LandingFooter app="cv" />
    </div>
  )
}
```

Replace `frontend/src/app/accueil/voyage/page.tsx` with:

```tsx
import "@/components/landing/landing.css"
import { LandingNav } from "@/components/landing/LandingNav"
import { LandingFooter } from "@/components/landing/LandingFooter"
import { Doors } from "@/components/landing/Doors"
import { voyageCopy } from "@/components/landing/copy/voyage"

// The voyage. landing, served at voyage.DOMAIN/ by the proxy's rewrite
// (landings spec, decision 8). Task 7 of the plan fills in the sections.
export default function VoyageLandingPage() {
  return (
    <div className="lp lp-voy">
      <LandingNav app="voyage" copy={voyageCopy.nav} placement="hero" />
      <main>
        <section className="lp-section" style={{ paddingTop: "calc(var(--lp-nav-h) + 48px)" }}>
          <div className="lp-container lp-hero-copy">
            <span className="lp-label">{voyageCopy.hero.label}</span>
            <h1>{voyageCopy.hero.title}</h1>
            <p className="lp-sub">{voyageCopy.hero.sub}</p>
            <Doors primary={voyageCopy.hero.primary} secondary={voyageCopy.hero.secondary} ring="peach" />
          </div>
        </section>
      </main>
      <LandingFooter app="voyage" />
    </div>
  )
}
```

- [ ] **Step 10: The legal pages take the host's menu and footer (decision 13)**

Replace `frontend/src/app/(legal)/layout.tsx` with:

```tsx
import "@/components/landing/landing.css"
import type { ReactNode } from "react"
import { SiteNav } from "@/components/layout/SiteNav"
import { SiteFooter } from "@/components/layout/SiteFooter"
import { LandingNav } from "@/components/landing/LandingNav"
import { LandingFooter } from "@/components/landing/LandingFooter"
import { cvCopy } from "@/components/landing/copy/cv"
import { voyageCopy } from "@/components/landing/copy/voyage"
import { currentSite } from "@/lib/site-server"

// On cv. and voyage. the legal pages wear that app's menu and footer (landings
// spec, decision 13): SiteNav's links are anchors on the root landing, which
// those hosts no longer show at "/".
export default async function LegalLayout({ children }: { children: ReactNode }) {
  const { app } = await currentSite()
  const landing = app === "cv" || app === "voyage" ? app : null
  return (
    <div className="min-h-screen overflow-x-clip bg-background">
      {landing ? (
        <LandingNav
          app={landing}
          copy={landing === "cv" ? cvCopy.nav : voyageCopy.nav}
          showPrices={cvCopy.showPrices}
          placement="page"
        />
      ) : (
        <SiteNav />
      )}

      <main
        className="mx-auto max-w-[760px] animate-fade-up px-5 py-14 text-[15px] leading-[1.75] text-navy-ink sm:px-8
        [&_h1]:mb-3 [&_h1]:font-display [&_h1]:text-3xl [&_h1]:font-extrabold [&_h1]:tracking-tight [&_h1]:text-navy md:[&_h1]:text-4xl
        [&_h1+p]:mb-10 [&_h1+p]:font-mono [&_h1+p]:text-[11px] [&_h1+p]:uppercase [&_h1+p]:tracking-[0.12em] [&_h1+p]:text-orange-dark
        [&_h2]:mb-3 [&_h2]:mt-12 [&_h2]:border-b [&_h2]:border-border [&_h2]:pb-2 [&_h2]:font-display [&_h2]:text-lg [&_h2]:font-bold [&_h2]:tracking-tight [&_h2]:text-navy
        [&_p]:mb-4 [&_p]:text-muted-foreground
        [&_ul]:mb-4 [&_ul]:list-none [&_ul]:space-y-2 [&_ul]:pl-0
        [&_li]:relative [&_li]:pl-5 [&_li]:text-muted-foreground
        [&_li]:before:absolute [&_li]:before:left-0 [&_li]:before:top-[0.62em] [&_li]:before:h-1.5 [&_li]:before:w-1.5 [&_li]:before:rounded-[2px] [&_li]:before:bg-orange [&_li]:before:content-['']
        [&_strong]:font-semibold [&_strong]:text-navy
        [&_a]:text-orange-dark [&_a]:underline [&_a]:underline-offset-2 hover:[&_a]:no-underline"
      >
        <div className="rounded-2xl bg-card px-7 py-9 ring-1 ring-foreground/10 shadow-soft md:px-10 md:py-11">
          {children}
        </div>
      </main>

      {landing ? <LandingFooter app={landing} /> : <SiteFooter />}
    </div>
  )
}
```

(The `<main>` and its classes are today's, unchanged.)

- [ ] **Step 11: Run every check**

Run: `(cd frontend && npm test && npx tsc --noEmit && npm run lint; npm run build)`
Expected: 31 tests pass, `tsc` silent, lint at most 11 problems, build
succeeds.

- [ ] **Step 12: Look at it**

Run: `docker compose up -d`. In Chrome:

1. http://cv.neoori.localhost:8080/: the menu, the logo drawing itself (rings,
   then letters), the headline, two doors and a navy footer. Reload: the logo
   is still (same tab session). Open a new tab on the same URL: it draws again.
2. http://voyage.neoori.localhost:8080/: the same on navy, white letters.
3. Sign in as a candidate, reload cv.: « Mon espace » leads to `/espace`; on
   voyage. it leads to `/voyage`. As a counselor, `/conseiller`.
4. At 390 px wide (DevTools device toolbar): the menu button opens the list
   and every entry closes it.
5. http://cv.neoori.localhost:8080/cgv shows the cv. menu (plain bar) and
   footer; http://voyage.neoori.localhost:8080/cgv shows a navy bar.
   http://neoori.localhost:8080/cgv still redirects to cv.
6. DevTools > Rendering > « prefers-reduced-motion: reduce »: the logo does not
   move, and the headline appears without rising.

- [ ] **Step 13: Commit**

```bash
git add frontend/src/components/landing frontend/src/lib/logo-motion.ts frontend/src/lib/logo-motion.test.ts \
  frontend/src/lib/landing-nav.ts frontend/src/lib/landing-nav.test.ts frontend/src/app/accueil "frontend/src/app/(legal)/layout.tsx"
git commit -m "feat(landing): the shell of both landings, and the legal pages' menu

Landings spec decisions 11, 13 and 16-19: lp- stylesheet, logo motion A once
per tab session (never under reduce motion), the menu with « Mon espace »
by role and « Tarifs » hidden while prices are, the footer, and the two
doors. On cv. and voyage. the legal pages take that app's menu and footer.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The cv. landing

Decisions 15–16, ruling 6, Appendix A (cv.) and Appendix B. The whole page,
including its metadata. The 3D box is an empty placeholder until Task 9.

**Files:**
- Modify: `frontend/src/types/index.ts` (`SECTION_TITLES` gains §10 and §11)
- Create: `frontend/src/lib/report-tiers.ts`, `frontend/src/lib/report-tiers.test.ts`
- Create: `frontend/src/components/landing/CvHero.tsx`
- Create: `frontend/src/components/landing/ReportIndex.tsx`
- Create: `frontend/src/components/landing/CardGrid.tsx`
- Create: `frontend/src/components/landing/AdvisorsSection.tsx`
- Create: `frontend/src/components/landing/Pricing.tsx`
- Create: `frontend/src/components/landing/DataSection.tsx`
- Create: `frontend/src/components/landing/Faq.tsx`
- Create: `frontend/src/components/landing/FinalCall.tsx`
- Modify: `frontend/src/components/landing/landing.css` (append)
- Modify: `frontend/src/app/accueil/cv/page.tsx`

**Interfaces:**
- Consumes: Tasks 2–5.
- Produces:
  - `REPORT_TIERS: Tier[]`, with `Tier = { id: "free" | "complet" | "premium"; rows: { key; mark; title }[] }`
  - `type Bg = "white" | "cool" | "deep" | "dusk" | "dawn"`, exported from `CardGrid.tsx`
  - `<CvHero copy object>{band}</CvHero>`, where the section has `id="lp-cv-hero"`
  - `<ReportIndex copy />`
  - `<CardGrid id title intro? items layout bg note? />`, with `layout: "steps" | "grid"` and items `{ title, text, action?: ReactNode }`
  - `<AdvisorsSection copy bg />`
  - `<Pricing copy cta />`
  - `<DataSection copy bg />`
  - `<Faq copy bg />` (async)
  - `<FinalCall copy primary secondary ring bg />` (async)

- [ ] **Step 1: Write the failing test that ties the landing to the real report**

`frontend/src/lib/report-tiers.test.ts`:

```ts
import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { REPORT_TIERS } from "./report-tiers.ts"

// backend/app/services/section_registry.py, parcours 1:  _s("key", "Title"[, tiers=…])
const registry = readFileSync(new URL("../../../backend/app/services/section_registry.py", import.meta.url), "utf8")
const start = registry.indexOf("_P1 = [")
const p1 = registry.slice(start, registry.indexOf("\n]", start))
const backend = new Map(
  [...p1.matchAll(/_s\("(\w+)", "([^"]+)"(?:, tiers=(\w+|\(FREE,\)))?/g)].map((m) => [
    m[1],
    { title: m[2].replace(/'/g, "’"), tiers: m[3] ?? "ALL_TIERS" },
  ]),
)

test("the landing lists the report's real sections, in the backend's tiers (landings spec, decision 16)", () => {
  const allowed: Record<string, string[]> = { free: ["ALL_TIERS", "(FREE,)"], complet: ["PAID_UP"], premium: ["PREMIUM_ONLY"] }
  const seen = new Set<string>()
  for (const tier of REPORT_TIERS) {
    for (const row of tier.rows) {
      const entry = backend.get(row.key)
      assert.ok(entry, `§${row.key} is not in section_registry.py`)
      assert.equal(row.title, entry.title)
      assert.ok(allowed[tier.id].includes(entry.tiers), `§${row.key}: ${entry.tiers} in the backend, ${tier.id} on the landing`)
      seen.add(row.key)
    }
  }
  assert.deepEqual([...backend.keys()].filter((key) => !seen.has(key)), [])
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `(cd frontend && npm test)`
Expected: FAIL with `Cannot find module …/lib/report-tiers.ts`.

- [ ] **Step 3: Add §10 and §11 to `SECTION_TITLES`, then write `report-tiers.ts`**

In `frontend/src/types/index.ts`, inside `SECTION_TITLES`, after the line
`"9": "Proposition de CV retravaillé",` add:

```ts
  "10": "Préparation à l'entretien",
  "11": "Questions difficiles",
```

(Straight apostrophes, like the rest of the map and the backend. The landing
turns them into `’`. `debloquer/page.tsx` reads only the keys it lists, so
nothing else changes.)

`frontend/src/lib/report-tiers.ts`:

```ts
import { SECTION_TITLES } from "../types/index.ts"

/** The report's sections by tier, for the cv. landing (landings spec,
 *  decision 16). Titles are the report's own (SECTION_TITLES), with
 *  typographic apostrophes; report-tiers.test.ts checks them, and their tiers,
 *  against the backend's section_registry.py. */
export type TierId = "free" | "complet" | "premium"

export interface TierRow {
  key: string
  mark: string
  title: string
}

export interface Tier {
  id: TierId
  rows: TierRow[]
}

const rows = (keys: string[]): TierRow[] =>
  keys.map((key) => ({ key, mark: `§${key}`, title: SECTION_TITLES[key].replace(/'/g, "’") }))

export const REPORT_TIERS: Tier[] = [
  { id: "free", rows: [...rows(["1", "2", "3"]), { key: "verdict", mark: "✓", title: "Verdict" }] },
  { id: "complet", rows: rows(["4", "5", "6", "7", "8", "9"]) },
  { id: "premium", rows: rows(["10", "11"]) },
]
```

- [ ] **Step 4: Run the test and watch it pass**

Run: `(cd frontend && npm test)`
Expected: PASS (32 tests).

- [ ] **Step 5: Append the cv. styles to `landing.css`**

Append to `frontend/src/components/landing/landing.css`:

```css
/* cv. hero, direction 2 « Le rapport en index » (ruling 6) */
.lp-cv-hero { position: relative; padding-top: clamp(24px, 6vw, 64px); }
.lp-cv-hero-in { position: relative; display: grid; gap: 26px; justify-items: start; }
.lp-cv-hero h1 { font-size: clamp(2.8rem, 7vw, 6.2rem); max-width: 10ch; letter-spacing: -0.042em; line-height: 0.98; }
.lp-cv-object { position: absolute; z-index: 3; right: -1%; top: -2%; width: min(44vw, 620px); aspect-ratio: 1 / 1.12; pointer-events: none; }
.lp-index { position: relative; margin-top: clamp(56px, 8vw, 104px); background: var(--lp-cool); padding-block: clamp(40px, 6vw, 64px) clamp(48px, 7vw, 80px); }
.lp-index-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px 24px; margin-bottom: 28px; }
.lp-index-head h2 { font-size: clamp(1.4rem, 2.2vw, 1.8rem); }
.lp-index-head p { color: var(--lp-ink-2); font-size: 0.95rem; }
.lp-tiers { display: grid; grid-template-columns: 1.15fr 1.45fr 1fr; gap: 20px; }
.lp-tier { background: #ffffff; border-radius: 20px; padding: 22px 24px 24px; display: grid; gap: 14px; align-content: start; box-shadow: 0 1px 2px rgba(28, 53, 97, 0.05), 0 16px 34px -24px rgba(28, 53, 97, 0.3); }
.lp-tier-name { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.lp-cv .lp-tier-name .lp-label { color: var(--lp-navy); }
.lp-tag { font: 600 0.75rem/1 var(--lp-body); border-radius: 999px; padding: 6px 10px; }
.lp-tag--free { background: #e3f2ec; color: #1d6b53; }
.lp-tag--complet { background: var(--lp-peach-soft); color: #9a3f19; }
.lp-tag--premium { background: #e9edf6; color: var(--lp-navy); }
.lp-tier ol { display: grid; gap: 9px; }
.lp-tier li { display: grid; grid-template-columns: 2.6em minmax(0, 1fr); gap: 6px; font: 500 0.97rem/1.35 var(--lp-body); }
.lp-tier li b { font: 700 0.8rem/1.7 var(--lp-mono); color: var(--lp-orange); }
@media (max-width: 900px) {
  .lp-cv-hero { padding-top: 0; }
  .lp-cv-hero-in { gap: 22px; }
  .lp-cv-hero h1 { font-size: clamp(2.3rem, 10.5vw, 3.4rem); letter-spacing: -0.036em; line-height: 1.02; }
  .lp-cv-object { position: relative; order: -1; right: auto; top: auto; justify-self: stretch; width: auto; height: clamp(300px, 86vw, 420px); aspect-ratio: auto; margin-inline: calc(var(--lp-gutter) * -1); background: radial-gradient(95% 85% at 50% 28%, #ffffff 0%, #eef2f8 68%, #e6ebf3 100%); }
  .lp-index { margin-top: 48px; padding-block: 44px 56px; }
  /* On phones the tiers become one vertical line, like the voyage. path. */
  .lp-tiers { grid-template-columns: minmax(0, 1fr); gap: 0; position: relative; padding-left: 30px; }
  .lp-tiers::before { content: ""; position: absolute; left: 7px; top: 8px; bottom: 30px; width: 1px; background: linear-gradient(to bottom, var(--lp-orange), rgba(28, 53, 97, 0.28) 45%, rgba(28, 53, 97, 0.18)); }
  .lp-tier { position: relative; background: transparent; box-shadow: none; border-radius: 0; padding: 0 0 26px; gap: 12px; }
  .lp-tier::before { content: ""; position: absolute; left: -30px; top: 1px; width: 15px; height: 15px; border-radius: 50%; background: var(--lp-navy); box-shadow: 0 0 0 5px var(--lp-cool); }
  .lp-tier--free::before { background: var(--lp-orange); box-shadow: 0 0 0 5px var(--lp-cool), 0 0 22px 6px rgba(234, 86, 36, 0.32); }
  .lp-tier--premium::before { background: var(--lp-cool); box-shadow: 0 0 0 5px var(--lp-cool), inset 0 0 0 2px var(--lp-navy); }
  .lp-tier-name { justify-content: flex-start; gap: 12px; }
  .lp-tier ol { gap: 8px; }
  .lp-tier li { font-size: 0.95rem; }
}

/* Steps: an ordered sequence, numbered, joined by a line. */
.lp-steps { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 28px; counter-reset: lp-step; }
.lp-steps.lp-cols-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.lp-steps > li { counter-increment: lp-step; position: relative; display: grid; gap: 10px; align-content: start; padding-top: 56px; }
.lp-steps > li::before { content: counter(lp-step); position: absolute; top: 0; left: 0; width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; font: 700 0.95rem/1 var(--lp-mono); background: var(--lp-peach-soft); color: var(--lp-primary); }
.lp-steps > li::after { content: ""; position: absolute; top: 20px; left: 52px; right: -16px; height: 1px; background: var(--lp-line); }
.lp-steps > li:last-child::after { display: none; }
.lp-steps p { color: var(--lp-ink-2); }
/* Grid: a few cards side by side. */
.lp-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.lp-card { border-radius: 20px; padding: 24px 26px 26px; display: grid; gap: 10px; align-content: start; }
.lp-bg-white .lp-card, .lp-bg-dawn .lp-card { background: var(--lp-cool); }
.lp-bg-cool .lp-card { background: #ffffff; box-shadow: 0 1px 2px rgba(28, 53, 97, 0.05), 0 16px 34px -24px rgba(28, 53, 97, 0.3); }
.lp-bg-deep .lp-card, .lp-bg-dusk .lp-card { background: rgba(255, 255, 255, 0.06); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.12); }
.lp-card p, .lp-cards-note { color: var(--lp-ink-2); }
.lp-bg-deep .lp-card p, .lp-bg-dusk .lp-card p, .lp-bg-deep .lp-cards-note, .lp-bg-dusk .lp-cards-note,
.lp-bg-deep .lp-steps p, .lp-bg-dusk .lp-steps p { color: rgba(255, 255, 255, 0.78); }
.lp-bg-deep .lp-steps > li::before, .lp-bg-dusk .lp-steps > li::before { background: rgba(247, 179, 148, 0.16); color: var(--lp-peach); }
.lp-bg-deep .lp-steps > li::after, .lp-bg-dusk .lp-steps > li::after { background: rgba(255, 255, 255, 0.18); }
.lp-cards-note { margin-top: 24px; font-size: 0.95rem; }
@media (max-width: 900px) {
  .lp-steps, .lp-steps.lp-cols-4 { grid-template-columns: minmax(0, 1fr); gap: 22px; }
  .lp-steps > li { padding-top: 0; padding-left: 56px; min-height: 40px; }
  .lp-steps > li::after { top: 48px; left: 20px; right: auto; bottom: -14px; width: 1px; height: auto; }
  .lp-grid { grid-template-columns: minmax(0, 1fr); }
}

/* Pour les conseillers */
.lp-advisors-in { display: grid; grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr); gap: clamp(28px, 5vw, 72px); align-items: start; }
.lp-advisors h2 { max-width: 18ch; margin-top: 14px; }
.lp-advisors-links { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 26px; }
.lp-advisors ul { display: grid; }
.lp-advisors li { display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: 14px; padding-block: 18px; border-top: 1px solid var(--lp-line); font: 500 1.05rem/1.45 var(--lp-body); }
.lp-advisors li svg { width: 22px; height: 22px; color: var(--lp-orange); margin-top: 2px; }
@media (max-width: 900px) { .lp-advisors-in { grid-template-columns: minmax(0, 1fr); } }

/* Tarifs */
.lp-plans { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; }
.lp-plan { background: #ffffff; border-radius: 20px; padding: 24px; display: grid; gap: 8px; align-content: start; box-shadow: 0 1px 2px rgba(28, 53, 97, 0.05), 0 16px 34px -24px rgba(28, 53, 97, 0.3); }
.lp-plan-price { font: 800 2.2rem/1 var(--lp-display); letter-spacing: -0.02em; }
.lp-prices .lp-btn { margin-top: 24px; }
@media (max-width: 900px) { .lp-plans { grid-template-columns: minmax(0, 1fr); } }

/* Vos données */
.lp-data-in { display: grid; gap: 22px; max-width: 760px; }
.lp-data ul { display: grid; gap: 14px; }
.lp-data li { display: grid; grid-template-columns: 26px minmax(0, 1fr); gap: 12px; font-size: 1.02rem; }
.lp-data li svg { width: 20px; height: 20px; color: var(--lp-orange); margin-top: 3px; }

/* Questions */
.lp-faq-in { display: grid; gap: 26px; max-width: 820px; }

/* Final call */
.lp-final-in { display: grid; gap: 24px; justify-items: center; text-align: center; }
.lp-final h2 { font-size: clamp(2rem, 4.4vw, 3.4rem); max-width: 18ch; }
.lp-final-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; }
.lp-final-bridge { color: var(--lp-ink-2); }
```

- [ ] **Step 6: Write the section components**

`frontend/src/components/landing/CvHero.tsx`:

```tsx
import type { CSSProperties, ReactNode } from "react"
import { Doors } from "./Doors"
import type { HeroCopy } from "./copy/types"

const at = (i: number) => ({ "--i": i }) as CSSProperties

/** cv. hero, direction 2 « Le rapport en index » (landings spec, ruling 6):
 *  the copy and the two doors, the 3D sheet (`object`), then the report band
 *  (`children`) that the sheet spills into. On phones the sheet comes first. */
export function CvHero({ copy, object, children }: { copy: HeroCopy; object: ReactNode; children: ReactNode }) {
  return (
    <section id="lp-cv-hero" className="lp-cv-hero" aria-labelledby="lp-h1">
      <div className="lp-container lp-cv-hero-in">
        <div className="lp-hero-copy lp-rise">
          <span className="lp-label" style={at(0)}>{copy.label}</span>
          <h1 id="lp-h1" style={at(1)}>{copy.title}</h1>
          <p className="lp-sub" style={at(2)}>{copy.sub}</p>
          <div style={at(3)}>
            <Doors primary={copy.primary} secondary={copy.secondary} ring="orange" />
          </div>
        </div>
        {object}
      </div>
      {children}
    </section>
  )
}
```

`frontend/src/components/landing/ReportIndex.tsx`:

```tsx
import { REPORT_TIERS } from "@/lib/report-tiers"
import type { CvCopy } from "./copy/types"

/** « Ce que contient le rapport » (landings spec, decision 16): three cards on
 *  desktop, one vertical line with a marker per tier on phones. */
export function ReportIndex({ copy }: { copy: CvCopy["report"] }) {
  return (
    <div className="lp-index" id="rapport">
      <div className="lp-container">
        <div className="lp-index-head lp-reveal">
          <h2>{copy.title}</h2>
          <p>{copy.intro}</p>
        </div>
        <div className="lp-tiers lp-reveal">
          {REPORT_TIERS.map((tier) => (
            <section key={tier.id} className={`lp-tier lp-tier--${tier.id}`} aria-label={copy.tiers[tier.id].tag}>
              <div className="lp-tier-name">
                <span className="lp-label">{copy.tiers[tier.id].name}</span>
                <span className={`lp-tag lp-tag--${tier.id}`}>{copy.tiers[tier.id].tag}</span>
              </div>
              <ol>
                {tier.rows.map((row) => (
                  <li key={row.key}>
                    <b>{row.mark}</b>
                    {row.title}
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}
```

`frontend/src/components/landing/CardGrid.tsx`:

```tsx
import type { ReactNode } from "react"
import type { ItemCopy } from "./copy/types"

/** A section's ground (Appendix B): white and cool on cv.; deep, dusk, then
 *  dawn on voyage. */
export type Bg = "white" | "cool" | "deep" | "dusk" | "dawn"

/** A titled section of short items: a numbered sequence (`steps`) or cards
 *  side by side (`grid`). */
export function CardGrid({
  id,
  title,
  intro,
  items,
  layout,
  bg,
  note,
}: {
  id: string
  title: string
  intro?: string
  items: (ItemCopy & { action?: ReactNode })[]
  layout: "steps" | "grid"
  bg: Bg
  note?: string
}) {
  const list = items.map((item) => (
    <li key={item.title} className={layout === "grid" ? "lp-card" : undefined}>
      <h3>{item.title}</h3>
      <p>{item.text}</p>
      {item.action}
    </li>
  ))
  return (
    <section id={id} className={`lp-section lp-bg-${bg}`} aria-labelledby={`${id}-h`}>
      <div className="lp-container lp-reveal">
        <div className="lp-section-head">
          <h2 id={`${id}-h`}>{title}</h2>
          {intro ? <p>{intro}</p> : null}
        </div>
        {layout === "steps" ? (
          <ol className={`lp-steps${items.length === 4 ? " lp-cols-4" : ""}`}>{list}</ol>
        ) : (
          <ul className="lp-grid">{list}</ul>
        )}
        {note ? <p className="lp-cards-note">{note}</p> : null}
      </div>
    </section>
  )
}
```

`frontend/src/components/landing/AdvisorsSection.tsx`:

```tsx
import { Check } from "lucide-react"
import { AppLink } from "@/lib/site-context"
import type { Bg } from "./CardGrid"
import type { AdvisorsCopy } from "./copy/types"

/** « Pour les conseillers », the target of « Je suis conseiller » (landings
 *  spec, decision 16). */
export function AdvisorsSection({ copy, bg }: { copy: AdvisorsCopy; bg: Bg }) {
  return (
    <section id="conseillers" className={`lp-section lp-advisors lp-bg-${bg}`} aria-labelledby="conseillers-h">
      <div className="lp-container lp-advisors-in lp-reveal">
        <div>
          <span className="lp-label">{copy.label}</span>
          <h2 id="conseillers-h">{copy.title}</h2>
          <div className="lp-advisors-links">
            <AppLink href={copy.signup.href} className="lp-btn lp-btn-dark">{copy.signup.label}</AppLink>
            <AppLink href={copy.signin.href} className="lp-btn lp-btn-line">{copy.signin.label}</AppLink>
          </div>
        </div>
        <ul>
          {copy.points.map((point) => (
            <li key={point}>
              <Check aria-hidden="true" />
              <span>{point}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
```

`frontend/src/components/landing/Pricing.tsx`:

```tsx
import { WipeLink } from "./WipeLink"
import type { CvCopy, DoorCopy } from "./copy/types"

/** « Tarifs » (landings spec, decision 16). Rendered only while
 *  `cvCopy.showPrices` is true. */
export function Pricing({ copy, cta }: { copy: CvCopy["prices"]; cta: DoorCopy }) {
  return (
    <section id="tarifs" className="lp-section lp-prices lp-bg-cool" aria-labelledby="tarifs-h">
      <div className="lp-container lp-reveal">
        <div className="lp-section-head">
          <h2 id="tarifs-h">{copy.title}</h2>
          <p>{copy.intro}</p>
        </div>
        <ul className="lp-plans">
          {copy.plans.map((plan) => (
            <li key={plan.name} className="lp-plan">
              <span className="lp-label">{plan.name}</span>
              <p className="lp-plan-price">{plan.price}</p>
              <p>{plan.text}</p>
            </li>
          ))}
        </ul>
        <p className="lp-cards-note">{copy.note}</p>
        <WipeLink href={cta.href} ring="orange" className="lp-btn lp-btn-primary">{cta.label}</WipeLink>
      </div>
    </section>
  )
}
```

`frontend/src/components/landing/DataSection.tsx`:

```tsx
import { ShieldCheck } from "lucide-react"
import { AppLink } from "@/lib/site-context"
import type { Bg } from "./CardGrid"
import type { DataCopy } from "./copy/types"

/** « Vos données » (landings spec, decision 16). No claim about where data is
 *  processed; the privacy page says it. */
export function DataSection({ copy, bg }: { copy: DataCopy; bg: Bg }) {
  return (
    <section id="donnees" className={`lp-section lp-data lp-bg-${bg}`} aria-labelledby="donnees-h">
      <div className="lp-container lp-data-in lp-reveal">
        <h2 id="donnees-h">{copy.title}</h2>
        <ul>
          {copy.points.map((point) => (
            <li key={point}>
              <ShieldCheck aria-hidden="true" />
              <span>{point}</span>
            </li>
          ))}
        </ul>
        <AppLink href={copy.link.href} className="lp-text-link">{copy.link.label}</AppLink>
      </div>
    </section>
  )
}
```

`frontend/src/components/landing/Faq.tsx`:

```tsx
import { Accordion } from "@/components/ui/accordion"
import { landingHref } from "@/lib/site"
import { currentSite } from "@/lib/site-server"
import type { Bg } from "./CardGrid"
import type { FaqCopy } from "./copy/types"

/** « Questions » (landings spec, decision 16), on the app's existing
 *  JS-free accordion. */
export async function Faq({ copy, bg }: { copy: FaqCopy; bg: Bg }) {
  const site = await currentSite()
  const items = copy.items.map((item) => ({
    q: item.q,
    a: (
      <>
        {item.a}
        {item.link ? (
          <>
            {" "}
            <a href={landingHref(item.link.app, site)} className="lp-text-link">{item.link.label}</a>
          </>
        ) : null}
      </>
    ),
  }))
  return (
    <section id="questions" className={`lp-section lp-bg-${bg}`} aria-labelledby="questions-h">
      <div className="lp-container lp-faq-in lp-reveal">
        <h2 id="questions-h">{copy.title}</h2>
        <Accordion items={items} />
      </div>
    </section>
  )
}
```

`frontend/src/components/landing/FinalCall.tsx`:

```tsx
import { ArrowRight } from "lucide-react"
import { landingHref } from "@/lib/site"
import { currentSite } from "@/lib/site-server"
import { WipeLink } from "./WipeLink"
import type { Bg } from "./CardGrid"
import type { DoorCopy, FinalCopy } from "./copy/types"

/** The final call (landings spec, decision 16): the video ad's closing line,
 *  both doors, and a bridge to the other app. */
export async function FinalCall({
  copy,
  primary,
  secondary,
  ring,
  bg,
}: {
  copy: FinalCopy
  primary: DoorCopy
  secondary: DoorCopy
  ring: "orange" | "peach"
  bg: Bg
}) {
  const site = await currentSite()
  return (
    <section className={`lp-section lp-final lp-bg-${bg}`} aria-labelledby="final-h">
      <div className="lp-container lp-final-in lp-reveal">
        <h2 id="final-h">{copy.title}</h2>
        <div className="lp-final-actions">
          <WipeLink href={primary.href} ring={ring} className="lp-btn lp-btn-primary">
            {primary.label} <ArrowRight aria-hidden="true" />
          </WipeLink>
          <a href={secondary.href} className="lp-btn lp-btn-secondary">{secondary.label}</a>
        </div>
        <p className="lp-final-bridge">
          {copy.bridge.text}{" "}
          <a href={landingHref(copy.bridge.link.app, site)} className="lp-text-link">{copy.bridge.link.label}</a>
        </p>
      </div>
    </section>
  )
}
```

- [ ] **Step 7: Assemble the cv. page, with its metadata**

Replace `frontend/src/app/accueil/cv/page.tsx` with:

```tsx
import "@/components/landing/landing.css"
import type { Metadata } from "next"
import { origin } from "@/lib/site"
import { currentSite } from "@/lib/site-server"
import { cvCopy } from "@/components/landing/copy/cv"
import { LandingNav } from "@/components/landing/LandingNav"
import { LandingFooter } from "@/components/landing/LandingFooter"
import { CvHero } from "@/components/landing/CvHero"
import { ReportIndex } from "@/components/landing/ReportIndex"
import { CardGrid } from "@/components/landing/CardGrid"
import { AdvisorsSection } from "@/components/landing/AdvisorsSection"
import { Pricing } from "@/components/landing/Pricing"
import { DataSection } from "@/components/landing/DataSection"
import { Faq } from "@/components/landing/Faq"
import { FinalCall } from "@/components/landing/FinalCall"

// Landings spec, decision 15: this landing's own title, description,
// canonical and share image. The root layout's template adds « · neoori ».
export async function generateMetadata(): Promise<Metadata> {
  const { settings } = await currentSite()
  const url = `${origin("cv", settings)}/`
  const { title, description, ogAlt } = cvCopy.meta
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      type: "website",
      locale: "fr_FR",
      url,
      siteName: "neoori",
      title: `${title} · neoori`,
      description,
      images: [{ url: "/og/cv.png", width: 1200, height: 630, alt: ogAlt }],
    },
    twitter: { card: "summary_large_image", title: `${title} · neoori`, description, images: ["/og/cv.png"] },
  }
}

// The cv. landing, « J'ai une cible », served at cv.DOMAIN/ by the proxy's
// rewrite (landings spec, decisions 8 and 16).
export default function CvLandingPage() {
  const c = cvCopy
  return (
    <div className="lp lp-cv">
      <LandingNav app="cv" copy={c.nav} showPrices={c.showPrices} placement="hero" />
      <main>
        <CvHero copy={c.hero} object={<div className="lp-cv-object" aria-hidden="true" />}>
          <ReportIndex copy={c.report} />
        </CvHero>
        <CardGrid id="comment" title={c.how.title} items={c.how.items} layout="steps" bg="white" />
        <CardGrid id="commencer" title={c.ways.title} intro={c.ways.intro} items={c.ways.items} layout="grid" bg="cool" />
        <AdvisorsSection copy={c.advisors} bg="white" />
        {c.showPrices ? <Pricing copy={c.prices} cta={c.hero.primary} /> : null}
        <DataSection copy={c.data} bg="cool" />
        <Faq copy={c.faq} bg="white" />
        <FinalCall copy={c.final} primary={c.hero.primary} secondary={c.hero.secondary} ring="orange" bg="cool" />
      </main>
      <LandingFooter app="cv" />
    </div>
  )
}
```

(`/og/cv.png` arrives in Task 8. Until then the share image is a 404, which
nothing reads in dev.)

- [ ] **Step 8: Run every check**

Run: `(cd frontend && npm test && npx tsc --noEmit && npm run lint; npm run build)`
Expected: 32 tests pass, `tsc` silent, lint at most 11 problems, build
succeeds.

- [ ] **Step 9: Check the page without a browser (Review Focus 1)**

Run: `docker compose up -d`, then:

```bash
H='Host: cv.neoori.localhost'
curl -s -H "$H" http://127.0.0.1:8080/ | grep -o 'Lire un parcours face à sa cible.' | head -1
curl -s -H "$H" http://127.0.0.1:8080/ | grep -o 'href="/analyse/nouveau"' | head -1
curl -s -H "$H" http://127.0.0.1:8080/ | grep -o 'Préconisations terrain' | head -1
curl -s -H "$H" http://127.0.0.1:8080/ | grep -o '<title>[^<]*</title>'
curl -s -H "$H" http://127.0.0.1:8080/ | grep -o '<link rel="canonical" href="[^"]*"'
curl -s -H "$H" http://127.0.0.1:8080/ | grep -c 'id="tarifs"'
```

Expected:
1. The headline
2. The main door as a plain link
3. A §5 title from the real report
4. `<title>Analyse de CV face à une cible · neoori</title>`
5. `href="http://cv.neoori.localhost:8080/"`
6. `0`: prices are hidden

- [ ] **Step 10: Look at it**

In Chrome, http://cv.neoori.localhost:8080/:
- At 1440 px: the big headline on the left, the doors, and the tier band in
  three cards.
- At 390 px: the tiers become one vertical line, orange marker first.
- At 320 px: no sideways scroll on the page.
- Every section heading reads as on the prototype (`prototype/src/cv-2.html`).
- « Je suis conseiller » scrolls to « Pour les conseillers ».
- The FAQ's last answer links to the voyage. landing.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/report-tiers.ts frontend/src/lib/report-tiers.test.ts \
  frontend/src/components/landing frontend/src/app/accueil/cv/page.tsx
git commit -m "feat(landing): the cv. landing

Landings spec decisions 15-16, ruling 6: the hero with both doors, the
report's real sections by tier (checked against section_registry.py),
how it works, the four ways in, advisors, data, questions and the final
call, with its own metadata. « Tarifs » is built and stays hidden.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The voyage. landing

Decisions 15 and 17, ruling 6, Appendix A (voyage.) and Appendix B. The whole
page, with the navy-to-dawn progression and its metadata. The 3D box is an
empty placeholder until Task 9.

**Files:**
- Create: `frontend/src/components/landing/VoyageHero.tsx`
- Modify: `frontend/src/components/landing/landing.css` (append)
- Modify: `frontend/src/app/accueil/voyage/page.tsx`

**Interfaces:**
- Consumes: Tasks 2–6, including `CardGrid`, `Bg`, `AdvisorsSection`,
  `DataSection`, `Faq`, `FinalCall` and `Doors`.
- Produces: `<VoyageHero copy object />`, whose section has `id="lp-voy-hero"`
  (Task 9's pointer area).

- [ ] **Step 1: Append the voyage. styles to `landing.css`**

```css
/* voyage. hero, direction 2 « Six étapes » (ruling 6): mist on the left,
   dawn on the right, the six sessions as a path, the glass oo above its end. */
.lp-voy-hero { position: relative; overflow: hidden; isolation: isolate; min-height: min(100svh, 900px); background: var(--lp-navy); }
.lp-voy-hero-in { position: relative; z-index: 2; min-height: min(100svh, 900px); display: grid; grid-template-rows: 1fr auto; gap: 40px; padding-top: calc(var(--lp-nav-h) + clamp(24px, 6vh, 64px)); padding-bottom: clamp(40px, 7vh, 72px); }
.lp-voy-hero .lp-hero-copy { max-width: 620px; }
.lp-voy-hero h1 { font-size: clamp(2.6rem, 5.4vw, 4.6rem); max-width: 13ch; }
.lp-voy-object { position: absolute; z-index: 0; left: 81%; top: 44%; width: min(72%, 1100px); aspect-ratio: 1; translate: -50% -50%; }
.lp-mist { position: absolute; inset: -20%; z-index: 1; pointer-events: none; filter: blur(14px);
  background:
    radial-gradient(34% 22% at 18% 66%, rgba(214, 222, 240, 0.16), transparent 70%),
    radial-gradient(40% 26% at 46% 82%, rgba(214, 222, 240, 0.12), transparent 70%),
    radial-gradient(30% 20% at 70% 40%, rgba(214, 222, 240, 0.07), transparent 70%);
  animation: lp-mist 26s ease-in-out infinite alternate; }
.lp-mist--2 { opacity: 0.8; animation-duration: 34s; animation-direction: alternate-reverse;
  background: radial-gradient(38% 24% at 30% 30%, rgba(214, 222, 240, 0.1), transparent 70%), radial-gradient(44% 26% at 64% 70%, rgba(214, 222, 240, 0.1), transparent 70%); }
@keyframes lp-mist { from { transform: translate3d(-4%, 1%, 0); } to { transform: translate3d(4%, -2%, 0); } }
.lp-mist-left { position: absolute; inset: 0; z-index: 1; pointer-events: none;
  background: linear-gradient(to right, rgba(214, 222, 240, 0.16) 0%, rgba(214, 222, 240, 0.05) 45%, rgba(214, 222, 240, 0) 70%), radial-gradient(40% 50% at 92% 88%, rgba(247, 179, 148, 0.2), transparent 70%); }
.lp-path { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); position: relative; }
.lp-path::before { content: ""; position: absolute; left: 6px; right: 0; top: 7px; height: 1px; background: linear-gradient(to right, rgba(247, 179, 148, 0.95), rgba(255, 255, 255, 0.28) 30%, rgba(255, 255, 255, 0.5)); }
.lp-step { position: relative; display: grid; gap: 6px; align-content: start; padding-top: 30px; padding-right: 12px; }
.lp-step i { position: absolute; top: 0; left: 0; width: 15px; height: 15px; border-radius: 50%; background: #8d9bb6; box-shadow: 0 0 0 5px var(--lp-navy); }
.lp-step.is-lit i { background: var(--lp-peach); box-shadow: 0 0 0 5px var(--lp-navy), 0 0 26px 8px rgba(247, 179, 148, 0.55); }
.lp-step b { font: 600 0.78rem/1 var(--lp-mono); letter-spacing: 0.08em; text-transform: uppercase; }
.lp-step.is-lit b { color: var(--lp-peach); }
.lp-step span { font: 500 0.92rem/1.35 var(--lp-body); color: rgba(255, 255, 255, 0.7); }
@media (max-width: 900px) {
  .lp-voy-hero { display: flex; flex-direction: column; min-height: 0; }
  .lp-voy-object { position: relative; order: 0; left: auto; top: auto; translate: none; width: auto; height: 300px; aspect-ratio: auto; margin-top: var(--lp-nav-h); }
  .lp-voy-hero-in { order: 1; min-height: 0; grid-template-rows: auto; padding-top: 8px; padding-bottom: 48px; }
  .lp-path { grid-template-columns: minmax(0, 1fr); gap: 18px; }
  .lp-path::before { left: 7px; right: auto; top: 6px; bottom: 6px; width: 1px; height: auto; background: linear-gradient(to bottom, rgba(247, 179, 148, 0.95), rgba(255, 255, 255, 0.3)); }
  .lp-step { padding-top: 0; padding-left: 34px; }
}
.lp-bg-dawn .lp-final-bridge { color: var(--lp-ink-2); }
@media (prefers-reduced-motion: reduce) {
  .lp-mist { animation: none; }
}
```

- [ ] **Step 2: Write `VoyageHero`**

`frontend/src/components/landing/VoyageHero.tsx`:

```tsx
import type { CSSProperties, ReactNode } from "react"
import { Doors } from "./Doors"
import type { VoyageCopy } from "./copy/types"

const at = (i: number) => ({ "--i": i }) as CSSProperties

/** voyage. hero, direction 2 « Six étapes » (landings spec, ruling 6): the
 *  copy and the two doors, the six sessions as a path from mist to dawn
 *  (session 0 lit), and the glass oo (`object`) above the path's far end. On
 *  phones the oo comes first and the path turns vertical. */
export function VoyageHero({ copy, object }: { copy: VoyageCopy["hero"]; object: ReactNode }) {
  return (
    <section id="lp-voy-hero" className="lp-voy-hero" aria-labelledby="lp-h1">
      {object}
      <div className="lp-mist" aria-hidden="true" />
      <div className="lp-mist lp-mist--2" aria-hidden="true" />
      <div className="lp-mist-left" aria-hidden="true" />
      <div className="lp-container lp-voy-hero-in">
        <div className="lp-hero-copy lp-rise">
          <span className="lp-label" style={at(0)}>{copy.label}</span>
          <h1 id="lp-h1" style={at(1)}>{copy.title}</h1>
          <p className="lp-sub" style={at(2)}>{copy.sub}</p>
          <div style={at(3)}>
            <Doors primary={copy.primary} secondary={copy.secondary} ring="peach" />
          </div>
        </div>
        <ol className="lp-path" aria-label={copy.stepsLabel}>
          {copy.steps.map((step, i) => (
            <li key={step.name} className={i === 0 ? "lp-step is-lit" : "lp-step"}>
              <i aria-hidden="true" />
              <b>{step.name}</b>
              {step.caption ? <span>{step.caption}</span> : null}
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
```

- [ ] **Step 3: Assemble the voyage. page, with its metadata**

Replace `frontend/src/app/accueil/voyage/page.tsx` with:

```tsx
import "@/components/landing/landing.css"
import type { Metadata } from "next"
import { landingHref, origin } from "@/lib/site"
import { currentSite } from "@/lib/site-server"
import { voyageCopy } from "@/components/landing/copy/voyage"
import { LandingNav } from "@/components/landing/LandingNav"
import { LandingFooter } from "@/components/landing/LandingFooter"
import { VoyageHero } from "@/components/landing/VoyageHero"
import { CardGrid } from "@/components/landing/CardGrid"
import { AdvisorsSection } from "@/components/landing/AdvisorsSection"
import { DataSection } from "@/components/landing/DataSection"
import { Faq } from "@/components/landing/Faq"
import { FinalCall } from "@/components/landing/FinalCall"

// Landings spec, decision 15: this landing's own title, description,
// canonical and share image. The root layout's template adds « · neoori ».
export async function generateMetadata(): Promise<Metadata> {
  const { settings } = await currentSite()
  const url = `${origin("voyage", settings)}/`
  const { title, description, ogAlt } = voyageCopy.meta
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      type: "website",
      locale: "fr_FR",
      url,
      siteName: "neoori",
      title: `${title} · neoori`,
      description,
      images: [{ url: "/og/voyage.png", width: 1200, height: 630, alt: ogAlt }],
    },
    twitter: { card: "summary_large_image", title: `${title} · neoori`, description, images: ["/og/voyage.png"] },
  }
}

// The voyage. landing, served at voyage.DOMAIN/ by the proxy's rewrite
// (landings spec, decisions 8 and 17). The grounds go from navy to dawn.
export default async function VoyageLandingPage() {
  const site = await currentSite()
  const v = voyageCopy
  const how = v.how.items.map(({ title, text, link }) => ({
    title,
    text,
    action: link ? <a href={landingHref(link.app, site)} className="lp-text-link">{link.label}</a> : undefined,
  }))
  return (
    <div className="lp lp-voy">
      <LandingNav app="voyage" copy={v.nav} placement="hero" />
      <main>
        <VoyageHero copy={v.hero} object={<div className="lp-voy-object" aria-hidden="true" />} />
        <CardGrid id="emporter" title={v.take.title} items={v.take.items} layout="grid" bg="deep" note={v.take.note} />
        <CardGrid id="etapes" title={v.how.title} items={how} layout="steps" bg="dusk" note={v.how.note} />
        <AdvisorsSection copy={v.advisors} bg="dawn" />
        <DataSection copy={v.data} bg="dawn" />
        <Faq copy={v.faq} bg="dawn" />
        <FinalCall copy={v.final} primary={v.hero.primary} secondary={v.hero.secondary} ring="peach" bg="dawn" />
      </main>
      <LandingFooter app="voyage" />
    </div>
  )
}
```

- [ ] **Step 4: Run every check**

Run: `(cd frontend && npm test && npx tsc --noEmit && npm run lint; npm run build)`
Expected: 32 tests pass, `tsc` silent, lint at most 11 problems, build
succeeds.

- [ ] **Step 5: Check the page without a browser (Review Focus 1)**

Run: `docker compose up -d`, then:

```bash
H='Host: voyage.neoori.localhost'
curl -s -H "$H" http://127.0.0.1:8080/ | grep -o 'Du brouillard à la clarté, une étape après l’autre.' | head -1
curl -s -H "$H" http://127.0.0.1:8080/ | grep -o 'href="/voyage"' | head -1
curl -s -H "$H" http://127.0.0.1:8080/ | grep -o 'Session 5' | head -1
curl -s -H "$H" http://127.0.0.1:8080/ | grep -o '<title>[^<]*</title>'
```

Expected: the headline; the main door as a plain link; the path's last step;
`<title>Le voyage, du brouillard à la clarté · neoori</title>`.

- [ ] **Step 6: Look at it**

In Chrome, http://voyage.neoori.localhost:8080/:
- At 1440 px: mist drifting, the path along the bottom with session 0 lit,
  then the sections going from navy through dusk to dawn.
- On the dawn sections, the buttons turn navy and the labels darker orange.
- At 390 px: the path is vertical.
- At 320 px: no sideways scroll.
- « Les six étapes » in the menu scrolls to « Comment ça se passe ».
- « Découvrir J’ai une cible » leads to http://cv.neoori.localhost:8080/.
- Compare with `prototype/src/voyage-2.html`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/landing frontend/src/app/accueil/voyage/page.tsx
git commit -m "feat(landing): the voyage. landing

Landings spec decisions 15 and 17, ruling 6: the hero with the six sessions
as a path from mist to dawn, what you leave with, how it works, advisors,
data, questions and the final call, on grounds going from navy to dawn,
with its own metadata.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The 3D scenes, and the still images made from them

Decisions 24–26 and Appendix B (3D). This task ports the round-2 prototype's
scenes to TypeScript and adds a dev-only page that renders the four stills
and the two share images. A script then encodes them within the budget.

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json` (`three`, `@types/three`)
- Create: `frontend/src/components/landing/scenes/core.ts`
- Create: `frontend/src/components/landing/scenes/sheet.ts`
- Create: `frontend/src/components/landing/scenes/mark.ts`
- Create: `frontend/src/components/landing/scenes/index.ts`
- Create: `frontend/src/app/dev/stills/page.tsx`, `frontend/src/app/dev/stills/StillsStudio.tsx`
- Create: `frontend/src/app/dev/stills/save/route.ts`
- Create: `frontend/scripts/encode-stills.mjs`
- Modify: `frontend/.gitignore`
- Create (generated, committed): `frontend/public/landing/{cv,voyage}-{desktop,phone}.{avif,webp}`, `frontend/public/og/{cv,voyage}.png`

**Interfaces:**
- Consumes: `MARK_PATH`, `MARK_VIEWBOX`, `LOGO_*` (Task 3); `cvCopy` and
  `voyageCopy` (Task 4).
- Produces (from `@/components/landing/scenes`):
  - `type SceneKind = "sheet" | "mark"`
  - `interface SceneController { dispose(): void }`
  - `mountScene(kind: SceneKind, host: HTMLElement, opts: { layout: Layout; pointerArea: HTMLElement | null }): SceneController`
  - `renderStill(kind: SceneKind, layout: Layout, width: number, height: number, pixelRatio: number): { canvas: HTMLCanvasElement; dispose(): void }`
  - from `scenes/core`: `type Layout = "desktop" | "phone"`
  - the files `/landing/<name>.avif|.webp` and `/og/<app>.png`

- [ ] **Step 1: Install three.js and its types**

Run: `(cd frontend && npm view three@~0.186.0 version && npm view @types/three@~0.186.0 version)`
Expected: `0.186.x` lines for each.

Run: `(cd frontend && npm install --save-exact three@~0.186.0 && npm install --save-exact --save-dev @types/three@~0.186.0)`
Then: `docker compose up -d --build -V frontend`, so the dev container gets
the new packages.

- [ ] **Step 2: Write `scenes/core.ts`**

```ts
import * as THREE from "three"
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js"

/** Shared parts of the two landing scenes (landings spec, Appendix B). Only
 *  scenes/index.ts is imported from outside, and only through a dynamic
 *  import, so three.js never reaches the first-visit bundle. */

export type Layout = "desktop" | "phone"
export type Pointer = { x: number; y: number }
export type Update = (t: number, pointer: Pointer) => void
export type View = { w: number; h: number }

export interface Stage {
  renderer: THREE.WebGLRenderer
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  /** Called with the visible size of the plane z = 0 whenever the canvas resizes. */
  onLayout: ((view: View) => void) | null
  view(): View
  resize(width: number, height: number): void
  render(): void
  dispose(): void
}

export const OO_COLORS = ["#ec6932", "#f49b68", "#f6b385"] as const

export function createStage(
  host: HTMLElement,
  o: { alpha: boolean; background: string | null; z: number; pixelRatio: number; attach: boolean; preserveDrawingBuffer?: boolean },
): Stage {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: o.alpha,
    powerPreference: "high-performance",
    preserveDrawingBuffer: o.preserveDrawingBuffer ?? false,
  })
  renderer.setPixelRatio(o.pixelRatio)
  renderer.toneMapping = THREE.NeutralToneMapping
  renderer.outputColorSpace = THREE.SRGBColorSpace
  if (o.alpha) renderer.setClearColor(0x000000, 0)
  if (o.attach) host.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  if (o.background) scene.background = new THREE.Color(o.background)
  const room = new RoomEnvironment()
  const pmrem = new THREE.PMREMGenerator(renderer)
  const environment = pmrem.fromScene(room, 0.04)
  scene.environment = environment.texture
  pmrem.dispose()
  ;(room as unknown as { dispose?: () => void }).dispose?.()

  const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100)
  camera.position.set(0, 0, o.z)

  const stage: Stage = {
    renderer,
    scene,
    camera,
    onLayout: null,
    view() {
      const h = 2 * camera.position.z * Math.tan((camera.fov * Math.PI) / 360)
      return { w: h * camera.aspect, h }
    },
    resize(width, height) {
      if (!width || !height) return
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      stage.onLayout?.(stage.view())
    },
    render() {
      renderer.render(scene, camera)
    },
    dispose() {
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh
        mesh.geometry?.dispose()
        const materials = Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : []
        for (const material of materials) {
          ;(material as THREE.MeshBasicMaterial).map?.dispose()
          material.dispose()
        }
      })
      environment.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    },
  }
  return stage
}

/** Vertex colours along x: the oo's orange-to-peach gradient. */
export function paintGradient(geometry: THREE.BufferGeometry, colors: readonly string[] = OO_COLORS): THREE.BufferGeometry {
  const stops = colors.map((c) => new THREE.Color(c))
  geometry.computeBoundingBox()
  const box = geometry.boundingBox as THREE.Box3
  const position = geometry.getAttribute("position")
  const out = new Float32Array(position.count * 3)
  const color = new THREE.Color()
  const span = box.max.x - box.min.x || 1
  for (let i = 0; i < position.count; i++) {
    const t = (position.getX(i) - box.min.x) / span
    if (t < 0.5) color.copy(stops[0]).lerp(stops[1], t * 2)
    else color.copy(stops[1]).lerp(stops[2], (t - 0.5) * 2)
    out[i * 3] = color.r
    out[i * 3 + 1] = color.g
    out[i * 3 + 2] = color.b
  }
  geometry.setAttribute("color", new THREE.BufferAttribute(out, 3))
  return geometry
}

/** A radial gradient on a canvas texture, for glows and soft shadows. */
export function radialTexture(stops: ReadonlyArray<readonly [number, string]>, size = 512): THREE.CanvasTexture {
  const canvas = document.createElement("canvas")
  canvas.width = canvas.height = size
  const g = canvas.getContext("2d")
  if (!g) throw new Error("2d context unavailable")
  const gradient = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  for (const [offset, color] of stops) gradient.addColorStop(offset, color)
  g.fillStyle = gradient
  g.fillRect(0, 0, size, size)
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

/** Runs `update` every frame while `host` is on screen and the tab visible;
 *  the pointer over `pointerArea` tilts the object a little. */
export function runLoop(stage: Stage, host: HTMLElement, update: Update, pointerArea: HTMLElement): { stop(): void } {
  const target = { x: 0, y: 0 }
  const current = { x: 0, y: 0 }
  let running = false
  let visible = false
  let stopped = false
  const t0 = performance.now()

  const frame = () => {
    if (!running || stopped) return
    current.x += (target.x - current.x) * 0.05
    current.y += (target.y - current.y) * 0.05
    update((performance.now() - t0) / 1000, current)
    stage.render()
    requestAnimationFrame(frame)
  }
  const sync = () => {
    const go = visible && !document.hidden && !stopped
    if (go && !running) {
      running = true
      requestAnimationFrame(frame)
    }
    if (!go) running = false
  }
  const move = (event: PointerEvent) => {
    const r = pointerArea.getBoundingClientRect()
    target.x = ((event.clientX - r.left) / r.width - 0.5) * 2
    target.y = ((event.clientY - r.top) / r.height - 0.5) * 2
  }
  const leave = () => {
    target.x = 0
    target.y = 0
  }
  pointerArea.addEventListener("pointermove", move, { passive: true })
  pointerArea.addEventListener("pointerleave", leave, { passive: true })
  const observer = new IntersectionObserver((entries) => {
    visible = entries.some((entry) => entry.isIntersecting)
    sync()
  }, { threshold: 0.02 })
  observer.observe(host)
  document.addEventListener("visibilitychange", sync)

  return {
    stop() {
      stopped = true
      running = false
      observer.disconnect()
      document.removeEventListener("visibilitychange", sync)
      pointerArea.removeEventListener("pointermove", move)
      pointerArea.removeEventListener("pointerleave", leave)
    },
  }
}
```

- [ ] **Step 3: Write `scenes/sheet.ts` (cv.)**

```ts
import * as THREE from "three"
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js"
import { paintGradient, radialTexture, type Layout, type Stage, type Update } from "./core"

/** cv.: an A4 sheet with the report's § marks, and the « cible » ring in
 *  matte ceramic (landings spec, Appendix B). At t = 0 it is exactly the
 *  still image. */
export function buildSheet(stage: Stage, layout: Layout): Update {
  const key = new THREE.DirectionalLight("#ffffff", 1.1)
  key.position.set(3, 5, 6)
  stage.scene.add(key)

  const root = new THREE.Group()
  const group = new THREE.Group()
  root.add(group)
  stage.scene.add(root)

  const paper = new THREE.MeshPhysicalMaterial({ color: "#ffffff", roughness: 0.62, clearcoat: 0.15, clearcoatRoughness: 0.6 })
  group.add(new THREE.Mesh(new RoundedBoxGeometry(2.1, 2.97, 0.06, 4, 0.05), paper))

  const bar = (w: number, h: number, x: number, y: number, color: string) => {
    const mesh = new THREE.Mesh(new RoundedBoxGeometry(w, h, 0.016, 2, 0.008), new THREE.MeshStandardMaterial({ color, roughness: 0.75 }))
    mesh.position.set(-0.85 + w / 2 + x, y, 0.036)
    group.add(mesh)
  }
  bar(0.38, 0.06, 0, 1.24, "#ea5624")
  bar(1.15, 0.11, 0, 1.06, "#1c3561")
  bar(0.8, 0.05, 0, 0.9, "#c7cfdc")
  for (const y of [0.62, -0.06, -0.74]) {
    bar(0.17, 0.1, 0, y, "#ea5624")
    bar(0.9, 0.08, 0.24, y, "#2b4677")
    ;[1.62, 1.5, 1.58, 1.2].forEach((w, i) => bar(w, 0.042, 0, y - 0.17 - i * 0.11, "#dfe5ee"))
  }

  const ceramic = new THREE.MeshPhysicalMaterial({ vertexColors: true, roughness: 0.44, metalness: 0, clearcoat: 0.5, clearcoatRoughness: 0.35 })
  const target = new THREE.Group()
  target.add(new THREE.Mesh(paintGradient(new THREE.TorusGeometry(0.52, 0.085, 48, 160)), ceramic))
  target.add(new THREE.Mesh(
    new THREE.SphereGeometry(0.07, 32, 32),
    new THREE.MeshPhysicalMaterial({ color: "#ea5624", roughness: 0.4, clearcoat: 0.6 }),
  ))
  target.position.set(0.5, 0.75, 0.75)
  target.rotation.set(0.25, -0.45, 0)
  group.add(target)

  const shadow = new THREE.Mesh(
    new THREE.PlaneGeometry(3.4, 4.2),
    new THREE.MeshBasicMaterial({
      map: radialTexture([[0, "rgba(28,53,97,0.28)"], [1, "rgba(28,53,97,0)"]]),
      transparent: true,
      depthWrite: false,
      toneMapped: false,
    }),
  )
  shadow.position.set(0.3, -0.35, -1.4)
  group.add(shadow)

  stage.onLayout = (view) => {
    if (layout === "desktop") {
      root.position.set(0.05, 0, 0)
      root.scale.setScalar(Math.min(1.12, view.w / 2.8))
    } else {
      root.position.set(0.05, -0.12, 0)
      root.scale.setScalar(Math.min(1.18, view.h / 3.9))
    }
  }

  return (t, pointer) => {
    group.position.y = Math.sin(t * 0.8) * 0.03
    group.rotation.set(
      -0.38 + Math.sin(t * 0.3) * 0.04 + pointer.y * 0.16,
      0.34 + Math.sin(t * 0.4) * 0.12 + pointer.x * 0.28,
      0.08,
    )
    target.position.y = 0.75 + Math.sin(t * 1.1) * 0.05
    target.rotation.z = Math.sin(t * 0.6) * 0.1
  }
}
```

- [ ] **Step 4: Write `scenes/mark.ts` (voyage.)**

```ts
import * as THREE from "three"
import { SVGLoader } from "three/addons/loaders/SVGLoader.js"
import { MARK_PATH, MARK_VIEWBOX } from "@/components/brand/logo-paths"
import { radialTexture, type Layout, type Stage, type Update } from "./core"

const NAVY = "#1c3561"
const MARK_WIDTH = 225 * 0.0175 // the mark's width in world units at scale 1

/** voyage.: the oo mark extruded from the logo, in frosted glass, lit from
 *  below like dawn (landings spec, Appendix B). On desktop it is drawn in a
 *  square box, so the still and the live scene share one framing at every
 *  screen width (decision 26). */
export function buildMark(stage: Stage, layout: Layout): Update {
  const key = new THREE.DirectionalLight("#fff1e6", 1.4)
  key.position.set(3, 4, 5)
  stage.scene.add(key)
  const rim = new THREE.DirectionalLight("#f7b394", 2.2)
  rim.position.set(-4, -1, -3)
  stage.scene.add(rim)

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${MARK_VIEWBOX.w} ${MARK_VIEWBOX.h}"><path d="${MARK_PATH}"/></svg>`
  const shapes = new SVGLoader().parse(svg).paths.flatMap((path) => SVGLoader.createShapes(path))
  const geometry = new THREE.ExtrudeGeometry(shapes, {
    depth: 22, curveSegments: 72, bevelEnabled: true, bevelThickness: 7, bevelSize: 3, bevelOffset: -3, bevelSegments: 8,
  })
  geometry.scale(1, -1, -1)
  geometry.center()
  // attenuationDistance is in world units: the mark is about 0.4 thick, so
  // 1.6 gives a light dawn tint (70–80 in round 1 gave no tint at all).
  const glass = new THREE.MeshPhysicalMaterial({
    color: "#ffeee4", roughness: 0.28, transmission: 1, thickness: 26, ior: 1.45,
    attenuationColor: new THREE.Color("#f2a27a"), attenuationDistance: 1.6, clearcoat: 1, clearcoatRoughness: 0.12,
  })
  const spin = new THREE.Group()
  spin.add(new THREE.Mesh(geometry, glass))
  spin.scale.setScalar(0.0175)
  const root = new THREE.Group()
  root.add(spin)
  stage.scene.add(root)

  // An opaque dawn glow behind the mark: the glass refracts it, and its edge
  // is exactly the page navy, so it melts into the background.
  const glow = new THREE.Mesh(
    new THREE.CircleGeometry(3.6, 96),
    new THREE.MeshBasicMaterial({ map: radialTexture([[0, "#8d6468"], [0.42, "#454468"], [1, NAVY]]), toneMapped: false }),
  )
  stage.scene.add(glow)

  stage.onLayout = (view) => {
    // Desktop: the mark fills 41.7 % of its square box and the glow about 92 %.
    // Phone: the round-2 prototype's framing.
    const scale = layout === "desktop" ? (0.417 * view.w) / MARK_WIDTH : Math.min(0.7, (0.62 * view.w) / MARK_WIDTH)
    const glowScale = layout === "desktop" ? 0.17 * view.w : Math.max(0.5, scale * 1.1)
    root.scale.setScalar(scale)
    glow.position.set(0, -0.45 * scale, -3)
    glow.scale.setScalar(glowScale)
  }

  return (t, pointer) => {
    spin.rotation.y = Math.sin(t * 0.45) * 0.32 + pointer.x * 0.35
    spin.rotation.x = -0.12 + Math.sin(t * 0.33) * 0.06 + pointer.y * 0.22
    spin.position.y = Math.sin(t * 0.8) * 0.06
  }
}
```

- [ ] **Step 5: Write `scenes/index.ts`**

```ts
import { createStage, runLoop, type Layout, type Stage, type Update } from "./core"
import { buildMark } from "./mark"
import { buildSheet } from "./sheet"

export type SceneKind = "sheet" | "mark"

export interface SceneController {
  dispose(): void
}

const SPECS: Record<SceneKind, {
  alpha: boolean
  background: string | null
  z: number
  maxPixelRatio: number
  build: (stage: Stage, layout: Layout) => Update
}> = {
  sheet: { alpha: true, background: null, z: 9.4, maxPixelRatio: 2, build: buildSheet },
  // Glass is the costly material: cap its pixel ratio at 1.5.
  mark: { alpha: false, background: "#1c3561", z: 9, maxPixelRatio: 1.5, build: buildMark },
}

/** The live scene, inside `host` (landings spec, decision 24). The caller
 *  decides whether it may run (lib/live-3d.ts). */
export function mountScene(
  kind: SceneKind,
  host: HTMLElement,
  opts: { layout: Layout; pointerArea: HTMLElement | null },
): SceneController {
  const spec = SPECS[kind]
  const stage = createStage(host, {
    alpha: spec.alpha,
    background: spec.background,
    z: spec.z,
    pixelRatio: Math.min(window.devicePixelRatio || 1, spec.maxPixelRatio),
    attach: true,
  })
  const update = spec.build(stage, opts.layout)
  const fit = () => stage.resize(host.clientWidth, host.clientHeight)
  const observer = new ResizeObserver(fit)
  observer.observe(host)
  fit()
  update(0, { x: 0, y: 0 })
  stage.render()
  const loop = runLoop(stage, host, update, opts.pointerArea ?? host)
  return {
    dispose() {
      loop.stop()
      observer.disconnect()
      stage.dispose()
    },
  }
}

/** One frame at t = 0, for the still images (decision 26). */
export function renderStill(
  kind: SceneKind,
  layout: Layout,
  width: number,
  height: number,
  pixelRatio: number,
): { canvas: HTMLCanvasElement; dispose(): void } {
  const spec = SPECS[kind]
  const stage = createStage(document.body, {
    alpha: spec.alpha,
    background: spec.background,
    z: spec.z,
    pixelRatio,
    attach: false,
    preserveDrawingBuffer: true,
  })
  const update = spec.build(stage, layout)
  stage.resize(width, height)
  update(0, { x: 0, y: 0 })
  stage.render()
  return { canvas: stage.renderer.domElement, dispose: () => stage.dispose() }
}
```

- [ ] **Step 6: Write the dev-only save route**

`frontend/src/app/dev/stills/save/route.ts`:

```ts
import { mkdir, writeFile } from "node:fs/promises"
import path from "node:path"

const NAME = /^(cv|voyage)-(desktop|phone)\.png$|^og-(cv|voyage)\.png$/

/** Dev only (landings spec, decision 26): writes one PNG rendered by
 *  /dev/stills into public/landing/ (stills) or public/og/ (share images).
 *  Answers 404 anywhere but `next dev`. */
export async function POST(request: Request): Promise<Response> {
  if (process.env.NODE_ENV !== "development") return new Response(null, { status: 404 })
  const name = new URL(request.url).searchParams.get("name") ?? ""
  if (!NAME.test(name)) return new Response("unexpected name", { status: 400 })
  const share = name.startsWith("og-")
  const dir = path.join(process.cwd(), "public", share ? "og" : "landing")
  const file = path.join(dir, share ? name.slice(3) : name)
  await mkdir(dir, { recursive: true })
  await writeFile(file, Buffer.from(await request.arrayBuffer()))
  return Response.json({ saved: path.relative(process.cwd(), file) })
}
```

- [ ] **Step 7: Write the dev-only page**

`frontend/src/app/dev/stills/page.tsx`:

```tsx
import { notFound } from "next/navigation"
import { StillsStudio } from "./StillsStudio"

// Dev only (landings spec, decision 26): renders the landings' still images
// and share images from the 3D scenes and saves them into public/. A 404
// outside `next dev`.
export default function StillsPage() {
  if (process.env.NODE_ENV !== "development") notFound()
  return <StillsStudio />
}
```

`frontend/src/app/dev/stills/StillsStudio.tsx`:

```tsx
"use client"

import { useState } from "react"
import { renderStill, type SceneKind } from "@/components/landing/scenes"
import type { Layout } from "@/components/landing/scenes/core"
import { LOGO_LETTERS, LOGO_NAVY, LOGO_OO, LOGO_OO_GRADIENT, LOGO_VIEWBOX } from "@/components/brand/logo-paths"
import { cvCopy } from "@/components/landing/copy/cv"
import { voyageCopy } from "@/components/landing/copy/voyage"

interface StillSpec {
  name: string
  scene: SceneKind
  layout: Layout
  width: number
  height: number
  pixelRatio: number
}

// CSS sizes of the boxes the landings give each still: the cv. desktop box is
// 620 × 694 at most (aspect 1 / 1.12); the voyage. desktop box is 72 % of a
// 1440 px hero (1037 px, square); the phone boxes at 390 px wide.
const STILLS: StillSpec[] = [
  { name: "cv-desktop", scene: "sheet", layout: "desktop", width: 620, height: 694, pixelRatio: 2 },
  { name: "cv-phone", scene: "sheet", layout: "phone", width: 390, height: 335, pixelRatio: 2 },
  { name: "voyage-desktop", scene: "mark", layout: "desktop", width: 1037, height: 1037, pixelRatio: 1.5 },
  { name: "voyage-phone", scene: "mark", layout: "phone", width: 390, height: 300, pixelRatio: 2 },
]

async function save(name: string, canvas: HTMLCanvasElement): Promise<string> {
  const blob = await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error(`${name}: empty canvas`))), "image/png"))
  const response = await fetch(`/dev/stills/save?name=${encodeURIComponent(`${name}.png`)}`, { method: "POST", body: blob })
  if (!response.ok) throw new Error(`${name}: ${response.status} ${await response.text()}`)
  const { saved } = (await response.json()) as { saved: string }
  return saved
}

function logoImage(light: boolean): Promise<HTMLImageElement> {
  const stops = LOGO_OO_GRADIENT.stops.map(([offset, color]) => `<stop offset="${offset}" stop-color="${color}"/>`).join("")
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${LOGO_VIEWBOX.w} ${LOGO_VIEWBOX.h}">` +
    `<defs><linearGradient id="g" x1="${LOGO_OO_GRADIENT.x1}" y1="0" x2="${LOGO_OO_GRADIENT.x2}" y2="0" gradientUnits="userSpaceOnUse">${stops}</linearGradient></defs>` +
    `<g fill="${light ? "#ffffff" : LOGO_NAVY}">${Object.values(LOGO_LETTERS).map((d) => `<path d="${d}"/>`).join("")}</g>` +
    `<path d="${LOGO_OO}" fill="url(#g)"/></svg>`
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error("logo image"))
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  })
}

function wrap(g: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const lines: string[] = []
  let line = ""
  for (const word of text.split(" ")) {
    const next = line ? `${line} ${word}` : word
    if (line && g.measureText(next).width > maxWidth) {
      lines.push(line)
      line = word
    } else {
      line = next
    }
  }
  if (line) lines.push(line)
  return lines
}

/** A 1200 × 630 share image: the ground, the 3D still on the right, the logo,
 *  the label and the headline (landings spec, decision 15). */
async function shareImage(app: "cv" | "voyage", still: HTMLCanvasElement): Promise<HTMLCanvasElement> {
  const dark = app === "voyage"
  const hero = dark ? voyageCopy.hero : cvCopy.hero
  const canvas = document.createElement("canvas")
  canvas.width = 1200
  canvas.height = 630
  const g = canvas.getContext("2d")
  if (!g) throw new Error("2d context unavailable")
  g.fillStyle = dark ? "#1c3561" : "#f4f6fa"
  g.fillRect(0, 0, 1200, 630)
  const scale = Math.min(540 / still.width, 560 / still.height)
  const w = still.width * scale
  const h = still.height * scale
  g.drawImage(still, 1200 - 48 - w, (630 - h) / 2, w, h)
  g.drawImage(await logoImage(dark), 72, 64, 190, (190 * LOGO_VIEWBOX.h) / LOGO_VIEWBOX.w)

  const css = getComputedStyle(document.documentElement)
  const display = css.getPropertyValue("--font-jakarta").trim() || "sans-serif"
  const mono = css.getPropertyValue("--font-jetbrains").trim() || "monospace"
  await document.fonts.load(`800 54px ${display}`)
  await document.fonts.load(`500 18px ${mono}`)
  const spaced = g as CanvasRenderingContext2D & { letterSpacing: string }
  g.fillStyle = dark ? "#f7b394" : "#c9491e"
  g.font = `500 18px ${mono}`
  spaced.letterSpacing = "3px"
  g.fillText(hero.label.toUpperCase(), 72, 220)
  spaced.letterSpacing = "0px"
  g.fillStyle = dark ? "#ffffff" : "#1c3561"
  g.font = `800 54px ${display}`
  wrap(g, hero.title, 560).forEach((line, i) => g.fillText(line, 72, 296 + i * 62))
  return canvas
}

/** Renders the four stills and the two share images, and saves them. */
export function StillsStudio() {
  const [log, setLog] = useState<string[]>([])
  const [busy, setBusy] = useState(false)

  const run = async () => {
    setBusy(true)
    const lines: string[] = []
    const add = (line: string) => {
      lines.push(line)
      setLog([...lines])
    }
    try {
      const desktop: Partial<Record<"cv" | "voyage", HTMLCanvasElement>> = {}
      for (const spec of STILLS) {
        const { canvas, dispose } = renderStill(spec.scene, spec.layout, spec.width, spec.height, spec.pixelRatio)
        add(`${spec.name}: ${await save(spec.name, canvas)}`)
        if (spec.layout === "desktop") {
          const copy = document.createElement("canvas")
          copy.width = canvas.width
          copy.height = canvas.height
          copy.getContext("2d")?.drawImage(canvas, 0, 0)
          desktop[spec.scene === "sheet" ? "cv" : "voyage"] = copy
        }
        dispose()
      }
      for (const app of ["cv", "voyage"] as const) {
        const still = desktop[app]
        if (!still) throw new Error(`${app}: no desktop still`)
        add(`og-${app}: ${await save(`og-${app}`, await shareImage(app, still))}`)
      }
      add("Terminé. Lancez maintenant : node scripts/encode-stills.mjs")
    } catch (error) {
      add(`Erreur : ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main style={{ padding: 32, fontFamily: "system-ui", display: "grid", gap: 16, maxWidth: 720 }}>
      <h1>Images fixes des landings</h1>
      <p>Rend les quatre images fixes et les deux images de partage depuis les scènes 3D, puis les enregistre dans public/.</p>
      <button type="button" onClick={run} disabled={busy} style={{ justifySelf: "start", padding: "10px 16px" }}>
        {busy ? "Rendu…" : "Rendre et enregistrer"}
      </button>
      <pre>{log.join("\n")}</pre>
    </main>
  )
}
```

- [ ] **Step 8: Write the encoder, and keep the PNG masters out of git**

`frontend/scripts/encode-stills.mjs`:

```js
// Encodes the stills rendered by /dev/stills (landings spec, decision 26):
// public/landing/<name>.png → <name>.avif and <name>.webp, the AVIF within the
// speed budget (decision 30: 90 KB desktop, 50 KB phone). Exits 1 if one
// cannot fit. Run from frontend/: node scripts/encode-stills.mjs
import { readdirSync, statSync } from "node:fs"
import { fileURLToPath } from "node:url"
import sharp from "sharp"

const dir = fileURLToPath(new URL("../public/landing/", import.meta.url))
const BUDGET = { desktop: 90 * 1024, phone: 50 * 1024 }
let failed = false

for (const file of readdirSync(dir).filter((name) => name.endsWith(".png"))) {
  const base = file.slice(0, -4)
  const budget = base.endsWith("-desktop") ? BUDGET.desktop : BUDGET.phone
  let quality = 55
  let size = Infinity
  while (quality >= 25) {
    await sharp(`${dir}${file}`).avif({ quality, effort: 6 }).toFile(`${dir}${base}.avif`)
    size = statSync(`${dir}${base}.avif`).size
    if (size <= budget) break
    quality -= 10
  }
  await sharp(`${dir}${file}`).webp({ quality: 82, alphaQuality: 90, effort: 6 }).toFile(`${dir}${base}.webp`)
  const webp = statSync(`${dir}${base}.webp`).size
  const ok = size <= budget
  if (!ok) failed = true
  console.log(`${base}: avif ${(size / 1024).toFixed(1)} KB (q${quality}) ${ok ? "ok" : "OVER BUDGET"} · webp ${(webp / 1024).toFixed(1)} KB`)
}
if (failed) process.exit(1)
```

Append to `frontend/.gitignore`:

```gitignore

# Landing still masters (rendered by /dev/stills; the AVIF and WebP are committed)
/public/landing/*.png
```

- [ ] **Step 9: Run every check**

Run: `(cd frontend && npm test && npx tsc --noEmit && npm run lint; npm run build)`
Expected: 32 tests pass, `tsc` silent, lint at most 11 problems, build
succeeds. If `tsc` cannot find `three/addons/...`, check that
`@types/three` 0.186 is installed: it declares those paths.

- [ ] **Step 10: Render, encode, and look at the images**

1. In Chrome, open http://cv.neoori.localhost:8080/dev/stills and press
   « Rendre et enregistrer ».
   Expected: six lines naming `public/landing/cv-desktop.png` …
   `public/og/voyage.png`, then « Terminé ».
2. Run: `(cd frontend && node scripts/encode-stills.mjs)`
   Expected: four lines, each `ok`, and exit code 0.
3. Open the six images, for example `open frontend/public/landing/*.webp frontend/public/og/*.png`:
   - **The cv. images:** the sheet with its orange and navy bars, and the
     ceramic ring above it. The background is transparent.
   - **The voyage. images:** the glass oo with a warm glow beneath, whose
     edges fade to exactly the page navy.
   - **The two share images:** logo, label and headline on the left, the
     object on the right, and nothing overlapping.

   Compare with the prototype's heroes.
4. Expected file list: `ls frontend/public/landing frontend/public/og` shows
   the PNG masters plus 4 `.avif` and 4 `.webp` in `landing/`, and `cv.png`
   and `voyage.png` in `og/`.

- [ ] **Step 11: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/.gitignore frontend/scripts/encode-stills.mjs \
  frontend/src/components/landing/scenes frontend/src/app/dev \
  frontend/public/landing/*.avif frontend/public/landing/*.webp frontend/public/og
git commit -m "feat(landing): the 3D scenes, and the still images made from them

Landings spec decisions 24-26: three.js 0.186 scenes for the cv. sheet and
the voyage. glass oo (Appendix B), loaded only through a dynamic import. A
dev-only page (/dev/stills, 404 outside next dev) renders each scene at
t = 0, and encode-stills.mjs turns the PNG masters into AVIF and WebP
within the budget. Share images 1200x630 for both landings.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Still first, then live — `HeroObject`

Decisions 24–26. Each landing's 3D box shows its still image straight from
the server. After `load` and an idle moment, on a capable desktop, the live
scene fades in over it.

**Files:**
- Create: `frontend/src/lib/live-3d.ts`, `frontend/src/lib/live-3d.test.ts`
- Create: `frontend/src/components/landing/HeroObject.tsx`
- Modify: `frontend/src/components/landing/landing.css` (append)
- Modify: `frontend/src/app/accueil/cv/page.tsx`, `frontend/src/app/accueil/voyage/page.tsx`

**Interfaces:**
- Consumes:
  - `mountScene`, `SceneKind` (Task 8)
  - the files `/landing/*.{avif,webp}` (Task 8)
  - `CvHero`'s `object` prop and section id `lp-cv-hero` (Task 6)
  - `VoyageHero`'s `object` prop and section id `lp-voy-hero` (Task 7)
- Produces:
  - `interface DeviceInfo { width; reducedMotion; saveData?; effectiveType?; deviceMemory?; cores?; webgl2 }`
  - `canRunLive3D(d: DeviceInfo): boolean`
  - `readDevice(w: Window): DeviceInfo`
  - `<HeroObject scene desktop phone pointerAreaId className />`, where
    `desktop` and `phone` are `{ src; width; height }` and `src` has no
    extension

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/live-3d.test.ts`:

```ts
import { test } from "node:test"
import assert from "node:assert/strict"
import { canRunLive3D, type DeviceInfo } from "./live-3d.ts"

const CAPABLE: DeviceInfo = { width: 1440, reducedMotion: false, webgl2: true }

test("a capable desktop gets the live 3D (landings spec, decision 24)", () => {
  assert.equal(canRunLive3D(CAPABLE), true)
  assert.equal(canRunLive3D({ ...CAPABLE, saveData: false, effectiveType: "4g", deviceMemory: 8, cores: 8 }), true)
})

test("anything else keeps the still image (Review Focus 5)", () => {
  const changes: Partial<DeviceInfo>[] = [
    { width: 900 }, { reducedMotion: true }, { webgl2: false }, { saveData: true },
    { effectiveType: "3g" }, { effectiveType: "slow-2g" }, { deviceMemory: 2 }, { cores: 2 },
  ]
  for (const change of changes) assert.equal(canRunLive3D({ ...CAPABLE, ...change }), false, JSON.stringify(change))
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `(cd frontend && npm test)`
Expected: FAIL with `Cannot find module …/lib/live-3d.ts`.

- [ ] **Step 3: Write `frontend/src/lib/live-3d.ts`**

```ts
/** Whether the live 3D may replace the still image (landings spec, decision
 *  24). Unknown values (browsers that do not report them) do not block. */
export interface DeviceInfo {
  width: number
  reducedMotion: boolean
  saveData?: boolean
  effectiveType?: string
  deviceMemory?: number
  cores?: number
  webgl2: boolean
}

const SLOW = ["slow-2g", "2g", "3g"]

export function canRunLive3D(d: DeviceInfo): boolean {
  if (d.width <= 900 || d.reducedMotion || !d.webgl2) return false
  if (d.saveData === true) return false
  if (d.effectiveType !== undefined && SLOW.includes(d.effectiveType)) return false
  if (d.deviceMemory !== undefined && d.deviceMemory < 4) return false
  if (d.cores !== undefined && d.cores < 4) return false
  return true
}

type NetworkInformation = { saveData?: boolean; effectiveType?: string }

/** DeviceInfo from the browser. The WebGL 2 probe frees its context at once. */
export function readDevice(w: Window): DeviceInfo {
  const nav = w.navigator as Navigator & { connection?: NetworkInformation; deviceMemory?: number }
  let webgl2 = false
  try {
    const gl = w.document.createElement("canvas").getContext("webgl2")
    webgl2 = gl !== null
    gl?.getExtension("WEBGL_lose_context")?.loseContext()
  } catch {
    webgl2 = false
  }
  return {
    width: w.innerWidth,
    reducedMotion: w.matchMedia("(prefers-reduced-motion: reduce)").matches,
    saveData: nav.connection?.saveData,
    effectiveType: nav.connection?.effectiveType,
    deviceMemory: nav.deviceMemory,
    cores: nav.hardwareConcurrency,
    webgl2,
  }
}
```

- [ ] **Step 4: Run it and watch it pass**

Run: `(cd frontend && npm test)`
Expected: PASS (34 tests).

- [ ] **Step 5: Write `HeroObject`**

`frontend/src/components/landing/HeroObject.tsx`:

```tsx
"use client"

import { useEffect, useRef, useState } from "react"
import { cn } from "@/lib/utils"
import { canRunLive3D, readDevice } from "@/lib/live-3d"

export interface Still {
  /** Path without extension: `${src}.avif` and `${src}.webp` exist. */
  src: string
  width: number
  height: number
}

/** A landing's 3D object, still first (landings spec, decisions 24–26). The
 *  server renders a still image of the exact scene. After `load` and an idle
 *  moment, on a capable desktop, the live three.js scene fades in over it;
 *  any failure, or the window narrowing to a phone width, keeps the still. */
export function HeroObject({
  scene,
  desktop,
  phone,
  pointerAreaId,
  className,
}: {
  scene: "sheet" | "mark"
  desktop: Still
  phone: Still
  pointerAreaId: string
  className?: string
}) {
  const host = useRef<HTMLDivElement>(null)
  const [live, setLive] = useState(false)

  useEffect(() => {
    let disposed = false
    let controller: { dispose(): void } | null = null
    const narrow = window.matchMedia("(max-width: 900px)")

    const stop = () => {
      controller?.dispose()
      controller = null
      setLive(false)
    }
    const start = async () => {
      if (disposed || controller || !host.current || !canRunLive3D(readDevice(window))) return
      try {
        const { mountScene } = await import("./scenes")
        if (disposed || !host.current) return
        controller = mountScene(scene, host.current, {
          layout: "desktop",
          pointerArea: document.getElementById(pointerAreaId),
        })
        setLive(true)
      } catch (error) {
        console.error("neoori: the live 3D did not start; the still image stays.", error)
        stop()
      }
    }
    const kick = () => {
      if ("requestIdleCallback" in window) window.requestIdleCallback(() => void start(), { timeout: 2000 })
      else setTimeout(() => void start(), 800)
    }
    const onNarrow = () => {
      if (narrow.matches) stop()
    }

    narrow.addEventListener("change", onNarrow)
    if (document.readyState === "complete") kick()
    else window.addEventListener("load", kick, { once: true })
    return () => {
      disposed = true
      narrow.removeEventListener("change", onNarrow)
      window.removeEventListener("load", kick)
      controller?.dispose()
    }
  }, [scene, pointerAreaId])

  return (
    <div ref={host} className={cn("lp-3d", live && "is-live", className)} aria-hidden="true">
      <picture>
        <source media="(min-width: 901px)" type="image/avif" srcSet={`${desktop.src}.avif`} />
        <source media="(min-width: 901px)" type="image/webp" srcSet={`${desktop.src}.webp`} />
        <source type="image/avif" srcSet={`${phone.src}.avif`} />
        <img
          className="lp-still"
          src={`${phone.src}.webp`}
          alt=""
          width={phone.width}
          height={phone.height}
          decoding="async"
          fetchPriority="high"
        />
      </picture>
    </div>
  )
}
```

- [ ] **Step 6: Append the 3D styles to `landing.css`**

```css
/* The 3D objects: a still image first; the live scene fades in over it on
   capable desktops (decisions 24–26). */
.lp-3d picture, .lp-3d .lp-still { position: absolute; inset: 0; width: 100%; height: 100%; }
.lp-3d .lp-still { object-fit: contain; transition: opacity 0.3s ease 0.1s; }
.lp-3d canvas { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; transition: opacity 0.3s ease; }
.lp-3d.is-live canvas { opacity: 1; }
.lp-3d.is-live .lp-still { opacity: 0; }
.lp-voy-object .lp-still { object-fit: cover; }
```

- [ ] **Step 7: Put the objects in the two heroes**

In `frontend/src/app/accueil/cv/page.tsx`:

(a) Add the import `import { HeroObject } from "@/components/landing/HeroObject"`.

(b) Replace `object={<div className="lp-cv-object" aria-hidden="true" />}` with:

```tsx
object={
  <HeroObject
    scene="sheet"
    desktop={{ src: "/landing/cv-desktop", width: 1240, height: 1388 }}
    phone={{ src: "/landing/cv-phone", width: 780, height: 670 }}
    pointerAreaId="lp-cv-hero"
    className="lp-cv-object"
  />
}
```

In `frontend/src/app/accueil/voyage/page.tsx`:

(a) Add the import `import { HeroObject } from "@/components/landing/HeroObject"`.

(b) Replace `object={<div className="lp-voy-object" aria-hidden="true" />}` with:

```tsx
object={
  <HeroObject
    scene="mark"
    desktop={{ src: "/landing/voyage-desktop", width: 1556, height: 1556 }}
    phone={{ src: "/landing/voyage-phone", width: 780, height: 600 }}
    pointerAreaId="lp-voy-hero"
    className="lp-voy-object"
  />
}
```

- [ ] **Step 8: Run every check**

Run: `(cd frontend && npm test && npx tsc --noEmit && npm run lint; npm run build)`
Expected: 34 tests pass, `tsc` silent, lint at most 11 problems (Next's
`no-img-element` rule does not flag an `<img>` inside `<picture>`), build
succeeds.

- [ ] **Step 9: Look at it, desktop then phone**

In Chrome with DevTools' Network panel open:

1. **http://cv.neoori.localhost:8080/ at 1440 px.**
   - The sheet appears at once, as an image.
   - About a second after load, a JavaScript chunk of roughly 130 KB
     (three.js) loads and the object starts to float. The crossfade from the
     still must not jump: the first live frame equals the still.
   - Moving the pointer over the hero tilts it.
2. **http://voyage.neoori.localhost:8080/:** the same with the glass oo.
3. **Scroll the hero out of view.** In the Performance panel (record 3 s), no
   frames are drawn for the canvas.
4. **At 390 px (DevTools device toolbar, then reload):** the phone still,
   with no three.js chunk in Network and no `<canvas>` in Elements.
5. **DevTools > Rendering > « prefers-reduced-motion: reduce », then reload:**
   the still only.
6. **From 1440 px, narrow the window below 900 px:** the canvas goes away and
   the still stays.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/lib/live-3d.ts frontend/src/lib/live-3d.test.ts frontend/src/components/landing \
  frontend/src/app/accueil
git commit -m "feat(landing): still image first, live 3D on capable desktops

Landings spec decisions 24-26: HeroObject serves the still (AVIF/WebP, art
directed) and, after load, imports the scene only when canRunLive3D()
agrees: wide screen, no reduce motion, no data saving or slow network,
enough memory and cores, WebGL 2. Any failure keeps the still.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: The ∞ wipe into the product

Decision 22. The landing's main buttons open the next page through a circle
growing from the button, with a thin brand ring riding its edge. This uses the
browser's View Transitions API around a router push. A small client component
in the root layout tells a waiting wipe that the new page has committed.

**Files:**
- Create: `frontend/src/lib/wipe.ts`, `frontend/src/lib/wipe.test.ts`
- Create: `frontend/src/lib/nav-settle.ts`, `frontend/src/lib/nav-settle.test.ts`
- Create: `frontend/src/components/landing/NavigationSettled.tsx`
- Modify: `frontend/src/components/landing/WipeLink.tsx` (whole file)
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/app/globals.css` (append)

**Interfaces:**
- Consumes: `useSite().href` (existing); `<WipeLink>`'s props (Task 5), which
  stay the same.
- Produces:
  - `wipeRadius(x: number, y: number, width: number, height: number): number`
  - `ringSnapshot(radius: number, maxSize?: number): { size: number; stroke: number; scale: number }`
  - `RING_STROKE = 5`
  - `waitForNavigation(timeoutMs?: number): Promise<void>`
  - `settleNavigation(): void`
  - `<NavigationSettled />`
  - the CSS custom properties `--wipe-x`, `--wipe-y`, `--wipe-r`,
    `--ring-tx`, `--ring-ty`, `--ring-scale`
  - the class `neoori-wipe` on `<html>` during a wipe
  - `view-transition-name: neoori-wipe-ring`

- [ ] **Step 1: Write the failing tests**

`frontend/src/lib/wipe.test.ts`:

```ts
import { test } from "node:test"
import assert from "node:assert/strict"
import { RING_STROKE, ringSnapshot, wipeRadius } from "./wipe.ts"

test("the circle reaches the farthest corner, with a margin (landings spec, decision 22)", () => {
  assert.equal(wipeRadius(0, 0, 300, 400), 500 + 12)
  assert.equal(wipeRadius(150, 200, 300, 400), 250 + 12)
})

test("the ring's snapshot is at most 1200 px and keeps a 5 px stroke once scaled", () => {
  assert.deepEqual(ringSnapshot(400), { size: 800, stroke: RING_STROKE, scale: 1 })
  const big = ringSnapshot(1700)
  assert.equal(big.size, 1200)
  assert.ok(Math.abs(big.stroke * big.scale - RING_STROKE) < 1e-9)
})
```

`frontend/src/lib/nav-settle.test.ts`:

```ts
import { test } from "node:test"
import assert from "node:assert/strict"
import { settleNavigation, waitForNavigation } from "./nav-settle.ts"

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

test("a wipe waits until the new page has committed", async () => {
  let done = false
  const wait = waitForNavigation(1000).then(() => { done = true })
  await pause(10)
  assert.equal(done, false)
  settleNavigation()
  await wait
  assert.equal(done, true)
})

test("…and never longer than its timeout (Review Focus 2)", async () => {
  const start = Date.now()
  await waitForNavigation(30)
  assert.ok(Date.now() - start >= 25)
})

test("a newer wait releases the older one", async () => {
  const first = waitForNavigation(1000)
  const second = waitForNavigation(1000)
  await first
  settleNavigation()
  await second
})
```

- [ ] **Step 2: Run them and watch them fail**

Run: `(cd frontend && npm test)`
Expected: FAIL with `Cannot find module …/lib/wipe.ts` and `…/lib/nav-settle.ts`.

- [ ] **Step 3: Write the two helpers**

`frontend/src/lib/wipe.ts`:

```ts
/** Geometry of the ∞ wipe (landings spec, decision 22). */

export const RING_STROKE = 5

/** The radius that covers the viewport from (x, y), with a small margin. */
export function wipeRadius(x: number, y: number, width: number, height: number): number {
  return Math.hypot(Math.max(x, width - x), Math.max(y, height - y)) + 12
}

/** The ring is captured once, at `size` px at most, and its transition layer
 *  is scaled up by `scale`; the stroke is drawn thinner by the same factor so
 *  that it ends at RING_STROKE px. */
export function ringSnapshot(radius: number, maxSize = 1200): { size: number; stroke: number; scale: number } {
  const diameter = 2 * radius
  const size = Math.min(diameter, maxSize)
  return { size, stroke: (RING_STROKE * size) / diameter, scale: diameter / size }
}
```

`frontend/src/lib/nav-settle.ts`:

```ts
let pending: (() => void) | null = null

/** Resolves once the next client navigation has committed (NavigationSettled
 *  calls settleNavigation), or after `timeoutMs`: a View Transition must never
 *  wait on a navigation that does not come (landings spec, decision 22). */
export function waitForNavigation(timeoutMs = 3000): Promise<void> {
  pending?.()
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer)
      if (pending === done) pending = null
      resolve()
    }
    const timer = setTimeout(done, timeoutMs)
    pending = done
  })
}

/** Releases the wipe that is waiting, if any. */
export function settleNavigation(): void {
  const done = pending
  pending = null
  done?.()
}
```

- [ ] **Step 4: Run them and watch them pass**

Run: `(cd frontend && npm test)`
Expected: PASS (39 tests).

- [ ] **Step 5: Write `NavigationSettled` and mount it**

`frontend/src/components/landing/NavigationSettled.tsx`:

```tsx
"use client"

import { usePathname } from "next/navigation"
import { useLayoutEffect } from "react"
import { settleNavigation } from "@/lib/nav-settle"

/** Tells a waiting ∞ wipe that the new page is in the DOM (landings spec,
 *  decision 22). Mounted once, in the root layout; renders nothing. */
export function NavigationSettled() {
  const pathname = usePathname()
  useLayoutEffect(() => {
    settleNavigation()
  }, [pathname])
  return null
}
```

In `frontend/src/app/layout.tsx`:

(a) Add the import `import { NavigationSettled } from "@/components/landing/NavigationSettled"`.

(b) Replace:

```tsx
        <SiteProvider site={site}>
          <AuthProvider>{children}</AuthProvider>
        </SiteProvider>
```

with:

```tsx
        <SiteProvider site={site}>
          <NavigationSettled />
          <AuthProvider>{children}</AuthProvider>
        </SiteProvider>
```

- [ ] **Step 6: Write the wipe**

Replace `frontend/src/components/landing/WipeLink.tsx` with:

```tsx
"use client"

import type { MouseEvent, ReactNode } from "react"
import { useRouter } from "next/navigation"
import { AppLink, useSite } from "@/lib/site-context"
import { waitForNavigation } from "@/lib/nav-settle"
import { ringSnapshot, wipeRadius } from "@/lib/wipe"

const RING = { orange: "#ea5624", peach: "#f7b394" } as const
const VARS = ["--wipe-x", "--wipe-y", "--wipe-r", "--ring-tx", "--ring-ty", "--ring-scale"] as const

/** The landing's main button, with the ∞ wipe (landings spec, decision 22):
 *  the next page appears in a circle growing from the button, a thin brand
 *  ring riding its edge. A plain link without JavaScript or View Transitions,
 *  under reduce motion, with a modifier key, or towards another host. */
export function WipeLink({
  href,
  ring,
  className,
  children,
}: {
  href: string
  ring: keyof typeof RING
  className?: string
  children: ReactNode
}) {
  const router = useRouter()
  const site = useSite()

  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    if (site.href(href) !== href) return
    if (typeof document.startViewTransition !== "function") return
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return
    event.preventDefault()

    // A keyboard press has no pointer position: open from the button's centre.
    const box = event.currentTarget.getBoundingClientRect()
    const x = event.detail > 0 ? event.clientX : box.left + box.width / 2
    const y = event.detail > 0 ? event.clientY : box.top + box.height / 2
    const radius = wipeRadius(x, y, window.innerWidth, window.innerHeight)
    const snap = ringSnapshot(radius)
    const root = document.documentElement
    root.style.setProperty("--wipe-x", `${x}px`)
    root.style.setProperty("--wipe-y", `${y}px`)
    root.style.setProperty("--wipe-r", `${radius}px`)
    root.style.setProperty("--ring-tx", `${x - snap.size / 2}px`)
    root.style.setProperty("--ring-ty", `${y - snap.size / 2}px`)
    root.style.setProperty("--ring-scale", String(snap.scale))
    root.classList.add("neoori-wipe")
    const ringElement = drawRing(x, y, snap, RING[ring])

    const transition = document.startViewTransition(async () => {
      ringElement.remove()
      router.push(href)
      await waitForNavigation()
    })
    transition.ready.catch(() => {})
    transition.finished
      .finally(() => {
        ringElement.remove()
        root.classList.remove("neoori-wipe")
        for (const name of VARS) root.style.removeProperty(name)
      })
      .catch(() => {})
  }

  return (
    <AppLink href={href} className={className} onClick={onClick}>
      {children}
    </AppLink>
  )
}

/** The ring, drawn at its snapshot size but scaled almost to nothing on
 *  screen. A View Transition captures an element without its transform, so
 *  the snapshot stays sharp, and the visitor never sees the ring before it
 *  grows. It leaves the DOM in the transition's update, so it exists only in
 *  the old state. */
function drawRing(x: number, y: number, snap: { size: number; stroke: number }, color: string): SVGSVGElement {
  const ns = "http://www.w3.org/2000/svg"
  const { size, stroke } = snap
  const svg = document.createElementNS(ns, "svg")
  svg.setAttribute("width", String(size))
  svg.setAttribute("height", String(size))
  svg.setAttribute("viewBox", `0 0 ${size} ${size}`)
  svg.setAttribute("aria-hidden", "true")
  svg.style.cssText = [
    "position:fixed",
    `left:${x - size / 2}px`,
    `top:${y - size / 2}px`,
    `width:${size}px`,
    `height:${size}px`,
    "pointer-events:none",
    "transform:scale(0.002)",
    "view-transition-name:neoori-wipe-ring",
    "z-index:2147483647",
  ].join(";")
  const circle = document.createElementNS(ns, "circle")
  circle.setAttribute("cx", String(size / 2))
  circle.setAttribute("cy", String(size / 2))
  circle.setAttribute("r", String(size / 2 - stroke / 2))
  circle.setAttribute("fill", "none")
  circle.setAttribute("stroke", color)
  circle.setAttribute("stroke-width", String(stroke))
  svg.appendChild(circle)
  document.body.appendChild(svg)
  return svg
}
```

- [ ] **Step 7: Append the wipe's CSS to `globals.css`**

`frontend/src/app/globals.css` stays loaded while the page changes, so the
wipe's rules live there. Append:

```css
/* ── The ∞ wipe (landings spec, decision 22). WipeLink sets the variables and
   the class for one View Transition; nothing here applies otherwise. ── */
html.neoori-wipe::view-transition-old(root) { animation: none; }
html.neoori-wipe::view-transition-new(root) {
  animation: neoori-wipe-in 900ms cubic-bezier(0.76, 0, 0.24, 1) both;
}
html.neoori-wipe::view-transition-group(neoori-wipe-ring) {
  transform-origin: 50% 50%;
  animation: neoori-ring-grow 900ms cubic-bezier(0.76, 0, 0.24, 1) both;
}
html.neoori-wipe::view-transition-old(neoori-wipe-ring) {
  animation: neoori-ring-fade 900ms linear both;
}
@keyframes neoori-wipe-in {
  from { clip-path: circle(0px at var(--wipe-x) var(--wipe-y)); }
  to { clip-path: circle(var(--wipe-r) at var(--wipe-x) var(--wipe-y)); }
}
@keyframes neoori-ring-grow {
  from { transform: translate(var(--ring-tx), var(--ring-ty)) scale(0.002); }
  to { transform: translate(var(--ring-tx), var(--ring-ty)) scale(var(--ring-scale)); }
}
@keyframes neoori-ring-fade {
  0%, 55% { opacity: 1; }
  100% { opacity: 0; }
}
```

- [ ] **Step 8: Run every check**

Run: `(cd frontend && npm test && npx tsc --noEmit && npm run lint; npm run build)`
Expected: 39 tests pass, `tsc` silent, lint at most 11 problems, build
succeeds.

- [ ] **Step 9: Check the wipe in Chrome**

`docker compose up -d`, then on http://cv.neoori.localhost:8080/:

1. **Click « Analyser mon CV » in the hero.** The form appears through a
   circle growing from the click point, with an orange ring at its edge that
   fades in the second half. The address becomes `/analyse/nouveau`.
2. **Press Back.** The landing is whole: no circle, nothing clipped
   (Review Focus 2).
3. **Tab to the button and press Enter.** The circle opens from the button's
   centre.
4. **⌘-click the button.** A new tab, no wipe.
5. **On http://voyage.neoori.localhost:8080/, signed out, click « Commencer
   le voyage ».** The circle, with a peach ring, opens on `/inscription?redirect=%2Fvoyage`.
6. **DevTools > Rendering > « prefers-reduced-motion: reduce ».** A plain page
   change.
7. **DevTools > Performance, record one wipe.** The ring is sharp at 1× and
   (on a Retina screen) 2×. No frame shows a large ring before it grows.

If check 7 fails — the ring blurs, flashes or sits in the wrong place — keep
the reveal and drop the ring:
- delete `drawRing` and the lines that set `--ring-tx`, `--ring-ty` and
  `--ring-scale`
- delete the two `neoori-wipe-ring` rules and the two `neoori-ring-*`
  keyframes from `globals.css`
- note it in the commit message

That is the spec's own fallback (decision 22).

- [ ] **Step 10: Commit**

```bash
git add frontend/src/lib/wipe.ts frontend/src/lib/wipe.test.ts frontend/src/lib/nav-settle.ts frontend/src/lib/nav-settle.test.ts \
  frontend/src/components/landing/NavigationSettled.tsx frontend/src/components/landing/WipeLink.tsx \
  frontend/src/app/layout.tsx frontend/src/app/globals.css
git commit -m "feat(landing): the ∞ wipe into the product

Landings spec decision 22: the main buttons open the next page through a
circle growing from the click, a thin brand ring at its edge, with the
browser's View Transitions around a router push. NavigationSettled tells
the wipe when the new page has committed (3 s at most). A plain link
without View Transitions, under reduce motion, or with a modifier key.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: `robots.txt` and `sitemap.xml` per host

Decision 14. Pure builders in `lib/seo.ts`, tested; two thin Next metadata
routes read the host per request.

**Files:**
- Create: `frontend/src/lib/seo.ts`, `frontend/src/lib/seo.test.ts`
- Create: `frontend/src/app/robots.ts`, `frontend/src/app/sitemap.ts`

**Interfaces:**
- Consumes: `origin`, `AppName`, `SiteSettings` (`lib/site.ts`); `currentSite` (`lib/site-server.ts`).
- Produces:
  - `robotsFor(app: AppName, settings: SiteSettings): MetadataRoute.Robots`
  - `sitemapFor(app: AppName, settings: SiteSettings): MetadataRoute.Sitemap`

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/seo.test.ts`:

```ts
import { test } from "node:test"
import assert from "node:assert/strict"
import { robotsFor, sitemapFor } from "./seo.ts"
import type { SiteSettings } from "./site.ts"

const PROD: SiteSettings = { domain: "neoori.tech", scheme: "https", port: "" }
const DEV: SiteSettings = { domain: "neoori.localhost", scheme: "http", port: "8080" }

test("robots per host (landings spec, decision 14)", () => {
  assert.deepEqual(robotsFor("cv", PROD), {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/analyse", "/rapport", "/espace", "/profil", "/conseiller", "/admin", "/c/", "/accueil"],
    },
    sitemap: "https://cv.neoori.tech/sitemap.xml",
  })
  assert.deepEqual(robotsFor("voyage", PROD), {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/voyage", "/profil", "/conseiller", "/admin", "/accueil", "/cgv", "/confidentialite", "/mentions-legales"],
    },
    sitemap: "https://voyage.neoori.tech/sitemap.xml",
  })
  assert.deepEqual(robotsFor("root", PROD), {
    rules: { userAgent: "*", allow: "/$", disallow: ["/"] },
    sitemap: "https://neoori.tech/sitemap.xml",
  })
})

test("sitemaps list absolute URLs built from DOMAIN", () => {
  assert.deepEqual(sitemapFor("cv", PROD).map((entry) => entry.url), [
    "https://cv.neoori.tech/", "https://cv.neoori.tech/cgv",
    "https://cv.neoori.tech/confidentialite", "https://cv.neoori.tech/mentions-legales",
  ])
  assert.deepEqual(sitemapFor("voyage", DEV).map((entry) => entry.url), ["http://voyage.neoori.localhost:8080/"])
  assert.deepEqual(sitemapFor("root", PROD).map((entry) => entry.url), ["https://neoori.tech/"])
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `(cd frontend && npm test)`
Expected: FAIL with `Cannot find module …/lib/seo.ts`.

- [ ] **Step 3: Write `frontend/src/lib/seo.ts`**

```ts
import type { MetadataRoute } from "next"
import { origin, type AppName, type SiteSettings } from "./site.ts"

// Landings spec, decision 14. cv. lists the legal pages; voyage. keeps its
// copies out of the index; the root shows its landing and nothing else.
const DISALLOW: Record<AppName, string[]> = {
  cv: ["/analyse", "/rapport", "/espace", "/profil", "/conseiller", "/admin", "/c/", "/accueil"],
  voyage: ["/voyage", "/profil", "/conseiller", "/admin", "/accueil", "/cgv", "/confidentialite", "/mentions-legales"],
  root: ["/"],
}

const LISTED: Record<AppName, string[]> = {
  cv: ["/", "/cgv", "/confidentialite", "/mentions-legales"],
  voyage: ["/"],
  root: ["/"],
}

/** robots.txt for one host, every URL built from DOMAIN. */
export function robotsFor(app: AppName, settings: SiteSettings): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: app === "root" ? "/$" : "/", disallow: DISALLOW[app] },
    sitemap: `${origin(app, settings)}/sitemap.xml`,
  }
}

/** sitemap.xml for one host. */
export function sitemapFor(app: AppName, settings: SiteSettings): MetadataRoute.Sitemap {
  const base = origin(app, settings)
  return LISTED[app].map((path) => ({ url: `${base}${path}` }))
}
```

- [ ] **Step 4: Run it and watch it pass**

Run: `(cd frontend && npm test)`
Expected: PASS (41 tests).

- [ ] **Step 5: Write the two metadata routes**

`frontend/src/app/robots.ts`:

```ts
import type { MetadataRoute } from "next"
import { robotsFor } from "@/lib/seo"
import { currentSite } from "@/lib/site-server"

// One robots.txt per host (landings spec, decision 14). Reading the host
// makes this route per request rather than cached at build time.
export default async function robots(): Promise<MetadataRoute.Robots> {
  const { app, settings } = await currentSite()
  return robotsFor(app, settings)
}
```

`frontend/src/app/sitemap.ts`:

```ts
import type { MetadataRoute } from "next"
import { sitemapFor } from "@/lib/seo"
import { currentSite } from "@/lib/site-server"

// One sitemap.xml per host (landings spec, decision 14).
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const { app, settings } = await currentSite()
  return sitemapFor(app, settings)
}
```

- [ ] **Step 6: Run every check, then check the three hosts**

Run: `(cd frontend && npm test && npx tsc --noEmit && npm run lint; npm run build)`
Expected: 41 tests pass, `tsc` silent, lint at most 11 problems, build
succeeds.

Run: `docker compose up -d`, then:

```bash
for h in neoori.localhost cv.neoori.localhost voyage.neoori.localhost; do
  echo "== $h"; curl -s -H "Host: $h" http://127.0.0.1:8080/robots.txt; curl -s -H "Host: $h" http://127.0.0.1:8080/sitemap.xml | grep -o '<loc>[^<]*</loc>'
done
```

Expected: each host prints its own rules, and a `Sitemap:` line plus `<loc>`
lines with `http://…localhost:8080` URLs for that host, exactly as in
decision 14.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/seo.ts frontend/src/lib/seo.test.ts frontend/src/app/robots.ts frontend/src/app/sitemap.ts
git commit -m "feat(seo): robots.txt and sitemap.xml per host

Landings spec decision 14: cv. lists its landing and the legal pages,
voyage. its landing, the root its landing only; app pages and the internal
/accueil paths stay out. URLs come from DOMAIN.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: The "poste only" wording, fixed where it lives today

Ruling 4 and Appendix A, « Wording fixes elsewhere ». Copy changes only, each
listed for the PM in the spec. A test keeps the old phrases from coming back.

**Files:**
- Create: `frontend/src/lib/wording.test.ts`
- Modify: `frontend/src/app/layout.tsx:44`
- Modify: `frontend/src/app/analyse/nouveau/page.tsx:388, 393, 394`
- Modify: `frontend/src/app/page.tsx:78, 79, 160, 390`

**Interfaces:** none.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/wording.test.ts`:

```ts
import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const read = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8")

// Landings spec, ruling 4: the cible is a métier, a formation, a poste or a
// projet. These phrases said it was only a job.
const PHRASES = [
  "poste que vous visez",
  "Vous visez un poste",
  "Le poste ou le secteur",
  "texte de l’offre d’emploi",
  "du point de vue des recruteurs",
]

test("no page says the cible is only a job", () => {
  for (const file of ["app/layout.tsx", "app/page.tsx", "app/analyse/nouveau/page.tsx"]) {
    const source = read(file)
    for (const phrase of PHRASES) assert.ok(!source.includes(phrase), `${file} still says « ${phrase} »`)
  }
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `(cd frontend && npm test)`
Expected: FAIL, naming `app/layout.tsx` and « poste que vous visez ».

- [ ] **Step 3: Make the eight replacements**

Use exact find-and-replace on each file, and keep every other character as it
is, including whatever space sits before a colon.

| File | Find | Replace with |
|---|---|---|
| `app/layout.tsx` | `face au poste que vous visez, et le voyage` | `face à ce que vous visez (métier, formation, poste ou projet), et le voyage` |
| `app/analyse/nouveau/page.tsx` | `— ou coller le texte de l’offre —` | `— ou coller le texte de l’offre, de la fiche métier ou du programme —` |
| `app/analyse/nouveau/page.tsx` | `Le poste ou le secteur que vous visez…` | `Le métier, la formation, le poste ou le projet que vous visez…` |
| `app/analyse/nouveau/page.tsx` | `Collez ici le texte de l’offre d’emploi…` | `Collez ici l’offre, la fiche métier ou le programme de formation…` |
| `app/page.tsx` | `Une offre d’emploi en main, ou le poste que vous visez décrit avec vos mots.` | `Un métier, une formation, un poste ou un projet, décrit avec vos mots, ou l’offre, la fiche métier ou le programme que vous avez en main.` |
| `app/page.tsx` | `du point de vue des recruteurs, en tenant compte des ATS.` | `face à votre cible et, pour une candidature, en tenant compte des ATS.` |
| `app/page.tsx` | `Vous visez un poste` | `Vous visez un métier, une formation, un poste ou un projet` |
| `app/page.tsx` | `face au poste que vous visez.` | `face à ce que vous visez.` |

(The root landing changes by these four sentences only; the developer approved
three, and the spec lists the fourth, the ATS one, for confirmation.)

- [ ] **Step 4: Run every check**

Run: `(cd frontend && npm test && npx tsc --noEmit && npm run lint; npm run build)`
Expected: 42 tests pass, `tsc` silent, lint at most 11 problems, build
succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/wording.test.ts frontend/src/app/layout.tsx frontend/src/app/page.tsx frontend/src/app/analyse/nouveau/page.tsx
git commit -m "fix(copy): the cible is never only a job

Landings spec ruling 4, Appendix A: the site description, the analysis
form's hints and four sentences of the root landing now name a métier, a
formation, a poste or a projet. A test keeps the old phrases out.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: The docs

The spec's « Docs » section: CLAUDE.md, the split spec's amendment notes, and
TEST-PLAN.md.

**Files:**
- Modify: `CLAUDE.md` (« Sous-domaines »)
- Modify: `docs/superpowers/specs/2026-10-09-subdomain-split-design.md` (decisions 13 and 16)
- Modify: `TEST-PLAN.md` (rows 14.4, 14.6, 14.16, and a new section 15)

**Interfaces:** none.

- [ ] **Step 1: CLAUDE.md**

In « Sous-domaines », replace the two table rows:

```markdown
| `cv.DOMAIN` | « J'ai une cible »: `/analyse/*`, `/rapport`, `/espace`; `/` → `/analyse/nouveau` until its landing exists |
| `voyage.DOMAIN` | le voyage: `/voyage/*`; `/` → `/voyage` |
```

with:

```markdown
| `cv.DOMAIN` | « J'ai une cible »: its landing at `/`, `/analyse/*`, `/rapport`, `/espace` |
| `voyage.DOMAIN` | le voyage: its landing at `/`, `/voyage/*` |
```

Then, after the paragraph that ends with « uses `AppLink`, `useSite().href` or
`go()` (`lib/site-context.tsx`). », add:

```markdown
- **Each subdomain's `/` is its landing**, served in place from
  `/accueil/cv` / `/accueil/voyage` (a rewrite in `proxy.ts`); a direct
  request for `/accueil/*` is sent back to `/`. In links, `/` and `/#anchor`
  mean the current host's own landing; another app's landing is
  `useSite().landing(app)` or `landingHref()`. Every landing string lives in
  `components/landing/copy/*.ts` (the PM reviews those files), and the 3D
  stills are re-rendered from `/dev/stills` in `next dev`. Spec:
  `docs/superpowers/specs/2026-10-10-subdomain-landings-design.md`.
```

- [ ] **Step 2: The split spec's amendment notes**

In `docs/superpowers/specs/2026-10-09-subdomain-split-design.md`, at the end
of decision 13 (after « …so the address stays `cv.DOMAIN/`. »), add:

```markdown
    *Amended 2026-10-10 (landings spec, decisions 8–9): `/` on cv and voyage
    now serves each app's landing from `/accueil/cv` / `/accueil/voyage`.*
```

At the end of decision 16, add:

```markdown
    *Amended 2026-10-10 (landings spec, decision 12): on cv and voyage, `/`
    and `/#anchor` mean that host's own landing; the root keeps its own.*
```

- [ ] **Step 3: TEST-PLAN.md**

(a) Row 14.4: replace its « Expect » cell with
`The cv. landing; then the voyage. landing (addresses unchanged)`.

(b) Row 14.6: replace its « Expect » cell with
`Logout lands on the voyage. landing at voyage.neoori.localhost:8080/; the cv tab goes to /connexion`.

(c) Row 14.16: replace its « Expect » cell with
`` `200`; `200`; `200`; `301` → `https://neoori.tech/` ``.

(d) Before `## What to report back`, add this section:

```markdown
## 15 · Les landings

`cv.neoori.localhost:8080` and `voyage.neoori.localhost:8080`, in Chrome
(spec: `docs/superpowers/specs/2026-10-10-subdomain-landings-design.md`).

| # | Do | Expect |
|---|---|---|
| 15.1 | Open `http://cv.neoori.localhost:8080/` in a new tab | « Lire un parcours face à sa cible. »; the logo's rings draw, then its letters rise; the address stays `/` |
| 15.2 | Reload | The logo is still (once per tab session) |
| 15.3 | Click « Je suis conseiller » | Scrolls to « Pour les conseillers » |
| 15.4 | Click « Analyser mon CV »; then Back | The form opens through a growing circle with an orange ring; Back shows the landing whole |
| 15.5 | Signed out, on voyage., click « Commencer le voyage » | The circle, peach ring, opens on `/inscription?redirect=%2Fvoyage` |
| 15.6 | Sign in as a candidate, then a counselor; open both landings | « Mon espace » leads to `/espace` (cv.), `/voyage` (voyage.), `/conseiller` (counselor) |
| 15.7 | At 1440 px, wait a second after load | The 3D object floats and follows the pointer; Network shows one three.js chunk |
| 15.8 | At 390 px, reload | The 3D object is an image first; no three.js chunk; buttons full width, notes left; the cv. tiers and the voyage. steps are vertical lines |
| 15.9 | DevTools > Rendering > « prefers-reduced-motion: reduce », reload | No logo motion, no rise, no wipe, the 3D a still image |
| 15.10 | Launch Chrome with `--disable-3d-apis`, open both landings | The still images; no error |
| 15.11 | `curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: cv.neoori.localhost' http://127.0.0.1:8080/accueil/cv` | `307` |
| 15.12 | `curl -s -H 'Host: voyage.neoori.localhost' http://127.0.0.1:8080/robots.txt` | voyage.'s rules and its sitemap URL |
| 15.13 | Open `cv.…/cgv`, then `voyage.…/cgv` | The cv. menu and footer; then a navy bar and the footer |

After the deploy, on production:

| # | Do | Expect |
|---|---|---|
| 15.14 | `curl -sI https://cv.neoori.tech https://voyage.neoori.tech \| grep -iE '^HTTP'` | `200` twice |
| 15.15 | `curl -s https://cv.neoori.tech \| grep -o 'property="og:url" content="[^"]*"'` | `https://cv.neoori.tech/`; the same check on voyage. names voyage. |
| 15.16 | In Safari (macOS or iOS), the wipe and the reduced-motion check | As 15.4 and 15.9: Safari does not resolve `*.localhost`, so it is checked here |
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md TEST-PLAN.md docs/superpowers/specs/2026-10-09-subdomain-split-design.md
git commit -m "docs: the landings in CLAUDE.md, the split spec and the test plan

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Final checks — speed, accessibility, the screenshot round

Decisions 30–31 and the spec's « Testing » section. Nothing new ships here
except a small measuring script. The results go into the hand-over to the
developer.

**Files:**
- Create: `frontend/scripts/landing-weight.mjs`

**Interfaces:** none.

- [ ] **Step 1: Every automated check, from clean**

Run: `(cd frontend && rm -rf .next && npm test && npx tsc --noEmit && npm run lint; npm run build)`
Expected: 42 tests pass, `tsc` silent, lint at most 11 problems, build
succeeds.

- [ ] **Step 2: Start the production build locally**

```bash
(cd frontend && cp -R public .next/standalone/ && mkdir -p .next/standalone/.next && cp -R .next/static .next/standalone/.next/)
(cd frontend/.next/standalone && DOMAIN=neoori.localhost PUBLIC_SCHEME=http PUBLIC_PORT=3000 PORT=3000 HOSTNAME=0.0.0.0 node server.js)
```

Run the second command in the background. `HOSTNAME=0.0.0.0` is the
Dockerfile's: keep it. Bound to `127.0.0.1`, the landings answer 307 here
although they work in production (the comment in `proxy.ts`, Task 2 Step 5).
The server listens on every interface while it runs; Step 8 stops it.

Then check:

```bash
for h in neoori.localhost cv.neoori.localhost voyage.neoori.localhost; do curl -s -o /dev/null -w "$h %{http_code}\n" -H "Host: $h" http://127.0.0.1:3000/; done
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: cv.neoori.localhost' http://127.0.0.1:3000/dev/stills
```

Expected: `200` for each of the three hosts, then `404`: the dev page does
not exist in production.

- [ ] **Step 3: Write the weight script**

`frontend/scripts/landing-weight.mjs`:

```js
// What a first visit to one page downloads, compressed (landings spec,
// decision 30): HTML, CSS and JS gzipped as the server sends them, plus the
// preloaded fonts and the stills the HTML names. The live 3D chunk is not
// counted: it loads after the page, on capable desktops only. Neither are
// pictures served through /_next/image (the root landing's photos): their
// size depends on the screen, so the script reports how many, not their weight.
// Usage: node scripts/landing-weight.mjs http://127.0.0.1:3000 cv.neoori.localhost
// (the host goes in a header: Node does not resolve *.localhost on macOS).
import http from "node:http"
import { gzipSync } from "node:zlib"

const [base, host] = process.argv.slice(2)
if (!base || !host) throw new Error("usage: landing-weight.mjs <server origin> <host name>")

function get(path, accept = "*/*") {
  return new Promise((resolve, reject) => {
    const request = http.request(new URL(path, base), { headers: { host, accept } }, (response) => {
      if (response.statusCode !== 200) {
        response.resume()
        reject(new Error(`${response.statusCode} ${path}`))
        return
      }
      const chunks = []
      response.on("data", (chunk) => chunks.push(chunk))
      response.on("end", () => resolve(Buffer.concat(chunks)))
    })
    request.on("error", reject)
    request.end()
  })
}

const html = (await get("/", "text/html")).toString("utf8")
const assets = new Set()
for (const m of html.matchAll(/(?:src|href)="(\/_next\/static\/[^"]+\.(?:js|css))"/g)) assets.add(m[1])
// Next.js names the preloaded fonts in React's flight data (`:HL[…]`) and in a
// Link header, never in a <link> tag: take every font file the page names.
for (const m of html.matchAll(/\/_next\/static\/media\/[^"\\\s]+\.woff2/g)) assets.add(m[0])
const images = new Set()
for (const m of html.matchAll(/<source[^>]*media="\(min-width: 901px\)"[^>]*type="image\/avif"[^>]*srcSet="([^"]+)"/gi)) images.add(m[1])
for (const m of html.matchAll(/<img[^>]*\ssrc="(\/(?!_next)[^"]+)"/gi)) images.add(m[1])
const resized = html.match(/<img[^>]*\ssrc="\/_next\/image/gi)?.length ?? 0

const totals = { html: gzipSync(Buffer.from(html)).length, js: 0, css: 0, fonts: 0, images: 0 }
for (const path of assets) {
  const body = await get(path)
  if (path.endsWith(".js")) totals.js += gzipSync(body).length
  else if (path.endsWith(".css")) totals.css += gzipSync(body).length
  else totals.fonts += body.length
}
for (const path of images) totals.images += (await get(path, "image/avif,image/webp,*/*")).length
const kb = (n) => `${(n / 1024).toFixed(0)} KB`
const total = Object.values(totals).reduce((a, b) => a + b, 0)
const note = resized ? `, plus ${resized} /_next/image pictures not counted` : ""
console.log(host, Object.fromEntries(Object.entries(totals).map(([k, v]) => [k, kb(v)])), `total ${kb(total)}${note}`)
```

- [ ] **Step 4: Measure the three landings against the budget**

Run, with the production server from Step 2 still running:

```bash
(cd frontend && for h in neoori.localhost cv.neoori.localhost voyage.neoori.localhost; do node scripts/landing-weight.mjs http://127.0.0.1:3000 "$h"; done)
```

Expected:
- Each landing's total is at most 700 KB.
- Each landing's `js` is at most the root landing's `js` plus 25 KB (same
  build, same shared chunks). This is the « landing-specific client JS »
  budget.
- For reference, the plan's code measured on 2026-10-10 with stand-in stills
  at their budget sizes: root `js` 209 KB; cv. and voyage. `js` 200 KB,
  fonts 218 KB, totals about 580 KB.
- `images` adds the desktop AVIF to the phone WebP, although a visitor
  downloads one still: an upper bound.
- The root line leaves out its photos (« /_next/image pictures not counted »).
  Compare only its `js` with the landings'. The 700 KB budget is today's root
  landing as measured live on 2026-10-10: 685 KB (HTML 36, JS 207, CSS 18,
  fonts 218, images 206).

Write the three lines into the hand-over.

- [ ] **Step 5: Lighthouse, mobile and desktop**

For each of `http://neoori.localhost:3000/` (the « before » figure),
`http://cv.neoori.localhost:3000/` and `http://voyage.neoori.localhost:3000/`:

```bash
npx --yes lighthouse@12 "$URL" --form-factor=mobile --screenEmulation.mobile --throttling-method=simulate \
  --only-categories=performance,accessibility --output=json --output-path="$TMPDIR/lh.json" --chrome-flags="--headless=new" --quiet
node -e 'const r=require(process.env.TMPDIR+"/lh.json");const a=r.audits;console.log({LCP:a["largest-contentful-paint"].displayValue,CLS:a["cumulative-layout-shift"].displayValue,TBT:a["total-blocking-time"].displayValue,perf:r.categories.performance.score,a11y:r.categories.accessibility.score})'
```

Repeat with `--preset=desktop` in place of the three `--form-factor`,
`--screenEmulation` and `--throttling-method` flags.

Expected on mobile for both landings: LCP ≤ 2.5 s, CLS ≤ 0.05, TBT ≤ 200 ms.
Accessibility should be ≥ 0.95. If a target is missed, look in the JSON's
`audits` for the cause (usually the LCP image or a render-blocking request).
Fix it in the component that owns it, and re-run.

- [ ] **Step 6: The screenshot round**

In Chrome, on the dev stack, take a screenshot of each cell and keep them for
the hand-over:

| | 320 px | 390 px | 768 px | 1440 px |
|---|---|---|---|---|
| cv. landing, signed out | ✓ | ✓ | ✓ | ✓ |
| voyage. landing, signed out | ✓ | ✓ | ✓ | ✓ |
| cv. landing, signed in as a counselor | | ✓ | | ✓ |
| both landings, « prefers-reduced-motion: reduce » | | ✓ | | ✓ |
| `cv.…/cgv`, `voyage.…/cgv` | | ✓ | | ✓ |

Check on each screenshot:
- no sideways scroll
- no text over the 3D object
- buttons at least 44 px tall
- headlines without a lone last word

Then walk the keyboard through one landing:
- Tab: menu, doors, links, accordion, footer, each with a visible focus ring
- Enter on an accordion question opens it
- Escape: nothing breaks

- [ ] **Step 7: Firefox, and WebGL off**

- In Firefox (≥ 144) on both landings: the sections show without the scroll
  reveal, and the wipe works.
- Launch Chrome with `--disable-3d-apis`: the still images only, and no
  console error (TEST-PLAN 15.10).

Note in the hand-over any check that could not be done locally. Safari is
checked on production (TEST-PLAN 15.16).

- [ ] **Step 8: Commit the script, stop the server**

Stop the production server from Step 2. Then:

```bash
git add frontend/scripts/landing-weight.mjs
git commit -m "chore(landing): a script to weigh a first visit

Landings spec decision 30. Used for the final checks; results in the
hand-over.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Report to the developer:
- the three weight lines
- the Lighthouse figures (before and after)
- the screenshots
- the wipe's ring outcome (Task 10, Step 9)
- whether Next.js is on 16.4 or stayed on 16.2.6 (Task 1)
- the open items that gate the merge: the PM's approval of the sentence list
  (`components/landing/copy/*.ts`), `showPrices`, and the RGPD contact address

Merge and push only on the developer's go.
