import Link from "next/link"
import { SiteNav } from "@/components/layout/SiteNav"
import { SiteFooter } from "@/components/layout/SiteFooter"
import { Logo, InfinityMark } from "@/components/brand/Logo"
import { Photo } from "@/components/media/Photo"
import { Reveal } from "@/components/motion/Reveal"
import { Accordion } from "@/components/ui/accordion"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  ArrowRight, Check, Lock, ShieldCheck, ScanText, Target, PenLine, FileCheck2,
  UserRound, Building2, Users, Server, EyeOff, History, Mail,
} from "lucide-react"

/* ── The deliverable, rendered as proof (mirrors the real report chrome) ── */
const PREVIEW_SECTIONS = [
  { n: "1", title: "Lecture stratégique du parcours" },
  { n: "2", title: "Forces du profil pour la cible" },
  { n: "3", title: "Compétences transférables" },
  { n: "4", title: "Angles morts du CV" },
]
const PREVIEW_TAGS = ["Gestion de projet", "Coordination", "Budget", "Animation d’équipe", "Reporting"]

function Bar({ w }: { w: string }) {
  return <span className="block h-1.5 rounded-full bg-navy/10" style={{ width: w }} />
}

function ReportPreview({ className }: { className?: string }) {
  return (
    <div className={`overflow-hidden rounded-2xl bg-white ring-1 ring-foreground/10 shadow-float ${className ?? ""}`}>
      <div className="h-1.5 bg-orange" />
      <div className="bg-navy px-5 pb-4 pt-4">
        <Logo tone="light" className="text-[13px]" />
        <p className="mt-2.5 font-display text-sm font-bold text-white">Camille D. — Chargée de projet</p>
        <p className="text-[11px] italic text-peach">Cible : Cheffe de projet digital · juin 2026</p>
      </div>
      <div className="space-y-3 p-4">
        {PREVIEW_SECTIONS.map((s) => (
          <div key={s.n}>
            <div className="mb-1.5 flex items-center gap-1.5">
              <span className="grid h-4 w-5 place-items-center rounded-[3px] bg-orange-dark font-mono text-[9px] font-bold text-white">
                §{s.n}
              </span>
              <span className="font-display text-[11px] font-semibold uppercase tracking-wide text-navy">{s.title}</span>
            </div>
            {s.n === "3" ? (
              <div className="flex flex-wrap gap-1">
                {PREVIEW_TAGS.map((t) => (
                  <span key={t} className="rounded-md bg-secondary px-1.5 py-0.5 text-[9px] font-medium text-navy">{t}</span>
                ))}
              </div>
            ) : (
              <div className="space-y-1">
                <Bar w="100%" />
                <Bar w={s.n === "4" ? "62%" : "84%"} />
              </div>
            )}
          </div>
        ))}
        <div className="flex items-center gap-1.5 rounded-md bg-secondary/70 px-2.5 py-2 text-[10px] text-muted-foreground">
          <Lock className="size-3" /> §5 Préconisations terrain · §6 Réécriture · §7 Synthèse — plan complet
        </div>
      </div>
    </div>
  )
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="eyebrow inline-flex items-center gap-2 text-orange-dark">
      <InfinityMark className="text-[1.05em]" /> {children}
    </p>
  )
}

/* ── Section data ── */
const STEPS = [
  { icon: ScanText, n: "01", title: "Le CV", desc: "Import d’un PDF (≤ 10 Mo) ou copier-coller du parcours." },
  { icon: Target, n: "02", title: "La cible", desc: "Le poste ou le projet visé, plus huit informations de contexte." },
  { icon: PenLine, n: "03", title: "L’analyse", desc: "Une lecture structurée par l’IA, fidèle au prompt validé en interne." },
  { icon: FileCheck2, n: "04", title: "Le rapport", desc: "Neuf sections, exportables en PDF, plus une synthèse conseiller." },
]

