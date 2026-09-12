"use client"

import { useEffect, useMemo, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { api, ApiError } from "@/lib/api"
import { fmtDate, planLabel, roleLabel } from "@/lib/format"
import type { User } from "@/types"
import { Search, Users } from "lucide-react"

/** The three values the API accepts (contracts § E16). */
const ROLE_OPTIONS: User["role"][] = ["candidate", "counselor", "admin"]

const planVariant = (plan: User["plan"]) => (plan === "paid" ? "peach" : "secondary")

export default function UtilisateursPage() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState("")
  const [savingId, setSavingId] = useState<string | null>(null)
  const [rowError, setRowError] = useState<Record<string, string>>({})

  const changeRole = async (id: string, role: string) => {
    setSavingId(id)
    setRowError((current) => ({ ...current, [id]: "" }))
    try {
      const res = await api.put<{ user: User }>(`/admin/users/${id}/role`, { role })
      setUsers((list) => list.map((u) => (u.id === res.user.id ? res.user : u)))
    } catch (err) {
      // The API refuses to demote the last admin with a 409 and a French
      // sentence — show it on the row rather than swallowing it.
      setRowError((current) => ({
        ...current,
        [id]: err instanceof ApiError ? err.message : "Échec de la modification.",
      }))
    } finally {
      setSavingId(null)
    }
  }

  useEffect(() => {
    api
      .get<{ users: User[] }>("/admin/users")
      .then((r) => setUsers(r.users))
      .catch((err) => setError(err?.message ?? "Erreur de chargement"))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return users
    return users.filter((u) => u.email.toLowerCase().includes(q))
  }, [users, query])

  if (error)
    return (
      <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
        {error}
      </div>
    )

  return (
    <>
      <header className="mb-6">
        <p className="eyebrow text-orange-dark">Administration</p>
        <h1 className="mt-1 font-display text-2xl font-bold text-navy">
          Utilisateurs
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Liste des comptes. Le rôle est modifiable : un conseiller peut ouvrir les fiches de
          synthèse et valider les portraits du voyage.
        </p>
      </header>

      <div className="rounded-2xl bg-card p-4 shadow-card ring-1 ring-foreground/10 sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2 text-sm text-navy">
            <Users className="size-4 text-muted-foreground" aria-hidden="true" />
            <span className="font-mono text-xs tracking-wide text-muted-foreground">
              {loading
                ? "Chargement…"
                : `${filtered.length} compte${filtered.length !== 1 ? "s" : ""}${
                    query.trim() ? ` sur ${users.length}` : ""
                  }`}
            </span>
          </div>

          <div className="relative w-full sm:max-w-xs">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Rechercher par e-mail…"
              aria-label="Rechercher un utilisateur par e-mail"
              className="h-10 pl-9"
            />
          </div>
        </div>

        <div className="mt-4 overflow-hidden rounded-xl border border-border">
          <Table>
            <TableHeader>
              <TableRow className="bg-secondary hover:bg-secondary">
                <TableHead className="eyebrow text-navy-500">E-mail</TableHead>
                <TableHead className="eyebrow text-navy-500">Rôle</TableHead>
                <TableHead className="eyebrow text-navy-500">Plan</TableHead>
                <TableHead className="eyebrow text-right text-navy-500">
                  Crédits
                </TableHead>
                <TableHead className="eyebrow text-navy-500">Inscrit le</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                Array.from({ length: 8 }, (_, i) => (
                  <TableRow key={i} className="hover:bg-transparent">
                    <TableCell colSpan={5} className="py-3">
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              ) : filtered.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell
                    colSpan={5}
                    className="py-12 text-center text-sm text-muted-foreground"
                  >
                    {query.trim()
                      ? "Aucun utilisateur ne correspond à cette recherche."
                      : "Aucun utilisateur."}
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell className="font-medium text-navy">
                      {u.email}
                    </TableCell>
                    <TableCell>
                      <Select
                        value={u.role}
                        onValueChange={(v) => {
                          if (typeof v === "string" && v !== u.role) void changeRole(u.id, v)
                        }}
                      >
                        <SelectTrigger
                          size="sm"
                          className="w-36"
                          disabled={savingId === u.id}
                          aria-label={`Rôle de ${u.email}`}
                        >
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLE_OPTIONS.map((role) => (
                            <SelectItem key={role} value={role}>
                              {roleLabel(role)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {rowError[u.id] ? (
                        <p className="mt-1 text-[11px] text-destructive">{rowError[u.id]}</p>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <Badge variant={planVariant(u.plan)}>
                        {planLabel(u.plan)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs tabular-nums text-muted-foreground">
                      {u.credits_remaining}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {fmtDate(u.created_at)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </>
  )
}
