import type { Metadata } from "next"
import { Inter, Manrope } from "next/font/google"
import { headers } from "next/headers"
import "./globals.css"
import { AnimateObserver } from "@/components/animate-observer"

const inter = Inter({ subsets: ["latin"] })
const manrope = Manrope({ subsets: ["latin"], variable: "--font-manrope" })

export const metadata: Metadata = {
  title: "Deep Copy — Market analysis and agent experiments",
  description: "An AI project for financial markets: public reports, analysis for your assistants through Momentum MCP, and paper trading experiments.",
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  await headers()

  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body className={`${inter.className} ${manrope.variable}`}>
        <AnimateObserver />
        {children}
      </body>
    </html>
  )
}
