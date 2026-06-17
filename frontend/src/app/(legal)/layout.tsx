import type { ReactNode } from "react"
import { SiteNav } from "@/components/layout/SiteNav"
import { SiteFooter } from "@/components/layout/SiteFooter"

export default function LegalLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen overflow-x-clip bg-background">
      <SiteNav />

      <main
        className="mx-auto max-w-[760px] animate-fade-up px-5 py-14 text-[15px] leading-[1.75] text-navy-ink sm:px-8
        [&_h1]:mb-3 [&_h1]:font-display [&_h1]:text-3xl [&_h1]:font-extrabold [&_h1]:tracking-tight [&_h1]:text-navy md:[&_h1]:text-4xl
        [&_h1+p]:mb-10 [&_h1+p]:font-mono [&_h1+p]:text-[11px] [&_h1+p]:uppercase [&_h1+p]:tracking-[0.12em] [&_h1+p]:text-orange-dark
        [&_h2]:mb-3 [&_h2]:mt-12 [&_h2]:border-b [&_h2]:border-border [&_h2]:pb-2 [&_h2]:font-display [&_h2]:text-lg [&_h2]:font-bold [&_h2]:tracking-tight [&_h2]:text-navy
        [&_p]:mb-4 [&_p]:text-muted-foreground
        [&_ul]:mb-4 [&_ul]:list-none [&_ul]:space-y-2 [&_ul]:pl-0
        [&_li]:relative [&_li]:pl-5 [&_li]:text-muted-foreground
        [&_li]:before:absolute [&_li]:before:left-0 [&_li]:before:top-[0.62em] [&_li]:before:h-1.5 [&_li]:before:w-1.5 [&_li]:before:rounded-[2px] [&_li]:before:bg-orange [&_li]:before:content-['']
        [&_strong]:font-semibold [&_strong]:text-navy
        [&_a]:text-orange-dark [&_a]:underline [&_a]:underline-offset-2 hover:[&_a]:no-underline"
      >
        <div className="rounded-2xl bg-card px-7 py-9 ring-1 ring-foreground/10 shadow-soft md:px-10 md:py-11">
          {children}
        </div>
      </main>

      <SiteFooter />
    </div>
  )
}
