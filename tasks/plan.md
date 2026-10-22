# Momentum delivery and review plan

The target is a private Cloud Run analysis worker using LiteLLM and one PostgreSQL
`momentum` database: `_sessions` for ADK history and `_analysis` for financial
results. See the [specification](../docs/specs/momentum-service.md).

## Review strategy

The replacement stack starts from `main` at `1ad365b`. Each PR covers one domain
and changes fewer than 1,000 counted lines (additions plus deletions); generated
`uv.lock` and `package-lock.json` are excluded by repository policy. Dependencies
are explicit: review and merge from the bottom of the stack upwards, retargeting
and rerunning checks as parent PRs land. No automatic merge is configured.

The stack starts from tested worker source `83003b5`. Review corrections cover
provider date windows, fallback and durable resume statistics. Previously deployed
migrations stay byte-for-byte unchanged, including the obsolete layouts whose
checksums and compatibility tests must remain valid. Their presence is historical
compatibility, not a request to provision separate databases again.

The old 25-PR stack remains available as history. The replacement folds live
fixes into the responsible domain: gateway pacing into agent configuration and
nullable trader rationale into result persistence. This avoids asking reviewers
to approve behavior already known to fail before reviewing its correction.

## Validation

Each code checkpoint runs all unit tests present at that checkpoint plus Ruff.
Each database checkpoint runs the applicable real PostgreSQL integration suite
against the labeled disposable local container. The final stack preserves the
164 unit and 52 database tests, the immutable image reference and Terraform tests.
CI is introduced progressively: library checks with the package, database checks
with the harness, and infrastructure/dependency checks with the deployment root.

The deployed worker has already completed a real AAPL analysis through LiteLLM
and persisted its correlated financial result. Restacking PRs does not redeploy
infrastructure or execute another paid analysis. Live evidence is in
[the infrastructure PR](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/98),
which introduces the rollout guide.
