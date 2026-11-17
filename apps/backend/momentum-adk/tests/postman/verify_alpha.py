"""Run the real requests client against the local Postman simulation."""

import json
import os
from datetime import datetime, timezone

from app.infrastructure.market_data.alpha_vantage import (
    common,
    fundamentals,
    indicator,
    news,
)

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
for name in (
    "close_50_sma",
    "close_200_sma",
    "close_10_ema",
    "macd",
    "macds",
    "macdh",
    "rsi",
    "boll",
    "boll_ub",
    "boll_lb",
    "atr",
):
    result = indicator.get_indicator("AAPL", name, "2026-10-23", 2)
    assert "2026-10-21: 42\n2026-10-23: 42\n" in result
    assert "2026-10-20" not in result and "2026-10-24" not in result
print("14 real HTTP requests passed against synthetic Alpha Vantage fixtures")
