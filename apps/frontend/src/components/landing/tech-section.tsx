export function TechSection() {
  return (
    <section className="border-t border-outline-variant py-20 md:py-28">
      <div className="max-w-6xl mx-auto px-6">
        <div id="tech" data-animate="section-heading" className="grid md:grid-cols-12 gap-8 mb-12 scroll-mt-20">
          <div className="md:col-span-7">
            <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-[-0.03em] leading-[1.12] md:leading-[1.08] font-display mb-6">
              The architecture connects all three products,
              <br />
              <span className="text-on-surface-muted font-medium">from end to end.</span>
            </h2>
          </div>
        </div>

        <div
          data-animate="architecture-flow"
          className="rounded-2xl border border-outline-variant/60 bg-surface-lowest p-6 md:p-10"
        >
          <div
            data-motion-marker="architecture-signal"
            data-motion-loop
            className="architecture-signal-track"
            aria-hidden="true"
          />
          <div className="relative z-1 flex flex-col gap-5">
            <div data-motion-item={0} className="flex justify-center">
              <ArchBlock label="User" sub="Browser" />
            </div>
            <Arrow />
            <div data-motion-item={1} className="flex justify-center">
              <ArchBlock label="Next.js 16" sub="React 19 · Tailwind 4 · NextAuth" />
            </div>
            <Arrow />
            <div data-motion-item={2} className="flex justify-center">
              <ArchBlock label="FastAPI" sub="Python 3.14 · Astral-sh UV · Pydantic" />
            </div>
            <Arrow />
            <div data-motion-item={3} className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <ArchBlock label="Google ADK" sub="AI agents · Gemini 2.5 Flash" />
              <ArchBlock label="PostgreSQL 16" sub="SQLAlchemy · User data" />
              <ArchBlock label="Redis 7" sub="Market regime cache · Sessions" />
            </div>
            <Arrow />
            <div data-motion-item={4} className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <ArchBlock label="Docker SDK" sub="Provisions 1 isolated container per user" />
              <ArchBlock label="MCP IBKR" sub="MCP server · Interactive Brokers Gateway API" />
            </div>
            <Arrow />
            <div data-motion-item={5} className="flex justify-center">
              <ArchBlock label="Google Cloud Platform" sub="Hosted in Europe · Cloud Run · Cloud SQL · Secret Manager" />
            </div>
            <Arrow />
            <div data-motion-item={6} className="flex justify-center">
              <ArchBlock label="Interactive Brokers" sub="Financial markets" />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function ArchBlock({ label, sub }: { label: string; sub: string }) {
  return (
    <div className="architecture-node rounded-xl border border-outline-variant/60 bg-surface-low px-6 py-4 text-center">
      <div className="text-sm font-semibold font-display">{label}</div>
      <div className="text-xs text-on-surface-variant mt-1">{sub}</div>
    </div>
  )
}

function Arrow() {
  return (
    <div className="flex justify-center">
      <div className="architecture-link w-px h-5 bg-outline-variant/50" />
    </div>
  )
}
