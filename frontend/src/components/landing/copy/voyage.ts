import { typeset } from "../../../lib/typeset.ts"
import type { VoyageCopy } from "./types"

/** Every visible string of the voyage. landing (landings spec, decision 32).
 *  The PM reviews this file; the spec's Appendix A was its first version.
 *  Write plain spaces and typographic apostrophes (’): typeset() sets the
 *  French no-break spaces. */
export const voyageCopy = typeset<VoyageCopy>({
  meta: {
    title: "Le voyage, du brouillard à la clarté",
    description:
      "Six étapes pour poser ce que vous savez déjà de vous : la première en cinq minutes, en autonomie, les cinq suivantes avec un conseiller. Puis un portrait, relu ensemble.",
    ogAlt: "Le voyage · Du brouillard à la clarté, une étape après l’autre.",
  },
  nav: {
    links: [
      { href: "/#etapes", label: "Les six étapes" },
      { href: "/#conseillers", label: "Pour les conseillers" },
      { href: "/#questions", label: "Questions" },
    ],
    signIn: "Se connecter",
    myHome: "Mon espace",
    cross: { app: "cv", label: "J’ai une cible" },
    openMenu: "Ouvrir le menu",
    closeMenu: "Fermer le menu",
    home: "neoori, accueil",
  },
  hero: {
    label: "Le voyage",
    title: "Du brouillard à la clarté, une étape après l’autre.",
    sub: "Six étapes pour poser ce que vous savez déjà de vous. La première se fait en cinq minutes, en autonomie ; les cinq suivantes, avec un conseiller.",
    primary: { label: "Commencer le voyage", note: "Session 0 : cinq minutes, en autonomie.", href: "/voyage" },
    secondary: { label: "Je suis conseiller", note: "Vos codes, les séances, le portrait à valider.", href: "#conseillers" },
    stepsLabel: "Les six étapes du voyage",
    steps: [
      { name: "Session 0", caption: "Dans 10 ans · cinq minutes, en autonomie" },
      { name: "Session 1", caption: "avec votre conseiller" },
      { name: "Session 2" },
      { name: "Session 3" },
      { name: "Session 4" },
      { name: "Session 5", caption: "puis le portrait, relu ensemble" },
    ],
  },
  take: {
    title: "Ce que vous emportez",
    items: [
      { title: "Votre phrase", text: "Dès la session 0, une première phrase sur vous, tirée de vos 20 réponses." },
      {
        title: "Votre portrait",
        text: "Après la session 5, un portrait en six parties : ce qui vous fait vibrer, ce dont vous avez besoin, les chemins possibles… Votre conseiller le relit et le valide avec vous avant de vous le remettre.",
      },
    ],
    note: "Ni note, ni score : le voyage décrit, il ne classe pas.",
  },
  how: {
    title: "Comment ça se passe",
    items: [
      { title: "Session 0, en autonomie", text: "Dans 10 ans : 20 affirmations, oui, non ou « – ». Cinq minutes." },
      {
        title: "Sessions 1 à 5, avec votre conseiller",
        text: "Votre conseiller vous donne un code qui ouvre les séances. Vous avancez d’une séance à l’autre, à votre rythme.",
      },
      { title: "Le portrait", text: "Rédigé à partir de vos réponses, relu et validé par votre conseiller, puis remis." },
      {
        title: "Et vos analyses",
        text: "Le voyage peut ensuite enrichir vos analyses de CV.",
        link: { app: "cv", label: "Découvrir J’ai une cible" },
      },
    ],
    note: "Un compte gratuit garde vos réponses d’une séance à l’autre.",
  },
  advisors: {
    label: "Pour les conseillers",
    title: "Accompagnez chaque voyage, séance après séance.",
    points: [
      "Votre code ouvre les sessions 1 à 5.",
      "Une fiche de suivi par voyage, visible de vous uniquement.",
      "Le portrait se relit ensemble et n’est remis qu’après votre validation.",
      "Le voyage peut ensuite nourrir les analyses de CV.",
    ],
    signup: { href: "/inscription-conseiller", label: "Créer un compte conseiller" },
    signin: { href: "/connexion", label: "Se connecter" },
  },
  data: {
    title: "Vos données",
    points: [
      "Vos réponses, votre phrase et votre portrait sont chiffrés.",
      "Votre phrase et le premier jet du portrait sont rédigés par une IA ; le portrait n’est remis qu’après la relecture de votre conseiller.",
      "Vous pouvez effacer votre voyage à tout moment. L’effacement retire aussi ce que vos analyses de CV en avaient repris.",
    ],
    link: { href: "/confidentialite", label: "Lire la politique de confidentialité" },
  },
  faq: {
    title: "Questions",
    items: [
      {
        q: "Faut-il un conseiller ?",
        a: "Pas pour la session 0 : elle se fait en autonomie, en cinq minutes. Les sessions 1 à 5 se font avec un conseiller, qui vous donne un code.",
      },
      {
        q: "Je n’ai pas de conseiller.",
        a: "Commencez par la session 0. Pour la suite, parlez-en à la structure qui vous accompagne : Mission Locale, Cap Emploi, France Travail ou un conseil en évolution professionnelle.",
      },
      {
        q: "Est-ce un test de personnalité ?",
        a: "Non. Le voyage ne vous classe pas et ne vous donne pas de score. Il vous aide à poser des mots sur ce que vous savez déjà.",
      },
      {
        q: "Combien de temps ça prend ?",
        a: "Cinq minutes pour la session 0. Pour les suivantes, le rythme se décide avec votre conseiller.",
      },
      { q: "Faut-il un compte ?", a: "Oui, pour garder vos réponses d’une séance à l’autre. La création du compte est gratuite." },
      {
        q: "Puis-je tout effacer ?",
        a: "Oui, à tout moment. L’effacement retire aussi ce que vos analyses de CV en avaient repris.",
      },
    ],
  },
  final: {
    title: "Votre parcours a des choses à dire. Aidez-le à les dire.",
    bridge: { text: "Vous avez déjà une cible ?", link: { app: "cv", label: "Analyser mon CV" } },
  },
})
