import { MotionDelay } from "./motion-delay"

const ENTRANCE_SELECTOR = "[data-animate]"
const LOOP_SELECTOR = "[data-motion-loop]"

export class BrowserMotionRuntime {
  constructor(private readonly browserWindow: Window) {}

  prefersReducedMotion(): boolean {
    return this.browserWindow.matchMedia("(prefers-reduced-motion: reduce)").matches
  }

  supportsObservers(): boolean {
    return typeof IntersectionObserver !== "undefined" && typeof MutationObserver !== "undefined"
  }

  createIntersectionObserver(
    callback: IntersectionObserverCallback,
    options: IntersectionObserverInit,
  ): IntersectionObserver {
    return new IntersectionObserver(callback, options)
  }

  createMutationObserver(callback: MutationCallback): MutationObserver {
    return new MutationObserver(callback)
  }
}

export class LandingMotionController {
  private readonly observedEntrances = new WeakSet<Element>()
  private readonly observedLoops = new WeakSet<Element>()
  private readonly visibleLoops = new Set<HTMLElement>()
  private entranceObserver: IntersectionObserver | null = null
  private loopObserver: IntersectionObserver | null = null
  private mutationObserver: MutationObserver | null = null

  constructor(
    private readonly document: Document,
    private readonly runtime: BrowserMotionRuntime,
  ) {}

  start(): void {
    if (this.prefersReducedMotion()) return
    if (!this.supportsObservers()) return

    this.entranceObserver = this.createEntranceObserver()
    this.loopObserver = this.createLoopObserver()
    this.mutationObserver = this.createMutationObserver()
    this.document.documentElement.classList.add("motion-ready")
    this.document.addEventListener("visibilitychange", this.syncVisibleLoops)
    this.observeNewElements()
    this.mutationObserver.observe(this.document.body, { childList: true, subtree: true })
  }

  stop(): void {
    this.entranceObserver?.disconnect()
    this.loopObserver?.disconnect()
    this.mutationObserver?.disconnect()
    this.document.removeEventListener("visibilitychange", this.syncVisibleLoops)
    this.document.documentElement.classList.remove("motion-ready")
    this.visibleLoops.forEach((element) => element.classList.remove("motion-loop-active"))
    this.visibleLoops.clear()
  }

  private prefersReducedMotion(): boolean {
    return this.runtime.prefersReducedMotion()
  }

  private supportsObservers(): boolean {
    return this.runtime.supportsObservers()
  }

  private createEntranceObserver(): IntersectionObserver {
    return this.runtime.createIntersectionObserver(this.revealEntrances, {
      threshold: 0.12,
      rootMargin: "0px 0px -8% 0px",
    })
  }

  private createLoopObserver(): IntersectionObserver {
    return this.runtime.createIntersectionObserver(this.updateVisibleLoops, { threshold: 0.05 })
  }

  private createMutationObserver(): MutationObserver {
    return this.runtime.createMutationObserver(this.observeNewElements)
  }

  private readonly revealEntrances = (entries: IntersectionObserverEntry[]): void => {
    entries.filter((entry) => entry.isIntersecting).forEach((entry) => this.reveal(entry.target))
  }

  private reveal(target: Element): void {
    const element = target as HTMLElement
    const delay = MotionDelay.from(element.dataset.delay)

    element.style.setProperty("--motion-delay", delay.toCssValue())
    element.classList.add("in-view")
    this.entranceObserver?.unobserve(element)
  }

  private readonly updateVisibleLoops = (entries: IntersectionObserverEntry[]): void => {
    entries.forEach((entry) => this.updateVisibleLoop(entry))
    this.syncVisibleLoops()
  }

  private updateVisibleLoop(entry: IntersectionObserverEntry): void {
    const element = entry.target as HTMLElement

    if (entry.isIntersecting) this.visibleLoops.add(element)
    if (!entry.isIntersecting) this.visibleLoops.delete(element)
  }

  private readonly syncVisibleLoops = (): void => {
    this.queryElements(LOOP_SELECTOR).forEach((element) => {
      const shouldRun = !this.document.hidden && this.visibleLoops.has(element)
      element.classList.toggle("motion-loop-active", shouldRun)
    })
  }

  private readonly observeNewElements = (): void => {
    this.observeEntrances()
    this.observeLoops()
  }

  private observeEntrances(): void {
    this.queryElements(ENTRANCE_SELECTOR).forEach((element) => {
      if (this.observedEntrances.has(element)) return
      this.observedEntrances.add(element)
      this.entranceObserver?.observe(element)
    })
  }

  private observeLoops(): void {
    this.queryElements(LOOP_SELECTOR).forEach((element) => {
      if (this.observedLoops.has(element)) return
      this.observedLoops.add(element)
      this.loopObserver?.observe(element)
    })
  }

  private queryElements(selector: string): HTMLElement[] {
    return Array.from(this.document.querySelectorAll<HTMLElement>(selector))
  }
}
