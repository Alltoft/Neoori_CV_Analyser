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
