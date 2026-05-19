"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDown, LogOut, LayoutDashboard, PlusCircle } from "lucide-react"

export function AppBar() {
  const { user, logout } = useAuth()
  const router = useRouter()

  const handleLogout = async () => {
    await logout()
    router.push("/")
  }

  return (
    <header className="w-full border-b border-border bg-background sticky top-0 z-50">
      <div className="max-w-[1100px] mx-auto px-8 h-12 flex items-center justify-between">
        <Link href="/espace" className="font-bold text-base tracking-tight text-foreground">
          neoori
        </Link>

        <div className="flex items-center gap-3">
          <Button render={<Link href="/analyse/nouveau"/>} size="sm" className="bg-primary text-primary-foreground hover:bg-primary/90 h-7 text-xs">
            <PlusCircle className="h-3.5 w-3.5 mr-1.5" />
            Nouvelle analyse
          </Button>

          {user && (
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button variant="ghost" size="sm" className="h-7 text-xs gap-1"/>}>
                {user.email}
                <ChevronDown className="h-3 w-3" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-44">
                <DropdownMenuItem render={<Link href="/espace"/>}>
                  <LayoutDashboard className="h-3.5 w-3.5 mr-2" />
                  Mon espace
                </DropdownMenuItem>
                {user.role === "admin" && (
                  <DropdownMenuItem render={<Link href="/admin"/>}>Administration</DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} className="text-destructive">
                  <LogOut className="h-3.5 w-3.5 mr-2" />
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