const SECTIONS_FULL = [
  { n: "1", t: "Lecture stratégique du parcours", free: true },
  { n: "2", t: "Forces du profil pour la cible", free: true },
  { n: "3", t: "Compétences transférables", free: true },
  { n: "4", t: "Angles morts du CV actuel", free: true },
  { n: "5", t: "Préconisations terrain", free: false },
  { n: "6", t: "Exemple de réécriture", free: false },
  { n: "7", t: "Synthèse", free: false },
  { n: "8", t: "Pistes d’évolution", free: false },
  { n: "9", t: "Proposition de CV retravaillé", free: false },
]

const PERSONAS = [
  {
    img: "/img/persona-candidat.jpg",
    icon: UserRound,
    title: "Candidats",
    desc: "Comprendre comment son CV est lu face à un poste précis, et obtenir des pistes concrètes pour le retravailler.",
    cta: { href: "/analyse/nouveau", label: "Démarrer mon analyse" },
  },
  {
    img: "/img/persona-conseiller.jpg",
    icon: Users,
    title: "Conseillers",
    desc: "Une synthèse prête pour l’entretien — cible, points sensibles, préconisations — sans ressaisie ni double travail.",
    cta: { href: "/#rapport", label: "Voir la vue conseiller" },
  },
  {
    img: "/img/persona-organisation.jpg",
    icon: Building2,
    title: "Organisations",
    desc: "Un outil cadré pour vos dispositifs : RGPD, hébergement européen, traçabilité des versions, accès conseiller gratuit.",
    cta: { href: "mailto:nneoori@proton.me?subject=neoori%20—%20demande%20organisation", label: "Nous contacter" },
  },
]

const TRUST = [
  { icon: Server, t: "Hébergement européen", d: "Données traitées et hébergées dans l’Union européenne." },
  { icon: EyeOff, t: "Sans entraînement IA", d: "Vos données ne servent jamais à entraîner des modèles." },
  { icon: History, t: "Traçabilité B2G", d: "Chaque analyse conserve la version exacte du prompt utilisé." },
  { icon: ShieldCheck, t: "RGPD & maîtrise", d: "Consentement explicite, suppression possible à tout moment." },
]

