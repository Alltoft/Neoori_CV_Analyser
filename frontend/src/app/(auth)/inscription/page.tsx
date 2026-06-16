"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
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
import { Logo } from "@/components/brand/Logo"

const schema = z.object({
  email:    z.string().email("Email invalide."),
  password: z.string().min(8, "8 caractères minimum."),
  confirm:  z.string(),
}).refine(d => d.password === d.confirm, {
  message: "Les mots de passe ne correspondent pas.",
  path: ["confirm"],
})
type Fields = z.infer<typeof schema>

export default function InscriptionPage() {
  const { register: registerUser } = useAuth()
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async ({ email, password }: Fields) => {
    setError(null)
    try {
      await registerUser(email, password)
      router.push("/espace")
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur lors de la création du compte.")
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4 relative overflow-hidden">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -top-24 right-0 h-[360px] w-[360px] rounded-full bg-peach/20 blur-[110px]" />
        <div className="absolute bottom-0 -left-20 h-[320px] w-[320px] rounded-full bg-orange/10 blur-[110px]" />
      </div>
      <div className="w-full max-w-sm">
        <Link href="/" className="flex justify-center mb-8 text-2xl">
          <Logo />
        </Link>

        <Card className="border-border shadow-xl shadow-navy/5">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">Créer un compte</CardTitle>
            <CardDescription>Gratuit · 1 analyse offerte.</CardDescription>
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
                <Input id="password" type="password" autoComplete="new-password"
                  placeholder="8 caractères minimum" {...register("password")} />
                {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="confirm">Confirmer le mot de passe</Label>
                <Input id="confirm" type="password" autoComplete="new-password"
                  placeholder="••••••••" {...register("confirm")} />
                {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
              </div>

              <Button type="submit" className="w-full bg-primary hover:bg-primary/90 text-primary-foreground"
                disabled={isSubmitting}>
                {isSubmitting ? "Création…" : "Créer mon compte →"}
              </Button>
            </form>

            <p className="mt-4 text-center text-xs text-muted-foreground">
              Déjà un compte ?{" "}
              <Link href="/connexion" className="text-foreground underline underline-offset-2">
                Se connecter
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
