import Link from "next/link"
import { ArrowUpRight, ChevronDown } from "lucide-react"
import { CopyEndpointButton } from "./copy-endpoint-button"

const MCP_TOOLS = ["list_analyses", "get_analysis", "get_recommendations", "latest_market_scan"]
const USE_CASES = [
  { title: "Find a stock analysis", detail: "Read an available report and the arguments behind its recommendation." },
  { title: "Read recommendations", detail: "Reuse published results in your assistant or workflow." },
  { title: "Add market context", detail: "Read the latest Market Scanner report through the same endpoint." },
]

export function McpSection() {
  return (
    <section id="momentum-mcp" aria-labelledby="momentum-mcp-title" className="scroll-mt-20 border-t border-outline-variant py-16 md:py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div data-animate="section-heading" className="mb-10 grid gap-6 md:grid-cols-12 md:gap-12">
          <h2 id="momentum-mcp-title" className="text-balance font-display text-4xl font-bold leading-tight tracking-tight md:col-span-7 md:text-5xl">
            Momentum.
            <br />
            <span className="font-medium text-on-surface-muted">Company analysis in your assistant.</span>
          </h2>
          <p className="max-w-prose self-end text-base leading-relaxed text-on-surface-variant md:col-span-5">
            Momentum explores a company in depth and explains the arguments behind its recommendation. MCP lets your assistant access published reports and use them in your conversations.
          </p>
        </div>

        <div className="grid items-start gap-8 lg:grid-cols-12 lg:gap-16">
          <div className="min-w-0 lg:col-span-6">
            <h3 className="font-display text-lg font-semibold">What your assistant can read</h3>
            <dl className="mt-5 divide-y divide-outline-variant border-y border-outline-variant">
              {USE_CASES.map(useCase => (
                <div key={useCase.title} className="py-5">
                  <dt className="text-sm font-semibold">{useCase.title}</dt>
                  <dd className="mt-1 text-sm leading-relaxed text-on-surface-variant">{useCase.detail}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="min-w-0 rounded-2xl border border-outline-variant bg-surface-lowest p-6 lg:col-span-6 md:p-8">
            <h3 className="font-display text-lg font-semibold">Connect your assistant</h3>
            <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
              Access is public, with no API key. Add this address to the MCP connections in your compatible assistant.
            </p>
            <code className="mt-5 block break-all rounded-lg bg-surface-low p-4 font-mono text-sm">https://mcp.deepcopy.fr</code>
            <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2">
              <CopyEndpointButton value="https://mcp.deepcopy.fr" />
              <Link href="/docs#connecter" prefetch={false} className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold underline decoration-outline-control underline-offset-4 transition-colors hover:text-primary-dim">
                Read the connection guide <ArrowUpRight className="h-4 w-4 shrink-0" aria-hidden="true" />
              </Link>
            </div>
            <details className="group mt-5 border-t border-outline-variant pt-2">
              <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 text-sm font-semibold hover:text-primary-dim [&::-webkit-details-marker]:hidden">
                Some available tools
                <ChevronDown className="h-4 w-4 shrink-0 transition-transform group-open:rotate-180 motion-reduce:transition-none" aria-hidden="true" />
              </summary>
              <ul className="mt-2 space-y-2 text-sm text-on-surface-variant">
                {MCP_TOOLS.map(tool => <li key={tool}><code className="break-all font-mono text-xs">{tool}</code></li>)}
              </ul>
              <p className="mt-4 text-xs leading-relaxed text-on-surface-variant">
                Ticker suggestions are moderated and do not automatically start an analysis.
              </p>
              <Link href="/docs#mcp-tools" prefetch={false} className="mt-2 inline-flex min-h-11 items-center gap-2 text-sm underline decoration-outline-control underline-offset-4 hover:text-primary-dim">
                Explore all tools <ArrowUpRight className="h-4 w-4 shrink-0" aria-hidden="true" />
              </Link>
            </details>
          </div>
        </div>
      </div>
    </section>
  )
}
