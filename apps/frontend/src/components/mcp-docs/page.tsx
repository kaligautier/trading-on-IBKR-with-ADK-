"use client"

import { useState, useEffect, useRef } from "react"
import { PublicActions } from "@/components/landing/public-actions"
import { CopyEndpointButton } from "@/components/landing/copy-endpoint-button"
import Link from "next/link"

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function ApiDocsPage() {
  return (
    <div className="min-h-screen bg-surface text-on-surface overflow-x-clip">
      <NavBar />
      <div className="max-w-7xl mx-auto px-6 pt-20">
        <div className="grid md:grid-cols-[260px_1fr] gap-12 lg:gap-16 items-start">
          <DocsToc />
          <main className="min-w-0">
            <HeroSection />
            <DocsChoiceSection />
            <ScannerDocs />
            <McpSection />
            <CtaSection />
          </main>
        </div>
      </div>
      <Footer />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Global Table of Contents (Dia-style stepper)                       */
/* ------------------------------------------------------------------ */

type TocSub = { id: string; number: string; title: string }
type TocSection = { id: string; number: string; title: string; desc: string; subs: TocSub[] }

const TOC_SECTIONS: TocSection[] = [
  {
    id: "scanner", number: "01", title: "Market Scanner",
    desc: "Read the daily report without an account.", subs: [],
  },
  {
    id: "mcp-tools",
    number: "02",
    title: "MCP Tools",
    desc: "Connect any LLM to market analysis through the Model Context Protocol.",
    subs: [
      { id: "quickstart", number: "2.1", title: "Quickstart" },
      { id: "protocol-2026", number: "2.2", title: "Protocol 2026-07-28" },
      { id: "tool-list_analyses", number: "2.3", title: "list_analyses" },
      { id: "tool-latest_analyses", number: "2.4", title: "latest_analyses" },
      { id: "tool-get_analysis", number: "2.5", title: "get_analysis" },
      { id: "tool-get_recommendations", number: "2.6", title: "get_recommendations" },
      { id: "tool-suggest_ticker", number: "2.7", title: "suggest_ticker" },
      { id: "tool-get_suggestion_status", number: "2.8", title: "get_suggestion_status" },
      { id: "moderation", number: "2.9", title: "Moderation" },
    ],
  },
  {
    id: "connecter",
    number: "03",
    title: "Connect an agent",
    desc: "Access public analysis with your agent.",
    subs: [],
  },
]

function DocsToc() {
  const [activeId, setActiveId] = useState(TOC_SECTIONS[0].id)
  const observerRef = useRef<IntersectionObserver | null>(null)

  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting)
        if (visible.length > 0) setActiveId(visible[0].target.id)
      },
      { rootMargin: "-30% 0px -60% 0px", threshold: 0 },
    )
    const ids = TOC_SECTIONS.flatMap((s) => [s.id, ...s.subs.map((sub) => sub.id)])
    ids.forEach((id) => {
      const el = document.getElementById(id)
      if (el) observerRef.current?.observe(el)
    })
    return () => observerRef.current?.disconnect()
  }, [])

  return (
    <aside className="hidden md:block md:sticky md:top-24 max-h-[calc(100vh-7rem)] overflow-y-auto pr-2 space-y-5">
      {TOC_SECTIONS.map((section) => (
        <TocSectionItem key={section.id} section={section} activeId={activeId} />
      ))}
    </aside>
  )
}

