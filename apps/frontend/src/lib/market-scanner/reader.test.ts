import { readFileSync } from "node:fs"
import assert from "node:assert/strict"
import { test } from "node:test"
import { LatestScanReader } from "./reader.ts"

const config = { baseUrl: "https://reader-example.run.app", useIam: true, production: true }
const scan = {
  id: "455a9557-4f0e-4e25-b235-444abb866b95", scan_date: "2026-10-12",
  created_at: "2026-10-12T05:05:13Z",
  report: JSON.parse(readFileSync("../backend/market-scanner-adk/examples/report-v3.json", "utf8")).market_regime,
}

test("uses an audience-bound metadata token only for the fixed reader endpoint", async () => {
  const requests: { url: string; options?: RequestInit }[] = []
  const fetcher: typeof fetch = async (url, options) => {
    requests.push({ url: String(url), options })
    return requests.length === 1 ? new Response("identity-token") : Response.json(scan)
  }
  const result = await new LatestScanReader(config, fetcher).latest()
  assert.equal(result?.id, scan.id)
  assert.equal(new URL(requests[0].url).searchParams.get("audience"), config.baseUrl)
  assert.equal(new Headers(requests[0].options?.headers).get("Metadata-Flavor"), "Google")
  assert.equal(requests[1].url, `${config.baseUrl}/market-scans/latest`)
  assert.equal(new Headers(requests[1].options?.headers).get("X-Serverless-Authorization"), "Bearer identity-token")
  assert.equal(requests[1].options?.redirect, "error")
  assert.ok(requests.every(request => request.options?.signal instanceof AbortSignal))
})

test("metadata failure never falls back to anonymous reader access", async () => {
  let calls = 0
  const fetcher: typeof fetch = async () => { calls++; return new Response("secret upstream error", { status: 403 }) }
  await assert.rejects(new LatestScanReader(config, fetcher).latest(), /^Error: reader_identity_failed$/)
  assert.equal(calls, 1)
})

test("only HTTP 404 means no published report; failures and bad JSON stay errors", async () => {
  const local = { baseUrl: "http://127.0.0.1:8099", useIam: false, production: false }
  assert.equal(await new LatestScanReader(local, async () => new Response(null, { status: 404 })).latest(), null)
  for (const response of [new Response("forbidden", { status: 403 }), new Response("bad json")]) {
    await assert.rejects(new LatestScanReader(local, async () => response).latest())
  }
})

test("rejects credential-bearing, arbitrary and unauthenticated production upstreams", () => {
  for (const baseUrl of ["https://example.com", "https://user:secret@reader-example.run.app", "http://metadata.google.internal", "https://reader-example.run.app/arbitrary"]) {
    assert.throws(() => new LatestScanReader({ ...config, baseUrl }), /reader_configuration_invalid/)
  }
  assert.throws(() => new LatestScanReader({ ...config, useIam: false }), /reader_configuration_invalid/)
})
