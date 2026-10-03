"use client"

import { useState, type FormEvent } from "react"
import { api, ApiError } from "@/lib/api"
import { useCooldown } from "@/lib/useCooldown"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"

interface Props {
  /** Where the link should land, when the page knows. Sent as given. */
  next?: string | null
  submitLabel?: string
}

/** « Recevoir un lien de connexion »: an address, then the sent state with
 *  « Renvoyer » on the server's one-a-minute clock (social sign-in spec,
 *  decision 14). The server sends whether or not the address has an
 *  account, so this screen can say plainly that a link left. */
export function EmailLinkForm({ next = null, submitLabel = "Envoyer le lien" }: Props) {
  const [email, setEmail] = useState("")
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const { wait, restart } = useCooldown(false)

  const send = async (to: string) => {
    setError(null)
    setSending(true)
    try {
      const res = await api.post<{ mail_sent: boolean }>(
        "/auth/email-link", { email: to, next: next ?? undefined }, { skipRedirect: true },
      )
      setSentTo(to)
      setFailed(!res.mail_sent)
      if (res.mail_sent) restart()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur lors de l’envoi.")
    } finally {
      setSending(false)
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    send(email.trim())
  }

  if (sentTo) {
    return (
      <div className="space-y-4">
        {failed ? (
          <Alert variant="destructive">
            <AlertDescription>L’envoi a échoué. Réessayez dans un instant.</AlertDescription>
          </Alert>
        ) : (
          <p className="text-sm text-muted-foreground">
            Un lien de connexion a été envoyé à <strong className="text-navy">{sentTo}</strong>.
            Il est valable 15 minutes. Pensez à regarder dans les courriers indésirables.
          </p>
        )}
        {error && (
          <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
        )}
        <Button
          type="button"
          variant="outline"
          className="h-11 w-full"
          disabled={wait > 0 || sending}
          onClick={() => send(sentTo)}
        >
          {sending ? "Envoi…" : wait > 0 ? `Renvoyer le lien (${wait} s)` : "Renvoyer le lien"}
        </Button>
        <button
          type="button"
          onClick={() => { setSentTo(null); setFailed(false); setError(null) }}
          className="link-underline block w-full text-center text-sm font-medium text-orange-dark"
        >
          Changer d’adresse
        </button>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      {error && (
        <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="link-email">Email</Label>
        <Input
          id="link-email" type="email" autoComplete="email" className="h-10"
          placeholder="vous@exemple.fr" required
          value={email} onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <Button type="submit" size="lg" className="h-11 w-full" disabled={sending}>
        {sending ? "Envoi…" : submitLabel}
      </Button>
    </form>
  )
}
