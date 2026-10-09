import type { Metadata, Viewport } from "next"
import { Inter, JetBrains_Mono, Plus_Jakarta_Sans } from "next/font/google"
import "./globals.css"
import { AuthProvider } from "@/lib/auth"
import { origin } from "@/lib/site"
import { SiteProvider } from "@/lib/site-context"
import { currentSite } from "@/lib/site-server"

// Display — neoori charter face (Plus Jakarta Sans): humanist geometric sans, brand-aligned.
const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin", "latin-ext"],
  variable: "--font-jakarta",
  display: "swap",
})

// Body — clean, legible workhorse for dense French copy.
const inter = Inter({
  subsets: ["latin", "latin-ext"],
  variable: "--font-inter",
  display: "swap",
})

// Data / eyebrows — technical precision (section markers, B2G traceability).
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
})

// Per request (subdomain split spec, decision 24): metadataBase and og:url
// name the host the page is served on — its origin rebuilt from DOMAIN, never
// the raw Host header — so each subdomain's preview names itself. Reading the
// host makes every page dynamic; at this traffic that costs nothing.
export async function generateMetadata(): Promise<Metadata> {
  const { settings, app } = await currentSite()
  const url = origin(app, settings)
  return {
    metadataBase: new URL(url),
    title: {
      default: "neoori — Orientation et analyse de CV",
      template: "%s · neoori",
    },
    description:
      "Faites le point sur votre parcours : l'analyse de votre CV face au poste que vous visez, et le voyage, six sessions pour poser ce que vous savez déjà de vous. Conçu pour les conseillers, les organisations de l'emploi et les candidats.",
    keywords: [
      "orientation professionnelle", "analyse de CV", "projet professionnel", "reconversion",
      "insertion professionnelle", "conseiller en évolution professionnelle", "Cap Emploi",
      "France Travail", "Mission Locale", "RGPD", "bilan de compétences",
    ],
    applicationName: "neoori",
    authors: [{ name: "neoori" }],
    openGraph: {
      type: "website",
      locale: "fr_FR",
      url,
      siteName: "neoori",
      title: "neoori — Orientation et analyse de CV",
      description:
        "L'analyse de votre CV face à votre cible, et le voyage en six sessions. Pour les conseillers, les organisations de l'emploi et les candidats.",
      images: [{ url: "/img/og-cover.png", width: 1200, height: 630, alt: "neoori" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "neoori — Orientation et analyse de CV",
      description:
        "L'analyse de votre CV face à votre cible, et le voyage en six sessions pour faire le point sur votre parcours.",
      images: ["/img/og-cover.png"],
    },
    icons: { icon: "/icon.svg" },
  }
}

export const viewport: Viewport = {
  themeColor: "#1c3561",
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const site = await currentSite()
  return (
    <html
      lang="fr"
      suppressHydrationWarning
      className={`${jakarta.variable} ${inter.variable} ${jetbrains.variable}`}
    >
      <body className="antialiased min-h-screen bg-background text-foreground">
        <script dangerouslySetInnerHTML={{ __html: "document.documentElement.classList.add('js')" }} />
        <SiteProvider site={site}>
          <AuthProvider>{children}</AuthProvider>
        </SiteProvider>
      </body>
    </html>
  )
}
