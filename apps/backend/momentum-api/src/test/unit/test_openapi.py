"""Published methods, error statuses, validators and output aliases agree with HTTP."""

import json
import runpy
from pathlib import Path

from app.presentation.routes.analyses import QUERY_PARAMETERS


def test_openapi_policy_and_financial_shapes():
    exporter = runpy.run_path(
        str(Path(__file__).resolve().parents[3] / "scripts/export_openapi.py")
    )
    schema = json.loads(exporter["export"]())
    assert len(schema["paths"]) == 8
    ids = []
    for path, operations in schema["paths"].items():
        assert set(operations) == {"get", "head", "options"}
        for method, operation in operations.items():
            ids.append(operation["operationId"])
            if "{analysis_id}" in path:
                assert any(
                    parameter["in"] == "path" and parameter["name"] == "analysis_id"
                    for parameter in operation["parameters"]
                )
            assert "422" not in operation["responses"]
            assert operation["security"] == (
                [] if path == "/health" else [{"Bearer": []}]
            )
            header_names = {
                parameter["name"].lower()
                for parameter in operation.get("parameters", [])
                if parameter["in"] == "header"
            }
            assert not header_names & {"accept", "content-type", "authorization"}
            if method in {"get", "head"}:
                assert {"accept-encoding", "if-match", "if-none-match"} <= header_names
                assert {
                    parameter["name"]
                    for parameter in operation.get("parameters", [])
                    if parameter["in"] == "query"
                } == QUERY_PARAMETERS.get(path, frozenset())
            if method == "get":
                assert "application/json" in operation["responses"]["200"]["content"]
            if method == "head":
                assert all(
                    "content" not in response
                    for response in operation["responses"].values()
                )
    assert len(set(ids)) == len(ids)
    financial = schema["components"]["schemas"]
    assert "macd_signal" in financial["TechnicalIndicators"]["properties"]
    assert "macd_signal_state" not in financial["TechnicalIndicators"]["properties"]
    assert "user_id" not in financial["AnalysisDetail"]["properties"]
    assert schema["components"]["responses"]["405"]["headers"]["Allow"]
    assert (
        "application/problem+json"
        in schema["components"]["responses"]["400"]["content"]
    )


def test_offline_export_is_independent_of_runtime_environment(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "cloud_run")
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setenv("DATABASE_POOL_SIZE", "999")
    exporter = runpy.run_path(
        str(Path(__file__).resolve().parents[3] / "scripts/export_openapi.py")
    )
    assert (
        json.loads(exporter["export"]())["info"]["title"] == "Momentum consultation API"
    )
