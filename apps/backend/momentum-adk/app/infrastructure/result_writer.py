"""Financial section writers ported from DeepCopy 38d0736.

Add execution correlation and retain market-cap units and zero-price targets.
The repository owns the transaction; writers never commit individual sections.
"""

from dataclasses import dataclass
from typing import ClassVar, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contracts import WorkflowExecution, WorkflowResult
from app.infrastructure.models import (
    AnalysisResult,
    DebateArgumentRow,
    Fundamentals,
    NewsItemRow,
    NewsResult,
    PortfolioDecisionRow,
    ResearchPlanRow,
    RunStats,
    SentimentItemRow,
    SentimentResult,
    TechnicalIndicators,
    TraderProposalRow,
)


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    """Models used to produce an analysis."""

    llm_provider: str
    deep_think_llm: str
    quick_think_llm: str


@dataclass(frozen=True, slots=True)
class AnalysisRecord:
    """Typed persistence input shared by all row writers."""

    result: WorkflowResult
    models: ModelMetadata


class ResultSectionWriter(Protocol):
    """Write one cohesive section of a completed analysis."""

    def write(self, parent: AnalysisResult, record: AnalysisRecord) -> None:
        """Add section rows to the current SQLAlchemy session."""


class PostgresResultWriter:
    """Write one typed workflow result without owning the transaction."""

    def __init__(self, model_metadata: ModelMetadata) -> None:
        self._model_metadata = model_metadata

    async def write(self, session: AsyncSession, execution: WorkflowExecution) -> None:
        for field, maximum in (
            ("user_id", 128),
            ("session_id", 128),
            ("invocation_id", 256),
        ):
            value = getattr(execution, field)
            if not value.strip() or len(value) > maximum:
                raise ValueError("Valid execution correlation is required")
        record = AnalysisRecord(execution.result, self._model_metadata)
        parent = self._parent(record, execution)
        session.add(parent)
        await session.flush()
        ResultSectionWriters.for_session(session).write(parent, record)

    @staticmethod
    def _parent(record: AnalysisRecord, execution: WorkflowExecution) -> AnalysisResult:
        result = record.result
        models = record.models
        return AnalysisResult(
            session_id=execution.session_id,
            invocation_id=execution.invocation_id,
            user_id=execution.user_id,
            ticker=result.ticker,
            analysis_date=result.analysis_date,
            llm_provider=models.llm_provider,
            deep_think_llm=models.deep_think_llm,
            quick_think_llm=models.quick_think_llm,
            next_analysis_date=result.next_analysis_date,
            next_analysis_desc=result.next_analysis_desc,
        )


class ResultSectionWriters:
    """First-class collection of flat-schema section writers."""

    def __init__(self, writers: tuple[ResultSectionWriter, ...]) -> None:
        self._writers = writers

    @classmethod
    def for_session(cls, session: AsyncSession) -> "ResultSectionWriters":
        return cls(
            (
                MarketSectionWriter(session),
                FundamentalsSectionWriter(session),
                SentimentAndNewsSectionWriter(session),
                DecisionSectionWriter(session),
                DebateAndStatisticsSectionWriter(session),
            )
        )

    def write(self, parent: AnalysisResult, record: AnalysisRecord) -> None:
        for writer in self._writers:
            writer.write(parent, record)


class IndicatorColumns:
    """Flatten structured indicator objects into SQLAlchemy column values."""

    INDICATORS: ClassVar[dict[str, str]] = {
        "close_price": "close_price",
        "sma_50": "sma_50",
        "sma_200": "sma_200",
        "ema_10": "ema_10",
        "rsi": "rsi",
        "macd": "macd",
        "macd_signal_line": "macd_signal_val",
        "macd_histogram": "macd_histogram",
        "boll_upper": "boll_upper",
        "boll_lower": "boll_lower",
        "atr": "atr",
        "vwma": "vwma",
        "mfi": "mfi",
    }

    def __init__(self, market: dict) -> None:
        self._market = market

    def values(self) -> dict:
        columns: dict = {}
        for source, target in self.INDICATORS.items():
            columns.update(self._indicator(source, target))
        return columns

    def _indicator(self, source: str, target: str) -> dict:
        indicator = self._market.get(source) or {}
        signal_column = self._signal_column(target)
        return {
            target: indicator.get("value"),
            signal_column: indicator.get("signal"),
            self._comment_column(target): indicator.get("interpretation"),
        }

    @staticmethod
    def _signal_column(target: str) -> str:
        if target == "close_price":
            return "close_signal"
        if target == "macd":
            return "macd_signal_state"
        return f"{target}_signal"

    @staticmethod
    def _comment_column(target: str) -> str:
        if target == "close_price":
            return "close_comment"
        return f"{target}_comment"


