import { redirect } from "next/navigation"

/**
 * Parcours 2 and 3 were retired on 2026-10-08, so there is nothing left to
 * choose: every « Lancer mon analyse » lands on the parcours 1 form. A
 * temporary redirect, because the four-door submit flow (sub-project 2)
 * changes this entry again.
 */
export default function AnalysePage() {
  redirect("/analyse/nouveau")
}
