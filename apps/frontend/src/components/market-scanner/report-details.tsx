import { formatValue, type MarketAsset, type MarketScan } from "@/lib/market-scanner/report"

type Report = MarketScan["report"]
const STATUS = { documented: "Documenté", hypothesis: "Hypothèse", unestablished: "Non établi" }
const QUALITY = { available: "Disponible", stale: "Ancienne", unavailable: "Indisponible" }

function SourceLinks({ ids, sources }: { ids: string[]; sources: Report["sources"] }) {
  return sources.filter(source => ids.includes(source.id)).map(source => source.url ? (
    <a key={source.id} href={source.url} target="_blank" rel="noopener noreferrer" className="mr-3 inline-flex min-h-11 items-center break-words text-xs underline underline-offset-4">{source.title}</a>
  ) : <span key={source.id} className="text-xs">{source.title} · lien indisponible</span>)
}

export function AssetDetails({ asset, quality, sources }: { asset: MarketAsset; quality?: Report["data_quality"][string]; sources: Report["sources"] }) {
  return (
    <details id={`asset-${asset.asset_key}`} className="group border-t border-outline-variant py-2">
      <summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold">{asset.name} <span className="ml-2 font-normal text-on-surface-muted">{formatValue(asset.value)} {asset.unit}</span></summary>
      <div className="space-y-3 pb-5 text-sm leading-relaxed">
        <p className="text-xs text-on-surface-muted">Observation : {asset.observed_on ?? "date inconnue"} · Percentile sur 3 ans : {asset.percentile_3y === null ? "indisponible" : `${(asset.percentile_3y * 100).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`}</p>
        <p><strong>Observation.</strong> {asset.observation}</p>
        <p><strong>{STATUS[asset.interpretation.status]}.</strong> {asset.interpretation.text}</p>
        <SourceLinks ids={asset.interpretation.source_ids} sources={sources} />
        {quality && <p className="text-xs text-on-surface-variant">Donnée {QUALITY[quality.status].toLowerCase()} · {quality.source_url ? <a href={quality.source_url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4">{quality.source}</a> : quality.source}{quality.reason ? ` · ${quality.reason}` : ""}</p>}
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
    <div className="space-y-8">
      <section className="space-y-4" aria-labelledby="themes-title">
        <h3 id="themes-title" className="font-display text-xl font-bold">Lecture par famille d’actifs</h3>
        {report.themes.map((theme, index) => <details key={index} className="border-t border-outline-variant py-2"><summary className="min-h-11 cursor-pointer py-3 font-medium">{theme.family}</summary><p className="mb-3 text-sm leading-relaxed">{theme.observation}</p><p className="text-sm leading-relaxed"><strong>{STATUS[theme.interpretation.status]}.</strong> {theme.interpretation.text}</p><SourceLinks ids={theme.interpretation.source_ids} sources={report.sources} /></details>)}
      </section>
      {report.macro_overview && <section className="space-y-4" aria-labelledby="macro-title">
        <h3 id="macro-title" className="font-display text-xl font-bold">Contexte macroéconomique</h3>
        <p className="text-sm leading-relaxed">{report.macro_overview.context}</p>
        {report.macro_overview.themes.map((theme, index) => (
          <details key={index} className="border-t border-outline-variant py-2">
            <summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold">{theme.title} · {STATUS[theme.status]}</summary>
            <dl className="space-y-3 pb-4 text-sm leading-relaxed">{[
              ["Observation", theme.observation], ["Contexte rapporté", theme.development],
              ["Mécanisme envisagé", theme.transmission], ["Éléments contradictoires", theme.counter_evidence],
              ["Incertitudes", theme.uncertainty],
            ].map(([label, text]) => <div key={label}><dt className="font-semibold">{label}</dt><dd className="text-on-surface-variant">{text}</dd></div>)}</dl>
          </details>
        ))}
        <TextList title="Données manquantes" items={report.macro_overview.data_gaps} />
      </section>}
      <TextList title="Limites du rapport" items={report.limitations} />
      <TextList title="Points à surveiller" items={report.watch_points} />
      <section className="space-y-3" aria-labelledby="sources-title">
        <h3 id="sources-title" className="font-display text-xl font-bold">Sources et couverture</h3>
        <p className="text-xs text-on-surface-muted">Dates d’observation : {report.scope.observation_dates.join(", ") || "non renseignées"}.</p>
        {report.scope.stale.length > 0 && <p className="text-sm">Données anciennes : {report.scope.stale.join(", ")}</p>}
        {report.scope.unavailable.length > 0 && <p className="text-sm">Actifs indisponibles : {report.scope.unavailable.join(", ")}</p>}
        {Object.entries(report.data_quality).filter(([, quality]) => quality.status === "unavailable").map(([key, quality]) => (
          <div key={key} className="border-l-2 border-outline-variant pl-4 text-sm">
            <p className="font-semibold">{quality.name} · Indisponible</p>
            <p className="mt-1 text-on-surface-variant">{quality.reason ?? "Le fournisseur n’a pas précisé de motif."}</p>
            <p className="mt-1 text-xs">{quality.source_url ? <a href={quality.source_url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4">{quality.source}</a> : quality.source}</p>
          </div>
        ))}
        {report.sources.length ? <SourceLinks ids={report.sources.map(source => source.id)} sources={report.sources} /> : <p className="text-sm text-on-surface-variant">Aucune référence de recherche n’est jointe à ce rapport. Les interprétations restent à distinguer des observations chiffrées et de leurs fournisseurs.</p>}
      </section>
    </div>
  )
}
