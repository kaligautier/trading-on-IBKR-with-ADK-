import { ArrowUpRight } from "lucide-react"

const RESEARCH_QUESTIONS = [
  {
    title: "Understand portfolio state",
    description: "A held position and a pending order describe different states. The workflow must account for both before proposing another trade.",
  },
  {
    title: "Set decision boundaries",
    description: "The investor profile, permitted assets and allocation limits set boundaries for agent proposals.",
  },
  {
    title: "Track what actually happened",
    description: "A proposal, an order submitted to the broker and a confirmed execution are separate steps that need to be tracked individually.",
  },
]

export function RulesSection() {
  return (
    <section id="deep-copy" aria-labelledby="deep-copy-title" className="border-y border-outline-variant py-16 md:py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid gap-8 lg:grid-cols-12 lg:gap-16">
          <div className="min-w-0 lg:col-span-5">
            <h2 id="deep-copy-title" className="text-balance font-display text-4xl font-bold leading-tight tracking-tight md:text-5xl">
              Experimental trading.
              <br />
              <span className="font-medium text-on-surface-muted">Explore the path to execution.</span>
            </h2>
            <p className="mt-6 text-sm font-semibold text-primary-dim">Private experiment</p>
            <p className="mt-4 max-w-prose text-base leading-relaxed text-on-surface-variant">
              This part of Deep Copy explores how agents can analyse a portfolio and prepare trades on Interactive Brokers. Paper trading trials use a simulation account with virtual funds.
            </p>
            <p className="mt-4 max-w-prose text-sm leading-relaxed text-on-surface-variant">
              Access to this workflow is private. Scanner and Momentum can be used independently, without connecting a brokerage account.
            </p>
          </div>
          <div className="min-w-0 lg:col-span-7">
            <h3 className="font-display text-lg font-semibold">Questions this experiment explores</h3>
            <dl className="mt-5 divide-y divide-outline-variant border-y border-outline-variant">
              {RESEARCH_QUESTIONS.map(question => (
                <div key={question.title} className="py-5">
                  <dt className="font-display text-base font-semibold">{question.title}</dt>
                  <dd className="mt-2 text-sm leading-relaxed text-on-surface-variant">{question.description}</dd>
                </div>
              ))}
            </dl>
            <a href="#engineering" className="mt-4 inline-flex min-h-11 items-center gap-2 text-sm font-semibold underline decoration-outline-control underline-offset-4 transition-colors hover:text-primary-dim">
              Explore the Scanner engineering choices <ArrowUpRight className="h-4 w-4 shrink-0" aria-hidden="true" />
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}
