"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowRight, KeyRound, Map as MapIcon, ShieldCheck, Trash2 } from "lucide-react"

import { AppBar } from "@/components/layout/AppBar"
import { MicroReveal } from "@/components/voyage/MicroReveal"
import { SessionProgress } from "@/components/voyage/SessionProgress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { copyToClipboard } from "@/lib/utils"
import {
  createVoyage, deleteVoyage, getBank, getResponses, getVoyage, retryMicro, unlockVoyage,
} from "@/lib/voyage"
import type { Bank, Voyage, VoyageResponses } from "@/types/voyage"

/** Normal poll cadence while a phrase or a portrait is being written; back off
 *  to 4 s after a failed read rather than hammering a possibly-down backend
 *  (frontend/src/app/analyse/en-cours/[id]/page.tsx uses the same two values). */
const POLL_MS = 2000
const POLL_BACKOFF_MS = 4000
/** Give up on a single continuous "generating" streak after 3 minutes on this
 *  page load (R10) — the en-cours screen's 10 min ceiling is for a whole
 *  analysis, not a one-sentence phrase or a six-section portrait. */
const POLL_MAX_MS = 3 * 60 * 1000

type Profile = { prenom?: string | null; tranche_age?: string | null }

/** How many of each session's items already have an answer — drives the
 *  « Reprendre » vs « Commencer » label and the per-row counter. */
function answeredBySession(
  bank: Bank | null,
  responses: VoyageResponses | null,
): Record<string, number> {
  const out: Record<string, number> = {}
  if (!bank || !responses) return out
  for (const s of bank.sessions) {
    out[s.n] = s.items.filter((it) => responses.answers[it.id] !== undefined).length
  }
  return out
}

