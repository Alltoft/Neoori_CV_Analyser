import * as React from "react"

import { cn } from "@/lib/utils"

/** A form block, numbered or not. The analysis forms number their steps
 *  because they are walked in order; the profile does not, because its blocks
 *  are answered elsewhere and it exists to change one of them. */
function SectionCard({
  n,
  title,
  hint,
  className,
  children,
}: {
  n?: number | string
  title: string
  hint?: React.ReactNode
  className?: string
  children: React.ReactNode
}) {
  return (
    <div
      data-slot="section-card"
      className={cn("rounded-2xl bg-card p-5 ring-1 ring-foreground/10 shadow-soft sm:p-6", className)}
    >
      <div className="mb-1 flex items-center gap-2.5">
        {n !== undefined && (
          <span className="grid size-6 shrink-0 place-items-center rounded-md bg-orange-dark font-mono text-[11px] font-bold text-white">
            {n}
          </span>
        )}
        <h2 className="font-display text-base font-semibold text-navy">{title}</h2>
      </div>
      {hint && (
        <div className={cn("mb-3 text-xs text-muted-foreground", n !== undefined && "pl-[2.1rem]")}>
          {hint}
        </div>
      )}
      <div className={hint ? "" : "mt-3"}>{children}</div>
    </div>
  )
}

export { SectionCard }
