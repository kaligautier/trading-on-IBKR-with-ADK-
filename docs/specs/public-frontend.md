# Public Deep Copy frontend

## Outcome

Restore the existing Deep Copy public landing and documentation, preserve its
visual identity, and display the latest report from the scanner consultation API.
Visitors need no account. Host the frontend on public Cloud Run with Terraform.

## Boundaries

- Browser → frontend: public HTTPS, read-only market information.
- Frontend → reader: fixed configured URL; a dedicated service account supplies
  a Google ID token on the server. Tokens never enter browser props or logs.
- Reader → storage: existing read-only service; no changes to the scan job.
- No login, portfolio management, IBKR credential collection, newsletter backend,
  generic API proxy, or ability to trigger an analysis from the public frontend.
- Retain the public Momentum documentation; label it separately from the scanner.
- Keep the source checkout unchanged. Port only active public dependencies.

## Acceptance criteria

1. `/` and `/docs` are accessible anonymously, with working navigation and no
   dependency on an authenticated application.
2. Preserve the paper palette, Inter/Manrope typography, editorial sections and
   responsive behavior of the original public site.
3. Display the reader's report-v3 date, regime, observations, horizons, sources,
   quality indicators and limitations without inventing absent probabilities.
4. Distinguish loading, no published report and upstream failure. A reader outage
   must leave the landing and documentation usable. Never present fixtures as live.
5. Render external report text with React escaping; validate the API contract.
6. Network calls have deadlines; the public route cannot select an arbitrary
   upstream or forward browser authorization to the reader.
7. Terraform manages the public service, dedicated identity and scoped invocation
   grant. Reader anonymous access remains denied after deployment.
8. Verify local lint/types/build, boundary tests, responsive keyboard/browser
   behavior and live anonymous access with the persisted report ID and date.
9. Every commit stays below 1,000 changed lines of code and documentation. Only the
   generated npm lockfile is excluded; report its size separately in the PR.
10. Put the report conclusion and concise public arbitration before the detailed
    observations. Keep figures/assets and family/macro analysis collapsed initially,
    with native keyboard-accessible disclosures. Keep source caveats visible.
11. Require arbitration for newly generated reports; accept absent or null
    arbitration in historical reports without fabricating a justification.

## Applicable BEST_PRATICE.todo

| Requirement | Application and evidence |
| --- | --- |
| SOLID / Object Calisthenics | Focused parsing, transport and rendering responsibilities; small functions/classes where useful, no speculative abstraction. |
| Useful clean architecture | UI depends on a report contract; server transport owns IAM and network details. |
| just commands | Repeatable install, dev, lint, typecheck, test, build and infrastructure checks. |
| Small commits | Keep each dependency-ordered commit below 1,000 authored changed lines; report generated lockfile size separately. |
| Official documentation | Next.js bundled version documentation, Google Cloud Run and Terraform provider documentation. |
| Scientific papers | No new trading method or agent algorithm in this change; not applicable. |
| Terraform / Cloud Run | Dedicated frontend Terraform root and reproducible container deployment. |
| Secret Manager | No static frontend credential: workload identity obtains reader ID tokens. Any future secret must use Secret Manager. |
| Gateway / ADK / Agent Engine / Model Armor / Promptfoo | Agent execution is outside this frontend change; preserve the existing scanner boundary. |
| Cloud Run jobs / cron | Existing scan scheduling remains outside this change. |

## Delivery and operations

The current review consolidates the application foundation, landing sections and
motion, public documentation, reader contract/transport, scanner rendering and
public arbitration in the existing PR #12 at the maintainer's request. Use
dependency-ordered commits below the size limit. Cloud Run delivery remains a
separate follow-up; local checks do not prove deployment or live model quality.
Every slice states what it validates and what remains pending.
Deploy the exact tested image digest; document its source commit, URL, readiness,
anonymous frontend response and denied anonymous reader response. Roll back by
restoring the previous frontend digest through Terraform.
