import { ArrowRight, ArrowUpRight } from "lucide-react"

const REPOSITORY = "https://github.com/kaligautier/trading-on-IBKR-with-ADK-"

const DECISIONS = [
  {
    title: "Calculer avant d’interpréter",
    description: "Python calcule les variations et les percentiles à partir d’observations datées. Les agents s’appuient sur ce relevé pour formuler leur diagnostic.",
    link: "Voir les calculs",
    path: "apps/backend/market-scanner-adk/src/app/services/market_data_trend_service.py",
  },
  {
    title: "Confronter l’analyse avant la synthèse",
    description: "Après la recherche, un agent critique examine les contradictions, les dates et les explications causales. Le synthétiseur pèse ces objections avant de rédiger le rapport.",
    link: "Lire le workflow de recherche",
    path: "docs/macro-research.md#research-critique-and-arbitration",
  },
  {
    title: "Produire une fois, consulter ensuite",
    description: "Le rapport est enregistré dans PostgreSQL. Une API de lecture distincte le restitue : consulter la landing ne relance pas les agents.",
    link: "Comprendre l’API de lecture",
    path: "apps/backend/market-scanner-api/README.md",
  },
]

const PIPELINE = [
  { title: "Collecte", detail: "Observations datées" },
  { title: "Calcul", detail: "Variations et percentiles" },
  { title: "Analyse", detail: "Recherche, critique, synthèse" },
  { title: "Publication", detail: "Rapport enregistré, puis consulté" },
]

export function EngineeringSection() {
  return (
    <section id="engineering" aria-labelledby="engineering-title" className="border-t border-outline-variant py-20 md:py-28">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid gap-10 lg:grid-cols-12 lg:gap-16">
          <div className="lg:col-span-5">
            <h2 id="engineering-title" className="text-balance font-display text-4xl font-bold leading-tight tracking-tight md:text-5xl">
              Engineering.
              <br />
              <span className="font-medium text-on-surface-muted">Les choix derrière le rapport.</span>
            </h2>
            <p className="mt-6 max-w-prose text-sm leading-relaxed text-on-surface-variant">
              Le Market Scanner comme cas concret : du calcul des données à la lecture du résultat,
              chaque étape a une responsabilité et du code à examiner.
            </p>
            <a href={REPOSITORY} className="mt-5 inline-flex min-h-11 items-center gap-2 text-sm font-semibold underline decoration-outline-control underline-offset-4 transition-colors hover:text-primary-dim">
              Explorer le code sur GitHub <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
            </a>
          </div>
          <dl className="divide-y divide-outline-variant border-y border-outline-variant lg:col-span-7">
            {DECISIONS.map(decision => (
              <div key={decision.title} className="py-6">
                <dt className="font-display text-lg font-semibold">{decision.title}</dt>
                <dd>
                  <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">{decision.description}</p>
                  <a href={`${REPOSITORY}/blob/main/${decision.path}`} className="mt-2 inline-flex min-h-11 items-center gap-2 text-sm font-medium underline decoration-outline-control underline-offset-4 transition-colors hover:text-primary-dim">
                    {decision.link} <ArrowUpRight className="h-4 w-4 shrink-0" aria-hidden="true" />
                  </a>
                </dd>
              </div>
            ))}
          </dl>
        </div>
        <ol aria-label="Du relevé de marché au rapport consultable" className="mt-12 grid gap-6 border-t border-outline-variant pt-8 sm:grid-cols-2 lg:grid-cols-4">
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
        <p className="mt-6 max-w-prose text-xs leading-relaxed text-on-surface-muted">
          Le régime de marché reste une interprétation qualitative. Les tests du logiciel ne mesurent pas sa capacité à prévoir les marchés.
        </p>
      </div>
    </section>
  )
}
