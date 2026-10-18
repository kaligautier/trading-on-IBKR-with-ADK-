"use client"

import { useState } from "react"
import { Check, Copy } from "lucide-react"

type CopyState = "idle" | "copied" | "error"

const COPY_LABELS: Record<CopyState, string> = {
  idle: "Copy endpoint",
  copied: "Endpoint copied",
  error: "Copy failed — try again",
}

export function CopyEndpointButton({ value, label = "Copy endpoint", inverted = false }: { value: string; label?: string; inverted?: boolean }) {
  const [state, setState] = useState<CopyState>("idle")

  async function copyEndpoint() {
    try {
      await navigator.clipboard.writeText(value)
      setState("copied")
    } catch {
      setState("error")
    }
  }

  const Icon = state === "copied" ? Check : Copy

  return (
    <button
      type="button"
      onClick={copyEndpoint}
      className={`inline-flex min-h-11 items-center gap-2 rounded-lg px-2 text-xs font-semibold transition-colors ${inverted ? "text-slate-300 hover:text-white" : "text-on-surface-variant hover:text-on-surface"}`}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      <span role="status">{state === "idle" ? label : COPY_LABELS[state]}</span>
    </button>
  )
}
