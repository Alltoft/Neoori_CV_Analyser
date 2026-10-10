import { ShieldCheck } from "lucide-react"
import { AppLink } from "@/lib/site-context"
import type { Bg } from "./CardGrid"
import type { DataCopy } from "./copy/types"

/** « Vos données » (landings spec, decision 16). No claim about where data is
 *  processed; the privacy page says it. */
export function DataSection({ copy, bg }: { copy: DataCopy; bg: Bg }) {
  return (
    <section id="donnees" className={`lp-section lp-data lp-bg-${bg}`} aria-labelledby="donnees-h">
      <div className="lp-container lp-data-in lp-reveal">
        <h2 id="donnees-h">{copy.title}</h2>
        <ul>
          {copy.points.map((point) => (
            <li key={point}>
              <ShieldCheck aria-hidden="true" />
              <span>{point}</span>
            </li>
          ))}
        </ul>
        <AppLink href={copy.link.href} className="lp-text-link">{copy.link.label}</AppLink>
      </div>
    </section>
  )
}
