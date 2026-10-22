# Remote release map — 2026-10-21

GCP project `preprod-deep-copy`, region `europe-west1`; Aiven project `deep-copy`,
service `pg-25f92602`. The service host was matched to deployed secret versions
before obtaining administrator credentials. No hostname/password/token is committed.

| Consumer | Database / schemas | Connection secret version | Deployed image digest |
| --- | --- | --- | --- |
| `market-scanner-adk` service and `market-scanner-daily` job | `market_scanner` / `_sessions`, `_analysis` | `market-scanner-database-url:2` | `sha256:0f97ac08efc4ee751ce4bc78945e5cb4028226c071290aaeaa973ca73290932c` |
| `market-scanner-api` service | `market_scanner` / `_analysis` | `market-scanner-reader-database-url:2` | `sha256:a333eee870f9373b70cd6a92e91a0ddc356bdb2b10d85942ac7426aa5364af87` |
| `momentum-analysis` job, preserved existing deployment | `momentum` / `_sessions`, `_analysis` | `momentum-session-database-url:1`, `momentum-result-database-url:1` | Baseline `sha256:ff22bf24ecd93708195f6cf83fbd08128d037e36dcffc025a0860970f867d9f5` |

Scanner and reader images live in Artifact Registry repository
`europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner`, named
`market-scanner-adk` and `market-scanner-api`. Both are tested linux/amd64 images
built from source commit `5452ecc33e0f4f82d1b4b105414ad82b9666099f`,
retained by tag `source/domain-databases-20261021`. Scanner service revision: `market-scanner-adk-00005-pmz`;
reader revision: `market-scanner-api-00011-zs8`, each with all traffic.

Terraform owners: `infra` (GCS prefix `preprod/runtime`) and `infra/reader`
(`preprod/reader`), bucket `preprod-deep-copy-tfstate`. Numeric release inputs are
in their ignored `release.local.tfvars`; this map records their non-secret values.
Plans changed only images, DB secret versions and `DATABASE_SCHEMA=_analysis`.
Frontend IAM and the Scanner LiteLLM key version `1` were preserved.

Momentum's authoritative runtime is the separate `momentum-cloud-run` worktree,
with its own Terraform root and ongoing changes. It already used the final domain
layout at inventory time; this cutover did not apply its infrastructure or reset
its database. Its baseline image is an observation, not a request to roll back
subsequent independent Momentum releases.

TLS parameters were copied exactly from the deployed connection URLs: Scanner
retains `sslmode=require`; reader retains `verify-full` and its CA volume. The
migration/admin verification connections use `verify-full`. This deployment does
not claim to strengthen Scanner's existing TLS verification mode.

Server PostgreSQL 18.6 has `max_connections=15`. Scanner writer limit=4 (API
session+analysis and one job session+analysis), reader limit=2; each Momentum writer
limit=2, migrator limit=1. Scanner service max instances=1, concurrency=1, worker=1;
no overlapping validation jobs or deployments. LiteLLM connections share the same
server budget; extra jobs/replicas require a new capacity review.
