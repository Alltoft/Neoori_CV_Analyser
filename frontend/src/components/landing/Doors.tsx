import { ArrowRight } from "lucide-react"
import { WipeLink } from "./WipeLink"
import type { DoorCopy } from "./copy/types"

/** The hero's two doors (landings spec, ruling 5): the person's, with the ∞
 *  wipe, and « Je suis conseiller », which scrolls to the advisors section. */
export function Doors({ primary, secondary, ring }: { primary: DoorCopy; secondary: DoorCopy; ring: "orange" | "peach" }) {
  return (
    <div className="lp-doors">
      <div className="lp-door">
        <WipeLink href={primary.href} ring={ring} className="lp-btn lp-btn-primary">
          {primary.label} <ArrowRight aria-hidden="true" />
        </WipeLink>
        <p className="lp-door-note">{primary.note}</p>
      </div>
      <div className="lp-door">
        <a href={secondary.href} className="lp-btn lp-btn-secondary">{secondary.label}</a>
        <p className="lp-door-note">{secondary.note}</p>
      </div>
    </div>
  )
}
