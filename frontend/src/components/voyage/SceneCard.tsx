"use client"

import { OptionCard } from "@/components/voyage/OptionCard"
import type { BankScene } from "@/types/voyage"

/**
 * One scene, one screen. Title, subtitle, narrative, question and options are
 * the cahier's own text (tutoiement), served by GET /api/voyage/bank and
 * rendered verbatim — spec decision 15.
 */
export function SceneCard({
  scene,
  value,
  disabled,
  onSelect,
}: {
  scene: BankScene
  value?: string
  disabled?: boolean
  onSelect: (letter: string) => void
}) {
  return (
    <article className="overflow-hidden rounded-2xl bg-card shadow-soft ring-1 ring-foreground/10">
      <div className="voyage-rule" />
      <div className="p-5 sm:p-6">
        <h2 className="font-display text-xl font-bold leading-tight text-navy">{scene.title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{scene.subtitle}</p>

        {scene.narrative.length > 0 && (
          <div className="mt-4 space-y-2.5 rounded-xl bg-secondary/60 p-4">
            {scene.narrative.map((paragraph, i) => (
              <p key={i} className="text-sm leading-relaxed text-navy-700">{paragraph}</p>
            ))}
          </div>
        )}

        <p className="mt-5 font-display text-base font-semibold text-navy">{scene.question}</p>

        <div className="mt-3 space-y-2">
          {scene.options.map((o) => (
            <OptionCard
              key={o.letter}
              letter={o.letter}
              label={o.label}
              text={o.text}
              selected={value === o.letter}
              disabled={disabled}
              onSelect={() => onSelect(o.letter)}
            />
          ))}
        </div>
      </div>
    </article>
  )
}
