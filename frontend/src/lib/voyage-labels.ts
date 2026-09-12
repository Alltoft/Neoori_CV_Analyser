/**
 * French display labels for the counselor synthesis sheet.
 *
 * The scoring API returns its vocabulary as ASCII snake_case keys and bare axis
 * ids (contracts § B.5: "conscienciosite", "autonomie", "A7"), and S0Score.axes
 * carries no labels at all — only tensions[] and top3[] do. The counselor
 * manual prints accented French for every one of them, so this file is that
 * display map.
 *
 * Mirrors backend/app/services/voyage/bank.py — AXES, RIASEC_UNIVERS, BIG5,
 * SDT, SCHWARTZ, STYLES, S4_SLOTS — and backend/app/services/voyage/scoring.py's
 * three level words (LEVEL_HIGH / LEVEL_MID / LEVEL_LOW).
 * backend/tests/test_voyage_counselor_labels.py reads this file as text and
 * fails when any of them drift.
 *
 * COUNSELOR SURFACE ONLY. Every string below is a framework name, a trait name
 * or a pole label. Spec decision 7: the person never sees a score, a trait name
 * or a framework name — so /voyage, /voyage/session/[n] and /voyage/portrait may
 * never import this module. The same test enforces that.
 */
import type { S4Score, S5Score } from "@/types/voyage"

/** The ten S0 bipolar axes, in axis-id order. Mirrors bank.AXES. */
export const AXIS_ROWS: { id: string; label: string; neg: string; pos: string }[] = [
  { id: "A1", label: "Mobilité territoriale", neg: "Ancrage local", pos: "Mobilité / international" },
  { id: "A2", label: "Visibilité", neg: "Discrétion", pos: "Reconnaissance publique" },
  { id: "A3", label: "Rapport au collectif", neg: "Indépendance / solo", pos: "Collectif / équipe" },
  { id: "A4", label: "Échelle d'impact", neg: "Impact local", pos: "Impact global / systémique" },
  { id: "A5", label: "Sécurité vs risque", neg: "Stabilité / salariat", pos: "Risque / entrepreneuriat" },
  { id: "A6", label: "Type de création", neg: "Organisation / méthode", pos: "Expression libre" },
  { id: "A7", label: "Nature du lien", neg: "Systèmes / idées", pos: "Lien humain direct" },
  { id: "A8", label: "Temporalité de l'impact", neg: "Long terme / différé", pos: "Impact immédiat / visible" },
  { id: "A9", label: "Rapport au corps", neg: "Sédentaire / bureau", pos: "Terrain / action physique" },
  { id: "A10", label: "Transmission vs expertise", neg: "Expertise individuelle", pos: "Transmission / enseigner" },
]

/** Tie-break order R I A S E C. Mirrors bank.RIASEC_LETTERS + RIASEC_UNIVERS. */
export const RIASEC_ROWS: { letter: string; univers: string }[] = [
  { letter: "R", univers: "Réaliste" },
  { letter: "I", univers: "Investigateur" },
  { letter: "A", univers: "Artistique" },
  { letter: "S", univers: "Social" },
  { letter: "E", univers: "Entreprenant" },
  { letter: "C", univers: "Conventionnel" },
]

/** Mirrors bank.BIG5, in that order — the manual prints them left to right. */
export const BIG5_ROWS: { key: string; label: string }[] = [
  { key: "ouverture", label: "Ouverture" },
  { key: "conscienciosite", label: "Conscienciosité" },
  { key: "extraversion", label: "Extraversion" },
  { key: "agreabilite", label: "Agréabilité" },
  { key: "nevrotisme", label: "Névrotisme" },
]

/** The three Big Five level words scoring.py prints into S3Score.levels — not
 *  a key→label map like the rows above it: scoring.py already returns these
 *  words directly, so they are pinned here as literals, one-to-one with the
 *  Python names, so a text-parity test can still catch a drift.
 *  Mirrors backend/app/services/voyage/scoring.py LEVEL_HIGH / LEVEL_MID / LEVEL_LOW. */
export const LEVEL_HIGH = "Élevé"
export const LEVEL_MID = "Moyen"
export const LEVEL_LOW = "Faible"

/** Mirrors bank.SDT. */
export const SDT_ROWS: { key: string; label: string }[] = [
  { key: "autonomie", label: "Autonomie" },
  { key: "appartenance", label: "Appartenance" },
  { key: "competence", label: "Compétence" },
]

/** Mirrors bank.SCHWARTZ — the eleven values the manual's Dimension column uses. */
export const SCHWARTZ_LABELS: Record<string, string> = {
  autodirection: "Auto-direction",
  stimulation: "Stimulation",
  hedonisme: "Hédonisme",
  reussite: "Réussite",
  pouvoir: "Pouvoir",
  securite: "Sécurité",
  conformite: "Conformité",
  bienveillance: "Bienveillance",
  universalisme: "Universalisme",
  integrite: "Intégrité",
  conservation: "Conservation",
}

/** Mirrors bank.STYLES. */
export const STYLE_LABELS: Record<string, string> = {
  holistique: "Holistique",
  sequentiel: "Séquentiel",
  adaptatif: "Adaptatif",
  consultatif: "Consultatif",
}

/** The manual's « Synthèse environnementale » box. Its four printed cells come
 *  first (S4-1, S4-2, S4-3, S4-5); S4-4 and S4-6 follow, because the paper sheet
 *  has no room for them and the scorer returns all six. */
export const S4_ROWS: { key: keyof S4Score; label: string }[] = [
  { key: "espace", label: "Espace physique idéal (S4-1)" },
  { key: "rythme", label: "Rythme & chronotype (S4-2)" },
  { key: "equipe", label: "Configuration d'équipe (S4-3)" },
  { key: "irritant", label: "Ce qui épuise (S4-5)" },
  { key: "manager", label: "Le manager idéal (S4-4)" },
  { key: "vendredi", label: "Le vendredi soir (S4-6)" },
]

/** The manual's « Synthèse Risque & Sens » box, S5-1 through S5-7. */
export const S5_ROWS: { key: keyof S5Score; label: string }[] = [
  { key: "risque", label: "Appétence au risque (S5-1)" },
  { key: "rapport_echec", label: "L'échec possible (S5-2)" },
  { key: "rapport_flou", label: "Le flou (S5-3)" },
  { key: "valeur_centrale", label: "Valeur centrale (S5-4)" },
  { key: "trace", label: "Type d'impact voulu (S5-5)" },
  { key: "sacrifice", label: "Sacrifice accepté (S5-6)" },
  { key: "vivant", label: "Moment où le jeune se sent vivant(e) (S5-7)" },
]

/** Profile brackets, for the counselor sheet's key-facts strip. Mirrors
 *  backend/app/models/profile.py AGE_BRACKETS / SITUATIONS and the labels
 *  frontend/src/app/profil/page.tsx:36-52 already shows the candidate. */
export const TRANCHE_LABELS: Record<string, string> = {
  moins_25: "Moins de 25 ans",
  "25_34": "25 – 34 ans",
  "35_44": "35 – 44 ans",
  "45_54": "45 – 54 ans",
  "55_plus": "55 ans et plus",
}

export const SITUATION_LABELS: Record<string, string> = {
  en_recherche: "En recherche d'emploi",
  en_reconversion: "En reconversion",
  en_poste_evolution: "En poste, je souhaite évoluer",
  premiere_insertion: "Première insertion",
  reprise_apres_pause: "En reprise après une pause",
}
