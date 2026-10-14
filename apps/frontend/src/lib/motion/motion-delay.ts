const MAXIMUM_DELAY_MILLISECONDS = 320

export class MotionDelay {
  private constructor(private readonly milliseconds: number) {}

  static from(rawDelay: string | undefined): MotionDelay {
    const parsedDelay = Number.parseInt(rawDelay ?? "0", 10)

    if (!Number.isFinite(parsedDelay)) return new MotionDelay(0)

    const boundedDelay = Math.min(Math.max(parsedDelay, 0), MAXIMUM_DELAY_MILLISECONDS)
    return new MotionDelay(boundedDelay)
  }

  toCssValue(): string {
    return `${this.milliseconds}ms`
  }
}
