# Les landings de cv. et voyage. — Design Spec
Date: 2026-10-10
Status: design approved in conversation 2026-10-10 (two rounds of visual
exploration, then a seven-part design summary, each approved); this written
spec awaits the developer's review. Decisions made while writing, which the
conversation did not cover, are marked **Claude's call** and listed again at
the end.

## Overview

The subdomain split (`docs/superpowers/specs/2026-10-09-subdomain-split-design.md`)
gave each product its own host and promised each one its own landing (ruling 2),
with `/` meanwhile redirecting straight into the product (decision 13). This
spec designs those two landings and the changes around them:

| Host | Today | After |
|---|---|---|
| `cv.DOMAIN/` | 307 → `/analyse/nouveau` | the cv. landing, « J'ai une cible » |
| `voyage.DOMAIN/` | 307 → `/voyage` | the voyage. landing, « Le voyage » |
| `DOMAIN/` | today's landing | unchanged, except four sentences (see « Wording fixes ») |

Both landings present their product as its own app, for advisors and for the
people they accompany, whoever they are. They share one look: neat, elegant,
professional, no people in any form, motion in the logo, a few 3D objects, the
∞ circle wipe from the October video ad.

**Base:** `initial` at 2b5b539. **Branch:** `feat/subdomain-landings`.

**Visual exploration** (private pages, the developer's account):
round 1, the building blocks, https://claude.ai/artifact/UNCumvFCvYouvX8EofR1mZ;
round 2, the heroes, https://claude.ai/artifact/SEjsvR73xvwV149iJm1cwA.
The round 2 prototype source is kept beside this spec, in
`2026-10-10-subdomain-landings/prototype/`, as reference only: the build
re-implements it inside the app. Every value the build needs is in
Appendix B, so the prototype can be deleted without loss.

## What the code does today (initial 2b5b539)

- `frontend/src/lib/site.ts`: `route()` answers `/` on cv and voyage with the
  `DAY_ONE` redirect. Its `Route` type has only `serve` and `redirect`.
- `frontend/src/proxy.ts`: asks `route()` first, then runs the sign-in gate.
- `frontend/src/app/page.tsx`: the root landing. With `(legal)/layout.tsx`, it
  is the only user of `SiteNav` / `SiteFooter`, whose links point at root
  anchors (`/#voyage` …), which by decision 16 always mean the root landing.
- `AppBar` logout calls `go("/")`, the root landing (decision 16).
- `frontend/src/components/brand/Logo.tsx`: renders `public/neoori-logo.png`, a
  two-line lockup whose second line is an English tagline. Dark backgrounds
  get it on a white plate. `variant="mark"` points at `/img/neoori-mark.png`,
  which does not exist. The vector files in `public/brand/` are unused.
- No `robots.txt`, no sitemap. `layout.tsx` metadata is the same on every
  host apart from `metadataBase` and `og:url`.
- `next` 16.2.6, `react` 19.2.4. React's `<ViewTransition>` exists only in the
  React build Next bundles, behind `experimental.viewTransition`.
- No animation or 3D library is installed (`tw-animate-css` only).
- Measured live on 2026-10-10 (gzip): root landing HTML 36 KB, JS 207 KB,
  CSS 18 KB, fonts 218 KB (5 files), images 206 KB (WebP; AVIF is not switched
  on). The analysis form loads 348 KB of JS. The server sends gzip, not Brotli.

## Decisions

### Rulings (developer, 2026-10-10)

1. **The look:** neat, elegant, professional, using current web technology.
   **No humans in any form:** no photos, drawings, 3D characters, avatars,
   silhouettes or person icons. Motion in the logo, 3D here and there, the ∞
   circle wipe from the video ad. Free tools only (no paid plan, trial,
   watermark or non-commercial tier). The first reference, SmartyMe, was
   dropped.
2. **3D is a mix (option C).** Every visitor first sees a still image of the
   exact 3D scene. On capable devices, the live scene replaces it once the
   page is ready.
3. **Building blocks (round 1):**
   - logo motion A, « Tracé »
   - for voyage., the oo mark extruded from the logo, in frosted glass
   - for cv., an A4 sheet with the report's § marks and a « cible » ring in matte ceramic
   - cv. ground: cool grey `#f4f6fa` (not the charter mint)
   - voyage.: the charter navy `#1c3561` (not a darker night navy)
   - the three brand fonts, unchanged
4. **The « cible » is never only a job.** It is a métier, a formation, a
   poste or a projet. neoori is an app for advisors, and advisors accompany
   everyone.
5. **The hero speaks to both audiences (option C).** One headline that holds
   for both, then two buttons side by side: the person's (« Analyser mon
   CV » / « Commencer le voyage ») and « Je suis conseiller ». A full
   advisors section sits lower on the page.
6. **Directions (round 2):**
   - cv., direction 2 « Le rapport en index »
   - voyage., direction 2 « Six étapes »
   - **cv. on phones, reworked after review to follow voyage's pattern:** the
     3D panel first, then the copy and the two buttons, then the report's
     sections as one vertical line with a marker per tier.
7. **Design summary approved in full**, including these changes outside the
   two landings:
   - `/` in links means each app's own landing on cv. and voyage.
   - the vector logo replaces the PNG across the whole app
   - the "poste only" wording is fixed, including on the root landing
   - Next.js is upgraded to 16.4 first
   - signed-in visitors see the landing too

### Routing and hosts

8. **`/` on cv. and voyage. is an internal rewrite** to `/accueil/cv` and
   `/accueil/voyage`, so the address stays `cv.DOMAIN/`. This is decision 13
   of the split spec, carried out. `route()` gains a third answer,
   `{ kind: "rewrite", path }`, and `proxy.ts` answers it with
   `NextResponse.rewrite`, before the sign-in gate: a landing is public.
