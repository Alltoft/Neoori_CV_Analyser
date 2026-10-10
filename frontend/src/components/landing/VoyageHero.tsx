import type { CSSProperties, ReactNode } from "react"
import { Doors } from "./Doors"
import type { VoyageCopy } from "./copy/types"

const at = (i: number) => ({ "--i": i }) as CSSProperties

/** voyage. hero, direction 2 « Six étapes » (landings spec, ruling 6): the
 *  copy and the two doors, the six sessions as a path from mist to dawn
 *  (session 0 lit), and the glass oo (`object`) above the path's far end. On
 *  phones the oo comes first and the path turns vertical. */
export function VoyageHero({ copy, object }: { copy: VoyageCopy["hero"]; object: ReactNode }) {
  return (
    <section id="lp-voy-hero" className="lp-voy-hero" aria-labelledby="lp-h1">
      {object}
      <div className="lp-mist" aria-hidden="true" />
      <div className="lp-mist lp-mist--2" aria-hidden="true" />
      <div className="lp-mist-left" aria-hidden="true" />
      <div className="lp-container lp-voy-hero-in">
        <div className="lp-hero-copy lp-rise">
          <span className="lp-label" style={at(0)}>{copy.label}</span>
          <h1 id="lp-h1" style={at(1)}>{copy.title}</h1>
          <p className="lp-sub" style={at(2)}>{copy.sub}</p>
          <div style={at(3)}>
            <Doors primary={copy.primary} secondary={copy.secondary} ring="peach" />
          </div>
        </div>
        <ol className="lp-path" aria-label={copy.stepsLabel}>
          {copy.steps.map((step, i) => (
            <li key={step.name} className={i === 0 ? "lp-step is-lit" : "lp-step"}>
              <i aria-hidden="true" />
              <b>{step.name}</b>
              {step.caption ? <span>{step.caption}</span> : null}
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
