import { NavSection } from "@/components/landing/nav-section"
import { HeroSection } from "@/components/landing/hero-section"
import { ProductSuiteSection } from "@/components/landing/product-suite-section"
import { MarketScannerSection } from "@/components/landing/market-scanner-section"
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
        <ProductSuiteSection />
        <div className="bg-surface-low">
          <MarketScannerSection />
        </div>
        <CtaSection />
      </main>
      <FooterSection />
    </div>
  )
}
