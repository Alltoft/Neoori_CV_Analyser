"use client"

import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { User } from "@/types"

export default function UtilisateursPage() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.get<{ users: User[] }>("/admin/users")
      .then(r => setUsers(r.users))
      .catch(err => setError(err?.message ?? "Erreur de chargement"))
      .finally(() => setLoading(false))
  }, [])

  if (error) return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div>
  )

  return (
    <>
    <div className="mb-5">
      <p className="font-mono text-[11px] tracking-[0.15em] uppercase text-orange">Administration</p>
      <h1 className="font-display font-bold text-2xl text-navy mt-1">utilisateurs</h1>
    </div>
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-display font-bold text-sm text-navy">utilisateurs</h2>
        <span className="text-[10px] text-muted-foreground">
          lecture seule · {users.length} compte{users.length !== 1 ? "s" : ""}
        </span>
      </div>

      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-navy/20 text-navy text-[10px] font-mono uppercase tracking-[0.1em]">
            <th className="text-left pb-2 pr-4 font-normal">email</th>
            <th className="text-left pb-2 pr-4 font-normal">rôle</th>
            <th className="text-left pb-2 pr-4 font-normal">plan</th>
            <th className="text-left pb-2 pr-4 font-normal">crédits</th>
            <th className="text-left pb-2 font-normal">inscrit le</th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 8 }, (_, i) => (
                <tr key={i} className="border-b border-dashed border-border">
                  <td colSpan={5} className="py-2">
                    <Skeleton className="h-5" />
                  </td>
                </tr>
              ))
            : users.map(u => (
                <tr key={u.id} className="border-b border-dashed border-border last:border-0">
                  <td className="py-2 pr-4 text-navy">{u.email}</td>
                  <td className="py-2 pr-4">
                    <Badge
                      variant="outline"
                      className={cn("text-[9px] px-1.5",
                        u.role === "admin"     ? "bg-destructive/10 border-destructive/30 text-destructive" :
                        u.role === "counselor" ? "bg-navy/10 border-navy/30 text-navy" :
                        "bg-secondary text-secondary-foreground border-transparent"
                      )}
                    >
                      {u.role}
                    </Badge>
                  </td>
                  <td className="py-2 pr-4">
                    <Badge
                      variant="outline"
                      className={cn("text-[9px] px-1.5",
                        u.plan === "paid"
                          ? "bg-orange/10 border-orange/30 text-orange"
                          : "bg-secondary text-secondary-foreground border-transparent"
                      )}
                    >
                      {u.plan}
                    </Badge>
                  </td>
                  <td className="py-2 pr-4 font-mono text-[10px] text-muted-foreground">
                    {u.credits_remaining}
                  </td>
                  <td className="py-2 text-[10px] text-muted-foreground">
                    {new Date(u.created_at).toLocaleDateString("fr-FR")}
                  </td>
                </tr>
              ))}
        </tbody>
      </table>

      {!loading && users.length === 0 && (
        <p className="text-center text-xs text-muted-foreground py-8">
          aucun utilisateur
        </p>
      )}
    </div>
    </>
  )
}
