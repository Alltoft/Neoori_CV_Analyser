"use client"

import { useState } from "react"
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
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"

const schema = z.object({
  email:    z.string().email("Email invalide."),
  password: z.string().min(1, "Mot de passe requis."),
})
type Fields = z.infer<typeof schema>

export default function ConnexionPage() {
  const { login } = useAuth()
  const router     = useRouter()
  const params     = useSearchParams()
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
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <Link href="/" className="block text-center font-bold text-xl mb-8 tracking-tight">
          neoori
        </Link>

        <Card className="border-border">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">Se connecter</CardTitle>
            <CardDescription>Accédez à vos analyses.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" autoComplete="email"
                  placeholder="vous@exemple.fr" {...register("email")} />
                {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password">Mot de passe</Label>
                <Input id="password" type="password" autoComplete="current-password"
                  placeholder="••••••••" {...register("password")} />
                {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
              </div>

              <Button type="submit" className="w-full bg-primary hover:bg-primary/90 text-primary-foreground"
                disabled={isSubmitting}>
                {isSubmitting ? "Connexion…" : "Se connecter →"}
              </Button>
            </form>

            <p className="mt-4 text-center text-xs text-muted-foreground">
              Pas encore de compte ?{" "}
              <Link href="/inscription" className="text-foreground underline underline-offset-2">
                Créer un compte
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
