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
import { api, ApiError } from "@/lib/api"
import type { User } from "@/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"

const INVALID = "Ce lien n’est pas valide. Demandez-en un nouveau."

// Passwords are never trimmed or otherwise transformed: what is typed is what
// the server stores and what the person logs in with afterwards.
const schema = z
  .object({
    password: z.string().min(8, "8 caractères minimum."),
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, {
    message: "Les mots de passe ne correspondent pas.",
    path: ["confirm"],
  })
type Fields = z.infer<typeof schema>

function Reinitialiser() {
  const params = useSearchParams()
  const { app, go } = useSite()
  const { refresh } = useAuth()
  const token = params.get("token") ?? ""
  const [dead, setDead] = useState<string | null>(token ? null : INVALID)
  const [error, setError] = useState<string | null>(null)
  // Set once the password is saved: the button stays disabled while the
  // navigation runs, after isSubmitting has already gone false.
  const [leaving, setLeaving] = useState(false)
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async ({ password }: Fields) => {
    setError(null)
    try {
      const res = await api.post<{ user: User }>("/auth/reset-password", { token, password }, { skipRedirect: true })
      await refresh()
      setLeaving(true)
      // replace, not push: Back must not reopen the spent link.
      go(homeFor(res.user.role, app), { replace: true })
    } catch (e) {
      const code = e instanceof ApiError ? e.body?.code : undefined
      if (code === "link_expired" || code === "link_invalid") setDead((e as ApiError).message)
      else setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
    }
  }

  return (
    <>
      <h1 className="font-display text-2xl font-bold text-navy">Nouveau mot de passe</h1>
      {dead ? (
        <>
          <Alert variant="destructive" className="mt-6"><AlertDescription>{dead}</AlertDescription></Alert>
          <p className="mt-5 text-center text-sm">
            <Link href="/mot-de-passe-oublie" className="link-underline font-medium text-orange-dark">
              Demander un nouveau lien
            </Link>
          </p>
        </>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
          {error && (
            <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="password">Nouveau mot de passe</Label>
            <Input id="password" type="password" autoComplete="new-password" className="h-10" placeholder="8 caractères minimum" {...register("password")} />
            {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="confirm">Confirmer le mot de passe</Label>
            <Input id="confirm" type="password" autoComplete="new-password" className="h-10" placeholder="••••••••" {...register("confirm")} />
            {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
          </div>
          <Button type="submit" size="lg" className="h-11 w-full" disabled={isSubmitting || leaving}>
            {isSubmitting || leaving ? "Enregistrement…" : "Enregistrer et me connecter"}
          </Button>
        </form>
      )}
    </>
  )
}

export default function ReinitialiserMotDePassePage() {
  return (
    <AuthLayout>
      <Suspense>
        <Reinitialiser />
      </Suspense>
    </AuthLayout>
  )
}
