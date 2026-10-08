# LiteLLM image dependency review

## Decision and evidence

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

The multi-platform index pins in `variables.tf` are:

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
