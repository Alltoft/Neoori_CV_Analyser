"use client"

import { useCallback, useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { api, ApiError } from "@/lib/api"
import type { User } from "@/types"

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

  const handleCopyCode = useCallback((code: string, id: string) => {
    navigator.clipboard.writeText(code)
      .then(() => {
        setCopiedId(id)
        setTimeout(() => setCopiedId(null), 2000)
      })
      .catch(() => {})
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
    <div className="grid grid-cols-2 gap-6">
      {/* Left panel: Counselors */}
      <div>
        {errorCounselors && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 mb-4">
            {errorCounselors}
          </div>
        )}

        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="font-semibold text-sm">conseillers</h2>
            <span className="text-[10px] text-muted-foreground">
              {counselors.length} conseiller{counselors.length !== 1 ? "s" : ""}
            </span>
          </div>

          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-muted-foreground text-[10px] font-mono uppercase">
                <th className="text-left pb-2 pr-4 font-normal">email</th>
                <th className="text-left pb-2 font-normal">créé le</th>
              </tr>
            </thead>
            <tbody>
              {loadingCounselors
                ? Array.from({ length: 4 }, (_, i) => (
                    <tr key={i} className="border-b border-dashed border-border">
                      <td colSpan={2} className="py-2">
                        <Skeleton className="h-5" />
                      </td>
                    </tr>
                  ))
                : counselors.map(c => (
                    <tr key={c.id} className="border-b border-dashed border-border last:border-0">
                      <td className="py-2 pr-4">{c.email}</td>
                      <td className="py-2 text-[10px] text-muted-foreground">
                        {new Date(c.created_at).toLocaleDateString("fr-FR")}
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>

          {!loadingCounselors && counselors.length === 0 && (
            <p className="text-center text-xs text-muted-foreground py-8">
              aucun conseiller inscrit
            </p>
          )}
        </div>
      </div>

      {/* Right panel: Code manager */}
      <div>
        {errorCodes && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 mb-4">
            {errorCodes}
          </div>
        )}

        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="font-semibold text-sm">codes d'accès conseiller</h2>
            <span className="text-[10px] text-muted-foreground">
              {codes.length} code{codes.length !== 1 ? "s" : ""}
            </span>
          </div>

          {/* Code generation form */}
          <div className="mb-4 pb-4 border-b border-border flex gap-2">
            <Input
              type="text"
              placeholder="label du code..."
              value={newCodeLabel}
              onChange={e => setNewCodeLabel(e.target.value)}
              disabled={creatingCode}
              className="text-xs h-8"
            />
            <Button
              size="sm"
              onClick={handleCreateCode}
              disabled={creatingCode || !newCodeLabel.trim()}
              className="text-xs h-8"
            >
              {creatingCode ? "..." : "+ générer"}
            </Button>
          </div>

          {/* Codes table */}
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-muted-foreground text-[10px] font-mono uppercase">
                <th className="text-left pb-2 pr-4 font-normal">code</th>
                <th className="text-left pb-2 pr-4 font-normal">label</th>
                <th className="text-left pb-2 pr-4 font-normal">statut</th>
                <th className="text-left pb-2 pr-4 font-normal">uses</th>
                <th className="text-left pb-2 pr-4 font-normal">créé le</th>
                <th className="text-left pb-2 font-normal">actions</th>
              </tr>
            </thead>
            <tbody>
              {loadingCodes
                ? Array.from({ length: 4 }, (_, i) => (
                    <tr key={i} className="border-b border-dashed border-border">
                      <td colSpan={6} className="py-2">
                        <Skeleton className="h-5" />
                      </td>
                    </tr>
                  ))
                : codes.map(c => (
                    <tr key={c.id} className="border-b border-dashed border-border last:border-0">
                      <td className="py-2 pr-4 font-mono text-[9px] text-muted-foreground">
                        {c.code}
                      </td>
                      <td className="py-2 pr-4 text-[10px]">{c.label}</td>
                      <td className="py-2 pr-4">
                        <Badge
                          variant="outline"
                          className={`text-[9px] px-1.5 ${
                            c.is_active
                              ? "bg-green-50 border-green-200 text-green-700"
                              : "bg-gray-50 border-gray-200 text-gray-700"
                          }`}
                        >
                          {c.is_active ? "actif" : "inactif"}
                        </Badge>
                      </td>
                      <td className="py-2 pr-4 text-[10px] text-muted-foreground">
                        {c.uses_count}
                      </td>
                      <td className="py-2 pr-4 text-[10px] text-muted-foreground">
                        {new Date(c.created_at).toLocaleDateString("fr-FR")}
                      </td>
                      <td className="py-2 flex gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleCopyCode(c.code, c.id)}
                          disabled={deletingId === c.id}
                          className="text-[9px] h-6 px-2"
                        >
                          {copiedId === c.id ? "copié ✓" : "copier"}
                        </Button>
                        {c.is_active && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleDeactivateCode(c.id)}
                            disabled={creatingCode || deletingId === c.id}
                            className="text-[9px] h-6 px-2 text-red-600 hover:text-red-700 hover:bg-red-50"
                          >
                            {deletingId === c.id ? "..." : "désactiver"}
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>

          {!loadingCodes && codes.length === 0 && (
            <p className="text-center text-xs text-muted-foreground py-8">
              aucun code généré
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
