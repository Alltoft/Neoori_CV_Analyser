import type { User } from "@/types"
import type { LinkCopy } from "../components/landing/copy/types"
import type { AppName } from "./site"
import { homeFor } from "./home.ts"

/** The menu's account entry (landings spec, decision 11): « Mon espace »,
 *  leading to the person's home on this host by role, once signed in;
 *  « Se connecter » otherwise. */
export function accountLink(
  role: User["role"] | null,
  app: AppName,
): { href: string; kind: "home" | "signin" } {
  return role ? { href: homeFor(role, app), kind: "home" } : { href: "/connexion", kind: "signin" }
}

/** The menu's section links, without « Tarifs » while prices are hidden
 *  (decision 16). */
export function visibleLinks(links: LinkCopy[], showPrices: boolean): LinkCopy[] {
  return links.filter((link) => showPrices || !link.pricesOnly)
}
