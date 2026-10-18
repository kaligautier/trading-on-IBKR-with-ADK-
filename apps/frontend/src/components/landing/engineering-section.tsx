import { ArrowRight, ArrowUpRight, ChevronDown } from "lucide-react"

const REPOSITORY = "https://github.com/kaligautier/trading-on-IBKR-with-ADK-"

const DECISIONS = [
  {
    title: "Why separate report generation from reading?",
    summary: "One analysis can serve many readers without repeating agent calls.",
    choice: "The workflow collects data, calls the agents and saves the report in PostgreSQL. A separate read API then serves that result to the site. Opening the page does not trigger another scan.",
    benefit: "The generation cost is shared across readers. Reading does not wait for the agents, and the latest saved report remains available if a new analysis fails.",
    tradeoff: "An available report can be old, so its date must remain visible. The producer and reader also share a report format that must stay compatible.",
    link: "Read the API contract",
    path: "apps/backend/market-scanner-api/README.md",
  },
  {
    title: "Why keep calculations in Python?",
    summary: "Reproducible calculations, followed by an interpretation from the agents.",
    choice: "Python calculates changes and percentiles from dated observations. The agents use this snapshot to research the context and propose a diagnosis. During assembly, figures come from the calculated data.",
    benefit: "Calculations can be tested with known inputs. Their accuracy can be checked separately from the quality of the explanations produced by the model.",
    tradeoff: "The code still depends on data quality and freshness. The market regime proposed by the agents remains a qualitative interpretation.",
    link: "Explore the calculations",
    path: "apps/backend/market-scanner-adk/src/app/services/market_data_trend_service.py",
  },
  {
    title: "Why add a critical review?",
    summary: "A convincing explanation can still contain contradictions.",
    choice: "After research, a critic agent reviews dates, contradictions and causal explanations. The synthesiser weighs these objections against the available evidence before writing the report and explaining its diagnosis.",
    benefit: "The workflow includes a step to challenge the analysis and make its limits explicit. A critique that does not match the expected format stops the scan before synthesis and persistence.",
    tradeoff: "This step adds a model call. The critic uses the same model and no external tools, so its review is not an independent fact check.",
    link: "Explore the research workflow",
    path: "docs/macro-research.md#research-critique-and-arbitration",
  },
  {
    title: "Why run scans as background jobs?",
    summary: "Accepting a request and completing an analysis are different states.",
    choice: "The scheduled trigger submits a Cloud Run Job that runs the workflow. The job requires a persisted report before it considers the run successful.",
    benefit: "The analysis runs without keeping an HTTP request open throughout. An accepted launch is not enough to announce that a new report is available.",
    tradeoff: "The agent session stays in memory during the job. Saving the final report does not allow the graph to resume automatically from an interrupted step.",
    link: "Explore the job runner",
    path: "apps/backend/market-scanner-adk/src/app/jobs/daily_scan.py",
  },
]

const PIPELINE = [
  { title: "Data", detail: "Data collection and Python calculations" },
  { title: "Analysis", detail: "Research, review and synthesis" },
  { title: "Persistence", detail: "Validation and PostgreSQL storage" },
  { title: "Reading", detail: "Read API, then display on the site" },
]

