import type { Metadata } from "next"
import type { ReactNode } from "react"

// A private report: never indexed, and no Referer from it (four-doors spec,
// decision 30 — the key is in the fragment anyway, this is belt and braces).
export const metadata: Metadata = {
  title: "Votre rapport",
  referrer: "no-referrer",
  robots: { index: false, follow: false },
}

export default function RapportLayout({ children }: { children: ReactNode }) {
  return children
}
