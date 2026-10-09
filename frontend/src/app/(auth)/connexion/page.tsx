"use client"

import { Suspense, useState } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useAuth } from "@/lib/auth"
import { homeFor } from "@/lib/home"
import { useSite } from "@/lib/site-context"
import { ApiError } from "@/lib/api"
import { safeRedirect } from "@/lib/safe-redirect"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"
import { VerificationPending } from "@/components/auth/VerificationPending"
import { SocialSignIn } from "@/components/auth/SocialSignIn"

const schema = z.object({
  email: z.string().email("Email invalide."),
  password: z.string().min(1, "Mot de passe requis."),
})
type Fields = z.infer<typeof schema>

/** What /api/auth/<provider>/callback reports when it sends someone back
 *  here (social sign-in spec, decision 12). A Map, not an object literal:
 *  "?erreur=constructor" must find nothing. */
const OAUTH_ERRORS = new Map([
  ["annule", "Connexion annulée."],
  ["echec", "La connexion n’a pas abouti. Réessayez, ou utilisez « Recevoir un lien de connexion »."],
  ["indisponible", "Ce mode de connexion n’est pas disponible pour le moment."],
  ["email_non_verifie", "Ce compte ne confirme pas votre adresse email. Utilisez « Recevoir un lien de connexion »."],
])

function ConnexionForm() {
  const { login } = useAuth()
  const { app, go } = useSite()
  const params = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  // Checked as given by safeRedirect: only a path on this site is followed or
  // passed on, anything else falls back to the role's home.
  const redirect = safeRedirect(params.get("redirect"))
  const oauthError = OAUTH_ERRORS.get(params.get("erreur") ?? "") ?? null
  // Right password, unconfirmed address: the server says so only to someone
  // who knows the password (spec decision 9). Holds the address to resend to.
  const [unverified, setUnverified] = useState<string | null>(null)

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async ({ email, password }: Fields) => {
    setError(null)
    try {
      const signedIn = await login(email, password)
      // A ?redirect= still wins — it is the page they were turned away from.
      // Otherwise each role lands on its own home rather than the candidate
      // espace: an admin in Administration, an approved conseiller in their
      // espace conseiller.
      go(redirect ?? homeFor(signedIn.role, app))
    } catch (e) {
      if (e instanceof ApiError && e.body?.code === "email_unverified") {
        setUnverified(email)
        return
      }
      setError(e instanceof ApiError ? e.message : "Erreur de connexion.")
    }
  }

  const inscriptionHref = redirect ? `/inscription?redirect=${encodeURIComponent(redirect)}` : "/inscription"

  if (unverified) {
    return (
      <AuthLayout>
        {/* Keyed by address, so a later unconfirmed login starts a fresh countdown. */}
        <VerificationPending
          key={unverified}
          variant="login"
          email={unverified}
          next={redirect}
          onRestart={() => setUnverified(null)}
          restartLabel="Retour à la connexion"
        />
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-bold text-navy">Se connecter</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">Retrouvez vos analyses, votre profil et votre voyage.</p>

      {oauthError && (
        <Alert variant="destructive" className="mt-6">
          <AlertDescription>{oauthError}</AlertDescription>
        </Alert>
      )}

      <SocialSignIn next={redirect} separator="ou" />

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" className="h-10" placeholder="vous@exemple.fr" {...register("email")} />
          {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
        </div>

        <div className="space-y-1.5">
          <div className="flex items-baseline justify-between">
            <Label htmlFor="password">Mot de passe</Label>
            <Link href="/mot-de-passe-oublie" className="text-xs text-muted-foreground underline underline-offset-2">
              Mot de passe oublié ?
            </Link>
          </div>
          <Input id="password" type="password" autoComplete="current-password" className="h-10" placeholder="••••••••" {...register("password")} />
          {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
        </div>

        <Button type="submit" size="lg" className="h-11 w-full" disabled={isSubmitting}>
          {isSubmitting ? "Connexion…" : "Se connecter"}
        </Button>
      </form>

      <p className="mt-5 text-center text-sm text-muted-foreground">
        Pas encore de compte ?{" "}
        <Link href={inscriptionHref} className="link-underline font-medium text-orange-dark">
          Créer un compte
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

export default function ConnexionPage() {
  return (
    <Suspense>
      <ConnexionForm />
    </Suspense>
  )
}
