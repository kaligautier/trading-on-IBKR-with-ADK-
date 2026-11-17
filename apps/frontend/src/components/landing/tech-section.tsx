import { ChromaticTextReveal } from "@/components/motion/chromatic-text-reveal"

const STACK = [
  { name: "Application", tools: "Next.js · React · TypeScript · Tailwind CSS", detail: "The public site and its reading experience." },
  { name: "Agents & data", tools: "Python · Google ADK · FastAPI · Pydantic · SQLAlchemy", detail: "Collect, calculate, analyse and validate before publication." },
  { name: "Storage & inference", tools: "PostgreSQL · LiteLLM · Redis / Valkey", detail: "Persisted reports and a model gateway, with optional shared Redis state." },
  { name: "Delivery", tools: "uv · Docker · Cloud Run · Terraform · Secret Manager", detail: "Locked dependencies, container images and infrastructure as code." },
]

export function TechSection() {
  return (
    <section id="tech" aria-labelledby="tech-title" className="scroll-mt-20 border-t border-outline-variant py-16 md:py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid gap-6 md:grid-cols-12 md:gap-12">
          <h2 id="tech-title" className="font-display text-4xl font-bold leading-[1.12] tracking-[-0.03em] md:col-span-7 md:text-5xl">
            <ChromaticTextReveal prefix="The" words={["technology"]} loop={false} /><br />
            <span className="font-medium text-on-surface-muted">behind Deep Copy.</span>
          </h2>
          <p className="max-w-prose self-end text-sm leading-relaxed text-on-surface-variant md:col-span-5">
            The building blocks of the ecosystem, from the interface to agents, storage and deployment.
          </p>
        </div>
        <dl className="mt-10 divide-y divide-outline-variant border-y border-outline-variant md:mt-12">
          {STACK.map(group => (
            <div key={group.name} className="grid gap-2 py-6 md:grid-cols-12 md:gap-12">
              <dt className="font-display text-sm font-semibold md:col-span-3">{group.name}</dt>
              <dd className="min-w-0 md:col-span-9">
                <p className="text-sm font-medium leading-relaxed">{group.tools}</p>
                <p className="mt-1 text-sm leading-relaxed text-on-surface-muted">{group.detail}</p>
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
}
