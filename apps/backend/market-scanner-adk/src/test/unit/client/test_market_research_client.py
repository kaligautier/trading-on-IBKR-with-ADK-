"""Provider contracts: dated data and explicit, non-fatal gaps (AAA)."""

import json
from datetime import UTC, date, datetime
from unittest.mock import Mock

import pytest

from app.client.market_research_client import MarketResearchClient


async def should_filter_future_undated_and_unrelated_news():
    # Arrange
    search = Mock(
        return_value=[
            {
                "title": "Relevant",
                "providerPublishTime": 1791244800,
                "relatedTickers": ["^GSPC"],
            },
            {
                "title": "Future",
                "providerPublishTime": 1791417600,
                "relatedTickers": ["^GSPC"],
            },
            {"title": "Undated", "relatedTickers": ["^GSPC"]},
            {
                "title": "Unrelated",
                "providerPublishTime": 1791244800,
                "relatedTickers": ["OTHER"],
            },
        ]
    )
    client = MarketResearchClient(
        search=search, now=lambda: datetime(2026, 10, 7, tzinfo=UTC)
    )
    # Act
    result = await client.get_news("^GSPC", date(2026, 10, 6))
    # Assert
    assert [item["title"] for item in result["items"]] == ["Relevant"]
    assert result["status"] == "available"
    assert "sample" in result["coverage"]


async def should_return_a_missing_key_without_requesting_fred():
    # Arrange
    http = Mock()
    client = MarketResearchClient(http=http)
    # Act
    result = await client.get_macro_indicators("cpi", date(2026, 10, 6))
    # Assert
    assert result["status"] == "unavailable"
    assert result["reason"] == "FRED_API_KEY not configured"
    http.get_text.assert_not_called()


async def should_pin_fred_vintage_and_preserve_units_and_missing_values():
    # Arrange
    http = Mock()
    http.get_text.side_effect = [
        json.dumps(
            {"seriess": [{"title": "CPI", "units": "Index", "frequency": "Monthly"}]}
        ),
        json.dumps(
            {
                "observations": [
                    {"date": "2026-08-01", "value": "325.2"},
                    {"date": "2026-09-01", "value": "."},
                    {"date": "2026-11-01", "value": "999"},
                ]
            }
        ),
    ]
    client = MarketResearchClient(
        http=http,
        fred_api_key="private-test-key",
        now=lambda: datetime(2026, 10, 7, tzinfo=UTC),
    )
    # Act
    result = await client.get_macro_indicators("cpi", date(2026, 10, 6))
    # Assert
    assert result["items"] == [{"date": "2026-08-01", "value": 325.2}]
    assert result["units"] == "Index"
    assert result["vintage"] == "2026-10-06"
    assert all(
        "realtime_start=2026-10-06" in call.args[0]
        and "realtime_end=2026-10-06" in call.args[0]
        for call in http.get_text.call_args_list
    )
    assert "private-test-key" not in json.dumps(result)


async def should_withhold_live_odds_for_historical_scans():
    # Arrange
    http = Mock()
    client = MarketResearchClient(
        http=http, now=lambda: datetime(2026, 10, 7, tzinfo=UTC)
    )
    # Act
    result = await client.get_prediction_markets("Fed", date(2026, 10, 6))
    # Assert
    assert result["status"] == "withheld"
    http.get_text.assert_not_called()


async def should_return_only_open_future_markets_with_valid_probabilities():
    # Arrange
    market = {
        "question": "Fed cut?",
        "endDate": "2026-11-01T00:00:00Z",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.7", "0.3"]',
        "volumeNum": 1200,
    }
    http = Mock()
    http.get_text.return_value = json.dumps(
        {
            "events": [
                {
                    "markets": [
                        market,
                        {**market, "closed": True},
                        {**market, "outcomePrices": '["NaN", "1"]'},
                        {**market, "endDate": "invalid"},
                    ]
                }
            ]
        }
    )
    client = MarketResearchClient(
        http=http, now=lambda: datetime(2026, 10, 7, tzinfo=UTC)
    )
    # Act
    result = await client.get_prediction_markets("Fed", date(2026, 10, 7))
    # Assert
    assert len(result["items"]) == 1
    assert result["items"][0]["outcomes"] == {"Yes": 0.7, "No": 0.3}
    assert result["items"][0]["volume_usd"] == 1200
    assert "market-implied" in result["coverage"]


