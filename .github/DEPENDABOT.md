# Dependency maintenance

`.github/dependabot.yml` configures weekly version checks on Mondays at 08:00
Europe/Paris. GitHub starts version updates after the configuration reaches the
default branch (`main`). Check actual runs under **Insights → Dependency graph →
Dependabot**; a valid configuration alone does not prove a successful update run.

| Ecosystem | Locations |
| --- | --- |
| uv | `apps/backend/market-scanner-adk`, `apps/backend/market-scanner-api` |
| npm | `apps/frontend` |
| Docker | Both backend Dockerfiles and `database/Dockerfile` |
| Terraform | `infra/market-scanner`, `infra/bootstrap`, `infra/litellm`, `infra/reader` |
| GitHub Actions | `.github/workflows` (configured with directory `/`) |

Each application has its own update entry to respect the one-component-per-PR
policy. uv includes indirect locked dependencies as well as direct dependencies.
Next.js and its ESLint configuration are grouped together; React, React DOM and
their type packages form another group. Major upgrades remain eligible and need
compatibility review. Version PRs are capped at three per entry (33 total);
security PRs have a separate GitHub limit and do not wait for the weekly schedule.

## Security settings

Dependency graph, Dependabot alerts and Dependabot security updates must be
enabled in repository **Settings → Advanced Security**. These repository settings
are separate from the version-update configuration. An administrator can verify
the two Dependabot settings with:

```sh
gh api repos/kaligautier/trading-on-IBKR-with-ADK-/vulnerability-alerts --silent
gh api repos/kaligautier/trading-on-IBKR-with-ADK-/automated-security-fixes
```

The first command succeeds with HTTP 204 when alerts are enabled. The second
must return `"enabled": true` and `"paused": false`. Security-update coverage
depends on GitHub's supported ecosystems and advisory data; retain the existing
`pip-audit`, `npm audit` and container audits in CI.

## Reviewing updates

- Review release notes and compatibility, including the ADK/ddtrace coupling
  documented in the scanner's `pyproject.toml`.
- Require the relevant existing CI checks and review both manifests and lockfiles.
  Keep Actions and Docker references pinned to immutable SHAs/digests.
- Do not grant Dependabot production credentials to make a check pass. The
  existing PR checks run without cloud deployment credentials.
- Merge reviewed updates manually; this setup adds no automatic merging or
  deployment. Investigate failing updater runs in the Dependabot tab.

Dependabot does not maintain arbitrary version literals in scripts, workflow
`with.version` values, or image digests assembled from Terraform variables
(including the LiteLLM and gateway mirrors). Those require separate reviewed
updates and the existing image audits. Provider updates do not deploy Terraform.

References: [configuration options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference),
[supported ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories),
[enabling version updates](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-version-updates).
