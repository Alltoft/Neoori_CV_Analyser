import * as React from "react"
import { Plus } from "lucide-react"
import { cn } from "@/lib/utils"

/** Lightweight, JS-free FAQ accordion built on native <details> (accessible by default). */
export function Accordion({
  items,
  className,
}: {
  items: { q: React.ReactNode; a: React.ReactNode }[]
  className?: string
}) {
  return (
    <div className={cn("divide-y divide-border overflow-hidden rounded-2xl bg-card ring-1 ring-foreground/10", className)}>
      {items.map((it, i) => (
        <details key={i} className="group/acc px-5 sm:px-6">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 font-display text-[15px] font-semibold text-navy [&::-webkit-details-marker]:hidden">
            {it.q}
            <Plus className="size-4 shrink-0 text-orange transition-transform duration-200 group-open/acc:rotate-45" />
          </summary>
          <div className="-mt-1 pb-5 text-sm leading-relaxed text-muted-foreground">{it.a}</div>
        </details>
      ))}
    </div>
  )
}