@pytest.mark.parametrize(
    "tool,args",
    [
        ("get_news", ("^GSPC",)),
        ("get_global_news", ()),
        ("get_macro_indicators", ("cpi",)),
        ("get_prediction_markets", ("Fed",)),
    ],
)
async def should_degrade_timeouts_without_leaking_provider_credentials(tool, args):
    # Arrange
    http, search = Mock(), Mock()
    http.get_text.side_effect = TimeoutError("secret-key-in-url")
    search.side_effect = TimeoutError("secret-key-in-url")
    client = MarketResearchClient(
        http=http,
        search=search,
        fred_api_key="secret-key-in-url",
        now=lambda: datetime(2026, 10, 7, tzinfo=UTC),
    )
    # Act
    result = await getattr(client, tool)(*args, date(2026, 10, 7))
    # Assert
    assert result["status"] == "unavailable"
    assert "secret-key" not in json.dumps(result)


@pytest.mark.parametrize(
    "tool,args",
    [
        ("get_news", ("^GSPC",)),
        ("get_global_news", ()),
        ("get_macro_indicators", ("cpi",)),
        ("get_prediction_markets", ("Fed",)),
    ],
)
async def should_distinguish_empty_samples_from_provider_failures(tool, args):
    # Arrange
    http = Mock()
    http.get_text.return_value = json.dumps(
        {"seriess": [{"title": "CPI"}], "observations": [], "events": []}
    )
    client = MarketResearchClient(
        http=http,
        search=lambda q, n: [],
        fred_api_key="test-key",
        now=lambda: datetime(2026, 10, 7, tzinfo=UTC),
    )
    # Act
    result = await getattr(client, tool)(*args, date(2026, 10, 7))
    # Assert
    assert result["status"] == "empty"
    assert result["items"] == []


async def should_reject_future_analysis_dates_before_fetching_news():
    # Arrange
    search = Mock()
    client = MarketResearchClient(
        search=search, now=lambda: datetime(2026, 10, 7, tzinfo=UTC)
    )
    # Act
    result = await client.get_global_news(date(2026, 10, 8))
    # Assert
    assert result["status"] == "unavailable"
    search.assert_not_called()


async def should_clamp_live_fred_vintage_to_chicagos_calendar_day():
    # Arrange
    http = Mock()
    http.get_text.return_value = json.dumps(
        {"seriess": [{"title": "CPI"}], "observations": []}
    )
    client = MarketResearchClient(
        http=http,
        fred_api_key="test-key",
        now=lambda: datetime(2026, 10, 7, 1, tzinfo=UTC),
    )
    # Act
    result = await client.get_macro_indicators("cpi", date(2026, 10, 7))
    # Assert
    assert result["vintage"] == "2026-10-06"
    assert all(
        "realtime_end=2026-10-06" in call.args[0]
        for call in http.get_text.call_args_list
    )


async def should_preserve_nested_news_dates_publishers_and_deduplicate_global_results():
    # Arrange
    article = {
        "content": {
            "title": "Policy update",
            "pubDate": "2026-10-07T00:30:00+02:00",
            "provider": {"displayName": "Institution"},
        }
    }
    client = MarketResearchClient(
        search=lambda q, n: [article, article],
        now=lambda: datetime(2026, 10, 7, tzinfo=UTC),
    )
    # Act
    result = await client.get_global_news(date(2026, 10, 6))
    # Assert
    assert len(result["items"]) == 1
    assert result["items"][0]["publisher"] == "Institution"
    assert result["items"][0]["published_at"] == "2026-10-06T22:30:00+00:00"
