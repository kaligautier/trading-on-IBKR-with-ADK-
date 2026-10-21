"""Stable workflow result construction and report rendering."""

from app.components.callbacks.statistics import MomentumStatistics
from app.domain.analysis import (
    render_fundamentals_analysis,
    render_market_analysis,
    render_news_analysis,
    render_pm_decision,
    render_sentiment_analysis,
)
from app.domain.contracts import WorkflowResult
from app.domain.rating import parse_rating
from app.domain.state import (
    AnalystReports,
    NextAnalysisRecommendation,
    PortfolioOutcome,
)


class WorkflowResultBuilder:
    """Build the public result contract from the terminal workflow state."""

    def __init__(self, statistics: MomentumStatistics) -> None:
        self._statistics = statistics

    def build(
        self,
        outcome: PortfolioOutcome,
        next_run: NextAnalysisRecommendation,
    ) -> WorkflowResult:
        reports = outcome.risk.trader.research.reports
        decision = outcome.decision
        return WorkflowResult(
            ticker=reports.request.ticker,
            analysis_date=reports.request.analysis_date,
            signal=parse_rating(render_pm_decision(decision)),
            final_decision=render_pm_decision(decision),
            structured=StructuredResultBuilder(outcome).build(),
            reports=ReportBuilder(reports, outcome).build(),
            next_analysis_date=next_run.analysis_date,
            next_analysis_desc=next_run.description,
            run_stats=self._statistics.snapshot(),
            memory_reflections=reports.memory_reflections,
        )


class StructuredResultBuilder:
    """Map typed workflow state to the existing persistence contract."""

    def __init__(self, outcome: PortfolioOutcome) -> None:
        self._outcome = outcome

    def build(self) -> dict:
        research = self._outcome.risk.trader.research
        reports = research.reports
        risk = self._outcome.risk
        return {
            "Market Analyst": self._dump(reports.market),
            "Sentiment Analyst": self._dump(reports.social),
            "News Analyst": self._dump(reports.news),
            "Fundamentals Analyst": self._dump(reports.fundamentals),
            "Bull Researcher": [self._dump(item) for item in research.bull_arguments],
            "Bear Researcher": [self._dump(item) for item in research.bear_arguments],
            "Research Manager": self._dump(research.plan),
            "Trader": self._dump(risk.trader.proposal),
            "Aggressive Analyst": [
                self._dump(item) for item in risk.aggressive_arguments
            ],
            "Conservative Analyst": [
                self._dump(item) for item in risk.conservative_arguments
            ],
            "Neutral Analyst": [self._dump(item) for item in risk.neutral_arguments],
            "Portfolio Manager": self._dump(self._outcome.decision),
        }

    @staticmethod
    def _dump(value):
        if value is None:
            return None
        return value.model_dump(mode="json")


class ReportBuilder:
    """Render human-readable reports from typed agent outputs."""

    def __init__(self, reports: AnalystReports, outcome: PortfolioOutcome) -> None:
        self._reports = reports
        self._outcome = outcome

    def build(self) -> dict[str, str]:
        return {
            "market_report": self._render(
                self._reports.market,
                render_market_analysis,
            ),
            "sentiment_report": self._render(
                self._reports.social,
                render_sentiment_analysis,
            ),
            "news_report": self._render(self._reports.news, render_news_analysis),
            "fundamentals_report": self._render(
                self._reports.fundamentals,
                render_fundamentals_analysis,
            ),
            "final_trade_decision": render_pm_decision(self._outcome.decision),
        }

    @staticmethod
    def _render(value, renderer) -> str:
        if value is None:
            return ""
        return renderer(value)
