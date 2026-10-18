import type { Metadata } from "next"
import ApiDocsPage from "@/components/mcp-docs/page"

export const metadata: Metadata = {
  title: "Deep Copy — Momentum MCP documentation",
  description:
    "Connect an MCP 2026-07-28 client to the public Deep Copy Momentum server.",
}

export default function DocsPage() {
  return <ApiDocsPage />
}
