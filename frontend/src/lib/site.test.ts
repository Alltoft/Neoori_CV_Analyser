import { test } from "node:test"
import assert from "node:assert/strict"
import {
  appOfHost, isInternalLanding, landingHref, origin, ownerOf, passesThrough, resolveHref, route,
  settingsFromEnv, type AppName, type Site, type SiteSettings,
} from "./site.ts"
import { signInRedirect } from "./sign-in-gate.ts"

const PROD: SiteSettings = { domain: "neoori.tech", scheme: "https", port: "" }
const DEV: SiteSettings = { domain: "neoori.localhost", scheme: "http", port: "8080" }
const serve = { kind: "serve" }
const to = (location: string) => ({ kind: "redirect", location })
const rewrite = (path: string) => ({ kind: "rewrite", path })
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
  assert.deepEqual(r("/"), rewrite("/accueil/cv"))
  assert.deepEqual(r("/analyse/nouveau"), serve)
  assert.deepEqual(r("/espace"), serve)
  assert.deepEqual(r("/connexion", "?redirect=%2Fvoyage"), serve)
  assert.deepEqual(r("/voyage"), to("https://voyage.neoori.tech/voyage"))
  assert.deepEqual(r("/voyage/etape/parcours", "?a=b"), to("https://voyage.neoori.tech/voyage/etape/parcours?a=b"))
})

test("voyage serves its own and the shared paths, and hands cv's over", () => {
  const r = (path: string, search = "") => route("voyage.neoori.tech", path, search, PROD)
  assert.deepEqual(r("/"), rewrite("/accueil/voyage"))
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
  // Landings spec, decision 12: "/" and "/#…" are this host's own landing.
  assert.equal(resolveHref("/#rapport", on("cv")), "/#rapport")
  assert.equal(resolveHref("/", on("voyage")), "/")
  assert.equal(resolveHref("/inscription-conseiller", on("root")), "https://cv.neoori.tech/inscription-conseiller")
  assert.equal(resolveHref("/analyse", on("root")), "https://cv.neoori.tech/analyse")
  assert.equal(resolveHref("mailto:a@b.fr", on("root")), "mailto:a@b.fr")
  assert.equal(resolveHref("https://stripe.test/s", on("cv")), "https://stripe.test/s")
})

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
