import type { ReactNode } from "react"
import type { ItemCopy } from "./copy/types"

/** A section's ground (Appendix B): white and cool on cv.; deep, dusk, then
 *  dawn on voyage. */
export type Bg = "white" | "cool" | "deep" | "dusk" | "dawn"

/** A titled section of short items: a numbered sequence (`steps`) or cards
 *  side by side (`grid`). */
export function CardGrid({
  id,
  title,
  intro,
  items,
  layout,
  bg,
  note,
}: {
  id: string
  title: string
  intro?: string
  items: (ItemCopy & { action?: ReactNode })[]
  layout: "steps" | "grid"
  bg: Bg
  note?: string
}) {
  const list = items.map((item) => (
    <li key={item.title} className={layout === "grid" ? "lp-card" : undefined}>
      <h3>{item.title}</h3>
      <p>{item.text}</p>
      {item.action}
    </li>
  ))
  return (
    <section id={id} className={`lp-section lp-bg-${bg}`} aria-labelledby={`${id}-h`}>
      <div className="lp-container lp-reveal">
        <div className="lp-section-head">
          <h2 id={`${id}-h`}>{title}</h2>
          {intro ? <p>{intro}</p> : null}
        </div>
        {layout === "steps" ? (
          <ol className={`lp-steps${items.length === 4 ? " lp-cols-4" : ""}`}>{list}</ol>
        ) : (
          <ul className="lp-grid">{list}</ul>
        )}
        {note ? <p className="lp-cards-note">{note}</p> : null}
      </div>
    </section>
  )
}
