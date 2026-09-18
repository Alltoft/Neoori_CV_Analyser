import type { Metadata, Viewport } from "next"
import { Inter, JetBrains_Mono, Plus_Jakarta_Sans } from "next/font/google"
import "./globals.css"
import { AuthProvider } from "@/lib/auth"

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

// Baked at image build time via the NEXT_PUBLIC_SITE_URL build-arg (CI repo
// variable SITE_URL); falls back to the local docker dev origin.
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:8080"

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "neoori — Orientation et analyse de CV",
    template: "%s · neoori",
  },
  description:
    "Faites le point sur votre parcours, avec ou sans CV : trois parcours d'analyse et le voyage, six sessions pour poser ce que vous savez déjà de vous. Conçu pour les conseillers, les organisations de l'emploi et les candidats.",
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
    url: SITE_URL,
    siteName: "neoori",
    title: "neoori — Orientation et analyse de CV",
    description:
      "Trois parcours d'analyse, avec ou sans CV, et le voyage en six sessions. Pour les conseillers, les organisations de l'emploi et les candidats.",
    images: [{ url: "/img/og-cover.png", width: 1200, height: 630, alt: "neoori" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "neoori — Orientation et analyse de CV",
    description:
      "Trois parcours d'analyse, avec ou sans CV, et le voyage en six sessions pour faire le point sur votre parcours.",
    images: ["/img/og-cover.png"],
  },
  icons: { icon: "/icon.svg" },
}

export const viewport: Viewport = {
  themeColor: "#1c3561",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="fr"
      suppressHydrationWarning
      className={`${jakarta.variable} ${inter.variable} ${jetbrains.variable}`}
    >
      <body className="antialiased min-h-screen bg-background text-foreground">
        <script dangerouslySetInnerHTML={{ __html: "document.documentElement.classList.add('js')" }} />
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  )
}
