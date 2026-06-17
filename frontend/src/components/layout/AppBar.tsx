"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDown, LogOut, LayoutDashboard, PlusCircle, Shield } from "lucide-react"
import { Logo } from "@/components/brand/Logo"

/** Authed-app top bar (espace + analysis flow). */
export function AppBar() {
  const { user, logout } = useAuth()
  const router = useRouter()

  const handleLogout = async () => {
    await logout()
    router.push("/")
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/85 backdrop-blur-md no-print">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8">
        <Link href="/espace" className="text-[24px] transition-opacity hover:opacity-80" aria-label="neoori — mon espace">
          <Logo />
        </Link>

        <div className="flex items-center gap-2">
          <Button render={<Link href="/analyse/nouveau" />} size="lg">
            <PlusCircle />
            <span className="hidden sm:inline">Nouvelle analyse</span>
            <span className="sm:hidden">Analyse</span>
          </Button>

          {user && (
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button variant="ghost" size="lg" className="gap-1.5" />}>
                <span className="hidden max-w-[14rem] truncate sm:inline">{user.email}</span>
                <ChevronDown className="size-4" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                <DropdownMenuItem render={<Link href="/espace" />}>
                  <LayoutDashboard />
                  Mon espace
                </DropdownMenuItem>
                {user.role === "admin" && (
                  <DropdownMenuItem render={<Link href="/admin" />}>
                    <Shield />
                    Administration
                  </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
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
