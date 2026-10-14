"use client"

import { useEffect } from "react"
import {
  BrowserMotionRuntime,
  LandingMotionController,
} from "@/lib/motion/landing-motion-controller"

export function AnimateObserver() {
  useEffect(() => {
    const runtime = new BrowserMotionRuntime(window)
    const controller = new LandingMotionController(document, runtime)
    controller.start()

    return () => controller.stop()
  }, [])

  return null
}
