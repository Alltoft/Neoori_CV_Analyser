"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, Printer, RotateCcw, Trash2 } from "lucide-react"
import { AppBar } from "@/components/layout/AppBar"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { ReportDocument } from "@/components/report/ReportDocument"
import { ApiError } from "@/lib/api"
import { counselor } from "@/lib/counselor"
import { parseUtc } from "@/lib/utils"
import type { Analysis, AnalysisInputs } from "@/types"

const POLL_MS = 4000

/** An advisor-door report, on the counselor's page (four-doors spec,
 *  decisions 26-27): the full report, print, private notes, delete, and
 *  « Relancer » when the run failed. */
export default function ConseillerAnalysePage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [label, setLabel] = useState<string | null>(null)
  // True only once a fetch has answered 404. Any other failure is a retry.
  const [missing, setMissing] = useState(false)
  // The last non-404 failure of the report fetch, cleared by the next success.
  // Shown only while the page has no report yet (see the render below).
  const [loadError, setLoadError] = useState<string | null>(null)
  const [note, setNote] = useState("")
  // The note is editable only once it has been read: an empty box saved over a
  // note that failed to load would erase it.
  const [noteLoad, setNoteLoad] = useState<"loading" | "ready" | "failed">("loading")
  // Bumped by « Réessayer »: the note-loading effect depends on it.
  const [noteTry, setNoteTry] = useState(0)
  const [noteState, setNoteState] = useState<"idle" | "saving" | "saved" | "error">("idle")
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [relaunching, setRelaunching] = useState(false)
  // Bumped to restart polling after « Relancer ».
  const [round, setRound] = useState(0)

  // Polling lives inside the effect, with a cancel flag: a useCallback that
  // schedules itself trips react-hooks/immutability.
  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout> | null = null
    async function poll() {
      let wait = POLL_MS
      try {
        const r = await counselor.analysis(id)
        if (!alive) return
        setAnalysis(r.analysis)
        setLabel(r.code_label)
        setLoadError(null)
        if (r.analysis.status !== "queued" && r.analysis.status !== "running") return
      } catch (e) {
        if (!alive) return
        // Only a 404 means the report is gone. A 502, a 429 or a dropped
        // connection keeps what is on screen and tries again, more slowly: it
        // must not tell a counselor the report is gone, nor stop the watch of
        // a run that is still going.
        if (e instanceof ApiError && e.status === 404) {
          setMissing(true)
          return
        }
        setLoadError(e instanceof ApiError ? e.message : "Erreur inattendue.")
        wait = POLL_MS * 2
      }
      timer = setTimeout(poll, wait)
    }
    void poll()
    return () => { alive = false; if (timer) clearTimeout(timer) }
  }, [id, round])

  useEffect(() => {
    let alive = true
    counselor.note(id)
      .then((r) => { if (alive) { setNote(r.note); setNoteLoad("ready") } })
      .catch(() => { if (alive) setNoteLoad("failed") })
    return () => { alive = false }
  }, [id, noteTry])

  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : "Erreur inattendue.")

  const relaunch = async () => {
    setError(null)
    setRelaunching(true)
    try {
      const r = await counselor.relaunch(id)
      // The row is queued again: show it so, without waiting for the next poll.
      setAnalysis(r.analysis)
      setRound((n) => n + 1)
    } catch (e) {
      fail(e)
      // 409: the run was already relaunched (from another tab); look again.
      if (e instanceof ApiError && e.status === 409) setRound((n) => n + 1)
    } finally {
      setRelaunching(false)
    }
  }

  const retryNote = () => {
    setNoteLoad("loading")
    setNoteTry((n) => n + 1)
  }

  const saveNote = async () => {
    setNoteState("saving")
    try {
      await counselor.saveNote(id, note)
      // Typing while the save was in flight already set "idle": keep it.
      setNoteState((s) => (s === "saving" ? "saved" : s))
    } catch {
      setNoteState("error")
    }
  }

  const remove = async () => {
    setDeleting(true)
    try {
      await counselor.deleteAnalysis(id)
      // `deleting` stays set: the page is on its way out, and a second click
      // would only be a 404.
      router.push("/conseiller")
    } catch (e) {
      fail(e)
      setDeleting(false)
    }
  }

  // Not while a delete is leaving the page: the poll that fires meanwhile
  // would answer 404 for the report we have just deleted.
  if (missing && !deleting) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="mx-auto max-w-md py-24 text-center">
          <h1 className="font-display text-xl font-bold text-navy">Analyse introuvable.</h1>
          <Button render={<Link href="/conseiller" />} variant="outline" size="lg" className="mt-6">
            <ArrowLeft className="size-4" /> Mon espace conseiller
          </Button>
        </div>
      </div>
    )
  }

  const inputs: AnalysisInputs = analysis?.inputs ?? {}
  const who = [inputs.prenom, (inputs.nom ?? "").toUpperCase()].filter(Boolean).join(" ")
  const created = analysis ? parseUtc(analysis.created_at) : null
  const date = created && !Number.isNaN(created.getTime())
    ? created.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })
    : ""
  const running = analysis?.status === "queued" || analysis?.status === "running"
  const failed = analysis?.status === "error" || analysis?.status === "timeout"

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />

      {/* top-20: the app bar is 5rem tall, so this sticks just under it. */}
      <div className="no-print sticky top-20 z-40 flex flex-wrap items-center justify-center gap-2 border-b border-border bg-secondary/95 py-3 backdrop-blur-sm">
        <Button render={<Link href="/conseiller" />} variant="ghost" size="sm">
          <ArrowLeft className="size-3.5" /> Mon espace conseiller
        </Button>
        <Button variant="outline" size="sm" disabled={!analysis || running || failed}
                onClick={() => setTimeout(() => window.print(), 50)}>
          <Printer className="size-3.5" /> PDF
        </Button>
        {failed && (
          <Button size="sm" onClick={relaunch} disabled={relaunching}>
            <RotateCcw className="size-3.5" /> Relancer
          </Button>
        )}
        {confirmDelete ? (
          <span className="inline-flex items-center gap-2">
            <span className="text-xs text-navy">Supprimer définitivement cette analyse ?</span>
            <Button variant="destructive" size="sm" onClick={remove} disabled={deleting}>Supprimer</Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)} disabled={deleting}>Annuler</Button>
          </span>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}>
            <Trash2 className="size-3.5" /> Supprimer l’analyse
          </Button>
        )}
      </div>

      <div className="mx-auto max-w-4xl px-4 py-6">
        <p className="no-print mb-4 text-sm font-medium text-navy">
          {[who || "—", label ? `code « ${label} »` : null, date].filter(Boolean).join(" · ")}
        </p>
        {error && <Alert variant="destructive" className="mb-4"><AlertDescription>{error}</AlertDescription></Alert>}
        {/* Nothing to keep on screen yet: say why, while the retry goes on. With
            a report showing, a failed poll stays silent and the page carries on. */}
        {loadError && !analysis && (
          <Alert variant="destructive" className="mb-4"><AlertDescription>{loadError}</AlertDescription></Alert>
        )}
        {running && (
          <Alert className="mb-4"><AlertDescription>Analyse en cours… La page se met à jour toute seule.</AlertDescription></Alert>
        )}
        {failed && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>L’analyse n’a pas abouti. Vous pouvez la relancer.</AlertDescription>
          </Alert>
        )}
        {analysis && !running && !failed && <ReportDocument analysis={analysis} loading={false} unlockHref={null} />}

        <section className="no-print mt-6 rounded-2xl bg-card p-5 ring-1 ring-foreground/10">
          <h2 id="notes-privees" className="font-display text-base font-semibold text-navy">Notes privées</h2>
          <p className="mt-1 text-xs text-muted-foreground">Visibles par vous seul.</p>
          <Textarea
            aria-labelledby="notes-privees"
            className="mt-3 min-h-32 bg-background text-sm"
            value={note}
            maxLength={20000}
            disabled={noteLoad !== "ready"}
            onChange={(e) => { setNote(e.target.value); setNoteState("idle") }}
          />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button size="sm" variant="navy" onClick={saveNote}
                    disabled={noteLoad !== "ready" || noteState === "saving"}>Enregistrer</Button>
            {noteLoad === "failed" && (
              <>
                <span className="text-xs text-destructive">Les notes n’ont pas pu être chargées.</span>
                <Button size="sm" variant="outline" onClick={retryNote}>Réessayer</Button>
              </>
            )}
            {noteState === "saved" && <span className="text-xs text-success">Enregistré.</span>}
            {noteState === "error" && <span className="text-xs text-destructive">Échec de l’enregistrement. Réessayez.</span>}
          </div>
        </section>
      </div>
    </div>
  )
}
