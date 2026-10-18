import type { MarketScan } from "@/lib/market-scanner/report"

export function Arbitration({ report }: { report: MarketScan["report"] }) {
  const arbitration = report.arbitration
  if (!arbitration) return (
    <div className="space-y-4">
      <p className="text-sm text-on-surface-muted">No decision rationale was provided for this report.</p>
      <WatchPoints points={report.watch_points} />
    </div>
  )
  return (
    <div className="space-y-5">
    <section aria-labelledby="arbitration-title" className="space-y-5 break-words">
      <h3 id="arbitration-title" className="font-display text-xl font-bold">How the diagnosis was reached</h3>
      <div className="grid gap-5 md:grid-cols-2">
        <div className="min-w-0 border-l-2 border-outline-variant pl-4">
          <h4 className="font-semibold">Supporting observations</h4>
          <ul className="mt-2 list-disc space-y-2 pl-4 text-sm leading-relaxed text-on-surface-variant">
            {arbitration.supporting_factors.map((factor, index) => <li key={index}>{factor}</li>)}
          </ul>
        </div>
        <div className="min-w-0 border-l-2 border-outline-variant pl-4">
          <h4 className="font-semibold">Main counterargument</h4>
          <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">{arbitration.main_counterargument}</p>
        </div>
      </div>
      <div>
        <h4 className="font-semibold">Why this diagnosis</h4>
        <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">{arbitration.decision_rationale}</p>
      </div>
      <div>
        <h4 className="font-semibold">What would change the diagnosis</h4>
        {arbitration.invalidation_conditions.length > 0 ? (
          <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed text-on-surface-variant">
            {arbitration.invalidation_conditions.map((condition, index) => <li key={index}>{condition}</li>)}
          </ul>
        ) : <p className="mt-2 text-sm text-on-surface-muted">No conditions were specified in this report.</p>}
      </div>
    </section>
    <WatchPoints points={report.watch_points} />
    </div>
  )
}

function WatchPoints({ points }: { points: string[] }) {
  if (points.length === 0) return null
  return (
    <section aria-labelledby="watch-points-title">
        <h3 id="watch-points-title" className="font-display text-lg font-semibold">Watch points</h3>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-on-surface-variant">
          {points.map((point, index) => <li key={index}>{point}</li>)}
        </ul>
      </section>
  )
}
