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
  if (routed.kind === "rewrite") {
    // Each subdomain's landing lives at an internal path and is public: serve
    // it in place of "/", so the address stays cv.DOMAIN/ (landings spec,
    // decision 8). Next keeps a rewrite internal only while its target has
    // the server's own origin; otherwise it proxies it, and this proxy runs
    // again for /accueil/… and answers 307. req.url carries that origin when
    // the server binds 0.0.0.0, as the Dockerfile does. Bound to 127.0.0.1,
    // Next renames the host "localhost" in req.url alone, and every landing
    // turns into a 307.
    return NextResponse.rewrite(new URL(routed.path, req.url))
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
