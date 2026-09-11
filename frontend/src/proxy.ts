import { NextRequest, NextResponse } from "next/server"

/** Routes that need an account. Gated at the edge so no page ever renders a
 *  form the user can fill and then lose at submit. */
const PROTECTED = ["/admin", "/profil", "/voyage"]

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl

  if (!PROTECTED.some((p) => pathname.startsWith(p))) return NextResponse.next()

  // Presence only — the signature and the role are enforced server-side.
  const hasToken = req.cookies.has("access_token_cookie")
  if (!hasToken) {
    const url = req.nextUrl.clone()
    url.pathname = "/connexion"
    url.searchParams.set("redirect", pathname)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

// Next 16 reads `config`, not `proxyConfig` — under the old name this matcher
// was ignored, so the proxy ran on every request including static assets.
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.png$).*)"],
}
