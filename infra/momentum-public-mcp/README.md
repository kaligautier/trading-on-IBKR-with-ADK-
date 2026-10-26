# Public MCP deployment

Independent Terraform roots in `preprod-deep-copy/europe-west1`:

- `build/`: dedicated Cloud Build identity, private source bucket, repository
  publication grants and caller-key secret metadata. Existing Cloud Build API
  and Artifact Registry remain owned by their existing roots.
- This root: public `momentum-public-mcp`, dedicated runtime, additive invocation
  rights on the private `momentum-api` and `market-scanner-api`, and access to a
  single pinned caller-key secret version. No database or ADK permissions.

The Cloud Run `run.app` HTTPS URL remains available. Preprod configuration enables
the explicit transfer of `mcp.deepcopy.fr` to this service; other configurations
leave domain mapping disabled by default. The service keeps explicit scaling
limits and disables session affinity. Data APIs remain IAM protected.
No load balancer, Cloud Armor policy or additional edge resource is provisioned.

## Transfer the public domain

The applying account must have verified ownership of `deepcopy.fr` with Google.
The existing `mcp` CNAME is `ghs.googlehosted.com.`; compare it with
`domain_resource_records` and retain it unless Google's required records differ.
The mapping uses `force_override` to take over the hostname from
`deepcopy-momentum-mcp` in `gen-lang-client-0690499141`. Ensure legacy automation
will not reclaim that mapping. This plan changes routing, not the runtime image.

```sh
terraform -chdir=infra/momentum-public-mcp init -backend-config=config/preprod.backend.hcl
terraform -chdir=infra/momentum-public-mcp plan -var-file=config/preprod.tfvars -out=domain.tfplan
terraform -chdir=infra/momentum-public-mcp show domain.tfplan
terraform -chdir=infra/momentum-public-mcp apply domain.tfplan
gcloud beta run domain-mappings describe --domain=mcp.deepcopy.fr --project=preprod-deep-copy --region=europe-west1
python3 apps/backend/momentum-public-mcp/scripts/verify_live.py https://mcp.deepcopy.fr
```

Review a mapping-only plan before applying. Wait for `Ready` and
`CertificateProvisioned`, then require the real consultation verification above
to pass before retiring the old project. Domain mapping is a Google Preview
feature and certificate provisioning can delay availability. `prevent_destroy`
protects the mapping: setting the flag to false is not a rollback. A rollback
requires an explicit transfer back to the old service while it still exists.

References: [Cloud Run custom domains](https://docs.cloud.google.com/run/docs/mapping-custom-domains)
and [Terraform domain mapping](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_domain_mapping).

```sh
terraform -chdir=infra/momentum-public-mcp/build init -backend-config=preprod.backend.hcl
terraform -chdir=infra/momentum-public-mcp/build plan -out=build.tfplan
terraform -chdir=infra/momentum-public-mcp/build apply build.tfplan
```

Provision a random caller key directly into Secret Manager
`momentum-mcp-caller-key`, outside Terraform. Use a numeric version in the
runtime configuration. Momentum API must use the same key for the original
suggestions caller HMAC validation.

```sh
gcloud builds submit apps/backend/momentum-public-mcp \
  --project=preprod-deep-copy --region=europe-west1 \
  --config=infra/momentum-public-mcp/cloudbuild.yaml \
  --service-account=projects/preprod-deep-copy/serviceAccounts/momentum-mcp-builder@preprod-deep-copy.iam.gserviceaccount.com \
  --gcs-source-staging-dir=gs://preprod-deep-copy-mcp-build-sources/source
```

The app's `.gcloudignore` excludes environments, tests, caches and credentials.
Builds use pinned Python/uv digests, a locked wheel toolchain and a non-root
runtime image with no development dependencies. Keep the numeric secret version
in release tfvars, and deploy the resulting immutable image through the verifier:

```sh
python3 infra/momentum-public-mcp/deploy.py "$IMAGE_WITH_SHA256" --plan-only
python3 infra/momentum-public-mcp/deploy.py "$IMAGE_WITH_SHA256"
```

`deploy.py` validates the release inputs, saves and applies a Terraform plan, then
runs `verify_live.py` against the resulting URL. Verification calls the five
consultation tools, `server/discover` and `tools/list` without initialization or
sessions. It validates persisted analysis/report fields, tool errors, correlation
headers and rejection of legacy handshakes. It never submits a suggestion.
An existing analysis and nonempty scanner report are required to pass.

Only after verification succeeds does the wrapper write `.local/mcp-release.json`
and update the image digest in release tfvars. Commit the updated tfvars with the
release. A failed verification exits nonzero and leaves the deployed revision in
place for diagnosis; it does not automatically roll back. Earlier evidence files
refer to their recorded digest and must not be read as proof of a failed release.
To roll back, invoke the same wrapper with the previously verified image digest.
Keep API versions compatible with that image. Direct `terraform apply` bypasses
the gate, so use the wrapper for application releases.

Separately verify both private reader URLs reject unauthenticated requests.
For runtime diagnosis, use `X-Request-ID` to find the canonical
`request_completed` event in Cloud Logging. It includes HTTP, tool, business and
upstream outcomes, as described in the application README. Optional tfvars
`log_success_sample_rate` (default 1) and `log_slow_request_ms` (default 2000)
control tail sampling; errors and slow requests are always retained. Cloud Run
supplies `K_SERVICE` and `K_REVISION` for deployment attribution.

The recovered suggestion routes run in Momentum API using its existing pool and
isolated `_suggestions` schema. Both tools target that same API; the MCP has no
storage credentials. To explicitly test a pending submission after deployment:

```sh
cd apps/backend/momentum-public-mcp
uv run --locked python scripts/verify_live.py "$MCP_URL" --suggestion-symbol MCPTEST-UNIQUE
```

This creates a durable record marked as a test and checks status and deduplication.
Without the flag, the script only reads data. Confirm the record independently in
PostgreSQL before claiming durable persistence.

For an ADC reauthentication error, refresh local Application Default Credentials
or supply an ephemeral `GOOGLE_OAUTH_ACCESS_TOKEN` from the existing gcloud
identity to Terraform. Never print tokens or put them in HCL, plans or files.

Offline validation uses `terraform init -backend=false -lockfile=readonly`,
`terraform validate` and `terraform test` in a separate checkout/directory when
the root has already been initialized against the live backend.
`python3 -m unittest discover -s infra/momentum-public-mcp/tests -p 'test_*.py'`
tests release gating without cloud access; CI runs it on each relevant change.
