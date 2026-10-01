"use client"

import { Suspense, useState } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { Controller, useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useAuth } from "@/lib/auth"
import { ApiError } from "@/lib/api"
import { safeRedirect } from "@/lib/safe-redirect"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"
import { VerificationPending } from "@/components/auth/VerificationPending"
import { TRANCHES_AGE } from "@/lib/profile-options"

// Prénom and tranche d'âge are asked here because session_lock has demanded
// them before session 1 since the voyage shipped. Asking mid-journey means
// bouncing someone out of the sessions and into a form; this is the one moment
// they are already filling one.
const schema = z
  .object({
    prenom: z.string().min(1, "Prénom requis."),
    tranche_age: z.string().min(1, "Tranche d'âge requise."),
    email: z.string().email("Email invalide."),
    password: z.string().min(8, "8 caractères minimum."),
    confirm: z.string(),
    consent: z.boolean().refine((v) => v === true, {
      message: "Veuillez accepter les CGV et la politique de confidentialité.",
    }),
  })
  .refine((d) => d.password === d.confirm, {
    message: "Les mots de passe ne correspondent pas.",
    path: ["confirm"],
  })
type Fields = z.infer<typeof schema>

function InscriptionForm() {
  const { register: registerUser } = useAuth()
  const params = useSearchParams()
  // Where they were heading (the proxy sends /analyse/* here). It travels in
  // the confirmation link, so the email round-trip lands them back on it.
  // Checked as given by safeRedirect; an unusable value is simply no redirect.
  const next = safeRedirect(params.get("redirect"))
  const [error, setError] = useState<string | null>(null)
  const [taken, setTaken] = useState(false)
  const [pending, setPending] = useState<{ email: string; mailSent: boolean } | null>(null)

  const { register, control, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { consent: false, prenom: "", tranche_age: "" },
  })

  const onSubmit = async ({ email, password, prenom, tranche_age, consent }: Fields) => {
    setError(null)
    setTaken(false)
    try {
      const { mail_sent } = await registerUser(email, password, { prenom, tranche_age, consent }, next)
      setPending({ email, mailSent: mail_sent })
    } catch (e) {
      // 409: the address already has an account, confirmed or not. Signing in
      // or resetting the password is the way back — never a second account.
      setTaken(e instanceof ApiError && e.status === 409)
      setError(e instanceof ApiError ? e.message : "Erreur lors de la création du compte.")
    }
  }

  const connexionHref = next ? `/connexion?redirect=${encodeURIComponent(next)}` : "/connexion"

  if (pending) {
    return (
      <AuthLayout>
        {/* Keyed by address: the countdown and the failure flag start from the
            props once, so a second signup must never inherit the first's. */}
        <VerificationPending
          key={pending.email}
          email={pending.email}
          next={next}
          mailSent={pending.mailSent}
          onRestart={() => { reset(); setPending(null) }}
        />
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-bold text-navy">Créer un compte</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">Gratuit · 1 analyse offerte.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>
              {error}
              {taken && (
                <span className="mt-1.5 block">
                  <Link href={connexionHref} className="underline underline-offset-2">Se connecter</Link>
                  {" · "}
                  <Link href="/mot-de-passe-oublie" className="underline underline-offset-2">Mot de passe oublié ?</Link>
                </span>
              )}
            </AlertDescription>
          </Alert>
        )}

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
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" className="h-10" placeholder="vous@exemple.fr" {...register("email")} />
          {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password">Mot de passe</Label>
          <Input id="password" type="password" autoComplete="new-password" className="h-10" placeholder="8 caractères minimum" {...register("password")} />
          {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="confirm">Confirmer le mot de passe</Label>
          <Input id="confirm" type="password" autoComplete="new-password" className="h-10" placeholder="••••••••" {...register("confirm")} />
          {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
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

        <Button type="submit" size="lg" className="h-11 w-full" disabled={isSubmitting}>
          {isSubmitting ? "Création…" : "Créer mon compte"}
        </Button>
      </form>

      <p className="mt-5 text-center text-sm text-muted-foreground">
        Déjà un compte ?{" "}
        <Link href={connexionHref} className="link-underline font-medium text-orange-dark">
          Se connecter
        </Link>
      </p>

      <p className="mt-2 text-center text-sm text-muted-foreground">
        Vous accompagnez des demandeurs d&apos;emploi ?{" "}
        <Link href="/inscription-conseiller" className="link-underline font-medium text-orange-dark">
          Demander un compte conseiller
        </Link>
      </p>
    </AuthLayout>
  )
}

export default function InscriptionPage() {
  return (
    <Suspense>
      <InscriptionForm />
    </Suspense>
  )
}
