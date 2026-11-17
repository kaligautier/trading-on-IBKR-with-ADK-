# Market Scanner root relocation evidence

Verified on 2026-10-22 against base commit `7949165`, implementing
[spec PR #138](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/138).
The operator procedure and rollback are in the
[Scanner guide](../../infra/market-scanner/README.md#moving-an-existing-checkout).

## Repository checks

- All 12 tracked Scanner Terraform, lock, config and test files moved from
  `infra/` to `infra/market-scanner/` byte-for-byte. No resource or input contract
  changed, and no Terraform configuration remains in the parent directory.
- Scanner CI init/validate/test paths and the Dependabot directory were updated.
  The broad `infra/**` workflow triggers and bootstrap checks were preserved.
- Active operational examples, contribution commands and ownership references
  use the new root. Dated migration evidence retains its historical paths.
- Terraform recursive formatting and Scanner/bootstrap validation passed.
  All 10 Scanner mock tests and the bootstrap mock test passed.
- `actionlint` 1.7.7 passed for the Scanner workflow. All 20 PR-policy unit tests
  passed. Local Markdown links/anchors and representative ignored release inputs,
  state, provider data, plans and override paths were checked.

## Remote state and full plans

The original root was reconstructed from the base commit in an isolated directory.
Both roots used the same current private release inputs, Terraform 1.14.4,
unchanged provider lock, GCS backend configuration and `default` workspace.

| Check | Result |
| --- | --- |
| State lineage | Identical before and after |
| State serial | Identical before and after |
| State resource address inventory | Same 9 addresses |
| Original root, full refreshed plan | Exit 0; no changes |
| Relocated root, full refreshed plan | Exit 0; no changes |

The first comparison found stale ignored release inputs in the main local
checkout: both roots proposed the same image and database secret-version rollback.
The existing integration worktree held current release inputs matching the live
deployment. Those identical inputs were supplied to both isolated roots before
the successful comparison; the user's original local inputs were not edited.

Plans used neither resource targeting nor disabled refresh. No apply, state
migration, resource import, deployment or scan execution occurred. Raw state,
plans, logs and release inputs remained in protected local files outside Git.
This evidence is a dated observation; rerun the full plan before a later deployment.
