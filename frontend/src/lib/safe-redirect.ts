/** Same cap as the server's NEXT_MAX_LENGTH (backend/app/utils/auth_links.py). */
const MAX_LENGTH = 512

/** "." and ".." as a URL parser reads them, percent-encoded dots included. */
const DOT_SEGMENTS = new Set([".", "..", "%2e", ".%2e", "%2e.", "%2e%2e"])

/**
 * Validates a `?redirect=` value before a page navigates to it or hands it to
 * the server as the confirmation link's landing page.
 *
 * The value is judged exactly as it arrives, character for character: it is
 * never decoded, normalised or rebuilt through `new URL(...)`, because every
 * one of those steps is a place where "/safe" can turn into "//evil.example".
 * Accepted: a string that starts with "/" and not with "//" (protocol-relative)
 * or "/\" (browsers read the backslash as a slash), at most 512 characters.
 * Anything else, including a missing value, is null, and the caller falls back
 * to its own default. Same rules as the server's safe_next.
 *
 * Control characters are refused too. A browser drops tab and newline from a
 * URL before parsing it, so "/<TAB>/evil.example" starts like a path and
 * resolves as "//evil.example". Rejecting them reads the string as given and
 * rewrites nothing.
 *
 * So is any "." or ".." segment in the path part (before "?" or "#"). The
 * router resolves the href against the current URL, and "/..//evil.example"
 * comes out of that as the path "//evil.example": another host.
 */
export function safeRedirect(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null
  if (!value.startsWith("/")) return null
  if (value.startsWith("//") || value.startsWith("/\\")) return null
  if (value.length > MAX_LENGTH) return null
  for (let i = 0; i < value.length; i++) {
    const c = value.charCodeAt(i)
    if (c < 0x20 || c === 0x7f) return null
  }
  if (hasDotSegment(value)) return null
  return value
}

/** A backslash separates segments too: browsers read it as a slash. */
function hasDotSegment(value: string): boolean {
  const path = value.split(/[?#]/, 1)[0]
  return path.split(/[/\\]/).some((segment) => DOT_SEGMENTS.has(segment.toLowerCase()))
}
