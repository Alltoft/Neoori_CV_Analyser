export const LOGO_PLAYED_KEY = "neoori:logo-played"

/** Whether the landing's logo plays motion A now (landings spec, decision
 *  19): once per tab session, never under reduce motion. Blocked storage
 *  (private windows, some in-app browsers) plays and remembers nothing. */
export function shouldPlayLogo(
  storage: Pick<Storage, "getItem" | "setItem"> | null,
  reducedMotion: boolean,
): boolean {
  if (reducedMotion) return false
  if (!storage) return true
  try {
    if (storage.getItem(LOGO_PLAYED_KEY) === "1") return false
    storage.setItem(LOGO_PLAYED_KEY, "1")
  } catch {
    // Storage refused: play, remember nothing.
  }
  return true
}
