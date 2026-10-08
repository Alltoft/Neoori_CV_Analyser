"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Controller, useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useAuth } from "@/lib/auth"
import { homeFor } from "@/lib/home"
import { api, ApiError } from "@/lib/api"
import { TRANCHES_AGE } from "@/lib/profile-options"
import type { User } from "@/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"

/** profiles.prenom's width (PRENOM_MAX_LENGTH on the server). */
const PRENOM_MAX = 120

const schema = z.object({
  prenom: z.string().trim().min(1, "Prénom requis.").max(PRENOM_MAX, `${PRENOM_MAX} caractères maximum.`),
  tranche_age: z.string().min(1, "Tranche d'âge requise."),
  consent: z.boolean().refine((v) => v === true, {
    message: "Veuillez accepter les CGV et la politique de confidentialité.",
  }),
})
type Fields = z.infer<typeof schema>

type Ticket =
  | { kind: "loading" }
  | { kind: "ready"; email: string }
  | { kind: "expired" }
  | { kind: "unchecked"; message: string }

/** The last step of a signup by Google, Microsoft or the email link. The
 *  address is already proven, so only the prénom, the age bracket and the
 *  consent are asked; the account is created on submit, not before (social
 *  sign-in spec, decisions 1 and 22). */
export default function FinaliserPage() {
  const router = useRouter()
  const { refresh } = useAuth()
  const [ticket, setTicket] = useState<Ticket>({ kind: "loading" })
  const [attempt, setAttempt] = useState(0)
  const [error, setError] = useState<string | null>(null)
  // Set once the account exists: the button stays disabled while the navigation runs, after isSubmitting has gone false.
  const [leaving, setLeaving] = useState(false)

  const { register, control, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { prenom: "", tranche_age: "", consent: false },
  })

  useEffect(() => {
    let live = true
    api.get<{ email: string; prenom: string }>("/auth/signup", { skipRedirect: true })
      .then((t) => {
        if (!live) return
        reset({ prenom: t.prenom, tranche_age: "", consent: false })
        setTicket({ kind: "ready", email: t.email })
      })
      .catch((e) => {
        if (!live) return
        const code = e instanceof ApiError ? e.body?.code : undefined
        if (typeof code === "string" && code.startsWith("link_")) setTicket({ kind: "expired" })
        else setTicket({ kind: "unchecked", message: e instanceof ApiError ? e.message : "Chargement impossible pour le moment." })
      })
    return () => { live = false }
  }, [attempt, reset])

  const onSubmit = async (fields: Fields) => {
    setError(null)
    try {
      const res = await api.post<{ user: User; next: string | null }>("/auth/signup", fields, { skipRedirect: true })
      await refresh()
      setLeaving(true)
      router.replace(res.next ?? homeFor(res.user.role))
    } catch (e) {
      const code = e instanceof ApiError ? e.body?.code : undefined
      if (typeof code === "string" && code.startsWith("link_")) setTicket({ kind: "expired" })
      else setError(e instanceof ApiError ? e.message : "Erreur lors de la création du compte.")
    }
  }

  if (ticket.kind === "loading") {
    return <AuthLayout><p className="text-sm text-muted-foreground">Chargement…</p></AuthLayout>
  }

  if (ticket.kind === "unchecked") {
    return (
      <AuthLayout>
        <h1 className="font-display text-2xl font-bold text-navy">Finaliser votre inscription</h1>
        <Alert variant="destructive" className="mt-6"><AlertDescription>{ticket.message}</AlertDescription></Alert>
        <Button type="button" size="lg" className="mt-6 h-11 w-full"
          onClick={() => { setTicket({ kind: "loading" }); setAttempt((n) => n + 1) }}>
          Réessayer
        </Button>
      </AuthLayout>
    )
  }

  if (ticket.kind === "expired") {
    return (
      <AuthLayout>
        <h1 className="font-display text-2xl font-bold text-navy">Finaliser votre inscription</h1>
        <Alert variant="destructive" className="mt-6">
          <AlertDescription>Cette étape a expiré. Recommencez depuis la page d’inscription.</AlertDescription>
        </Alert>
        <p className="mt-5 text-center text-sm text-muted-foreground">
          <Link href="/inscription" className="link-underline font-medium text-orange-dark">Retour à l’inscription</Link>
        </p>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-bold text-navy">Finaliser votre inscription</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Dernière étape : ces informations servent à personnaliser vos analyses.
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
        {error && (
          <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="username" className="h-10" value={ticket.email} readOnly />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="prenom">Prénom</Label>
            <Input id="prenom" autoComplete="given-name" className="h-10" placeholder="Marie" {...register("prenom")} />
            {errors.prenom && <p className="text-xs text-destructive">{errors.prenom.message}</p>}
          </div>

          <div className="space-y-1.5">
            <Label>Tranche d&apos;âge</Label>
            <Controller
              name="tranche_age"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger className="h-10 w-full"><SelectValue placeholder="Choisir…" /></SelectTrigger>
                  <SelectContent>
                    {TRANCHES_AGE.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.tranche_age && <p className="text-xs text-destructive">{errors.tranche_age.message}</p>}
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="flex items-start gap-2.5 text-xs leading-relaxed text-muted-foreground">
            <input
              type="checkbox"
              className="mt-0.5 size-4 shrink-0 rounded border-input accent-[var(--primary)]"
              {...register("consent")}
            />
            <span>
              J’accepte les{" "}
              <Link href="/cgv" target="_blank" className="text-navy underline underline-offset-2">CGV</Link>{" "}
              et la{" "}
              <Link href="/confidentialite" target="_blank" className="text-navy underline underline-offset-2">politique de confidentialité</Link>.
            </span>
          </label>
          {errors.consent && <p className="text-xs text-destructive">{errors.consent.message}</p>}
        </div>

        <Button type="submit" size="lg" className="h-11 w-full" disabled={isSubmitting || leaving}>
          {isSubmitting || leaving ? "Création…" : "Créer mon compte"}
        </Button>
      </form>
    </AuthLayout>
  )
}
