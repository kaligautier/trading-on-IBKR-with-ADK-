import { PublicActions } from "./public-actions"

export function CtaSection() {
  return (
    <section className="border-t border-outline-variant py-24 md:py-32">
      <div data-animate="cta-focus" className="cta-focus max-w-2xl mx-auto px-6 text-center">
        <div
          data-motion-marker="cta-signal"
          data-motion-loop
          className="cta-signal"
          aria-hidden="true"
        />
        <div className="relative z-1">
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-[-0.03em] leading-[1.12] md:leading-[1.08] mb-6 font-display">
            A first look at the market.
          </h2>
          <p className="text-on-surface-variant mb-10 max-w-md mx-auto text-sm leading-relaxed">
            Read the Market Scanner report for free. Explore the engineering choices behind the project to understand how it is produced.
          </p>
          <div className="flex justify-center">
            <PublicActions />
          </div>
        </div>
      </div>
    </section>
  )
}
