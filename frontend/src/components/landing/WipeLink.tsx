"use client"

import type { ReactNode } from "react"
import { AppLink } from "@/lib/site-context"

/** The landing's main button. The ∞ wipe (landings spec, decision 22) comes
 *  on top of this link; without JavaScript it stays a plain link. */
export function WipeLink({
  href,
  ring: _ring,
  className,
  children,
}: {
  href: string
  ring: "orange" | "peach"
  className?: string
  children: ReactNode
}) {
  return <AppLink href={href} className={className}>{children}</AppLink>
}
