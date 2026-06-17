"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
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
  const { logout } = useAuth()

  const handleLogout = async () => {
    await logout()
    router.push("/")
  }

  return (
    <div className="min-h-screen bg-secondary">
      <header className="sticky top-0 z-50 w-full border-b border-border bg-background/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-5 sm:gap-5 sm:px-8">
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
