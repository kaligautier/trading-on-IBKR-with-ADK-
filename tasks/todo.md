# Momentum review checklist

Status: implementation is deployed and verified; source integration into `main`
is pending review. This checklist replaces the chronological implementation
steps with the final domain boundaries. The original SPEC remains authoritative
for unfinished functionality.

## Ordered stack

- [ ] 01 `review/momentum-01-design` — define final architecture and review sequence.
- [ ] 02 `review/momentum-02-contracts` — package validated analysis inputs and storage configuration.
- [ ] 03 `review/momentum-03-financial-schemas` — preserve financial schemas and rendering contracts.
- [ ] 04 `review/momentum-04-result-models` — model financial results and execution correlation.
- [ ] 05 `review/momentum-05-database-foundation` — preserve migration history and restricted database grants.
- [ ] 06 `review/momentum-06-database-compatibility` — retain applied split-database migrations and compatibility checks.
- [ ] 07 `review/momentum-07-database-runtime` — use one database with isolated session and analysis schemas.
- [ ] 08 `review/momentum-08-result-persistence` — commit complete financial results atomically.
- [ ] 09 `review/momentum-09-alpha-market-data` — add market primitives and Alpha Vantage adapters.
- [ ] 10 `review/momentum-10-yahoo-market-tools` — connect Yahoo data and provider routing to ADK tools.
- [ ] 11 `review/momentum-11-gateway-agents` — route all agent roles through a bounded LiteLLM gateway.
- [ ] 12 `review/momentum-12-workflow` — compose analyst debates and final decisions.
- [ ] 13 `review/momentum-13-decision-memory` — enrich analyses with decision memory and outcomes.
- [ ] 14 `review/momentum-14-worker-image` — package the persistent analysis worker.
- [ ] 15 `review/momentum-15-cloud-run` — deploy and verify the private analysis job.

## Reviewer checks

- Package and contracts: invalid tickers/analysts fail validation; no eager cloud initialization.
- Financial schemas: original fields, enums and renderers remain compatible.
- Result models: twelve tables and required execution correlation; no session foreign key.
- Database foundation: runtime privileges are restricted; migration rollback preserves Scanner.
- Migration compatibility: applied historical checksums remain unchanged.
- Unified runtime: both explicit URLs target `momentum`; each login accesses its own schema.
- Persistence: all sections commit together; failures roll back; null trader rationale is supported.
- Market data: provider selection, report formats and ticker path handling are preserved.
- Agents: every role uses LiteLLM; shared request pacing respects the existing virtual key.
- Workflow: all analyst, investment, risk and portfolio stages remain present.
- Memory: outcome enrichment is preserved; filesystem memory/cache remains ephemeral in Cloud Run.
- Worker: validated payload, bounded connections, correlated result commit before exit zero.
- Deployment: private job, dedicated identity, secret references, immutable image, isolated state.

## Remaining implementation scope

- [ ] Private HTTP dispatcher, request contract and job-scoped execution permissions.
- [ ] HTTP authentication/anonymous-denial tests and authorized dispatch verification.
- [ ] Broader controlled provider/transport failure coverage from the original specification.
- [ ] Automated image publication after checks; current release was explicitly deployed.

The 97 historical analyses were copied separately into `_analysis` with `legacy`
correlation markers. No old sessions were imported. That operational data copy is
not a schema migration or a tracked database dump; backups remain private.
