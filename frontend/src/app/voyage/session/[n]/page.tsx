"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, ArrowRight, Check, Lock } from "lucide-react"

import { AppBar } from "@/components/layout/AppBar"
import { ChecklistRow } from "@/components/voyage/ChecklistRow"
import { SceneCard } from "@/components/voyage/SceneCard"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import {
  completeSession, getBank, getResponses, getVoyage, missingItems, putResponses,
} from "@/lib/voyage"
import {
  isScene, sessionLock, LOCK_CODE, LOCK_PROFILE, NEUTRAL, NEUTRAL_MAX,
  type BankChecklistItem, type BankSession, type ChecklistAnswer,
  type GateProfile, type Voyage, type VoyageAnswer, type VoyageResponses,
} from "@/types/voyage"
import { stepForLock } from "@/lib/profile-steps"

/** Every field sessionLock() reads. A narrower type here would not fail to
 *  compile — they are all optional — it would just make the mirror decide that
 *  a block it never fetched is unanswered, and lock a session the server
 *  opens. */
type Profile = GateProfile

/** The server's read-only refusal, byte-identical to routes/voyage.py. */
const SESSION_CLOSED = "Cette session est terminée : ses réponses ne sont plus modifiables."

const asMark = (v: VoyageAnswer | undefined): ChecklistAnswer | undefined =>
  typeof v === "boolean" || v === NEUTRAL ? v : undefined
/** A scene's choices, first choice first. A bare letter is a single choice —
 *  how every answer was stored before ranked choices. */
const asLetters = (v: VoyageAnswer | undefined): string[] =>
  typeof v === "string" ? [v] : Array.isArray(v) ? v : []

/** Screens that hold answers: the checklist is one, each scene is one. */
const itemSteps = (session: BankSession) =>
  session.kind === "checklist" ? 1 : session.items.length

/** The screen « Terminer » sits on. A session with closing paragraphs (S1, S5)
 *  ends on a screen of its own for them; the others end on their last item.
 *  The billet de sortie that used to close every session is gone (PM ruling
 *  2026-09-15 — it dated from when a counselor filled the cahier in). */
const lastStepOf = (session: BankSession) =>
  session.outro.length > 0 ? itemSteps(session) : itemSteps(session) - 1

/** The step to land on when resuming: the first item with no answer, or the
 *  last screen when every item is answered. R11: a completed session always
 *  resumes at step 0 instead — reopening one shows its rows/scenes read-only
 *  first rather than jumping straight to the end. */
function resumeStep(
  session: BankSession,
  answers: Record<string, VoyageAnswer>,
  done: boolean,
): number {
  if (done) return 0
  if (session.kind === "checklist") {
    return session.items.every((it) => answers[it.id] !== undefined) ? lastStepOf(session) : 0
  }
  const idx = session.items.findIndex((it) => asLetters(answers[it.id]).length === 0)
  return idx === -1 ? lastStepOf(session) : idx
}

