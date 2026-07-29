/**
 * Bloc 5 — the eight condition families.
 *
 * Values mirror `backend/app/models/profile.py` exactly; the backend drops any
 * family or state it doesn't recognise, so a drift here silently loses answers
 * rather than erroring.
 */

export type ConditionState = "me_convient" | "possible_avec_adaptation" | "a_eviter"

export interface ConditionEntry {
  state?: ConditionState
  point_fort: boolean
}

export type ConditionsValue = Record<string, ConditionEntry>

export const CONDITION_STATES: {
  value: ConditionState
  label: string
  short: string
}[] = [
  { value: "me_convient", label: "Me convient", short: "Me convient" },
  { value: "possible_avec_adaptation", label: "Possible avec une adaptation", short: "Avec adaptation" },
  { value: "a_eviter", label: "À éviter", short: "À éviter" },
]

export const CONDITION_FAMILIES: {
  value: string
  label: string
  examples: string
}[] = [
  { value: "rythme", label: "Rythme", examples: "horaires réguliers, variables, tôt le matin, de nuit, saisonnier" },
  { value: "environnement", label: "Environnement", examples: "lieu calme, lieu animé, espace partagé, extérieur" },
  { value: "deplacements", label: "Déplacements", examples: "trajets longs, déplacements fréquents, conduite" },
  { value: "effort_physique", label: "Effort physique", examples: "station debout, port de charges, gestes répétitifs" },
  { value: "attention", label: "Attention", examples: "plusieurs tâches à la fois, interruptions, délais courts, concentration longue" },
  { value: "relation", label: "Relation", examples: "contact public, équipe, autonomie, prise de parole" },
  { value: "consignes", label: "Consignes", examples: "écrites, orales, apprentissage par la pratique" },
  { value: "organisation", label: "Organisation", examples: "planning à l'avance, imprévus, autonomie d'organisation" },
]

/**
 * Families where tolerating the requirement genuinely differentiates a
 * candidate. Kept in sync with DIFFERENTIATING in the backend model — the
 * report only valorises a point fort on one of these.
 */
const DIFFERENTIATING = new Set(["rythme", "environnement", "deplacements", "effort_physique"])

export interface ConditionsSummary {
  points_forts: string[]
  me_convient: string[]
  possible_avec_adaptation: string[]
  a_eviter: string[]
}

const labelOf = (value: string) =>
  CONDITION_FAMILIES.find((f) => f.value === value)?.label ?? value

/**
 * What the profile already says — the live synthesis under the form.
 *
 * Mirrors `prompt_context()` on the backend: « me convient » is never a
 * strength, and a point fort only counts on a demanding requirement. Showing
 * the user a "point fort" the report would then ignore would be a lie.
 */
export function summarize(value: ConditionsValue): ConditionsSummary {
  const out: ConditionsSummary = {
    points_forts: [],
    me_convient: [],
    possible_avec_adaptation: [],
    a_eviter: [],
  }

  for (const family of CONDITION_FAMILIES) {
    const entry = value[family.value]
    if (!entry) continue
    if (entry.point_fort && DIFFERENTIATING.has(family.value)) {
      out.points_forts.push(labelOf(family.value))
    }
    if (entry.state === "me_convient") out.me_convient.push(labelOf(family.value))
    else if (entry.state === "possible_avec_adaptation") out.possible_avec_adaptation.push(labelOf(family.value))
    else if (entry.state === "a_eviter") out.a_eviter.push(labelOf(family.value))
  }

  return out
}
