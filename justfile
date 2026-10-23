# List repository-wide commands.
default:
    @just --list

# Run the same repository-wide Ruff lint and format checks as CI.
lint:
    uvx ruff==0.17.2 check --extend-select C90 --config 'lint.mccabe.max-complexity=10' --config 'include=["*.py", "*.pyi"]' .
    uvx ruff==0.17.2 format --check --config 'include=["*.py", "*.pyi"]' .

# Check Python cyclomatic complexity across the repository (maximum 10).
complexity:
    uvx ruff==0.17.2 check . --select C90 \
      --config 'lint.mccabe.max-complexity=10' \
      --config 'include=["*.py", "*.pyi"]'