export default function VoyagePage() {
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()

  const [bank, setBank] = useState<Bank | null>(null)
  const [voyage, setVoyage] = useState<Voyage | null>(null)
  const [responses, setResponses] = useState<VoyageResponses | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loaded, setLoaded] = useState(false)
  // R9: a failed read is never treated as "no voyage" — it renders an Alert
  // and a retry, and nothing else, instead of falling through to the consent
  // gate (which would offer to create a second voyage over a live one).
  const [loadError, setLoadError] = useState<string | null>(null)
  // Action-level errors (create / redeem / retry / delete) — shown above
  // whichever content block is already on screen, unlike loadError.
  const [error, setError] = useState<string | null>(null)

  // Consent gate
  const [consent, setConsent] = useState(false)
  const [age, setAge] = useState(false)
  const [creating, setCreating] = useState(false)

  // Counselor code
  const [code, setCode] = useState("")
  const [codeState, setCodeState] = useState<"idle" | "checking">("idle")

  // Session-0 phrase retry (PM-Q2)
  const [retryingMicro, setRetryingMicro] = useState(false)

  // R10: true once the current generating streak (phrase or portrait) has
  // run past POLL_MAX_MS on this page load.
  const [stalled, setStalled] = useState(false)

  // R8: share-link copy confirmation.
  const [copied, setCopied] = useState(false)

  // F1: a loadError retry in flight. State (not a ref) because it drives the
  // button's disabled state and label; the guard in retryLoad below is safe
  // because React flushes discrete click events synchronously, so a second
  // click always observes the first click's update (same reasoning as F3).
  const [reloading, setReloading] = useState(false)

  // Poll bookkeeping — mutable, read only inside the poll effect/timer, never
  // during render (react-hooks/refs).
  const streakStartRef = useRef<number | null>(null)
  // F2: the last (micro_status, portrait_status) pair the poll effect saw —
  // lets it tell "still generating, same thing" from "still generating, but
  // the thing that's generating just changed" (e.g. the phrase just
  // succeeded and the portrait is what's left running).
  const lastPairRef = useRef<string | null>(null)
  const delayRef = useRef(POLL_MS)
  const [pollTick, setPollTick] = useState(0)
  // F4: true while the page `error` on screen came from retryPhrase's own
  // rejection — cleared by any other setError call, and by the poll loop
  // once it sees the phrase actually leave "generating".
  const retryErrorRef = useRef(false)

  // The proxy gates /voyage on cookie *presence*, which misses an expired
  // token. Without this, an expired session renders the consent form and only
  // fails at POST. Same guard as frontend/src/app/profil/page.tsx:104-106.
  useEffect(() => {
    if (!authLoading && !user) router.replace("/connexion?redirect=/voyage")
  }, [authLoading, user, router])

  // The loader: fetches bank + voyage + profile (+ responses, once a voyage
  // exists) and reports any rejection as loadError. Reused by the mount
  // effect below, the loadError "Réessayer" button, the post-delete reload
  // and start()'s post-409 re-read (R9, R24).
  //
  // F1 fix: loadError is cleared only once the read actually succeeds, not
  // synchronously when the loader starts. Clearing it eagerly left `loaded`
  // true and `voyage` still null for the whole retry, so the consent gate
  // (and its "Commencer le voyage" button) was reachable while a stale
  // failure was being re-checked — on a finished voyage a click there is a
  // 201 retake that hides a validated portrait, exactly what R9 exists to
  // prevent. This also has no leading synchronous setState, so the mount
  // effect can call it directly (see below) without tripping
  // react-hooks/set-state-in-effect.
  const load = useCallback(() => {
    return Promise.all([
      getBank(),
      getVoyage(),
      api.get<{ profile: Profile | null }>("/profile", { skipRedirect: true }).then((r) => r.profile),
    ])
      .then(([b, v, p]) => {
        setLoadError(null)
        setBank(b)
        setVoyage(v)
        setProfile(p)
        if (!v) {
          setResponses(null)
          return undefined
        }
        return getResponses().then((r) => { setResponses(r) })
      })
      .catch((e) => {
        setLoadError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      })
      .finally(() => {
        setLoaded(true)
      })
  }, [])

  // R15: the loader waits for auth — it never fires while a token is still
  // being checked or has come back empty (that case is the redirect above).
  useEffect(() => {
    if (authLoading || !user) return
    load()
  }, [authLoading, user, load])

  // While the phrase or the portrait is being written, re-read the voyage.
  // Each successful read replaces `voyage`, which re-runs this effect — that
  // is the loop. R10: a failed read backs off to 4 s (pollTick forces the
  // re-run since `voyage` itself did not change); a continuous streak past
  // POLL_MAX_MS on this page load sets `stalled` and stops scheduling.
  useEffect(() => {
    const microStatus = voyage?.micro_status ?? null
    const portraitStatus = voyage?.portrait_status ?? null
    const generating = microStatus === "generating" || portraitStatus === "generating"
    if (!voyage || !generating) {
      streakStartRef.current = null
      lastPairRef.current = null
      return
    }
    // F2: restart the streak whenever the pair changes, not only when
    // generating starts or stops. Without this, the phrase succeeding while
    // the portrait keeps generating left the portrait riding the phrase's
    // old streak clock and stalling early.
    const pairKey = `${microStatus}|${portraitStatus}`
    if (lastPairRef.current !== pairKey) {
      lastPairRef.current = pairKey
      streakStartRef.current = Date.now()
    }

    let alive = true
    const delay = delayRef.current
    const t = setTimeout(() => {
      if (!alive) return
      const started = streakStartRef.current
      if (started !== null && Date.now() - started >= POLL_MAX_MS) {
        setStalled(true)
        return
      }
      setStalled(false)
      getVoyage()
        .then((v) => {
          if (!alive) return
          delayRef.current = POLL_MS
          // F4: a retry-path error next to the phrase is stale once polling
          // shows the phrase actually resolved on its own.
          if (retryErrorRef.current && v?.micro_status !== "generating") {
            retryErrorRef.current = false
            setError(null)
          }
          // A poll that returns null (voyage deleted in another tab) must
          // still be applied — silently keeping the stale voyage would leave
          // this tab polling a voyage that no longer exists.
          setVoyage(v)
        })
        .catch(() => {
          if (!alive) return
          delayRef.current = POLL_BACKOFF_MS
          setPollTick((n) => n + 1)
        })
    }, delay)

    return () => { alive = false; clearTimeout(t) }
  }, [voyage, pollTick])

  const start = useCallback(() => {
    setError(null)
    setCreating(true)
    createVoyage()
      .then((v) => {
        setVoyage(v)
        setResponses({ answers: {}, billets: {} })
      })
      .catch((e) => {
        // A 409 means this tab's "no voyage" view is stale — re-read instead
        // of leaving a dead-end error on what looks like the consent gate.
        if (e instanceof ApiError && e.status === 409) return load()
        retryErrorRef.current = false
        setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
        return undefined
      })
      .finally(() => {
        setCreating(false)
      })
  }, [load])

  // F3: guarded with a ref, not codeState. State would also survive two
  // separate discrete events (React flushes those synchronously, so the
  // second handler always sees the first's update) but a ref reads back
  // immediately regardless, so the guard does not depend on reasoning about
  // event-flushing timing.
  const checkingRef = useRef(false)

  const redeem = useCallback(() => {
    if (checkingRef.current) return
    setError(null)
    if (!code.trim()) {
      retryErrorRef.current = false
      setError("Saisissez votre code conseiller.")
      return
    }
    checkingRef.current = true
    setCodeState("checking")
    unlockVoyage(code)
      .then((v) => {
        setVoyage(v)
        setCode("")
      })
      .catch((e) => {
        // F6: a 409 means the voyage was already unlocked (e.g. in another
        // tab) — re-read instead of leaving the error up next to a code
        // field that no longer applies.
        if (e instanceof ApiError && e.status === 409) return load()
        retryErrorRef.current = false
        setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
        return undefined
      })
      .finally(() => {
        setCodeState("idle")
        checkingRef.current = false
      })
  }, [code, load])

  // PM-Q2: retry a session-0 phrase stuck in "error" or stalled in
  // "generating". On acceptance, restart the poll streak from zero; on any
  // rejection, show the message and re-read the voyage.
  const retryPhrase = useCallback(() => {
    setError(null)
    setRetryingMicro(true)
    retryMicro()
      .then((v) => {
        streakStartRef.current = null
        lastPairRef.current = null
        delayRef.current = POLL_MS
        setStalled(false)
        setVoyage(v)
      })
      .catch((e) => {
        // F4: flagged so the poll loop can clear this once it sees the
        // phrase actually leave "generating" on its own.
        retryErrorRef.current = true
        setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
        streakStartRef.current = null
        lastPairRef.current = null
        delayRef.current = POLL_MS
        setStalled(false)
        return load()
      })
      .finally(() => {
        setRetryingMicro(false)
      })
  }, [load])

  const remove = useCallback(() => {
    if (!window.confirm(
      "Supprimer votre voyage ? Vos réponses, votre phrase et votre portrait seront effacés. Cette action est définitive.",
    )) return
    deleteVoyage()
      .then(() => {
        // R24: an older finished voyage may legitimately resurface — let the
        // loader decide, rather than assuming there is nothing left.
        retryErrorRef.current = false
        setError(null)
        setCode("")
        setConsent(false)
        setAge(false)
        streakStartRef.current = null
        lastPairRef.current = null
        delayRef.current = POLL_MS
        setStalled(false)
        return load()
      })
      .catch((e) => {
        retryErrorRef.current = false
        setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      })
  }, [load])

  const copyShareLink = useCallback(() => {
    if (!voyage?.share_token) return
    const url = `${window.location.origin}/voyage/c/${voyage.share_token}`
    copyToClipboard(url).then((ok) => {
      if (!ok) {
        window.prompt("Copiez le lien conseiller :", url)
        return
      }
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    })
  }, [voyage])

  // F1: wraps load() for the loadError "Réessayer" button specifically —
  // disables the button and swaps its label while a retry is in flight, and
  // a second click cannot start a parallel load.
  const retryLoad = useCallback(() => {
    if (reloading) return
    setReloading(true)
    load().finally(() => setReloading(false))
  }, [load, reloading])

  if (authLoading || !user || !loaded) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="mx-auto max-w-3xl px-4 py-8">
          <Skeleton className="h-9 w-64" />
          <div className="mt-6 space-y-3">
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20 rounded-2xl" />)}
          </div>
        </div>
      </div>
    )
  }

  const answered = answeredBySession(bank, responses)
  const finished = voyage?.status === "termine"

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />
      <div className="voyage-rule" role="presentation" aria-hidden />

      <div className="mx-auto max-w-3xl px-4 py-8">
        <div className="mb-6">
          <p className="eyebrow inline-flex items-center gap-2 text-orange-dark">
            <MapIcon className="size-3.5" aria-hidden /> Le voyage
          </p>
          <h1 className="mt-1.5 font-display text-2xl font-bold text-navy sm:text-3xl">
            Mon cahier d&apos;exploration
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Six sessions pour poser ce que vous savez déjà de vous. La première prend 5 minutes
            et se fait en autonomie ; les cinq suivantes se font avec un conseiller.
          </p>
          <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
            Aucune session n&apos;est obligatoire : vos analyses fonctionnent sans. Ce que vous
            répondez ici les rend plus précises.
          </p>
        </div>

        {loadError ? (
          <>
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{loadError}</AlertDescription>
            </Alert>
            <Button size="lg" onClick={retryLoad} disabled={reloading}>
              {reloading ? "Chargement…" : "Réessayer"}
            </Button>
          </>
        ) : (
          <>
            {error && (
              <Alert variant="destructive" className="mb-4">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* ── No voyage yet: consent + age gate ─────────────────────── */}
            {!voyage && (
              <div className="rounded-2xl bg-card p-5 shadow-soft ring-1 ring-foreground/10 sm:p-6">
                <h2 className="font-display text-base font-semibold text-navy">Votre accord</h2>

                <label className="mt-3 flex cursor-pointer items-start gap-3 rounded-lg bg-secondary/60 p-3">
                  <Checkbox className="mt-0.5" checked={consent} onCheckedChange={(v) => setConsent(v)} />
                  <span className="text-xs leading-relaxed text-navy-700">
                    J&apos;accepte que mes réponses au voyage soient conservées et chiffrées, et
                    utilisées pour préparer mon portrait et enrichir mes analyses.
                    <span className="mt-1 block text-muted-foreground">
                      Elles sont stockées séparément de mon profil. Je peux les supprimer à tout
                      moment depuis cette page, sans toucher au reste de mon compte.
                    </span>
                  </span>
                </label>

                <label className="mt-3 flex cursor-pointer items-start gap-3 rounded-lg bg-secondary/60 p-3">
                  <Checkbox className="mt-0.5" checked={age} onCheckedChange={(v) => setAge(v)} />
                  <span className="text-xs leading-relaxed text-navy-700">J&apos;ai 15 ans ou plus.</span>
                </label>

                <div className="mt-5 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
                  <p className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                    <ShieldCheck className="size-3.5 shrink-0 text-success" aria-hidden />
                    Données chiffrées, supprimables à tout moment.
                  </p>
                  <Button size="lg" disabled={!consent || !age || creating} onClick={start}>
                    {creating ? "Création…" : "Commencer le voyage"} <ArrowRight className="size-4" />
                  </Button>
                </div>
              </div>
            )}

            {/* ── A voyage exists ───────────────────────────────────────── */}
            {voyage && bank && (
              <div className="space-y-5">
                <MicroReveal
                  status={voyage.micro_status}
                  phrase={voyage.micro_phrase}
                  stalled={voyage.micro_status === "generating" && stalled}
                  retrying={retryingMicro}
                  onRetry={retryPhrase}
                />

                <SessionProgress
                  sessions={bank.sessions}
                  voyage={voyage}
                  profile={profile}
                  answered={answered}
                />

                {!voyage.has_code && (
                  <div>
                    <div className="flex flex-col gap-3 rounded-2xl bg-card p-4 ring-1 ring-foreground/10 sm:flex-row sm:items-center">
                      <span className="inline-flex shrink-0 items-center gap-2 text-sm font-medium text-navy">
                        <KeyRound className="size-4 text-orange-dark" aria-hidden />
                        Vous avez un code conseiller ?
                      </span>
                      <Input
                        value={code}
                        onChange={(e) => setCode(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") redeem() }}
                        placeholder="ex. A1B2C3D4"
                        aria-label="Code conseiller"
                        className="h-10 flex-1 bg-background font-mono text-sm"
                      />
                      <Button variant="outline" size="lg" onClick={redeem} disabled={codeState === "checking"}>
                        {codeState === "checking" ? "Vérification…" : "Activer"}
                      </Button>
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                      Le code ouvre les sessions 1 à 5. Il est gratuit pour les bénéficiaires
                      Cap Emploi, Mission Locale et France Travail.
                    </p>
                  </div>
                )}

                {/* F5: nothing is left to open on a finished voyage, so the
                    nudge to fill the profile no longer applies. */}
                {!finished && (!profile?.prenom || !profile?.tranche_age) ? (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    Les sessions 1 à 5 utilisent le prénom et la tranche d&apos;âge de votre
                    profil.{" "}
                    <Link href="/profil" className="link-underline text-navy">Compléter mon profil</Link>
                  </p>
                ) : null}

                {/* R8: nothing else surfaces this to the candidate — without
                    it every portrait stays draft forever. */}
                {voyage.share_token && (
                  <div className="rounded-2xl bg-card p-4 ring-1 ring-foreground/10">
                    <p className="font-display text-sm font-semibold text-navy">
                      Lien à transmettre à votre conseiller
                    </p>
                    <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center">
                      <Input
                        readOnly
                        value={`${window.location.origin}/voyage/c/${voyage.share_token}`}
                        aria-label="Lien conseiller"
                        onFocus={(e) => e.currentTarget.select()}
                        className="h-10 flex-1 bg-background font-mono text-xs"
                      />
                      <Button variant="outline" size="lg" className="shrink-0" onClick={copyShareLink}>
                        {copied ? "Lien copié" : "Copier le lien"}
                      </Button>
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                      Ce lien ne s&apos;ouvre que pour un conseiller connecté à son compte.
                    </p>
                  </div>
                )}

                {/* Portrait — only meaningful once the voyage is finished. */}
                {finished && voyage.portrait_status === "validated" && (
                  <div className="flex flex-col items-start justify-between gap-3 rounded-2xl bg-navy p-5 sm:flex-row sm:items-center">
                    <div>
                      <p className="eyebrow text-peach">Votre portrait</p>
                      <p className="mt-1 font-display text-base font-bold text-white">
                        Relu et validé par votre conseiller.
                      </p>
                    </div>
                    <Button
                      render={<Link href="/voyage/portrait" />}
                      size="lg"
                      className="shrink-0 bg-white text-navy hover:bg-white/90"
                    >
                      Voir mon portrait <ArrowRight className="size-4" />
                    </Button>
                  </div>
                )}

                {finished && voyage.portrait_status === "generating" && (
                  <p className="rounded-2xl bg-card p-4 text-sm leading-relaxed text-muted-foreground ring-1 ring-foreground/10">
                    {stalled
                      ? "La rédaction de votre portrait prend plus de temps que prévu. Si elle n'aboutit pas, votre conseiller pourra la relancer depuis le lien ci-dessus."
                      : "Votre portrait est en cours de rédaction."}
                  </p>
                )}

                {finished && voyage.portrait_status === "draft" && (
                  <p className="rounded-2xl bg-card p-4 text-sm leading-relaxed text-muted-foreground ring-1 ring-foreground/10">
                    Votre portrait est rédigé. Transmettez le lien ci-dessus à votre conseiller :
                    vous y aurez accès une fois qu&apos;il aura été relu avec vous.
                  </p>
                )}

                {finished && voyage.portrait_status === "error" && (
                  <p className="rounded-2xl bg-card p-4 text-sm leading-relaxed text-muted-foreground ring-1 ring-foreground/10">
                    La rédaction de votre portrait n&apos;a pas abouti. Votre conseiller peut la
                    relancer depuis le lien ci-dessus.
                  </p>
                )}

                <div className="pt-2">
                  <button
                    type="button"
                    onClick={remove}
                    className="inline-flex items-center gap-1.5 text-xs text-muted-foreground underline-offset-2 hover:text-destructive hover:underline"
                  >
                    <Trash2 className="size-3.5" aria-hidden /> Supprimer mon voyage
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
