"use client"

import { Suspense, useEffect, useState, type FormEvent } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { useAuth } from "@/lib/auth"
import { homeFor } from "@/lib/home"
import { useSite } from "@/lib/site-context"
import { api, ApiError } from "@/lib/api"
import type { User } from "@/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"

const INVALID = "Ce lien n’est pas valide. Demandez-en un nouveau."

type LinkState =
  | { kind: "checking" }
  | { kind: "ready"; email: string }
  | { kind: "dead"; message: string }
  /** The check itself failed (429, a 5xx while the backend restarts, the
   *  network): nothing is known about the link, so it is not called dead. */
  | { kind: "unchecked"; message: string }

/** The link plus the password chosen at signup: that pair, not the link
 *  alone, opens the account (spec decision 8 — pre-account hijacking). */
function VerifierEmail() {
  const params = useSearchParams()
  const { app, go } = useSite()
  const { refresh } = useAuth()
  const token = params.get("token") ?? ""
  const [state, setState] = useState<LinkState>(() =>
    token ? { kind: "checking" } : { kind: "dead", message: INVALID },
  )
  const [attempt, setAttempt] = useState(0)
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [resendEmail, setResendEmail] = useState("")
  const [resent, setResent] = useState<string | null>(null)
  const [resendError, setResendError] = useState<string | null>(null)
  const [resending, setResending] = useState(false)

  useEffect(() => {
    if (!token) return
    let live = true
    // skipRedirect on every call here: a 401 must reach this page, not send
    // the person to /connexion.
    api.post<{ email: string }>("/auth/verify-email/check", { token }, { skipRedirect: true })
      .then((r) => { if (live) setState({ kind: "ready", email: r.email }) })
      .catch((e) => {
        if (!live) return
        // Only the server's own verdict on the link (400 link_expired /
        // link_invalid) makes it dead. Anything else says nothing about it.
        const code = e instanceof ApiError ? e.body?.code : undefined
        if (e instanceof ApiError && e.status === 400 && typeof code === "string" && code.startsWith("link_")) {
          setState({ kind: "dead", message: e.message })
        } else {
          setState({
            kind: "unchecked",
            message: e instanceof ApiError ? e.message : "Vérification du lien impossible pour le moment.",
          })
        }
      })
    return () => { live = false }
  }, [token, attempt])

  const recheck = () => {
    setState({ kind: "checking" })
    setAttempt((n) => n + 1)
  }

  const confirm = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      // The password goes as typed: never trimmed, so one with surrounding
      // spaces still matches the one chosen at signup.
      const res = await api.post<{ user: User; next: string | null }>(
        "/auth/verify-email", { token, password }, { skipRedirect: true },
      )
      await refresh()
      // `next` is the landing path the server signed into the link, followed
      // exactly as given. replace, not push: Back must not reopen the spent
      // link. The button stays disabled until this page unmounts.
      go(res.next ?? homeFor(res.user.role, app), { replace: true })
    } catch (err) {
      const code = err instanceof ApiError ? err.body?.code : undefined
      if (code === "wrong_password") setError("Mot de passe incorrect.")
      else if (code === "link_expired" || code === "link_invalid") setState({ kind: "dead", message: (err as ApiError).message })
      else setError(err instanceof ApiError ? err.message : "Erreur inattendue.")
      setSubmitting(false)
    }
  }

  const resend = async (e: FormEvent) => {
    e.preventDefault()
    setResendError(null)
    setResending(true)
    try {
      const res = await api.post<{ message?: string }>(
        "/auth/resend-verification", { email: resendEmail }, { skipRedirect: true },
      )
      // The server's sentence, worded to hold whether or not a mail left.
      setResent(res?.message ?? "Demande prise en compte.")
    } catch (err) {
      // The server answers the same sentence whatever the address, so a
      // failure here is the network or the rate limit: say so rather than
      // claim a mail left.
      setResendError(err instanceof ApiError ? err.message : "Erreur lors de l’envoi.")
    } finally {
      setResending(false)
    }
  }

  if (state.kind === "checking") {
    return <p className="text-sm text-muted-foreground">Vérification du lien…</p>
  }

  if (state.kind === "unchecked") {
    return (
      <>
        <h1 className="font-display text-2xl font-bold text-navy">Confirmez votre adresse</h1>
        <Alert variant="destructive" className="mt-6"><AlertDescription>{state.message}</AlertDescription></Alert>
        <Button type="button" size="lg" className="mt-6 h-11 w-full" onClick={recheck}>
          Réessayer
        </Button>
      </>
    )
  }

  if (state.kind === "dead") {
    return (
      <>
        <h1 className="font-display text-2xl font-bold text-navy">Lien expiré ou invalide</h1>
        <Alert variant="destructive" className="mt-6"><AlertDescription>{state.message}</AlertDescription></Alert>
        {resent ? (
          <Alert className="mt-6">
            <AlertDescription className="text-sm text-foreground">{resent}</AlertDescription>
          </Alert>
        ) : (
          <form onSubmit={resend} className="mt-6 space-y-4">
            {resendError && (
              <Alert variant="destructive"><AlertDescription>{resendError}</AlertDescription></Alert>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="resend-email">Email du compte</Label>
              <Input id="resend-email" type="email" autoComplete="email" className="h-10" required
                value={resendEmail} onChange={(e) => setResendEmail(e.target.value)} />
            </div>
            <Button type="submit" size="lg" className="h-11 w-full" disabled={resending}>
              {resending ? "Envoi…" : "Recevoir un nouveau lien"}
            </Button>
          </form>
        )}
        <p className="mt-5 text-center text-sm text-muted-foreground">
          <Link href="/connexion" className="link-underline font-medium text-orange-dark">Retour à la connexion</Link>
        </p>
      </>
    )
  }

  return (
    <>
      <h1 className="font-display text-2xl font-bold text-navy">Confirmez votre adresse</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Saisissez le mot de passe choisi à l’inscription pour activer votre compte.
      </p>
      <form onSubmit={confirm} className="mt-7 space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>
              {error}{" "}
              <Link href="/mot-de-passe-oublie" className="underline underline-offset-2">Mot de passe oublié ?</Link>
            </AlertDescription>
          </Alert>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="username" className="h-10" value={state.email} readOnly />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Mot de passe</Label>
          <Input id="password" type="password" autoComplete="current-password" className="h-10" required
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <Button type="submit" size="lg" className="h-11 w-full" disabled={submitting || !password}>
          {submitting ? "Activation…" : "Activer mon compte"}
        </Button>
      </form>
    </>
  )
}

export default function VerifierEmailPage() {
  return (
    <AuthLayout>
      <Suspense>
        <VerifierEmail />
      </Suspense>
    </AuthLayout>
  )
}
