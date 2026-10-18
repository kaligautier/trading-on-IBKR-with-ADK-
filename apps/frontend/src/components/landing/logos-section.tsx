import Image from "next/image"

const ROW1 = [
  { name: "Interactive Brokers", logo: "/logos/ibkr.svg", height: 24, className: "h-7" },
  { name: "Google", logo: "/logos/google.svg", height: 28, className: "h-6" },
  { name: "Anthropic", logo: "/logos/anthropic.svg", height: 22, className: "h-7" },
  { name: "OpenAI", logo: "/logos/openai.svg", height: 26, className: "h-8" },
  { name: "Scaleway", logo: "/logos/scaleway.svg", height: 24, className: "h-8" },
  { name: "Amazon", logo: "/logos/amazon.svg", height: 24, className: "h-5" },
]

const ROW2 = [
  { name: "Python", logo: "/logos/python.svg", height: 24, className: "h-8" },
  { name: "Next.js", logo: "/logos/nextjs.svg", height: 24, className: "h-8" },
  { name: "Docker", logo: "/logos/docker.svg", height: 24, className: "h-8" },
  { name: "PostgreSQL", logo: "/logos/postgresql.svg", height: 24, className: "h-8" },
  { name: "Redis", logo: "/logos/redis.svg", height: 22, className: "h-8" },
  { name: "Google ADK", logo: "/logos/google-adk.png", height: 28, className: "h-12" },
]

export function LogosSection() {
  return (
    <section id="partners" className="scroll-mt-20 border-t border-outline-variant py-16 md:py-20">
      <div className="max-w-6xl mx-auto px-6">
        <h2
          data-animate="section-heading"
          className="mb-12 text-center font-display text-xl font-semibold tracking-[-0.02em] text-on-surface-variant"
        >
          The technologies behind the ecosystem
        </h2>
        <div data-animate="logo-rails" className="flex flex-col gap-8">
          <div data-motion-item={0} className="relative overflow-hidden">
            <div data-motion-loop className="flex w-max animate-marquee items-center">
              {[ROW1, ROW1].map((set, setIndex) => {
                const isDecorativeCopy = setIndex === 1

                return (
                  <div
                    key={setIndex}
                    aria-hidden={isDecorativeCopy}
                    className="flex items-center gap-20 pr-20 md:gap-32 md:pr-32"
                  >
                    {set.map((partner, i) => (
                      <Image
                        key={i}
                        src={partner.logo}
                        alt={isDecorativeCopy ? "" : partner.name}
                        width={partner.height * 5}
                        height={partner.height}
                        className={`w-auto opacity-50 hover:opacity-80 transition-opacity ${partner.className}`}
                      />
                    ))}
                  </div>
                )
              })}
            </div>
          </div>
          <div data-motion-item={1} className="relative overflow-hidden">
            <div data-motion-loop className="flex w-max animate-marquee-reverse items-center">
              {[ROW2, ROW2].map((set, setIndex) => {
                const isDecorativeCopy = setIndex === 1

                return (
                  <div
                    key={setIndex}
                    aria-hidden={isDecorativeCopy}
                    className="flex items-center gap-20 pr-20 md:gap-32 md:pr-32"
                  >
                    {set.map((partner, i) => (
                      <Image
                        key={i}
                        src={partner.logo}
                        alt={isDecorativeCopy ? "" : partner.name}
                        width={partner.height * 5}
                        height={partner.height}
                        className={`w-auto opacity-50 hover:opacity-80 transition-opacity ${partner.className}`}
                      />
                    ))}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
