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
