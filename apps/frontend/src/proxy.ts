import { NextRequest, NextResponse } from "next/server"

export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64")
  const development = process.env.NODE_ENV === "development"
  const policy = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${development ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'", // React motion styles and Next development styles.
    `connect-src 'self'${development ? " ws:" : ""}`,
    "img-src 'self' data:", "font-src 'self'", "object-src 'none'",
    "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'",
  ].join("; ")
  const headers = new Headers(request.headers)
  headers.set("x-nonce", nonce)
  headers.set("Content-Security-Policy", policy)
  const response = NextResponse.next({ request: { headers } })
  response.headers.set("Content-Security-Policy", policy)
  return response
}

export const config = { matcher: ["/", "/docs/:path*"] }
