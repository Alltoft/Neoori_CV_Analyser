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
  Compass, Sprout,
} from "lucide-react"

/* ── The deliverable, rendered as proof (mirrors the real report chrome) ── */
const PREVIEW_SECTIONS = [
  { n: "1", title: "Lecture stratégique du parcours" },
  { n: "2", title: "Forces du profil pour la cible" },
  { n: "3", title: "Compétences transférables" },
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
                <Bar w={s.n === "2" ? "62%" : "84%"} />
              </div>
            )}
          </div>
        ))}
        <div className="flex items-center gap-1.5 rounded-md bg-secondary/70 px-2.5 py-2 text-[10px] text-muted-foreground">
          <Lock className="size-3" /> §4 Ce qui reste à renforcer · §5 Préconisations terrain · §6 Réécriture — plan complet
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
  { icon: ScanText, n: "01", title: "Votre CV", desc: "Importez votre PDF ou collez votre texte. En quelques secondes, c’est prêt." },
  { icon: Target, n: "02", title: "Ce que vous recherchez", desc: "Dites-nous ce que vous recherchez. Et si vous avez des contraintes ou des besoins particuliers — mobilité, aménagement, situation personnelle — vous pouvez les renseigner ici. L’analyse en tient compte. Elle est faite pour vous, pas pour un profil standard." },
  { icon: PenLine, n: "03", title: "La lecture", desc: "neoori lit votre CV du point de vue des recruteurs et en tenant compte des ATS." },
  { icon: FileCheck2, n: "04", title: "Votre rapport", desc: "Vous repartez avec des réponses claires. Ce qui fonctionne. Ce qui coince. Et comment corriger, concrètement." },
]

const SECTIONS_FULL = [
  { n: "1", t: "Ce que le recruteur retient en premier", free: true },
  { n: "2", t: "Vos forces réelles pour ce poste précis", free: true },
  { n: "3", t: "Vos compétences transférables — celles que vous n’avez peut-être pas pensé à mettre en avant", free: true },
  { n: "4", t: "Ce qui reste à renforcer — et comment", free: false },
  { n: "5", t: "Des préconisations concrètes, issues du terrain", free: false },
  { n: "6", t: "Un exemple de reformulation de votre expérience", free: false },
  { n: "7", t: "Une synthèse de votre profil", free: false },
  { n: "8", t: "Des pistes d’évolution", free: false },
  { n: "9", t: "Une proposition de CV retravaillé, prête à envoyer", free: false },
]

const PARCOURS = [
  {
    href: "/analyse/nouveau",
    n: "1",
    icon: Target,
    title: "J'ai une cible",
    lead: "Vous visez un poste ou un secteur précis, peut-être avec une offre en main.",
    detail: "Votre CV est comparé à cette cible, point par point.",
    needs: "CV requis",
    // Charter accents, one per scenario — the colour is the wayfinding, so it
    // has to survive into the form pages too, not just live on this card.
    ring: "ring-orange/35 hover:ring-orange",
    bar: "bg-orange",
    chip: "bg-peach-soft text-orange-dark",
  },
  {
    href: "/analyse/direction",
    n: "2",
    icon: Compass,
    title: "Je cherche ma direction",
    lead: "Vous avez un parcours, mais pas encore de cible.",
    detail: "On part de ce que vous avez déjà construit pour identifier des pistes.",
    needs: "CV requis",
    ring: "ring-navy/25 hover:ring-navy",
    bar: "bg-navy",
    chip: "bg-secondary text-navy",
  },
  {
    href: "/analyse/depart",
    n: "3",
    icon: Sprout,
    title: "Je pars de zéro",
    lead: "Peu ou pas d'expérience formelle, ou un retour après une longue pause.",
    detail: "Sport, bénévolat, aidance, projets personnels : tout compte.",
    needs: "Aucun CV nécessaire",
    ring: "ring-teal/35 hover:ring-teal",
    bar: "bg-teal",
    chip: "bg-teal/10 text-teal",
  },
]

