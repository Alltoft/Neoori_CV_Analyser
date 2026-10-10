import { ArrowRight } from "lucide-react"
import { landingHref } from "@/lib/site"
import { currentSite } from "@/lib/site-server"
import { WipeLink } from "./WipeLink"
import type { Bg } from "./CardGrid"
import type { DoorCopy, FinalCopy } from "./copy/types"

/** The final call (landings spec, decision 16): the video ad's closing line,
 *  both doors, and a bridge to the other app. */
export async function FinalCall({
  copy,
  primary,
  secondary,
  ring,
  bg,
}: {
  copy: FinalCopy
  primary: DoorCopy
  secondary: DoorCopy
  ring: "orange" | "peach"
  bg: Bg
}) {
  const site = await currentSite()
  return (
    <section className={`lp-section lp-final lp-bg-${bg}`} aria-labelledby="final-h">
      <div className="lp-container lp-final-in lp-reveal">
        <h2 id="final-h">{copy.title}</h2>
        <div className="lp-final-actions">
          <WipeLink href={primary.href} ring={ring} className="lp-btn lp-btn-primary">
            {primary.label} <ArrowRight aria-hidden="true" />
          </WipeLink>
          <a href={secondary.href} className="lp-btn lp-btn-secondary">{secondary.label}</a>
        </div>
        <p className="lp-final-bridge">
          {copy.bridge.text}{" "}
          <a href={landingHref(copy.bridge.link.app, site)} className="lp-text-link">{copy.bridge.link.label}</a>
        </p>
      </div>
    </section>
  )
}
