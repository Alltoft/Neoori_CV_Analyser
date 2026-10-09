"use client"

import { useEffect, useState } from "react"

/** Mirrors auth_mail.COOLDOWN on the server: one account mail a minute. */
export const COOLDOWN_S = 60

/** The « Renvoyer » countdown every account-mail screen shows: seconds left
 *  before another mail may be asked for. restart() starts a new minute. */
export function useCooldown(running: boolean) {
  const [wait, setWait] = useState(running ? COOLDOWN_S : 0)

  useEffect(() => {
    if (wait <= 0) return
    const t = setTimeout(() => setWait((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [wait])

  return { wait, restart: () => setWait(COOLDOWN_S) }
}
