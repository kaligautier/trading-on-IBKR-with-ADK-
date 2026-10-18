import { readFileSync } from "node:fs"
import assert from "node:assert/strict"
import { test } from "node:test"
import { parseScan, safeSourceUrl, formatValue } from "./report.ts"

function fixture() {
  return {
    id: "455a9557-4f0e-4e25-b235-444abb866b95",
    scan_date: "2026-10-12", created_at: "2026-10-12T05:05:13Z",
    report: JSON.parse(readFileSync("../backend/market-scanner-adk/examples/report-v3.json", "utf8")).market_regime,
  }
}

test("accepts the producer's published report-v3 example", () => {
  const input = fixture()
  const scan = parseScan(input)
  assert.equal(scan.report.assets.length, input.report.assets.length)
  assert.equal(scan.report.summary, input.report.summary)
})

test("defaults omitted watch points but rejects an explicit null", () => {
  const input = fixture()
  delete input.report.watch_points
  assert.deepEqual(parseScan(input).report.watch_points, [])
  input.report.watch_points = null
  assert.throws(() => parseScan(input), /Invalid report/)
})

test("preserves exact decimal values and missing horizons", () => {
  const input = fixture()
  input.report.assets[0].value = "40310000000000.123456"
  input.report.assets[0].horizons["5y"] = null
  const asset = parseScan(input).report.assets[0]
  assert.equal(asset.value, "40310000000000.123456")
  assert.equal(asset.horizons["5y"], null)
  assert.equal(formatValue(asset.value).replaceAll("\u202f", " "), "40 310 000 000 000,123456")
})

test("rejects incompatible versions and invalid nested data", () => {
  const input = fixture()
  input.report.schema_version = 2
  assert.throws(() => parseScan(input), /Invalid report/)
  input.report.schema_version = 3
  input.report.assets[0].value = "not a number"
  assert.throws(() => parseScan(input), /Invalid report/)
})

test("never converts malformed availability or non-finite changes into a report", () => {
  const input = fixture()
  input.report.scope.available = "25"
  assert.throws(() => parseScan(input), /Invalid report/)
  const other = fixture()
  other.report.assets[0].horizons["1d"] = { change_pct: Infinity, trend: "rising" }
  assert.throws(() => parseScan(other), /Invalid report/)
})

test("only exposes HTTP(S) source links without credentials", () => {
  assert.equal(safeSourceUrl("javascript:alert(1)"), null)
  assert.equal(safeSourceUrl("https://user:password@example.com"), null)
  assert.equal(safeSourceUrl("https://example.com/report"), "https://example.com/report")
})

test("preserves the sign of exact decimals between minus one and zero", () => {
  assert.equal(formatValue("-0.25"), "-0,25")
})

test("retains provenance and failure reasons for assets excluded from the snapshot", () => {
  const input = fixture()
  input.report.scope.unavailable = ["missing_asset"]
  input.report.data_quality.missing_asset = {
    name: "Missing index", source: "Test provider", source_url: "https://example.com/data",
    observed_on: null, reason: "Provider timeout", status: "unavailable",
  }
  const report = parseScan(input).report
  assert.equal(report.assets.some(asset => asset.asset_key === "missing_asset"), false)
  assert.deepEqual(report.data_quality.missing_asset, input.report.data_quality.missing_asset)
})
