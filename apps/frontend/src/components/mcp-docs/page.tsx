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
    desc: "Lire le rapport quotidien sans compte.", subs: [],
  },
  {
    id: "mcp-tools",
    number: "02",
    title: "MCP Tools",
    desc: "Branche n'importe quel LLM aux analyses de marché via le Model Context Protocol.",
    subs: [
      { id: "quickstart", number: "2.1", title: "Quickstart" },
      { id: "protocol-2026", number: "2.2", title: "Protocole 2026-07-28" },
      { id: "tool-list_analyses", number: "2.3", title: "list_analyses" },
      { id: "tool-latest_analyses", number: "2.4", title: "latest_analyses" },
      { id: "tool-get_analysis", number: "2.5", title: "get_analysis" },
      { id: "tool-get_recommendations", number: "2.6", title: "get_recommendations" },
      { id: "tool-latest_market_scan", number: "2.7", title: "latest_market_scan" },
      { id: "tool-suggest_ticker", number: "2.8", title: "suggest_ticker" },
      { id: "tool-get_suggestion_status", number: "2.9", title: "get_suggestion_status" },
      { id: "moderation", number: "2.10", title: "Modération" },
    ],
  },
  {
    id: "connecter",
    number: "03",
    title: "Connecter un agent",
    desc: "Accède aux analyses publiques avec ton agent.",
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
    <section className="pb-10" aria-label="Choisir une documentation">
      <p className="mb-4 text-xs font-medium uppercase tracking-[0.15em] text-on-surface-muted">
        Deux produits, deux usages
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <a
          href="#mcp-tools"
          className="group rounded-2xl border border-on-surface/10 bg-surface-low p-6 transition hover:border-on-surface/25 hover:bg-surface-high"
        >
          <span className="text-[10px] font-medium uppercase tracking-[0.15em] text-on-surface-muted">
            MCP public
          </span>
          <h2 className="mt-3 font-display text-xl font-semibold text-on-surface">
            Voir la documentation MCP
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
            Un service indépendant pour connecter n&apos;importe quel agent aux analyses Momentum publiques.
          </p>
          <span className="mt-5 inline-block text-xs font-medium text-on-surface underline underline-offset-4">
            Consulter les outils →
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
            Consulter le Market Scanner
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
            Le rapport quotidien, ses observations, ses horizons et ses limites, sans connexion.
          </p>
          <span className="mt-5 inline-block text-xs font-medium text-on-surface underline underline-offset-4">
            Comprendre le rapport →
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
        Le rapport quotidien est consultable sans compte depuis la page d’accueil.
        Sa date de publication et les dates d’observation permettent de distinguer
        une analyse récente de données de marché plus anciennes.
      </p>
      <p className="text-on-surface-variant mb-6 leading-relaxed">
        Les huit horizons vont d’un jour à cinq ans, avec une mesure depuis le
        début de l’année. Une valeur manquante reste indisponible. Les limites,
        sources et hypothèses accompagnent les observations ; le régime de marché
        ne constitue ni une probabilité de gain ni une recommandation d’investissement.
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
        Le serveur Momentum expose publiquement les analyses et accepte les suggestions de tickers.
        Il est accessible sans clé API via l&apos;endpoint HTTP suivant :
      </p>

      <CodeBlock
        title="URL du serveur MCP public"
        language="text"
        code={`https://mcp.deepcopy.fr`}
      />

      <p className="text-on-surface-variant mb-6 max-w-2xl leading-relaxed">
        Dans un client compatible MCP <InlineCode>2026-07-28</InlineCode>, renseigne simplement cette URL.
        Le client g&egrave;re ensuite la d&eacute;couverte du serveur et les en-t&ecirc;tes de transport.
      </p>

      <CodeBlock
        title="claude_desktop_config.json (client compatible)"
        language="json"
        code={`{
  "mcpServers": {
    "deep-copy": {
      "url": "https://mcp.deepcopy.fr"
    }
  }
}`}
      />

      <SectionTitle id="protocol-2026">Protocole MCP 2026-07-28</SectionTitle>
      <p className="text-on-surface-variant mb-6 max-w-2xl leading-relaxed">
        Le serveur utilise le protocole MCP moderne en <strong className="text-on-surface">Streamable HTTP stateless</strong>.
        Chaque appel est un <InlineCode>POST</InlineCode> ind&eacute;pendant : il n&apos;y a plus de handshake
        <InlineCode>initialize</InlineCode>, de session <InlineCode>Mcp-Session-Id</InlineCode> ou de requ&ecirc;te
        <InlineCode>notifications/initialized</InlineCode>. Les informations du client et la version sont
        envoy&eacute;es dans <InlineCode>params._meta</InlineCode> &agrave; chaque requ&ecirc;te.
      </p>

      <CodeBlock
        title="Découvrir les capacités du serveur"
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
        "io.modelcontextprotocol/clientInfo": {"name": "mon-client", "version": "1.0.0"},
        "io.modelcontextprotocol/clientCapabilities": {}
      }
    }
  }'`}
      />

      <p className="text-on-surface-variant mb-6 max-w-2xl leading-relaxed">
        Pour un appel <InlineCode>tools/call</InlineCode>, le client reprend ces m&eacute;tadonn&eacute;es et ajoute
        <InlineCode>Mcp-Name</InlineCode> avec le nom de l&apos;outil. Les valeurs des en-t&ecirc;tes doivent correspondre
        au contenu JSON-RPC ; le serveur rejette les requ&ecirc;tes incoh&eacute;rentes.
      </p>

      <CodeBlock
        title="Appeler list_analyses"
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
        "io.modelcontextprotocol/clientInfo": {"name": "mon-client", "version": "1.0.0"},
        "io.modelcontextprotocol/clientCapabilities": {}
      }
    }
  }'`}
      />

      <p className="text-xs text-on-surface-muted mb-8 max-w-2xl">
        R&eacute;f&eacute;rence : <a className="underline hover:text-on-surface" href="https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http" target="_blank" rel="noopener noreferrer">sp&eacute;cification Streamable HTTP MCP 2026-07-28</a>.
      </p>

      <SectionTitle>MCP Tools</SectionTitle>

      <p className="mb-6 max-w-2xl text-sm text-on-surface-variant">
        List tools return their arrays in <InlineCode>result.structuredContent.result</InlineCode>. Pass an item&apos;s <InlineCode>id</InlineCode> as <InlineCode>analysis_id</InlineCode> to <InlineCode>get_analysis</InlineCode>.
      </p>

      <div className="mt-6">
        <ToolDoc
          id="tool-list_analyses"
          name="list_analyses"
          description="Liste paginée des analyses avec filtre par ticker. Retourne un résumé : rating, prix, RSI, tendance, PE ratio."
          params={[
            { name: "ticker", type: "str | None", default: "None", description: "Filtre par symbole (ex: AAPL)" },
            { name: "limit", type: "int", default: "50", description: "Nombre de résultats (max 200)" },
            { name: "offset", type: "int", default: "0", description: "Décalage pour pagination" },
          ]}
          responseFields={["id", "analysis_date", "ticker", "rating", "executive_summary", "price_target", "entry_price", "stop_loss", "rsi", "rsi_signal", "trend_direction", "key_support", "key_resistance", "pe_ratio", "peg_ratio", "beta"]}
        />
        <ToolDoc
          id="tool-latest_analyses"
          name="latest_analyses"
          description="Dernière analyse par ticker. Filtre optionnel par portfolio rating."
          params={[
            { name: "ticker", type: "str | None", default: "None", description: "Un seul ticker" },
            { name: "rating", type: "str | None", default: "None", description: "Comma-separated: Buy,Overweight,Hold,Underweight,Sell" },
          ]}
          responseFields={["id", "ticker", "rating", "executive_summary", "price_target", "trader_action", "rsi", "trend_direction"]}
        />
        <ToolDoc
          id="tool-get_analysis"
          name="get_analysis"
          description="Détail complet : indicateurs techniques, fondamentaux, sentiment, news, débats bull/bear, décision portfolio."
          params={[
            { name: "analysis_id", type: "str (UUID)", default: "required", description: "Identifiant de l'analyse" },
          ]}
          responseFields={["technical_indicators", "fundamentals", "sentiment", "news", "research_plan", "trader_proposal", "portfolio_decision", "debate_arguments", "run_stats"]}
        />
        <ToolDoc
          id="tool-get_recommendations"
          name="get_recommendations"
          description="Recommandations actives filtrées par rating. Idéal pour « quoi acheter ? »."
          params={[
            { name: "rating", type: "str", default: '"Buy,Overweight"', description: "Ratings cibles" },
            { name: "limit", type: "int", default: "10", description: "Max résultats (max 100)" },
          ]}
          responseFields={["id", "ticker", "rating", "price_target", "entry_price", "stop_loss", "position_size", "risk_reward_ratio"]}
        />
        <ToolDoc
          id="tool-latest_market_scan"
          name="latest_market_scan"
          description="Returns the latest daily market regime and normalized asset signals. No parameters: send an empty arguments object ({})."
          params={[]}
          responseFields={["id", "scan_date", "created_at", "regime", "summary", "recommendation", "assets", "signals", "session_id"]}
        />
        <ToolDoc
          id="tool-suggest_ticker"
          name="suggest_ticker"
          description="Propose un ticker à analyser. Une analyse ou suggestion existante est retournée sans nouvelle écriture ; sinon une suggestion unique est créée pour modération."
          params={[
            { name: "symbol", type: "str", default: "required", description: "Symbole boursier (ex: ASML)" },
            { name: "reason", type: "str", default: '""', description: "Why this ticker deserves analysis (maximum 500 characters)" },
          ]}
          responseFields={["id", "symbol", "reason", "source", "status", "review_reason", "created_at", "reviewed_at"]}
        />
        <ToolDoc
          id="tool-get_suggestion_status"
          name="get_suggestion_status"
          description="Consulte la décision de modération associée à une suggestion."
          params={[
            { name: "suggestion_id", type: "str (UUID)", default: "required", description: "Identifiant retourné par suggest_ticker" },
          ]}
          responseFields={["id", "symbol", "status", "created_at", "reviewed_at", "review_reason"]}
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
        Une suggestion, pas un ordre d&apos;analyse
      </h3>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-on-surface-variant">
        Un ticker inconnu est sauvegardé une seule fois avec le statut <InlineCode>pending</InlineCode>.
        Si une analyse ou une proposition existe déjà, elle est renvoyée sans écriture.
        L&apos;administrateur peut ensuite approuver ou rejeter une nouvelle proposition.
      </p>
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <WorkflowStep number="1" title="Proposition" detail="Le LLM appelle suggest_ticker." />
        <WorkflowStep number="2" title="Modération" detail="L’administrateur vérifie la demande." />
        <WorkflowStep number="3" title="Analyse" detail="Un job est créé après approbation." />
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
          Connectez votre LLM aux march&eacute;s
        </h2>
        <p className="text-on-surface-variant mb-6 max-w-md mx-auto">
          Le MCP Momentum est public et sans clé API.
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
            Confidentialit&eacute;
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
          <CopyEndpointButton value={code} label="Copier le code" inverted />
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
          Paramètres
        </div>
        <dl className="mt-1 divide-y divide-on-surface/10">
          {params.map((p) => (
            <div key={p.name} className="py-3.5 first:pt-3">
              <dt className="flex items-baseline gap-2.5 flex-wrap">
                <span className="font-mono text-[13px] font-medium text-on-surface">{p.name}</span>
                <span className="font-mono text-xs text-on-surface-muted">{p.type}</span>
                {p.default === "required" ? (
                  <span className="text-[10px] font-medium uppercase tracking-wide text-amber-600 dark:text-amber-400">
                    requis
                  </span>
                ) : (
                  <span className="text-xs text-on-surface-muted">
                    défaut <span className="font-mono text-on-surface-variant">{p.default}</span>
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
          Réponse
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
