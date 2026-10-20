import { NavSection } from "@/components/landing/nav-section"
import { HeroSection } from "@/components/landing/hero-section"
import { LogosSection } from "@/components/landing/logos-section"
import { TechSection } from "@/components/landing/tech-section"
import { RulesSection } from "@/components/landing/rules-section"
import { MarketScannerSection } from "@/components/landing/market-scanner-section"
import { EngineeringSection } from "@/components/landing/engineering-section"
import { McpSection } from "@/components/landing/mcp-section"
import { DisclaimerSection } from "@/components/landing/disclaimer-section"
import { CtaSection } from "@/components/landing/cta-section"
import { FooterSection } from "@/components/landing/footer-section"
import { LandingSignal } from "@/components/landing/landing-signal"

export const dynamic = "force-dynamic"

export default function LandingPage() {
  return (
    <div className="min-h-screen overflow-x-clip bg-surface text-on-surface">
      <NavSection />
      <LandingSignal />
      <main>
        <HeroSection />
        <div id="products" className="bg-surface-low">
          <MarketScannerSection />
          <McpSection />
        </div>
        <LogosSection />
        <TechSection />
        <RulesSection />
        <EngineeringSection />
        <DisclaimerSection />
        <CtaSection />
      </main>
      <FooterSection />
    </div>
  )
}
