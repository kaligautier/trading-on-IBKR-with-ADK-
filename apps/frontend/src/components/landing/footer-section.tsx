import Link from "next/link"

const FOOTER_LINK_CLASS = "inline-flex min-h-11 min-w-11 items-center transition-colors hover:text-on-surface"

export function FooterSection() {
  return (
    <footer className="py-10 border-t border-outline-variant">
      <div className="max-w-6xl mx-auto px-6">
        <div className="flex flex-col items-start justify-between gap-7 md:flex-row md:items-center">
          <div className="max-w-xs">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-on-surface text-xs font-bold text-surface-lowest">
                DC
              </div>
              <span className="text-sm font-semibold">Deep Copy</span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-on-surface-muted">An AI project for financial markets.</p>
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-3 text-xs text-on-surface-muted">
            <a href="#market-scanner" className={FOOTER_LINK_CLASS}>Market Scanner</a>
            <a href="#momentum-mcp" className={FOOTER_LINK_CLASS}>Momentum</a>
            <a href="#deep-copy" className={FOOTER_LINK_CLASS}>Experimental trading</a>
            <a href="#engineering" className={FOOTER_LINK_CLASS}>Engineering</a>
            <Link href="/docs" className={FOOTER_LINK_CLASS}>Documentation</Link>
            <Link href="https://deepcopy.fr/legal/privacy" className={FOOTER_LINK_CLASS}>
              Privacy
            </Link>
            <span>© 2026 Deep Copy</span>
          </div>
        </div>
      </div>
    </footer>
  )
}
