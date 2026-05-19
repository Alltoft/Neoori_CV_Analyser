"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth"

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
        <div className="max-w-[1280px] mx-auto px-6 h-10 flex items-center gap-4">
          <span className="font-bold text-sm">neoori</span>
          <Badge variant="outline" className="text-[10px]">admin</Badge>
          <nav className="flex gap-5 ml-4">
            {NAV.map(({ label, href }) => {
              const active =
                href === "/admin" ? pathname === "/admin" : pathname.startsWith(href)
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "text-xs pb-0.5 transition-colors",
                    active
                      ? "text-foreground border-b border-primary"
                      : "text-muted-foreground hover:text-foreground"
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
