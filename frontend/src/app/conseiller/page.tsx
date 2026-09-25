"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { AppBar } from "@/components/layout/AppBar"
import { Alert, AlertAction, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { StatCard } from "@/components/ui/stat-card"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { counselor } from "@/lib/counselor"
import { fmtDate, fmtInt } from "@/lib/format"
import type { Beneficiaire, CodeStatut, CounselorCodeRow, CounselorProfile, CounselorStats } from "@/types"
import { Ban, Check, Copy, KeyRound, Plus, TicketCheck, UserCheck, Users } from "lucide-react"

const STATUT_LABEL: Record<CodeStatut, string> = {
  actif: "Actif",
  utilise: "Utilisé",
  expire: "Expiré",
  revoque: "Révoqué",
}

const STATUT_VARIANT: Record<CodeStatut, "success" | "secondary" | "warning"> = {
  actif: "success",
  utilise: "secondary",
  expire: "warning",
  revoque: "secondary",
}

export default function ConseillerPage() {
  const { user, loading: authLoading, refresh: refreshAuth } = useAuth()
  const router = useRouter()

  const [profile, setProfile] = useState<CounselorProfile | null>(null)
  const [loadingProfile, setLoadingProfile] = useState(true)
  // `profile === null` means two different things — "the server says you have no
  // demande" and "we never got an answer". Only the first should offer to start
  // one, so the failure case is tracked separately.
  const [profileFailed, setProfileFailed] = useState(false)
  const [stats, setStats] = useState<CounselorStats | null>(null)
  const [codes, setCodes] = useState<CounselorCodeRow[]>([])
  const [people, setPeople] = useState<Beneficiaire[]>([])
  const [error, setError] = useState<string | null>(null)
  const [label, setLabel] = useState("")
  const [places, setPlaces] = useState("1")
  const [creating, setCreating] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  // Expired cookie: keep the deep link so they land back here after signing in.
  useEffect(() => {
    if (!authLoading && !user) router.replace("/connexion?redirect=/conseiller")
  }, [authLoading, user, router])

  // Extracted so the "Réessayer" button (rendered with the error alert below)
  // can re-run the same fetch, not just this mount's effect.
  const loadProfile = useCallback(() => {
    return counselor.me()
      .then((r) => { setProfile(r.profile); setProfileFailed(false); setError(null) })
      .catch((e) => {
        setError(e instanceof ApiError ? e.message : "Erreur de chargement.")
        setProfileFailed(true)
      })
      .finally(() => setLoadingProfile(false))
  }, [])

  useEffect(() => {
    if (authLoading || !user) return
    loadProfile()
  }, [authLoading, user, loadProfile])

  const loadDashboard = useCallback(async () => {
    try {
      const [s, c, b] = await Promise.all([
        counselor.stats(), counselor.codes(), counselor.beneficiaires(),
      ])
      setStats(s)
      setCodes(c.codes)
      setPeople(b.beneficiaires)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur de chargement.")
    }
  }, [])

  // Approval flips user.role in the DB, but the access token in the browser
  // still says "candidate" until it expires (1 h) — and every /api/counselor
  // route below /me reads the claim. POST /auth/refresh re-mints it from the
  // row (backend auth.py:93-99); useAuth().refresh is GET /auth/me and does
  // NOT, so both are needed: one for the cookie, one for the context.
  useEffect(() => {
    if (profile?.status !== "approved") return
    const run = async () => {
      if (user && user.role !== "counselor") {
        try {
          await api.post("/auth/refresh")
          await refreshAuth()
        } catch {
          // Refresh cookie gone: the 403 below tells them to sign in again.
        }
      }
      await loadDashboard()
    }
    run()
  }, [profile?.status, user, refreshAuth, loadDashboard])

  const handleCreate = async () => {
    if (!label.trim()) return
    setCreating(true)
    setError(null)
    try {
      const n = Number.parseInt(places, 10)
      await counselor.createCode(label.trim(), Number.isFinite(n) && n > 0 ? n : 1)
      setLabel("")
      setPlaces("1")
      await loadDashboard()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur lors de la création.")
    } finally {
      setCreating(false)
    }
  }

  const handleCopy = async (code: string, id: string) => {
    try {
      await navigator.clipboard.writeText(code)
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    } catch {
      setError("Impossible de copier le code dans le presse-papiers.")
    }
  }

  const handleRevoke = async (id: string) => {
    if (!window.confirm("Révoquer ce code ? Il ne pourra plus être utilisé.")) return
    try {
      await counselor.revokeCode(id)
      await loadDashboard()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur lors de la révocation.")
    }
  }

  if (authLoading || !user || loadingProfile) {
    return (
      <>
        <AppBar />
        <main className="mx-auto max-w-6xl px-5 py-10">
          <Skeleton className="h-8 w-64" />
        </main>
      </>
    )
  }

  return (
    <>
      <AppBar />
      <main className="mx-auto max-w-6xl px-5 py-10">
        <p className="eyebrow text-orange-dark">Espace conseiller</p>
        <h1 className="mt-1 font-display text-2xl font-bold text-navy sm:text-3xl">
          {profile?.status === "approved" ? "Mes bénéficiaires" : "Votre demande"}
        </h1>

        {error && (
          <Alert variant="destructive" className="mt-5">
            <AlertDescription>{error}</AlertDescription>
            {profileFailed && (
              <AlertAction>
                <Button size="sm" variant="outline" onClick={() => loadProfile()}>
                  Réessayer
                </Button>
              </AlertAction>
            )}
          </Alert>
        )}

        {/* No demande at all — only once the server has actually said so; a
            failed fetch must not look identical to never having applied. */}
        {!profile && !profileFailed && (
          <div className="mt-6 rounded-2xl bg-card p-6 ring-1 ring-foreground/10">
            <p className="text-sm text-muted-foreground">
              Aucune demande de compte conseiller n&apos;est associée à ce compte.
            </p>
            <Button render={<Link href="/inscription-conseiller" />} size="lg" className="mt-4">
              Faire une demande
            </Button>
          </div>
        )}

        {profile?.status === "pending" && (
          <div className="mt-6 rounded-2xl bg-card p-6 ring-1 ring-foreground/10">
            <p className="text-sm text-navy">Votre demande est en cours d&apos;examen.</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Vous recevrez un email dès qu&apos;elle aura été traitée. En attendant, votre
              compte fonctionne normalement comme compte candidat.
            </p>
            <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
              <div><dt className="eyebrow text-muted-foreground">Structure</dt><dd className="text-navy">{profile.structure}</dd></div>
              <div><dt className="eyebrow text-muted-foreground">Fonction</dt><dd className="text-navy">{profile.fonction}</dd></div>
              <div><dt className="eyebrow text-muted-foreground">Téléphone</dt><dd className="text-navy">{profile.telephone}</dd></div>
              <div><dt className="eyebrow text-muted-foreground">Demande envoyée le</dt><dd className="text-navy">{fmtDate(profile.created_at)}</dd></div>
            </dl>
          </div>
        )}

        {(profile?.status === "rejected" || profile?.status === "revoked") && (
          <div className="mt-6 rounded-2xl bg-card p-6 ring-1 ring-foreground/10">
            <p className="text-sm text-navy">
              {profile.status === "rejected"
                ? "Votre demande n'a pas été retenue."
                : "Votre accès conseiller a été retiré."}
            </p>
            {profile.decision_reason && (
              <p className="mt-3 rounded-lg bg-secondary px-4 py-3 text-sm text-muted-foreground">
                {profile.decision_reason}
              </p>
            )}
            <p className="mt-3 text-sm text-muted-foreground">
              Votre compte reste utilisable comme compte candidat.
            </p>
          </div>
        )}

        {profile?.status === "approved" && (
          <>
            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Bénéficiaires" value={stats ? fmtInt(stats.beneficiaires) : "—"} hint="Codes utilisés" icon={<Users className="size-4" />} />
              <StatCard label="Accompagnements" value={stats ? fmtInt(stats.accompagnements) : "—"} hint="Portraits validés" icon={<UserCheck className="size-4" />} accent />
              <StatCard label="Codes restants" value={stats ? (stats.codes_restants === null ? "Illimité" : fmtInt(stats.codes_restants)) : "—"} hint={stats?.max_codes === null ? "Aucune limite" : `Sur ${fmtInt(stats?.max_codes)}`} icon={<TicketCheck className="size-4" />} />
              <StatCard label="En circulation" value={stats ? fmtInt(stats.codes_en_circulation) : "—"} hint="Codes non utilisés" icon={<KeyRound className="size-4" />} />
            </div>

            <section className="mt-6 rounded-2xl bg-card ring-1 ring-foreground/10 shadow-soft">
              <div className="flex items-center gap-2 border-b border-border px-5 py-4">
                <KeyRound className="size-4 text-orange" />
                <h2 className="font-display text-base font-semibold text-navy">Mes codes</h2>
              </div>

              <div className="px-5 py-4">
                <form
                  onSubmit={(e) => { e.preventDefault(); handleCreate() }}
                  className="mb-5 flex flex-col gap-3 border-b border-border pb-5 sm:flex-row sm:items-end"
                >
                  <div className="flex-1 space-y-1.5">
                    <Label htmlFor="code-label">Pour qui ?</Label>
                    <Input id="code-label" className="h-10" placeholder="Prénom ou référence dossier"
                           value={label} onChange={(e) => setLabel(e.target.value)} disabled={creating} />
                  </div>
                  <div className="w-full space-y-1.5 sm:w-28">
                    <Label htmlFor="code-places">Places</Label>
                    <Input id="code-places" type="number" min={1} className="h-10"
                           value={places} onChange={(e) => setPlaces(e.target.value)} disabled={creating} />
                  </div>
                  <Button type="submit" variant="navy" size="lg" disabled={creating || !label.trim()} className="shrink-0">
                    <Plus className="size-4" />
                    {creating ? "Génération…" : "Générer"}
                  </Button>
                </form>

                <p className="mb-4 text-xs text-muted-foreground">
                  Un code par personne, valable 90 jours. Pour un atelier, indiquez le nombre
                  de places{stats?.max_uses_per_code != null ? ` (${stats.max_uses_per_code} maximum)` : ""}.
                </p>

                <div className="w-full overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left">
                        <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Code</th>
                        <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Libellé</th>
                        <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Statut</th>
                        <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Expire le</th>
                        <th className="eyebrow pb-2 text-right font-medium text-muted-foreground">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {codes.map((c) => (
                        <tr key={c.id} className="border-b border-border/60 last:border-0">
                          <td className="py-3 pr-4"><span className="select-all font-mono font-medium text-navy">{c.code}</span></td>
                          <td className="py-3 pr-4 text-navy">{c.label}</td>
                          <td className="py-3 pr-4"><Badge variant={STATUT_VARIANT[c.statut]}>{STATUT_LABEL[c.statut]}</Badge></td>
                          <td className="py-3 pr-4 font-mono text-xs text-muted-foreground whitespace-nowrap">{fmtDate(c.expires_at)}</td>
                          <td className="py-3">
                            <div className="flex items-center justify-end gap-1.5">
                              <Button size="sm" variant="outline" onClick={() => handleCopy(c.code, c.id)}>
                                {copiedId === c.id
                                  ? <><Check className="size-3.5 text-success" />Copié</>
                                  : <><Copy className="size-3.5" />Copier</>}
                              </Button>
                              {c.statut === "actif" && (
                                <Button size="sm" variant="ghost" onClick={() => handleRevoke(c.id)}
                                        className="text-destructive hover:bg-destructive/10 hover:text-destructive">
                                  <Ban className="size-3.5" />Révoquer
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {codes.length === 0 && (
                  <p className="py-10 text-center text-sm text-muted-foreground">
                    Aucun code généré pour le moment.
                  </p>
                )}
              </div>
            </section>

            <section className="mt-6 rounded-2xl bg-card ring-1 ring-foreground/10 shadow-soft">
              <div className="flex items-center gap-2 border-b border-border px-5 py-4">
                <Users className="size-4 text-orange" />
                <h2 className="font-display text-base font-semibold text-navy">Mes bénéficiaires</h2>
              </div>
              <div className="px-5 py-4">
                <div className="w-full overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left">
                        <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Prénom</th>
                        <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Email</th>
                        <th className="eyebrow pb-2 font-medium text-muted-foreground">Utilisé le</th>
                      </tr>
                    </thead>
                    <tbody>
                      {people.map((p, i) => (
                        <tr key={`${p.email ?? "anon"}-${i}`} className="border-b border-border/60 last:border-0">
                          <td className="py-2.5 pr-4 text-navy">{p.prenom ?? "—"}</td>
                          <td className="py-2.5 pr-4 text-navy">{p.email ?? "Bénéficiaire anonyme"}</td>
                          <td className="py-2.5 font-mono text-xs text-muted-foreground whitespace-nowrap">{fmtDate(p.redeemed_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {people.length === 0 && (
                  <p className="py-10 text-center text-sm text-muted-foreground">
                    Aucun code n&apos;a encore été utilisé.
                  </p>
                )}
              </div>
            </section>
          </>
        )}
      </main>
    </>
  )
}
