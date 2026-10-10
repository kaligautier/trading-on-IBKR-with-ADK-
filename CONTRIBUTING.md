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

Run the scanner's unit tests and lint checks from its directory:

```sh
TZ=UTC uv run pytest -q src/test/unit
uv run ruff check src
```

Add or update tests for behavior changes. Database integration tests live in
`apps/backend/market-scanner-adk/src/test/integration` and require a disposable
local PostgreSQL database. Follow the [database test instructions](database/README.md)
to run them without skips. Migration files live in `database/changelog`.

For Terraform changes, run these checks from the repository root:

```sh
terraform fmt -check -recursive infra
terraform -chdir=infra/bootstrap init -backend=false
terraform -chdir=infra/bootstrap validate
terraform -chdir=infra/bootstrap test
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
terraform -chdir=infra test
```

Terraform tests use mocked providers and do not verify a live deployment.
See the [deployment guide](infra/README.md) for live validation.
Documentation-only changes should have valid links and commands that match the
repository.

## Pull requests

- Explain what changed and why; link a related issue when available.
- Include the validation commands and results, and identify anything not tested.
- Update the relevant documentation when configuration or behavior changes.
- Keep project-authored documentation, comments, and examples in English.
- Exclude credentials, local environment files, Terraform state, and private data
  from commits and attached logs.

Submit changes through a GitHub pull request for maintainer review.
