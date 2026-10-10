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
  // The root shows its landing alone, but crawlers still need what that page
  // is made of: favicon, share image, styles, scripts, fonts and photos
  // (review finding: without them, no favicon in results, no share card).
  assert.deepEqual(robotsFor("root", PROD), {
    rules: {
      userAgent: "*",
      allow: ["/$", "/_next/", "/img/", "/icon.svg", "/favicon.ico", "/sitemap.xml"],
      disallow: ["/"],
    },
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
