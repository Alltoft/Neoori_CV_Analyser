import { NextRequest, NextResponse } from "next/server"
import { SESSION_COOKIE, signInRedirect } from "@/lib/sign-in-gate"
import { route, settingsFromEnv } from "@/lib/site"

export function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl

  // Which host serves the path comes first (subdomain split spec, decision
  // 37). DOMAIN is read per request from the container's environment, so a
  // domain change needs no rebuild (decision 21).
  const routed = route(req.headers.get("host"), pathname, search, settingsFromEnv(process.env))
  if (routed.kind === "redirect") {
    // 307, never 308: browsers keep a permanent redirect for ever, and the
    // root's role is provisional (decision 12). A same-host target goes out
    // as a relative Location.
    return NextResponse.redirect(new URL(routed.location, req.url), 307)
  }

  const to = signInRedirect(pathname, search, req.cookies.has(SESSION_COOKIE))
  if (to) return NextResponse.redirect(new URL(to, req.url))

  return NextResponse.next()
}

// Next 16 reads `config`, not `proxyConfig` — under the old name this matcher
// was ignored, so the proxy ran on every request including static assets.
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.png$).*)"],
}
