"use client"

import { useState } from "react"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { api, ApiError } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"

const schema = z.object({ email: z.string().email("Email invalide.") })
type Fields = z.infer<typeof schema>

export default function MotDePasseOubliePage() {
  const [done, setDone] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async ({ email }: Fields) => {
    setError(null)
    try {
      // The same sentence comes back whether or not the address has an
      // account (spec decision 11) — it is shown as is.
      const res = await api.post<{ message: string }>("/auth/forgot-password", { email }, { skipRedirect: true })
      setDone(res.message)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
    }
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-bold text-navy">Mot de passe oublié</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Indiquez l’adresse de votre compte : vous recevrez un lien pour choisir un nouveau mot de passe, valable 1 heure.
      </p>

      {done ? (
        <Alert className="mt-7">
          <AlertDescription className="text-sm text-foreground">
            {done} Pensez à regarder dans les courriers indésirables.
          </AlertDescription>
        </Alert>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
          {error && (
            <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" className="h-10" placeholder="vous@exemple.fr" {...register("email")} />
            {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
          </div>
          <Button type="submit" size="lg" className="h-11 w-full" disabled={isSubmitting}>
            {isSubmitting ? "Envoi…" : "Recevoir le lien"}
          </Button>
        </form>
      )}

      <p className="mt-5 text-center text-sm text-muted-foreground">
        <Link href="/connexion" className="link-underline font-medium text-orange-dark">Retour à la connexion</Link>
      </p>
    </AuthLayout>
  )
}
