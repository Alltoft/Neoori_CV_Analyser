import Link from "next/link"
import type { ReactNode } from "react"

export default function LegalLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <header className="w-full border-b border-border bg-background sticky top-0 z-50">
        <div className="max-w-[760px] mx-auto px-6 h-12 flex items-center justify-between">
          <Link href="/" className="font-bold text-base tracking-tight">neoori</Link>
          <nav className="flex gap-4 text-xs text-muted-foreground">
            <Link href="/mentions-legales" className="hover:text-foreground">Mentions légales</Link>
            <Link href="/cgv" className="hover:text-foreground">CGV</Link>
            <Link href="/confidentialite" className="hover:text-foreground">Confidentialité</Link>
          </nav>
        </div>
      </header>
      <main className="max-w-[760px] mx-auto px-6 py-10 text-sm leading-relaxed
        [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:mb-6
        [&_h2]:text-base [&_h2]:font-semibold [&_h2]:mt-8 [&_h2]:mb-2
        [&_p]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-3 [&_li]:mb-1
        [&_strong]:font-semibold">
        {children}
      </main>
      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        neoori · bêta
      </footer>
    </div>
  )
}
