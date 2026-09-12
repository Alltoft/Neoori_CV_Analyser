"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import {
  ArrowLeft,
  Check,
  Loader2,
  Printer,
  RefreshCw,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { Logo } from "@/components/brand/Logo"
import { RestitutionGuide } from "@/components/voyage/RestitutionGuide"
import { SynthesisSheet } from "@/components/voyage/SynthesisSheet"
import { ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { fmtDateTime } from "@/lib/format"
import {
  getCounselorVoyage, putPortrait, regeneratePortrait, validatePortrait,
} from "@/lib/voyage"
import { SITUATION_LABELS, TRANCHE_LABELS } from "@/lib/voyage-labels"
import {
  PORTRAIT_SECTIONS,
  type CounselorPortrait,
  type CounselorVoyage,
  type PortraitSections,
  type PortraitStatus,
} from "@/types/voyage"

/** The portrait lifecycle in the counselor's words. Chrome, not manual text. */
const PORTRAIT_STATUS_LABELS: Record<PortraitStatus, string> = {
  none: "Pas encore rédigé",
  generating: "Rédaction en cours…",
  draft: "Brouillon à relire",
  validated: "Validé et transmis",
  error: "Échec de la rédaction",
}

/** The flag generation writes when framework vocabulary survived two attempts
 *  (contracts § G.1, FLAG_VOCABULAIRE). */
const FLAG_VOCABULAIRE = "vocabulaire"

const EMPTY_SECTIONS: PortraitSections = {
  accroche: "",
  qui_tu_es: "",
  vibrer: "",
  besoins: "",
  chemins: "",
  pas_encore: "",
}

/** The API may return a partial draft (contracts § I: Partial<PortraitSections>);
 *  the six textareas need all six keys. */
const fillSections = (partial: Partial<PortraitSections>): PortraitSections => ({
  accroche: partial.accroche ?? "",
  qui_tu_es: partial.qui_tu_es ?? "",
  vibrer: partial.vibrer ?? "",
  besoins: partial.besoins ?? "",
  chemins: partial.chemins ?? "",
  pas_encore: partial.pas_encore ?? "",
})

/** Poll cadence while the portrait is being written, and how long this page
 *  load keeps at it (R14) — same values as the candidate hub
 *  (frontend/src/app/voyage/page.tsx POLL_MS / POLL_MAX_MS). */
const POLL_MS = 2000
const POLL_MAX_MS = 3 * 60 * 1000

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

  // In-flight guard (R7 / R14): shared by the mount load, the manual retry
  // and Task 8's 2 s portrait poll, all of which call `load` — a ref, not
  // state, since it is read-and-set inside the same synchronous call and
  // never drives a render itself.
  const loadingRef = useRef(false)

  // R9: the module that owns every voyage endpoint path, not a raw api.get
  // here. Promise-chained (not `async`) so this can be called directly from
  // an effect body without tripping react-hooks/set-state-in-effect — see
  // frontend/src/lib/auth.tsx:36 for what that looks like when it is not.
  const load = useCallback((): Promise<void> => {
    if (loadingRef.current) return Promise.resolve()
    loadingRef.current = true
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
        loadingRef.current = false
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

  // ── portrait draft ────────────────────────────────────────────────────────
  const [sections, setSections] = useState<PortraitSections>(EMPTY_SECTIONS)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [regenerating, setRegenerating] = useState(false)
  // R16: which status "Régénérer" was armed against, not a bare boolean — the
  // confirmation below is *derived* from comparing this to the current
  // status, so a status that changes underneath the button (a poll tick,
  // another tab) un-arms it for free, on the very next render, with no reset
  // effect at all (the same "derive it instead" fix as R7b, one hook up).
  const [confirmRegenFor, setConfirmRegenFor] = useState<PortraitStatus | null>(null)
  const [validating, setValidating] = useState(false)
  const [stalled, setStalled] = useState(false)
  const seededRef = useRef("")
  const streakStartRef = useRef<number | null>(null)

  const portraitStatus = data?.portrait.status
  const confirmRegen = confirmRegenFor !== null && confirmRegenFor === portraitStatus

  useEffect(() => {
    if (!data || data.portrait.status === "generating") return
    // Seed the six fields once per draft. Re-seeding on every poll tick or on
    // every save response would wipe what the counselor is typing.
    const signature = `${data.portrait.status}:${data.portrait.validated_at ?? ""}`
    if (seededRef.current === signature) return
    seededRef.current = signature
    setSections(fillSections(data.portrait.sections))
  }, [data])

  // R14: poll every 2 s while generating, capped at POLL_MAX_MS on this page
  // load (same shape as the candidate hub's own streak ceiling). `load`
  // itself is the in-flight guard, so an overlapping tick is a no-op rather
  // than a second concurrent fetch; a failed tick lands in `error`, which the
  // render below never consults while `data` already exists — so it cannot
  // destroy the editor.
  useEffect(() => {
    if (portraitStatus !== "generating") {
      // Not a `setStalled(false)` reset here on purpose: nothing in this page
      // can start a *new* generating streak without a full remount (the
      // regenerate button never renders while status is already
      // "generating"), so a stale `stalled` never has a next streak to leak
      // into — and a bare reset-on-change is exactly the pattern
      // react-hooks/set-state-in-effect flags (R7b's fix, applied here too).
      streakStartRef.current = null
      return
    }
    if (streakStartRef.current === null) streakStartRef.current = Date.now()

    let alive = true
    const id = setInterval(() => {
      if (!alive) return
      const started = streakStartRef.current
      if (started !== null && Date.now() - started >= POLL_MAX_MS) {
        setStalled(true)
        clearInterval(id)
        return
      }
      void load()
    }, POLL_MS)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [portraitStatus, load])

  // R12 / R15: shared by "Enregistrer" and "Valider et transmettre". The API
  // answers a blank section with {"errors": [...]}, and lib/api.ts resolves
  // error ?? errors[0] ?? message ?? fallback — an errors *array* alone
  // degrades to "Erreur inattendue.", so the gap is named here instead.
  // Rejects (without touching `data`) rather than validating stale text when
  // a section is blank or the save itself fails.
  const saveSections = useCallback((): Promise<CounselorPortrait> => {
    const missing = PORTRAIT_SECTIONS.filter(({ key }) => !sections[key].trim())
    if (missing.length > 0) {
      return Promise.reject(
        new Error(`À compléter avant d’enregistrer : ${missing.map((m) => m.title).join(", ")}.`),
      )
    }
    return putPortrait(token, sections).then((portrait) => {
      setData((current) => (current ? { ...current, portrait } : current))
      return portrait
    })
  }, [sections, token])

  const saveDraft = useCallback(() => {
    setSaving(true)
    setActionError(null)
    saveSections()
      .then(() => {
        setSaved(true)
        setTimeout(() => setSaved(false), 2000)
      })
      .catch((e) => {
        setActionError(
          e instanceof ApiError ? e.message
            : e instanceof Error ? e.message
              : "Échec de l’enregistrement.",
        )
      })
      .finally(() => setSaving(false))
  }, [saveSections])

  const regenerate = useCallback(() => {
    // Two-click confirmation: regeneration replaces the text in the fields.
    if (!confirmRegen) {
      setConfirmRegenFor(portraitStatus ?? null)
      return
    }
    setRegenerating(true)
    setActionError(null)
    seededRef.current = "" // let the new draft repopulate the fields
    regeneratePortrait(token)
      .then((portrait) => {
        setData((current) => (current ? { ...current, portrait } : current))
        setConfirmRegenFor(null) // R16: reset on success
      })
      .catch((e) => {
        setActionError(e instanceof ApiError ? e.message : "Échec de la régénération.")
        setConfirmRegenFor(null) // R16: reset on any error
      })
      .finally(() => setRegenerating(false))
  }, [confirmRegen, portraitStatus, token])

  // R12: save the counselor's current edits FIRST, and post validate only
  // once that save has actually resolved. The server validates the STORED
  // sections — without this, a corrected textarea sits unsaved while validate
  // reads the old text, and the seed effect above then overwrites the
  // textareas with that old text once the response lands, so the correction
  // simply vanishes and the candidate receives the un-edited draft.
  const validate = useCallback(() => {
    setValidating(true)
    setActionError(null)
    saveSections()
      .then(() => validatePortrait(token))
      .then((portrait) => {
        setData((current) => (current ? { ...current, portrait } : current))
      })
      .catch((e) => {
        setActionError(
          e instanceof ApiError ? e.message
            : e instanceof Error ? e.message
              : "Échec de la validation.",
        )
      })
      .finally(() => setValidating(false))
  }, [saveSections, token])

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

            {/* ── Portrait ───────────────────────────────────────────────── */}
            {data ? (
              <section className="mt-8">
                <h2 className="eyebrow text-orange-dark">Portrait</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {PORTRAIT_STATUS_LABELS[data.portrait.status]}
                  {data.portrait.edited ? " · modifié par un conseiller" : ""}
                  {data.portrait.validated_at
                    ? ` · validé le ${fmtDateTime(data.portrait.validated_at)}`
                    : ""}
                </p>

                {/* R13: what failed, before the counselor reaches for "Régénérer". */}
                {data.portrait.status === "error" && data.portrait.error ? (
                  <p className="mt-1 text-xs text-destructive">{data.portrait.error}</p>
                ) : null}

                {data.portrait.flags.includes(FLAG_VOCABULAIRE) ? (
                  <div className="no-print mt-3 flex gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-xs leading-relaxed text-destructive">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                    <p>
                      Vocabulaire à vérifier : la rédaction a gardé des termes techniques — noms de
                      tests, de traits ou de résultats — après une seconde tentative. Relisez et
                      réécrivez les passages concernés avant de valider.
                    </p>
                  </div>
                ) : null}

                {data.portrait.status === "generating" ? (
                  <p className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                    {stalled
                      ? "La rédaction prend plus de temps que prévu. Rechargez la page dans quelques instants."
                      : "Rédaction en cours. Cette page se met à jour toute seule."}
                  </p>
                ) : (
                  <>
                    {/* Editor — screen only. Each field carries .ai-block: this
                        prose is AI-written, the same marking rule as the
                        session-0 phrase above (phase-4 ruling R6). */}
                    <div className="no-print mt-4 space-y-4">
                      {PORTRAIT_SECTIONS.map(({ key, title }) => (
                        <div key={key}>
                          <label
                            htmlFor={`portrait-${key}`}
                            className="text-sm font-semibold text-navy"
                          >
                            {title}
                          </label>
                          <Textarea
                            id={`portrait-${key}`}
                            value={sections[key]}
                            onChange={(e) =>
                              setSections((current) => ({ ...current, [key]: e.target.value }))
                            }
                            className="ai-block mt-1 min-h-24 text-sm"
                          />
                        </div>
                      ))}

                      {actionError ? (
                        <p className="text-xs text-destructive">{actionError}</p>
                      ) : null}

                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {/* R11: draft or error — never while generating, and
                            never a dead end on error (commit c9edd16). */}
                        {data.portrait.status === "draft" || data.portrait.status === "error" ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={saving || validating || regenerating}
                            onClick={regenerate}
                          >
                            <RefreshCw className="size-3.5" />
                            {confirmRegen ? "Confirmer : réécrire le brouillon" : "Régénérer"}
                          </Button>
                        ) : null}
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={saving || validating || regenerating}
                          onClick={saveDraft}
                        >
                          {saved ? (
                            <>
                              <Check className="size-3.5 text-success" /> Enregistré
                            </>
                          ) : saving ? (
                            "Enregistrement…"
                          ) : (
                            "Enregistrer"
                          )}
                        </Button>
                        {data.portrait.status === "draft" ? (
                          <Button
                            variant="navy"
                            size="sm"
                            disabled={saving || validating || regenerating}
                            onClick={validate}
                          >
                            {validating ? "Transmission…" : "Valider et transmettre"}
                          </Button>
                        ) : null}
                      </div>

                      {data.portrait.status === "validated" ? (
                        <p className="text-right text-xs text-success">
                          Transmis au candidat. Vos corrections restent enregistrables.
                        </p>
                      ) : null}
                    </div>

                    {/* Print mirror — what the counselor carries into the room */}
                    <div className="hidden print:block">
                      {PORTRAIT_SECTIONS.map(({ key, title }) => (
                        <div key={key} className="print-break ai-block mt-4 p-3">
                          <h3 className="font-display text-sm font-semibold text-navy">{title}</h3>
                          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-navy">
                            {sections[key] || "—"}
                          </p>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </section>
            ) : null}

            <RestitutionGuide />
          </div>
        </div>
      </div>
    </div>
  )
}
