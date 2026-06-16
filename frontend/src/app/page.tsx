import Link from "next/link"
import { Header } from "@/components/layout/Header"
import { Logo, InfinityMark } from "@/components/brand/Logo"
import { Separator } from "@/components/ui/separator"
import { ArrowRight, ShieldCheck } from "lucide-react"

const HOW_IT_WORKS = [
  { n: "01", title: "Votre parcours",    desc: "Téléchargez votre CV ou racontez votre parcours en quelques lignes" },
  { n: "02", title: "Votre projet",      desc: "Téléchargez une offre d'emploi, une fiche de poste ou décrivez-le en quelques mots" },
  { n: "03", title: "Votre analyse",     desc: "Tient compte des ATS et de la lecture humaine" },
  { n: "04", title: "Votre CV optimisé", desc: "Téléchargez une proposition de CV retravaillé" },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      <Header />

      {/* ── Ambient brand gradient ── */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -top-32 -right-24 h-[520px] w-[520px] rounded-full bg-orange/15 blur-[120px]" />
        <div className="absolute top-40 -left-32 h-[420px] w-[420px] rounded-full bg-peach/25 blur-[120px]" />
      </div>

      {/* ── Hero ── */}
      <section className="max-w-[1000px] mx-auto px-8 pt-20 pb-14 relative">
        <InfinityMark
          animate
          className="absolute right-6 top-10 hidden md:block opacity-[0.07] animate-float"
          style={{ height: "240px" }}
        />

        <div className="animate-fade-up">
          <p className="inline-flex items-center gap-2 text-[11px] font-mono tracking-[0.18em] uppercase text-orange">
            <InfinityMark className="h-[0.9em]" /> Analyse de CV · Bêta
          </p>

          <h1 className="text-5xl md:text-6xl font-extrabold leading-[1.03] tracking-tight text-navy mt-5 max-w-[680px]">
            Analysez votre profil,
            <br />
            <span className="text-gradient-brand">construisez votre avenir.</span>
          </h1>

          <p className="mt-6 text-lg text-muted-foreground max-w-[560px] leading-relaxed">
            Choisissez la situation qui vous correspond le mieux pour démarrer
            votre analyse personnalisée.
          </p>
        </div>

        {/* ── Bifurcation A / B ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-12">
          {/* Card A */}
          <Link
            href="/analyse/nouveau"
            className="group relative overflow-hidden rounded-2xl border border-border bg-card p-7 hover-lift"
          >
            <span className="absolute inset-x-0 top-0 h-1.5 bg-brand-gradient" />
            <span className="inline-flex items-center rounded-full bg-orange/10 px-2.5 py-1 text-[10px] font-mono tracking-[0.15em] uppercase text-orange">
              Chemin A
            </span>
            <p className="mt-5 font-display font-bold text-xl text-navy leading-snug pr-6">
              « J&apos;ai déjà travaillé et je veux évoluer ou me reconvertir »
            </p>
            <p className="mt-3 text-sm text-muted-foreground">
              Analyse de parcours + CV retravaillé en 9 sections
            </p>
            <span className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-orange">
              Démarrer
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </span>
          </Link>

          {/* Card B */}
          <Link
            href="/analyse/orientation"
            className="group relative overflow-hidden rounded-2xl border border-border bg-card p-7 hover-lift"
          >
            <span className="absolute inset-x-0 top-0 h-1.5 bg-navy" />
            <span className="inline-flex items-center rounded-full bg-navy/10 px-2.5 py-1 text-[10px] font-mono tracking-[0.15em] uppercase text-navy">
              Chemin B
            </span>
            <p className="mt-5 font-display font-bold text-xl text-navy leading-snug pr-6">
              « Je démarre, je reprends ou je cherche ma direction »
            </p>
            <p className="mt-3 text-sm text-muted-foreground">
              Portrait de potentiel + pistes d&apos;orientation
            </p>
            <span className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-navy">
              Démarrer
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </span>
          </Link>
        </div>

        {/* ── Confidentialité ── */}
        <div className="mt-8 flex items-start gap-3 rounded-xl border border-border bg-secondary/60 px-5 py-4">
          <ShieldCheck className="h-5 w-5 text-orange shrink-0 mt-0.5" />
          <div>
            <p className="text-[10px] font-mono tracking-[0.15em] uppercase text-navy mb-1">
              Confidentialité
            </p>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Vos données sont utilisées uniquement pour produire cette analyse.
              Elles ne sont pas partagées avec des tiers ni utilisées pour entraîner
              des modèles d&apos;IA.
            </p>
          </div>
        </div>

        {/* ── How it works ── */}
        <Separator className="mt-16 mb-12" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {HOW_IT_WORKS.map(({ n, title, desc }) => (
            <div key={n} className="flex flex-col gap-2">
              <span className="text-2xl font-bold text-orange font-mono">{n}</span>
              <p className="font-display font-semibold text-base text-navy">{title}</p>
              <p className="text-sm text-muted-foreground leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Footer band ── */}
      <footer className="mt-12 bg-navy text-white/80">
        <div className="max-w-[1000px] mx-auto px-8 py-10">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
            <div>
              <Logo tone="light" className="text-2xl" />
              <p className="mt-2 text-sm text-white/55">Unlock Your Potential. Shape Your Tomorrow.</p>
            </div>
            <nav className="flex flex-wrap gap-5 text-sm text-white/65">
              <Link href="/mentions-legales" className="hover:text-white transition-colors">Mentions légales</Link>
              <Link href="/cgv" className="hover:text-white transition-colors">CGV</Link>
              <Link href="/confidentialite" className="hover:text-white transition-colors">Confidentialité</Link>
            </nav>
          </div>
          <Separator className="my-6 bg-white/10" />
          <p className="text-xs text-white/45">Bêta · données chiffrées · supprimables à tout moment</p>
        </div>
      </footer>
    </div>
  )
}
