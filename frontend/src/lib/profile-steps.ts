/** Where each block of the Profil de base is asked.
 *
 *  There is no profile form to go and fill any more. The blocks are asked at
 *  the points of the voyage where the person is already engaged enough to
 *  answer them, and `backend/app/models/voyage.py:session_lock` enforces the
 *  same placement server-side:
 *
 *    signup      prénom, tranche d'âge          — what session 1 has always wanted
 *    entrée      ville, nom, situation          — before session 0, on the hub
 *    parcours    diplôme, études, appétence     — between sessions 1 and 2
 *    conditions  bloc 5 + OETH                  — between sessions 4 and 5
 *
 *  One declaration, because two surfaces render these: the hub inlines
 *  « entrée » on its consent gate, and /voyage/etape/<clé> serves the other
 *  two. `/profil` stays the place to change an answer, never the place to
 *  give it for the first time.
 */

import {
  APPETENCES_ETUDES, DIPLOMES, SITUATIONS, TYPES_ETUDES, type Option,
} from "./profile-options"

export type StepKey = "entree" | "parcours" | "conditions"

export interface StepField {
  name: string
  label: string
  kind: "text" | "select"
  options?: Option[]
  /** Required fields gate the step's submit button. The optional ones are
   *  optional on the server too — see models/voyage.PARCOURS_FIELDS. */
  required: boolean
  placeholder?: string
  hint?: string
}

export interface ProfileStep {
  key: StepKey
  title: string
  intro: string
  /** Rendered as plain fields, or as bloc 5's matrix — which has its own
   *  component, its own consent and its own encryption. */
  kind: "fields" | "conditions"
  fields: StepField[]
  /** Where to go once it is saved. */
  done: string
}

export const PROFILE_STEPS: Record<StepKey, ProfileStep> = {
  entree: {
    key: "entree",
    title: "Avant de commencer",
    intro:
      "Ce n'est pas un test, et il n'y a pas de bonne réponse. Trois questions rapides, "
      + "puis la première session.",
    kind: "fields",
    fields: [
      {
        name: "ville",
        label: "Votre ville ou code postal",
        kind: "text",
        required: true,
        placeholder: "Lyon",
        hint: "Sert à lire la demande locale. Sans elle, cette ligne reste « à vérifier ».",
      },
      { name: "nom", label: "Votre nom", kind: "text", required: false, placeholder: "Facultatif" },
      {
        name: "situation",
        label: "Votre situation aujourd'hui",
        kind: "select",
        options: SITUATIONS,
        required: true,
      },
    ],
    done: "/voyage",
  },

  parcours: {
    key: "parcours",
    title: "Votre parcours",
    intro:
      "Avant de continuer, deux ou trois choses sur votre parcours. Il n'y a pas de bon "
      + "ni de mauvais niveau.",
    kind: "fields",
    fields: [
      {
        name: "diplome",
        label: "Votre dernier diplôme ou niveau",
        kind: "select",
        options: DIPLOMES,
        required: true,
      },
      {
        name: "type_etudes",
        label: "Le type d'études suivi",
        kind: "select",
        options: TYPES_ETUDES,
        required: true,
      },
      {
        name: "intitule_etudes",
        label: "L'intitulé exact",
        kind: "text",
        required: false,
        placeholder: "Facultatif — ex. Bac STI2D",
      },
      {
        name: "appetence_etudes",
        label: "Les études que vous envisagez",
        kind: "select",
        options: APPETENCES_ETUDES,
        required: true,
        hint: "C'est ce qui permet de dire si une piste est atteignable pour vous.",
      },
    ],
    done: "/voyage",
  },

  conditions: {
    key: "conditions",
    title: "Vos conditions de travail",
    intro:
      "Les mêmes questions pour tout le monde. On ne demande jamais la cause d'une "
      + "limitation, seulement son effet sur le travail. Vous pouvez tout laisser vide.",
    kind: "conditions",
    fields: [],
    done: "/voyage",
  },
}

export const STEP_KEYS = Object.keys(PROFILE_STEPS) as StepKey[]

export function isStepKey(value: string | undefined): value is StepKey {
  return value !== undefined && value in PROFILE_STEPS
}

/** Which step answers a lock, so a locked card can link to its remedy instead
 *  of naming a page the person then has to find. Mirrors the lock strings in
 *  `frontend/src/types/voyage.ts`. */
export function stepForLock(lock: string | null): StepKey | null {
  if (lock === "Complétez votre parcours") return "parcours"
  if (lock === "Complétez vos conditions de travail") return "conditions"
  return null
}

/** Whether every required field of a step has a value. */
export function stepIsComplete(
  step: ProfileStep,
  values: Record<string, string>,
): boolean {
  return step.fields
    .filter((field) => field.required)
    .every((field) => (values[field.name] ?? "").trim().length > 0)
}
