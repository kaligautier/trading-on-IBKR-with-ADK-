"use client"

// Adapted from the beui.dev chromatic text reveal supplied for this project.
import { motion, useInView, useReducedMotion, type MotionStyle, type UseInViewOptions } from "motion/react"
import { useCallback, useEffect, useRef, useState } from "react"
import styles from "./chromatic-text-reveal.module.css"

const CHROMATIC_PALETTE = ["#60a5fa", "#818cf8", "#c084fc", "#fb7185", "#fbbf24"]
const TRAIL_HALF_WIDTH = 14
const REVEAL_START = `-${TRAIL_HALF_WIDTH}%`
const REVEAL_FINISH = `${100 + TRAIL_HALF_WIDTH}%`
const EASE_IN_OUT = [0.65, 0, 0.35, 1] as const
const EASE_OUT = [0.16, 1, 0.3, 1] as const

export type ChromaticTextRevealProps = {
  prefix: string
  words: string[]
  colors?: string[]
  foregroundColor?: string
  duration?: number
  delay?: number
  pauseDuration?: number
  loop?: boolean
  startOnView?: boolean
  once?: boolean
  inViewMargin?: UseInViewOptions["margin"]
  className?: string
}

function composeChromaticGradient(colors: string[], foregroundColor: string) {
  const palette = colors.length > 0 ? colors : CHROMATIC_PALETTE
  const colorStops = palette.map((color, index) => {
    const offset = palette.length === 1 ? 0 : -TRAIL_HALF_WIDTH + (index / (palette.length - 1)) * TRAIL_HALF_WIDTH * 2
    return `${color} calc(var(--chromatic-sweep) ${offset < 0 ? "-" : "+"} ${Number(Math.abs(offset).toFixed(2))}%)`
  })
  return `linear-gradient(90deg, ${foregroundColor} 0%, ${foregroundColor} calc(var(--chromatic-sweep) - ${TRAIL_HALF_WIDTH}%), ${colorStops.join(", ")}, transparent calc(var(--chromatic-sweep) + ${TRAIL_HALF_WIDTH}%), transparent 100%)`
}

export function ChromaticTextReveal({
  prefix,
  words,
  colors = CHROMATIC_PALETTE,
  foregroundColor = "var(--color-on-surface)",
  duration = 1.6,
  delay = 0,
  pauseDuration = 0.8,
  loop = true,
  startOnView = true,
  once = false,
  inViewMargin,
  className,
}: ChromaticTextRevealProps) {
  const ref = useRef<HTMLSpanElement>(null)
  const timerRef = useRef<number | null>(null)
  const [wordIndex, setWordIndex] = useState(0)
  const reduceMotion = useReducedMotion()
  const isInView = useInView(ref, { once, margin: inViewMargin, amount: 0.4 })
  const shouldReveal = !startOnView || isInView || reduceMotion
  const activeIndex = words.length ? wordIndex % words.length : 0
  const activeWord = words[activeIndex] ?? ""

  const clearPendingWord = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const scheduleNextWord = useCallback(() => {
    clearPendingWord()
    if (reduceMotion || !shouldReveal || words.length < 2 || (activeIndex === words.length - 1 && !loop)) return
    timerRef.current = window.setTimeout(() => {
      setWordIndex((index) => (index + 1) % words.length)
    }, pauseDuration * 1000)
  }, [activeIndex, clearPendingWord, loop, pauseDuration, reduceMotion, shouldReveal, words.length])

  // Cancel a pending rotation when preferences, visibility or the word list change.
  useEffect(() => clearPendingWord, [clearPendingWord, reduceMotion, shouldReveal, words, loop])

  return (
    <span ref={ref} className={`${styles.root}${className ? ` ${className}` : ""}`}>
      {prefix ? <span>{prefix}{words.length ? " " : null}</span> : null}
      {words.length ? (
        <span className={styles.words}>
          {Array.from(new Set(words)).map((word) => (
            <span key={word} aria-hidden className={styles.sizing}>{word}</span>
          ))}
          <motion.span
            key={`${activeWord}-${activeIndex}`}
            aria-hidden
            initial={reduceMotion ? false : { opacity: 0.56, filter: "blur(6px)", transform: "translateY(5px)" }}
            animate={{
              "--chromatic-sweep": shouldReveal ? REVEAL_FINISH : REVEAL_START,
              opacity: 1,
              filter: "blur(0px)",
              transform: "translateY(0px)",
            }}
            transition={{
              "--chromatic-sweep": reduceMotion || !shouldReveal ? { duration: 0 } : { duration, delay, ease: EASE_IN_OUT },
              opacity: { duration: reduceMotion ? 0 : 0.28, ease: EASE_OUT },
              filter: { duration: reduceMotion ? 0 : 0.36, ease: EASE_OUT },
              transform: { duration: reduceMotion ? 0 : 0.36, ease: EASE_OUT },
            }}
            onAnimationComplete={scheduleNextWord}
            className={styles.reveal}
            style={{
              "--chromatic-sweep": reduceMotion ? REVEAL_FINISH : REVEAL_START,
              "--chromatic-gradient": composeChromaticGradient(colors, foregroundColor),
              "--chromatic-foreground": foregroundColor,
            } as MotionStyle}
          >
            {activeWord}
          </motion.span>
          <span className="sr-only">{activeWord}</span>
        </span>
      ) : null}
    </span>
  )
}
