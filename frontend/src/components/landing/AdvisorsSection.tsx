import { Check } from "lucide-react"
import { AppLink } from "@/lib/site-context"
import type { Bg } from "./CardGrid"
import type { AdvisorsCopy } from "./copy/types"

/** « Pour les conseillers », the target of « Je suis conseiller » (landings
 *  spec, decision 16). */
export function AdvisorsSection({ copy, bg }: { copy: AdvisorsCopy; bg: Bg }) {
  return (
    <section id="conseillers" className={`lp-section lp-advisors lp-bg-${bg}`} aria-labelledby="conseillers-h">
      <div className="lp-container lp-advisors-in lp-reveal">
        <div>
          <span className="lp-label">{copy.label}</span>
          <h2 id="conseillers-h">{copy.title}</h2>
          <div className="lp-advisors-links">
            <AppLink href={copy.signup.href} className="lp-btn lp-btn-dark">{copy.signup.label}</AppLink>
            <AppLink href={copy.signin.href} className="lp-btn lp-btn-line">{copy.signin.label}</AppLink>
          </div>
        </div>
        <ul>
          {copy.points.map((point) => (
            <li key={point}>
              <Check aria-hidden="true" />
              <span>{point}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
