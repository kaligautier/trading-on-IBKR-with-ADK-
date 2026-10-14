import { Suspense } from "react"

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
        <div data-animate="section-heading" className="mb-14 grid gap-8 md:grid-cols-12">
          <div className="md:col-span-7">
            <h2 id="market-scanner-title" className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-[-0.03em] leading-[1.12] md:leading-[1.08] font-display">
              Market Scanner lit le marché.
              <br />
              <span className="text-on-surface-muted font-medium">Vous voyez le régime.</span>
            </h2>
          </div>
          <div className="self-end md:col-span-5">
            <p className="text-on-surface-variant leading-relaxed text-sm">
              Des indices, leur volatilité et le contexte macro sur huit horizons pour distinguer
              les régimes Risk-On, Prudent et Risk-Off. Accès libre, sans inscription.
            </p>
          </div>
        </div>

        <div data-animate="scanner-stages" className="mb-8 grid border-y border-outline-variant md:grid-cols-3">
          {[
            {
              step: "01 · Collecte",
              title: "Agrégation journalière",
              desc: "Notre plateforme agrège les principaux actifs de marché (indices, volatilité, matières premières, devises et crypto) et calcule pour chacun leur performance sur 8 périodes.",
            },
            {
              step: "02 · Analyse",
              title: "Une vision marché enrichie",
              desc: "Le scanner sépare les observations chiffrées, le contexte économique et les hypothèses explicatives, en précisant les limites des données.",
            },
            {
              step: "03 · Synthèse",
              title: "Régime de marché",
              desc: "Les tendances des actions et les indicateurs de volatilité déterminent le régime Risk-On, Prudent ou Risk-Off. Les agents expliquent ce résultat et les signaux contradictoires.",
            },
          ].map(({ step, title, desc }, index) => (
            <div key={step} data-motion-item={index} className="border-b border-outline-variant p-6 last:border-b-0 md:border-b-0 md:border-r md:last:border-r-0">
              <p className="text-xs font-semibold uppercase tracking-[0.15em] text-on-surface-muted mb-3">{step}</p>
              <h3 className="text-sm font-bold mb-2 font-display tracking-[-0.01em]">{title}</h3>
              <p className="text-xs text-on-surface-variant leading-relaxed">{desc}</p>
            </div>
          ))}
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
