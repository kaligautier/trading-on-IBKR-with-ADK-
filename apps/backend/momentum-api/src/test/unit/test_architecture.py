"""Core use cases stay independent of presentation and concrete storage."""

import ast
from pathlib import Path

import pytest


@pytest.mark.parametrize("layer", ["domain", "ports", "services", "adapters"])
def test_dependencies_point_toward_domain(layer):
    root = Path(__file__).resolve().parents[2] / "app"
    package = root / layer
    assert package.is_dir()
    forbidden = ["app.presentation", "fastapi", "starlette"]
    if layer in {"domain", "ports", "services"}:
        forbidden.extend(["app.adapters", "sqlalchemy", "asyncpg"])
    if layer == "domain":
        forbidden.extend(["app.ports", "app.services"])
    for source in package.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.ImportFrom):
                imported = [node.module or ""]
            elif isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            else:
                continue
            for name in imported:
                assert not any(
                    name == prefix or name.startswith(prefix + ".")
                    for prefix in forbidden
                ), (source.relative_to(root), name)
