export function DisclaimerSection() {
  const disclaimers = [
    "Deep Copy n'est pas un courtier.",
    "Deep Copy ne détient pas vos fonds.",
    "Les ordres sont transmis via votre compte Interactive Brokers.",
    "Les décisions automatisées ne sont activées que selon les paramètres validés par l'utilisateur.",
    "Investir comporte un risque de perte en capital.",
    "Les performances passées ou simulées ne préjugent pas des performances futures.",
  ]

  return (
    <section id="disclaimer" className="scroll-mt-20 border-t border-outline-variant py-16 md:py-20">
      <div className="max-w-6xl mx-auto px-6">
        <h2 data-animate="section-heading" className="text-2xl md:text-3xl font-bold tracking-[-0.02em] font-display mb-8">
          Avertissements et cadre juridique
        </h2>
        <ul data-animate="disclaimer-list" className="space-y-3 max-w-2xl">
          {disclaimers.map((text, index) => (
            <li data-motion-item={index} key={text} className="flex items-start gap-3 text-on-surface-variant text-sm">
              <span className="mt-2 block h-1 w-1 rounded-full bg-outline-variant shrink-0" />
              {text}
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
