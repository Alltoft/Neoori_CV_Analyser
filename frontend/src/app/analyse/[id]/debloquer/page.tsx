"use client"

import { useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { AppBar } from "@/components/layout/AppBar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { CheckCircle2, Circle } from "lucide-react"
import { SECTION_TITLES } from "@/types"

const FREE  = ["1","2","3","4"]
const PAID  = ["5","6","7","8","9"]

export default function DebloquerPage() {
  const { id } = useParams<{ id: string }>()
  const [code, setCode] = useState("")

  return (
    <div className="min-h-screen bg-background">
      <AppBar />
      <div className="max-w-[1000px] mx-auto px-8 py-10">
        <div className="flex items-baseline justify-between mb-2">
          <h1 className="text-2xl font-bold">Débloquer le livrable complet</h1>
          <Badge variant="outline" className="font-mono text-xs">v1.3 · bêta</Badge>
        </div>
        <p className="text-sm text-muted-foreground mb-8">
          Vous avez vu les 4 premières sections. Les 5 suivantes sont la partie actionnable.
        </p>

        <div className="grid grid-cols-2 gap-6">
          {/* Free card */}
          <div className="rounded-lg border border-border bg-card p-6">
            <p className="font-semibold text-sm">gratuit</p>
            <p className="text-4xl font-bold mt-2">0 €</p>
            <p className="text-xs text-muted-foreground">version d'essai · 1 analyse</p>
            <Separator className="my-4" />
            <ul className="space-y-2">
              {FREE.map(n => (
                <li key={n} className="flex items-center gap-2 text-xs">
                  <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0" />
                  § {n} · {SECTION_TITLES[n]}
                </li>
              ))}
              {PAID.map(n => (
                <li key={n} className="flex items-center gap-2 text-xs text-muted-foreground line-through">
                  <Circle className="h-3.5 w-3.5 shrink-0 opacity-30" />
                  § {n} · {SECTION_TITLES[n]}
                </li>
              ))}
            </ul>
          </div>

          {/* Paid card */}
          <div className="rounded-lg border-2 border-primary bg-primary text-primary-foreground p-6 relative">
            <Badge className="absolute -top-3 right-5 bg-background text-foreground border border-border text-[10px]">
              recommandé
            </Badge>
            <p className="font-semibold text-sm">complet</p>
            <div className="flex items-baseline gap-2">
              <p className="text-4xl font-bold mt-2">9 €</p>
              <span className="text-sm opacity-80">une fois · sans abonnement</span>
            </div>
            <p className="text-xs opacity-80">livrable 9 sections + CV retravaillé + export conseiller</p>
            <Separator className="my-4 opacity-30" />
            <ul className="space-y-2 mb-5">
              {[...FREE,...PAID].map(n => (
                <li key={n} className="flex items-center gap-2 text-xs">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 opacity-70" />
                  § {n} · {SECTION_TITLES[n]}
                </li>
              ))}
            </ul>
            <Button className="w-full bg-background text-primary hover:bg-background/90 font-semibold">
              débloquer pour 9 € →
            </Button>
            <p className="text-[10px] opacity-75 text-center mt-2">
              code conseiller — gratuit pour les bénéficiaires Cap Emploi / France Travail
            </p>
          </div>
        </div>

        {/* Counselor code input */}
        <div className="mt-6 rounded-lg border border-border bg-secondary p-4 flex items-center gap-4">
          <span className="font-medium text-sm shrink-0">déjà un code conseiller ?</span>
          <Input
            value={code}
            onChange={e => setCode(e.target.value)}
            placeholder="CAP-2026-XXXX-XXXX"
            className="font-mono text-sm flex-1 bg-background"
          />
          <Button variant="outline" size="sm">activer</Button>
        </div>

        <div className="mt-4">
          <Link href={`/analyse/${id}/rapport`} className="text-xs text-muted-foreground underline underline-offset-2">
            ← Retour au rapport
          </Link>
        </div>
      </div>
    </div>
  )
}
