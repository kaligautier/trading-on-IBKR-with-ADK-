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
            Commencez par le bon usage.
            <br />
            <span className="text-on-surface-muted font-medium">Observer. Connecter. Orchestrer.</span>
          </h2>
          <p className="text-on-surface-variant mb-10 max-w-md mx-auto text-sm leading-relaxed">
            Le Market Scanner est libre d&apos;accès. Momentum MCP connecte ces analyses à vos outils.
            Deep Copy vous permet ensuite de tester vos stratégies sur un compte IBKR paper.
          </p>
          <div className="flex justify-center">
            <PublicActions />
          </div>
        </div>
      </div>
    </section>
  )
}
