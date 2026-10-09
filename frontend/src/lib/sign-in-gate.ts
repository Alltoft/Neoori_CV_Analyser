/**
 * The proxy's sign-in gate, as a pure function (moved out of proxy.ts by the
 * subdomain split so `node --test` can load it). Presence only: the
 * signature and the role are enforced server-side.
 */

/** The session cookie: backend/app/config.py JWT_ACCESS_COOKIE_NAME. Keep
 *  the two in step. */
export const SESSION_COOKIE = "neoori_access"

/** Routes that need an account. Gated at the edge so no page ever renders a
 *  screen the visitor cannot use without a session. Inside /analyse only the
 *  exact paths in PUBLIC are open. */
const PROTECTED = ["/admin", "/conseiller", "/profil", "/voyage", "/espace", "/analyse"]

/** Where a signed-out visitor on these lands instead of /connexion. A report,
 *  its waiting page and its unlock page are where new people arrive from a
 *  link or a mail, so they open on signup — and the redirect survives the
 *  confirmation email, because it travels inside the link. */
const SIGNUP_FIRST = ["/analyse"]

/** The voyage hub, exact: voyage.DOMAIN/ lands there, so new people arrive on
 *  it, as they did on the analysis form before four doors (subdomain split
 *  spec, decision 14). Deeper voyage pages keep /connexion. */
const SIGNUP_FIRST_EXACT = ["/voyage"]

/** Open to signed-out visitors inside /analyse (four-doors spec, ruling 1):
 *  the form, the advisor-door confirmation, and /analyse itself (a redirect
 *  to the form). Exact paths: /analyse/<id>/* stays the owner's. */
const PUBLIC = ["/analyse", "/analyse/nouveau", "/analyse/envoyee"]

/** Where to send a request, or null to let it through. `redirect` carries
 *  pathname + search exactly as requested, never decoded or rebuilt: the
 *  value is only ever used as a navigation target, and the pages that read it
 *  back check it as given. */
export function signInRedirect(pathname: string, search: string, signedIn: boolean): string | null {
  if (signedIn || PUBLIC.includes(pathname)) return null
  if (!PROTECTED.some((p) => pathname.startsWith(p))) return null
  const signupFirst =
    SIGNUP_FIRST.some((p) => pathname.startsWith(p)) || SIGNUP_FIRST_EXACT.includes(pathname)
  const query = new URLSearchParams({ redirect: pathname + search })
  return `${signupFirst ? "/inscription" : "/connexion"}?${query}`
}
