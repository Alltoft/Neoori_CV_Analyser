"use client"

import dynamic from "next/dynamic"

// The report's key is in the fragment (four-doors spec, decision 30): only
// the browser has it, so the page renders there and nowhere else.
const RapportSansCompte = dynamic(() => import("@/components/analyse/RapportSansCompte"), { ssr: false })

export default function RapportPage() {
  return <RapportSansCompte />
}
