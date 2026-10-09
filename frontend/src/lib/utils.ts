import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** The API's datetimes are naive UTC ISO strings, with no offset, and
 *  `new Date()` reads those as local time. A trailing `Z` or a `±hh:mm` /
 *  `±hhmm` offset is kept as it is; otherwise the string is taken as UTC. */
export function parseUtc(s: string): Date {
  return new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(s) ? s : `${s}Z`)
}

/** Copy text to clipboard. Falls back to a hidden textarea when the
 *  Clipboard API is unavailable (non-secure context, permission denied). */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    try {
      const ta = document.createElement("textarea")
      ta.value = text
      ta.style.position = "fixed"
      ta.style.opacity = "0"
      document.body.appendChild(ta)
      ta.select()
      const ok = document.execCommand("copy")
      document.body.removeChild(ta)
      return ok
    } catch {
      return false
    }
  }
}
