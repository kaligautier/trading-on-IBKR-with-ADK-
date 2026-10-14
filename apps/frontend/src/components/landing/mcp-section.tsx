import Link from "next/link"
import { ArrowUpRight, Braces, Check, Radio } from "lucide-react"
import { CopyEndpointButton } from "./copy-endpoint-button"

const MCP_TOOLS = ["list_analyses", "get_analysis", "get_recommendations", "latest_market_scan"]

export function McpSection() {
  return (
    <section id="momentum-mcp" aria-labelledby="momentum-mcp-title" className="scroll-mt-20 border-t border-outline-variant py-20 md:py-28">
      <div className="mx-auto max-w-6xl px-6">
        <div data-animate="section-heading" className="mb-14 grid gap-8 md:grid-cols-12">
          <div className="md:col-span-8">
            <h2 id="momentum-mcp-title" className="font-display text-4xl font-bold leading-[1.12] tracking-[-0.035em] md:text-6xl md:leading-[1.08] lg:text-7xl">
              Momentum MCP donne le contexte
              <br />
              <span className="font-medium text-on-surface-muted">à vos propres agents.</span>
            </h2>
          </div>
          <div className="self-end md:col-span-4">
            <p className="text-sm leading-relaxed text-on-surface-variant md:text-base">
              Analyses et recommandations accessibles à Claude, ChatGPT et vos workflows compatibles
              grâce à un serveur public, sans clé API.
            </p>
          </div>
        </div>

        <div data-animate="mcp-connection" className="grid gap-3 md:grid-cols-12">
          <div data-motion-item={0} data-motion-loop className="relative overflow-hidden rounded-2xl border border-outline-variant/60 bg-surface-lowest p-6 md:col-span-7 md:p-8">
            <div className="mcp-signal-orbit absolute -right-24 -top-24 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />
            <div className="relative">
              <div className="mb-8 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-on-surface text-surface-lowest">
                    <Braces className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold font-display">Momentum MCP</p>
                    <p className="text-xs text-on-surface-muted">Streamable HTTP · stateless</p>
                  </div>
                </div>
                <span className="flex items-center gap-1.5 rounded-full bg-success-container px-2.5 py-1 text-xs font-medium text-on-success-container">
                  <Radio className="h-3 w-3" /> Public
                </span>
              </div>

              <div className="rounded-xl border border-outline-variant/60 bg-surface-low p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.15em] text-on-surface-muted">
                  Endpoint MCP
                </p>
                <code className="block break-all font-mono text-sm text-on-surface">https://mcp.deepcopy.fr</code>
                <div className="mt-5 flex flex-col gap-2 border-t border-outline-variant/60 pt-4 sm:flex-row sm:items-center sm:justify-between">
                  <span className="font-mono text-xs text-on-surface-muted">MCP-Protocol-Version: 2026-07-28</span>
                  <CopyEndpointButton value="https://mcp.deepcopy.fr" />
                </div>
              </div>

              <Link
                href="/docs#mcp-tools"
                className="mt-6 inline-flex min-h-11 items-center justify-center rounded-full bg-on-surface px-4 text-xs font-medium text-surface-lowest transition hover:bg-on-surface/80"
              >
                Lire la documentation
                <ArrowUpRight className="ml-1.5 h-3.5 w-3.5" aria-hidden="true" />
              </Link>
            </div>
          </div>

          <div data-motion-item={1} className="rounded-2xl border border-outline-variant/60 bg-surface-low p-6 md:col-span-5 md:p-8">
            <h3 className="mb-5 font-display text-lg font-semibold tracking-[-0.02em]">
              Parmi les sept outils publics
            </h3>
            <div className="space-y-2">
              {MCP_TOOLS.map((tool) => (
                <div key={tool} className="flex items-center gap-3 rounded-xl bg-surface-lowest px-4 py-3">
                  <Check className="h-4 w-4 shrink-0 text-success" />
                  <code className="font-mono text-xs text-on-surface">{tool}</code>
                </div>
              ))}
            </div>
            <p className="mt-6 text-xs leading-relaxed text-on-surface-variant">
              Les autres outils donnent accès aux dernières analyses et permettent de proposer un
              ticker pour modération.
            </p>
          </div>
        </div>

        <div data-animate="mcp-use-cases" className="mt-4 grid gap-3 border-t border-outline-variant/60 pt-10 md:grid-cols-3">
          <div data-motion-item={0} className="rounded-2xl bg-surface-low p-6">
            <h3 className="mb-2 font-display text-lg font-semibold tracking-[-0.02em]">
              Un standard, pas une nouvelle interface.
            </h3>
            <p className="text-xs leading-relaxed text-on-surface-variant">
              Votre agent garde son interface habituelle et vient chercher le contexte Momentum au
              moment où il en a besoin.
            </p>
          </div>

          <div data-motion-item={1} className="rounded-2xl bg-surface-low p-6">
            <h3 className="mb-2 font-display text-lg font-semibold tracking-[-0.02em]">
              Du signal brut à la décision.
            </h3>
            <p className="text-xs leading-relaxed text-on-surface-variant">
              Le scanner décrit le régime de marché. Le MCP permet à votre agent de le confronter à
              une analyse d&apos;actif ou à une recommandation précise.
            </p>
          </div>

          <div data-motion-item={2} className="rounded-2xl bg-surface-low p-6">
            <h3 className="mb-2 font-display text-lg font-semibold tracking-[-0.02em]">
              Recherche, synthèse, workflow.
            </h3>
            <p className="text-xs leading-relaxed text-on-surface-variant">
              Branchez le serveur à un assistant, un notebook ou un workflow maison pour produire
              des réponses plus contextualisées et reproductibles.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
