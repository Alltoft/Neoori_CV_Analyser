/** Option sets for the Profil de base. Values mirror
 *  `backend/app/models/profile.py`; the labels are the French the candidate
 *  reads.
 *
 *  One file because the blocks no longer live on one page. The questions are
 *  asked where the person already is — two at signup, the rest inside the
 *  voyage — and `/profil` is the edit surface for all of them. A label
 *  duplicated per surface is a label that drifts per surface.
 */

export interface Option {
  value: string
  label: string
}

/* ── Bloc 1 — Vous ─────────────────────────────────────────────────────────── */

/** Mirrors backend AGE_BRACKETS. Seven since the voyage brought school-age
 *  candidates in; 22–24 stops where 25–34 starts, so 25 sits in one bucket. */
export const TRANCHES_AGE: Option[] = [
  { value: "14_17", label: "14 – 17 ans" },
  { value: "18_21", label: "18 – 21 ans" },
  { value: "22_24", label: "22 – 24 ans" },
  { value: "25_34", label: "25 – 34 ans" },
  { value: "35_44", label: "35 – 44 ans" },
  { value: "45_54", label: "45 – 54 ans" },
  { value: "55_plus", label: "55 ans et plus" },
]

/** Written before the split. Offered only to whoever already carries it, so
 *  opening a form does not blank a bracket they never touched — picking a new
 *  one is what retires it. Never shown to anyone else. */
export const LEGACY_TRANCHE: Option = { value: "moins_25", label: "Moins de 25 ans" }

export function trancheOptions(current?: string | null): Option[] {
  return current === LEGACY_TRANCHE.value ? [LEGACY_TRANCHE, ...TRANCHES_AGE] : TRANCHES_AGE
}

/* ── Bloc 2 — Votre situation ──────────────────────────────────────────────── */

/** Mobility used to be a separate chip field; the PM merged it in here because
 *  the two were asking the same question twice. */
export const SITUATIONS: Option[] = [
  { value: "en_recherche", label: "En recherche d'emploi" },
  { value: "en_reconversion", label: "En reconversion" },
  { value: "en_poste_evolution", label: "En poste, je souhaite évoluer" },
  { value: "premiere_insertion", label: "Première insertion" },
  { value: "reprise_apres_pause", label: "En reprise après une pause" },
]

export const RECONVERSION_SCOPES: Option[] = [
  { value: "meme_domaine", label: "Rester dans mon domaine" },
  { value: "changer_de_metier", label: "Changer de métier" },
  { value: "changer_de_secteur", label: "Changer de secteur" },
]

/* ── « Ton parcours » — asked between session 1 and session 2 ──────────────── */

export const DIPLOMES: Option[] = [
  { value: "sans_diplome", label: "Sans diplôme" },
  { value: "cap_bep", label: "CAP / BEP" },
  { value: "bac", label: "Bac" },
  { value: "bac_2", label: "Bac +2" },
  { value: "bac_3_plus", label: "Bac +3 ou plus" },
]

export const TYPES_ETUDES: Option[] = [
  { value: "generales", label: "Générales" },
  { value: "technologiques", label: "Technologiques" },
  { value: "professionnelles", label: "Professionnelles" },
  { value: "manuelles", label: "Manuelles ou pratiques" },
  { value: "autre", label: "Autre" },
]

/** The one that filters: without it nothing can say whether a piste is
 *  reachable for this person. */
export const APPETENCES_ETUDES: Option[] = [
  { value: "courtes", label: "Courtes (jusqu'à 2 ans)" },
  { value: "longues", label: "Longues (plus de 2 ans)" },
  { value: "indecis", label: "Je ne sais pas encore" },
  { value: "travailler", label: "Je préfère travailler maintenant" },
]

/** Retired from every form: ville plus the bassin d'emploi replaces it. Kept
 *  here so a row that answered it while it was still asked can be rendered
 *  read-only rather than shown as a raw key. */
export const RAYONS: Option[] = [
  { value: "ma_ville", label: "Ma ville" },
  { value: "30km", label: "Jusqu'à 30 km" },
  { value: "ma_region", label: "Ma région" },
  { value: "toute_la_france", label: "Toute la France" },
]

/** Options no longer offered anywhere, kept so a row that still carries one
 *  renders as words instead of a raw key. Add to this list when retiring a
 *  value, rather than deleting it outright. */
export const RETIRED_OPTIONS: Option[] = [LEGACY_TRANCHE]

export function labelOf(options: Option[], value?: string | null): string | null {
  if (!value) return null
  return [...options, ...RETIRED_OPTIONS].find((option) => option.value === value)?.label ?? value
}
