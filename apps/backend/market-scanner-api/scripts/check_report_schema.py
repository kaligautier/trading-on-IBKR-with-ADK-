"""Run using the writer environment and PYTHONPATH to detect contract drift."""

import json
from pathlib import Path

from app.models.market_regime import MarketRegime

path = Path(__file__).resolve().parents[1] / "src/app/schemas/report-v3.json"
assert json.loads(path.read_text()) == MarketRegime.model_json_schema(
    mode="serialization"
), "Reader schema is stale: review the writer contract and regenerate report-v3.json"
print("Reader JSON schema matches the writer serialization contract")
