"use client"

import { useTransition } from "react"
import { useRouter } from "next/navigation"

export function RetryButton() {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  return (
    <button type="button" disabled={pending} onClick={() => startTransition(() => router.refresh())} className="mt-5 inline-flex min-h-11 items-center underline underline-offset-4 disabled:opacity-60">
      {pending ? "Chargement…" : "Réessayer"}
    </button>
  )
}
