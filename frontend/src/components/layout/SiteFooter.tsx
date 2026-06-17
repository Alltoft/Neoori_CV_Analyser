import Link from "next/link"
import { Logo, InfinityMark } from "@/components/brand/Logo"
import { ShieldCheck } from "lucide-react"

const COLS: { title: string; links: { href: string; label: string }[] }[] = [
  {
    title: "Produit",
    links: [
      { href: "/#module", label: "Le module" },
      { href: "/#rapport", label: "Le rapport" },
      { href: "/#tarifs", label: "Tarifs" },
      { href: "/analyse/nouveau", label: "Démarrer une analyse" },
    ],
  },
  {
    title: "Pour qui",
    links: [
      { href: "/#pour-qui", label: "Candidats" },
      { href: "/#pour-qui", label: "Conseillers" },
      { href: "/#pour-qui", label: "Organisations" },
    ],
  },
  {
    title: "Légal",
    links: [
      { href: "/mentions-legales", label: "Mentions légales" },
      { href: "/cgv", label: "CGV" },
      { href: "/confidentialite", label: "Confidentialité" },
    ],
  },
]

export function SiteFooter() {
  const year = new Date().getFullYear()
  return (
    <footer className="relative overflow-hidden bg-navy text-white/80">
      <InfinityMark
        tone="light"
        aria-hidden
        className="pointer-events-none absolute -right-6 -top-10 text-[220px] opacity-[0.06]"
      />
      <div className="relative mx-auto max-w-6xl px-5 py-14 sm:px-8">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-[1.4fr_repeat(3,1fr)]">
          <div className="col-span-2 md:col-span-1">
            <Logo tone="light" className="text-2xl" />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-white/60">
              Une lecture stratégique du CV, au service de votre projet professionnel.
            </p>
            <p className="eyebrow mt-5 inline-flex items-center gap-2 text-peach">
              <span className="inline-block size-1.5 rounded-full bg-orange" />
              Bêta
            </p>
          </div>

          {COLS.map((col) => (
            <nav key={col.title} aria-label={col.title}>
              <p className="eyebrow text-white/45">{col.title}</p>
              <ul className="mt-4 space-y-2.5">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <Link href={l.href} className="text-sm text-white/70 transition-colors hover:text-white">
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-12 flex flex-col gap-4 border-t border-white/10 pt-6 text-xs text-white/50 sm:flex-row sm:items-center sm:justify-between">
          <p>© {year} neoori · Bêta</p>
          <p className="inline-flex items-center gap-2">
            <ShieldCheck className="size-3.5 text-success" />
            Données chiffrées, hébergées dans l’Union européenne, supprimables à tout moment.
          </p>
        </div>
      </div>
    </footer>
  )
}
