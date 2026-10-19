"use client"

import { useState } from "react"
import Image from "next/image"
import { Pause, Play } from "lucide-react"

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
  const [paused, setPaused] = useState(false)

  return (
    <section id="partners" aria-labelledby="ecosystem-title" className="scroll-mt-20 border-t border-outline-variant py-12 md:py-16">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-9 flex flex-wrap items-center justify-between gap-3">
          <h2 id="ecosystem-title" className="font-display text-xl font-semibold tracking-[-0.02em] text-on-surface-variant">
            The technologies behind the ecosystem
          </h2>
          <button type="button" onClick={() => setPaused(value => !value)} className="hidden min-h-11 items-center gap-2 rounded-full px-3 text-xs text-on-surface-variant transition-colors hover:bg-surface-low sm:inline-flex motion-reduce:hidden">
            {paused ? <Play className="h-3.5 w-3.5" aria-hidden="true" /> : <Pause className="h-3.5 w-3.5" aria-hidden="true" />}
            {paused ? "Resume animation" : "Pause animation"}
          </button>
        </div>
        <div className="flex flex-col gap-10">
          {[ROW1, ROW2].map((row, rowIndex) => (
            <div key={rowIndex} className="ecosystem-rail overflow-hidden">
              <div data-motion-loop className={`ecosystem-track flex w-max items-center ${rowIndex === 0 ? "animate-marquee" : "animate-marquee-reverse"}`} style={{ animationPlayState: paused ? "paused" : "running" }}>
                {[false, true].map(isCopy => (
                  <ul key={String(isCopy)} aria-hidden={isCopy} aria-label={rowIndex === 0 ? "Ecosystem platforms" : "Development technologies"} className={`ecosystem-group flex items-center gap-12 pr-12 md:gap-20 md:pr-20 ${isCopy ? "ecosystem-copy" : ""}`}>
                    {row.map(technology => (
                      <li key={technology.name} className="flex w-32 shrink-0 flex-col items-center gap-3 text-center">
                        <div className="flex h-12 items-center justify-center">
                          <Image src={technology.logo} alt="" width={technology.height * 5} height={technology.height} className={`max-w-full w-auto ${technology.className}`} />
                        </div>
                        <span className="text-xs leading-relaxed text-on-surface-muted">{technology.name}</span>
                      </li>
                    ))}
                  </ul>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
