# Required pull request checks

`ci.yml` always runs on pull requests, including documentation-only changes.
It selects reusable component workflows using `.github/ci-components.json` and
the complete three-dot PR diff. Renames include both the old and new paths.
Changes to the gate itself select all components; manual runs also select all.

`CI required` runs with `always()` and checks both the called workflow result
and every required child job. A failure, cancellation, missing result or
unexpected skip fails the gate. Only unselected components may be skipped.
The scope job also runs the PR-policy and gate regression tests on every PR.
Ruff and database rehearsal retain their existing independent required checks.

When adding a component or verification job, update the manifest and the caller
in the same PR. Every reusable workflow exposes `toJSON(jobs)` so missing or
skipped child jobs cannot be hidden behind a successful workflow result.
Keep scoped push checks and scheduled image audits; they serve different events.

Scanner publication remains in `scanner.yml` on main push/manual dispatch and
depends on the same read-only `scanner-checks.yml` used by PRs. The PR caller
does not receive OIDC write permission or inherit release secrets.

## Activate after merge

The new check becomes mandatory only when GitHub branch protection is updated.
Merge the workflow first, confirm `CI required` has been emitted successfully
for a PR, then apply the versioned required-check list from the updated main:

```sh
gh api --method PATCH \
  repos/kaligautier/trading-on-IBKR-with-ADK-/branches/main/protection/required_status_checks \
  --input .github/required-checks.json
gh api repos/kaligautier/trading-on-IBKR-with-ADK-/branches/main/protection/required_status_checks
```

The file preserves the four existing checks, their GitHub Actions app binding
and strict up-to-date enforcement. Review it against live protection before
applying if other requirements have been added meanwhile. This endpoint does
not change review rules, administrator enforcement or force-push protection.
Do not require the path-filtered push workflows individually.

Known advisory failures remain failures: this gate introduces no audit bypass
for LiteLLM while corrected official images are awaited (issue #53).
