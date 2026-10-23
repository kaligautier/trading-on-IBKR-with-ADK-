# Ruff setup

The repository follows the pre-commit and GitHub Actions workflow described in
[the Ruff guide](https://www.stephane-robert.info/docs/developper/programmation/python/ruff/).

## Before each commit

The root `.pre-commit-config.yaml` uses Ruff **0.17.2** for Python files across
this repository:

- `ruff-check --fix` applies safe fixes and checks complexity (`C90`, maximum 10).
- `ruff-format` formats the code after lint fixes.

Both hooks use each application's existing Ruff configuration. `ruff-check` is
the current hook name; `ruff` is its legacy alias.

Enable the hooks once per clone, from the repository root:

```sh
uv tool install pre-commit
pre-commit install
```

After installation, pre-commit checks staged Python files at commit time. If a hook modifies a file or reports an
error, the commit stops. Review and stage corrections, then retry the commit.
Complexity errors require a manual refactor.

To run the hooks on all tracked files (this can modify files):

```sh
pre-commit run --all-files
```

## GitHub Actions and local checks

The global `.github/workflows/lint.yml` runs on pushes to `main` and pull
requests targeting `main`. It uses the same Ruff version, project settings and
complexity threshold, checking Python files across the repository without applying
fixes. The explicit include override also applies inside nested projects, so the
new Markdown formatter is outside the scope of both CI and the Python hooks:

```sh
uvx ruff==0.17.2 check --output-format=github --extend-select C90 --config 'lint.mccabe.max-complexity=10' --config 'include=["*.py", "*.pyi"]' .
uvx ruff==0.17.2 format --check --config 'include=["*.py", "*.pyi"]' .
```

Run `just lint` for the same local checks, or `just complexity` for C90 only.
Keep the version and complexity options aligned in the hook configuration,
workflow and root justfile when upgrading Ruff.

Ruff checks lint and formatting; it does **not** execute pytest or enforce file
and method line counts. Application workflows retain their existing tests.
All four backend development dependencies and lockfiles use Ruff 0.17.2 as well. Shared scripts use the explicit
rule set in `ruff.toml`, preserving the policy used before the upgrade.

References: [official Ruff integration](https://docs.astral.sh/ruff/integrations/#pre-commit)
and [pre-commit installation](https://pre-commit.com/#install).
