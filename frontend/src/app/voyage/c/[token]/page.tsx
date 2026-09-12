"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Printer, ShieldAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Logo } from "@/components/brand/Logo"
import { RestitutionGuide } from "@/components/voyage/RestitutionGuide"
import { SynthesisSheet } from "@/components/voyage/SynthesisSheet"
import { ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { getCounselorVoyage } from "@/lib/voyage"
import { SITUATION_LABELS, TRANCHE_LABELS } from "@/lib/voyage-labels"
import type { CounselorVoyage, PortraitStatus } from "@/types/voyage"

/** The portrait lifecycle in the counselor's words. Chrome, not manual text. */
const PORTRAIT_STATUS_LABELS: Record<PortraitStatus, string> = {
  none: "Pas encore rédigé",
  generating: "Rédaction en cours…",
  draft: "Brouillon à relire",
  validated: "Validé et transmis",
  error: "Échec de la rédaction",
}

/**
 * Counselor surface for le voyage — the synthesis sheet, the portrait draft and
 * the restitution guide.
 *
 * THIS IS THE ONLY PAGE IN THE APP THAT MAY SHOW A SCORE, A TRAIT NAME OR A
 * FRAMEWORK NAME (spec decision 7). Two gates stand in front of it: the API
 * needs the counselor/admin role *and* the token (contracts § E, counselor
 * endpoints), and the guard below refuses to fetch anything for anyone else, so
 * a candidate holding the link never even triggers a request. Nothing here may
 * be copied into /voyage, /voyage/session/[n] or /voyage/portrait.
 */
export default function VoyageCounselorPage() {
  const { token } = useParams<{ token: string }>()
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()
  const allowed = user?.role === "counselor" || user?.role === "admin"

  const [data, setData] = useState<CounselorVoyage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloading, setReloading] = useState(false)

  // R9: the module that owns every voyage endpoint path, not a raw api.get
  // here. Promise-chained (not `async`) so this can be called directly from
  // an effect body without tripping react-hooks/set-state-in-effect — see
  // frontend/src/lib/auth.tsx:36 for what that looks like when it is not.
  const load = useCallback((): Promise<void> => {
    return getCounselorVoyage(token)
      .then((voyage) => {
        setData(voyage)
        setError(null)
      })
      .catch((e) => {
        // R7 / R14 (Task 8's poll reuses this same loader): never blank out
        // data already on screen. Only the pre-data branch below ever reads
        // `error`, so a failed reload — including a later poll tick — cannot
        // throw away the synthesis sheet or what the counselor is typing.
        setError(e instanceof ApiError ? e.message : "Erreur de chargement.")
      })
      .finally(() => {
        setLoading(false)
      })
  }, [token])

  // R8: the proxy only checks cookie *presence* — an expired token still
  // reaches this page, and useAuth's own 401 (skipRedirect) resolves to
  // `user: null`. Redirect from here with the deep link intact, rather than
  // letting api.ts's bare "/connexion" swallow it (same guard as
  // frontend/src/app/voyage/page.tsx).
  useEffect(() => {
    if (!authLoading && !user) router.replace(`/connexion?redirect=/voyage/c/${token}`)
  }, [authLoading, user, router, token])

  // R7b: no setState for the !allowed case. The render below checks !allowed
  // before it ever consults `loading`, so that branch's static card has
  // nothing to derive from `loading` — deleting the call (rather than
  // guarding it) is what keeps this effect from tripping
  // react-hooks/set-state-in-effect.
  useEffect(() => {
    if (authLoading || !allowed) return
    void load()
  }, [authLoading, allowed, load])

  // R7: the "Réessayer" button on the pre-data error card. `load` itself is
  // the in-flight guard (Task 8 adds it) — this just drives the button's own
  // disabled state and label.
  const retryLoad = useCallback(() => {
    setReloading(true)
    load().finally(() => setReloading(false))
  }, [load])

  // ── gate ───────────────────────────────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-secondary px-5">
        <Skeleton className="h-40 w-full max-w-sm rounded-2xl" />
      </div>
    )
  }

  if (!allowed) {
    return (
      <div className="grid min-h-screen place-items-center bg-secondary px-5">
        <div className="max-w-sm rounded-2xl bg-card p-8 text-center ring-1 ring-foreground/10 shadow-card">
          <Logo className="mx-auto text-2xl" />
          <ShieldAlert className="mx-auto mt-6 size-6 text-destructive" aria-hidden="true" />
          <h1 className="mt-3 font-display text-lg font-bold text-navy">Accès non autorisé.</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {user
              ? "Cette fiche est réservée aux conseillers. Votre portrait apparaît sur votre espace dès qu’un conseiller l’a validé."
              : "Connectez-vous avec un compte conseiller pour ouvrir cette fiche."}
          </p>
          <Button
            render={<Link href={user ? "/espace" : `/connexion?redirect=/voyage/c/${token}`} />}
            variant="outline"
            size="lg"
            className="mt-6"
          >
            {user ? "Mon espace" : "Se connecter"}
          </Button>
        </div>
      </div>
    )
  }

  // R7: a failed load, with nothing already on screen — this never fires once
  // `data` exists (a later poll tick failing does not fall in here).
  if (error && !data) {
    return (
      <div className="grid min-h-screen place-items-center bg-secondary px-5">
        <div className="max-w-sm rounded-2xl bg-card p-8 text-center ring-1 ring-foreground/10 shadow-card">
          <Logo className="mx-auto text-2xl" />
          <h1 className="mt-6 font-display text-lg font-bold text-navy">{error}</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Vérifiez le lien avec la personne qui vous l’a transmis.
          </p>
          <Button size="lg" className="mt-6" onClick={retryLoad} disabled={reloading}>
            {reloading ? "Chargement…" : "Réessayer"}
          </Button>
        </div>
      </div>
    )
  }

  const prenom = data?.prenom ?? "—"
  const facts: [string, string][] = [
    ["Prénom", prenom],
    [
      "Tranche d’âge",
      data?.tranche_age ? TRANCHE_LABELS[data.tranche_age] ?? data.tranche_age : "—",
    ],
    ["Situation", data?.situation ? SITUATION_LABELS[data.situation] ?? data.situation : "—"],
    ["Portrait", data ? PORTRAIT_STATUS_LABELS[data.portrait.status] : "—"],
  ]

  return (
    <div className="min-h-screen bg-secondary">
      {/* Action bar */}
      <div className="no-print sticky top-0 z-40 flex items-center justify-between gap-3 border-b border-border bg-secondary/95 px-5 py-3 backdrop-blur-sm sm:px-8">
        <Button render={<Link href="/espace" />} variant="ghost" size="sm">
          <ArrowLeft className="size-3.5" /> Mon espace
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={loading}
          onClick={() => setTimeout(() => window.print(), 50)}
        >
          <Printer className="size-3.5" /> PDF fiche
        </Button>
      </div>

      <div className="px-4 py-8">
        <div className="report-shell">
          <div className="report-rule" />

          <div className="bg-navy px-8 pb-6 pt-6 text-white">
            <div className="flex items-center justify-between gap-3">
              <Logo tone="light" className="text-base" />
              <Badge variant="peach">VERSION CONSEILLER</Badge>
            </div>
            <h1 className="mt-3 font-display text-2xl font-extrabold leading-tight text-white">
              Le voyage · {prenom}
            </h1>
            <p className="mt-1 text-sm text-peach">
              Fiche de synthèse, portrait à relire et guide d’entretien
            </p>
          </div>

          <div className="px-8 py-7">
            {/* The boundary, said out loud on the page itself. */}
            <p className="mb-6 rounded-lg border border-orange/30 bg-peach-soft px-4 py-3 text-xs leading-relaxed text-navy">
              Document conseiller. Cette fiche porte des résultats chiffrés et des noms de tests :
              elle ne se montre pas au candidat. Le portrait qu’il recevra, lui, est écrit sans ces
              termes.
            </p>

            {loading ? (
              <div className="mb-7 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (
                  <Skeleton key={i} className="h-12" />
                ))}
              </div>
            ) : (
              <div className="mb-7 grid grid-cols-1 gap-3 rounded-lg bg-secondary p-4 text-xs sm:grid-cols-2 lg:grid-cols-4">
                {facts.map(([label, value]) => (
                  <div key={label}>
                    <p className="eyebrow text-muted-foreground">{label}</p>
                    <p className="mt-1 font-semibold text-navy">{value}</p>
                  </div>
                ))}
              </div>
            )}

            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-24" />
                ))}
              </div>
            ) : data ? (
              <SynthesisSheet
                synthesis={data.synthesis}
                microPhrase={data.micro_phrase}
                microStatus={data.micro_status}
                rowScoringVersion={data.scoring_version}
              />
            ) : null}

            <RestitutionGuide />
          </div>
        </div>
      </div>
    </div>
  )
}
