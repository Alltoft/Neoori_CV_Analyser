"use client"

import { useCallback, useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { PromptVersion } from "@/types"

type Path = "A" | "B"

export default function PromptsPage() {
  const [versions, setVersions] = useState<PromptVersion[]>([])
  const [path, setPath] = useState<Path>("A")
  const [text, setText] = useState("")
  const [savedText, setSavedText] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rollingBackId, setRollingBackId] = useState<string | null>(null)

  const dirty = text !== savedText

  const loadData = useCallback(async (p: Path) => {
    const [pv, ap] = await Promise.all([
      api.get<{ prompts: PromptVersion[] }>("/prompts/"),
      api.get<{ prompt: PromptVersion }>(`/prompts/active?path=${p}`).catch(() => ({ prompt: null })),
    ])
    setVersions(pv.prompts)
    const t = ap.prompt?.system_prompt_text ?? ""
    setText(t)
    setSavedText(t)
    setError(null)
  }, [])

  useEffect(() => {
    setLoading(true)
    loadData(path)
      .catch(err => setError(err?.message ?? "Erreur de chargement"))
      .finally(() => setLoading(false))
  }, [loadData, path])

  const publish = async () => {
    if (!text.trim() || !dirty) return
    setSaving(true)
    setError(null)
    try {
      const activeVersion = versions.find(v => v.is_active && (v.path ?? "A") === path)
      const suffix = path === "B" ? "-B" : ""
      const fallback = `v1.${new Date().toISOString().slice(0,10).replace(/-/g,"")}${suffix}`
      const lastLabel = activeVersion?.version_label ?? fallback
      const stripped = lastLabel.replace(/-[AB]$/, "")
      const bumped = /^v\d+\.\d+$/.test(stripped)
        ? stripped.replace(/v(\d+)\.(\d+)/, (_, maj, min) => `v${maj}.${+min + 1}`)
        : `v1.${versions.filter(v => (v.path ?? "A") === path).length + 1}`
      const nextLabel = `${bumped}${suffix}`
      await api.post("/prompts/", {
        version_label: nextLabel,
        system_prompt_text: text,
        path,
        activate: true,
      })
      await loadData(path)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur lors de la publication")
    } finally {
      setSaving(false)
    }
  }

  const rollback = async (id: string) => {
    setRollingBackId(id)
    try {
      setError(null)
      await api.post(`/prompts/${id}/rollback`, {})
      await loadData(path)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur lors du rollback")
    } finally {
      setRollingBackId(null)
    }
  }

  const activeVersion = versions.find(v => v.is_active && (v.path ?? "A") === path)
  const visibleVersions = versions.filter(v => (v.path ?? "A") === path)

  return (
    <>
    <div className="mb-5">
      <p className="font-mono text-[11px] tracking-[0.15em] uppercase text-orange">Administration</p>
      <h1 className="font-display font-bold text-2xl text-navy mt-1">prompts système</h1>
    </div>
    <div className="grid grid-cols-[1.4fr_1fr] gap-4">
      {/* Editor */}
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h2 id="prompt-editor-label" className="font-display font-bold text-sm text-navy">prompt système</h2>
            <p className="text-[10px] text-muted-foreground">
              éditable sans redéploiement · versionné · rollback possible
            </p>
            <div className="flex gap-1 mt-2">
              {(["A", "B"] as const).map(p => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPath(p)}
                  className={cn(
                    "px-2.5 py-1 rounded-full border text-[10px] font-mono uppercase tracking-widest transition-colors",
                    path === p
                      ? "bg-orange border-orange text-white"
                      : "bg-background border-border text-muted-foreground hover:border-orange/50 hover:text-orange",
                  )}
                >
                  chemin {p}
                </button>
              ))}
            </div>
          </div>
          {activeVersion && (
            <Badge className="bg-orange text-white text-[10px] font-mono">
              {activeVersion.version_label} · ACTIF
            </Badge>
          )}
        </div>

        {loading ? (
          <Skeleton className="h-72" />
        ) : (
          <Textarea
            id="prompt-editor"
            aria-labelledby="prompt-editor-label"
            value={text}
            onChange={e => setText(e.target.value)}
            className="min-h-[320px] font-mono text-xs bg-secondary resize-none"
            placeholder="Collez ici le texte complet du system prompt…"
          />
        )}

        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive mt-3">
            {error}
          </div>
        )}

        <div className="flex gap-2 mt-3 items-center">
          <Button
            variant="navy"
            size="sm"
            className="text-xs h-7"
            disabled={!dirty || saving || loading}
            onClick={publish}
          >
            {saving ? "publication…" : "publier nouvelle version"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-xs h-7"
            disabled={!dirty}
            onClick={() => setText(savedText)}
          >
            annuler
          </Button>
          <span className="text-[10px] text-muted-foreground ml-auto">
            traçabilité B2G : chaque analyse stocke la version utilisée
          </span>
        </div>
      </div>

      {/* Version history */}
      <div className="rounded-xl border border-border bg-card p-4">
        <h2 className="font-display font-bold text-sm text-navy mb-3">historique des versions</h2>
        {loading ? (
          Array(4).fill(0).map((_, i) => <Skeleton key={i} className="h-10 mb-2" />)
        ) : visibleVersions.length === 0 ? (
          <p className="text-xs text-muted-foreground">aucune version</p>
        ) : (
          <div>
            {visibleVersions.map(v => (
              <div
                key={v.id}
                className="flex items-center gap-2 py-2 border-b border-dashed border-border last:border-0"
              >
                <span className="font-mono text-xs font-medium w-12 text-navy">{v.version_label}</span>
                {v.is_active && (
                  <span className="inline-flex items-center rounded-md bg-peach-soft px-1.5 py-0.5 text-[10px] font-mono text-orange-dark">actif</span>
                )}
                <span className="text-[10px] text-muted-foreground flex-1">
                  {v.author ?? "—"} · {new Date(v.created_at).toLocaleDateString("fr-FR")}
                </span>
                {!v.is_active && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-[10px] h-6 px-2"
                    disabled={rollingBackId !== null}
                    onClick={() => rollback(v.id)}
                  >
                    {rollingBackId === v.id ? "…" : "rollback"}
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
    </>
  )
}
