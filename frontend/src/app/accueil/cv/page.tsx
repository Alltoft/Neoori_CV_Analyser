import "@/components/landing/landing.css"
import type { Metadata } from "next"
import { origin } from "@/lib/site"
import { currentSite } from "@/lib/site-server"
import { cvCopy } from "@/components/landing/copy/cv"
import { LandingNav } from "@/components/landing/LandingNav"
import { LandingFooter } from "@/components/landing/LandingFooter"
import { CvHero } from "@/components/landing/CvHero"
import { ReportIndex } from "@/components/landing/ReportIndex"
import { CardGrid } from "@/components/landing/CardGrid"
import { AdvisorsSection } from "@/components/landing/AdvisorsSection"
import { Pricing } from "@/components/landing/Pricing"
import { DataSection } from "@/components/landing/DataSection"
import { Faq } from "@/components/landing/Faq"
import { FinalCall } from "@/components/landing/FinalCall"

// Landings spec, decision 15: this landing's own title, description,
// canonical and share image. The root layout's template adds « · neoori ».
export async function generateMetadata(): Promise<Metadata> {
  const { settings } = await currentSite()
  const url = `${origin("cv", settings)}/`
  const { title, description, ogAlt } = cvCopy.meta
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      type: "website",
      locale: "fr_FR",
      url,
      siteName: "neoori",
      title: `${title} · neoori`,
      description,
      images: [{ url: "/og/cv.png", width: 1200, height: 630, alt: ogAlt }],
    },
    twitter: { card: "summary_large_image", title: `${title} · neoori`, description, images: ["/og/cv.png"] },
  }
}

// The cv. landing, « J'ai une cible », served at cv.DOMAIN/ by the proxy's
// rewrite (landings spec, decisions 8 and 16).
export default function CvLandingPage() {
  const c = cvCopy
  return (
    <div className="lp lp-cv">
      <LandingNav app="cv" copy={c.nav} showPrices={c.showPrices} placement="hero" />
      <main>
        <CvHero copy={c.hero} object={<div className="lp-cv-object" aria-hidden="true" />}>
          <ReportIndex copy={c.report} />
        </CvHero>
        <CardGrid id="comment" title={c.how.title} items={c.how.items} layout="steps" bg="white" />
        <CardGrid id="commencer" title={c.ways.title} intro={c.ways.intro} items={c.ways.items} layout="grid" bg="cool" />
        <AdvisorsSection copy={c.advisors} bg="white" />
        {c.showPrices ? <Pricing copy={c.prices} cta={c.hero.primary} /> : null}
        <DataSection copy={c.data} bg="cool" />
        <Faq copy={c.faq} bg="white" />
        <FinalCall copy={c.final} primary={c.hero.primary} secondary={c.hero.secondary} ring="orange" bg="cool" />
      </main>
      <LandingFooter app="cv" />
    </div>
  )
}