const PERSONAS = [
  {
    img: "/img/persona-candidat.jpg",
    icon: UserRound,
    title: "Candidats",
    desc: "Vous postulez avec un parcours qui vous appartient — y compris ses contraintes, ses spécificités, ses besoins. neoori ne les efface pas. Il les intègre. Pour vous donner des recommandations qui tiennent vraiment la route, dans votre vie réelle.",
    cta: { href: "/analyse", label: "Lancer mon analyse" },
  },
  {
    img: "/img/persona-conseiller.jpg",
    icon: Users,
    title: "Conseillers",
    desc: "Vos bénéficiaires arrivent en entretien avec un rapport déjà structuré : leurs forces, leurs fragilités, vos préconisations. Vous travaillez ensemble, à partir d’une même base. Vous gagnez du temps. Eux, de la confiance.",
    cta: { href: "/#rapport", label: "Voir la vue conseiller" },
  },
  {
    img: "/img/persona-organisation.jpg",
    icon: Building2,
    title: "Organisations",
    desc: "Un outil cadré pour vos dispositifs — RGPD, hébergement européen, traçabilité des analyses, accès conseiller gratuit.",
    cta: { href: "mailto:nneoori@proton.me?subject=neoori%20—%20demande%20organisation", label: "Nous contacter" },
  },
]

const TRUST = [
  { icon: Server, t: "Hébergement européen", d: "Vos données sont traitées et stockées dans l’Union européenne." },
  { icon: EyeOff, t: "Sans entraînement IA", d: "Votre CV ne sert jamais à former un modèle." },
  { icon: History, t: "Vos analyses, toujours accessibles", d: "Chaque analyse est conservée et retrouvable. Vous pouvez y revenir, la partager, l’utiliser pour d’autres candidatures." },
  { icon: ShieldCheck, t: "RGPD & maîtrise", d: "Consentement explicite, suppression possible à tout moment. Vous gardez la main." },
]

