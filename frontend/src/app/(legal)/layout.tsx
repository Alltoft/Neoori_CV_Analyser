import Link from "next/link"
import type { ReactNode } from "react"
import { Logo } from "@/components/brand/Logo"
import { Separator } from "@/components/ui/separator"

export default function LegalLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      {/* ── Ambient brand gradient ── */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -top-40 -right-32 h-[440px] w-[440px] rounded-full bg-orange/10 blur-[120px]" />
        <div className="absolute top-32 -left-32 h-[360px] w-[360px] rounded-full bg-peach/20 blur-[120px]" />
      </div>

      <header className="w-full border-b border-border bg-background/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-[820px] mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/" className="text-lg transition-opacity hover:opacity-80">
            <Logo />
          </Link>
          <nav className="flex gap-5 text-xs font-mono tracking-[0.04em] text-muted-foreground">
            <Link href="/mentions-legales" className="transition-colors hover:text-orange">Mentions légales</Link>
            <Link href="/cgv" className="transition-colors hover:text-orange">CGV</Link>
            <Link href="/confidentialite" className="transition-colors hover:text-orange">Confidentialité</Link>
          </nav>
        </div>
      </header>

      <main
        className="max-w-[760px] mx-auto px-6 py-14 text-[15px] leading-[1.75] text-navy-ink animate-fade-up
        [&_h1]:font-display [&_h1]:text-3xl md:[&_h1]:text-4xl [&_h1]:font-extrabold [&_h1]:tracking-tight [&_h1]:text-navy [&_h1]:mb-3
        [&_h1+p]:font-mono [&_h1+p]:text-[11px] [&_h1+p]:tracking-[0.12em] [&_h1+p]:uppercase [&_h1+p]:text-orange [&_h1+p]:mb-10
        [&_h2]:font-display [&_h2]:text-lg [&_h2]:font-bold [&_h2]:tracking-tight [&_h2]:text-navy [&_h2]:mt-12 [&_h2]:mb-3 [&_h2]:pb-2 [&_h2]:border-b [&_h2]:border-border
        [&_p]:mb-4 [&_p]:text-muted-foreground
        [&_ul]:list-none [&_ul]:pl-0 [&_ul]:mb-4 [&_ul]:space-y-2
        [&_li]:relative [&_li]:pl-5 [&_li]:text-muted-foreground
        [&_li]:before:content-[''] [&_li]:before:absolute [&_li]:before:left-0 [&_li]:before:top-[0.62em] [&_li]:before:h-1.5 [&_li]:before:w-1.5 [&_li]:before:rounded-[2px] [&_li]:before:bg-orange
        [&_strong]:font-semibold [&_strong]:text-navy
        [&_a]:text-orange [&_a]:underline [&_a]:underline-offset-2 hover:[&_a]:text-orange-dark"
      >
        <div className="rounded-2xl border border-border bg-card px-7 py-9 md:px-10 md:py-11 shadow-sm">
          {children}
        </div>
      </main>

      <footer className="mt-8 bg-navy text-white/80">
        <div className="max-w-[760px] mx-auto px-6 py-9">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <Logo tone="light" className="text-xl" />
            <nav className="flex flex-wrap gap-5 text-xs font-mono tracking-[0.04em] text-white/65">
              <Link href="/mentions-legales" className="transition-colors hover:text-white">Mentions légales</Link>
              <Link href="/cgv" className="transition-colors hover:text-white">CGV</Link>
              <Link href="/confidentialite" className="transition-colors hover:text-white">Confidentialité</Link>
            </nav>
          </div>
          <Separator className="my-5 bg-white/10" />
          <p className="text-xs font-mono tracking-[0.04em] text-white/45">neoori · bêta</p>
        </div>
      </footer>
    </div>
  )
}
