**Infrastructure review — origin/main, 23 October 2026**

The infrastructure demonstrates strong intermediate engineering with several
senior-level design choices. My indicative assessment is **7/10 overall**:
architecture, security design and configuration testing are stronger than
operational automation and cross-stack verification. This rates the evidence in
this repository, not the author's experience, independence or professional title.

Reviewed revision: [`d5151286eef670f631bcb77c4cfc2610ccb13472`][revision], fetched
from `origin/main` for this review. Findings and links refer to that commit.
The previous local Terraform audit examined `19fe390`; its governance identity,
Momentum secret-protection and gateway-validation findings were fixed by
[`376fe74`][fixes] and are not repeated as current defects.

**Scope and verification**

The inventory contains 109 tracked files under `infra/`, including 35 Terraform
files, nine HCL test files, nine roots and one child policy module. Review covered
Terraform resources, IAM and networking boundaries, bootstrap scripts, container
configuration, operational documentation, and the associated workflows and
Dependabot configuration. Official Google Cloud and HashiCorp documentation was
searched and consulted for the comparisons below.

Checks ran against a clean archive of the reviewed commit, using Terraform
1.14.4, matching CI. Each configuration was initialized with
`init -backend=false -input=false -lockfile=readonly`, validated and tested.
No live backend was initialized and no cloud resources were changed.

| Configuration | Validate | Existing Terraform test runs passed |
| --- | --- | ---: |
| `bootstrap` | Pass | 1 |
| `market-scanner` | Pass | 10 |
| `reader` | Pass | 6 |
| `momentum` | Pass | 18 |
| `momentum-api` | Pass | 6 |
| `litellm` | Pass | 34 |
| `litellm/governance` | Pass | 0 |
| `litellm/governance/policy` | Pass | 4 |
| `frontend` | Pass | 5 |
| `frontend/build` | Pass | 0 |
| **Total** | **10/10** | **84** |

`terraform fmt -check -recursive infra` passed. All ten provider lockfiles
remained byte-identical to the commit after initialization. Frozen Scanner test
dependencies were installed with Python 3.12; all 28 LiteLLM Python regression
tests and Ruff checks on its scripts/tests passed. Two additional temporary
mocked Terraform plans and two Python characterization scenarios reproduced
the first two findings below; they are separate from the existing test counts.

The Terraform tests use mocked providers, including the test with `command =
apply`. The two configurations with zero tests have schema validation only.
Mock tests cannot establish effective cloud permissions, connectivity or a
successful deployment. [HashiCorp documents this distinction][terraform-tests].
Container smoke tests and image vulnerability scans were inspected but not
rerun. Effective IAM, remote state, current drift, deployed image overrides,
provider backups and restore success were not verified in this review.

**Findings requiring attention**

1. **P2 — Generic database bootstrap validates retained credentials too late.**
   In [bootstrap_database.py][bootstrap-generic], the script changes database
   ownership and privileges before reading and validating the retained
   connection URL. A mocked run with an existing database and a stored URL for
   another host recorded five SQL mutation calls before the expected refusal.
   Those mutations are not enclosed in a transaction that rolls them back.
   Separately, the script tests the supplied CA but `SecretStore.upload()` keeps
   any existing CA version without reading or comparing its contents. After a
   CA change, this can report a successful bootstrap while workloads remain
   pinned to an incompatible CA. The mock confirmed that the retained CA is
   neither accessed nor replaced; it does not simulate a real TLS failure.
   [The Aiven bootstrap][bootstrap-aiven] already performs the URL/CA preflight.
   Move these checks ahead of every SQL mutation in the generic path and reuse
   the same preflight logic. Add regressions requiring zero mutations for a
   mismatched URL or CA. Preserve credentials and require explicit rotation.

2. **P2, conditional on onboarding — Momentum and LiteLLM can own the same IAM
   member in two states.**
   [Momentum][momentum-iam] creates Secret Accessor for its worker on
   `litellm-client-momentum`. Following the [governance onboarding guide][onboard]
   with `client_service_accounts = { momentum =
   "momentum-worker@preprod-deep-copy.iam.gserviceaccount.com" }` makes
   [LiteLLM][client-iam] create the identical project/secret/role/member tuple.
   Two independent mocked plans confirmed that equality. Removing the grant
   from either owner can revoke it while the other state still expects it.
   The checked-in example has an empty client map, so this is a reproducible
   integration hazard, not a claim that both live states currently contain it.
   Assign this grant to one root and document ownership. Inspect both states
   before migrating ownership; simply deleting a resource declaration can
   revoke access. Terraform expects [one address per managed remote object][one-owner].

