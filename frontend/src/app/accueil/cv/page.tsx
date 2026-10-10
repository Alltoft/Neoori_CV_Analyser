import "@/components/landing/landing.css"
import { LandingNav } from "@/components/landing/LandingNav"
import { LandingFooter } from "@/components/landing/LandingFooter"
import { Doors } from "@/components/landing/Doors"
import { cvCopy } from "@/components/landing/copy/cv"

// The cv. landing, served at cv.DOMAIN/ by the proxy's rewrite (landings spec,
// decision 8). Task 6 of the plan fills in the sections.
export default function CvLandingPage() {
  return (
    <div className="lp lp-cv">
      <LandingNav app="cv" copy={cvCopy.nav} showPrices={cvCopy.showPrices} placement="hero" />
      <main>
        <section className="lp-section">
          <div className="lp-container lp-hero-copy">
            <span className="lp-label">{cvCopy.hero.label}</span>
            <h1>{cvCopy.hero.title}</h1>
            <p className="lp-sub">{cvCopy.hero.sub}</p>
            <Doors primary={cvCopy.hero.primary} secondary={cvCopy.hero.secondary} ring="orange" />
          </div>
        </section>
      </main>
      <LandingFooter app="cv" />
    </div>
  )
}
