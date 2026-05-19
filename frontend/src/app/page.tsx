import Link from "next/link"
import { Header } from "@/components/layout/Header"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"

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
      <section className="max-w-[1100px] mx-auto px-8 pt-20 pb-24">
        <div className="grid grid-cols-[1.1fr_0.9fr] gap-12 items-start">
          <div>
            <Badge variant="outline" className="mb-4 text-xs font-mono tracking-wider uppercase">
              Bêta · Analyse CV
            </Badge>
            <h1 className="text-5xl font-bold leading-[1.05] tracking-tight text-foreground mt-2">
              Un CV lu autrement.
              <br />
              <span className="text-primary">Pour les parcours</span>
              <br />
              qu'on ne sait pas lire.
            </h1>
            <p className="mt-6 text-base text-muted-foreground max-w-[440px] leading-relaxed">
              neoori produit une analyse stratégique de votre CV à destination de
              trois lecteurs simultanés : vous, votre conseiller, le RH.
            </p>
            <div className="flex gap-3 mt-8">
              <Button render={<Link href="/analyse/nouveau"/>} size="lg" className="bg-primary hover:bg-primary/90 text-primary-foreground">analyser mon CV →</Button>
              <Button render={<Link href="/espace"/>} size="lg" variant="outline">voir un exemple</Button>
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              prend ~2 min · sans compte pour la version d'essai
            </p>
          </div>

          {/* Stacked report illustration */}
          <div className="relative h-[340px]">
            <div
              className="absolute right-8 top-8 w-[240px] bg-background border border-border rounded-lg p-4 shadow-md"
              style={{ transform: "rotate(2deg)" }}
            >
              <Badge className="bg-primary text-primary-foreground text-[10px]">livrable candidat</Badge>
              <p className="mt-3 font-semibold text-sm">Analyse de CV</p>
              <p className="text-xs text-muted-foreground">Marion C. · Référente handicap</p>
              <div className="mt-3 space-y-1.5">
                {["§ 1 · Lecture stratégique","§ 2 · Forces du profil","§ 3 · Compétences","§ 4 · Angles morts"].map(s => (
                  <div key={s} className="h-2.5 bg-muted rounded-sm" style={{ width: s.includes("morts") ? "70%" : "90%" }} />
                ))}
              </div>
            </div>
            <div
              className="absolute right-0 top-0 w-[240px] bg-secondary border border-border rounded-lg p-4 shadow-sm"
              style={{ transform: "rotate(-3deg)" }}
            >
              <Badge variant="outline" className="text-[10px]">version conseiller</Badge>
              <p className="mt-3 font-semibold text-sm">Synthèse</p>
              <div className="mt-2 space-y-1.5">
                {[1,2,3,4,5].map(i => (
                  <div key={i} className="h-2 bg-border rounded-sm" style={{ width: `${[100,90,70,100,50][i-1]}%` }} />
                ))}
              </div>
              <p className="mt-3 text-[10px] font-mono text-muted-foreground">§ 1 · 4 · 5</p>
            </div>
            <p className="absolute right-[-8px] bottom-6 text-[11px] text-muted-foreground italic bg-secondary/80 px-2 py-1 rounded border border-border rotate-1">
              même analyse, deux exports →
            </p>
          </div>
        </div>

        {/* ── How it works ── */}
        <Separator className="mt-16 mb-12" />
        <div className="grid grid-cols-3 gap-8">
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
        <div className="max-w-[1100px] mx-auto px-8 flex items-center justify-between">
          <span className="font-bold text-sm">neoori</span>
          <span className="text-xs text-muted-foreground">Bêta · données chiffrées · supprimables à tout moment</span>
        </div>
      </footer>
    </div>
  )
}
