"use client"

import Link from "next/link"
import { ArrowRight, Compass, Map as MapIcon, Sprout, Target } from "lucide-react"

import { AppBar } from "@/components/layout/AppBar"

/**
 * The three cards. Clicking one picks the form *and* the prompt — the CDC is
 * explicit that there is no going back once a form opens, so the copy has to
 * make the choice legible before the click, not after.
 */
const PARCOURS = [
  {
    href: "/analyse/nouveau",
    n: "1",
    icon: Target,
    title: "J'ai une cible",
    lead: "Vous visez un poste ou un secteur précis, peut-être avec une offre en main.",
    detail: "Votre CV est comparé à cette cible, point par point.",
    needs: "CV requis",
  },
  {
    href: "/analyse/direction",
    n: "2",
    icon: Compass,
    title: "Je cherche ma direction",
    lead: "Vous avez un parcours, mais pas encore de cible.",
    detail: "On part de ce que vous avez déjà construit pour identifier des pistes.",
    needs: "CV requis",
  },
  {
    href: "/analyse/depart",
    n: "3",
    icon: Sprout,
    title: "Je pars de zéro",
    lead: "Peu ou pas d'expérience formelle, ou un retour après une longue pause.",
    detail: "Sport, bénévolat, aidance, projets personnels : tout compte comme matière première.",
    needs: "Aucun CV nécessaire",
  },
]

export default function ChoisirParcoursPage() {
  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />
      <div className="mx-auto max-w-5xl px-4 py-10">
        <div className="mb-8 max-w-2xl">
          <p className="eyebrow text-orange-dark">Votre parcours</p>
          <h1 className="mt-1 font-display text-2xl font-bold text-navy sm:text-3xl">
            Par où commencer ?
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Choisissez la situation qui vous ressemble le plus. Vous pourrez toujours
            en lancer une autre plus tard.
          </p>
        </div>

        {/* The voyage is a fourth scenario, not a fourth parcours: full width
            and on the charter's inverted surface, so the difference reads
            before any hue does. The three parcours own orange, navy and teal. */}
        <Link
          href="/voyage"
          className="group mb-5 block overflow-hidden rounded-2xl bg-navy shadow-card transition-shadow hover:shadow-float focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-peach"
        >
          <span className="voyage-rule block" />
          <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center">
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-white/10 text-peach">
              <MapIcon className="size-5" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="eyebrow text-peach">Le voyage</p>
              <h2 className="mt-1 font-display text-lg font-bold text-white">
                Mon cahier d&apos;exploration
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-white/80">
                5 minutes pour commencer. Ce que vous y répondez enrichit toutes vos analyses.
              </p>
            </div>
            <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5 text-xs font-medium text-white">
              Commencer
              <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
            </span>
          </div>
        </Link>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
          {PARCOURS.map(({ href, n, icon: Icon, title, lead, detail, needs }) => (
            <Link
              key={n}
              href={href}
              className="group flex flex-col rounded-2xl bg-card p-6 shadow-soft ring-1 ring-foreground/10 transition-shadow hover:shadow-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <div className="mb-4 flex items-center gap-3">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-peach-soft text-orange-dark">
                  <Icon className="size-4" aria-hidden />
                </span>
                <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                  Parcours {n}
                </span>
              </div>

              <h2 className="font-display text-lg font-bold leading-tight text-navy">{title}</h2>
              <p className="mt-2 text-sm text-navy-700">{lead}</p>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{detail}</p>

              <div className="mt-auto flex items-center justify-between gap-2 pt-5">
                <span className="rounded-full bg-secondary px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
                  {needs}
                </span>
                <ArrowRight className="size-4 text-orange transition-transform group-hover:translate-x-0.5" aria-hidden />
              </div>
            </Link>
          ))}
        </div>

        <p className="mt-8 text-xs text-muted-foreground">
          Les trois parcours partent du même profil de base.{" "}
          <Link href="/profil" className="link-underline text-navy">
            Compléter mon profil
          </Link>
        </p>
      </div>
    </div>
  )
}
