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
