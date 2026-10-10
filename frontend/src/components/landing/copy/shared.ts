import { typeset } from "../../../lib/typeset.ts"
import type { FooterCopy } from "./types"

/** The landings' footer, also on the legal pages of cv. and voyage. (landings
 *  spec, decision 13). */
export const footerCopy = typeset<FooterCopy>({
  label: "Liens du pied de page",
  tagline: "Pour les conseillers et les personnes qu’ils accompagnent.",
  apps: [
    { app: "cv", label: "J’ai une cible" },
    { app: "voyage", label: "Le voyage" },
  ],
  links: [
    { href: "/mentions-legales", label: "Mentions légales" },
    { href: "/confidentialite", label: "Confidentialité" },
    { href: "/cgv", label: "CGV" },
  ],
  signIn: { href: "/connexion", label: "Se connecter" },
  copyright: "© 2026 neoori",
})
