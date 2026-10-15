import { parseScan } from "./report.ts"

type ReaderConfig = { baseUrl: string; useIam: boolean; production: boolean }
const IDENTITY_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"

function readerOrigin(config: ReaderConfig): string {
  const url = new URL(config.baseUrl)
  const local = url.protocol === "http:" && ["127.0.0.1", "localhost"].includes(url.hostname)
  const cloudRun = url.protocol === "https:" && url.hostname.endsWith(".run.app") && !url.port
  if (url.username || url.password || url.pathname !== "/" || url.search || url.hash) throw new Error("reader_configuration_invalid")
  if (config.production && !config.useIam) throw new Error("reader_configuration_invalid")
  if (config.useIam ? !cloudRun : config.production || !local) throw new Error("reader_configuration_invalid")
  return url.origin
}

export class LatestScanReader {
  private readonly origin: string
  private readonly useIam: boolean
  private readonly fetcher: typeof fetch

  constructor(config: ReaderConfig, fetcher: typeof fetch = fetch) {
    this.origin = readerOrigin(config)
    this.useIam = config.useIam
    this.fetcher = fetcher
  }

  async latest() {
    const headers = new Headers({ Accept: "application/json" })
    if (this.useIam) headers.set("X-Serverless-Authorization", `Bearer ${await this.identityToken()}`)
    const response = await this.fetcher(`${this.origin}/market-scans/latest`, {
      headers, cache: "no-store", redirect: "error", signal: AbortSignal.timeout(20_000),
    })
    if (response.status === 404) return null
    if (!response.ok) throw new Error("reader_response_failed")
    return parseScan(await response.json())
  }

  private async identityToken(): Promise<string> {
    const url = new URL(IDENTITY_URL)
    url.searchParams.set("audience", this.origin)
    url.searchParams.set("format", "full")
    const response = await this.fetcher(url, {
      headers: { "Metadata-Flavor": "Google" }, cache: "no-store",
      redirect: "error", signal: AbortSignal.timeout(3_000),
    })
    if (!response.ok) throw new Error("reader_identity_failed")
    const token = (await response.text()).trim()
    if (!token || /\s/.test(token)) throw new Error("reader_identity_failed")
    return token
  }
}
