import type { MarketScan } from "@/lib/market-scanner/report"

export function Arbitration({ report }: { report: MarketScan["report"] }) {
  const arbitration = report.arbitration
  if (!arbitration) return (
    <div className="space-y-4">
      <p className="text-sm text-on-surface-muted">Arbitrage non renseigné pour ce rapport.</p>
      {report.watch_points.length > 0 && <section aria-labelledby="watch-points-title">
        <h3 id="watch-points-title" className="font-display text-lg font-semibold">Points à surveiller</h3>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-on-surface-variant">
          {report.watch_points.map((point, index) => <li key={index}>{point}</li>)}
        </ul>
      </section>}
    </div>
  )
  return (
    <section aria-labelledby="arbitration-title" className="space-y-5 break-words">
      <h3 id="arbitration-title" className="font-display text-xl font-bold">Comment le diagnostic est retenu</h3>
      <div className="grid gap-5 md:grid-cols-2">
        <div className="min-w-0 border-l-2 border-outline-variant pl-4">
          <h4 className="font-semibold">Ce qui soutient le diagnostic</h4>
          <ul className="mt-2 list-disc space-y-2 pl-4 text-sm leading-relaxed text-on-surface-variant">
            {arbitration.supporting_factors.map((factor, index) => <li key={index}>{factor}</li>)}
          </ul>
        </div>
        <div className="min-w-0 border-l-2 border-outline-variant pl-4">
          <h4 className="font-semibold">Principal contre-argument</h4>
          <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">{arbitration.main_counterargument}</p>
        </div>
      </div>
      <div>
        <h4 className="font-semibold">Pourquoi ce diagnostic</h4>
        <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">{arbitration.decision_rationale}</p>
      </div>
      <div>
        <h4 className="font-semibold">Ce qui ferait changer le diagnostic</h4>
        {arbitration.invalidation_conditions.length > 0 ? (
          <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed text-on-surface-variant">
            {arbitration.invalidation_conditions.map((condition, index) => <li key={index}>{condition}</li>)}
          </ul>
        ) : <p className="mt-2 text-sm text-on-surface-muted">Aucune condition précisée dans ce rapport.</p>}
      </div>
    </section>
  )
}
