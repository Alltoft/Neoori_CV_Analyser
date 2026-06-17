"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { StatCard } from "@/components/ui/stat-card"
import { api, ApiError } from "@/lib/api"
import { fmtDate, fmtInt } from "@/lib/format"
import type { User } from "@/types"
import { Ban, Check, Copy, KeyRound, Plus, TicketCheck, Users } from "lucide-react"

interface CounselorCode {
  id: string
  code: string
  label: string
  is_active: boolean
  uses_count: number
  created_at: string
}

export default function ConseillersPage() {
  const [counselors, setCounselors] = useState<User[]>([])
  const [codes, setCodes] = useState<CounselorCode[]>([])
  const [loadingCounselors, setLoadingCounselors] = useState(true)
  const [loadingCodes, setLoadingCodes] = useState(true)
  const [errorCounselors, setErrorCounselors] = useState<string | null>(null)
  const [errorCodes, setErrorCodes] = useState<string | null>(null)
  const [creatingCode, setCreatingCode] = useState(false)
  const [newCodeLabel, setNewCodeLabel] = useState("")
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  // Fetch counselors
  useEffect(() => {
    api.get<{ users: User[] }>("/admin/users")
      .then(r => {
        const filtered = r.users.filter(u => u.role === "counselor")
        setCounselors(filtered)
      })
      .catch(err => setErrorCounselors(err?.message ?? "Erreur de chargement"))
      .finally(() => setLoadingCounselors(false))
  }, [])

  // Fetch codes
  useEffect(() => {
    api.get<{ codes: CounselorCode[] }>("/admin/counselor-codes")
      .then(r => setCodes(r.codes))
      .catch(err => setErrorCodes(err?.message ?? "Erreur de chargement"))
      .finally(() => setLoadingCodes(false))
  }, [])

  const activeCodes = useMemo(() => codes.filter(c => c.is_active).length, [codes])

  const handleCopyCode = useCallback(async (code: string, id: string) => {
    try {
      await navigator.clipboard.writeText(code)
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    } catch {
      // Surface clipboard failures instead of swallowing them
      setErrorCodes("Impossible de copier le code dans le presse-papiers.")
    }
  }, [])

  const handleCreateCode = useCallback(async () => {
    if (!newCodeLabel.trim()) return

    setCreatingCode(true)
    try {
      const result = await api.post<{ code: CounselorCode }>(
        "/admin/counselor-codes",
        { label: newCodeLabel }
      )
      setCodes(prev => [result.code, ...prev])
      setNewCodeLabel("")
    } catch (err) {
      setErrorCodes(err instanceof ApiError ? err.message : "Erreur lors de la création")
    } finally {
      setCreatingCode(false)
    }
  }, [newCodeLabel])

  const handleDeactivateCode = useCallback(async (id: string) => {
    if (!window.confirm("Désactiver ce code d’accès ? Il ne pourra plus être utilisé.")) return
    setDeletingId(id)
    try {
      await api.delete(`/admin/counselor-codes/${id}`)
      setCodes(prev =>
        prev.map(c => c.id === id ? { ...c, is_active: false } : c)
      )
    } catch (err) {
      setErrorCodes(err instanceof ApiError ? err.message : "Erreur lors de la désactivation")
    } finally {
      setDeletingId(null)
    }
  }, [])

  return (
    <>
      {/* Page header */}
      <div className="mb-6">
        <p className="eyebrow text-orange-dark">Administration</p>
        <h1 className="font-display font-bold text-2xl sm:text-3xl text-navy mt-1">
          Conseillers
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Comptes conseillers et codes d’accès pour les bénéficiaires Cap Emploi / France Travail.
        </p>
      </div>

      {/* Summary tiles */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 mb-6">
        <StatCard
          label="Conseillers"
          value={loadingCounselors ? "—" : fmtInt(counselors.length)}
          hint="Comptes actifs"
          icon={<Users className="size-4" />}
        />
        <StatCard
          label="Codes d’accès"
          value={loadingCodes ? "—" : fmtInt(codes.length)}
          hint="Tous statuts"
          icon={<TicketCheck className="size-4" />}
        />
        <StatCard
          label="Codes actifs"
          value={loadingCodes ? "—" : fmtInt(activeCodes)}
          hint="Utilisables"
          icon={<KeyRound className="size-4" />}
          accent
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left panel: Counselors */}
        <section className="rounded-2xl bg-card ring-1 ring-foreground/10 shadow-soft">
          <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
            <div className="flex items-center gap-2">
              <Users className="size-4 text-orange" />
              <h2 className="font-display font-semibold text-base text-navy">
                Comptes conseillers
              </h2>
            </div>
            <span className="eyebrow text-muted-foreground">
              {counselors.length} compte{counselors.length !== 1 ? "s" : ""}
            </span>
          </div>

          <div className="px-5 py-4">
            {errorCounselors && (
              <div
                role="alert"
                className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
              >
                {errorCounselors}
              </div>
            )}

            <div className="w-full overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Email</th>
                    <th className="eyebrow pb-2 font-medium text-muted-foreground">Créé le</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingCounselors
                    ? Array.from({ length: 4 }, (_, i) => (
                        <tr key={i} className="border-b border-border/60">
                          <td colSpan={2} className="py-2.5">
                            <Skeleton className="h-5" />
                          </td>
                        </tr>
                      ))
                    : counselors.map(c => (
                        <tr key={c.id} className="border-b border-border/60 last:border-0">
                          <td className="py-2.5 pr-4 text-navy">{c.email}</td>
                          <td className="py-2.5 font-mono text-xs text-muted-foreground whitespace-nowrap">
                            {fmtDate(c.created_at)}
                          </td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>

            {!loadingCounselors && counselors.length === 0 && (
              <p className="py-10 text-center text-sm text-muted-foreground">
                Aucun conseiller inscrit pour le moment.
              </p>
            )}
          </div>
        </section>

        {/* Right panel: Code manager */}
        <section className="rounded-2xl bg-card ring-1 ring-foreground/10 shadow-soft">
          <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
            <div className="flex items-center gap-2">
              <KeyRound className="size-4 text-orange" />
              <h2 className="font-display font-semibold text-base text-navy">
                Codes d’accès conseiller
              </h2>
            </div>
            <span className="eyebrow text-muted-foreground">
              {codes.length} code{codes.length !== 1 ? "s" : ""}
            </span>
          </div>

          <div className="px-5 py-4">
            {errorCodes && (
              <div
                role="alert"
                className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
              >
                {errorCodes}
              </div>
            )}

            {/* Code generation form */}
            <form
              onSubmit={e => {
                e.preventDefault()
                handleCreateCode()
              }}
              className="mb-5 border-b border-border pb-5"
            >
              <Label htmlFor="code-label" className="eyebrow text-muted-foreground">
                Nouveau code
              </Label>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                <Input
                  id="code-label"
                  type="text"
                  placeholder="Libellé du code…"
                  value={newCodeLabel}
                  onChange={e => setNewCodeLabel(e.target.value)}
                  disabled={creatingCode}
                  className="h-10"
                />
                <Button
                  type="submit"
                  variant="navy"
                  size="lg"
                  disabled={creatingCode || !newCodeLabel.trim()}
                  className="shrink-0"
                >
                  <Plus className="size-4" />
                  {creatingCode ? "Génération…" : "Générer"}
                </Button>
              </div>
            </form>

            {/* Codes table */}
            <div className="w-full overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Code</th>
                    <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Libellé</th>
                    <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Statut</th>
                    <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Utilisations</th>
                    <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Créé le</th>
                    <th className="eyebrow pb-2 text-right font-medium text-muted-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingCodes
                    ? Array.from({ length: 4 }, (_, i) => (
                        <tr key={i} className="border-b border-border/60">
                          <td colSpan={6} className="py-2.5">
                            <Skeleton className="h-5" />
                          </td>
                        </tr>
                      ))
                    : codes.map(c => (
                        <tr key={c.id} className="border-b border-border/60 last:border-0 align-middle">
                          <td className="py-3 pr-4">
                            <span className="select-all font-mono text-sm font-medium text-navy">
                              {c.code}
                            </span>
                          </td>
                          <td className="py-3 pr-4 text-sm text-navy">{c.label}</td>
                          <td className="py-3 pr-4">
                            <Badge variant={c.is_active ? "success" : "secondary"}>
                              {c.is_active ? "Actif" : "Inactif"}
                            </Badge>
                          </td>
                          <td className="py-3 pr-4 font-mono text-xs text-muted-foreground tabular-nums">
                            {fmtInt(c.uses_count)}
                          </td>
                          <td className="py-3 pr-4 font-mono text-xs text-muted-foreground whitespace-nowrap">
                            {fmtDate(c.created_at)}
                          </td>
                          <td className="py-3">
                            <div className="flex items-center justify-end gap-1.5">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleCopyCode(c.code, c.id)}
                                disabled={deletingId === c.id}
                              >
                                {copiedId === c.id ? (
                                  <>
                                    <Check className="size-3.5 text-success" />
                                    Copié
                                  </>
                                ) : (
                                  <>
                                    <Copy className="size-3.5" />
                                    Copier
                                  </>
                                )}
                              </Button>
                              {c.is_active && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleDeactivateCode(c.id)}
                                  disabled={creatingCode || deletingId === c.id}
                                  className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                                >
                                  <Ban className="size-3.5" />
                                  {deletingId === c.id ? "…" : "Désactiver"}
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>

            {!loadingCodes && codes.length === 0 && (
              <p className="py-10 text-center text-sm text-muted-foreground">
                Aucun code généré pour le moment.
              </p>
            )}
          </div>
        </section>
      </div>
    </>
  )
}
