# Scanner remote cutover runbook

The 2026-10-21 execution is recorded in [evidence](evidence.md) and the
[release map](release-map.md). These are one-time fresh-cutover actions, not a
routine reset/retry script. Existing Momentum storage is preserved because its
remote layout already meets the requirement.

Run from the isolated worktree with the Scanner's locked dependencies installed.
Keep credentials and `AIVEN_AUTH_TOKEN` in ignored regular mode-0600 files.
Arguments below contain file paths only. The CA is a public certificate and must
be readable by the non-root Liquibase container. `CREDENTIALS` contains the three
existing defaultdb URLs: `MIGRATION_DATABASE_URL`, `MARKET_SCANNER_DATABASE_URL`,
and `MARKET_SCANNER_READER_DATABASE_URL`.

```sh
cutover() {
  uv run --project apps/backend/market-scanner-adk --frozen python \
    database/scripts/scanner_cutover.py "$@" \
    --credentials "$CREDENTIALS" --token-env "$TOKEN_ENV" --ca "$DATABASE_CA" \
    --evidence "$EVIDENCE_DIR" --aiven-project deep-copy --gcp-project preprod-deep-copy
}
cutover inspect
```

1. Inventory service/job revisions, active executions, effective grants, exact
   defaultdb objects and both domains' histories. Match the Aiven service host to
   the deployed secrets. Unknown ownership/dependencies stop cleanup.
2. For an absent Scanner database only: `cutover bootstrap`, then `cutover migrate`.
   Bootstrap separates administrator and migrator connections (Aiven administrator
   is not a superuser). Migrate validates, previews exactly five session and three
   analysis tables, applies, then checks a second no-op update. It expects the
   pre-migration state: do not rerun this action after it has already applied.
3. Verify real SDK session reopen and runtime DDL/metadata/reader denials. Build,
   test and publish both linux/amd64 images; write their immutable URLs to
   `images.json` with `scanner` and `reader` keys in the protected evidence folder.
   `cutover publish` copies the exact current deployed DB URLs, replacing only
   `/defaultdb` with `/market_scanner`, and records numeric secret versions.
4. Update ignored Terraform release inputs from the release map. Save and inspect
   both plans; only three Cloud Run resources should change. Pause the scheduler,
   confirm no active old execution, then apply the reviewed plans:

```sh
umask 077
terraform -chdir=infra plan -var-file=config/preprod.tfvars -var-file=config/release.local.tfvars -out=/private/tmp/scanner.tfplan
terraform -chdir=infra/reader plan -var-file=release.local.tfvars -out=/private/tmp/reader.tfplan
# Review these saved plans before pausing and applying them.
gcloud scheduler jobs pause market-scanner-daily-0700 --project=preprod-deep-copy --location=europe-west1
terraform -chdir=infra apply /private/tmp/scanner.tfplan
terraform -chdir=infra/reader apply /private/tmp/reader.tfplan
gcloud run jobs execute market-scanner-daily --project=preprod-deep-copy --region=europe-west1
```

5. Wait for success; correlate the execution with `_sessions.sessions/events` and
   `_analysis.market_scans.session_id = 'scheduled:' || execution`. Fetch session
   through the deployed ADK HTTP API after worker exit and compare reader latest
   and detail payloads exactly to the stored report. Record verified `execution`
   and `scan_id` in `verified-scan.json`; never fabricate this proof to bypass gates.
6. `cutover cleanup` rechecks all consumers' exact images, schemas, database URLs,
   traffic and completed executions. It requires the verified successful run and
   its report/session still in PostgreSQL. It refuses busy/unknown legacy clients,
   unexpected objects/history and dependencies. It drops only the three old Scanner
   tables, their schema and isolated Liquibase history, using RESTRICT, never CASCADE.
   Then it retires domain access to defaultdb while preserving existing unrelated
   login access. No whole database, Momentum or LiteLLM data is dropped.
7. Audit defaultdb, cross-domain CONNECT, histories and live consumer references.
   Resume scheduling and require both Terraform plans to report no changes:

```sh
gcloud scheduler jobs resume market-scanner-daily-0700 --project=preprod-deep-copy --location=europe-west1
```

On failure, preserve sessions/logs, diagnose, repair forward, and explicitly create
one new execution when appropriate. Do not replay an existing execution ID or
rerun bootstrap/reset automatically. If cleanup partially completes, inspect its
actual state and repair the remaining step; do not force its inventory guard.
