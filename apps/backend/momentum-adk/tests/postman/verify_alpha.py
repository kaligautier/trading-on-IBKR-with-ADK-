"""Run the real requests client against the local Postman simulation."""

import json
import os
from datetime import datetime, timezone

from app.infrastructure.market_data.alpha_vantage import common, fundamentals, news

common.API_BASE_URL = "http://127.0.0.1:4909/alpha/query"
os.environ["ALPHA_VANTAGE_API_KEY"] = "synthetic-only"
for result in (
    news.get_news("AAPL", "2026-10-20", "2026-10-20"),
    news.get_global_news("2026-10-20"),
):
    assert json.loads(result)["feed"][0]["title"] == "Evening headline"
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
result = fundamentals.get_balance_sheet("AAPL", curr_date=today)
assert "2000-01-01" in result and "9999-01-01" not in result
print("3 real HTTP requests passed against synthetic Alpha Vantage fixtures")
