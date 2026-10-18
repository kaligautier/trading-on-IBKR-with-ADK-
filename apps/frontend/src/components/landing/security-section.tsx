import { Code2, Container, Globe, Shield, Eye, KeyRound } from "lucide-react"

const securityItems = [
  {
    icon: Code2,
    stat: "Documented architecture",
    title: "Technical transparency",
    desc: "Each architecture component is documented: algorithms, risk rules and automated decisions are described in our public documentation.",
  },
  {
    icon: Globe,
    stat: "Official IBKR API",
    title: "Direct connection",
    desc: "Deep Copy connects only through the official Interactive Brokers API, without scraping, bypasses or unauthorised access.",
  },
  {
    icon: KeyRound,
    stat: "Two-factor authentication",
    title: "Two-step verification",
    desc: "Each connection to your IBKR gateway requires two-factor authentication. A session cannot be opened without your approval.",
  },
  {
    icon: Container,
    stat: "1 container = 1 user",
    title: "Dedicated isolation",
    desc: "Each IBKR gateway runs in a dedicated Docker container. Your sessions are isolated from those of other users.",
  },
  {
    icon: Eye,
    stat: "Every action logged",
    title: "Full traceability",
    desc: "Agents analyse, recommend and execute within authorised boundaries. Every decision, LLM call and submitted order is logged.",
  },
  {
    icon: Shield,
    stat: "No third-party tracking",
    title: "No data reselling",
    desc: "No advertising, data reselling or commercial use of your portfolio. Your data remains private.",
  },
]

export function SecuritySection() {
  return (
    <section className="border-t border-outline-variant py-20 md:py-28">
      <div className="max-w-6xl mx-auto px-6">
        <div id="security" data-animate="section-heading" className="mb-14 grid gap-8 scroll-mt-20 md:grid-cols-12">
          <div className="md:col-span-7">
            <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-[-0.03em] leading-[1.12] md:leading-[1.08] font-display">
              Understandable infrastructure,
              <br />
              <span className="text-on-surface-muted font-medium">verifiable boundaries.</span>
            </h2>
          </div>
          <div className="self-end md:col-span-5">
            <p className="text-on-surface-variant leading-relaxed text-sm">
              Open source code, isolated infrastructure, the official IBKR API and strong authentication. You stay in control at every step.
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
