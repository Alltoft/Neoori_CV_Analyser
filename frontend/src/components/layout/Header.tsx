"use client"

import Link from "next/link"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Logo } from "@/components/brand/Logo"

export function Header() {
  const { user } = useAuth()

  return (
    <header className="w-full border-b border-border bg-background/80 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-[1100px] mx-auto px-8 h-16 flex items-center justify-between">
        <Link href="/" className="text-2xl transition-opacity hover:opacity-80">
          <Logo />
        </Link>

        <nav className="flex items-center gap-6">
          <Link href="/#module"     className="text-sm text-muted-foreground hover:text-orange transition-colors">Le module</Link>
          <Link href="/#conseillers" className="text-sm text-muted-foreground hover:text-orange transition-colors">Conseillers</Link>
          <Link href="/#tarifs"     className="text-sm text-muted-foreground hover:text-orange transition-colors">Tarifs</Link>

          {user ? (
            <Button render={<Link href="/espace"/>} size="sm" variant="outline">Mon espace</Button>
          ) : (
            <Button render={<Link href="/connexion"/>} size="sm" variant="outline">Se connecter</Button>
          )}
        </nav>
      </div>
    </header>
  )
}
