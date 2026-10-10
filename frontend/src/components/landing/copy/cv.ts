import { typeset } from "../../../lib/typeset.ts"
import type { CvCopy } from "./types"

/** Every visible string of the cv. landing (landings spec, decision 32). The
 *  PM reviews this file; the spec's Appendix A was its first version. Write
 *  plain spaces and typographic apostrophes (’): typeset() sets the French
 *  no-break spaces. */
export const cvCopy = typeset<CvCopy>({
  // « Tarifs » stays hidden, in the page and in the menu, until the PM agrees (decision 16).
  showPrices: false,
  meta: {
    title: "Analyse de CV face à une cible",
    description:
      "Un métier, une formation, un poste ou un projet : neoori lit le CV face à ce qui est visé et montre les forces, ce qui reste à renforcer et par où avancer. Gratuit pour commencer.",
    ogAlt: "J’ai une cible · Lire un parcours face à sa cible.",
  },
  nav: {
    links: [
      { href: "/#comment", label: "Comment ça marche" },
      { href: "/#conseillers", label: "Pour les conseillers" },
      { href: "/#tarifs", label: "Tarifs", pricesOnly: true },
      { href: "/#questions", label: "Questions" },
    ],
    signIn: "Se connecter",
    myHome: "Mon espace",
    cross: { app: "voyage", label: "Le voyage" },
    openMenu: "Ouvrir le menu",
    closeMenu: "Fermer le menu",
    home: "neoori, accueil",
  },
  hero: {
    label: "J’ai une cible",
    title: "Lire un parcours face à sa cible.",
    sub: "Un métier, une formation, un poste, un projet : neoori lit le CV face à ce qui est visé, et montre les forces, ce qui reste à renforcer et par où avancer.",
    primary: { label: "Analyser mon CV", note: "Gratuit pour commencer, avec ou sans compte.", href: "/analyse/nouveau" },
    secondary: { label: "Je suis conseiller", note: "Vos codes, et les rapports qui vous reviennent.", href: "#conseillers" },
  },
  report: {
    title: "Ce que contient le rapport",
    intro: "Commencez gratuitement : §1 à §3 et un verdict. Le reste s’ajoute quand vous le souhaitez.",
    tiers: {
      free: { name: "Pour commencer", tag: "Gratuit" },
      complet: { name: "Rapport complet", tag: "Complet" },
      premium: { name: "En plus", tag: "Premium" },
    },
  },
  how: {
    title: "Comment ça marche",
    items: [
      { title: "Votre CV", text: "En PDF (10 Mo au plus) ou en texte collé." },
      {
        title: "Votre cible",
        text: "Un métier, une formation, un poste ou un projet, décrit avec vos mots. Une offre, une fiche métier ou un programme en main ? Collez-le.",
      },
      { title: "Votre lecture", text: "En quelques minutes : vos forces, ce qui reste à renforcer, et par où avancer." },
    ],
  },
  ways: {
    title: "Quatre façons de commencer",
    intro: "Vous choisissez au moment de lancer l’analyse.",
    items: [
      { title: "Avec votre compte", text: "La version gratuite, puis le rapport complet si vous le souhaitez. Vos analyses restent dans votre espace." },
      { title: "Avec un code promo", text: "Le rapport complet, une fois par compte." },
      {
        title: "Avec un code conseiller",
        text: "Le rapport complet, sans créer de compte. Il est remis à votre conseiller, et vous le découvrez ensemble.",
      },
      { title: "Sans compte", text: "La version gratuite, sur un lien privé valable 30 jours." },
    ],
  },
  advisors: {
    label: "Pour les conseillers",
    title: "Proposez l’analyse aux personnes que vous accompagnez.",
    points: [
      "Des codes à remettre, pour une analyse ou pour un voyage.",
      "Avec votre code, le rapport complet arrive dans votre espace conseiller, et nulle part ailleurs.",
      "Une note privée sur chaque analyse, visible de vous uniquement.",
      "Pour toute cible : un métier, une formation, un poste, un projet.",
    ],
    signup: { href: "/inscription-conseiller", label: "Créer un compte conseiller" },
    signin: { href: "/connexion", label: "Se connecter" },
  },
  prices: {
    title: "Tarifs",
    intro: "Paiement unique, sans abonnement.",
    plans: [
      { name: "Gratuit", price: "0 €", text: "§1 à §3 et un verdict." },
      { name: "Complet", price: "9 €", text: "Le rapport complet, §1 à §9." },
      { name: "Premium", price: "24 €", text: "Le rapport complet, plus la préparation à l’entretien (§10 et §11)." },
    ],
    note: "Vous passez au rapport complet depuis votre rapport gratuit, quand vous le souhaitez.",
  },
  data: {
    title: "Vos données",
    points: [
      "Votre CV et vos réponses servent à produire votre analyse.",
      "L’analyse est rédigée par une IA, à partir de votre CV et de votre cible.",
      "Vous pouvez supprimer une analyse à tout moment, depuis votre espace.",
      "Sans compte, le rapport s’efface de lui-même au bout de 30 jours.",
    ],
    link: { href: "/confidentialite", label: "Lire la politique de confidentialité" },
  },
  faq: {
    title: "Questions",
    items: [
      {
        q: "Ma cible n’est pas un poste précis. Est-ce que ça marche ?",
        a: "Oui. Une cible peut être un métier, une formation, un poste ou un projet. Décrivez-la avec vos mots ; une offre, une fiche métier ou un programme de formation aide aussi.",
      },
      {
        q: "Faut-il créer un compte ?",
        a: "Non. Sans compte, vous recevez la version gratuite sur un lien privé valable 30 jours. Avec un compte, vos analyses restent dans votre espace et vous pouvez passer au rapport complet.",
      },
      {
        q: "Que se passe-t-il avec un code conseiller ?",
        a: "Le rapport complet est remis à votre conseiller, pas à vous. Vous le découvrez ensemble, en rendez-vous.",
      },
      { q: "Combien de temps faut-il ?", a: "Quelques minutes pour remplir le formulaire, puis quelques minutes pour l’analyse." },
      {
        q: "Qui rédige l’analyse ?",
        a: "Une IA, à partir de votre CV, de votre cible et de vos réponses. Elle ne remplace pas un conseiller : elle prépare l’échange.",
      },
      {
        q: "Puis-je supprimer mon analyse ?",
        a: "Oui, depuis votre espace, à tout moment. Sans compte, elle s’efface d’elle-même au bout de 30 jours.",
      },
      {
        q: "Je n’ai pas encore de cible.",
        a: "Commencez par le voyage : six étapes pour poser ce que vous savez déjà de vous.",
        link: { app: "voyage", label: "Découvrir le voyage" },
      },
    ],
  },
  final: {
    title: "Votre parcours a des choses à dire.",
    bridge: { text: "Pas encore de cible ? Le voyage vous aide à la trouver.", link: { app: "voyage", label: "Découvrir le voyage" } },
  },
})
