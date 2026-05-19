import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { AuthProvider } from "@/lib/auth"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "neoori — Analyse de CV",
  description: "Une lecture stratégique de votre CV pour les parcours qu'on ne sait pas lire.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={inter.className}>
      <body className="antialiased min-h-screen bg-background">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  )
}
