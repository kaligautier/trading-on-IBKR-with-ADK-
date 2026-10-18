export const HORIZONS = ["1d", "1w", "1m", "3m", "6m", "ytd", "1y", "5y"] as const
export type Horizon = typeof HORIZONS[number]
export const HORIZON_LABELS = { "1d": "1 j", "1w": "1 sem", "1m": "1 mois", "3m": "3 mois", "6m": "6 mois", ytd: "Année", "1y": "1 an", "5y": "5 ans" }

function invalid(): never { throw new Error("Invalid report-v3 response") }
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return invalid()
  return value as Record<string, unknown>
}
function text(value: unknown): string {
  if (typeof value !== "string") return invalid()
  return value
}
function number(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return invalid()
  return value
}
function count(value: unknown): number {
  const result = number(value)
  return Number.isSafeInteger(result) && result >= 0 ? result : invalid()
}
function list<T>(value: unknown, parse: (item: unknown) => T): T[] {
  if (!Array.isArray(value)) return invalid()
  return value.map(parse)
}
function nullable<T>(value: unknown, parse: (item: unknown) => T): T | null {
  return value === null || value === undefined ? null : parse(value)
}
function choice<const T extends readonly string[]>(value: unknown, options: T): T[number] {
  const result = text(value)
  return options.includes(result) ? result : invalid()
}
function date(value: unknown): string {
  const result = text(value)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(result)) return invalid()
  const parsed = new Date(`${result}T00:00:00Z`)
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === result ? result : invalid()
}
function decimal(value: unknown): string | number {
  if (typeof value === "number") return number(value)
  const result = text(value)
  return /^-?\d+(\.\d+)?$/.test(result) ? result : invalid()
}
export function safeSourceUrl(value: unknown): string | null {
  if (typeof value !== "string") return null
  try {
    const url = new URL(value)
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null
  } catch { return null }
}
export function formatValue(value: number | string): string {
  if (typeof value === "number") return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: Math.abs(value) < 10 ? 4 : 2 }).format(value)
  const [integer, fraction] = value.split(".")
  const formatted = integer === "-0" ? "-0" : new Intl.NumberFormat("fr-FR").format(BigInt(integer))
  return fraction ? `${formatted},${fraction}` : formatted
}
function interpretation(value: unknown) {
  const item = object(value)
  const status = choice(item.status, ["documented", "hypothesis", "unestablished"])
  const source_ids = list(item.source_ids, text)
  if (status === "documented" && source_ids.length === 0) return invalid()
  return { text: text(item.text), status, source_ids }
}
function horizon(value: unknown) {
  const item = object(value)
  return { change_pct: number(item.change_pct), ref_price: decimal(item.ref_price), trend: choice(item.trend, ["rising", "falling", "stable"]) }
}
function asset(value: unknown) {
  const item = object(value)
  const rawHorizons = object(item.horizons)
  const horizons = Object.fromEntries(HORIZONS.map(key => [key, nullable(rawHorizons[key], horizon)])) as Record<Horizon, ReturnType<typeof horizon> | null>
  const percentile = nullable(item.percentile_3y, number)
  if (percentile !== null && (percentile < 0 || percentile > 1)) return invalid()
  return {
    asset_key: text(item.asset_key), name: text(item.name), symbol: text(item.symbol),
    value: decimal(item.value), unit: nullable(item.unit, text),
    observed_on: nullable(item.observed_on, date), horizons, percentile_3y: percentile,
    observation: text(item.observation), interpretation: interpretation(item.interpretation),
  }
}
function quality(value: unknown) {
  const item = object(value)
  return {
    name: text(item.name), source: text(item.source), source_url: safeSourceUrl(item.source_url),
    observed_on: nullable(item.observed_on, date), reason: nullable(item.reason, text),
    status: choice(item.status, ["available", "stale", "unavailable"]),
  }
}
function source(value: unknown) {
  const item = object(value)
  return { id: text(item.id), title: text(item.title), url: safeSourceUrl(item.url) }
}
function theme(value: unknown) {
  const item = object(value)
  return { family: text(item.family), observation: text(item.observation), interpretation: interpretation(item.interpretation) }
}
function macro(value: unknown) {
  const item = object(value)
  return {
    context: text(item.context), data_gaps: list(item.data_gaps, text),
    themes: list(item.themes, value => {
      const item = object(value)
      return {
        title: text(item.title), status: choice(item.status, ["hypothesis", "unestablished"]),
        observation: text(item.observation), development: text(item.development),
        transmission: text(item.transmission), counter_evidence: text(item.counter_evidence),
        uncertainty: text(item.uncertainty),
      }
    }),
  }
}
function report(value: unknown) {
  const item = object(value)
  if (item.schema_version !== 3) return invalid()
  const scope = object(item.scope)
  const assets = list(item.assets, asset)
  if (new Set(assets.map(asset => asset.asset_key)).size !== assets.length) return invalid()
  const sources = list(item.sources, source)
  const themes = list(item.themes, theme)
  const sourceIds = new Set(sources.map(source => source.id))
  for (const insight of [...assets, ...themes]) {
    if (insight.interpretation.source_ids.some(id => !sourceIds.has(id))) return invalid()
  }
  return {
    schema_version: 3 as const, title: text(item.title), summary: text(item.summary),
    regime: choice(item.regime, ["risk-on", "cautious", "risk-off"]),
    horizon: choice(item.horizon, [...HORIZONS, "level"]), assets, themes, sources,
    limitations: list(item.limitations, text), watch_points: item.watch_points === undefined ? [] : list(item.watch_points, text),
    macro_overview: nullable(item.macro_overview, macro),
    scope: {
      available: count(scope.available), requested: count(scope.requested),
      observation_dates: list(scope.observation_dates, date),
      stale: list(scope.stale, text), unavailable: list(scope.unavailable, text),
    },
    data_quality: Object.fromEntries(Object.entries(object(item.data_quality)).map(([key, value]) => [key, quality(value)])),
  }
}
export function parseScan(value: unknown) {
  const item = object(value)
  const id = text(item.id)
  if (!/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(id)) return invalid()
  const created_at = text(item.created_at)
  if (!Number.isFinite(Date.parse(created_at))) return invalid()
  return { id, scan_date: date(item.scan_date), created_at, report: report(item.report) }
}
export type MarketScan = ReturnType<typeof parseScan>
export type MarketAsset = MarketScan["report"]["assets"][number]
