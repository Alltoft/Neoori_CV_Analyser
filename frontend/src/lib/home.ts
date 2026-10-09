import type { AppName } from "./site"
import type { User } from "@/types"

/**
 * Where a signed-in person belongs, on the host they are on. Two places rely
 * on this agreeing: the app bar's logo, and where the sign-in pages send
 * someone who did not arrive with a ?redirect=. An admin or an approved
 * conseiller has no use for the candidate espace, and their menu is trimmed
 * to match — so the logo has to lead home, or they land somewhere with no
 * way back.
 *
 * A candidate's home is /espace on cv and the voyage hub on voyage (subdomain
 * split spec, decision 15). backend/app/routes/auth_oauth.py _home_path says
 * the same for a Google/Microsoft sign-in: keep the two in step.
 *
 * A pending, rejected or revoked conseiller is role "candidate" by design and
 * correctly gets the candidate home.
 */
export function homeFor(role: User["role"] | undefined, app: AppName): string {
  if (role === "admin") return "/admin"
  if (role === "counselor") return "/conseiller"
  return app === "voyage" ? "/voyage" : "/espace"
}
