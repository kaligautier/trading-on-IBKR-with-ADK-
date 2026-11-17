"""The partial library must install independently without starting a runtime."""

import ast
import os
import subprocess
import sys
import tomllib
from importlib import metadata


def test_package_is_installed_in_its_own_environment(project_root):
    distribution = metadata.distribution("momentum-adk")
    configuration = tomllib.loads((project_root / "pyproject.toml").read_text())

    assert distribution.version == configuration["project"]["version"]
    assert configuration["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "app"
    ]
    assert "scripts" not in configuration["project"]


def test_import_works_outside_checkout_without_runtime_configuration(tmp_path):
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GOOGLE_", "LITELLM_", "TA_", "DATABASE_", "MOMENTUM_"))
    }
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; import app; "
            "assert app.__file__; "
            "assert not any(name.startswith(('google', 'sqlalchemy', 'httpx')) "
            "for name in sys.modules)",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr


def test_application_does_not_import_sibling_or_legacy_packages(project_root):
    forbidden = {"api", "tradingagents", "apps", "market_scanner"}
    for source in (project_root / "app").rglob("*.py"):
        tree = ast.parse(source.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            assert not any(module.split(".")[0] in forbidden for module in modules)
