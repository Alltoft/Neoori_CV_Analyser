"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { createContext, useContext, useMemo, type ComponentProps, type ReactNode } from "react"
import { landingHref, resolveHref, type AppName, type Site } from "./site"

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
  /** "/" when `app` is this host's, that app's absolute "/" otherwise
   *  (landings spec, decision 12). */
  landing: (app: AppName) => string
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
    landing: (target) => landingHref(target, site),
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
