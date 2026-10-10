import { REPORT_TIERS } from "@/lib/report-tiers"
import type { CvCopy } from "./copy/types"

/** « Ce que contient le rapport » (landings spec, decision 16): three cards on
 *  desktop, one vertical line with a marker per tier on phones. */
export function ReportIndex({ copy }: { copy: CvCopy["report"] }) {
  return (
    <div className="lp-index" id="rapport">
      <div className="lp-container">
        <div className="lp-index-head lp-reveal">
          <h2>{copy.title}</h2>
          <p>{copy.intro}</p>
        </div>
        <div className="lp-tiers lp-reveal">
          {REPORT_TIERS.map((tier) => (
            <section key={tier.id} className={`lp-tier lp-tier--${tier.id}`} aria-label={copy.tiers[tier.id].tag}>
              <div className="lp-tier-name">
                <span className="lp-label">{copy.tiers[tier.id].name}</span>
                <span className={`lp-tag lp-tag--${tier.id}`}>{copy.tiers[tier.id].tag}</span>
              </div>
              <ol>
                {tier.rows.map((row) => (
                  <li key={row.key}>
                    <b>{row.mark}</b>
                    {row.title}
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}