9. *Claude's call.* **The `/accueil` paths are internal.** A direct request
   for `/accueil` or `/accueil/*`, on any host, gets a 307 to the `/` of the
   host that owns that landing: `/accueil/voyage` goes to `voyage.DOMAIN/`,
   anything else to `cv.DOMAIN/`. A rewrite does not run the proxy again, so
   the redirect never loops. One page then lives at one address, for people
   and for search engines alike.
10. **The root is unchanged:** `/` on the root host and on unknown hosts still
    serves today's landing (decisions 5 and 18).
11. **Signed-in visitors see the landing too.** Its menu shows « Mon espace »
    instead of « Se connecter », linking to `homeFor(role, app)`: `/espace`
    or `/voyage` for a candidate, `/conseiller` for a counselor, `/admin`
    for an admin.
12. **On cv. and voyage., `/` in a link means that host's own landing**, and
    `/#anchor` an anchor on it. This amends decision 16 of the split spec.
    - `resolveHref("/", site)` returns `/` on every host.
    - A link that must reach another app's landing uses a new helper,
      `landingHref(app, site)`, which returns `/` on that host and that
      host's origin + `/` everywhere else.
    - Logging out (`AppBar`, `go("/")`) now lands on the current app's landing.
    - The auth pages' logo leads there too.
    - The root keeps its own landing for all of these.
13. *Claude's call.* **Legal pages take the host's nav and footer.**
    `(legal)/layout.tsx` renders `LandingNav` / `LandingFooter` for the
    host's app on cv. and voyage., and `SiteNav` / `SiteFooter` on the root.
    Otherwise `/#voyage`-style links would, under decision 12, point at
    anchors the cv. landing does not have.