const FAQ = [
  { q: "Combien ça coûte ?", a: "Les sections 1 à 3 et le verdict de diagnostic sont gratuits, sans carte bancaire. Le rapport complet — neuf sections, dont la proposition de CV retravaillé — est à 9 €. Si votre conseiller vous a remis un code, l’accès complet est offert." },
  { q: "Les conseillers peuvent-ils utiliser neoori ?", a: "Vous accompagnez des candidats et vous souhaitez intégrer neoori à vos entretiens ? Contactez-nous. Nous offrons l’accès complet aux 5 premiers candidats, pour que vous puissiez tester l’outil dans vos conditions réelles." },
  { q: "Que deviennent mes données ?", a: "Elles sont hébergées dans l’Union européenne, chiffrées, et ne servent jamais à entraîner des modèles d’IA. Vous pouvez demander leur suppression à tout moment." },
  { q: "Combien de temps pour avoir mon rapport ?", a: "Quelques minutes. Le temps de renseigner votre cible et vos informations, l’analyse est déjà en cours." },
  { q: "Quels formats de CV sont acceptés ?", a: "Un PDF jusqu’à 10 Mo, ou un copier-coller de votre texte directement dans l’interface." },
  { q: "Quelle différence entre le rapport candidat et la synthèse conseiller ?", a: "C’est la même base : une seule et même synthèse — pour pouvoir travailler ensemble, candidat et conseiller, à partir d’une même lecture partagée." },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen overflow-x-clip bg-background">
      <SiteNav />

      {/* ───────────────────── Hero ───────────────────── */}
      <section className="bg-mesh relative">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-16 sm:px-8 lg:grid-cols-[1.05fr_0.95fr] lg:pb-28">
          <div className="animate-fade-up">
            <Eyebrow>Pour les acteurs de l’emploi</Eyebrow>
            <h1 className="mt-5 font-display text-[2rem] font-extrabold leading-[1.12] tracking-tight text-navy sm:text-5xl">
              Vous postulez. Assurez-vous que votre CV exprime vraiment{" "}
              <span className="text-gradient-brand">ce que vous valez.</span>
            </h1>
            <p className="mt-6 max-w-[34rem] text-lg leading-relaxed text-muted-foreground">
              neoori analyse votre CV face au poste que vous visez — et vous dit exactement ce qui retient l’attention, ce qui freine, et comment faire la différence.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button render={<Link href="/analyse" />} size="xl">
                Lancer mon analyse
                <ArrowRight />
              </Button>
              <Button render={<Link href="/#rapport" />} size="xl" variant="outline">
                Voir un exemple de rapport
              </Button>
            </div>
            <ul className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
              {["Une première analyse gratuite", "Résultat en quelques minutes", "Vos données restent les vôtres"].map((t) => (
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
              className="aspect-[3/2] w-full shadow-card lg:aspect-auto lg:h-[460px]"
              imgClassName="object-top"
              rounded="rounded-3xl"
              sizes="(max-width: 1024px) 100vw, 460px"
              priority
              overlay
            />
            <ReportPreview className="absolute -bottom-6 -left-4 hidden w-[244px] sm:block" />
            <div className="absolute -right-4 top-6 hidden rounded-xl bg-white px-3.5 py-2.5 shadow-float ring-1 ring-foreground/10 sm:block">
              <p className="font-display text-xl font-bold leading-none text-navy">9</p>
              <p className="eyebrow mt-1 text-muted-foreground">sections</p>
            </div>
          </div>
        </div>
      </section>

      {/* ───────────────────── Choose your scenario ───────────────────── */}
      <section id="parcours" className="mx-auto max-w-6xl px-5 py-16 sm:px-8 lg:py-20">
        <Reveal className="max-w-2xl">
          <Eyebrow>Par où commencer</Eyebrow>
          <h2 className="mt-3 font-display text-3xl font-bold text-navy sm:text-4xl">
            Trois situations, trois lectures
          </h2>
          <p className="mt-3 text-muted-foreground">
            Choisissez celle qui vous ressemble le plus. Chacune pose ses propres questions
            et produit son propre rapport.
          </p>
        </Reveal>

        <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-3">
          {PARCOURS.map((p, i) => (
            <Reveal key={p.n} delayMs={i * 90}>
              <Link
                href={p.href}
                className={`group flex h-full flex-col overflow-hidden rounded-2xl bg-card shadow-soft ring-1 transition-all hover:shadow-card focus-visible:outline-none focus-visible:ring-2 ${p.ring}`}
              >
                <span className={`block h-1.5 ${p.bar}`} />
                <div className="flex flex-1 flex-col p-6">
                  <div className="mb-4 flex items-center gap-3">
                    <span className={`grid size-9 shrink-0 place-items-center rounded-lg ${p.chip}`}>
                      <p.icon className="size-4" aria-hidden />
                    </span>
                    <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                      Parcours {p.n}
                    </span>
                  </div>
                  <h3 className="font-display text-lg font-bold leading-tight text-navy">{p.title}</h3>
                  <p className="mt-2 text-sm text-navy-700">{p.lead}</p>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{p.detail}</p>
                  <div className="mt-auto flex items-center justify-between gap-2 pt-5">
                    <span className="rounded-full bg-secondary px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
                      {p.needs}
                    </span>
                    <ArrowRight className="size-4 text-orange transition-transform group-hover:translate-x-0.5" aria-hidden />
                  </div>
                </div>
              </Link>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ───────────────────── Credibility band ───────────────────── */}
      <section className="border-y border-border bg-card">
        <div className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
          <p className="text-center text-sm text-muted-foreground">
            Conçu avec les contraintes des acteurs publics de l’emploi
          </p>
        </div>
      </section>

      {/* ───────────────────── How it works ───────────────────── */}
      <section id="module" className="mx-auto max-w-6xl px-5 py-20 sm:px-8 lg:py-24">
        <Reveal className="max-w-2xl">
          <Eyebrow>Le module</Eyebrow>
          <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-navy sm:text-4xl">
            Quatre étapes. Un regard neuf sur votre parcours.
          </h2>
          <p className="mt-4 text-muted-foreground">
            Vous avez déjà fait le plus dur — construire votre expérience. neoori vous aide à la montrer sous son meilleur jour.
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
              Un regard qui tient compte de votre réalité.
            </h2>
            <p className="mt-4 text-muted-foreground">
              Votre rapport part de ce que vous avez partagé — votre parcours, votre cible, votre situation personnelle. Les recommandations sont pensées pour vous, pour votre situation, pour votre vie réelle.
            </p>

            <ul className="mt-7 grid grid-cols-1 gap-x-6 gap-y-2.5 sm:grid-cols-2">
              {SECTIONS_FULL.map((s) => (
                <li key={s.n} className="flex items-start gap-2.5 text-sm">
                  {s.free ? (
                    <Check className="mt-0.5 size-4 shrink-0 text-success" />
                  ) : (
                    <Lock className="mt-0.5 size-3.5 shrink-0 text-orange" />
                  )}
                  <span className={s.free ? "text-navy" : "text-muted-foreground"}>{s.t}</span>
                </li>
              ))}
            </ul>
            <p className="mt-6 text-sm text-muted-foreground">
              <span className="font-medium text-navy">Les trois premières sections sont offertes.</span> Rapport complet à 9 €.
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Si vous êtes accompagné par un conseiller, il a peut-être un code qui vous donne accès à tout — gratuitement. Ça vaut la peine de lui demander.
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
            Un outil. Trois façons de s’en emparer.
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
              Commencez gratuitement. Allez aussi loin que vous voulez.
            </h2>
          </Reveal>

          <div className="mt-12 grid items-stretch gap-6 lg:grid-cols-3">
            {/* Free */}
            <Reveal className="flex">
              <div className="flex w-full flex-col rounded-3xl bg-card p-7 ring-1 ring-foreground/10 shadow-soft">
                <h3 className="font-display text-lg font-semibold text-navy">Gratuit</h3>
                <p className="mt-2 font-display text-4xl font-extrabold text-navy">0 €</p>
                <p className="mt-2 text-sm font-medium text-navy">Une première analyse qui change déjà le regard.</p>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  Vous découvrez comment votre CV est perçu face au poste que vous visez. Vous identifiez vos vraies forces — y compris celles que vous n’avez pas pensé à mettre en avant. Vous repartez avec des pistes concrètes pour corriger ce qui freine.
                </p>
                <p className="mt-3 text-xs text-muted-foreground">Sections 1 à 3 et verdict de diagnostic inclus. Aucune carte bancaire demandée.</p>
                <Button render={<Link href="/analyse" />} variant="outline" size="lg" className="mt-auto w-full">
                  Je commence maintenant
                </Button>
              </div>
            </Reveal>

            {/* Paid — highlighted */}
            <Reveal delayMs={90} className="flex">
              <div className="relative flex w-full flex-col rounded-3xl bg-navy p-7 text-white shadow-float">
                <span className="absolute right-5 top-5">
                  <Badge variant="peach">✦ Le plus choisi</Badge>
                </span>
                <h3 className="font-display text-lg font-semibold text-white">Analyse complète</h3>
                <p className="mt-2 font-display text-4xl font-extrabold text-white">
                  9 € <span className="text-base font-medium text-white/60">/ analyse</span>
                </p>
                <p className="mt-1 text-sm text-white/70">Le rapport en entier — pour repartir avec un CV retravaillé, prêt à envoyer.</p>
                <p className="mt-4 text-sm text-white/70">En plus des 3 premières sections, vous accédez à :</p>
                <ul className="mt-3 space-y-2.5 text-sm text-white/80">
                  {[
                    "Des préconisations terrain — pas des conseils génériques, des recommandations issues de l’expérience professionnelle réelle du recrutement",
                    "Un exemple concret de reformulation de votre expérience — pour voir la différence, pas juste la comprendre",
                    "Une synthèse de votre profil — claire, structurée, réutilisable pour d’autres candidatures",
                    "Des pistes d’évolution — pour aller plus loin que cette candidature",
                    "Une proposition de CV retravaillé — prête à personnaliser et à envoyer",
                  ].map((f) => (
                    <li key={f} className="flex items-start gap-2">
                      <Check className="mt-0.5 size-4 shrink-0 text-peach" /> <span>{f}</span>
                    </li>
                  ))}
                </ul>
                <Button render={<Link href="/analyse" />} size="lg" className="mt-auto w-full bg-white text-orange-dark hover:bg-white/90">
                  Accéder au rapport complet
                </Button>
              </div>
            </Reveal>

            {/* Counselor code */}
            <Reveal delayMs={180} className="flex">
              <div className="flex w-full flex-col rounded-3xl bg-card p-7 ring-1 ring-foreground/10 shadow-soft">
                <h3 className="font-display text-lg font-semibold text-navy">Code conseiller</h3>
                <p className="mt-2 font-display text-4xl font-extrabold text-navy">Gratuit</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Vous êtes accompagné par un conseiller ? Il a peut-être un code qui vous ouvre l’accès au rapport complet — gratuitement. Ça vaut la peine de lui demander.
                </p>
                <Button render={<Link href="/analyse" />} variant="outline" size="lg" className="mt-auto w-full">
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
              Sérieux, du premier au dernier octet.
            </h2>
            <p className="mt-4 text-white/70">
              neoori a été pensé et créé par une professionnelle de l’emploi. La rigueur du terrain, la puissance de l’IA.
            </p>
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
              Votre CV a des choses à dire. Aidez-le à les dire.
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
              Lancez votre première analyse maintenant — gratuitement, en quelques minutes. Vous repartez déjà avec quelque chose de concret.
            </p>
            <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
              <Button render={<Link href="/analyse" />} size="xl">
                Lancer mon analyse
                <ArrowRight />
              </Button>
              <Button
                render={<a href="mailto:nneoori@proton.me?subject=neoori%20—%20demande%20organisation" />}
                size="xl"
                variant="outline"
              >
                <Mail />
                Contacter l’équipe pour votre structure
              </Button>
            </div>
          </Reveal>
        </div>
      </section>

      <SiteFooter />
    </div>
  )
}