class MarketSectionWriter:
    """Write technical indicators and market assessments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def write(self, parent: AnalysisResult, record: AnalysisRecord) -> None:
        market = record.result.structured.get("Market Analyst")
        if not market:
            return
        self._session.add(
            TechnicalIndicators(
                result_id=parent.id,
                ticker=record.result.ticker,
                analysis_date=record.result.analysis_date,
                **IndicatorColumns(market).values(),
                trend_direction=market.get("trend_direction"),
                momentum_state=market.get("momentum_state"),
                volatility_regime=market.get("volatility_regime"),
                key_support=market.get("key_support"),
                key_resistance=market.get("key_resistance"),
                actionable_recommendation=market.get("actionable_recommendation"),
                summary_short=market.get("summary_short"),
                summary_long=market.get("summary_long"),
            )
        )


class FundamentalsSectionWriter:
    """Write flattened fundamental metrics."""

    METRICS: ClassVar[tuple[str, ...]] = (
        "market_cap",
        "pe_ratio",
        "forward_pe",
        "peg_ratio",
        "eps_ttm",
        "forward_eps",
        "revenue",
        "net_income",
        "profit_margin",
        "operating_margin",
        "roe",
        "roa",
        "debt_to_equity",
        "current_ratio",
        "total_cash",
        "free_cash_flow",
        "capex",
        "dividend_yield",
        "beta",
    )

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def write(self, parent: AnalysisResult, record: AnalysisRecord) -> None:
        fundamentals = record.result.structured.get("Fundamentals Analyst")
        if not fundamentals:
            return
        row = Fundamentals(
            result_id=parent.id,
            ticker=record.result.ticker,
            analysis_date=record.result.analysis_date,
        )
        for field_name in self.METRICS:
            self._apply_metric(row, field_name, fundamentals.get(field_name))
        self._apply_assessment(row, fundamentals)
        self._session.add(row)

    @staticmethod
    def _apply_metric(row: Fundamentals, field_name: str, metric: dict | None) -> None:
        if not metric:
            return
        if field_name == "market_cap":
            row.market_cap_unit = metric.get("unit")
        setattr(row, field_name, metric.get("value"))
        setattr(row, f"{field_name}_trend", metric.get("trend"))
        setattr(row, f"{field_name}_comment", metric.get("comment"))

    @staticmethod
    def _apply_assessment(row: Fundamentals, fundamentals: dict) -> None:
        row.financial_health = fundamentals.get("financial_health")
        row.growth_outlook = fundamentals.get("growth_outlook")
        row.valuation_assessment = fundamentals.get("valuation_assessment")
        row.summary_short = fundamentals.get("summary_short")
        row.summary_long = fundamentals.get("summary_long")


class SentimentAndNewsSectionWriter:
    """Write sentiment and news summaries with their item collections."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def write(self, parent: AnalysisResult, record: AnalysisRecord) -> None:
        self._write_sentiment(parent, record)
        self._write_news(parent, record)

    def _write_sentiment(self, parent: AnalysisResult, record: AnalysisRecord) -> None:
        sentiment = record.result.structured.get("Sentiment Analyst")
        if not sentiment:
            return
        common = self._common(parent, record)
        self._session.add(
            SentimentResult(
                **common,
                overall_sentiment=sentiment.get("overall_sentiment"),
                overall_signal=sentiment.get("overall_signal"),
                retail_sentiment=sentiment.get("retail_sentiment"),
                institutional_sentiment=sentiment.get("institutional_sentiment"),
                key_risk=sentiment.get("key_risk_from_sentiment"),
                key_catalyst=sentiment.get("key_catalyst_from_sentiment"),
                summary_short=sentiment.get("summary_short"),
                summary_long=sentiment.get("summary_long"),
            )
        )
        for item in sentiment.get("items", []):
            self._session.add(SentimentItemRow(**common, **item))

    def _write_news(self, parent: AnalysisResult, record: AnalysisRecord) -> None:
        news = record.result.structured.get("News Analyst")
        if not news:
            return
        common = self._common(parent, record)
        self._session.add(
            NewsResult(
                **common,
                overall_impact=news.get("overall_impact"),
                macro_environment=news.get("macro_environment"),
                sector_momentum=news.get("sector_momentum"),
                key_catalyst=news.get("key_catalyst"),
                key_risk=news.get("key_risk"),
                summary_short=news.get("summary_short"),
                summary_long=news.get("summary_long"),
            )
        )
        for item in news.get("items", []):
            self._session.add(NewsItemRow(**common, **item))

    @staticmethod
    def _common(parent: AnalysisResult, record: AnalysisRecord) -> dict:
        return {
            "result_id": parent.id,
            "ticker": record.result.ticker,
            "analysis_date": record.result.analysis_date,
        }


