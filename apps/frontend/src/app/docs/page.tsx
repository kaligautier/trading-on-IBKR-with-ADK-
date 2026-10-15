import type { Metadata } from "next"
import ApiDocsPage from "@/components/mcp-docs/page"

export const metadata: Metadata = {
  title: "Deep Copy — Documentation MCP Momentum",
  description:
    "Connecter un client MCP 2026-07-28 au serveur public Momentum de Deep Copy.",
}

export default function DocsPage() {
  return <ApiDocsPage />
}
