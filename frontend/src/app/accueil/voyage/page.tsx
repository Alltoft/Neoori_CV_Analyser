import "@/components/landing/landing.css"
import { LandingNav } from "@/components/landing/LandingNav"
import { LandingFooter } from "@/components/landing/LandingFooter"
import { Doors } from "@/components/landing/Doors"
import { voyageCopy } from "@/components/landing/copy/voyage"

// The voyage. landing, served at voyage.DOMAIN/ by the proxy's rewrite
// (landings spec, decision 8). Task 7 of the plan fills in the sections.
export default function VoyageLandingPage() {
  return (
    <div className="lp lp-voy">
      <LandingNav app="voyage" copy={voyageCopy.nav} placement="hero" />
      <main>
        <section className="lp-section" style={{ paddingTop: "calc(var(--lp-nav-h) + 48px)" }}>
          <div className="lp-container lp-hero-copy">
            <span className="lp-label">{voyageCopy.hero.label}</span>
            <h1>{voyageCopy.hero.title}</h1>
            <p className="lp-sub">{voyageCopy.hero.sub}</p>
            <Doors primary={voyageCopy.hero.primary} secondary={voyageCopy.hero.secondary} ring="peach" />
          </div>
        </section>
      </main>
      <LandingFooter app="voyage" />
    </div>
  )
}
