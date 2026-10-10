import type { MetadataRoute } from "next"
import { origin, type AppName, type SiteSettings } from "./site.ts"

// Landings spec, decision 14. cv. lists the legal pages; voyage. keeps its
// copies out of the index; the root shows its landing and nothing else.
const DISALLOW: Record<AppName, string[]> = {
  cv: ["/analyse", "/rapport", "/espace", "/profil", "/conseiller", "/admin", "/c/", "/accueil"],
  voyage: ["/voyage", "/profil", "/conseiller", "/admin", "/accueil", "/cgv", "/confidentialite", "/mentions-legales"],
  root: ["/"],
}

// The root's landing at "/" only ("/$"), plus what that page is made of:
// without its favicon, share image, styles and scripts, search results lose
// the favicon and shared links their card. The longest matching rule wins,
// so these beat « Disallow: / ».
const ROOT_ALLOW = ["/$", "/_next/", "/img/", "/icon.svg", "/favicon.ico", "/sitemap.xml"]

const LISTED: Record<AppName, string[]> = {
  cv: ["/", "/cgv", "/confidentialite", "/mentions-legales"],
  voyage: ["/"],
  root: ["/"],
}

/** robots.txt for one host, every URL built from DOMAIN. */
export function robotsFor(app: AppName, settings: SiteSettings): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: app === "root" ? ROOT_ALLOW : "/", disallow: DISALLOW[app] },
    sitemap: `${origin(app, settings)}/sitemap.xml`,
  }
}

/** sitemap.xml for one host. */
export function sitemapFor(app: AppName, settings: SiteSettings): MetadataRoute.Sitemap {
  const base = origin(app, settings)
  return LISTED[app].map((path) => ({ url: `${base}${path}` }))
}
