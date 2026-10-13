import "server-only"
import { LatestScanReader } from "./reader"
import type { MarketScan } from "./report"

export type ScanState =
  | { status: "available"; scan: MarketScan }
  | { status: "empty" | "unavailable" }

let cached: { until: number; result: Promise<ScanState> } | undefined

async function readLatest(): Promise<ScanState> {
  const started = performance.now()
  try {
    const reader = new LatestScanReader({
      baseUrl: process.env.MARKET_SCANNER_API_URL ?? "",
      useIam: process.env.MARKET_SCANNER_API_USE_IAM === "true",
      production: process.env.NODE_ENV === "production",
    })
    const scan = await reader.latest()
    console.info(JSON.stringify({ event: "reader_fetch", outcome: scan ? "available" : "empty", duration_ms: Math.round(performance.now() - started), scan_id: scan?.id }))
    return scan ? { status: "available", scan } : { status: "empty" }
  } catch {
    console.error(JSON.stringify({ event: "reader_fetch", outcome: "unavailable", duration_ms: Math.round(performance.now() - started) }))
    return { status: "unavailable" }
  }
}

export function latestScan(): Promise<ScanState> {
  if (cached && cached.until > Date.now()) return cached.result
  // Share concurrent requests and bound reader load per frontend instance.
  const entry = { until: Number.POSITIVE_INFINITY, result: readLatest() }
  cached = entry
  void entry.result.then(result => { entry.until = Date.now() + (result.status === "available" ? 60_000 : 5_000) })
  return entry.result
}
