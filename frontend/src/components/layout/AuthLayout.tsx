import Link from "next/link"
import { Photo } from "@/components/media/Photo"
import { Logo, InfinityMark } from "@/components/brand/Logo"
import { Check } from "lucide-react"

const POINTS = [
  "4 sections gratuites, sans carte bancaire",
  "Export PDF et synthèse conseiller",
  "Données hébergées dans l’Union européenne",
]

/** Split-screen auth chrome: brand/image panel + centered form area. */
export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand panel (lg+) */}
      <div className="relative hidden overflow-hidden lg:block">
        <div className="absolute inset-0">
          <Photo src="/img/auth-side.jpg" alt="" rounded={false} overlay className="h-full w-full" sizes="50vw" priority />
        </div>
        <div className="absolute inset-0 bg-navy/45" />
        <div className="relative flex h-full flex-col justify-between p-10 text-white">
          <Link href="/" aria-label="neoori — accueil">
            <Logo tone="light" className="text-2xl" />
          </Link>
          <div>
            <p className="eyebrow inline-flex items-center gap-2 text-peach">
              <InfinityMark tone="light" className="text-[1.05em]" /> Analyse stratégique de CV
            </p>
            <p className="mt-4 max-w-md font-display text-3xl font-bold leading-tight">
              Une lecture claire de chaque CV, au regard de sa cible.
            </p>
            <ul className="mt-7 space-y-3 text-sm text-white/85">
              {POINTS.map((p) => (
                <li key={p} className="flex items-center gap-2.5">
                  <Check className="size-4 shrink-0 text-peach" /> {p}
                </li>
              ))}
            </ul>
          </div>
          <p className="text-xs text-white/55">© neoori · Bêta</p>
        </div>
      </div>

      {/* Form area */}
      <div className="flex items-center justify-center bg-background px-5 py-12">
        <div className="w-full max-w-sm">
          <Link href="/" className="mb-8 flex justify-center text-2xl lg:hidden" aria-label="neoori — accueil">
            <Logo />
          </Link>
          {children}
        </div>
      </div>
    </div>
  )
}
