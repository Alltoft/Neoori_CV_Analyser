"use client"

import Link from "next/link"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"

export function Header() {
  const { user } = useAuth()

  return (
    <header className="w-full border-b border-border bg-background/95 backdrop-blur sticky top-0 z-50">
      <div className="max-w-[1100px] mx-auto px-8 h-14 flex items-center justify-between">
        <Link href="/" className="font-bold text-xl tracking-tight text-foreground">
          neoori
        </Link>

        <nav className="flex items-center gap-6">
          <Link href="/#module"     className="text-sm text-muted-foreground hover:text-foreground transition-colors">Le module</Link>
          <Link href="/#conseillers" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Conseillers</Link>
          <Link href="/#tarifs"     className="text-sm text-muted-foreground hover:text-foreground transition-colors">Tarifs</Link>

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