14. **Each host gets its own `robots.txt` and `sitemap.xml`**, from
    `app/robots.ts` and `app/sitemap.ts`, reading the host per request.
    *Claude's call* on the content (all URLs absolute, built from `DOMAIN`):

    | Host | Allow | Disallow | Sitemap lists |
    |---|---|---|---|
    | cv | `/` | `/analyse`, `/rapport`, `/espace`, `/profil`, `/conseiller`, `/admin`, `/c/`, `/accueil` | `/`, `/cgv`, `/confidentialite`, `/mentions-legales` |
    | voyage | `/` | `/voyage`, `/profil`, `/conseiller`, `/admin`, `/accueil`, and the legal pages (cv's sitemap lists them) | `/` |
    | root | `/` | everything else | `/` |

    Both files have an extension, so `passesThrough` already serves them
    on every host.
15. **Each landing has its own metadata**, through `generateMetadata` in its
    page:
    - title and description (Appendix A)
    - canonical: the host's origin + `/`
    - `og:url` the same
    - `og:image`: a static `/og/cv.png` or `/og/voyage.png` (1200×630),
      made from the landing's 3D still, the logo and the headline, and
      committed

    Static share images are a *Claude's call*: they need no runtime
    rendering, and they pass the proxy as files.

### Page structure

16. **cv. landing, top to bottom** (anchors in brackets):
    1. **Menu:** logo (motion A), « Comment ça marche », « Pour les
       conseillers », « Tarifs », « Questions », « Se connecter » or « Mon
       espace », and « Le voyage », which links to the voyage. landing.
    2. **Hero:**
       - label « J'ai une cible », headline, one sentence underneath
       - the two buttons, each with a one-line note
       - the 3D sheet: on the right on desktop, spilling into the band below;
         on phones, first, as a full-width panel
    3. **Ce que contient le rapport** (`#rapport`): the three tiers with the
       real section titles.
       - Gratuit: §1–§3 and Verdict
       - Complet: §4–§9
       - Premium: §10–§11

       Three white cards on desktop. On phones, one vertical line with a
       marker per tier: orange and lit for Gratuit, navy for Complet,
       outlined for Premium. The titles are read from one shared constant,
       which mirrors `backend/app/services/section_registry.py`, never typed
       again by hand.
    4. **Comment ça marche** (`#comment`): three steps. Votre CV, votre
       cible, votre lecture.
    5. **Quatre façons de commencer** (`#commencer`): what each door gives
       and where its report goes, from CLAUDE.md « Les quatre portes ».
       - avec votre compte
       - avec un code promo
       - avec un code conseiller
       - sans compte
    6. **Pour les conseillers** (`#conseillers`, the target of « Je suis
       conseiller »): four points, « Créer un compte conseiller »
       (`/inscription-conseiller`), « Se connecter » (`/connexion`).
    7. **Tarifs** (`#tarifs`): Gratuit, Complet 9 €, Premium 24 €, paid once,
       no subscription. Built, but shown only when `showPrices` in
       `copy/cv.ts` is true. It stays `false` until the PM agrees (Open
       items); while false, the menu drops « Tarifs ».
    8. **Vos données** (`#donnees`).
    9. **Questions** (`#questions`): an accordion of seven questions, using
       `components/ui/accordion`.
    10. **Final call:** the video ad's closing line, both buttons, and a
        link to the voyage. landing for people without a cible yet.
    11. **Footer** (`LandingFooter`).
17. **voyage. landing, top to bottom:**
    1. **Menu:** logo with white letters, « Les six étapes », « Pour les
       conseillers », « Questions », « Se connecter » or « Mon espace », and
       « J'ai une cible », which links to the cv. landing.
    2. **Hero:**
       - label « Le voyage », headline, one sentence underneath
       - the two buttons, each with a one-line note
       - the six sessions drawn as a path, session 0 lit
       - the glass oo above the path's far end, with mist drifting in front
    3. **Ce que vous emportez** (`#emporter`): « Votre phrase », « Votre
       portrait », and the line « Ni note, ni score ».
    4. **Comment ça se passe** (`#etapes`): session 0 on your own, sessions 1
       to 5 with your counselor, the portrait, and how the voyage feeds the
       CV analyses.
    5. **Pour les conseillers** (`#conseillers`).
    6. **Vos données** (`#donnees`).
    7. **Questions** (`#questions`): six questions.
    8. **Final call:** the ad's closing line, both buttons, and a link to the
       cv. landing.
    9. **Footer.**

    **The background goes from navy to dawn as the page goes down:**
    - hero `#1c3561`
    - « Ce que vous emportez » `#22406f`
    - « Comment ça se passe » `#3a3f66`, the dusk
    - from « Pour les conseillers » on, `#f8f3ee`, the dawn, with navy text

    These are static colours, one per section; only the hero has mist.
18. **Phones (≤ 900 px):**
    - Both heroes stack: menu, then the 3D (a still image on phones; see
      decision 23), then the copy and the buttons. On voyage. the six-step
      path comes next.
    - Buttons are full width.
    - Their notes sit left-aligned under each button, never centred.
    - Both vertical lines (cv. tiers, voyage. steps) use the same marker
      language: 15 px dot, 1 px line, the first marker lit.

### Motion

19. **Logo motion A** plays on the two landings only, the first time a
    landing is shown in a browser tab (a `sessionStorage` flag, every access
    in try/catch; if storage throws, it plays). Every other page, and the
    landings under « reduce motion », show the logo still. Timings are in
    Appendix B. *Claude's call:* per tab session rather than per visitor
    ever, so nothing outlives the visit.
20. **The hero copy rises in once** on load, in CSS: 0.8 s, the house curve,
    each element 80 ms after the last.
21. **Sections fade in as they scroll into view, in CSS only:** a scroll
    timeline wrapped in `@supports (animation-timeline: view())`. Chrome 115+
    and Safari 26+ animate. Firefox, which has no scroll timelines yet, shows
    the sections as they are. No JavaScript is involved.
22. **The ∞ wipe opens the product.** It runs on the hero's main button and
    the final call's main button.
    - « Analyser mon CV » goes to `/analyse/nouveau`; « Commencer le voyage »
      goes to `/voyage`, where the proxy sends a signed-out visitor on to
      `/inscription` (split spec decision 14).
    - The navigation runs as a View Transition: the new page is revealed
      through a circle growing from the clicked point, 900 ms, curve
      `cubic-bezier(.76,0,.24,1)` (the ad's).
    - A thin ring rides the circle's edge: 5 px, orange `#ea5624` on cv.,
      peach `#f7b394` on voyage., fading out over the second half. The ring
      is its own transition layer (`view-transition-name: neoori-wipe-ring`),
      sized to the full circle and scaled from 0, so it stays sharp.
    - **Fallbacks:**
      - if the ring cannot be made sharp in Chrome and Safari, the wipe
        ships without it (Testing, item 6)
      - browsers without View Transitions, and visitors who ask for
        reduced motion, simply navigate
      - the button stays a real link, so it also works without JavaScript
23. **Reduce motion turns all of it off:** no logo motion, no rise, no
    reveals, no wipe, no mist drift, no 3D motion. The 3D stays a still
    image.

### 3D

24. **`HeroObject`**, one client component per landing. Its behaviour:
    1. **On the server**, it renders the still image as a `<picture>`: AVIF,
       then WebP, then PNG, with one source for desktop and one for phones
       (`media`), explicit `width` and `height`, and `alt=""` because it is
       decorative.
    2. **After the page's `load` event and an idle moment**, it checks every
       condition below. *Claude's call* on the thresholds.
       - the viewport is wider than 900 px
       - no « reduce motion »
       - `navigator.connection.saveData` is not true
       - `effectiveType` is not `slow-2g`, `2g` or `3g`
       - `deviceMemory` is at least 4, or unknown
       - `hardwareConcurrency` is at least 4, or unknown
       - a WebGL 2 context can be created
    3. **If all hold**, it imports the scene module (a separate chunk that
       holds three.js), renders the first frame, which shows exactly what
       the still shows, then crossfades in 300 ms and hides the still.
    4. **While live**, it pauses when off-screen or when the tab is hidden,
       and frees its WebGL resources when the page is left.
    5. **On any failure**, the still stays and one console error is logged;
       nothing is shown to the visitor.
25. **Two scene modules**, `components/landing/scenes/sheet.ts` (cv.) and
    `scenes/mark.ts` (voyage.), port the round 2 prototype's `kit/scenes.js`
    (parameters in Appendix B).
    - three.js is pinned to 0.186.x. It is imported only by these two modules
      and loaded only through the dynamic import.
    - No React Three Fiber, no drei, no CDN at runtime: everything is served
      by our own server.
    - The pointer moves the object a little.
    - The idle motion is a slow float, as in the prototype.
26. **The still images come from the same scene modules**, so the switch from
    still to live is invisible. No Blender is needed. *Claude's call* on the
    pipeline:
    - A dev-only page, `/dev/stills`, renders each scene at t = 0, at twice
      the displayed size, for its desktop and its phone layout. It calls
      `notFound()` unless `NODE_ENV` is `development`. (Not `/__stills`:
      folders starting with `_` are private in the App Router.)
    - The page sends each PNG to a dev-only route handler, which writes it to
      `frontend/public/landing/`.
    - `frontend/scripts/encode-stills.mjs` encodes each PNG to AVIF and WebP
      with `sharp`, which already ships with Next (0.34.5).
    - The three formats are committed. Re-rendering after a design change is
      `npm run dev`, then open `/dev/stills`, then
      `node scripts/encode-stills.mjs`.
    - A still's edges are the exact page background (cv.: transparent over
      `#f4f6fa`; voyage.: `#1c3561`), so it blends into the page.

### Brand changes beyond the landings

27. **`Logo.tsx` renders the vector wordmark inline**:
    - The paths are generated once into
      `components/brand/logo-paths.ts`, from `public/brand/neoori-logo.svg`
      and `neoori-mark.svg`.
    - `tone="light"` / `onDark` draw white letters on the background itself,
      with no white plate.
    - `variant="mark"` draws the oo mark, which fixes the missing-file case.
    - The props stay the same. Each of the 12 files that use it is checked
      for size, because the vector is one line and wider than the two-line
      PNG.
    - The English tagline disappears with the PNG lockup, which also brings
      the logo in line with the Loi Toubon (all visible text in French).
    - `public/neoori-logo.png` stays on disk, but nothing in the UI uses it.
28. **`AnimatedLogo`** (landings only) uses the same paths, with motion A
    (Appendix B).

### Next.js upgrade

29. **The first task of the build upgrades `next` and `eslint-config-next`
    16.2.6 to the newest 16.4.x patch on the day of the build, and `react`
    / `react-dom` 19.2.4 to 19.3.x.**
    - 16.4.0 came out on 2026-10-06. It ships React 19.3, where
      `<ViewTransition>` is stable, and Next no longer needs a flag for it.
    - The task follows the official upgrade notes, then runs every check in
      « Testing ».
    - If a check fails and the cause can't be fixed within the task, we stay
      on 16.2.6 with `experimental.viewTransition: true`. If the wipe still
      misbehaves there, it is turned off: normal navigation, nothing else
      changes.

### Speed and accessibility

30. **Budgets per landing, first visit, compressed:**
    - everything together (HTML, CSS, JS, fonts and images), not counting the
      live 3D: at most 700 KB, today's root landing
    - landing-specific client JavaScript: at most 25 KB, with no animation
      library (CSS and the browser's Web Animations API do the work)
    - each desktop still at most 90 KB in AVIF; each phone still at most
      50 KB
    - the live 3D chunk, about 130 KB, loads after `load` and only on devices
      that pass decision 24

    Lighthouse targets (mobile, simulated 4G): main content (LCP) in at most
    2.5 s, layout shift (CLS) at most 0.05, blocking time (TBT) at most
    200 ms. Each target is measured before and after the change.
31. **Accessibility:**
    - landmarks, one `h1`, headings in order
    - AA contrast: orange text and buttons use `#c9491e`
    - a visible focus ring, and a menu that works from the keyboard
    - touch targets of at least 44 px
    - decorative canvas, stills and mist hidden from screen readers
    - French typography: U+00A0 before `:`, U+202F before `;` `!` `?`, and
      inside « »

### Copy

32. **Every visible string of the two landings lives in one place**,
    `components/landing/copy/cv.ts` and `copy/voyage.ts`, with their
    metadata. That file is what the PM reviews, and Appendix A is its first
    version. *Claude's call:* the rest of the app keeps its strings inline.
    Rules:
    - the PM's warm tone (memory « landing V3 copy »)
    - none of CLAUDE.md's banned words
    - the « cible » rule (ruling 4)
    - speak to advisors and to everyone they accompany
    - never promise a score, a type or a test result
    - no claim that data is processed in the EU
33. **The PM approves the sentence list before the merge.**

## How a page request is routed

```
proxy(request)
  path is a file, /_next/*, /__nextjs*, /api*      → serve (every host)
  path is /accueil or /accueil/*                   → 307 to the owning landing's host + "/"
  app = cv | voyage | root   (from the host; unknown → root)
  root:   path == "/"                              → serve today's landing
          otherwise                                → 307 to owner origin + path + query
  cv:     path == "/"                              → rewrite /accueil/cv
          owner == voyage                          → 307 voyage origin + path + query
  voyage: path == "/"                              → rewrite /accueil/voyage
          owner == cv                              → 307 cv origin + path + query
  then the sign-in gate, unchanged (a rewrite has already returned)
```

## Frontend

| Area | Files |
|---|---|
| Routing | `lib/site.ts` (`Route` rewrite kind, `LANDING`, `/accueil` rule, `resolveHref` for `/`, `landingHref`), `lib/site.test.ts`, `proxy.ts` |
| Landing routes | `app/accueil/cv/page.tsx`, `app/accueil/voyage/page.tsx` (server components, `generateMetadata`) |
| Landing components | `components/landing/`: `LandingNav`, `LandingFooter`, `AnimatedLogo`, `Doors`, `WipeLink`, `HeroObject`, `ReportIndex`, `Track`, `FourWays`, `AdvisorsSection`, `Pricing`, `DataSection`, `Faq`, `FinalCall`, `copy/cv.ts`, `copy/voyage.ts`, `scenes/sheet.ts`, `scenes/mark.ts`, `landing.css`. Styling: Tailwind utilities where they say it cleanly; `landing.css` for keyframes, scroll timelines, the View Transition pseudo-elements and the two hero layouts. The components import `landing.css` themselves (global CSS may be imported anywhere under `app/`), so the legal pages that use `LandingNav` get it too. |
| Stills | `app/dev/stills/page.tsx` + `app/dev/stills/save/route.ts` (dev only), `scripts/encode-stills.mjs`, `public/landing/*.{png,webp,avif}`, `public/og/{cv,voyage}.png` |
| SEO | `app/robots.ts`, `app/sitemap.ts` |
| Brand | `components/brand/Logo.tsx`, `components/brand/logo-paths.ts`, and the 12 files that render `<Logo>` (sizes) |
| Shared pages | `app/(legal)/layout.tsx` (decision 13), `components/layout/AuthLayout.tsx` and `AppBar.tsx` (decision 12) |
| Wording fixes | `app/layout.tsx`, `app/analyse/nouveau/page.tsx`, `app/page.tsx` (Appendix A, « Wording fixes ») |
| Dependencies | `package.json`, `package-lock.json`: the upgrade (decision 29) and `three` 0.186.x (decision 25) |

Backend, nginx, Docker: no change.

## Errors and edge cases

- **No JavaScript:** the page is server-rendered and complete; the still
  images show; the buttons are links.
- **No WebGL, or the live scene crashes:** the still stays.
- **Slow or data-saving connection:** the still only.
- **Firefox:** no section reveals (they show as they are); the wipe works
  from Firefox 144.
- **Safari before 18:** no wipe; a normal page change.
- **A signed-out visitor presses « Commencer le voyage »:** the proxy sends
  them on to `/inscription`, and the wipe reveals that page.
- **A counselor or an admin opens a landing:** « Mon espace » leads to
  `/conseiller` or `/admin`.
- **Someone types `/accueil/…`:** redirected to the landing's own `/`.
- **The domain changes:** canonical, `og:url`, robots and sitemap URLs all
  come from `DOMAIN`, so nothing breaks.
- **A dark-mode phone:** the landings keep their fixed look (cv. light,
  voyage. navy). There is no automatic dark mode.
- **`sessionStorage` blocked:** the logo plays each time; nothing breaks.

## Testing

1. **Unit tests** (`node --test src/lib/*.test.ts`, `site.test.ts`):
   - `/` on cv and voyage returns a rewrite to its `/accueil` path
   - `/` on root and on an unknown host serves
   - `/accueil`, `/accueil/cv` and `/accueil/voyage` redirect to the right
     origin, on each host
   - `resolveHref("/")` and `resolveHref("/#x")` stay on their host
   - `landingHref(app, site)` gives `/` on its own host and the absolute URL
     elsewhere
   - `robots.txt` and `sitemap.xml` pass through
2. **Type check, lint and build:** `tsc` clean; lint at the baseline
   (11 problems); `next build` succeeds.
3. **Logo:** every one of the 12 `<Logo>` call sites checked at its size, on
   light and dark backgrounds.
4. **Screenshots** of both landings at 390, 768 and 1440 px:
   - signed out and signed in
   - with « reduce motion »
   - with WebGL disabled (the still image stays)
   - in Firefox
5. **Lighthouse** (mobile and desktop) for each landing against decision 30.
   The before figure is today's root landing, the only landing there is.
6. **The wipe:** Chrome and Safari, ring sharp at 1× and 2× pixel density
   (decision 22), and back/forward navigation never stuck on a frame.
7. **Accessibility:** keyboard walk through the menu, the accordion and both
   buttons; contrast checked on every text colour.
8. **After deploy** (curl, no browser needed):
   - `cv./` and `voyage./` answer 200 with their own title
   - `/accueil/cv` answers 307 to `cv./`
   - robots and sitemap match decision 14 on all three hosts
   - `og:url` is right on each host
9. **TEST-PLAN.md** gains a walkthrough of both landings.

## Rollout

1. Build task by task on `feat/subdomain-landings`. The first task is the
   upgrade (decision 29).
2. Gate: the PM approves the sentence list (Appendix A, then `copy/*.ts`),
   including whether to show prices.
3. Merge into `initial` and push, which deploys, only on the developer's go.
4. Run the post-deploy checks (Testing, item 8).

**Rollback:** `IMAGE_TAG=<previous sha>` brings back the redirects and the
PNG logo. No data is involved.

## Docs

- **CLAUDE.md « Sous-domaines »:**
  - the host table says `/` serves each app's landing
  - the `/accueil` rule
  - the new meaning of `/` in links (decision 12)
  - « until its landing exists » removed
- **The split spec:** a dated amendment note at decisions 13 and 16 pointing
  here.
- **TEST-PLAN.md:** the landings walkthrough.

## Out of scope

- Redesigning the root landing (only its four sentences change).
- Analytics, a consent banner, A/B tests.
- An English version.
- An automatic dark mode.
- The voyage price.
- The Portrait module (CLAUDE.md « Out of scope »).
- AVIF for every image of the site (`images.formats`) and Brotli in nginx:
  two separate improvements found while measuring.
- Changing the analysis form or the voyage pages beyond the wording fixes.

## Open items

1. **PM:**
   - approve the sentence list
   - show prices on cv. (« Tarifs »)? The root landing already shows them.
   - the voyage price, if one is decided before the build
   - the RGPD contact address, which « Vos données » links to: it is still
     `[À COMPLÉTER]` in `/confidentialite`
2. **The 16.4 fix release:** take the newest patch on the day of the build.
3. **The four root-landing sentences:** the developer approved changing
   three; the fourth (« du point de vue des recruteurs, en tenant compte des
   ATS ») was found while writing this spec. Confirm it with the spec.

## Claude's calls

- 9: `/accueil` as the internal paths, and the redirect for direct requests.
- 13: legal pages take the host's nav and footer.
- 14: the robots and sitemap content.
- 15: static share images.
- 19: the logo plays once per tab session.
- 24: the live-3D thresholds, and the 900 px limit.
- 26: the still-image pipeline (dev page, route handler, sharp script).
- 16: « Tarifs » behind `showPrices` until the PM decides.
- 17: the voyage. colour steps from navy to dawn.
- 32: landing copy in one file per app.

---

## Appendix A — Sentence list (first version, for the PM)

Typography in the code follows decision 31. Below, spaces are plain.

### cv. — « J'ai une cible »

**Metadata**
- Title: Analyse de CV face à une cible · neoori
- Description: Un métier, une formation, un poste ou un projet : neoori lit le CV face à ce qui est visé et montre les forces, ce qui reste à renforcer et par où avancer. Gratuit pour commencer.
- Share image text: J'ai une cible · Lire un parcours face à sa cible.

**Menu**
Comment ça marche · Pour les conseillers · Tarifs · Questions · Se connecter (or Mon espace) · Le voyage · Ouvrir le menu / Fermer le menu (phone button labels)

**Hero**
- Label: J'ai une cible
- Headline: Lire un parcours face à sa cible.
- Underneath: Un métier, une formation, un poste, un projet : neoori lit le CV face à ce qui est visé, et montre les forces, ce qui reste à renforcer et par où avancer.
- Button: Analyser mon CV — Note: Gratuit pour commencer, avec ou sans compte.
- Button: Je suis conseiller — Note: Vos codes, et les rapports qui vous reviennent.

**Ce que contient le rapport**
- Title: Ce que contient le rapport
- Intro: Commencez gratuitement : §1 à §3 et un verdict. Le reste s'ajoute quand vous le souhaitez.
- Pour commencer · Gratuit: §1 Lecture stratégique du parcours · §2 Forces du profil pour la cible · §3 Compétences transférables · Verdict
- Rapport complet · Complet: §4 Ce qui reste à renforcer · §5 Préconisations terrain · §6 Exemple de réécriture · §7 Synthèse pour le candidat · §8 Pistes d'évolution · §9 Proposition de CV retravaillé
- En plus · Premium: §10 Préparation à l'entretien · §11 Questions difficiles

**Comment ça marche**
- Title: Comment ça marche
- Votre CV — En PDF (10 Mo au plus) ou en texte collé.
- Votre cible — Un métier, une formation, un poste ou un projet, décrit avec vos mots. Une offre, une fiche métier ou un programme en main ? Collez-le.
- Votre lecture — En quelques minutes : vos forces, ce qui reste à renforcer, et par où avancer.

**Quatre façons de commencer**
- Title: Quatre façons de commencer
- Intro: Vous choisissez au moment de lancer l'analyse.
- Avec votre compte — La version gratuite, puis le rapport complet si vous le souhaitez. Vos analyses restent dans votre espace.
- Avec un code promo — Le rapport complet, une fois par compte.
- Avec un code conseiller — Le rapport complet, sans créer de compte. Il est remis à votre conseiller, et vous le découvrez ensemble.
- Sans compte — La version gratuite, sur un lien privé valable 30 jours.

**Pour les conseillers**
- Label: Pour les conseillers
- Title: Proposez l'analyse aux personnes que vous accompagnez.
- Des codes à remettre, pour une analyse ou pour un voyage.
- Avec votre code, le rapport complet arrive dans votre espace conseiller, et nulle part ailleurs.
- Une note privée sur chaque analyse, visible de vous uniquement.
- Pour toute cible : un métier, une formation, un poste, un projet.
- Buttons: Créer un compte conseiller · Se connecter

**Tarifs** (if the PM agrees)
- Title: Tarifs
- Intro: Paiement unique, sans abonnement.
- Gratuit · 0 € — §1 à §3 et un verdict.
- Complet · 9 € — Le rapport complet, §1 à §9.
- Premium · 24 € — Le rapport complet, plus la préparation à l'entretien (§10 et §11).
- Note: Vous passez au rapport complet depuis votre rapport gratuit, quand vous le souhaitez.

**Vos données**
- Title: Vos données
- Votre CV et vos réponses servent à produire votre analyse.
- L'analyse est rédigée par une IA, à partir de votre CV et de votre cible.
- Vous pouvez supprimer une analyse à tout moment, depuis votre espace.
- Sans compte, le rapport s'efface de lui-même au bout de 30 jours.
- Link: Lire la politique de confidentialité

**Questions**
1. Ma cible n'est pas un poste précis. Est-ce que ça marche ? — Oui. Une cible peut être un métier, une formation, un poste ou un projet. Décrivez-la avec vos mots ; une offre, une fiche métier ou un programme de formation aide aussi.
2. Faut-il créer un compte ? — Non. Sans compte, vous recevez la version gratuite sur un lien privé valable 30 jours. Avec un compte, vos analyses restent dans votre espace et vous pouvez passer au rapport complet.
3. Que se passe-t-il avec un code conseiller ? — Le rapport complet est remis à votre conseiller, pas à vous. Vous le découvrez ensemble, en rendez-vous.
4. Combien de temps faut-il ? — Quelques minutes pour remplir le formulaire, puis quelques minutes pour l'analyse.
5. Qui rédige l'analyse ? — Une IA, à partir de votre CV, de votre cible et de vos réponses. Elle ne remplace pas un conseiller : elle prépare l'échange.
6. Puis-je supprimer mon analyse ? — Oui, depuis votre espace, à tout moment. Sans compte, elle s'efface d'elle-même au bout de 30 jours.
7. Je n'ai pas encore de cible. — Commencez par le voyage : six étapes pour poser ce que vous savez déjà de vous. (link: Découvrir le voyage)

**Final call**
- Title: Votre parcours a des choses à dire.
- Buttons: Analyser mon CV · Je suis conseiller
- Pas encore de cible ? Le voyage vous aide à la trouver. (link: Découvrir le voyage)

### voyage. — « Le voyage »

**Metadata**
- Title: Le voyage, du brouillard à la clarté · neoori
- Description: Six étapes pour poser ce que vous savez déjà de vous : la première en cinq minutes, en autonomie, les cinq suivantes avec un conseiller. Puis un portrait, relu ensemble.
- Share image text: Le voyage · Du brouillard à la clarté, une étape après l'autre.

**Menu**
Les six étapes · Pour les conseillers · Questions · Se connecter (or Mon espace) · J'ai une cible

**Hero**
- Label: Le voyage
- Headline: Du brouillard à la clarté, une étape après l'autre.
- Underneath: Six étapes pour poser ce que vous savez déjà de vous. La première se fait en cinq minutes, en autonomie ; les cinq suivantes, avec un conseiller.
- Button: Commencer le voyage — Note: Session 0 : cinq minutes, en autonomie.
- Button: Je suis conseiller — Note: Vos codes, les séances, le portrait à valider.
- Path: Session 0 — Dans 10 ans · cinq minutes, en autonomie · Session 1 — avec votre conseiller · Session 2 · Session 3 · Session 4 · Session 5 — puis le portrait, relu ensemble

**Ce que vous emportez**
- Title: Ce que vous emportez
- Votre phrase — Dès la session 0, une première phrase sur vous, tirée de vos 20 réponses.
- Votre portrait — Après la session 5, un portrait en six parties : ce qui vous fait vibrer, ce dont vous avez besoin, les chemins possibles… Votre conseiller le relit et le valide avec vous avant de vous le remettre.
- Ni note, ni score : le voyage décrit, il ne classe pas.

**Comment ça se passe**
- Title: Comment ça se passe
- Session 0, en autonomie — Dans 10 ans : 20 affirmations, oui, non ou « – ». Cinq minutes.
- Sessions 1 à 5, avec votre conseiller — Votre conseiller vous donne un code qui ouvre les séances. Vous avancez d'une séance à l'autre, à votre rythme.
- Le portrait — Rédigé à partir de vos réponses, relu et validé par votre conseiller, puis remis.
- Et vos analyses — Le voyage peut ensuite enrichir vos analyses de CV. (link: Découvrir J'ai une cible)
- Un compte gratuit garde vos réponses d'une séance à l'autre.

**Pour les conseillers**
- Label: Pour les conseillers
- Title: Accompagnez chaque voyage, séance après séance.
- Votre code ouvre les sessions 1 à 5.
- Une fiche de suivi par voyage, visible de vous uniquement.
- Le portrait se relit ensemble et n'est remis qu'après votre validation.
- Le voyage peut ensuite nourrir les analyses de CV.
- Buttons: Créer un compte conseiller · Se connecter

**Vos données**
- Title: Vos données
- Vos réponses, votre phrase et votre portrait sont chiffrés.
- Votre phrase et le premier jet du portrait sont rédigés par une IA ; le portrait n'est remis qu'après la relecture de votre conseiller.
- Vous pouvez effacer votre voyage à tout moment. L'effacement retire aussi ce que vos analyses de CV en avaient repris.
- Link: Lire la politique de confidentialité

**Questions**
1. Faut-il un conseiller ? — Pas pour la session 0 : elle se fait en autonomie, en cinq minutes. Les sessions 1 à 5 se font avec un conseiller, qui vous donne un code.
2. Je n'ai pas de conseiller. — Commencez par la session 0. Pour la suite, parlez-en à la structure qui vous accompagne : Mission Locale, Cap Emploi, France Travail ou un conseil en évolution professionnelle.
3. Est-ce un test de personnalité ? — Non. Le voyage ne vous classe pas et ne vous donne pas de score. Il vous aide à poser des mots sur ce que vous savez déjà.
4. Combien de temps ça prend ? — Cinq minutes pour la session 0. Pour les suivantes, le rythme se décide avec votre conseiller.
5. Faut-il un compte ? — Oui, pour garder vos réponses d'une séance à l'autre. La création du compte est gratuite.
6. Puis-je tout effacer ? — Oui, à tout moment. L'effacement retire aussi ce que vos analyses de CV en avaient repris.

**Final call**
- Title: Votre parcours a des choses à dire. Aidez-le à les dire.
- Buttons: Commencer le voyage · Je suis conseiller
- Vous avez déjà une cible ? (link: Analyser mon CV)

### Shared

**Footer (both landings)**
- Pour les conseillers et les personnes qu'ils accompagnent.
- Links: J'ai une cible · Le voyage · Mentions légales · Confidentialité · CGV · Se connecter
- © 2026 neoori

### Wording fixes elsewhere

| Where | Today | After |
|---|---|---|
| `app/layout.tsx:44` (site description, every host) | … l'analyse de votre CV face au poste que vous visez, et le voyage … | … l'analyse de votre CV face à ce que vous visez (métier, formation, poste ou projet), et le voyage … |
| `app/analyse/nouveau/page.tsx:388` | — ou coller le texte de l'offre — | — ou coller le texte de l'offre, de la fiche métier ou du programme — |
| `app/analyse/nouveau/page.tsx:393` | Le poste ou le secteur que vous visez… | Le métier, la formation, le poste ou le projet que vous visez… |
| `app/analyse/nouveau/page.tsx:394` | Collez ici le texte de l'offre d'emploi… | Collez ici l'offre, la fiche métier ou le programme de formation… |
| `app/page.tsx:78` (root) | Une offre d'emploi en main, ou le poste que vous visez décrit avec vos mots. | Un métier, une formation, un poste ou un projet, décrit avec vos mots, ou l'offre, la fiche métier ou le programme que vous avez en main. |
| `app/page.tsx:79` (root, found while writing — confirm) | … du point de vue des recruteurs, en tenant compte des ATS. | … face à votre cible et, pour une candidature, en tenant compte des ATS. |
| `app/page.tsx:160` (root) | Vous visez un poste : neoori lit … | Vous visez un métier, une formation, un poste ou un projet : neoori lit … |
| `app/page.tsx:390` (root) | … face au poste que vous visez. | … face à ce que vous visez. |

---

## Appendix B — Visual values

**Colours**
- Navy (text, voyage.): `#1c3561`
- Secondary text: `#56637b`
- Hairlines: `rgba(28,53,97,.12)`
- Buttons and orange text: `#c9491e`, hover `#b23f18`
- Orange marks: `#ea5624`
- Peach: `#f7b394`
- Peach-soft: `#fdeee5`
- cv. ground: `#ffffff`, bands `#f4f6fa`
- voyage. progression: `#1c3561` → `#22406f` → `#3a3f66` → `#f8f3ee`
- Free tag: `#e3f2ec` / `#1d6b53`
- Complet tag: `#fdeee5` / `#9a3f19`
- Premium tag: `#e9edf6` / `#1c3561`
- Logo letters: `#213a68`
- The oo gradient: `#ec6932` → `#f49b68` → `#f6b385`, horizontal

**Type**
- Headline: Plus Jakarta Sans 800, letter-spacing −0.032 em (−0.042 em on the cv. hero), line-height 1.02 (0.98 on the cv. hero), `text-wrap: balance`.
  - cv. hero: `clamp(2.8rem, 7vw, 6.2rem)`, and `clamp(2.3rem, 10.5vw, 3.4rem)` at 900 px and below
  - voyage. hero: `clamp(2.6rem, 5.4vw, 4.6rem)`
- Body: Inter 400, 17 px; hero line `clamp(1.05rem, 1.45vw, 1.2rem)`, at most 46 characters per line.
- Labels: JetBrains Mono 500, 0.74 rem, letter-spacing 0.16 em, capitals.
- Button notes: Inter 0.86 rem.

**Layout**
- Container 1240 px; side gutter `clamp(20px, 4vw, 40px)`; menu 76 px tall.
- Single breakpoint: 900 px.
- Sections: `clamp(64px, 9vw, 112px)` top and bottom.
- Buttons: 17 × 22 px padding, 14 px radius.
- Cards: 20 px radius, shadow `0 1px 2px rgba(28,53,97,.05), 0 16px 34px -24px rgba(28,53,97,.3)`.

**Motion**
- House curve: `cubic-bezier(.22,1,.36,1)`.
- Wipe: `cubic-bezier(.76,0,.24,1)`, 900 ms. The ring's opacity is 1 − smoothstep(0.55, 1, p).
- Logo motion A:
  - the two rings draw through a mask of stroked circles: radius 47.24, stroke 44, dash length = circumference
  - left ring starts at 12 o'clock, right ring at 6 o'clock, both clockwise
  - 900 ms each, curve `cubic-bezier(.65,0,.35,1)`, the right ring 160 ms after the left
  - then the letters n e r i rise from +28 px with opacity 0 → 1, 620 ms each, starting at 560 ms and 70 ms apart, curve `cubic-bezier(.16,1,.3,1)`
- Mist: blurred radial layers drifting ±4 %, over 26 s and 34 s, back and forth.

**3D (three.js 0.186, from `prototype/src/kit/scenes.js`)**
- **Renderer and lighting:**
  - antialias on, pixel ratio capped at 2, `NeutralToneMapping`, sRGB output
  - light from `RoomEnvironment` through `PMREMGenerator`, at 0.04 blur
  - camera FOV 28°
- **cv. sheet:**
  - camera at z 9.4, transparent background
  - A4 sheet: `RoundedBoxGeometry(2.1, 2.97, 0.06, 4, 0.05)`, physical material, white, roughness 0.62, clearcoat 0.15
  - bars on the sheet, positions in the prototype:
    - orange label `#ea5624`
    - navy title `#1c3561`
    - three sections at y 0.62 / −0.06 / −0.74, each an orange § chip `#ea5624`, a heading `#2b4677` and four lines `#dfe5ee`
  - ring: `TorusGeometry(0.52, 0.085, 48, 160)`, oo-gradient ceramic (roughness 0.44, clearcoat 0.5), with an orange sphere of radius 0.07 at its centre; ring at (0.5, 0.75, 0.75), rotation (0.25, −0.45, 0)
  - soft shadow plane 3.4 × 4.2 at (0.3, −0.35, −1.4)
  - pose: x −0.38, y 0.34, z 0.08
  - key light white, intensity 1.1, at (3, 5, 6)
  - layout scale: desktop min(1.12, w / 2.8); phone min(1.18, h / 3.9) with y −0.12
- **voyage. mark:**
  - camera at z 9, background `#1c3561`
  - shape: the oo mark's SVG path, extruded with depth 22, curve segments 72; bevel thickness 7, size 3, offset −3, segments 8; flipped (1, −1, −1), centred, scaled 0.0175
  - glass:
    - colour `#ffeee4`, roughness 0.28, transmission 1, thickness 26, IOR 1.45
    - attenuation colour `#f2a27a`, attenuation distance 1.6 (in world units: the value 70–80 used in round 1 gave no tint at all)
    - clearcoat 1, clearcoat roughness 0.12
  - dawn glow: an opaque disc of radius 3.6, radial gradient `#8d6468` → `#454468` (at 0.42) → `#1c3561`, placed 0.45 below the mark at z −3
  - lights: key `#fff1e6` 1.4 at (3, 4, 5); rim `#f7b394` 2.2 at (−4, −1, −3)
  - layout: desktop x = 0.31·w, y = 0.06·h, scale min(0.72, 0.3·w / 3.94); phone centred, scale min(0.7, 0.62·w / 3.94)
- **Idle motion:**
  - cv.: sheet rotation y 0.34 + 0.12·sin(0.4t), x −0.38 + 0.04·sin(0.3t); ring bobbing 0.05·sin(1.1t)
  - voyage.: mark rotation y 0.32·sin(0.45t), x −0.12 + 0.06·sin(0.33t)
  - the pointer adds up to ±0.35 rad, eased at 5 % per frame