const FAQ = [
  { q: "Combien ça coûte ?", a: "Les quatre premières sections sont gratuites et réellement utiles. L’analyse complète (neuf sections) est à 9 €, en paiement unique — sans abonnement." },
  { q: "C’est gratuit pour les conseillers ?", a: "Oui. Les bénéficiaires accompagnés par Cap Emploi, France Travail ou une Mission Locale accèdent à l’analyse complète gratuitement via un code conseiller." },
  { q: "Que deviennent les données ?", a: "Elles servent uniquement à produire l’analyse demandée. Elles sont hébergées dans l’UE, ne sont pas partagées à des tiers, ne servent pas à entraîner de modèles, et restent supprimables à tout moment." },
  { q: "Combien de temps pour un rapport ?", a: "Quelques minutes. L’analyse se génère en arrière-plan ; le rapport s’affiche dès qu’il est prêt." },
  { q: "Quels formats de CV ?", a: "Un PDF de 10 Mo maximum, ou du texte collé directement. La cible peut aussi être une offre d’emploi importée ou décrite en quelques lignes." },
  { q: "Rapport candidat et synthèse conseiller, quelle différence ?", a: "Une seule analyse produit deux exports : le rapport complet pour le candidat, et une synthèse ciblée (cible, points sensibles, préconisations) pour le conseiller, partageable par lien." },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen overflow-x-clip bg-background">
      <SiteNav />

      {/* ───────────────────── Hero ───────────────────── */}
      <section className="bg-mesh relative">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-16 sm:px-8 lg:grid-cols-[1.05fr_0.95fr] lg:pb-28 lg:pt-20">
          <div className="animate-fade-up">
            <Eyebrow>Pour les acteurs de l’emploi</Eyebrow>
            <h1 className="mt-5 font-display text-[2.6rem] font-extrabold leading-[1.04] tracking-tight text-navy sm:text-6xl">
              Objectivez chaque CV
              <br />
              <span className="text-gradient-brand">au regard de sa cible.</span>
            </h1>
            <p className="mt-6 max-w-[34rem] text-lg leading-relaxed text-muted-foreground">
              neoori transforme un CV et son contexte en une analyse stratégique structurée —
              forces, angles morts et préconisations concrètes. En quelques minutes.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button render={<Link href="/analyse/nouveau" />} size="xl">
                Démarrer une analyse
                <ArrowRight />
              </Button>
              <Button render={<Link href="/#rapport" />} size="xl" variant="outline">
                Voir un rapport type
              </Button>
            </div>
            <ul className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
              {["RGPD", "Hébergé dans l’UE", "Sans entraînement de modèles"].map((t) => (
                <li key={t} className="inline-flex items-center gap-1.5">
                  <Check className="size-4 text-success" /> {t}
                </li>
              ))}
            </ul>
          </div>

          {/* Report-as-proof */}
          <div className="relative">
            <Photo
              src="/img/hero-counselor.jpg"
              alt="Un conseiller accompagne un candidat dans l’analyse de son CV"
              className="aspect-[3/2] w-full shadow-card"
              imgClassName="object-top"
              rounded="rounded-3xl"
              sizes="(max-width: 1024px) 100vw, 460px"
              priority
              overlay
            />
            <ReportPreview className="absolute -bottom-6 -left-4 hidden w-[48%] sm:block" />
            <div className="absolute -right-4 top-6 hidden rounded-xl bg-white px-3.5 py-2.5 shadow-float ring-1 ring-foreground/10 sm:block">
              <p className="font-display text-xl font-bold leading-none text-navy">9</p>
              <p className="eyebrow mt-1 text-muted-foreground">sections</p>
            </div>
          </div>
        </div>
      </section>

      {/* ───────────────────── Credibility band ───────────────────── */}
      <section className="border-y border-border bg-card">
        <div className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
          <p className="text-center text-sm text-muted-foreground">
            Conçu avec les contraintes des acteurs publics de l’emploi
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-x-3 gap-y-2.5">
            {["France Travail", "Cap Emploi", "Missions Locales", "CEP", "Organismes de formation"].map((o) => (
              <span key={o} className="rounded-full bg-secondary px-4 py-1.5 text-sm font-medium text-navy/80">
                {o}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ───────────────────── How it works ───────────────────── */}
      <section id="module" className="mx-auto max-w-6xl px-5 py-20 sm:px-8 lg:py-24">
        <Reveal className="max-w-2xl">
          <Eyebrow>Le module</Eyebrow>
          <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-navy sm:text-4xl">
            Du CV au rapport, en quatre temps.
          </h2>
          <p className="mt-4 text-muted-foreground">
            Un parcours simple, pensé pour tenir dans un rendez-vous d’accompagnement.
          </p>
        </Reveal>

        <div className="relative mt-12 grid gap-6 md:grid-cols-4">
          <div aria-hidden className="absolute left-0 right-0 top-7 hidden h-px bg-gradient-to-r from-transparent via-border to-transparent md:block" />
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delayMs={i * 80} className="relative">
              <div className="flex flex-col">
                <div className="flex size-14 items-center justify-center rounded-2xl bg-card ring-1 ring-foreground/10 shadow-soft">
                  <s.icon className="size-6 text-orange" />
                </div>
                <span className="mt-4 font-mono text-xs tracking-widest text-orange-dark">{s.n}</span>
                <h3 className="mt-1 font-display text-lg font-semibold text-navy">{s.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{s.desc}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ───────────────────── The report ───────────────────── */}
      <section id="rapport" className="bg-mesh border-y border-border">
        <div className="mx-auto grid max-w-6xl items-center gap-14 px-5 py-20 sm:px-8 lg:grid-cols-2 lg:py-24">
          <Reveal className="order-2 lg:order-1">
            <Eyebrow>Le rapport</Eyebrow>
            <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-navy sm:text-4xl">
              Une analyse, deux livrables.
            </h2>
            <p className="mt-4 text-muted-foreground">
              D’une seule analyse, neoori produit un <strong className="font-semibold text-navy">rapport candidat</strong> complet
              et une <strong className="font-semibold text-navy">synthèse conseiller</strong> ciblée — partageable par lien sécurisé,
              avec le badge <span className="rounded bg-navy px-1.5 py-0.5 text-[11px] font-semibold text-white">VERSION CONSEILLER</span>.
            </p>

            <ul className="mt-7 grid grid-cols-1 gap-x-6 gap-y-2.5 sm:grid-cols-2">
              {SECTIONS_FULL.map((s) => (
                <li key={s.n} className="flex items-center gap-2.5 text-sm">
                  {s.free ? (
                    <Check className="size-4 shrink-0 text-success" />
                  ) : (
                    <Lock className="size-3.5 shrink-0 text-orange" />
                  )}
                  <span className={s.free ? "text-navy" : "text-muted-foreground"}>{s.t}</span>
                </li>
              ))}
            </ul>
            <p className="mt-6 text-sm text-muted-foreground">
              <span className="font-medium text-navy">Sections 1 à 4 gratuites.</span> Analyse complète (5 à 9) avec le plan à 9 €.
            </p>
          </Reveal>

          <Reveal delayMs={120} className="order-1 mx-auto w-full max-w-sm lg:order-2">
            <ReportPreview />
          </Reveal>
        </div>
      </section>

      {/* ───────────────────── For whom ───────────────────── */}
      <section id="pour-qui" className="mx-auto max-w-6xl px-5 py-20 sm:px-8 lg:py-24">
        <Reveal className="max-w-2xl">
          <Eyebrow>Pour qui</Eyebrow>
          <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-navy sm:text-4xl">
            Un même objet d’analyse, trois usages.
          </h2>
        </Reveal>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {PERSONAS.map((p, i) => (
            <Reveal key={p.title} delayMs={i * 90}>
              <div className="group flex h-full flex-col overflow-hidden rounded-3xl bg-card ring-1 ring-foreground/10 shadow-soft transition-shadow hover:shadow-card">
                <Photo
                  src={p.img}
                  alt={p.title}
                  className="aspect-[4/5] w-full"
                  imgClassName="scale-[1.1] origin-top"
                  rounded={false}
                  sizes="(max-width: 768px) 100vw, 380px"
                />
                <div className="flex flex-1 flex-col p-6">
                  <div className="flex items-center gap-2.5">
                    <span className="grid size-9 place-items-center rounded-xl bg-peach-soft text-orange-dark">
                      <p.icon className="size-4.5" />
                    </span>
                    <h3 className="font-display text-xl font-semibold text-navy">{p.title}</h3>
                  </div>
                  <p className="mt-3 flex-1 text-sm leading-relaxed text-muted-foreground">{p.desc}</p>
                  <Link
                    href={p.cta.href}
                    className="link-underline mt-5 inline-flex items-center gap-1.5 self-start text-sm font-semibold text-orange-dark"
                  >
                    {p.cta.label}
                    <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                  </Link>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ───────────────────── Pricing ───────────────────── */}
      <section id="tarifs" className="bg-mesh border-y border-border">
        <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8 lg:py-24">
          <Reveal className="mx-auto max-w-2xl text-center">
            <Eyebrow>Tarifs</Eyebrow>
            <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-navy sm:text-4xl">
              Simple, et sans abonnement.
            </h2>
          </Reveal>

          <div className="mt-12 grid items-stretch gap-6 lg:grid-cols-3">
            {/* Free */}
            <Reveal className="flex">
              <div className="flex w-full flex-col rounded-3xl bg-card p-7 ring-1 ring-foreground/10 shadow-soft">
                <h3 className="font-display text-lg font-semibold text-navy">Gratuit</h3>
                <p className="mt-2 font-display text-4xl font-extrabold text-navy">0 €</p>
                <p className="mt-1 text-sm text-muted-foreground">Sections 1 à 4 — une lecture déjà actionnable.</p>
                <Button render={<Link href="/analyse/nouveau" />} variant="outline" size="lg" className="mt-6 w-full">
                  Démarrer
                </Button>
              </div>
            </Reveal>

            {/* Paid — highlighted */}
            <Reveal delayMs={90} className="flex">
              <div className="relative flex w-full flex-col rounded-3xl bg-navy p-7 text-white shadow-float">
                <span className="absolute right-5 top-5">
                  <Badge variant="peach">Le plus choisi</Badge>
                </span>
                <h3 className="font-display text-lg font-semibold text-white">Analyse complète</h3>
                <p className="mt-2 font-display text-4xl font-extrabold text-white">
                  9 € <span className="text-base font-medium text-white/60">/ analyse</span>
                </p>
                <p className="mt-1 text-sm text-white/70">Les neuf sections, dont la réécriture et le CV retravaillé.</p>
                <ul className="mt-5 space-y-2 text-sm text-white/80">
                  {["Préconisations terrain", "Exemple de réécriture", "Proposition de CV retravaillé", "Export PDF"].map((f) => (
                    <li key={f} className="flex items-center gap-2">
                      <Check className="size-4 text-peach" /> {f}
                    </li>
                  ))}
                </ul>
                <Button render={<Link href="/analyse/nouveau" />} size="lg" className="mt-6 w-full bg-white text-orange-dark hover:bg-white/90">
                  Démarrer
                </Button>
              </div>
            </Reveal>

            {/* Counselor code */}
            <Reveal delayMs={180} className="flex">
              <div className="flex w-full flex-col rounded-3xl bg-card p-7 ring-1 ring-foreground/10 shadow-soft">
                <h3 className="font-display text-lg font-semibold text-navy">Code conseiller</h3>
                <p className="mt-2 font-display text-4xl font-extrabold text-navy">Gratuit</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Analyse complète offerte aux bénéficiaires Cap Emploi & France Travail.
                </p>
                <Button render={<Link href="/analyse/nouveau" />} variant="outline" size="lg" className="mt-6 w-full">
                  J’ai un code
                </Button>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ───────────────────── Trust / B2G ───────────────────── */}
      <section className="bg-mesh-navy">
        <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8 lg:py-24">
          <Reveal className="max-w-2xl">
            <p className="eyebrow inline-flex items-center gap-2 text-peach">
              <InfinityMark tone="light" className="text-[1.05em]" /> Confiance & conformité
            </p>
            <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Cadré pour le secteur public.
            </h2>
          </Reveal>
          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {TRUST.map((t, i) => (
              <Reveal key={t.t} delayMs={i * 80}>
                <div className="h-full rounded-2xl bg-white/5 p-6 ring-1 ring-white/10">
                  <span className="grid size-10 place-items-center rounded-xl bg-white/10 text-peach">
                    <t.icon className="size-5" />
                  </span>
                  <h3 className="mt-4 font-display text-base font-semibold text-white">{t.t}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-white/65">{t.d}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ───────────────────── FAQ ───────────────────── */}
      <section className="mx-auto max-w-3xl px-5 py-20 sm:px-8 lg:py-24">
        <Reveal className="text-center">
          <Eyebrow>Questions fréquentes</Eyebrow>
          <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-navy sm:text-4xl">
            Tout ce qu’il faut savoir.
          </h2>
        </Reveal>
        <Reveal className="mt-10">
          <Accordion items={FAQ} />
        </Reveal>
      </section>

      {/* ───────────────────── Final CTA ───────────────────── */}
      <section className="bg-mesh border-t border-border">
        <div className="mx-auto max-w-4xl px-5 py-20 text-center sm:px-8">
          <Reveal>
            <h2 className="font-display text-3xl font-extrabold tracking-tight text-navy sm:text-4xl">
              Prêt à objectiver vos CV ?
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
              Lancez une première analyse gratuite, ou échangeons sur un déploiement pour votre structure.
            </p>
            <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
              <Button render={<Link href="/analyse/nouveau" />} size="xl">
                Démarrer une analyse
                <ArrowRight />
              </Button>
              <Button
                render={<a href="mailto:nneoori@proton.me?subject=neoori%20—%20demande%20organisation" />}
                size="xl"
                variant="outline"
              >
                <Mail />
                Nous contacter
              </Button>
            </div>
          </Reveal>
        </div>
      </section>

      <SiteFooter />
    </div>
  )
}
