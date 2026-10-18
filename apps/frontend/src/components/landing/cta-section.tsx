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
            Un premier regard sur le marché.
          </h2>
          <p className="text-on-surface-variant mb-10 max-w-md mx-auto text-sm leading-relaxed">
            Consultez librement le rapport du Market Scanner. Pour comprendre comment il est produit,
            explorez les choix techniques du projet.
          </p>
          <div className="flex justify-center">
            <PublicActions />
          </div>
        </div>
      </div>
    </section>
  )
}
