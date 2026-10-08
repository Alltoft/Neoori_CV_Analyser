"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { useAuth } from "@/lib/auth"
import { homeFor } from "@/lib/home"
import { api, ApiError } from "@/lib/api"
import type { User } from "@/types"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"
import { EmailLinkForm } from "@/components/auth/EmailLinkForm"

const INVALID = "Ce lien n’est pas valide. Demandez-en un nouveau."

type LinkState =
  | { kind: "checking" }
  | { kind: "ready"; email: string }
  | { kind: "dead"; message: string }
  /** The check itself failed (429, a 5xx, the network): nothing is known
   *  about the link, so it is not called dead. */
  | { kind: "unchecked"; message: string }

type Consumed = { user: User; next: string | null } | { signup: true }

/** Where « Recevoir un lien de connexion » lands. Opening the page spends
 *  nothing — mail scanners open links, and some run scripts. Only the click
 *  on « Continuer » uses the link (social sign-in spec, decision 16), and the
 *  address shown says whose account it opens. */
function ConnexionLien() {
  const params = useSearchParams()
  const router = useRouter()
  const { refresh } = useAuth()
  const token = params.get("token") ?? ""
  const [state, setState] = useState<LinkState>(() =>
    token ? { kind: "checking" } : { kind: "dead", message: INVALID },
  )
  const [attempt, setAttempt] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!token) return
    let live = true
    api.post<{ email: string }>("/auth/email-link/check", { token }, { skipRedirect: true })
      .then((r) => { if (live) setState({ kind: "ready", email: r.email }) })
      .catch((e) => {
        if (!live) return
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

  const proceed = async () => {
    setError(null)
    setSubmitting(true)
    try {
      const res = await api.post<Consumed>("/auth/email-link/consume", { token }, { skipRedirect: true })
      // replace, not push: Back must not reopen the spent link.
      if ("signup" in res) {
        router.replace("/inscription/finaliser")
        return
      }
      await refresh()
      router.replace(res.next ?? homeFor(res.user.role))
    } catch (err) {
      const code = err instanceof ApiError ? err.body?.code : undefined
      if (code === "link_expired" || code === "link_invalid") {
        setState({ kind: "dead", message: (err as ApiError).message })
      } else {
        setError(err instanceof ApiError ? err.message : "Erreur inattendue.")
      }
      setSubmitting(false)
    }
  }

  if (state.kind === "checking") {
    return <p className="text-sm text-muted-foreground">Vérification du lien…</p>
  }

  if (state.kind === "unchecked") {
    return (
      <>
        <h1 className="font-display text-2xl font-bold text-navy">Connexion</h1>
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
        <div className="mt-6">
          <EmailLinkForm submitLabel="Recevoir un nouveau lien" />
        </div>
        <p className="mt-5 text-center text-sm text-muted-foreground">
          <Link href="/connexion" className="link-underline font-medium text-orange-dark">Retour à la connexion</Link>
        </p>
      </>
    )
  }

  return (
    <>
      <h1 className="font-display text-2xl font-bold text-navy">Connexion</h1>
      <p className="mt-3 text-sm text-muted-foreground">
        Connexion avec <strong className="text-navy">{state.email}</strong>.
      </p>
      {error && (
        <Alert variant="destructive" className="mt-6"><AlertDescription>{error}</AlertDescription></Alert>
      )}
      <Button type="button" size="lg" className="mt-6 h-11 w-full" disabled={submitting} onClick={proceed}>
        {submitting ? "Connexion…" : "Continuer"}
      </Button>
      <p className="mt-4 text-center text-xs text-muted-foreground">
        Ce n’est pas votre adresse ? Fermez cette page.
      </p>
    </>
  )
}

export default function ConnexionLienPage() {
  return (
    <AuthLayout>
      <Suspense>
        <ConnexionLien />
      </Suspense>
    </AuthLayout>
  )
}
