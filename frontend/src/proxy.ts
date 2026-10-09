import { NextRequest, NextResponse } from "next/server"

/** Routes that need an account. Gated at the edge so no page ever renders a
 *  screen the visitor cannot use without a session. Inside /analyse only the
 *  exact paths in PUBLIC are open. */
const PROTECTED = ["/admin", "/conseiller", "/profil", "/voyage", "/espace", "/analyse"]

/** Where a signed-out visitor on these lands instead of /connexion. A report,
 *  its waiting page and its unlock page are where new people arrive from a
 *  link or a mail, so they open on signup — and the redirect survives the
 *  confirmation email, because it travels inside the link. */
const SIGNUP_FIRST = ["/analyse"]

/** Open to signed-out visitors inside /analyse (four-doors spec, ruling 1):
 *  the form, the advisor-door confirmation, and /analyse itself (a redirect
 *  to the form). Exact paths: /analyse/<id>/* stays the owner's. */
const PUBLIC = ["/analyse", "/analyse/nouveau", "/analyse/envoyee"]

export function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl

  if (PUBLIC.includes(pathname)) return NextResponse.next()

  if (!PROTECTED.some((p) => pathname.startsWith(p))) return NextResponse.next()

  // Presence only — the signature and the role are enforced server-side.
  // backend/app/config.py JWT_ACCESS_COOKIE_NAME (subdomain split spec,
  // decision 25).
  const hasToken = req.cookies.has("neoori_access")
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
