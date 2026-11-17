"""Yahoo news restricted to an inclusive calendar window in UTC."""

from datetime import datetime, timedelta, timezone

import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from app.infrastructure.market_data.stockstats import yf_retry


def _extract_article_data(article: dict) -> dict:
    content = article.get("content") or article
    nested = bool(article.get("content"))
    timestamp = content.get("pubDate") if nested else article.get("providerPublishTime")
    try:
        pub_date = (
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if nested
            else datetime.fromtimestamp(timestamp, timezone.utc)
        )
        pub_date = (
            pub_date.replace(tzinfo=timezone.utc)
            if pub_date.tzinfo is None
            else pub_date.astimezone(timezone.utc)
        )
    except (ValueError, TypeError, AttributeError, OverflowError, OSError):
        pub_date = None
    url = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
    return {
        "title": content.get("title", "No title"),
        "summary": content.get("summary", ""),
        "publisher": (content.get("provider") or {}).get("displayName", "Unknown")
        if nested
        else article.get("publisher", "Unknown"),
        "link": url.get("url", "") if nested else article.get("link", ""),
        "pub_date": pub_date,
    }


def _window(articles, start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_date, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    ) + timedelta(days=1)
    for article in articles:
        data = _extract_article_data(article)
        # Unknown timestamps cannot establish historical availability.
        if data["pub_date"] is not None and start <= data["pub_date"] < end:
            yield data


def _render(articles):
    return "\n".join(
        f"### {a['title']} (source: {a['publisher']})\n{a['summary']}\nLink: {a['link']}\n"
        for a in articles
    )


def get_news_yfinance(ticker: str, start_date: str, end_date: str) -> str:
    """Return dated ticker news within both calendar bounds."""
    try:
        stock = yf.Ticker(ticker)
        articles = list(
            _window(yf_retry(lambda: stock.get_news(count=20)), start_date, end_date)
        )
        if not articles:
            return f"No news found for {ticker} between {start_date} and {end_date}"
        return (
            f"## {ticker} News, from {start_date} to {end_date}:\n\n{_render(articles)}"
        )
    except YFRateLimitError:
        raise
    except Exception as error:
        return f"Error fetching news for {ticker}: {error}"


def get_global_news_yfinance(
    curr_date: str, look_back_days: int = 7, limit: int = 10
) -> str:
    """Filter and deduplicate macro headlines before applying the result limit."""
    try:
        start = (
            datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days)
        ).strftime("%Y-%m-%d")
        articles, seen = [], set()
        for query in (
            "stock market economy",
            "Federal Reserve interest rates",
            "inflation economic outlook",
            "global markets trading",
        ):
            search = yf_retry(
                lambda q=query: yf.Search(
                    query=q, news_count=limit, enable_fuzzy_query=True
                )
            )
            for data in _window(search.news or [], start, curr_date):
                if data["title"] not in seen:
                    seen.add(data["title"])
                    articles.append(data)
            if len(articles) >= limit:
                break
        if not articles:
            return f"No global news found for {curr_date}"
        return f"## Global Market News, from {start} to {curr_date}:\n\n{_render(articles[:limit])}"
    except YFRateLimitError:
        raise
    except Exception as error:
        return f"Error fetching global news: {error}"
