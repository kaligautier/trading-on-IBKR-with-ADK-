export function LandingSignal() {
  return (
    <div
      data-motion-marker="scroll-progress"
      className="landing-scroll-signal"
      aria-hidden="true"
    >
      <div className="landing-scroll-signal-progress" />
    </div>
  )
}
