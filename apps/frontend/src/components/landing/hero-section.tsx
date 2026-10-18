import { PublicActions } from "./public-actions"

export function HeroSection() {
  return (
    <section className="relative overflow-x-clip pt-28 pb-16 md:pt-40 md:pb-24 lg:pt-44 lg:pb-28">
      <div
        data-motion-loop
        className="hero-signal-field pointer-events-none absolute -top-40 left-1/2 h-[600px] w-[900px] -translate-x-1/2 rounded-[50%]"
      />

      <div className="relative mx-auto grid max-w-6xl items-end gap-14 px-6 lg:grid-cols-12 lg:gap-12">
        <div className="lg:col-span-7">
          <h1 data-animate="hero-title" className="max-w-3xl text-balance text-5xl font-bold leading-[1.04] tracking-[-0.04em] font-display sm:text-6xl md:text-7xl md:leading-[1.02]">
            <span className="block text-balance">Understand the markets.</span>
            <span className="block text-balance font-medium text-on-surface-muted">Explore AI agents.</span>
          </h1>
        </div>

        <div className="lg:col-span-5 lg:pb-1">
          <p data-animate="hero-copy" data-delay="80" className="max-w-prose text-base leading-relaxed text-on-surface-variant md:text-lg">
            Deep Copy is my AI project for financial markets. Read a public market report, then explore the engineering choices behind it.
          </p>

          <div data-animate="hero-form" data-delay="160" className="mt-7 max-w-xl">
            <PublicActions />
          </div>
        </div>
      </div>
    </section>
  )
}
