# LiteLLM image dependency review

## 1.106.2 upgrade candidate

Both defaults in `variables.tf` now select the official
[1.106.2 release](https://github.com/BerriAI/litellm/releases/tag/v1.106.2),
listed by GitHub as the latest stable release on 2026-10-21 at 21:10 UTC.
At that check the previously considered 1.107.0 release page returned 404 and
its proxy tag was unavailable. The 1.106.2 release includes spend accounting,
batch pricing and token-counting fixes.

Budget exhaustion now defaults to HTTP 422 with error type `budget_exceeded`.
The container checks assert that response for per-agent and global budgets;
shared RPM exhaustion must still return HTTP 429. Clients should distinguish
an exhausted budget from a transient rate limit.

The upgrade tracked in
[issue #53](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/issues/53)
remains blocked by the image-security gate. The proposed pins are not a deployed
upgrade and must not be released until the remaining advisories are resolved.

Both GHCR image indexes were verified on 2026-10-21 and contain `linux/amd64`
and `linux/arm64` manifests:

```text
ghcr.io/berriai/litellm@sha256:7294b90f868c5c38c99b83021c7ba46f9b439e95f8e32964c925c7d2563a03f7
ghcr.io/berriai/litellm-migrations@sha256:bdcb8d71f3cc6344beeb7280b8865cfebfbe218426dd12f079ee4ea99dc10563
```

Installed package metadata extracted from both exact `linux/amd64` images with
`--network=none` confirms `litellm 1.106.2`, `aiohttp 3.14.5`, `yarl 1.25.1`, and
`certifi 2026.4.22`. The full `audit_images.py` run with `pip-audit==2.10.1`
exited 1. No aiohttp advisory was reported.

| Image, linux/amd64 | Installed distributions | Known advisories | Skipped packages |
| --- | ---: | ---: | ---: |
| Proxy 1.106.2 | 200 | 6 | 1 |
| Migrations 1.106.2 | 145 | 1 | 0 |

Remaining findings:

- Both images: `certifi 2026.4.22`, `PYSEC-2026-4320`
  (`GHSA-6q48-6c7w-9gw2`), fixed in `2026.10.19`.
- Proxy only: `pypdf 6.19.0`, `CVE-2026-113792`, `CVE-2026-113795`,
  `CVE-2026-113793`, `CVE-2026-113794`, and `CVE-2026-113786`.
  The reported fixes span 6.20.0 through 6.21.1; 6.21.1 addresses all five.
- The auditor skipped `litellm-admin-mcp 0.1.0` because it could not find the
  package on PyPI. This limits coverage; it is not a clean bill of health.

The arm64 images have not been audited for this candidate. No exceptions or
dependency replacements are applied inside the official images. Resolve the
remaining findings through official upstream images, update both digests
together, and rerun the audit and `LiteLLM checks` before marking the PR ready.
Investigate skipped packages before claiming complete Python package coverage.

Local configuration validation passed: 32 infrastructure tests, 4 governance
policy tests, 28 Python regression tests, and Ruff. The gateway route-isolation
and SSE smoke test also passed. See
[PR #99](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/99)
for the final container test and CI results. Provider responses in the native
gateway tests are simulated; they do not establish live Vertex connectivity.

No Cloud Run rollout or live Vertex inference is claimed. Before a deployed
upgrade, back up PostgreSQL, review the Terraform plan, execute migrations, and
verify gateway behavior after rollout.

## Historical 1.103.4 decision and evidence

The PR initially pinned LiteLLM 1.103.1. An audit of its installed proxy Python
packages found 31 advisories across seven packages. Upgrade both official images
to 1.103.4 rather than retain affected versions with advisory exceptions.
The [1.103.3 release](https://github.com/BerriAI/litellm/releases/tag/v1.103.3)
includes dependency updates and a stricter migration check. The
[1.103.4 release](https://github.com/BerriAI/litellm/releases/tag/v1.103.4)
includes further dependency updates in
[upstream PR #44776](https://github.com/BerriAI/litellm/pull/44776).

Audited on 2026-10-08 with `pip-audit==2.10.1`, using package metadata extracted
from the exact digest-pinned images with networking disabled:

| Image | Installed Python distributions | Known advisories | Skipped packages |
| --- | ---: | ---: | ---: |
| Proxy 1.103.4, linux/amd64 | 201 | 0 | 0 |
| Migrations 1.103.4, linux/amd64 | 147 | 0 | 0 |
| Proxy 1.103.4, linux/arm64 | 201 | 0 | 0 |
| Migrations 1.103.4, linux/arm64 | 147 | 0 | 0 |

The historical multi-platform index pins at that audit were:

```text
ghcr.io/berriai/litellm@sha256:8a372e5c22acddcd78e86a68e1c054bd97768ae600006a776475d2d8d4e7574b
ghcr.io/berriai/litellm-migrations@sha256:6206b0d6832242a5dd5b3eb7542da64e7a5b06c80a60dfed6c20f8be0e359158
```

The proxy package changes below remove the versions identified by the original
audit. Counts reflect the advisory database at the time of that scan and can
include related reports; they are not counts of independently exploitable paths.

| Package | 1.103.1 version | Original advisories | 1.103.4 version |
| --- | --- | ---: | --- |
| PyJWT | 2.13.0 | 14 | 2.15.0 |
| fsspec | 2026.4.0 | 1 | 2026.6.0 |
| multidict | 6.7.1 | 1 | 6.9.1 |
| oauthlib | 3.3.1 | 1 | 4.0.0 |
| pypdf | 6.16.2 | 8 | 6.19.0 |
| tornado | 6.5.8 | 3 | 6.5.9 |
| urllib3 | 2.7.0 | 3 | 2.8.0 |

The original findings include conditional JWT authentication bypass,
untrusted-input execution and denial of service, and OAuth timing exposure.
For example, the critical
[PyJWT advisory](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-ffc3-869f-jxw9)
requires a mixed symmetric/asymmetric algorithm allowlist and a particular key
representation. The
[urllib3 advisory](https://github.com/urllib3/urllib3/security/advisories/GHSA-vxq7-64xx-v4gw)
concerns unbounded buffering while parsing chunked responses, and the
[multidict advisory](https://github.com/aio-libs/multidict/security/advisories/GHSA-54p9-h82j-f925)
concerns a reference leak in view operations. This review does not claim all
findings were reachable in this deployment: the decision is to upgrade and
remove the affected versions, with no advisory suppressions.

## Reproduce and maintain

Docker and `uv` are required. The audit extracts installed distributions rather
than resolving or installing replacement dependencies inside the images:

```sh
python3 infra/litellm/scripts/audit_images.py --output-dir=/tmp/litellm-audit
```

The output contains each image reference/platform, exact package inventory and
JSON advisory report. The default platform is `linux/amd64`; add
`--platform=linux/arm64` to audit the Apple Silicon variant. The image containers
have no network access. The host needs access to GHCR and advisory services.
Keep generated reports outside Git and rerun the audit when preparing a release;
advisory data can change without an image change.

The `image-security` CI job audits both image defaults on every scoped PR and
main push. Any known advisory or auditor failure fails the job. No ignored IDs or
severity threshold are configured. Review an upstream update when this gate
fails, pin both official images to the same version, and rerun configuration,
migration, authentication, Redis/TLS and native gateway accounting tests before
deployment. Back up PostgreSQL and execute migrations before upgrading services.

Local regression checks passed on 1.103.4: migrations twice, UI authentication,
key persistence, two-instance Redis quotas/TLS, gateway route isolation, native
Gemini generation and incremental SSE, durable usage/global-budget accumulation,
and budget denial after restarting both proxies. The external Gemini provider
is stubbed for these tests; live Vertex inference and Cloud Run rollout require
separate deployment verification.

This gate covers installed Python packages and known advisories at scan time.
It does not audit OS packages, Node dependencies, image provenance or unknown
vulnerabilities, and is not a claim that the whole image is vulnerability-free.
