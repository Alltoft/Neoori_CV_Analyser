import Link from "next/link"
import { Header } from "@/components/layout/Header"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { ArrowRight } from "lucide-react"

const HOW_IT_WORKS = [
  { n: "01", title: "Vous racontez votre cible", desc: "CV + offre ou fiche métier + 6 champs de contexte" },
  { n: "02", title: "neoori traduit",            desc: "le langage de votre parcours vers celui du recruteur visé" },
  { n: "03", title: "3 lectures, 1 document",    desc: "pour vous · votre conseiller · un RH ou un jury" },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <Header />

      {/* ── Hero ── */}
      <section className="max-w-[920px] mx-auto px-8 pt-20 pb-16">
        <Badge variant="outline" className="mb-4 text-xs font-mono tracking-wider uppercase">
          Bêta · Analyse
        </Badge>
        <h1 className="text-5xl font-bold leading-[1.05] tracking-tight text-foreground mt-2">
          Analysez votre profil,
          <br />
          <span className="text-primary">construisez votre avenir.</span>
        </h1>
        <p className="mt-6 text-base text-muted-foreground max-w-[560px] leading-relaxed">
          Choisissez la situation qui vous correspond le mieux pour démarrer
          votre analyse personnalisée.
        </p>

        {/* ── Bifurcation A / B ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-10">
          {/* Card A — active */}
          <Link
            href="/analyse/nouveau"
            className="group relative overflow-hidden rounded-lg border-2 border-primary/40 bg-secondary p-6 transition-all hover:-translate-y-1 hover:shadow-md hover:border-primary"
          >
            <span className="absolute inset-x-0 top-0 h-1 bg-primary" />
            <Badge className="bg-primary/10 text-primary border-0 font-mono text-[10px] tracking-widest uppercase">
              Chemin A
            </Badge>
            <p className="mt-4 font-semibold text-lg text-foreground leading-snug">
              « J&apos;ai déjà travaillé et je veux évoluer ou me reconvertir »
            </p>
            <p className="mt-3 text-sm text-muted-foreground italic">
              Analyse de parcours + CV retravaillé en 9 sections
            </p>
            <ArrowRight className="absolute bottom-5 right-5 h-5 w-5 text-primary transition-transform group-hover:translate-x-1" />
          </Link>

          {/* Card B — active */}
          <Link
            href="/analyse/orientation"
            className="group relative overflow-hidden rounded-lg border-2 border-primary/40 bg-secondary p-6 transition-all hover:-translate-y-1 hover:shadow-md hover:border-primary"
          >
            <span className="absolute inset-x-0 top-0 h-1 bg-primary" />
            <Badge className="bg-primary/10 text-primary border-0 font-mono text-[10px] tracking-widest uppercase">
              Chemin B
            </Badge>
            <p className="mt-4 font-semibold text-lg text-foreground leading-snug">
              « Je démarre, je reprends ou je cherche ma direction »
            </p>
            <p className="mt-3 text-sm text-muted-foreground italic">
              Portrait de potentiel + pistes d&apos;orientation
            </p>
            <ArrowRight className="absolute bottom-5 right-5 h-5 w-5 text-primary transition-transform group-hover:translate-x-1" />
          </Link>
        </div>

        {/* ── Confidentialité ── */}
        <div className="mt-8 flex rounded-md overflow-hidden border border-border">
          <div className="w-1 bg-primary shrink-0" />
          <div className="bg-secondary/60 px-4 py-3 flex-1">
            <p className="text-[10px] font-bold tracking-widest uppercase text-foreground mb-1">
              Confidentialité
            </p>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Vos données sont utilisées uniquement pour produire cette analyse.
              Elles ne sont pas partagées avec des tiers ni utilisées pour entraîner
              des modèles d&apos;IA.
            </p>
          </div>
        </div>

        {/* ── How it works ── */}
        <Separator className="mt-16 mb-12" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {HOW_IT_WORKS.map(({ n, title, desc }) => (
            <div key={n} className="flex flex-col gap-1.5">
              <span className="text-2xl font-bold text-primary font-mono">{n}</span>
              <p className="font-semibold text-sm text-foreground">{title}</p>
              <p className="text-sm text-muted-foreground leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Footer band ── */}
      <footer className="border-t border-border bg-secondary py-6">
        <div className="max-w-[920px] mx-auto px-8 flex items-center justify-between">
          <span className="font-bold text-sm">neoori</span>
          <span className="text-xs text-muted-foreground">Bêta · données chiffrées · supprimables à tout moment</span>
        </div>
      </footer>
    </div>
  )
}
