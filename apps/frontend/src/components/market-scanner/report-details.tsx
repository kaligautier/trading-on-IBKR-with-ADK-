import { formatValue, type MarketAsset, type MarketScan } from "@/lib/market-scanner/report"

type Report = MarketScan["report"]
const STATUS = { documented: "Documented", hypothesis: "Hypothesis", unestablished: "Unestablished" }
const QUALITY = { available: "Available", stale: "Stale", unavailable: "Unavailable" }

function SourceLinks({ ids, sources }: { ids: string[]; sources: Report["sources"] }) {
  return sources.filter(source => ids.includes(source.id)).map(source => source.url ? (
    <a key={source.id} href={source.url} target="_blank" rel="noopener noreferrer" className="mr-3 inline-flex min-h-11 items-center break-words text-xs underline underline-offset-4">{source.title}</a>
  ) : <span key={source.id} className="text-xs">{source.title} · link unavailable</span>)
}

export function AssetDetails({ asset, quality, sources }: { asset: MarketAsset; quality?: Report["data_quality"][string]; sources: Report["sources"] }) {
  return (
    <details id={`asset-${asset.asset_key}`} className="group border-t border-outline-variant py-2">
      <summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold">{asset.name} <span className="ml-2 font-normal text-on-surface-muted">{formatValue(asset.value)} {asset.unit}</span></summary>
      <div className="space-y-3 pb-5 text-sm leading-relaxed">
        <p className="text-xs text-on-surface-muted">Observed on: {asset.observed_on ?? "unknown date"} · 3-year percentile: {asset.percentile_3y === null ? "unavailable" : `${(asset.percentile_3y * 100).toLocaleString("en-GB", { maximumFractionDigits: 1 })} %`}</p>
        <p><strong>Observation.</strong> {asset.observation}</p>
        <p><strong>{STATUS[asset.interpretation.status]}.</strong> {asset.interpretation.text}</p>
        <SourceLinks ids={asset.interpretation.source_ids} sources={sources} />
        {quality && <p className="text-xs text-on-surface-variant">Data: {QUALITY[quality.status].toLowerCase()} · {quality.source_url ? <a href={quality.source_url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4">{quality.source}</a> : quality.source}{quality.reason ? ` · ${quality.reason}` : ""}</p>}
      </div>
    </details>
  )
}

function TextList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null
  return <section className="space-y-3"><h4 className="font-semibold">{title}</h4><ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-on-surface-variant">{items.map((item, index) => <li key={index}>{item}</li>)}</ul></section>
}

export function Evidence({ scan }: { scan: MarketScan }) {
  const report = scan.report
  return (
    <div className="space-y-6">
      <details className="rounded-xl border border-outline-variant px-4 sm:px-6">
        <summary className="min-h-11 cursor-pointer py-5 font-display text-lg font-semibold">Asset class analysis and macroeconomic context</summary>
        <div className="space-y-8 pb-6">
          <section className="space-y-4" aria-labelledby="themes-title">
            <h3 id="themes-title" className="font-display text-xl font-bold">Analysis by asset class</h3>
            {report.themes.map((theme, index) => <details key={index} className="border-t border-outline-variant py-2"><summary className="min-h-11 cursor-pointer py-3 font-medium">{theme.family}</summary><p className="mb-3 text-sm leading-relaxed">{theme.observation}</p><p className="text-sm leading-relaxed"><strong>{STATUS[theme.interpretation.status]}.</strong> {theme.interpretation.text}</p><SourceLinks ids={theme.interpretation.source_ids} sources={report.sources} /></details>)}
          </section>
          {report.macro_overview && <section className="space-y-4" aria-labelledby="macro-title">
            <h3 id="macro-title" className="font-display text-xl font-bold">Macroeconomic context</h3>
            <p className="text-sm leading-relaxed">{report.macro_overview.context}</p>
            {report.macro_overview.themes.map((theme, index) => (
              <details key={index} className="border-t border-outline-variant py-2">
                <summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold">{theme.title} · {STATUS[theme.status]}</summary>
                <dl className="space-y-3 pb-4 text-sm leading-relaxed">{[
                  ["Observation", theme.observation], ["Reported context", theme.development],
                  ["Proposed mechanism", theme.transmission], ["Counter-evidence", theme.counter_evidence],
                  ["Uncertainty", theme.uncertainty],
                ].map(([label, text]) => <div key={label}><dt className="font-semibold">{label}</dt><dd className="text-on-surface-variant">{text}</dd></div>)}</dl>
              </details>
            ))}
          </section>}
        </div>
      </details>
      {(report.limitations.length > 0 || (report.macro_overview?.data_gaps.length ?? 0) > 0) && (
        <details className="rounded-xl border border-outline-variant px-4 sm:px-6">
          <summary className="min-h-11 cursor-pointer py-5 font-semibold">Report limitations and missing data</summary>
          <div className="space-y-5 pb-6">
            <TextList title="Report limitations" items={report.limitations} />
            {report.macro_overview && <TextList title="Missing data" items={report.macro_overview.data_gaps} />}
          </div>
        </details>
      )}
      <section className="space-y-3" aria-labelledby="sources-title">
        <h3 id="sources-title" className="font-display text-xl font-bold">Sources and coverage</h3>
        <p className="text-xs text-on-surface-muted">Observation dates: {report.scope.observation_dates.join(", ") || "not provided"}.</p>
        {report.scope.stale.length > 0 && <p className="text-sm">Stale data: {report.scope.stale.join(", ")}</p>}
        {report.scope.unavailable.length > 0 && <p className="text-sm">Unavailable assets: {report.scope.unavailable.join(", ")}</p>}
        {Object.entries(report.data_quality).filter(([, quality]) => quality.status === "unavailable").map(([key, quality]) => (
          <div key={key} className="border-l-2 border-outline-variant pl-4 text-sm">
            <p className="font-semibold">{quality.name} · Unavailable</p>
            <p className="mt-1 text-on-surface-variant">{quality.reason ?? "The provider did not specify a reason."}</p>
            <p className="mt-1 text-xs">{quality.source_url ? <a href={quality.source_url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4">{quality.source}</a> : quality.source}</p>
          </div>
        ))}
        {report.sources.length ? <SourceLinks ids={report.sources.map(source => source.id)} sources={report.sources} /> : <p className="text-sm text-on-surface-variant">No research references are attached to this report. Interpretations should be distinguished from numerical observations and their data providers.</p>}
      </section>
    </div>
  )
}