export function EngineeringSection() {
  return (
    <section id="engineering" aria-labelledby="engineering-title" className="border-t border-outline-variant py-20 md:py-28">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid gap-10 lg:grid-cols-12 lg:gap-16">
          <div className="min-w-0 lg:col-span-5">
            <h2 id="engineering-title" className="text-balance font-display text-4xl font-bold leading-tight tracking-tight md:text-5xl">
              Engineering.
              <br />
              <span className="font-medium text-on-surface-muted">The choices behind Deep Copy.</span>
            </h2>
            <p className="mt-6 max-w-prose text-base leading-relaxed text-on-surface-variant">
              Market Scanner is the example: why separate the stages, where to enforce checks and which tradeoffs to accept. Each choice links to the project code.
            </p>
            <a href={REPOSITORY} className="mt-5 inline-flex min-h-11 items-center gap-2 text-sm font-semibold underline decoration-outline-control underline-offset-4 transition-colors hover:text-primary-dim">
              Explore the code on GitHub <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
            </a>
          </div>
          <div className="min-w-0 divide-y divide-outline-variant border-y border-outline-variant lg:col-span-7">
            {DECISIONS.map((decision, index) => (
              <details key={decision.title} open={index === 0} className="group">
                <summary className="cursor-pointer list-none py-6 transition-colors hover:text-primary-dim [&::-webkit-details-marker]:hidden">
                  <h3 className="text-lg font-semibold leading-snug">
                    <span className="flex items-start justify-between gap-4 font-display">
                      <span>{decision.title}</span>
                      <ChevronDown className="mt-1 h-5 w-5 shrink-0 text-on-surface-muted transition-transform group-open:rotate-180 motion-reduce:transition-none" aria-hidden="true" />
                    </span>
                    <span className="mt-2 block pr-9 text-sm font-normal leading-relaxed text-on-surface-variant">{decision.summary}</span>
                  </h3>
                </summary>
                <div className="pb-6">
                  <dl className="space-y-5 text-sm leading-relaxed">
                    <div>
                      <dt className="font-semibold">The choice</dt>
                      <dd className="mt-1 text-on-surface-variant">{decision.choice}</dd>
                    </div>
                    <div>
                      <dt className="font-semibold">The benefit</dt>
                      <dd className="mt-1 text-on-surface-variant">{decision.benefit}</dd>
                    </div>
                    <div>
                      <dt className="font-semibold">The tradeoff</dt>
                      <dd className="mt-1 text-on-surface-variant">{decision.tradeoff}</dd>
                    </div>
                  </dl>
                  <a href={`${REPOSITORY}/blob/main/${decision.path}`} className="mt-4 inline-flex min-h-11 items-center gap-2 text-sm font-medium underline decoration-outline-control underline-offset-4 transition-colors hover:text-primary-dim">
                    {decision.link} <ArrowUpRight className="h-4 w-4 shrink-0" aria-hidden="true" />
                  </a>
                </div>
              </details>
            ))}
          </div>
        </div>
        <ol aria-label="From market snapshot to published report" className="mt-12 grid gap-6 border-t border-outline-variant pt-8 sm:grid-cols-2 lg:grid-cols-4">
          {PIPELINE.map((step, index) => (
            <li key={step.title} className="min-w-0">
              <div className="flex items-center justify-between gap-3">
                <p className="font-display text-sm font-semibold">{step.title}</p>
                {index < PIPELINE.length - 1 && <ArrowRight className="hidden h-4 w-4 shrink-0 text-on-surface-muted lg:block" aria-hidden="true" />}
              </div>
              <p className="mt-1 text-xs leading-relaxed text-on-surface-variant">{step.detail}</p>
            </li>
          ))}
        </ol>
        <div className="mt-10 grid gap-4 border-t border-outline-variant pt-8 lg:grid-cols-12 lg:gap-16">
          <h3 className="font-display text-lg font-semibold lg:col-span-5">What the tests check.</h3>
          <div className="min-w-0 lg:col-span-7">
            <p className="max-w-prose text-sm leading-relaxed text-on-surface-variant">
              Tests cover calculations, report formatting and API responses. These checks verify software behaviour. They do not measure its ability to predict markets.
            </p>
            <a href={`${REPOSITORY}/tree/main/apps/backend/market-scanner-api/src/test`} className="mt-2 inline-flex min-h-11 items-center gap-2 text-sm font-medium underline decoration-outline-control underline-offset-4 transition-colors hover:text-primary-dim">
              Explore the API tests <ArrowUpRight className="h-4 w-4 shrink-0" aria-hidden="true" />
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}
