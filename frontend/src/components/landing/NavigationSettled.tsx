"use client"

import { usePathname } from "next/navigation"
import { useLayoutEffect } from "react"
import { settleNavigation } from "@/lib/nav-settle"

/** Tells a waiting ∞ wipe that the new page is in the DOM (landings spec,
 *  decision 22). Mounted once, in the root layout; renders nothing. */
export function NavigationSettled() {
  const pathname = usePathname()
  useLayoutEffect(() => {
    settleNavigation()
  }, [pathname])
  return null
}
