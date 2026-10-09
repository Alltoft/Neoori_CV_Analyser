"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Check, Link2, Printer, Trash2 } from "lucide-react"
import { AppBar } from "@/components/layout/AppBar"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { RunProgress } from "@/components/analyse/RunProgress"
import { ReportDocument, isPaidReport } from "@/components/report/ReportDocument"
import { PriceProbe } from "@/components/report/PriceProbe"
import { ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { held, tokenFromHash } from "@/lib/held"
import { copyToClipboard, parseUtc } from "@/lib/utils"
import type { Analysis } from "@/types"

type State = "loading" | "running" | "ready" | "gone" | "deleted" | "failed"

/** A no-login report, opened by the key in its URL fragment (four-doors spec,
 *  decisions 30-32). Client-only: see app/rapport/page.tsx. */
export default function RapportSansCompte() {
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()
  const [token] = useState<string | null>(() => tokenFromHash())
  const [state, setState] = useState<State>(() => (token ? "loading" : "gone"))
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  // Bumped by « Réessayer »: the loading effect depends on it.
  const [attempt, setAttempt] = useState(0)
  const [copied, setCopied] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    let alive = true
    held.byToken(token)
      .then((r) => {
        if (!alive) return
        setAnalysis(r.analysis)
        setState(r.analysis.status === "success" ? "ready" : "running")
      })
      .catch((e) => {
        if (!alive) return
        // Only a 404 means the link is gone. The fragment is the person's one
        // key to this report: a 502, a 429 or a dropped connection must not
        // tell them it is dead, or they may throw it away.
        if (e instanceof ApiError && e.status === 404) {
          setState("gone")
          return
        }
        setLoadError(e instanceof ApiError ? e.message : "Erreur inattendue.")
        setState("failed")
      })
    return () => { alive = false }
  }, [token, attempt])

  // The fragment is the key. A link pasted over this one in the address bar is a
  // hashchange, not a page load: without this the page would keep showing the
  // old report beside a URL that is no longer its own (and « Supprimer » would
  // delete the old one).
  useEffect(() => {
    const reload = () => window.location.reload()
    window.addEventListener("hashchange", reload)
    return () => window.removeEventListener("hashchange", reload)
  }, [])

  const retry = () => {
    setState("loading")
    setAttempt((n) => n + 1)
  }

  const copyLink = async () => {
    setCopied(await copyToClipboard(window.location.href))
    setTimeout(() => setCopied(false), 2500)
  }

  // « Créer un compte pour le garder »: hand the report to the hold cookie,
  // sign in, and /espace claims it (decision 32). Someone already signed in
  // has nothing to sign in to: straight to /espace, which claims it.
  const keep = async () => {
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      await held.hold(token)
      router.push(user ? "/espace?garder=1" : `/inscription?redirect=${encodeURIComponent("/espace?garder=1")}`)
    } catch (e) {
      setBusy(false)
      if (e instanceof ApiError && e.status === 404) setState("gone")
      else setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
    }
  }

  const remove = async () => {
    if (!token || !analysis) return
    setBusy(true)
    setError(null)
    try {
      await held.remove(analysis.id, token)
      setState("deleted")
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
    } finally {
      setBusy(false)
    }
  }

  if (state === "loading") return <div className="min-h-screen bg-secondary" />

  if (state === "gone" || state === "deleted" || state === "failed") {
    return (
      <div className="bg-mesh flex min-h-screen items-center justify-center px-5 py-12">
        <div className="w-full max-w-md text-center">
          <h1 className="font-display text-2xl font-bold text-navy">
            {state === "deleted" ? "Rapport supprimé." : state === "failed" ? loadError : "Ce lien n'est plus valide."}
          </h1>
          {state === "failed" ? (
            <Button onClick={retry} variant="outline" size="lg" className="mt-6">
              Réessayer
            </Button>
          ) : (
            <Button render={<Link href="/analyse/nouveau" />} variant="outline" size="lg" className="mt-6">
              Nouvelle analyse
            </Button>
          )}
        </div>
      </div>
    )
  }

  if (state === "running" && token) {
    return (
      <RunProgress
        load={() =>
          held.byToken(token).then(
            (r) => r.analysis,
            (e) => {
              // The link died while the run was being watched (the report was
              // deleted, or kept, from another tab): say so, instead of
              // polling a dead key.
              if (e instanceof ApiError && e.status === 404) setState("gone")
              throw e
            },
          )
        }
        onDone={(a) => { setAnalysis(a); setState("ready") }}
        mailed={false}
        onRestart={() => router.push("/analyse/nouveau")}
      />
    )
  }

  const expires = analysis?.access_expires_at ? parseUtc(analysis.access_expires_at) : null
  const until = expires && !Number.isNaN(expires.getTime())
    ? expires.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })
    : null
  const hasOutput = Object.keys(analysis?.output ?? {}).length > 0
  const isPaid = isPaidReport(analysis)

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />

      <div className="no-print border-b border-border bg-card px-4 py-3 text-center text-sm text-navy">
        {until && <p>{`Ce rapport n'est accessible que par ce lien, jusqu'au ${until}.`}</p>}
        {error && <Alert variant="destructive" className="mx-auto mt-2 max-w-md"><AlertDescription>{error}</AlertDescription></Alert>}
        <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
          <Button variant="outline" size="sm" onClick={copyLink}>
            {copied ? <Check className="size-3.5 text-success" /> : <Link2 className="size-3.5" />}
            {copied ? "Lien copié" : "Copier le lien"}
          </Button>
          {/* Disabled until auth has answered, so the label and the route it
              takes (sign-up or straight to /espace) are never the wrong ones. */}
          <Button size="sm" onClick={keep} disabled={busy || authLoading}>
            {user ? "Garder dans mon espace" : "Créer un compte pour le garder"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setTimeout(() => window.print(), 50)}>
            <Printer className="size-3.5" /> PDF
          </Button>
          {confirmDelete ? (
            <span className="inline-flex items-center gap-2">
              <span className="text-xs">Supprimer définitivement ce rapport ?</span>
              <Button variant="destructive" size="sm" onClick={remove} disabled={busy}>Supprimer</Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>Annuler</Button>
            </span>
          ) : (
            <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}>
              <Trash2 className="size-3.5" /> Supprimer ce rapport
            </Button>
          )}
        </div>
      </div>

      <div className="px-4 py-8">
        <ReportDocument analysis={analysis} loading={false} unlockHref={null}>
          {/* For a signed-out visitor only (not while auth loads either): the offer
              is an account, /inscription would let someone signed in open a second
              one, and « Garder dans mon espace » above is already theirs. */}
          {hasOutput && !isPaid && !authLoading && !user && (
            <div className="no-print mt-2 flex flex-col items-start justify-between gap-4 rounded-xl bg-brand-gradient p-5 text-white sm:flex-row sm:items-center">
              <p className="font-display font-bold">Créez un compte pour débloquer le rapport complet</p>
              <Button onClick={keep} disabled={busy} size="lg" className="shrink-0 bg-white text-orange-dark hover:bg-white/90">
                Créer un compte pour le garder
              </Button>
            </div>
          )}
          {hasOutput && !isPaid && analysis && token && <PriceProbe analysisId={analysis.id} token={token} />}
        </ReportDocument>
      </div>
    </div>
  )
}
