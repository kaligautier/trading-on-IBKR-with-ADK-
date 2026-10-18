import { ArrowRight, ArrowUpRight, ChevronDown } from "lucide-react"

const REPOSITORY = "https://github.com/kaligautier/trading-on-IBKR-with-ADK-"

const DECISIONS = [
  {
    title: "Pourquoi séparer production et consultation ?",
    summary: "Une analyse peut servir à plusieurs lecteurs, sans multiplier les appels aux agents.",
    choice: "Le workflow collecte les données, appelle les agents et enregistre le rapport dans PostgreSQL. Une API de lecture distincte sert ensuite ce résultat au site. Ouvrir la page ne déclenche aucun nouveau scan.",
    benefit: "Le coût de génération est partagé entre les consultations. La lecture n’attend pas les agents et le dernier rapport enregistré reste accessible si une nouvelle analyse échoue.",
    tradeoff: "Un rapport disponible peut être ancien : sa date doit rester visible. Le producteur et le lecteur partagent aussi un format de rapport dont il faut maintenir la compatibilité.",
    link: "Lire le contrat de l’API de consultation",
    path: "apps/backend/market-scanner-api/README.md",
  },
  {
    title: "Pourquoi garder les calculs en Python ?",
    summary: "Des chiffres calculés de façon reproductible, puis une interprétation par les agents.",
    choice: "Python calcule les variations et les percentiles à partir d’observations datées. Les agents reçoivent ce relevé pour rechercher le contexte et proposer un diagnostic. À l’assemblage, les chiffres sont repris depuis les données calculées.",
    benefit: "Les calculs peuvent être testés avec des entrées connues. Leur exactitude se vérifie séparément de la qualité des explications produites par le modèle.",
    tradeoff: "Le code reste dépendant de la qualité et de la fraîcheur des données. Le régime de marché proposé par les agents reste une interprétation qualitative.",
    link: "Voir les calculs",
    path: "apps/backend/market-scanner-adk/src/app/services/market_data_trend_service.py",
  },
  {
    title: "Pourquoi ajouter une relecture critique ?",
    summary: "Une explication convaincante peut encore contenir des contradictions.",
    choice: "Après la recherche, un agent critique examine les dates, les contradictions et les explications causales. Le synthétiseur confronte ces objections aux éléments disponibles avant de rédiger le rapport et les raisons de son diagnostic.",
    benefit: "Le workflow prévoit une étape pour contester l’analyse et expliciter ses limites. Une critique qui ne respecte pas le format attendu arrête le scan avant la synthèse et la sauvegarde.",
    tradeoff: "Cette étape ajoute un appel au modèle. Le critique utilise le même modèle et aucun outil externe : sa relecture ne constitue pas une vérification indépendante des faits.",
    link: "Lire le workflow de recherche",
    path: "docs/macro-research.md#research-critique-and-arbitration",
  },
  {
    title: "Pourquoi lancer les scans en tâche de fond ?",
    summary: "Accepter une demande et terminer une analyse sont deux états différents.",
    choice: "Le déclenchement planifié soumet un Cloud Run Job, qui exécute le workflow. Le code du job exige un rapport persisté avant de considérer le traitement comme réussi.",
    benefit: "L’analyse avance sans garder une requête HTTP ouverte pendant toute sa durée. Un lancement accepté ne suffit pas à annoncer qu’un nouveau rapport est disponible.",
    tradeoff: "La session des agents reste en mémoire pendant le job. Conserver le rapport final ne permet donc pas de reprendre automatiquement le graphe à l’étape interrompue.",
    link: "Voir l’exécution du job",
    path: "apps/backend/market-scanner-adk/src/app/jobs/daily_scan.py",
  },
]

const PIPELINE = [
  { title: "Données", detail: "Collecte et calculs Python" },
  { title: "Analyse", detail: "Recherche, critique, synthèse" },
  { title: "Persistance", detail: "Validation et sauvegarde PostgreSQL" },
  { title: "Consultation", detail: "API de lecture, puis affichage sur le site" },
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
              <span className="font-medium text-on-surface-muted">Les choix derrière Deep Copy.</span>
            </h2>
            <p className="mt-6 max-w-prose text-base leading-relaxed text-on-surface-variant">
              Le Market Scanner sert de fil conducteur : pourquoi séparer les étapes,
              où placer les contrôles et quels compromis accepter.
              Chaque choix renvoie au code du projet.
            </p>
            <a href={REPOSITORY} className="mt-5 inline-flex min-h-11 items-center gap-2 text-sm font-semibold underline decoration-outline-control underline-offset-4 transition-colors hover:text-primary-dim">
              Explorer le code sur GitHub <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
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
                      <dt className="font-semibold">Le choix</dt>
                      <dd className="mt-1 text-on-surface-variant">{decision.choice}</dd>
                    </div>
                    <div>
                      <dt className="font-semibold">Ce que cela apporte</dt>
                      <dd className="mt-1 text-on-surface-variant">{decision.benefit}</dd>
                    </div>
                    <div>
                      <dt className="font-semibold">Le compromis</dt>
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
        <div className="mt-10 grid gap-4 border-t border-outline-variant pt-8 lg:grid-cols-12 lg:gap-16">
          <h3 className="font-display text-lg font-semibold lg:col-span-5">Ce que les tests vérifient.</h3>
          <div className="min-w-0 lg:col-span-7">
            <p className="max-w-prose text-sm leading-relaxed text-on-surface-variant">
              Les tests couvrent notamment les calculs, le format des rapports et leur restitution
              par l’API. Ces vérifications portent sur le fonctionnement du logiciel.
              Elles ne mesurent pas sa capacité à prévoir les marchés.
            </p>
            <a href={`${REPOSITORY}/tree/main/apps/backend/market-scanner-api/src/test`} className="mt-2 inline-flex min-h-11 items-center gap-2 text-sm font-medium underline decoration-outline-control underline-offset-4 transition-colors hover:text-primary-dim">
              Examiner les tests de l’API <ArrowUpRight className="h-4 w-4 shrink-0" aria-hidden="true" />
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}
