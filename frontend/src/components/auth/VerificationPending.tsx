"use client"

import { useState } from "react"
import { api, ApiError } from "@/lib/api"
import { useCooldown } from "@/lib/useCooldown"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

interface Props {
  email: string
  /** Where the link should land once confirmed, when the page knows. Passed to
   *  the server as given — never decoded or rebuilt here. */
  next?: string | null
  /** "sent": a link just left (signup, demande). "login": the account exists
   *  unconfirmed and nothing was sent this time. */
  variant?: "sent" | "login"
  /** False when the server could not hand the first mail to the provider. */
  mailSent?: boolean
  onRestart?: () => void
  restartLabel?: string
}

export function VerificationPending({
  email,
  next,
  variant = "sent",
  mailSent = true,
  onRestart,
  restartLabel = "Mauvaise adresse ? Recommencer",
}: Props) {
  const justSent = variant === "sent" && mailSent
  const { wait, restart } = useCooldown(justSent)
  const [failed, setFailed] = useState(variant === "sent" && !mailSent)
  const [notice, setNotice] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  const resend = async () => {
    setSending(true)
    setNotice(null)
    try {
      const res = await api.post<{ message?: string }>(
        "/auth/resend-verification", { email, next: next ?? undefined }, { skipRedirect: true },
      )
      setFailed(false)
      // The server's own sentence rather than a claim of ours: its 200 is the
      // same whether or not a mail left (the one-a-minute cooldown, a refused
      // send, an address with nothing to confirm), so how sure to sound is
      // the server's call, not this screen's.
      setNotice(`${res?.message ?? "Demande prise en compte."} Pensez à regarder dans les courriers indésirables.`)
      restart()
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : "Erreur lors de l’envoi.")
    } finally {
      setSending(false)
    }
  }

  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-navy">
        {variant === "sent" ? "Vérifiez votre boîte mail" : "Confirmez votre adresse"}
      </h1>
      {variant === "sent" ? (
        <p className="mt-3 text-sm text-muted-foreground">
          Un lien de confirmation a été envoyé à <strong className="text-navy">{email}</strong>.
          Ouvrez-le dans les 48 heures et saisissez votre mot de passe : votre compte sera activé.
        </p>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          Votre compte n’est pas encore activé. Ouvrez le lien envoyé à{" "}
          <strong className="text-navy">{email}</strong> lors de l’inscription, ou demandez-en un nouveau.
        </p>
      )}

      {failed && (
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>L’envoi a échoué. Réessayez dans un instant.</AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert className="mt-4">
          <AlertDescription className="text-sm text-foreground">{notice}</AlertDescription>
        </Alert>
      )}

      <Button
        type="button"
        variant="outline"
        className="mt-6 h-11 w-full"
        disabled={wait > 0 || sending}
        onClick={resend}
      >
        {sending ? "Envoi…" : wait > 0 ? `Renvoyer le lien (${wait} s)` : "Renvoyer le lien"}
      </Button>

      {onRestart && (
        <button
          type="button"
          onClick={onRestart}
          className="link-underline mt-4 block w-full text-center text-sm font-medium text-orange-dark"
        >
          {restartLabel}
        </button>
      )}
    </div>
  )
}
