import { Accordion } from "@/components/ui/accordion"
import { landingHref } from "@/lib/site"
import { currentSite } from "@/lib/site-server"
import type { Bg } from "./CardGrid"
import type { FaqCopy } from "./copy/types"

/** « Questions » (landings spec, decision 16), on the app's existing
 *  JS-free accordion. */
export async function Faq({ copy, bg }: { copy: FaqCopy; bg: Bg }) {
  const site = await currentSite()
  const items = copy.items.map((item) => ({
    q: item.q,
    a: (
      <>
        {item.a}
        {item.link ? (
          <>
            {" "}
            <a href={landingHref(item.link.app, site)} className="lp-text-link">{item.link.label}</a>
          </>
        ) : null}
      </>
    ),
  }))
  return (
    <section id="questions" className={`lp-section lp-bg-${bg}`} aria-labelledby="questions-h">
      <div className="lp-container lp-faq-in lp-reveal">
        <h2 id="questions-h">{copy.title}</h2>
        <Accordion items={items} />
      </div>
    </section>
  )
}