class DecisionSectionWriter:
    """Write research, trader, and portfolio decisions."""

    PORTFOLIO_FIELDS: ClassVar[tuple[str, ...]] = (
        "executive_summary",
        "investment_thesis",
        "price_target",
        "entry_price",
        "stop_loss",
        "position_size",
        "position_size_description",
        "time_horizon_months",
        "time_horizon_description",
        "risk_reward_ratio",
        "risk_reward_description",
    )

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def write(self, parent: AnalysisResult, record: AnalysisRecord) -> None:
        self._write_research(parent, record)
        self._write_trader(parent, record)
        self._write_portfolio(parent, record)

    def _write_research(self, parent: AnalysisResult, record: AnalysisRecord) -> None:
        research = record.result.structured.get("Research Manager")
        if not research:
            return
        self._session.add(
            ResearchPlanRow(
                **self._common(parent, record),
                recommendation=self._enum_value(research.get("recommendation")),
                rationale=research.get("rationale", ""),
                strategic_actions=research.get("strategic_actions", ""),
            )
        )

    def _write_trader(self, parent: AnalysisResult, record: AnalysisRecord) -> None:
        trader = record.result.structured.get("Trader")
        if not trader:
            return
        self._session.add(
            TraderProposalRow(
                **self._common(parent, record),
                action=self._enum_value(trader.get("action")),
                reasoning=trader.get("reasoning", ""),
                entry_price=trader.get("entry_price"),
                stop_loss=trader.get("stop_loss"),
                take_profit=trader.get("take_profit"),
                position_sizing=trader.get("position_sizing"),
                risk_reward_ratio=trader.get("risk_reward_ratio"),
            )
        )

    def _write_portfolio(self, parent: AnalysisResult, record: AnalysisRecord) -> None:
        portfolio = record.result.structured.get("Portfolio Manager")
        if not portfolio:
            return
        fields = {key: portfolio.get(key) for key in self.PORTFOLIO_FIELDS}
        self._session.add(
            PortfolioDecisionRow(
                **self._common(parent, record),
                **fields,
                rating=self._enum_value(portfolio.get("rating")),
            )
        )

    @staticmethod
    def _common(parent: AnalysisResult, record: AnalysisRecord) -> dict:
        return {
            "result_id": parent.id,
            "ticker": record.result.ticker,
            "analysis_date": record.result.analysis_date,
        }

    @staticmethod
    def _enum_value(value) -> str:
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)


class DebateAndStatisticsSectionWriter:
    """Write debate rounds and execution statistics."""

    DEBATES: ClassVar[dict[str, tuple[str, str]]] = {
        "Bull Researcher": ("investment", "bull"),
        "Bear Researcher": ("investment", "bear"),
        "Aggressive Analyst": ("risk", "aggressive"),
        "Conservative Analyst": ("risk", "conservative"),
        "Neutral Analyst": ("risk", "neutral"),
    }

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def write(self, parent: AnalysisResult, record: AnalysisRecord) -> None:
        for agent_name, debate_identity in self.DEBATES.items():
            self._write_debate(parent, record, agent_name, debate_identity)
        self._write_statistics(parent, record)

    def _write_debate(
        self,
        parent: AnalysisResult,
        record: AnalysisRecord,
        agent_name: str,
        debate_identity: tuple[str, str],
    ) -> None:
        rounds = record.result.structured.get(agent_name, [])
        normalized_rounds = [rounds] if isinstance(rounds, dict) else rounds
        for index, argument in enumerate(normalized_rounds, start=1):
            self._session.add(
                self._debate_row(parent, record, debate_identity, index, argument)
            )

    @staticmethod
    def _debate_row(
        parent: AnalysisResult,
        record: AnalysisRecord,
        debate_identity: tuple[str, str],
        round_number: int,
        argument: dict,
    ) -> DebateArgumentRow:
        debate_type, role = debate_identity
        return DebateArgumentRow(
            result_id=parent.id,
            ticker=record.result.ticker,
            analysis_date=record.result.analysis_date,
            debate_type=debate_type,
            role=role,
            round_number=round_number,
            thesis=argument.get("thesis"),
            conviction_level=argument.get("conviction_level"),
            stance=argument.get("stance"),
            target_price=(
                argument.get("target_price")
                if argument.get("target_price") is not None
                else argument.get("downside_target")
            ),
            recommended_entry=argument.get("recommended_entry"),
            recommended_position_size=argument.get("recommended_position_size"),
            key_data_point=argument.get("key_data_point"),
            argument_full=argument.get("argument_full"),
        )

    def _write_statistics(self, parent: AnalysisResult, record: AnalysisRecord) -> None:
        statistics = record.result.run_stats
        self._session.add(
            RunStats(
                result_id=parent.id,
                **statistics.model_dump(),
            )
        )
