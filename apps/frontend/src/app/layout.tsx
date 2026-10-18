import type { Metadata } from "next"
import { Inter, Manrope } from "next/font/google"
import { headers } from "next/headers"
import "./globals.css"
import { AnimateObserver } from "@/components/animate-observer"

const inter = Inter({ subsets: ["latin"] })
const manrope = Manrope({ subsets: ["latin"], variable: "--font-manrope" })

export const metadata: Metadata = {
  title: "Deep Copy — Analyses de marché et expérimentation agentique",
  description: "Un projet d’IA appliquée aux marchés : rapports en accès libre, analyses pour vos assistants via Momentum MCP et expérimentation de trading en simulation.",
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  await headers()

  return (
    <html lang="fr" data-scroll-behavior="smooth">
      <body className={`${inter.className} ${manrope.variable}`}>
        <AnimateObserver />
        {children}
      </body>
    </html>
  )
}
