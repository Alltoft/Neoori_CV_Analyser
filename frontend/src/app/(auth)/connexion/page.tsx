"use client"

import { Suspense, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useAuth } from "@/lib/auth"
import { ApiError } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"

const schema = z.object({
  email: z.string().email("Email invalide."),
  password: z.string().min(1, "Mot de passe requis."),
})
type Fields = z.infer<typeof schema>

function ConnexionForm() {
  const { login } = useAuth()
  const router = useRouter()
  const params = useSearchParams()
  const [error, setError] = useState<string | null>(null)

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async ({ email, password }: Fields) => {
    setError(null)
    try {
      await login(email, password)
      router.push(params.get("redirect") ?? "/espace")
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur de connexion.")
    }
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-bold text-navy">Se connecter</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">Accédez à vos analyses.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
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
          <Label htmlFor="password">Mot de passe</Label>
          <Input id="password" type="password" autoComplete="current-password" className="h-10" placeholder="••••••••" {...register("password")} />
          {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
        </div>

        <Button type="submit" size="lg" className="h-11 w-full" disabled={isSubmitting}>
          {isSubmitting ? "Connexion…" : "Se connecter"}
        </Button>
      </form>

      <p className="mt-5 text-center text-sm text-muted-foreground">
        Pas encore de compte ?{" "}
        <Link href="/inscription" className="link-underline font-medium text-orange-dark">
          Créer un compte
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