export default function SessionPlayerPage() {
  const { n } = useParams<{ n: string }>()
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()

  const [session, setSession] = useState<BankSession | null>(null)
  const [voyage, setVoyage] = useState<Voyage | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [answers, setAnswers] = useState<Record<string, VoyageAnswer>>({})
  const [step, setStep] = useState(0)
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  // Action-level errors: a missing answer, a failed save, a failed
  // completion. Kept separate from loadError below so the two screens never
  // overwrite each other's message.
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)

  // R9: a failed read is never treated as "no session" / "no voyage" — it
  // renders an Alert plus a "Réessayer" that re-runs the loader, and nothing
  // else below it (house pattern: frontend/src/app/voyage/page.tsx).
  const [loadError, setLoadError] = useState<string | null>(null)
  // F1 (hub pattern): a loadError retry in flight — disables the button and
  // swaps its label, and a second click cannot start a parallel load.
  const [reloading, setReloading] = useState(false)

  // One promise chain for every write, so two rapid toggles of the same item
  // cannot land out of order. Each link swallows its own rejection — a single
  // failure must not poison the chain for the rest of the session — and
  // reports success as a boolean, because the caller has to know whether it is
  // allowed to advance.
  const chain = useRef<Promise<unknown>>(Promise.resolve())
  // The most recent save rejection, kept alongside the boolean `save`
  // resolves with — state (`error`) is not safe to read back synchronously
  // right after an await in the same closure, so `finish` below reads this
  // ref instead of the `error` state to recognise the one 409 it must route
  // on rather than just display.
  const lastSaveErrorRef = useRef<ApiError | null>(null)
  const save = useCallback((patch: Partial<VoyageResponses>): Promise<boolean> => {
    const next = chain.current
      .then(() => putResponses(patch))
      .then(() => { setError(null); lastSaveErrorRef.current = null; return true })
      .catch((e: unknown) => {
        lastSaveErrorRef.current = e instanceof ApiError ? e : null
        setError(e instanceof ApiError
          ? e.message
          : "Enregistrement impossible. Vérifiez votre connexion.")
        return false
      })
    chain.current = next
    return next
  }, [])

  // The proxy gates the route on cookie *presence*, which misses an expired
  // token. Without this, an expired session renders the player and only
  // fails at the first save. Same guard as frontend/src/app/voyage/page.tsx.
  useEffect(() => {
    if (!authLoading && !user) router.replace(`/connexion?redirect=/voyage/session/${n}`)
  }, [authLoading, user, router, n])

  // The loader: bank + voyage + responses + profile. R9: getResponses 404
  // means "no voyage" — folded into an empty responses object here so the
  // no-voyage screen renders below, never the load-error screen; any other
  // rejection (from any of the four calls) is a real load error. Reused by
  // the mount effect below and the loadError "Réessayer" button.
  const load = useCallback(() => {
    return Promise.all([
      getBank(),
      getVoyage(),
      getResponses().catch((e: unknown): VoyageResponses => {
        if (e instanceof ApiError && e.status === 404) return { answers: {} }
        throw e
      }),
      api.get<{ profile: Profile | null }>("/profile", { skipRedirect: true }).then((r) => r.profile),
    ])
      .then(([bank, v, r, p]) => {
        setLoadError(null)
        const s = bank.sessions.find((x) => x.n === n) ?? null
        setNotFound(!s)
        if (!s) return
        setSession(s)
        setVoyage(v)
        setProfile(p)
        setAnswers(r.answers)
        const isDone = v ? (v.sessions_completed as string[]).includes(s.n) : false
        setStep(resumeStep(s, r.answers, isDone))
      })
      .catch((e) => {
        setLoadError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      })
      .finally(() => {
        setLoaded(true)
      })
  }, [n])

  // R15: the loader waits for auth — it never fires while a token is still
  // being checked or has come back empty (that case is the redirect above).
  useEffect(() => {
    if (authLoading || !user) return
    load()
  }, [authLoading, user, load])

  // F1 (hub pattern): wraps load() for the loadError "Réessayer" button —
  // disables the button and swaps its label while a retry is in flight, and
  // a second click cannot start a parallel load.
  const retryLoad = useCallback(() => {
    if (reloading) return
    setReloading(true)
    load().finally(() => setReloading(false))
  }, [load, reloading])

  const scenes = useMemo(() => (session ? session.items.filter(isScene) : []), [session])
  const rows = useMemo(
    () => (session
      ? session.items.filter((it): it is BankChecklistItem => !isScene(it))
      : []),
    [session],
  )
  const neutralCount = useMemo(
    () => rows.filter((it) => answers[it.id] === NEUTRAL).length,
    [rows, answers],
  )

  const done = session && voyage
    ? (voyage.sessions_completed as string[]).includes(session.n)
    : false
  // R12: the same exemption SessionProgress uses — a completed session is
  // never shown a lock screen, so "Revoir mes réponses" can never dead-end.
  const lock = session ? (done ? null : sessionLock(voyage, profile, session.n)) : null
  const lastStep = session ? lastStepOf(session) : 0
  const onOutro = session ? session.outro.length > 0 && step === itemSteps(session) : false
  const onLast = step >= lastStep

  const setAnswer = useCallback((id: string, value: VoyageAnswer) => {
    setAnswers((prev) => ({ ...prev, [id]: value }))
  }, [])

  /** Session 0 only: persist the row the moment it is toggled, so a dropped
   *  connection costs one affirmation and not the whole twenty-row screen.
   *  R13: a completed session is read-only — guarded here too, not only by
   *  the row's own `disabled` prop, so nothing can write through it.
   *
   *  ALSO frozen by `busy`, via ChecklistRow's `disabled={done || busy}`
   *  below (K6): the one moment `busy` is true while these rows are still on
   *  screen is `saveCurrent()`'s reconcile save, which resends every row's
   *  current answer once all twenty are filled in. A toggle made during that
   *  window races the reconcile's own patch — if the toggle's own save then
   *  fails, the row is left scored at the old value on the server even though
   *  the screen already shows the new one. Freezing the rows for that single
   *  round trip closes the window; a row's own toggle is still its own save
   *  the rest of the time (chained through `save` above, so two rapid
   *  toggles of the same row still land in click order). */
  const toggleRow = useCallback((id: string, value: ChecklistAnswer) => {
    if (done) return
    setAnswer(id, value)
    void save({ answers: { [id]: value } })
  }, [done, save, setAnswer])

  /** Save the screen on show, with the checks that gate leaving it. Resolves
   *  false when an answer is missing or the write failed — the caller must
   *  not move on. The closing screen holds no answer, so it saves nothing.
   *  Used by « Suivant » and by « Terminer » alike: the last item is saved by
   *  whichever of the two leaves it. */
  const saveCurrent = useCallback(async (): Promise<boolean> => {
    if (!session) return false
    if (session.kind === "checklist") {
      if (step !== 0) return true
      // R14: block before any write — no save while rows are unanswered.
      const missing = session.items.filter((it) => answers[it.id] === undefined)
      if (missing.length > 0) {
        setError(missing.length === 1
          ? "1 affirmation sans réponse."
          : `${missing.length} affirmations sans réponse.`)
        document.getElementById(`item-${missing[0].id}`)
          ?.scrollIntoView({ behavior: "smooth", block: "center" })
        return false
      }
      // Reconcile the whole screen: individual rows were already sent, this
      // catches anything a failed per-row write left behind.
      const patch: Record<string, VoyageAnswer> = {}
      for (const it of session.items) patch[it.id] = answers[it.id]
      return save({ answers: patch })
    }
    const item = session.items[step]
    if (!item) return true
    if (asLetters(answers[item.id]).length === 0) {
      setError("Choisissez une réponse pour continuer.")
      return false
    }
    return save({ answers: { [item.id]: answers[item.id] } })
  }, [answers, save, session, step])

  const next = useCallback(async () => {
    if (!session) return
    setError(null)
    // R13: a completed session advances without saving — re-answering a
    // scored session after completion would silently change a scoring the
    // counselor may already have restituted.
    if (done) {
      setStep((s) => Math.min(s + 1, lastStep))
      window.scrollTo({ top: 0, behavior: "smooth" })
      return
    }
    setBusy(true)
    try {
      // A failed write must not advance: the promise is « a dropped connection
      // loses one scene, not a session », and advancing would lose this one.
      if (!(await saveCurrent())) return
      setStep((s) => Math.min(s + 1, lastStep))
      window.scrollTo({ top: 0, behavior: "smooth" })
    } finally {
      setBusy(false)
    }
  }, [done, lastStep, saveCurrent, session])

  const back = useCallback(() => {
    setError(null)
    setStep((s) => Math.max(0, s - 1))
    window.scrollTo({ top: 0, behavior: "smooth" })
  }, [])

  const finish = useCallback(async () => {
    if (!session) return
    setBusy(true)
    setError(null)
    lastSaveErrorRef.current = null
    // saveCurrent() swallows its own rejection and reports a boolean, so the
    // last write is checked here rather than by the try/catch below.
    const saved = await saveCurrent()
    if (!saved) {
      // Same dead end as the completeSession 409 below, reached from the
      // save instead: the session was completed in another tab between
      // opening this screen and pressing "Terminer". Any other refusal (a
      // missing answer, the network, …) keeps its message on screen.
      // Read through a cast: TypeScript still narrows the ref to the null
      // assigned above, unaware that the await wrote to it.
      const failure = lastSaveErrorRef.current as ApiError | null
      if (failure?.status === 409 && failure.message === SESSION_CLOSED) {
        router.push("/voyage")
        return
      }
      setBusy(false)
      return
    }
    try {
      await completeSession(session.n)
      router.push("/voyage")
    } catch (e) {
      // R7 client: completed in another tab — go back rather than show a
      // dead end on a session that no longer needs finishing.
      if (e instanceof ApiError && e.status === 409
        && e.message === "Cette session est déjà terminée.") {
        router.push("/voyage")
        return
      }
      const missing = missingItems(e)
      setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      if (missing.length > 0 && session.kind !== "checklist") {
        const idx = session.items.findIndex((it) => it.id === missing[0])
        if (idx >= 0) setStep(idx)
      } else if (missing.length > 0) {
        setStep(0)
        window.setTimeout(() => {
          document.getElementById(`item-${missing[0]}`)
            ?.scrollIntoView({ behavior: "smooth", block: "center" })
        }, 100)
      }
      setBusy(false)
    }
  }, [router, saveCurrent, session])

  if (authLoading || !user || !loaded) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="mx-auto max-w-2xl px-4 py-8">
          <Skeleton className="h-9 w-56" />
          <Skeleton className="mt-6 h-72 rounded-2xl" />
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="voyage-rule" role="presentation" aria-hidden />
        <div className="mx-auto max-w-2xl px-4 py-8">
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{loadError}</AlertDescription>
          </Alert>
          <Button size="lg" onClick={retryLoad} disabled={reloading}>
            {reloading ? "Chargement…" : "Réessayer"}
          </Button>
        </div>
      </div>
    )
  }

  if (notFound || !session) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="voyage-rule" role="presentation" aria-hidden />
        <div className="mx-auto max-w-2xl px-4 py-16 text-center">
          <p className="font-display text-lg font-bold text-navy">Session inconnue.</p>
          <Button render={<Link href="/voyage" />} size="lg" className="mt-4">
            Retour au voyage
          </Button>
        </div>
      </div>
    )
  }

  if (!voyage) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="voyage-rule" role="presentation" aria-hidden />
        <div className="mx-auto max-w-2xl px-4 py-16 text-center">
          <p className="font-display text-lg font-bold text-navy">
            Vous n&apos;avez pas encore commencé le voyage.
          </p>
          <Button render={<Link href="/voyage" />} size="lg" className="mt-4">
            Aller au voyage
          </Button>
        </div>
      </div>
    )
  }

  if (lock) {
    // Spec § Frontend: the remedy depends on the reason, not a blanket "back"
    // button — LOCK_ORDER (the fallback below) is the only one that actually
    // means "go back to the voyage"; the other two point at where to fix it.
    // The two profile blocks asked inside the voyage have a step of their own;
    // it is a better remedy than /profil, which would ask for all six.
    const step = stepForLock(lock)
    const remedy = step
      ? { href: `/voyage/etape/${step}`, label: "Répondre maintenant" }
      : lock === LOCK_CODE
        ? { href: "/voyage", label: "Saisir mon code" }
        : lock === LOCK_PROFILE
          ? { href: "/profil", label: "Compléter mon profil" }
          : { href: "/voyage", label: "Retour au voyage" }
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="voyage-rule" role="presentation" aria-hidden />
        <div className="mx-auto max-w-2xl px-4 py-16 text-center">
          <span className="mx-auto grid size-12 place-items-center rounded-full bg-secondary text-muted-foreground">
            <Lock className="size-5" aria-hidden />
          </span>
          <p className="mt-4 font-display text-lg font-bold text-navy">{lock}</p>
          {/* Restores the spec's first sentence only — the second half
              ("Revenez au voyage pour voir ce qu'il manque.") assumed every
              remedy points back to /voyage, which is wrong once LOCK_PROFILE
              points to /profil instead. */}
          <p className="mt-2 text-sm text-muted-foreground">
            Cette session n&apos;est pas encore ouverte.
          </p>
          <Button render={<Link href={remedy.href} />} size="lg" className="mt-5">
            {remedy.label}
          </Button>
        </div>
      </div>
    )
  }

  const scene = session.kind === "scenes" && !onOutro ? scenes[step] : undefined
  const position = onOutro
    ? "Fin de session"
    : session.kind === "checklist"
      ? `${session.items.length} affirmations`
      : `Scène ${step + 1} sur ${scenes.length}`

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />
      <div className="voyage-rule" role="presentation" aria-hidden />

      <div className="mx-auto max-w-2xl px-4 py-8">
        <div className="mb-5">
          <Link
            href="/voyage"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            <ArrowLeft className="size-3.5" aria-hidden /> Le voyage
          </Link>
          <p className="eyebrow mt-3 text-orange-dark">Session {session.n}</p>
          <h1 className="mt-1 font-display text-2xl font-bold text-navy sm:text-3xl">
            {session.title}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">{session.subtitle}</p>
          <p className="mt-1.5 font-mono text-[11px] text-muted-foreground">
            {session.duration} · {position}
          </p>
        </div>

        {done && (
          <Alert className="mb-4">
            <AlertDescription>
              Session terminée. Vous pouvez la relire ; les réponses ne sont plus modifiables.
            </AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Session intro — first screen only */}
        {step === 0 && session.intro.length > 0 && (
          <div className="mb-5 space-y-2.5 rounded-2xl bg-card p-5 shadow-soft ring-1 ring-foreground/10">
            {session.intro.map((paragraph, i) => (
              <p key={i} className="text-sm leading-relaxed text-navy-700">{paragraph}</p>
            ))}
          </div>
        )}

        {/* ── Session 0: one scrolling list of 20 rows ─────────────────── */}
        {!onOutro && session.kind === "checklist" && (
          <div className="space-y-1.5">
            {/* Always mounted, so the live region exists before its first
                announcement; empty until the first « – ». */}
            <p aria-live="polite" className="text-right font-mono text-[11px] text-muted-foreground">
              {neutralCount === 0
                ? ""
                : neutralCount >= NEUTRAL_MAX && !done
                  ? `${NEUTRAL_MAX} réponses neutres maximum : retirez-en une pour en choisir une autre.`
                  : `Neutre : ${neutralCount} sur ${NEUTRAL_MAX}`}
            </p>
            {rows.map((item, i) => (
              <div key={item.id} id={`item-${item.id}`}>
                <ChecklistRow
                  n={i + 1}
                  text={item.text}
                  value={asMark(answers[item.id])}
                  disabled={done || busy}
                  neutralLocked={neutralCount >= NEUTRAL_MAX}
                  onChange={(v) => toggleRow(item.id, v)}
                />
              </div>
            ))}
          </div>
        )}

        {/* ── Sessions 1–5: one scene per screen ──────────────────────── */}
        {scene && (
          <div id={`item-${scene.id}`}>
            <SceneCard
              scene={scene}
              value={asLetters(answers[scene.id])}
              // Frozen while a save is in flight, not only once `done` —
              // without this a person can pick A, press « Suivant » or
              // « Terminer », then pick B before the save replies: the server
              // keeps A while the screen shows B. ChecklistRow does NOT get
              // the same freeze — see the comment on toggleRow above.
              disabled={done || busy}
              onChange={(letters) => setAnswer(scene.id, letters)}
            />
          </div>
        )}

        {/* ── Closing screen: the session's own last paragraphs (S1, S5) ── */}
        {onOutro && (
          <div className="space-y-2.5 rounded-2xl bg-card p-5 shadow-soft ring-1 ring-foreground/10">
            {session.outro.map((paragraph, i) => (
              <p key={i} className="text-sm leading-relaxed text-navy-700">{paragraph}</p>
            ))}
          </div>
        )}

        {/* ── Navigation ───────────────────────────────────────────────── */}
        <div className="mt-6 flex items-center justify-between gap-3">
          <Button variant="outline" size="lg" onClick={back} disabled={step === 0 || busy}>
            <ArrowLeft className="size-4" /> Précédent
          </Button>

          {!onLast ? (
            <Button size="lg" onClick={next} disabled={busy}>
              {busy ? "Enregistrement…" : "Suivant"} <ArrowRight className="size-4" />
            </Button>
          ) : done ? (
            <Button render={<Link href="/voyage" />} size="lg">
              Retour au voyage <ArrowRight className="size-4" />
            </Button>
          ) : (
            <Button size="lg" onClick={finish} disabled={busy}>
              {busy ? "Enregistrement…" : "Terminer"} <Check className="size-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
