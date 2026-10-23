"""The checker must fail when a writer column used by the API disappears."""

import runpy
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/check_storage_contract.py"


def test_projection_contract_and_detected_drift():
    checker = runpy.run_path(str(SCRIPT))
    source = checker["MODELS"].read_text()
    checker["check"](source)
    with pytest.raises(ValueError, match="Storage contract drift"):
        checker["check"](
            source.replace("macd_signal_state: Mapped", "renamed_signal: Mapped")
        )
