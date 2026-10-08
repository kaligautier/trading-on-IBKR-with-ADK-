"""Dated research data, adapted from TauricResearch/TradingAgents (Apache-2.0).

Modified for Scanner: JSON results, catalog symbols, bounded I/O, no URL/error
leaks, explicit gaps and stricter probability/date validation. See third_party/.
"""

import asyncio
import json
import math
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import yfinance as yf

from app.client.public_data_http_client import PublicDataHttpClient

SERIES = {
    "cpi": "CPIAUCSL",
    "core_pce": "PCEPILFE",
    "unemployment": "UNRATE",
    "payrolls": "PAYEMS",
    "gdp": "GDPC1",
    "fedfunds": "FEDFUNDS",
    "treasury_2y": "DGS2",
    "treasury_10y": "DGS10",
    "yield_curve": "T10Y2Y",
    "ecb_deposit_rate": "ECBDFR",
    "eurozone_hicp": "CP0000EZ19M086NEST",
}
GLOBAL_QUERIES = (
    "stock market",
    "Federal Reserve",
    "inflation",
    "economy",
    "ECB",
    "oil",
)


def _timestamp(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Undated timezone")
    return parsed.astimezone(UTC)


def _number(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Nonfinite provider number")
    return number


class MarketResearchClient:
    """Read-only optional vendors; no live-only data in historical requests."""

    def __init__(self, http=None, search=None, fred_api_key="", now=None):
        self.http = http or PublicDataHttpClient(timeout=8)
        self.search = search or self._search
        self.fred_api_key = fred_api_key
        self.now = now or (lambda: datetime.now(UTC))

    @staticmethod
    def _search(query, limit):
        return yf.Search(query, news_count=limit, timeout=8).news or []

    async def _json(self, base, params):
        # urllib does not log request URLs, unlike httpx INFO request logging.
        body = await asyncio.wait_for(
            asyncio.to_thread(self.http.get_text, base + "?" + urlencode(params)), 18
        )
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Invalid provider response")
        return data

    @staticmethod
    def _result(provider, as_of, items=None, **fields):
        items = items or []
        return {
            "provider": provider,
            "as_of": as_of.isoformat(),
            "status": "available" if items else "empty",
            "items": items,
            **fields,
        }

    def _valid_date(self, as_of):
        if as_of > self.now().date():
            raise ValueError("Future analysis date")

    async def _news(self, queries, as_of, symbol=None):
        self._valid_date(as_of)
        start = as_of - timedelta(days=7)
        items, seen, failures = [], set(), []
        for query in queries:
            articles = None
            for attempt in range(2):
                try:
                    articles = await asyncio.wait_for(
                        asyncio.to_thread(self.search, query, 20), 9
                    )
                    break
                except Exception as error:
                    if attempt:
                        failures.append(type(error).__name__)
            query_count = 0
            for article in articles or []:
                if not isinstance(article, dict):
                    continue
                content = article.get("content") or article
                if not isinstance(content, dict):
                    continue
                if symbol and symbol.upper() not in [
                    str(t).upper() for t in article.get("relatedTickers", [])
                ]:
                    continue
                try:
                    published = _timestamp(
                        content.get("pubDate") or article.get("providerPublishTime")
                    )
                except (ValueError, TypeError, OverflowError, OSError):
                    continue
                title = content.get("title") or ""
                if not title or title in seen or not start <= published.date() <= as_of:
                    continue
                provider = content.get("provider") or {}
                publisher = (
                    provider.get("displayName", "Unknown")
                    if isinstance(provider, dict)
                    else "Unknown"
                )
                publisher = content.get("publisher") or publisher
                seen.add(title)
                items.append(
                    {
                        "title": str(title)[:500],
                        "summary": str(content.get("summary") or "")[:1500],
                        "published_at": published.isoformat(),
                        "publisher": publisher,
                    }
                )
                query_count += 1
                if not symbol and query_count >= 4:
                    break
        result = self._result(
            "Yahoo Finance",
            as_of,
            sorted(items, key=lambda x: x["published_at"], reverse=True)[:20],
            window_start=start.isoformat(),
            coverage=(
                "Recent relevance sample; empty results do not establish "
                "absence of news or historical coverage."
            ),
        )
        if failures:
            result["gaps"] = failures
            if not items:
                result.update(status="unavailable", reason="News provider unavailable")
        return result

    async def get_news(self, symbol, as_of):
        try:
            return await self._news((symbol,), as_of, symbol=symbol)
        except Exception as error:
            return self._result(
                "Yahoo Finance",
                as_of,
                status="unavailable",
                reason=type(error).__name__,
            )

    async def get_global_news(self, as_of):
        try:
            return await self._news(GLOBAL_QUERIES, as_of)
        except Exception as error:
            return self._result(
                "Yahoo Finance",
                as_of,
                status="unavailable",
                reason=type(error).__name__,
            )

    async def get_macro_indicators(self, indicator, as_of):
        if not self.fred_api_key:
            return self._result(
                "FRED",
                as_of,
                status="unavailable",
                reason="FRED_API_KEY not configured",
            )
        if indicator not in SERIES:
            return self._result(
                "FRED",
                as_of,
                status="unavailable",
                reason="Unsupported indicator",
                supported=list(SERIES),
            )
        try:
            self._valid_date(as_of)
            vintage = min(
                as_of, self.now().astimezone(ZoneInfo("America/Chicago")).date()
            ).isoformat()
            params = {
                "series_id": SERIES[indicator],
                "api_key": self.fred_api_key,
                "file_type": "json",
                "realtime_start": vintage,
                "realtime_end": vintage,
            }
            meta = await self._json("https://api.stlouisfed.org/fred/series", params)
            info = (meta.get("seriess") or [{}])[0]
            start = (as_of - timedelta(days=400)).isoformat()
            data = await self._json(
                "https://api.stlouisfed.org/fred/series/observations",
                {
                    **params,
                    "observation_start": start,
                    "observation_end": as_of.isoformat(),
                    "sort_order": "asc",
                },
            )
            items = []
            for item in data.get("observations", []):
                try:
                    observed = date.fromisoformat(item["date"])
                    value = _number(item["value"])
                except (ValueError, TypeError, KeyError):
                    continue
                if start <= observed.isoformat() <= as_of.isoformat():
                    items.append({"date": observed.isoformat(), "value": value})
            return self._result(
                "FRED",
                as_of,
                sorted(items, key=lambda x: x["date"])[-14:],
                series_id=SERIES[indicator],
                title=info.get("title", SERIES[indicator]),
                units=info.get("units", "unknown"),
                frequency=info.get("frequency", "unknown"),
                vintage=vintage,
                coverage=(
                    "Point-in-time vintage. Index levels are not inflation rates; "
                    "monthly observations are not release dates."
                ),
            )
        except Exception as error:
            return self._result(
                "FRED", as_of, status="unavailable", reason=type(error).__name__
            )

    async def get_prediction_markets(self, topic, as_of):
        if as_of != self.now().date():
            return self._result(
                "Polymarket",
                as_of,
                status="withheld",
                reason="Only live odds available; no historical vintage",
            )
        try:
            data = await self._json(
                "https://gamma-api.polymarket.com/public-search",
                {"q": topic[:120], "limit_per_type": 20},
            )
            items = []
            for event in data.get("events", []):
                for market in event.get("markets", []):
                    if market.get("closed") or market.get("active") is False:
                        continue
                    try:
                        end = _timestamp(market.get("endDate"))
                        outcomes = market.get("outcomes") or []
                        prices = market.get("outcomePrices") or []
                        outcomes = (
                            json.loads(outcomes)
                            if isinstance(outcomes, str)
                            else outcomes
                        )
                        prices = (
                            json.loads(prices) if isinstance(prices, str) else prices
                        )
                        probabilities = [_number(p) for p in prices]
                        volume = _number(market.get("volumeNum") or 0)
                        if (
                            end <= self.now()
                            or len(outcomes) != len(prices)
                            or not outcomes
                            or volume < 0
                        ):
                            continue
                        if (
                            any(p < 0 or p > 1 for p in probabilities)
                            or abs(sum(probabilities) - 1) > 0.05
                        ):
                            continue
                        items.append(
                            {
                                "question": str(market.get("question") or "")[:500],
                                "outcomes": dict(
                                    zip(outcomes, probabilities, strict=True)
                                ),
                                "volume_usd": volume,
                                "resolves_at": end.isoformat(),
                            }
                        )
                    except (ValueError, TypeError, KeyError):
                        continue
            return self._result(
                "Polymarket",
                as_of,
                sorted(items, key=lambda x: x["volume_usd"], reverse=True)[:6],
                retrieved_at=self.now().isoformat(),
                coverage=(
                    "Live market-implied probabilities, not facts or guaranteed "
                    "outcomes. "
                    "Volume does not establish accuracy or liquidity."
                ),
            )
        except Exception as error:
            return self._result(
                "Polymarket", as_of, status="unavailable", reason=type(error).__name__
            )
