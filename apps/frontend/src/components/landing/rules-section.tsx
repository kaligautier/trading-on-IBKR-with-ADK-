import { Shield, DollarSign, Clock, ArrowUpDown, TrendingDown, OctagonX } from "lucide-react"

const criticalRules = [
  { icon: OctagonX, label: "Arrêt d'urgence", desc: "Stoppez toute activité en un clic, à tout moment." },
  { icon: TrendingDown, label: "Drawdown maximal", desc: "L'agent s'arrête si la perte dépasse votre seuil." },
]

const configurationRules = [
  { icon: Shield, label: "Actifs autorisés", desc: "Définissez les ETF, actions ou classes d'actifs que l'agent peut toucher." },
  { icon: DollarSign, label: "Budget maximal", desc: "Fixez un montant plafond par opération ou par période." },
  { icon: Clock, label: "Fréquence", desc: "Quotidien, hebdomadaire ou mensuel — vous choisissez le rythme." },
  { icon: ArrowUpDown, label: "Achat / Vente", desc: "Achat seul, vente seule, ou les deux. Vous décidez." },
]

export function RulesSection() {
  return (
    <section id="deep-copy" aria-labelledby="deep-copy-title" className="border-y border-outline-variant bg-surface-low py-20 md:py-28">
      <div className="max-w-6xl mx-auto px-6">
        <div data-animate="section-heading" className="mb-12 max-w-3xl scroll-mt-20 md:mb-16">
          <h2 id="deep-copy-title" className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-[-0.03em] leading-[1.12] md:leading-[1.08] font-display mb-6">
            Deep Copy cadre chaque décision.
            <br />
            <span className="text-on-surface-muted font-medium">Vous fixez les limites.</span>
          </h2>
          <p className="text-on-surface-variant leading-relaxed max-w-2xl text-base">
            L&apos;application fonctionne actuellement en paper trading. Avant chaque simulation,
            vous définissez les actifs, le budget, la fréquence et le niveau de risque autorisés.
          </p>
        </div>

        <div data-animate="control-locks" className="grid gap-3 lg:grid-cols-2">
          {criticalRules.map((rule, index) => (
            <div
              key={rule.label}
              data-motion-item={index}
              className="control-lock rounded-2xl bg-on-surface p-6 text-surface-lowest md:p-8"
            >
              <div className="mb-8 flex items-center justify-between gap-4">
                <div className="control-lock-node flex h-11 w-11 items-center justify-center rounded-xl bg-white/10">
                  <rule.icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <span className="text-xs text-surface-highest">Contrôle prioritaire</span>
              </div>
              <h3 className="font-display text-xl font-semibold tracking-[-0.02em] md:text-2xl">{rule.label}</h3>
              <p className="mt-2 max-w-md text-sm leading-relaxed text-surface-highest">{rule.desc}</p>
            </div>
          ))}
        </div>

        <div data-animate="rule-list" className="mt-8 grid gap-x-6 sm:grid-cols-2 lg:grid-cols-4">
          {configurationRules.map((rule, index) => (
            <div key={rule.label} data-motion-item={index} className="border-t border-outline-variant py-6">
              <div className="rule-node flex h-10 w-10 items-center justify-center rounded-xl bg-surface-lowest">
                <rule.icon className="h-4 w-4 text-on-surface" aria-hidden="true" />
              </div>
              <h3 className="mt-5 font-display text-sm font-semibold">{rule.label}</h3>
              <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">{rule.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
