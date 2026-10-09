"use client"

import { useAuth } from "@/lib/auth"
import { homeFor } from "@/lib/home"
import { AppLink, useSite } from "@/lib/site-context"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDown, LogOut, LayoutDashboard, Map as MapIcon, PlusCircle, Shield, UserRound } from "lucide-react"
import { Logo } from "@/components/brand/Logo"

/** Authed-app top bar (espace + analysis flow).
 *
 *  The menu is cut to the role. An admin and an approved conseiller do not use
 *  the candidate surfaces, so they are not offered them; each keeps only the
 *  one entry that is theirs, plus Déconnexion. Because their menu no longer
 *  leads anywhere, the logo carries them home instead of to /espace — without
 *  that, clicking it would drop them into the candidate space with no route
 *  back. A pending or revoked conseiller is role "candidate" and keeps the
 *  full candidate menu, which is correct: that is what they are until approval.
 *
 *  The bar sits on cv, voyage and shared pages alike, so every entry goes
 *  through AppLink: « Nouvelle analyse » or « Mon voyage » may be on the other
 *  host (subdomain split spec, decision 7).
 */
export function AppBar() {
  const { user, logout } = useAuth()
  const { app, go } = useSite()

  const handleLogout = async () => {
    await logout()
    // The root landing (decision 16). The session ended on every host.
    go("/")
  }

  const isCandidate = !user || user.role === "candidate"

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/85 backdrop-blur-md no-print">
      <div className="mx-auto flex h-20 max-w-6xl items-center justify-between px-5 sm:px-8">
        <AppLink
          href={user ? homeFor(user.role, app) : "/"}
          className="text-[24px] transition-opacity hover:opacity-80"
          aria-label="neoori — accueil"
        >
          <Logo />
        </AppLink>

        <div className="flex items-center gap-2">
          {isCandidate && (
            <Button render={<AppLink href="/analyse" />} size="lg">
              <PlusCircle />
              <span className="hidden sm:inline">Nouvelle analyse</span>
              <span className="sm:hidden">Analyse</span>
            </Button>
          )}

          {user && (
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button variant="ghost" size="lg" className="gap-1.5" />}>
                <span className="hidden max-w-[14rem] truncate sm:inline">{user.email}</span>
                <ChevronDown className="size-4" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                {user.role === "candidate" && (
                  <>
                    <DropdownMenuItem render={<AppLink href="/espace" />}>
                      <LayoutDashboard />
                      Mon espace
                    </DropdownMenuItem>
                    <DropdownMenuItem render={<AppLink href="/profil" />}>
                      <UserRound />
                      Mes informations
                    </DropdownMenuItem>
                    <DropdownMenuItem render={<AppLink href="/voyage" />}>
                      <MapIcon />
                      Mon voyage
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                  </>
                )}

                {user.role === "admin" && (
                  <>
                    <DropdownMenuItem render={<AppLink href="/admin" />}>
                      <Shield />
                      Administration
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                  </>
                )}

                <DropdownMenuItem onClick={handleLogout} variant="destructive">
                  <LogOut />
                  Déconnexion
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
    </header>
  )
}
