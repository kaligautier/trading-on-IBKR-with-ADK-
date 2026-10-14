import type { Metadata } from "next"
import { Inter, Manrope } from "next/font/google"
import { headers } from "next/headers"
import "./globals.css"
import { AnimateObserver } from "@/components/animate-observer"

const inter = Inter({ subsets: ["latin"] })
const manrope = Manrope({ subsets: ["latin"], variable: "--font-manrope" })

export const metadata: Metadata = {
  title: "Deep Copy — Deep Copy, Market Scanner et Momentum MCP",
  description: "Trois produits pour piloter un compte IBKR en paper trading, lire le régime de marché et connecter les analyses Momentum à vos agents.",
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
