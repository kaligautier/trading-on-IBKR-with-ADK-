"""Synthetic qualitative reports, never real market research."""

from app.models.market_report import ASSET_FAMILIES


def analysis_payload(keys, horizon="1d"):
    keys = list(keys)
    return {
        "title": "Test observations",
        "summary": "Test observations are available. Their scope is limited.",
        "regime": "cautious",
        "horizon": horizon,
        "limitations": ["Synthetic data; no valuation is provided."],
        "watch_points": ["A reversal in the observed direction."],
        "themes": [
            {
                "family": family,
                "observation": "One-day family observation.",
                "interpretation": explanation(),
            }
            for family, members in ASSET_FAMILIES.items()
            if set(keys).intersection(members)
        ],
        "asset_insights": [
            {
                "asset_key": key,
                "horizon": horizon,
                "observation": "One-day observation.",
                "interpretation": explanation(),
            }
            for key in keys
        ],
    }


def explanation():
    return {
        "text": "No verified catalyst in this synthetic data.",
        "status": "unestablished",
        "source_ids": [],
    }


def unsourced_analysis_payload(keys, horizon="1d"):
    payload = analysis_payload(keys, horizon)
    for item in payload["themes"] + payload["asset_insights"]:
        item["interpretation"].pop("source_ids")
    return payload
