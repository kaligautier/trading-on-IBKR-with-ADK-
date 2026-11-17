"""The standalone reader never acquires worker, cloud-dispatch or broker clients."""

import ast
from pathlib import Path


def test_runtime_has_no_execution_clients_or_sibling_imports():
    runtime = Path(__file__).resolve().parents[2] / "app"
    forbidden = {
        "google",
        "litellm",
        "httpx",
        "requests",
        "subprocess",
        "ib_insync",
        "momentum_adk",
        "market_scanner_api",
    }
    for source in runtime.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                roots = {(node.module or "").split(".")[0]}
            else:
                continue
            assert not roots & forbidden, source
