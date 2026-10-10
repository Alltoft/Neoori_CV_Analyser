import { WipeLink } from "./WipeLink"
import type { CvCopy, DoorCopy } from "./copy/types"

/** « Tarifs » (landings spec, decision 16). Rendered only while
 *  `cvCopy.showPrices` is true. */
export function Pricing({ copy, cta }: { copy: CvCopy["prices"]; cta: DoorCopy }) {
  return (
    <section id="tarifs" className="lp-section lp-prices lp-bg-cool" aria-labelledby="tarifs-h">
      <div className="lp-container lp-reveal">
        <div className="lp-section-head">
          <h2 id="tarifs-h">{copy.title}</h2>
          <p>{copy.intro}</p>
        </div>
        <ul className="lp-plans">
          {copy.plans.map((plan) => (
            <li key={plan.name} className="lp-plan">
              <span className="lp-label">{plan.name}</span>
              <p className="lp-plan-price">{plan.price}</p>
              <p>{plan.text}</p>
            </li>
          ))}
        </ul>
        <p className="lp-cards-note">{copy.note}</p>
        <WipeLink href={cta.href} ring="orange" className="lp-btn lp-btn-primary">{cta.label}</WipeLink>
      </div>
    </section>
  )
}
