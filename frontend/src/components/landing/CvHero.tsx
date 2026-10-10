import type { CSSProperties, ReactNode } from "react"
import { Doors } from "./Doors"
import type { HeroCopy } from "./copy/types"

const at = (i: number) => ({ "--i": i }) as CSSProperties

/** cv. hero, direction 2 « Le rapport en index » (landings spec, ruling 6):
 *  the copy and the two doors, the 3D sheet (`object`), then the report band
 *  (`children`) that the sheet spills into. On phones the sheet comes first. */
export function CvHero({ copy, object, children }: { copy: HeroCopy; object: ReactNode; children: ReactNode }) {
  return (
    <section id="lp-cv-hero" className="lp-cv-hero" aria-labelledby="lp-h1">
      <div className="lp-container lp-cv-hero-in">
        <div className="lp-hero-copy lp-rise">
          <span className="lp-label" style={at(0)}>{copy.label}</span>
          <h1 id="lp-h1" style={at(1)}>{copy.title}</h1>
          <p className="lp-sub" style={at(2)}>{copy.sub}</p>
          <div style={at(3)}>
            <Doors primary={copy.primary} secondary={copy.secondary} ring="orange" />
          </div>
        </div>
        {object}
      </div>
      {children}
    </section>
  )
}
