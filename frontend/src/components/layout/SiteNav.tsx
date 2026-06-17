"use client"

import Link from "next/link"
import { useState } from "react"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Logo } from "@/components/brand/Logo"
import { Menu, X, ArrowRight } from "lucide-react"

const LINKS = [
  { href: "/#module", label: "Le module" },
  { href: "/#rapport", label: "Le rapport" },
  { href: "/#pour-qui", label: "Pour qui" },
  { href: "/#tarifs", label: "Tarifs" },
]

/** Public marketing nav: real anchors, auth-aware CTA, responsive mobile panel. */
export function SiteNav() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/70 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8">
        <Link href="/" className="text-[26px] transition-opacity hover:opacity-80" aria-label="neoori — accueil">
          <Logo priority />
        </Link>

        <nav className="hidden items-center gap-8 md:flex">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="link-underline text-sm font-medium text-muted-foreground transition-colors hover:text-navy"
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <Button render={<Link href={user ? "/espace" : "/connexion"} />} size="lg" variant="ghost">
            {user ? "Mon espace" : "Se connecter"}
          </Button>
          <Button render={<Link href="/analyse/nouveau" />} size="lg">
            Démarrer
            <ArrowRight />
          </Button>
        </div>

        <button
          onClick={() => setOpen((o) => !o)}
          className="inline-grid size-9 place-items-center rounded-lg text-navy hover:bg-muted md:hidden"
          aria-label={open ? "Fermer le menu" : "Ouvrir le menu"}
          aria-expanded={open}
        >
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </div>

      {open && (
        <div className="animate-fade-in border-t border-border bg-background px-5 pb-5 pt-1 md:hidden">
          <nav className="flex flex-col">
            {LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="border-b border-border/60 py-3 text-[15px] font-medium text-navy"
              >
                {l.label}
              </Link>
            ))}
          </nav>
          <div className="mt-4 flex flex-col gap-2">
            <Button render={<Link href={user ? "/espace" : "/connexion"} />} variant="outline" size="lg" onClick={() => setOpen(false)}>
              {user ? "Mon espace" : "Se connecter"}
            </Button>
            <Button render={<Link href="/analyse/nouveau" />} size="lg" onClick={() => setOpen(false)}>
              Démarrer une analyse
              <ArrowRight />
            </Button>
          </div>
        </div>
      )}
    </header>
  )
}
