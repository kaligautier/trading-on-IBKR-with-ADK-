import { Code2, Container, Globe, Shield, Eye, KeyRound } from "lucide-react"

const securityItems = [
  {
    icon: Code2,
    stat: "Architecture documentée",
    title: "Transparence technique",
    desc: "Chaque composant de l'architecture est documenté : algorithmes, règles de risque et décisions automatisées sont décrits publiquement dans nos docs.",
  },
  {
    icon: Globe,
    stat: "API officielle IBKR",
    title: "Connexion directe",
    desc: "Deep Copy se connecte uniquement via l'API officielle Interactive Brokers. Aucun scraping, aucun contournement, aucun accès non autorisé.",
  },
  {
    icon: KeyRound,
    stat: "Authentification 2FA",
    title: "Double vérification",
    desc: "Chaque connexion à votre gateway IBKR nécessite une authentification à deux facteurs. Aucune session ne peut être ouverte sans votre validation.",
  },
  {
    icon: Container,
    stat: "1 conteneur = 1 utilisateur",
    title: "Isolation dédiée",
    desc: "Chaque gateway IBKR fonctionne dans un conteneur Docker dédié. Vos sessions sont isolées de celles des autres utilisateurs.",
  },
  {
    icon: Eye,
    stat: "Chaque action loguée",
    title: "Traçabilité complète",
    desc: "Les agents analysent, recommandent et exécutent uniquement dans le cadre autorisé. Chaque décision, appel LLM et ordre transmis est tracé.",
  },
  {
    icon: Shield,
    stat: "Zéro tracking tiers",
    title: "Aucune donnée revendue",
    desc: "Pas de publicité, pas de revente de données, pas d'exploitation commerciale de votre portefeuille. Vos données restent strictement privées.",
  },
]

export function SecuritySection() {
  return (
    <section className="border-t border-outline-variant py-20 md:py-28">
      <div className="max-w-6xl mx-auto px-6">
        <div id="security" data-animate="section-heading" className="mb-14 grid gap-8 scroll-mt-20 md:grid-cols-12">
          <div className="md:col-span-7">
            <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-[-0.03em] leading-[1.12] md:leading-[1.08] font-display">
              Une infrastructure lisible,
              <br />
              <span className="text-on-surface-muted font-medium">des limites vérifiables.</span>
            </h2>
          </div>
          <div className="self-end md:col-span-5">
            <p className="text-on-surface-variant leading-relaxed text-sm">
              Code ouvert, infrastructure isolée, connexion via l'API officielle IBKR
              et authentification forte. Vous gardez le contrôle à chaque étape.
            </p>
          </div>
        </div>

        <div data-animate="security-grid" className="grid grid-cols-1 gap-x-8 md:grid-cols-2 lg:grid-cols-3">
          {securityItems.map((item, index) => (
            <div key={item.title} data-motion-item={index} className="security-row border-t border-outline-variant py-6">
              <div className="flex items-start justify-between mb-5">
                <div className="security-node w-9 h-9 rounded-xl bg-surface-low flex items-center justify-center">
                  <item.icon className="w-4 h-4 text-on-surface" aria-hidden="true" />
                </div>
                <span className="text-xs font-medium text-on-surface-muted">
                  {item.stat}
                </span>
              </div>
              <h3 className="text-sm font-semibold font-display mb-2">{item.title}</h3>
              <p className="text-xs text-on-surface-variant leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
