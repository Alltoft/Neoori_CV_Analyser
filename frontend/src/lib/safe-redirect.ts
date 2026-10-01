/**
 * Validates a `?redirect=` value before a page navigates to it or hands it to
 * the server as the confirmation link's landing page.
 *
 * The value is judged exactly as it arrives, character for character: it is
 * never decoded, normalised or rebuilt through `new URL(...)`, because every
 * one of those steps is a place where "/safe" can turn into "//evil.example".
 * Accepted: a string that starts with "/" and not with "//" (protocol-relative)
 * or "/\" (browsers read the backslash as a slash). Anything else, including a
 * missing value, is null, and the caller falls back to its own default.
 *
 * Control characters are refused too. A browser drops tab and newline from a
 * URL before parsing it, so "/<TAB>/evil.example" starts like a path and
 * resolves as "//evil.example". Rejecting them reads the string as given and
 * rewrites nothing.
 */
export function safeRedirect(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null
  if (!value.startsWith("/")) return null
  if (value.startsWith("//") || value.startsWith("/\\")) return null
  for (let i = 0; i < value.length; i++) {
    const c = value.charCodeAt(i)
    if (c < 0x20 || c === 0x7f) return null
  }
  return value
}
