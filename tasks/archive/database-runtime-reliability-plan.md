# Database runtime reliability implementation plan

Authorized by the user instruction `implem` after specification PR #178.
Scope: [specification](../docs/specs/database-runtime-reliability.md).
The previous consultation plan/checklist is preserved under tasks/archive/.

## Dependency order and decisions

1. TLS adapters: explicit verified SSLContext shared between each worker's result
   and session connection paths. Keep separately packaged apps independent.
2. Memory migration: private analysis tables, execution-scoped unique key, narrow
   runtime grants, no reader access; preserve baseline adoption semantics.
3. Memory repository and orchestration: async bounded queries; use the existing
   result transaction for decisions/reflections. Stable record IDs disambiguate
   same-date decisions. External calls run outside transactions.
4. Capacity: inspect reserved slots and consumers, then encode the global budget,
   align pools/roles and add cross-process admission before model work. Admission
   cleanup and revision overlap are test obligations, not documentation assumptions.
5. Full rehearsal, TLS integration, restart/rollback/isolation/retry tests,
   constrained-capacity tests, packaging, Terraform mock checks and linked PRs.

## Delivery

Keep PR #178 as the specification/plan entry point. Publish dependent slices with
at most one application component and under 1,000 counted lines per PR. No merge
or live migration/apply is implied. Local evidence must never imply live rollout.

## Risks and checkpoints

- Old secrets may specify weaker TLS: document the verified URL/CA cutover.
- New memory tables change current fingerprints: distinguish immutable baseline
  verification/adoption from the post-migration state and test both.
- Do not keep transactions or extra pools open during model/market-data calls.
- Capacity allocation depends on live reserved/provider slots; fail closed when
  configuration is inconsistent, without increasing paid capacity.
- Checkpoint after each slice: focused regression passes, review diff, commit.
- Final checkpoint: every TLS/MEM/CAP/REG criterion has direct evidence; OPS
  records the deployment prerequisite separately.
