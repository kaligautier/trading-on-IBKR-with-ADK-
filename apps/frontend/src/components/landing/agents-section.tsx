import { Eye, Brain, Zap, ShieldCheck, LineChart, Bot } from "lucide-react"

const agents = [
  {
    icon: Eye,
    name: "Veille",
    role: "Market Watcher",
    desc: "Surveille les marchés en continu et détecte les opportunités d'achat en temps réel.",
  },
  {
    icon: Brain,
    name: "Stratégie",
    role: "Portfolio Strategist",
    desc: "Analyse votre allocation, calibre votre profil de risque et recommande des ajustements.",
  },
  {
    icon: ShieldCheck,
    name: "Risque",
    role: "Risk Manager",
    desc: "Surveille en continu les limites de drawdown définies et ne valide que les ordres conformes.",
  },
  {
    icon: Zap,
    name: "Trader",
    role: "Execution Engine",
    desc: "Exécute les ordres sur Interactive Brokers : DCA, rééquilibrage, ordres conditionnels.",
  },
  {
    icon: LineChart,
    name: "Reporting",
    role: "Performance Analyst",
    desc: "Génère vos rapports de performance et synthétise l'activité de l'équipe chaque semaine.",
  },
]

const orchestrationLogs = [
  { time: "08:59", agent: "Veille", action: "Signal détecté : IWDA sous MM50, zone d'achat", type: "warn" },
  { time: "09:00", agent: "Stratégie", action: "Validation : cohérent avec allocation cible (+2% ETF World)", type: "info" },
  { time: "09:00", agent: "Risque", action: "Vérification : exposition OK, drawdown 4.2% < limite 12%", type: "ok" },
  { time: "09:01", agent: "Trader", action: "Ordre simulé : Achat 3x IWDA @ 82,34 € via IBKR paper", type: "ok" },
  { time: "09:02", agent: "Reporting", action: "Portefeuille simulé mis à jour. Variation du mois : +2,4 %", type: "muted" },
]

const logColor: Record<string, string> = {
  warn: "text-warning",
  info: "text-on-surface-variant",
  ok: "text-success",
  muted: "text-on-surface-muted",
}

export function AgentsSection() {
  return (
    <section className="py-20 md:py-28">
      <div className="max-w-6xl mx-auto px-6">
        <div id="agents" data-animate="section-heading" className="mb-14 grid gap-8 scroll-mt-20 md:mb-16 md:grid-cols-12">
          <div className="md:col-span-7">
            <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-[-0.03em] leading-[1.12] md:leading-[1.08] font-display">
              De l&apos;analyse à l&apos;ordre simulé.
              <br />
              <span className="text-on-surface-muted font-medium">Chaque étape reste lisible.</span>
            </h2>
          </div>
          <div className="self-end md:col-span-5">
            <p className="text-on-surface-variant leading-relaxed text-sm">
              Vous connectez votre compte Interactive Brokers paper. Cinq agents spécialisés analysent
              le portefeuille, vérifient vos règles et documentent chaque simulation dans un journal commun.
            </p>
          </div>
        </div>

        <div
          data-animate="agent-handoff"
          className="grid items-start gap-4 lg:grid-cols-12"
        >
          <div
            className="rounded-2xl border border-outline-variant/60 bg-surface-lowest p-5 md:p-8 lg:col-span-7"
          >
            <div className="mb-5 flex flex-wrap items-center gap-3 border-b border-outline-variant pb-5 md:mb-6">
              <Bot className="h-4 w-4 text-on-surface-variant" aria-hidden="true" />
              <h3 className="font-display text-sm font-semibold">Scénario de paper trading</h3>
              <div className="ml-auto flex items-center gap-1.5">
                <span
                  data-motion-marker="agent-signal"
                  className="agent-status-signal"
                  aria-hidden="true"
                />
                <span className="text-xs text-on-surface-muted">Démonstration illustrative</span>
              </div>
            </div>
            <div className="orchestration-timeline">
              {orchestrationLogs.map((log, i) => (
                <div
                  key={log.time + log.agent}
                  data-orchestration-step={i}
                  data-log-type={log.type}
                  className="orchestration-event grid grid-cols-[3.75rem_1fr] gap-x-5 gap-y-1 border-b border-outline-variant/60 px-2 py-3 last:border-b-0 sm:grid-cols-[3.75rem_5.75rem_1fr] sm:items-baseline"
                >
                  <span className="whitespace-nowrap font-mono text-xs tabular-nums text-on-surface-muted">{log.time}</span>
                  <span className="text-xs font-semibold text-on-surface-variant">{log.agent}</span>
                  <span className={`col-span-2 text-xs leading-relaxed sm:col-span-1 ${logColor[log.type]}`}>{log.action}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="agent-roster grid gap-3 sm:grid-cols-2 lg:col-span-5 lg:grid-cols-1">
            {agents.map((agent, index) => (
              <div
                key={agent.name}
                data-orchestration-step={index}
                className="grid grid-cols-[2.75rem_1fr] gap-4 border-t border-outline-variant py-4 first:border-t-0 lg:first:border-t"
              >
                <div className="agent-signal-node flex h-11 w-11 items-center justify-center rounded-xl bg-surface-low">
                  <agent.icon className="h-4.5 w-4.5 text-on-surface" aria-hidden="true" />
                </div>
                <div>
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <h3 className="font-display text-sm font-semibold">{agent.name}</h3>
                    <span className="font-mono text-xs text-on-surface-muted">{agent.role}</span>
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-on-surface-variant">{agent.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
