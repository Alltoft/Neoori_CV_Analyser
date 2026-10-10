import "@/components/landing/landing.css"
import type { Metadata } from "next"
import { landingHref, origin } from "@/lib/site"
import { currentSite } from "@/lib/site-server"
import { voyageCopy } from "@/components/landing/copy/voyage"
import { LandingNav } from "@/components/landing/LandingNav"
import { LandingFooter } from "@/components/landing/LandingFooter"
import { VoyageHero } from "@/components/landing/VoyageHero"
import { CardGrid } from "@/components/landing/CardGrid"
import { AdvisorsSection } from "@/components/landing/AdvisorsSection"
import { DataSection } from "@/components/landing/DataSection"
import { Faq } from "@/components/landing/Faq"
import { FinalCall } from "@/components/landing/FinalCall"
import { HeroObject } from "@/components/landing/HeroObject"

// Landings spec, decision 15: this landing's own title, description,
// canonical and share image. The root layout's template adds « · neoori ».
export async function generateMetadata(): Promise<Metadata> {
  const { settings } = await currentSite()
  const url = `${origin("voyage", settings)}/`
  const { title, description, ogAlt } = voyageCopy.meta
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
      images: [{ url: "/og/voyage.png", width: 1200, height: 630, alt: ogAlt }],
    },
    twitter: { card: "summary_large_image", title: `${title} · neoori`, description, images: ["/og/voyage.png"] },
  }
}

// The voyage. landing, served at voyage.DOMAIN/ by the proxy's rewrite
// (landings spec, decisions 8 and 17). The grounds go from navy to dawn.
export default async function VoyageLandingPage() {
  const site = await currentSite()
  const v = voyageCopy
  const how = v.how.items.map(({ title, text, link }) => ({
    title,
    text,
    action: link ? <a href={landingHref(link.app, site)} className="lp-text-link">{link.label}</a> : undefined,
  }))
  return (
    <div className="lp lp-voy">
      <LandingNav app="voyage" copy={v.nav} placement="hero" />
      <main>
        <VoyageHero
          copy={v.hero}
          object={
            <HeroObject
              scene="mark"
              desktop={{ src: "/landing/voyage-desktop", width: 1555, height: 1555 }}
              phone={{ src: "/landing/voyage-phone", width: 780, height: 600 }}
              pointerAreaId="lp-voy-hero"
              className="lp-voy-object"
            />
          }
        />
        <CardGrid id="emporter" title={v.take.title} items={v.take.items} layout="grid" bg="deep" note={v.take.note} />
        <CardGrid id="etapes" title={v.how.title} items={how} layout="steps" bg="dusk" note={v.how.note} />
        <AdvisorsSection copy={v.advisors} bg="dawn" />
        <DataSection copy={v.data} bg="dawn" />
        <Faq copy={v.faq} bg="dawn" />
        <FinalCall copy={v.final} primary={v.hero.primary} secondary={v.hero.secondary} ring="peach" bg="dawn" />
      </main>
      <LandingFooter app="voyage" />
    </div>
  )
}
