"use client"

import { useCallback, useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { PromptVersion } from "@/types"

export default function PromptsPage() {
  const [versions, setVersions] = useState<PromptVersion[]>([])
  const [text, setText] = useState("")
  const [savedText, setSavedText] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rollingBackId, setRollingBackId] = useState<string | null>(null)

  const dirty = text !== savedText

  const loadData = useCallback(async () => {
    const [pv, ap] = await Promise.all([
      api.get<{ prompts: PromptVersion[] }>("/prompts/"),
      api.get<{ prompt: PromptVersion }>("/prompts/active").catch(() => ({ prompt: null })),
    ])
    setVersions(pv.prompts)
    const t = ap.prompt?.system_prompt_text ?? ""
    setText(t)
    setSavedText(t)
    setError(null)
  }, [])

  useEffect(() => {
    loadData()
      .catch(err => setError(err?.message ?? "Erreur de chargement"))
      .finally(() => setLoading(false))
  }, [loadData])

  const publish = async () => {
    if (!text.trim() || !dirty) return
    setSaving(true)
    setError(null)
    try {
      const activeVersion = versions.find(v => v.is_active)
      const lastLabel = activeVersion?.version_label ?? `v1.${new Date().toISOString().slice(0,10).replace(/-/g,"")}`
      const nextLabel = /^v\d+\.\d+$/.test(lastLabel)
        ? lastLabel.replace(/v(\d+)\.(\d+)/, (_, maj, min) => `v${maj}.${+min + 1}`)
        : `v1.${versions.length + 1}`
      await api.post("/prompts/", {
        version_label: nextLabel,
        system_prompt_text: text,
        activate: true,
      })
      await loadData()
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
      await loadData()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur lors du rollback")
    } finally {
      setRollingBackId(null)
    }
  }

  const activeVersion = versions.find(v => v.is_active)

  return (
    <div className="grid grid-cols-[1.4fr_1fr] gap-4">
      {/* Editor */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h2 id="prompt-editor-label" className="font-semibold text-sm">prompt système</h2>
            <p className="text-[10px] text-muted-foreground">
              éditable sans redéploiement · versionné · rollback possible
            </p>
          </div>
          {activeVersion && (
            <Badge className="bg-primary text-primary-foreground text-[10px]">
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
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 mt-3">
            {error}
          </div>
        )}

        <div className="flex gap-2 mt-3 items-center">
          <Button
            size="sm"
            className="text-xs h-7 bg-primary hover:bg-primary/90 text-primary-foreground"
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
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="font-semibold text-sm mb-3">historique des versions</h2>
        {loading ? (
          Array(4).fill(0).map((_, i) => <Skeleton key={i} className="h-10 mb-2" />)
        ) : versions.length === 0 ? (
          <p className="text-xs text-muted-foreground">aucune version</p>
        ) : (
          <div>
            {versions.map(v => (
              <div
                key={v.id}
                className="flex items-center gap-2 py-2 border-b border-dashed border-border last:border-0"
              >
                <span className="font-mono text-xs font-medium w-12">{v.version_label}</span>
                {v.is_active && (
                  <span className="text-[10px] text-muted-foreground">actif</span>
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
  )
}
