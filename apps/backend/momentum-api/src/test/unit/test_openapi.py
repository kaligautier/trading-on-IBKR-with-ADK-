"""Published methods, error statuses, validators and output aliases agree with HTTP."""

import json
import runpy
from pathlib import Path


def test_openapi_policy_and_financial_shapes():
    exporter = runpy.run_path(
        str(Path(__file__).resolve().parents[3] / "scripts/export_openapi.py")
    )
    schema = json.loads(exporter["export"]())
    assert len(schema["paths"]) == 7
    ids = []
    for path, operations in schema["paths"].items():
        assert set(operations) == {"get", "head", "options"}
        for method, operation in operations.items():
            ids.append(operation["operationId"])
            assert "422" not in operation["responses"]
            assert operation["security"] == (
                [] if path == "/health" else [{"Bearer": []}]
            )
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
