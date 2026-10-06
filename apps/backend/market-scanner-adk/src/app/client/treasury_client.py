"""Exact, dated US public debt from the Treasury's public API."""

import json
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from app.client.market_data_client import MarketDataClient
from app.client.public_data_http_client import PublicDataHttpClient
from app.dto.external.response.market_data_response_dto import (
    ClosingPrice,
    ClosingPriceHistory,
)
from app.models.calendar_horizon import CalendarHorizon

TREASURY_DEBT_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    "/v2/accounting/od/debt_to_penny"
)


class TreasuryClient(MarketDataClient):
    source_name = "U.S. Treasury"

    def __init__(self, http: PublicDataHttpClient | None = None) -> None:
        self._http = http or PublicDataHttpClient()

    def fetch_closing_prices(
        self, symbol: str, period: str, *, as_of: date | None = None
    ) -> ClosingPriceHistory:
        if symbol != "US_PUBLIC_DEBT" or period not in {"5y", "10y"}:
            raise ValueError("Unsupported Treasury series or history period")
        as_of = as_of or date.today()
        start = CalendarHorizon(period, years=int(period[:-1])).target_date(as_of)
        start -= timedelta(days=14)
        query = urlencode(
            {
                "fields": "record_date,tot_pub_debt_out_amt",
                "filter": f"record_date:gte:{start},record_date:lte:{as_of}",
                "sort": "-record_date",
                "page[size]": 10000,
            }
        )
        payload = json.loads(self._http.get_text(f"{TREASURY_DEBT_URL}?{query}"))
        if int(payload.get("meta", {}).get("total-pages", 1)) > 1:
            raise ValueError("Incomplete Treasury history")
        observations = []
        for row in payload["data"]:
            day = date.fromisoformat(row["record_date"])
            amount = Decimal(row["tot_pub_debt_out_amt"])
            if day > as_of or not amount.is_finite() or amount < 0:
                raise ValueError("Invalid debt observation")
            observations.append(ClosingPrice(day, amount))
        return ClosingPriceHistory(tuple(observations))
