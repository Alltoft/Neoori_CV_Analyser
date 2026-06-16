"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth"
import { Logo } from "@/components/brand/Logo"

const NAV = [
  { label: "vue d'ensemble", href: "/admin" },
  { label: "prompts",        href: "/admin/prompts" },
  { label: "analyses",       href: "/admin/analyses" },
  { label: "utilisateurs",   href: "/admin/utilisateurs" },
  { label: "conseillers",    href: "/admin/conseillers" },
  { label: "coûts API",      href: "/admin/couts" },
]

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { logout } = useAuth()

  return (
    <div className="min-h-screen bg-secondary">
      <div className="bg-background border-b border-border sticky top-0 z-40">
        <div className="max-w-[1280px] mx-auto px-6 h-12 flex items-center gap-4">
          <Link href="/admin" className="text-base transition-opacity hover:opacity-80">
            <Logo />
          </Link>
          <span className="inline-flex items-center rounded-md bg-navy px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.12em] text-white">
            admin
          </span>
          <nav className="flex gap-5 ml-4">
            {NAV.map(({ label, href }) => {
              const active =
                href === "/admin" ? pathname === "/admin" : pathname.startsWith(href)
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "text-xs pb-1 -mb-px transition-colors",
                    active
                      ? "text-navy font-medium border-b-2 border-orange"
                      : "text-muted-foreground hover:text-orange"
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
            className="ml-auto text-xs h-7"
            onClick={async () => { await logout(); router.push("/connexion") }}
          >
            déconnexion
          </Button>
        </div>
      </div>
      <div className="max-w-[1280px] mx-auto px-6 py-5">{children}</div>
    </div>
  )
}
