import { ArrowUpRight } from "lucide-react"

const RESEARCH_QUESTIONS = [
  {
    title: "Comprendre l’état du portefeuille",
    description: "Une position détenue et un ordre encore en attente décrivent deux états différents. Le workflow doit tenir compte des deux avant de proposer une nouvelle opération.",
  },
  {
    title: "Encadrer les décisions",
    description: "Le profil investisseur, les actifs autorisés et les limites d’allocation donnent un cadre aux propositions des agents.",
  },
  {
    title: "Suivre ce qui a réellement eu lieu",
    description: "Une proposition, un ordre transmis au courtier et une exécution confirmée sont des étapes distinctes à suivre séparément.",
  },
]

export function RulesSection() {
  return (
    <section id="deep-copy" aria-labelledby="deep-copy-title" className="border-y border-outline-variant py-16 md:py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid gap-8 lg:grid-cols-12 lg:gap-16">
          <div className="min-w-0 lg:col-span-5">
            <h2 id="deep-copy-title" className="text-balance font-display text-4xl font-bold leading-tight tracking-tight md:text-5xl">
              Trading expérimental.
              <br />
              <span className="font-medium text-on-surface-muted">Étudier le passage à l’action.</span>
            </h2>
            <p className="mt-6 text-sm font-semibold text-primary-dim">Expérimentation privée</p>
            <p className="mt-4 max-w-prose text-base leading-relaxed text-on-surface-variant">
              Ce volet de Deep Copy explore comment des agents peuvent analyser un portefeuille
              et préparer des opérations sur Interactive Brokers. Les essais en paper trading
              utilisent un compte de simulation, avec de l’argent fictif.
            </p>
            <p className="mt-4 max-w-prose text-sm leading-relaxed text-on-surface-variant">
              L’accès à ce workflow est privé. Le Scanner et Momentum restent utilisables
              indépendamment, sans connecter de compte de courtage.
            </p>
          </div>
          <div className="min-w-0 lg:col-span-7">
            <h3 className="font-display text-lg font-semibold">Les questions que ce volet explore</h3>
            <dl className="mt-5 divide-y divide-outline-variant border-y border-outline-variant">
              {RESEARCH_QUESTIONS.map(question => (
                <div key={question.title} className="py-5">
                  <dt className="font-display text-base font-semibold">{question.title}</dt>
                  <dd className="mt-2 text-sm leading-relaxed text-on-surface-variant">{question.description}</dd>
                </div>
              ))}
            </dl>
            <a href="#engineering" className="mt-4 inline-flex min-h-11 items-center gap-2 text-sm font-semibold underline decoration-outline-control underline-offset-4 transition-colors hover:text-primary-dim">
              Explorer les choix d’ingénierie du Scanner <ArrowUpRight className="h-4 w-4 shrink-0" aria-hidden="true" />
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}
