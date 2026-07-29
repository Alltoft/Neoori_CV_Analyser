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

const SITE_URL = "https://frontend-seven-fawn-59.vercel.app"

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "neoori — Analyse stratégique de CV",
    template: "%s · neoori",
  },
  description:
    "Une lecture stratégique du CV : forces, points à renforcer et préconisations concrètes au regard de la cible professionnelle. Conçu pour les conseillers, les organisations de l'emploi et les candidats.",
  keywords: [
    "analyse de CV", "conseiller en évolution professionnelle", "Cap Emploi",
    "France Travail", "Mission Locale", "reconversion", "RGPD", "bilan de compétences",
  ],
  applicationName: "neoori",
  authors: [{ name: "neoori" }],
  openGraph: {
    type: "website",
    locale: "fr_FR",
    url: SITE_URL,
    siteName: "neoori",
    title: "neoori — Analyse stratégique de CV",
    description:
      "Forces, points à renforcer et préconisations concrètes au regard de la cible. Pour les conseillers, les organisations de l'emploi et les candidats.",
    images: [{ url: "/img/og-cover.png", width: 1200, height: 630, alt: "neoori" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "neoori — Analyse stratégique de CV",
    description:
      "Forces, points à renforcer et préconisations concrètes au regard de la cible professionnelle.",
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
