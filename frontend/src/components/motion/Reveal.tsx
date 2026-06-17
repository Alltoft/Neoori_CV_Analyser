"use client"

import * as React from "react"
import { useReveal } from "@/lib/useReveal"
import { cn } from "@/lib/utils"

/** Fade-up on scroll-into-view. Content stays visible if JS is off (see .js .reveal). */
export function Reveal({
  children,
  className,
  delayMs,
}: {
  children: React.ReactNode
  className?: string
  delayMs?: number
}) {
  const ref = useReveal<HTMLDivElement>()
  return (
    <div ref={ref} className={cn("reveal", className)} style={delayMs ? { animationDelay: `${delayMs}ms` } : undefined}>
      {children}
    </div>
  )
}
