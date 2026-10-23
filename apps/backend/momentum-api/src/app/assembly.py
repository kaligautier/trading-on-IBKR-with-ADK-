"""Allowlisted response assembly from fully loaded, schema-qualified result rows."""

from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.dto import AnalysisDetail, AnalysisHeader, AnalysisSummary
from app.sections import (
    DebateArgument,
    Fundamentals,
    News,
    NewsItem,
    PortfolioDecision,
    ResearchPlan,
    RunStats,
    Sentiment,
    SentimentItem,
    TechnicalIndicators,
    TraderProposal,
)

Row = Mapping[str, object]
SECTION_MODELS: dict[str, type[BaseModel]] = {
    "technical_indicators": TechnicalIndicators,
    "fundamentals": Fundamentals,
    "sentiment_results": Sentiment,
    "sentiment_items": SentimentItem,
    "news_results": News,
    "news_items": NewsItem,
    "research_plans": ResearchPlan,
    "trader_proposals": TraderProposal,
    "portfolio_decisions": PortfolioDecision,
    "debate_arguments": DebateArgument,
    "run_stats": RunStats,
}


class InvalidStoredAnalysisError(ValueError):
    """Persisted data cannot be represented by the public contract."""


@dataclass(frozen=True, slots=True)
class StoredAnalysis:
    header: Row
    sections: Mapping[str, list[Row]]


def projection(model: type[BaseModel], row: Row) -> dict[str, object]:
    return {
        name: row[column]
        for name, field in model.model_fields.items()
        if isinstance(column := field.validation_alias or name, str) and column in row
    }


def single(stored: StoredAnalysis, table: str) -> Row | None:
    rows = stored.sections.get(table, [])
    if len(rows) > 1:
        raise InvalidStoredAnalysisError("Duplicate single-valued financial section")
    return rows[0] if rows else None


def section[Model: BaseModel](
    stored: StoredAnalysis, table: str, model: type[Model]
) -> Model | None:
    row = single(stored, table)
    return model.model_validate(projection(model, row)) if row is not None else None


def items[Model: BaseModel](
    stored: StoredAnalysis, table: str, model: type[Model]
) -> list[Model]:
    rows = stored.sections.get(table, [])
    if table == "debate_arguments":
        rows = sorted(
            rows,
            key=lambda r: (
                str(r.get("debate_type", "")),
                int(str(r.get("round_number", 0))),
                str(r.get("role", "")),
                str(r.get("id", "")),
            ),
        )
    else:
        rows = sorted(rows, key=lambda r: str(r.get("id", "")))
    return [model.model_validate(projection(model, row)) for row in rows]


def detail(stored: StoredAnalysis) -> AnalysisDetail:
    try:
        sentiment = section(stored, "sentiment_results", Sentiment)
        if sentiment is not None:
            sentiment = sentiment.model_copy(
                update={"items": items(stored, "sentiment_items", SentimentItem)}
            )
        news = section(stored, "news_results", News)
        if news is not None:
            news = news.model_copy(
                update={"items": items(stored, "news_items", NewsItem)}
            )
        return AnalysisDetail.model_validate(
            {
                **projection(AnalysisDetail, stored.header),
                "technical_indicators": section(
                    stored, "technical_indicators", TechnicalIndicators
                ),
                "fundamentals": section(stored, "fundamentals", Fundamentals),
                "sentiment": sentiment,
                "news": news,
                "research_plan": section(stored, "research_plans", ResearchPlan),
                "trader_proposal": section(stored, "trader_proposals", TraderProposal),
                "portfolio_decision": section(
                    stored, "portfolio_decisions", PortfolioDecision
                ),
                "debate_arguments": items(stored, "debate_arguments", DebateArgument),
                "run_stats": section(stored, "run_stats", RunStats),
            }
        )
    except (ValidationError, TypeError, ValueError):
        raise InvalidStoredAnalysisError("Stored analysis is invalid") from None


def summary(stored: StoredAnalysis) -> AnalysisSummary:
    data = projection(AnalysisHeader, stored.header)
    # These source tables have no overlapping public summary fields. Header fields
    # are selected separately so child IDs/dates never replace the result identity.
    financial_fields = set(AnalysisSummary.model_fields) - set(
        AnalysisHeader.model_fields
    )
    for table in ("technical_indicators", "fundamentals", "portfolio_decisions"):
        row = single(stored, table)
        if row is not None:
            data.update(
                {key: value for key, value in row.items() if key in financial_fields}
            )
    trader = single(stored, "trader_proposals")
    if trader is not None:
        for target, source in {
            "trader_action": "action",
            "trader_entry": "entry_price",
            "trader_stop": "stop_loss",
            "trader_take_profit": "take_profit",
        }.items():
            data[target] = trader.get(source)
    try:
        return AnalysisSummary.model_validate(data)
    except ValidationError:
        raise InvalidStoredAnalysisError("Stored analysis summary is invalid") from None
