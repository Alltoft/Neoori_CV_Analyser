"use client"

import { useEffect } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth"
import { Logo } from "@/components/brand/Logo"
import { LogOut } from "lucide-react"

const NAV = [
  { label: "Vue d’ensemble", href: "/admin" },
  { label: "Prompts",        href: "/admin/prompts" },
  { label: "Analyses",       href: "/admin/analyses" },
  { label: "Utilisateurs",   href: "/admin/utilisateurs" },
  { label: "Conseillers",    href: "/admin/conseillers" },
  { label: "Coûts API",      href: "/admin/couts" },
]

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { user, loading, logout } = useAuth()

  const handleLogout = async () => {
    await logout()
    router.push("/")
  }

  // The proxy checks that a cookie exists, not what it says. Without this a
  // signed-in candidate typing /admin renders the entire admin shell and only
  // meets 403s in the data — the pattern copied from voyage/c/[token]:91-92,
  // which refuses before it fetches.
  useEffect(() => {
    if (!loading && !user) router.replace("/connexion?redirect=/admin")
  }, [loading, user, router])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-secondary">
        <Skeleton className="h-8 w-48" />
      </div>
    )
  }

  // Signed out: the redirect above is already navigating this person away.
  // Render nothing rather than the admin-refusal copy below — that copy
  // ("réservée à l'administration" + "Retour à mon espace") is wrong for
  // someone who was never signed in, and would otherwise flash for one
  // frame while `user`/`loading` update together (lib/auth.tsx:35-46).
  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-secondary">
        <Skeleton className="h-8 w-48" />
      </div>
    )
  }

  if (user.role !== "admin") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-secondary px-5">
        <div className="max-w-md rounded-2xl bg-card p-6 text-center ring-1 ring-foreground/10">
          <h1 className="font-display text-lg font-semibold text-navy">Accès réservé</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Cette page est réservée à l&apos;administration.
          </p>
          <Button render={<Link href="/espace" />} size="lg" className="mt-4">
            Retour à mon espace
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-secondary">
      <header className="sticky top-0 z-50 w-full border-b border-border bg-background/85 backdrop-blur-md">
        <div className="mx-auto flex h-20 max-w-7xl items-center gap-3 px-5 sm:gap-5 sm:px-8">
          <Link
            href="/admin"
            className="text-[22px] transition-opacity hover:opacity-80"
            aria-label="neoori — administration"
          >
            <Logo />
          </Link>
          <Badge variant="navy">Admin</Badge>

          <nav className="-mx-2 ml-1 flex flex-1 items-center gap-4 overflow-x-auto px-2 sm:gap-6">
            {NAV.map(({ label, href }) => {
              const active =
                href === "/admin" ? pathname === "/admin" : pathname.startsWith(href)
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "shrink-0 whitespace-nowrap border-b-2 pb-1 text-sm transition-colors",
                    active
                      ? "border-orange font-medium text-navy"
                      : "border-transparent text-muted-foreground hover:text-orange"
                  )}
                >
                  {label}
                </Link>
              )
            })}
          </nav>

          <Button
            variant="ghost"
            size="sm"
            className="ml-auto shrink-0"
            onClick={handleLogout}
          >
            <LogOut className="size-4" />
            <span className="hidden sm:inline">Déconnexion</span>
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-6 sm:px-8 sm:py-8">{children}</main>
    </div>
  )
}
