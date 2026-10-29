import { Suspense } from "react"
import { ChromaticTextReveal } from "@/components/motion/chromatic-text-reveal"

import {
  MarketScannerPanel,
  MarketScannerPanelSkeleton,
} from "@/components/market-scanner/panel"
import { latestScan } from "@/lib/market-scanner/latest-scan"

async function LatestMarketScannerPanel() {
  const state = await latestScan()
  return <MarketScannerPanel state={state} />
}

export function MarketScannerSection() {
  return (
    <section id="market-scanner" aria-labelledby="market-scanner-title" className="scroll-mt-20 py-20 md:py-28">
      <div className="max-w-6xl mx-auto px-6">
        <div data-animate="section-heading" className="mb-10 grid gap-8 md:grid-cols-12">
          <div className="md:col-span-7">
            <h2 id="market-scanner-title" className="text-balance font-display text-4xl font-bold leading-tight tracking-tight md:text-5xl">
              <ChromaticTextReveal prefix="Market" words={["Scanner."]} loop={false} />
              <br />
              <span className="text-on-surface-muted font-medium">The market, in one report.</span>
            </h2>
          </div>
          <div className="self-end md:col-span-5">
            <p className="text-on-surface-variant leading-relaxed text-sm">
              Explore major indices, volatility and the economic context. Read the latest published report below, freely available without an account.
            </p>
          </div>
        </div>

        <div data-animate="scanner-console" className="scanner-console rounded-2xl border border-outline-variant/60 bg-surface-lowest p-4 md:p-6">
          <div data-motion-marker="scanner-frame" className="scanner-frame" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
          </div>
          <Suspense fallback={<MarketScannerPanelSkeleton />}>
            <LatestMarketScannerPanel />
          </Suspense>
        </div>
      </div>
    </section>
  )
}
