"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth"
import { homeFor } from "@/lib/home"
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
 */
export function AppBar() {
  const { user, logout } = useAuth()
  const router = useRouter()

  const handleLogout = async () => {
    await logout()
    router.push("/")
  }

  const isCandidate = !user || user.role === "candidate"

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/85 backdrop-blur-md no-print">
      <div className="mx-auto flex h-20 max-w-6xl items-center justify-between px-5 sm:px-8">
        <Link
          href={homeFor(user?.role)}
          className="text-[24px] transition-opacity hover:opacity-80"
          aria-label="neoori — accueil"
        >
          <Logo />
        </Link>

        <div className="flex items-center gap-2">
          {isCandidate && (
            <Button render={<Link href="/analyse" />} size="lg">
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
                    <DropdownMenuItem render={<Link href="/espace" />}>
                      <LayoutDashboard />
                      Mon espace
                    </DropdownMenuItem>
                    <DropdownMenuItem render={<Link href="/profil" />}>
                      <UserRound />
                      Mes informations
                    </DropdownMenuItem>
                    <DropdownMenuItem render={<Link href="/voyage" />}>
                      <MapIcon />
                      Mon voyage
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                  </>
                )}

                {user.role === "admin" && (
                  <>
                    <DropdownMenuItem render={<Link href="/admin" />}>
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
