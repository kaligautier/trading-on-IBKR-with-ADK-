import { ArrowDown, Eye, Landmark, SlidersHorizontal } from "lucide-react"
import { PublicActions } from "./public-actions"

const TRUST_POINTS = [
  {
    icon: Landmark,
    title: "Connecté à Interactive Brokers",
    description: "Deep Copy analyse un portefeuille et transmet ses ordres à IBKR via une gateway et un serveur MCP dédiés.",
  },
  {
    icon: SlidersHorizontal,
    title: "Des décisions sous contraintes",
    description: "Chaque agent agit selon des règles explicites de risque, d’allocation et d’exécution.",
  },
  {
    icon: Eye,
    title: "Une traçabilité complète",
    description: "Analyses, appels d’outils, décisions et ordres sont journalisés pour permettre leur inspection.",
  },
]

export function HeroSection() {
  return (
    <section className="relative overflow-x-clip pt-28 pb-16 md:pt-40 md:pb-24 lg:pt-44 lg:pb-28">
      <div
        data-motion-loop
        className="hero-signal-field pointer-events-none absolute -top-40 left-1/2 h-[600px] w-[900px] -translate-x-1/2 rounded-[50%]"
      />

      <div className="relative mx-auto grid max-w-6xl items-end gap-14 px-6 lg:grid-cols-12 lg:gap-12">
        <div className="lg:col-span-7">
          <h1 data-animate="hero-title" className="max-w-3xl text-5xl font-bold leading-[1.04] tracking-[-0.04em] font-display sm:text-6xl md:text-7xl md:leading-[1.02] lg:text-8xl">
            Vos agents IA tradent.
            <br />
            <span className="font-medium text-on-surface-muted">Vous dormez.</span>
          </h1>

          <p data-animate="hero-copy" data-delay="80" className="mt-7 max-w-2xl text-base leading-relaxed text-on-surface-variant md:mt-8 md:text-lg">
            Deep Copy est mon projet de recherche agentique. Il vise à démontrer la capacité des
            LLMs à analyser un contexte de marché, à utiliser des outils et à prendre des décisions de
            trading dans un environnement contrôlé.
          </p>

          <div data-animate="hero-form" data-delay="160" className="mt-9 max-w-xl md:mt-10">
            <PublicActions />
          </div>
        </div>

        <div data-animate="trust-stack" data-delay="180" className="lg:col-span-5 lg:pb-1">
          <div className="border-y border-outline-variant">
            {TRUST_POINTS.map((point, index) => (
              <div key={point.title} data-motion-item={index} className="grid grid-cols-[2.75rem_1fr] gap-4 border-b border-outline-variant py-5 last:border-b-0 md:py-6">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-surface-low">
                  <point.icon className="h-4.5 w-4.5 text-on-surface" aria-hidden="true" />
                </div>
                <div>
                  <h2 className="font-display text-sm font-semibold tracking-[-0.01em] md:text-base">{point.title}</h2>
                  <p className="mt-1 text-sm leading-relaxed text-on-surface-variant">{point.description}</p>
                </div>
              </div>
            ))}
          </div>

          <a
            href="#products"
            className="mt-5 inline-flex min-h-11 items-center gap-2 text-sm font-medium text-on-surface-variant transition-colors hover:text-on-surface"
          >
            Voir les trois usages
            <ArrowDown className="h-4 w-4" aria-hidden="true" />
          </a>
        </div>
      </div>
    </section>
  )
}
