import type { ScanState } from "@/lib/market-scanner/latest-scan"
import { formatValue, HORIZONS, HORIZON_LABELS, type MarketScan } from "@/lib/market-scanner/report"
import { AssetDetails, Evidence } from "./report-details"
import { Arbitration } from "./arbitration"
import { RetryButton } from "./retry-button"

const REGIMES = {
  "risk-on": { label: "Risk-On", style: "bg-success-container text-on-success-container" },
  cautious: { label: "Cautious", style: "bg-warning-container text-on-warning-container" },
  "risk-off": { label: "Risk-Off", style: "bg-danger-container text-on-danger-container" },
}
const KPI_ASSETS = ["vix", "sp500", "nasdaq100", "gold", "oil", "eurusd"]

export function MarketScannerPanelSkeleton() {
  return <p role="status" className="py-12 text-center text-on-surface-muted">Loading the latest report…</p>
}

export function MarketScannerPanel({ state }: { state: ScanState }) {
  if (state.status !== "available") return (
    <div className="py-12 text-center" role="status">
      <h3 className="font-display text-xl font-semibold">{state.status === "empty" ? "No report has been published yet" : "The report is temporarily unavailable"}</h3>
      <p className="mt-3 text-sm text-on-surface-variant">{state.status === "empty" ? "The next report will appear here once its analysis is complete." : "The report could not be loaded. Please try again shortly."}</p>
      <RetryButton />
    </div>
  )
  const { scan } = state
  const regime = REGIMES[scan.report.regime]
  return (
    <div className="relative space-y-8" data-scan-id={scan.id}>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-on-surface-muted">
        <span>Report date: <time dateTime={scan.scan_date}>{scan.scan_date}</time> · {scan.report.scope.available}/{scan.report.scope.requested} assets available</span>
        <time dateTime={scan.created_at}>Published {new Date(scan.created_at).toLocaleString("en-GB", { timeZone: "Europe/Paris", dateStyle: "short", timeStyle: "short" })} · Paris</time>
      </div>
      <section className={`rounded-2xl border border-outline-variant p-6 ${regime.style}`} aria-labelledby="regime-title">
        <p className="text-xs font-semibold uppercase tracking-[0.18em]">Market regime · {scan.report.horizon}</p>
        <h3 id="regime-title" className="mt-3 font-display text-2xl font-bold">{regime.label}</h3>
        <p className="mt-4 font-semibold text-on-surface">{scan.report.title}</p>
        <p className="mt-3 text-sm leading-relaxed text-on-surface">{scan.report.summary}</p>
      </section>
      <Arbitration report={scan.report} />
      <details className="rounded-xl border border-outline-variant px-4 sm:px-6">
        <summary className="min-h-11 cursor-pointer py-5 font-display text-lg font-semibold">Figures and observations · {scan.report.assets.length} assets</summary>
        <div className="space-y-8 pb-6">
          <KpiStrip scan={scan} />
          <HorizonTable scan={scan} />
          <section aria-labelledby="asset-details-title">
            <h3 id="asset-details-title" className="mb-2 font-display text-xl font-bold">Observations and interpretations</h3>
            <p className="mb-4 text-xs text-on-surface-muted">Expand an asset to read its analysis and data provenance.</p>
            {scan.report.assets.map(asset => <AssetDetails key={asset.asset_key} asset={asset} quality={scan.report.data_quality[asset.asset_key]} sources={scan.report.sources} />)}
          </section>
        </div>
      </details>
      <Evidence scan={scan} />
      <p className="border-t border-outline-variant pt-4 text-xs text-on-surface-muted">The displayed report refreshes no more than once every 60 seconds.</p>
    </div>
  )
}

function KpiStrip({ scan }: { scan: MarketScan }) {
  const assets = KPI_ASSETS.map(key => scan.report.assets.find(asset => asset.asset_key === key)).filter(asset => asset !== undefined)
  return (
    <section aria-labelledby="kpi-title">
      <h3 id="kpi-title" className="mb-5 font-display text-xl font-bold">Latest observations</h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {assets.map(asset => (
          <div key={asset.asset_key} className="flex flex-col gap-2 rounded-2xl border border-outline-variant bg-surface-lowest px-4 py-3">
            <span className="text-xs font-semibold text-on-surface-muted">{asset.name}</span>
            <span className="break-words text-lg font-bold tabular-nums">{formatValue(asset.value)} {asset.unit}</span>
            <Change value={asset.horizons["1d"]?.change_pct ?? null} />
            <span className="text-[11px] text-on-surface-muted">1 day · observed on {asset.observed_on ?? "unknown date"}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

function Change({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-on-surface-muted">Unavailable</span>
  const style = value > 0 ? "text-on-success-container" : value < 0 ? "text-on-danger-container" : "text-on-surface-muted"
  return <span className={`whitespace-nowrap text-xs font-medium tabular-nums ${style}`}>{value > 0 ? "+" : ""}{value.toLocaleString("en-GB", { maximumFractionDigits: 2 })} %</span>
}

function HorizonTable({ scan }: { scan: MarketScan }) {
  return (
    <section aria-labelledby="horizons-title">
      <h3 id="horizons-title" className="mb-2 font-display text-xl font-bold">The market across eight horizons</h3>
      <p className="mb-4 text-xs text-on-surface-muted">Percentage changes. YTD means year to date. Scroll the table horizontally on smaller screens.</p>
      <div role="region" aria-label="Changes by asset and horizon" tabIndex={0} className="overflow-x-auto rounded-xl border border-outline-variant">
        <table className="w-full min-w-[800px] text-left text-sm">
          <caption className="sr-only">Changes for each asset across eight periods; missing data remains unavailable.</caption>
          <thead className="bg-surface-low"><tr><th scope="col" className="p-3">Asset</th>{HORIZONS.map(horizon => <th key={horizon} scope="col" className="p-3 text-right text-xs">{HORIZON_LABELS[horizon]}</th>)}</tr></thead>
          <tbody>{scan.report.assets.map(asset => (
            <tr key={asset.asset_key} className="border-t border-outline-variant">
              <th scope="row" className="p-3 font-medium">{asset.name}</th>
              {HORIZONS.map(horizon => <td key={horizon} className="p-3 text-right"><Change value={asset.horizons[horizon]?.change_pct ?? null} /></td>)}
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  )
}