3. **P2 for production — Frontend domain mappings rely on a preview feature.**
   [frontend/main.tf][domains] uses `google_cloud_run_domain_mapping` when domain
   mappings are enabled. Google's current documentation calls this feature
   preview and advises against production use because of latency issues.
   For a production availability commitment, evaluate a global external
   Application Load Balancer, Google's recommended option, or Firebase Hosting.
   For a personal project, retaining the cheaper setup can be a documented
   tradeoff; this finding is not evidence of a current outage.
   [Official domain-mapping guidance][domain-docs].

**Operational maturity priorities**

- **Make failures and approaching expiry visible.** No `google_monitoring_*`
  resources, notification channels or `google_billing_budget` resources were
  found under `infra/`. The [key policy][key-policy] gives new keys a 30-day
  expiry and intentionally ignores later `duration` changes. Rotation is
  documented, but no expiry alert or scheduled rotation check is present in
  the reviewed workflows. A no-op apply will not renew a key. Add alerts for
  failed jobs, missing daily results, repeated gateway failures, expiring keys,
  database connection pressure and cloud spend. Verify that a forced failure
  reaches the intended notification channel. Console-managed monitoring may
  exist; its absence is not established by this code review.
  [Google supports managing alerting policies with Terraform][alerts].

- **Add a trusted deployment and drift workflow.** Existing Terraform CI checks
  run without a backend; they cannot detect drift or validate the actual
  deployment identity. Most deployment guides already use saved plans.
  However, the [governance commands][governance-plan] run an unsaved plan and
  then `apply -var-file`, which creates another plan. Save and apply the reviewed
  plan consistently. Introduce a trusted runner with short-lived credentials,
  per-state serialization, restricted plan artifacts and a periodic drift
  check. The governance runner must reach the private gateway. Keep cloud
  credentials away from untrusted PR code. These recommendations follow
  [Google's operational guidance][operations] and [security guidance][security].

- **Prove recovery with a timed exercise.** [RECOVERY.md][recovery] correctly
  separates infrastructure, state, database rows, secret values, encryption
  salt and OAuth assets. That is a strong runbook, but the reviewed code does
  not provide a repeatable scheduled restore exercise or measured recovery
  targets. Define acceptable data loss and downtime, restore into an isolated
  target, verify application data and privileges, and record elapsed time.
  This does not imply that provider-managed backups are absent.
  [Google recommends testing integrity, RPO and RTO][restore-docs].

**Smaller consistency improvements**

| Gap | Evidence and proportionate improvement |
| --- | --- |
| CI lock enforcement | [Momentum CI][momentum-ci] omits `-input=false -lockfile=readonly`. Add both. The existing lockfile is still used today; this is not evidence of arbitrary upgrades on every run. [HashiCorp documents readonly initialization][init-docs]. |
| Dependency update coverage | [Dependabot][dependabot] covers five Terraform directories. It omits `momentum`, `frontend`, `frontend/build`, `litellm/governance` and the policy module's standalone test lockfile. Docker coverage also omits `infra/frontend/Dockerfile`. Extend coverage and review updates. |
| Image audit scope | [audit_images.py][image-audit] scans installed Python packages in the proxy and migration defaults. It does not scan the NGINX image, OS packages, frontend image, or a different digest supplied by deployment inputs. Add release-image inventory/scanning appropriate to those artifacts; this is a coverage gap, not a claim of known vulnerabilities. |
| Incomplete entrypoint documentation | [infra/README.md][infra-readme] omits `momentum-api` from its inventory and validation loop. Its global Terraform minimum of 1.9 does not cover governance's 1.11 requirement. Align the inventory, commands and minimum version; CI currently pins 1.14.4. |
| Inconsistent interfaces | Many variables and outputs lack descriptions, especially in Momentum. Reader and Momentum API configurations are nearly identical. Add descriptions first; extract a small shared reader module only if joint maintenance justifies it. [Google's structure guidance][structure] supports clear interfaces and logical grouping. |

**Practices worth retaining**

- Separate application roots and state prefixes keep change scope manageable.
  This follows [Google's recommendation to separate applications][roots].
  A new orchestration framework is not needed merely to conform to a directory
  template. Introduce environment directories when a second environment exists.
- [The state bucket][state-bucket] enables private access, versioning, soft
  deletion and destruction protection. These align with the
  [GCS backend's locking and recovery guidance][gcs]. Effective bucket IAM still
  needs a live review.
- Dedicated service accounts, resource-level grants, IAM-protected readers,
  IAP-protected administration and an internal gateway show deliberate trust
  boundaries. The public frontend is intentional. Disabled gateway invoker IAM
  is paired with internal ingress and LiteLLM key authentication; it should
  not be treated as equivalent to an anonymous public gateway.
- Workloads use image digests and numeric secret versions. Governance combines
  ephemeral reads and write-only values so credentials need not be stored in
  plans/state. This goes beyond simply marking variables `sensitive`, which
  only redacts display. [HashiCorp sensitive-data guidance][sensitive].
- Tests reject public invocation, mutable images/secrets, unsafe URLs and
  unbounded policy settings. Bootstrap tests exercise error handling and
  credential redaction. CI actions are pinned by commit SHA.
- Resource limits, small database pools, scale-to-zero and disabled automatic
  job retries reflect cost awareness. Revision-level limits are not hard
  global ceilings: Google recommends service-level maximum instances for
  aggregate service caps, and temporary overruns remain possible.
  [Cloud Run scaling guidance][scaling].

No tracked Terraform state, saved plans or non-example local variable files
were found in the targeted `infra/` inventory. This is useful hygiene evidence,
not a full repository-history secret scan.

**Engineering-level assessment**

The scale below is a reviewer rubric, not an industry certification: 5 means
functional but reliant on manual safeguards; 8 means systematic design and
meaningful verification with remaining gaps; 10 would require exceptional
consistency and demonstrated operational outcomes.

| Dimension | Indicative score | Basis |
| --- | ---: | --- |
| Architecture | 8/10 | Clear roots, ownership intent and trust boundaries; one cross-root IAM conflict remains. |
| Security design | 8/10 | Scoped identities, secret hygiene, immutable references and explicit exposure. Runtime enforcement was not audited. |
| Automated testing | 8/10 | 84 Terraform and 28 Python cases pass, including negative paths; cross-root and recovery coverage is weaker. |
| Maintainability | 7/10 | Mostly short, focused files and useful guides; duplicated bootstrap behavior and inconsistent interfaces create drift. |
| Operations represented in code | 5/10 | Recovery procedures exist, but alerting, drift detection and repeatable release/restore evidence are incomplete. |

The strongest senior-level signals are reasoning about secret persistence,
failure recovery, IAM scope and provider limitations. The next step is to make
those guarantees consistent across roots and executable during operations.
For an interview or portfolio, be ready to explain why sensitive values differ
from ephemeral values, how IAM ownership moves safely between states, what mock
tests cannot establish, and how recovery is verified.

Recommended order: repair the generic bootstrap preflight; settle Momentum IAM
ownership before governance onboarding; add failure/expiry alerts; automate
reviewed plans and drift checks; rehearse recovery; then address dependency and
documentation consistency. Evaluate domain mapping before promising production
availability. Cosmetic file renaming and broad modularization are lower priority.

[revision]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/tree/d5151286eef670f631bcb77c4cfc2610ccb13472/infra
[fixes]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/commit/376fe74f1ae51013a7c66b44a53cee362e03fb48
[bootstrap-generic]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/infra/litellm/scripts/bootstrap_database.py#L129
[bootstrap-aiven]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/infra/litellm/scripts/bootstrap_aiven.py#L109
[momentum-iam]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/infra/momentum/main.tf#L43
[onboard]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/infra/litellm/governance/README.md#L24
[client-iam]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/infra/litellm/clients.tf#L27
[domains]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/infra/frontend/main.tf#L93
[key-policy]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/infra/litellm/governance/policy/main.tf#L85
[governance-plan]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/infra/litellm/governance/README.md#L33
[recovery]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/infra/litellm/RECOVERY.md
[momentum-ci]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/.github/workflows/momentum.yml#L101
[dependabot]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/.github/dependabot.yml
[image-audit]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/infra/litellm/scripts/audit_images.py#L32
[infra-readme]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/infra/README.md#L7
[state-bucket]: https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/d5151286eef670f631bcb77c4cfc2610ccb13472/infra/bootstrap/main.tf#L47
[terraform-tests]: https://developer.hashicorp.com/terraform/language/tests
[one-owner]: https://developer.hashicorp.com/terraform/cli/import/usage
[domain-docs]: https://docs.cloud.google.com/run/docs/mapping-custom-domains
[alerts]: https://docs.cloud.google.com/monitoring/alerts/terraform
[operations]: https://docs.cloud.google.com/docs/terraform/best-practices/operations
[security]: https://docs.cloud.google.com/docs/terraform/best-practices/security
[restore-docs]: https://docs.cloud.google.com/architecture/framework/reliability/perform-testing-for-recovery-from-data-loss
[init-docs]: https://developer.hashicorp.com/terraform/cli/commands/init
[structure]: https://docs.cloud.google.com/docs/terraform/best-practices/general-style-structure
[roots]: https://docs.cloud.google.com/docs/terraform/best-practices/root-modules
[gcs]: https://developer.hashicorp.com/terraform/language/backend/gcs
[sensitive]: https://developer.hashicorp.com/terraform/language/manage-sensitive-data
[scaling]: https://docs.cloud.google.com/run/docs/configuring/max-instances