function TocSectionItem({ section, activeId }: { section: TocSection; activeId: string }) {
  const isSubActive = section.subs.some((sub) => sub.id === activeId)
  const isActive = section.id === activeId || isSubActive

  return (
    <div className="space-y-2">
      <a
        href={`#${section.id}`}
        className={`block pl-4 transition-all duration-200 ${
          isActive
            ? "border-l-2 border-on-surface"
            : "border-l-2 border-transparent opacity-40 hover:opacity-70"
        }`}
      >
        <span className="text-[10px] font-medium text-on-surface-muted mb-1 block">{section.number}</span>
        <span className={`text-sm block ${isActive ? "font-semibold text-on-surface" : "font-medium text-on-surface"}`}>
          {section.title}
        </span>
        {isActive && (
          <span className="text-xs text-on-surface-variant mt-1 block leading-relaxed">{section.desc}</span>
        )}
      </a>

      {section.subs.length > 0 && (
        <div className="ml-4 space-y-1.5">
          {section.subs.map((sub) => {
            const isSubItemActive = sub.id === activeId
            return (
              <a
                key={sub.id}
                href={`#${sub.id}`}
                className={`flex items-baseline gap-2 pl-4 transition-all duration-200 ${
                  isSubItemActive
                    ? "border-l-2 border-on-surface"
                    : "border-l-2 border-transparent opacity-40 hover:opacity-70"
                }`}
              >
                <span className="text-[10px] font-mono text-on-surface-muted shrink-0">{sub.number}</span>
                <span className={`text-xs ${isSubItemActive ? "font-medium text-on-surface" : "text-on-surface-variant"}`}>
                  {sub.title}
                </span>
              </a>
            )
          })}
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Nav                                                               */
/* ------------------------------------------------------------------ */

function NavBar() {
  return (
    <header className="pointer-events-none fixed inset-x-0 top-0 z-50 flex items-center justify-center px-4 pt-4">
      {/* Floating monochrome pill (same style as the app header) */}
      <Link
        href="/"
        className="pointer-events-auto flex items-center gap-2.5 rounded-full border border-outline-variant bg-[#faf9f6]/80 px-3 py-1.5 backdrop-blur-xl shadow-[0_1px_2px_rgba(0,0,0,0.05),0_14px_34px_-16px_rgba(0,0,0,0.25)]"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-on-surface font-bold text-[11px] text-surface-lowest">
          DC
        </span>
        <span className="text-sm font-semibold text-on-surface tracking-tight font-display">
          Deep Copy
        </span>
      </Link>

      {/* Floating right cluster */}
      <div className="pointer-events-auto absolute right-4 flex items-center gap-4">
        <a
          href="https://github.com/kaligautier/trading-on-IBKR-with-ADK-"
          target="_blank"
          rel="noopener noreferrer"
          className="hidden md:flex items-center gap-1.5 text-xs text-on-surface-variant hover:text-on-surface transition"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" /></svg>
          Source
        </a>
        <a
          href="https://deepcopy.fr"
          className="text-xs font-medium text-on-surface-variant hover:text-on-surface transition"
        >
          deepcopy.fr
        </a>
      </div>
    </header>
  )
}

/* ------------------------------------------------------------------ */
/*  Sidebar TOC                                                       */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Hero                                                              */
/* ------------------------------------------------------------------ */

function HeroSection() {
  return (
    <section className="pt-12 pb-16 md:pt-16 md:pb-20">
      <h1 className="text-4xl md:text-5xl font-bold tracking-tight leading-[1.1] mb-6 text-on-surface font-display">
        Documentation
      </h1>

    </section>
  )
}

function DocsChoiceSection() {
  return (
    <section className="pb-10" aria-label="Choose a documentation guide">
      <p className="mb-4 text-xs font-medium uppercase tracking-[0.15em] text-on-surface-muted">
        Two products, two use cases
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <a
          href="#mcp-tools"
          className="group rounded-2xl border border-on-surface/10 bg-surface-low p-6 transition hover:border-on-surface/25 hover:bg-surface-high"
        >
          <span className="text-[10px] font-medium uppercase tracking-[0.15em] text-on-surface-muted">
            Public MCP
          </span>
          <h2 className="mt-3 font-display text-xl font-semibold text-on-surface">
            Read the MCP documentation
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
            An independent service that connects any agent to public Momentum analysis.
          </p>
          <span className="mt-5 inline-block text-xs font-medium text-on-surface underline underline-offset-4">
            Explore the tools →
          </span>
        </a>

        <Link
          href="#scanner"
          className="group rounded-2xl border border-on-surface/10 bg-surface-low p-6 transition hover:border-on-surface/25 hover:bg-surface-high"
        >
          <span className="text-[10px] font-medium uppercase tracking-[0.15em] text-on-surface-muted">
            Market Scanner
          </span>
          <h2 className="mt-3 font-display text-xl font-semibold text-on-surface">
            Read the Market Scanner
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
            The daily report, its observations, horizons and limitations, with no login required.
          </p>
          <span className="mt-5 inline-block text-xs font-medium text-on-surface underline underline-offset-4">
            Understand the report →
          </span>
        </Link>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  MCP Section                                                       */
/* ------------------------------------------------------------------ */

function ScannerDocs() {
  return (
    <section id="scanner" className="py-12 scroll-mt-20">
      <SectionTitle>Market Scanner</SectionTitle>
      <p className="text-on-surface-variant mb-6 leading-relaxed">
        The daily report is available on the homepage without an account. Its publication date and observation dates distinguish a recent analysis from older market data.
      </p>
      <p className="text-on-surface-variant mb-6 leading-relaxed">
        The eight horizons range from one day to five years, including year to date. Missing values remain unavailable. Limitations, sources and hypotheses accompany the observations; the market regime is neither a probability of profit nor an investment recommendation.
      </p>
      <PublicActions />
    </section>
  )
}

function McpSection() {
  return (
    <section id="mcp-tools" className="py-12 scroll-mt-20">
      <SectionTitle id="quickstart">Quickstart</SectionTitle>

      <p className="text-on-surface-variant mb-6 max-w-2xl leading-relaxed">
        The Momentum server provides public analysis and accepts ticker suggestions. It is available without an API key at this HTTP endpoint:
      </p>

      <CodeBlock
        title="Public MCP server URL"
        language="text"
        code={`https://mcp.deepcopy.fr`}
      />

      <p className="text-on-surface-variant mb-6 max-w-2xl leading-relaxed">
        In an MCP-compatible client <InlineCode>2026-07-28</InlineCode>, enter this URL. The client then handles server discovery and transport headers.
      </p>

      <CodeBlock
        title="claude_desktop_config.json (compatible client)"
        language="json"
        code={`{
  "mcpServers": {
    "deep-copy": {
      "url": "https://mcp.deepcopy.fr"
    }
  }
}`}
      />

      <SectionTitle id="protocol-2026">MCP protocol 2026-07-28</SectionTitle>
      <p className="text-on-surface-variant mb-6 max-w-2xl leading-relaxed">
        The server uses the modern MCP protocol over <strong className="text-on-surface">stateless Streamable HTTP</strong>. Each call is an independent <InlineCode>POST</InlineCode> request: there is no{" "}
        <InlineCode>initialize</InlineCode> handshake, <InlineCode>Mcp-Session-Id</InlineCode> session or{" "}
        <InlineCode>notifications/initialized</InlineCode> request. Client information and the protocol version are sent in <InlineCode>params._meta</InlineCode> with every request.
      </p>

      <CodeBlock
        title="Discover server capabilities"
        language="bash"
        code={`curl https://mcp.deepcopy.fr \\
  -H 'Content-Type: application/json' \\
  -H 'Accept: application/json, text/event-stream' \\
  -H 'MCP-Protocol-Version: 2026-07-28' \\
  -H 'Mcp-Method: server/discover' \\
  --data-raw '{
    "jsonrpc": "2.0",
    "id": "discover-1",
    "method": "server/discover",
    "params": {
      "_meta": {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": {"name": "my-client", "version": "1.0.0"},
        "io.modelcontextprotocol/clientCapabilities": {}
      }
    }
  }'`}
      />

      <p className="text-on-surface-variant mb-6 max-w-2xl leading-relaxed">
        For a <InlineCode>tools/call</InlineCode> call, the client reuses this metadata and adds{" "}
        <InlineCode>Mcp-Name</InlineCode> with the tool name. Header values must match the JSON-RPC payload; the server rejects inconsistent requests.
      </p>

      <CodeBlock
        title="Call list_analyses"
        language="bash"
        code={`curl https://mcp.deepcopy.fr \\
  -H 'Content-Type: application/json' \\
  -H 'Accept: application/json, text/event-stream' \\
  -H 'MCP-Protocol-Version: 2026-07-28' \\
  -H 'Mcp-Method: tools/call' \\
  -H 'Mcp-Name: list_analyses' \\
  --data-raw '{
    "jsonrpc": "2.0",
    "id": "list-1",
    "method": "tools/call",
    "params": {
      "name": "list_analyses",
      "arguments": {"ticker": "ASML", "limit": 10, "offset": 0},
      "_meta": {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": {"name": "my-client", "version": "1.0.0"},
        "io.modelcontextprotocol/clientCapabilities": {}
      }
    }
  }'`}
      />

      <p className="text-xs text-on-surface-muted mb-8 max-w-2xl">
        Reference: <a className="underline hover:text-on-surface" href="https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http" target="_blank" rel="noopener noreferrer">MCP 2026-07-28 Streamable HTTP specification</a>.
      </p>

      <SectionTitle>MCP Tools</SectionTitle>

      <div className="mt-6">
        <ToolDoc
          id="tool-list_analyses"
          name="list_analyses"
          description="Paginated analyses with an optional ticker filter. Returns a summary: rating, price, RSI, trend and P/E ratio."
          params={[
            { name: "ticker", type: "str | None", default: "None", description: "Filter by symbol (e.g. AAPL)" },
            { name: "limit", type: "int", default: "50", description: "Number of results (maximum 200)" },
            { name: "offset", type: "int", default: "0", description: "Pagination offset" },
          ]}
          responseFields={["ticker", "rating", "executive_summary", "price_target", "entry_price", "stop_loss", "rsi", "rsi_signal", "trend_direction", "key_support", "key_resistance", "pe_ratio", "peg_ratio", "beta"]}
        />
        <ToolDoc
          id="tool-latest_analyses"
          name="latest_analyses"
          description="Latest analysis for each ticker, with an optional portfolio rating filter."
          params={[
            { name: "ticker", type: "str | None", default: "None", description: "A single ticker" },
            { name: "rating", type: "str | None", default: "None", description: "Comma-separated: Buy,Overweight,Hold,Underweight,Sell" },
          ]}
          responseFields={["ticker", "rating", "executive_summary", "price_target", "trader_action", "rsi", "trend_direction"]}
        />
        <ToolDoc
          id="tool-get_analysis"
          name="get_analysis"
          description="Full report: technical indicators, fundamentals, sentiment, news, bull/bear debates and portfolio decision."
          params={[
            { name: "analysis_id", type: "str (UUID)", default: "required", description: "Analysis identifier" },
          ]}
          responseFields={["technical_indicators", "fundamentals", "sentiment", "news", "research_plan", "trader_proposal", "portfolio_decision", "debate_arguments", "run_stats"]}
        />
        <ToolDoc
          id="tool-get_recommendations"
          name="get_recommendations"
          description="Active recommendations filtered by rating, for queries about potential purchases."
          params={[
            { name: "rating", type: "str", default: '"Buy,Overweight"', description: "Target ratings" },
            { name: "limit", type: "int", default: "10", description: "Number of results (maximum 100)" },
          ]}
          responseFields={["ticker", "rating", "price_target", "entry_price", "stop_loss", "position_size", "risk_reward_ratio"]}
        />
        <ToolDoc
          id="tool-suggest_ticker"
          name="suggest_ticker"
          description="Suggest a ticker for analysis. An existing analysis or suggestion is returned without another write; otherwise, a single suggestion is created for moderation."
          params={[
            { name: "symbol", type: "str", default: "required", description: "Stock symbol (e.g. ASML)" },
            { name: "reason", type: "str | None", default: "None", description: "Why this ticker deserves analysis" },
          ]}
          responseFields={["suggestion_id | analysis_id | job_id", "symbol", "status", "created_at", "created"]}
        />
        <ToolDoc
          id="tool-get_suggestion_status"
          name="get_suggestion_status"
          description="Read the moderation decision for a suggestion."
          params={[
            { name: "suggestion_id", type: "str (UUID)", default: "required", description: "Identifier returned by suggest_ticker" },
          ]}
          responseFields={["suggestion_id", "symbol", "status", "created_at", "reviewed_at", "review_reason"]}
        />
      </div>

      <ModerationWorkflow />
    </section>
  )
}

function ModerationWorkflow() {
  return (
    <section id="moderation" className="scroll-mt-24 border-t border-on-surface/10 py-10">
      <h3 className="font-display text-xl font-semibold text-on-surface">
        A suggestion for review
      </h3>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-on-surface-variant">
        An unknown ticker is saved once with the status <InlineCode>pending</InlineCode>. If an analysis or suggestion already exists, it is returned without another write. An administrator can then approve or reject a new suggestion.
      </p>
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <WorkflowStep number="1" title="Suggestion" detail="The LLM calls suggest_ticker." />
        <WorkflowStep number="2" title="Moderation" detail="An administrator reviews the request." />
        <WorkflowStep number="3" title="Analysis" detail="A job is created after approval." />
      </div>
    </section>
  )
}

function WorkflowStep({
  number,
  title,
  detail,
}: {
  number: string
  title: string
  detail: string
}) {
  return (
    <div className="rounded-xl border border-on-surface/10 bg-surface-low p-4">
      <span className="font-mono text-xs text-on-surface-muted">{number}</span>
      <h4 className="mt-2 text-sm font-semibold text-on-surface">{title}</h4>
      <p className="mt-1 text-xs leading-relaxed text-on-surface-variant">{detail}</p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  CTA                                                               */
/* ------------------------------------------------------------------ */

function CtaSection() {
  return (
    <section id="connecter" className="py-16 scroll-mt-20">
      <div className="rounded-2xl border border-on-surface/5 bg-surface-low p-8 md:p-12 text-center">
        <h2 className="text-2xl md:text-3xl font-bold text-on-surface mb-4 font-display">
          Connect your LLM to market analysis
        </h2>
        <p className="text-on-surface-variant mb-6 max-w-md mx-auto">
          Momentum MCP is public and requires no API key.
        </p>
        <CopyEndpoint />
        <div className="flex justify-center mt-6">
          <PublicActions />
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Footer                                                            */
/* ------------------------------------------------------------------ */

function Footer() {
  return (
    <footer className="py-10 border-t border-on-surface/5 bg-surface-low">
      <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-5 h-5 rounded bg-on-surface flex items-center justify-center font-bold text-[8px] text-surface-lowest">
            DC
          </div>
          <span className="text-xs text-on-surface-muted">Deep Copy API Documentation</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-on-surface-muted">
          <a href="https://deepcopy.fr" className="hover:text-on-surface transition">
            deepcopy.fr
          </a>
          <a href="https://deepcopy.fr/legal/privacy" className="hover:text-on-surface transition">
            Privacy
          </a>
          <span>&copy; 2026 Deep Copy</span>
        </div>
      </div>
    </footer>
  )
}

/* ================================================================== */
/*  Shared Components                                                 */
/* ================================================================== */

function SectionTitle({ id, children }: { id?: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="text-2xl md:text-3xl font-bold text-on-surface mb-4 scroll-mt-20 font-display">
      {children}
    </h2>
  )
}

function InlineCode({ children }: { children: React.ReactNode }) {
  return (
    <code className="font-mono text-sm text-primary bg-surface-low px-1.5 py-0.5 rounded">
      {children}
    </code>
  )
}

/* ── Code Block ────────────────────────────────────────────────────── */

function CodeBlock({ title, language, code }: { title: string; language: string; code: string }) {
  return (
    <div className="rounded-xl border border-on-surface/10 overflow-hidden my-6">
      <div className="flex items-center justify-between px-4 py-2 bg-[#1e1e2e] border-b border-white/5">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/60" />
            <div className="w-2.5 h-2.5 rounded-full bg-green-500/60" />
          </div>
          <span className="text-[11px] font-mono text-slate-400">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-slate-500 uppercase">{language}</span>
          <CopyEndpointButton value={code} label="Copy code" inverted />
        </div>
      </div>
      <pre className="p-4 overflow-x-auto text-[13px] leading-relaxed font-mono text-slate-300 bg-[#1e1e2e]">
        {code}
      </pre>
    </div>
  )
}

function CopyEndpoint() {
  return <CopyEndpointButton value="https://mcp.deepcopy.fr" />
}

/* ── Tool Documentation ────────────────────────────────────────────── */

function ToolDoc({
  id,
  name,
  description,
  params,
  responseFields,
}: {
  id: string
  name: string
  description: string
  params: { name: string; type: string; default: string; description: string }[]
  responseFields: string[]
}) {
  return (
    <section id={id} className="scroll-mt-24 grid md:grid-cols-[210px_1fr] gap-x-12 gap-y-4 border-t border-on-surface/10 py-10">
      <div>
        <h3 className="font-mono text-[15px] font-semibold text-on-surface">{name}</h3>
        <p className="mt-2 text-sm text-on-surface-variant leading-relaxed">{description}</p>
      </div>

      <div className="min-w-0">
        <div className="text-[11px] font-medium uppercase tracking-wider text-on-surface-muted">
          Parameters
        </div>
        <dl className="mt-1 divide-y divide-on-surface/10">
          {params.map((p) => (
            <div key={p.name} className="py-3.5 first:pt-3">
              <dt className="flex items-baseline gap-2.5 flex-wrap">
                <span className="font-mono text-[13px] font-medium text-on-surface">{p.name}</span>
                <span className="font-mono text-xs text-on-surface-muted">{p.type}</span>
                {p.default === "required" ? (
                  <span className="text-[10px] font-medium uppercase tracking-wide text-amber-600 dark:text-amber-400">
                    required
                  </span>
                ) : (
                  <span className="text-xs text-on-surface-muted">
                    default <span className="font-mono text-on-surface-variant">{p.default}</span>
                  </span>
                )}
              </dt>
              <dd className="mt-1 text-[13px] text-on-surface-variant leading-relaxed">
                {p.description}
              </dd>
            </div>
          ))}
        </dl>

        <div className="mt-7 text-[11px] font-medium uppercase tracking-wider text-on-surface-muted">
          Response
        </div>
        <div className="mt-2.5 flex flex-wrap gap-x-5 gap-y-2">
          {responseFields.map((f) => (
            <span key={f} className="font-mono text-[12.5px] text-on-surface-variant">
              {f}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
