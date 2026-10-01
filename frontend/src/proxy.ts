import { NextRequest, NextResponse } from "next/server"

/** Routes that need an account. Gated at the edge so no page ever renders a
 *  form the user can fill and then lose at submit. */
const PROTECTED = ["/admin", "/conseiller", "/profil", "/voyage", "/espace", "/analyse"]

/** Where a signed-out visitor on these lands instead of /connexion. The
 *  analysis form is where new people arrive from the landing page, so it opens
 *  on signup — and the redirect survives the confirmation email, because it
 *  travels inside the link. */
const SIGNUP_FIRST = ["/analyse"]

export function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl

  if (!PROTECTED.some((p) => pathname.startsWith(p))) return NextResponse.next()

  // Presence only — the signature and the role are enforced server-side.
  const hasToken = req.cookies.has("access_token_cookie")
  if (!hasToken) {
    const url = req.nextUrl.clone()
    url.pathname = SIGNUP_FIRST.some((p) => pathname.startsWith(p)) ? "/inscription" : "/connexion"
    url.search = ""
    // pathname + search exactly as requested, never decoded or rebuilt: the
    // value is only ever used as a navigation target, and the pages that read
    // it back check it as given.
    url.searchParams.set("redirect", pathname + search)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

// Next 16 reads `config`, not `proxyConfig` — under the old name this matcher
// was ignored, so the proxy ran on every request including static assets.
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.png$).*)"],
}
