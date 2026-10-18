export function DisclaimerSection() {
  const disclaimers = [
    "Deep Copy is not a broker.",
    "Deep Copy does not hold your funds.",
    "Investing involves the risk of losing capital.",
    "Past or simulated performance does not predict future results.",
  ]

  return (
    <section id="disclaimer" className="scroll-mt-20 border-t border-outline-variant py-10 md:py-12">
      <div className="max-w-6xl mx-auto px-6">
        <h2 className="text-xl font-semibold font-display mb-5">
          Keep in mind
        </h2>
        <ul className="grid gap-x-8 gap-y-3 md:grid-cols-2">
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
