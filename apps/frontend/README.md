# Public frontend

Next.js landing and public documentation adapted from Deep Copy, with a read-only
report-v3 view. No account, portfolio controls or credential collection.

Requires Node.js 22.18+ and npm 11.19.1. Commands run from this directory:

```sh
just install
just check
just dev
```

`npm ci --ignore-scripts` uses the committed lockfile. Installation scripts stay
disabled in `.npmrc`; native platform packages are supplied by locked optional
dependencies. No dependency install script is needed for the production build.

Production builds use Next.js’s supported Webpack compiler. This avoids a local
Turbopack CSS worker port-binding failure; development retains the default compiler.

## Local reader access

Start an authenticated, loopback-only Cloud Run proxy with an account that already
has permission to invoke the reader:

```sh
gcloud run services proxy market-scanner-api --project=YOUR_PROJECT --region=europe-west1 --port=8099
MARKET_SCANNER_API_URL=http://127.0.0.1:8099 MARKET_SCANNER_API_USE_IAM=false just dev
```

Anonymous upstream access is permitted only in development and only on loopback.
Production requires a Cloud Run HTTPS URL and workload identity. Never place tokens
or reader credentials in `NEXT_PUBLIC_*` variables.

## Runtime boundary

The server calls only `/market-scans/latest` on the configured reader. Google ID
tokens come from the metadata server with that reader as audience. Redirects are
rejected. Metadata and reader deadlines are 3 and 20 seconds respectively.
Concurrent requests share one in-flight fetch per instance; a successful report
is retained for 60 seconds, empty/error states for 5 seconds. Errors remain visible
as unavailable states, never as synthetic reports or empty success responses.

`/health` checks the frontend process independently of the reader. Structured
`reader_fetch` logs contain outcome, duration and report ID, never response bodies
or tokens. Track unavailable outcomes separately from frontend HTTP status: the
landing deliberately stays usable when the reader is unavailable.

## Dependency audit

Next.js is pinned to 16.3.8; compatible fixes update sharp to 0.35.5 and
source-map-js to 1.2.2. Run `npm audit` for the complete graph and
`npm audit --omit=dev --audit-level=high` for the deployable runtime.

The remaining GHSA-vfj7-8cjw-p6xm finding is in `braces` through the Next ESLint
plugin's glob tooling. It processes repository-owned lint patterns, never browser
or reader input, and is not included in the standalone runtime. There is no
compatible upstream fix in the audited graph; downgrading Next's lint configuration
to v14 is not a suitable fix. Reassess on dependency updates; do not suppress
runtime audit findings.

## UI and contract verification

`npm test` consumes the scanner producer's synthetic example only in tests. No
fixture fallback exists in production. Verify `/` and `/docs` at 320/390, 768,
1024 and 1440 pixels; check menu keyboard behavior, disclosure controls, clipboard
failure feedback, console errors, horizontal overflow and reduced motion.

Deployment instructions: [Cloud Run frontend](../../infra/frontend/README.md).
