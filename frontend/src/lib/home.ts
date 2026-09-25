import type { User } from "@/types"

/**
 * Where a signed-in person belongs. Two places rely on this agreeing: the app
 * bar's logo, and where the login page sends someone who did not arrive with a
 * ?redirect=. An admin or an approved conseiller has no use for the candidate
 * espace, and their menu is trimmed to match — so the logo has to lead home,
 * or they land somewhere with no way back.
 *
 * A pending, rejected or revoked conseiller is role "candidate" by design and
 * correctly gets the candidate home.
 */
export function homeFor(role: User["role"] | undefined): string {
  if (role === "admin") return "/admin"
  if (role === "counselor") return "/conseiller"
  return "/espace"
}
