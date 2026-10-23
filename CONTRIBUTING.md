# Contributing

Contributions to Deepcopy are welcome. Keep pull requests focused on one change
and describe the problem, the resulting behavior, and how you verified it.
For substantial features, open an issue to discuss the proposed scope first.

## Development setup

The Market Scanner source is in `apps/backend/market-scanner-adk`.
It requires Python 3.12 or later and uv. From that directory:

```sh
uv sync --frozen
cp .env.example .env
```

Configure `GOOGLE_CLOUD_PROJECT`, `LITELLM_API_BASE` and `LITELLM_API_KEY` in `.env`.
The gateway must be reachable from your process; see
[LiteLLM configuration](docs/adk-litellm.md). Start the service with `just api 7777`.
Send `X-Market-Scanner-Token` with the configured token on API calls. For the
ADK UI at <http://127.0.0.1:7777/dev-ui/>, you can clear `MARKET_SCANNER_TOKEN`
only while the service is bound to localhost. Live scans call external providers
and Gemini; configuring a database URL also enables report persistence.

## Validation

### Ruff pre-commit hooks

The shared `.pre-commit-config.yaml` at the repository root runs Ruff 0.17.2
fixes and formatting on staged Python files throughout the repository. It uses
the same rules, including `C90` (maximum complexity 10), and Ruff version as
the global `Lint` workflow. Each contributor enables it once per clone:

```sh
uv tool install pre-commit
pre-commit install
```

Run these commands from the repository root. To check all tracked files in
the configured scope manually, run `pre-commit run --all-files`. If a hook
changes files, review and stage the corrections, then retry the commit.
Remaining lint errors also block the commit. GitHub Actions checks the whole
repository without modifying files. These Ruff hooks do not run pytest; tests
remain in the application workflows. Local hooks are not installed automatically
when cloning the repository.

### Python checks

The global `Lint` workflow checks the repository on pushes to `main` and pull
requests targeting `main`. It runs Ruff 0.17.2 lint (including `C90`, maximum
McCabe complexity 10) and format checks, with GitHub annotations for lint errors.
Global commands explicitly include only `.py` and `.pyi` files, matching the
hooks even when a nested project has its own Ruff configuration.
Run the same checks locally from the repository root:

```sh
just lint
```

This uses `uvx` with the pinned Ruff version and needs no application environment.
Keep its version and complexity options aligned with `.github/workflows/lint.yml`
and `.pre-commit-config.yaml` when upgrading Ruff. All four backend development
dependencies are also pinned to Ruff 0.17.2.
When upgrading Ruff, update those declarations and regenerate their lockfiles.

Run the repository-wide Python complexity audit from the root:

```sh
just complexity
```

This runs the pinned Ruff version through `uvx`, with a maximum McCabe complexity
of 10, without requiring an application environment.
This command checks the whole repository, including Python tests and scripts.

Run the scanner's unit tests and lint checks from its directory:

```sh
TZ=UTC uv run pytest -q src/test/unit
uv run ruff check src
```

Add or update tests for behavior changes. Database integration tests live in
`apps/backend/market-scanner-adk/src/test/integration` and require a disposable
local PostgreSQL database. Follow the [database test instructions](database/README.md)
to run them without skips. Migration files live in `database/domains/<domain>/migrations`.

For Terraform changes, run these checks from the repository root:

```sh
(
set -e
terraform fmt -check -recursive infra
for root in infra/bootstrap infra/market-scanner infra/litellm infra/reader infra/frontend/build infra/frontend; do
  terraform -chdir="$root" init -backend=false -input=false -lockfile=readonly
  terraform -chdir="$root" validate
  terraform -chdir="$root" test
done
)
```

Terraform tests use mocked providers and do not verify a live deployment.
See the [deployment guide](infra/market-scanner/README.md) for live validation.
Documentation-only changes should have valid links and commands that match the
repository.

## Pull requests

- Change at most one application component per PR. Each `apps/backend/<service>`
  directory is a separate component; `apps/frontend` (and any other
  `apps/<application>` directory) is also a component. The `PR component scope`
  CI check rejects changes spanning two components, including file moves between
  them. Tests, configuration and lockfiles inside a component count toward it.
  Shared files outside these directories (for example `.github`, `docs`,
  `database`, `infra` and root documentation) may accompany a component change
  or be changed independently. They do not increase the component count.
  Split coordinated changes into dependent PRs. This check does not replace
  code review or the existing PR size limit.
  Enforcement uses the default branch's trusted rules, never scripts from the
  proposed PR or a dependent PR's base branch. A separate read-only workflow
  tests proposed policy changes before they become enforcement rules on merge.
- Keep each PR at or below 1,000 changed lines (additions + deletions).
  Generated `package-lock.json` and `uv.lock` files are excluded from this count
  but must remain versioned and subject to dependency/security checks. All other
  files count. The `PR size` CI check fails above this limit;
  split larger changes into smaller PRs. The count applies to the whole PR,
  not to each commit. Binary files contribute GitHub's reported line count.
- Explain what changed and why; link a related issue when available.
- Include the validation commands and results, and identify anything not tested.
- Update the relevant documentation when configuration or behavior changes.
- Keep project-authored documentation, comments, and examples in English.
- Exclude credentials, local environment files, Terraform state, and private data
  from commits and attached logs.

Submit changes through a GitHub pull request for maintainer review.
