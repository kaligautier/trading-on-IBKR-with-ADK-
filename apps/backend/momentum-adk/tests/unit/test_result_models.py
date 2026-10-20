"""Financial persistence remains complete and isolated from ADK session metadata."""

from datetime import date
from uuid import uuid4

from sqlalchemy import UniqueConstraint, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.infrastructure import models

SECTIONS = {
    "technical_indicators": ("technical_indicators", False),
    "fundamentals": ("fundamentals", False),
    "sentiment": ("sentiment_results", False),
    "sentiment_items": ("sentiment_items", True),
    "news": ("news_results", False),
    "news_items": ("news_items", True),
    "research_plan": ("research_plans", False),
    "trader_proposal": ("trader_proposals", False),
    "portfolio_decision": ("portfolio_decisions", False),
    "debate_arguments": ("debate_arguments", True),
    "run_stats": ("run_stats", False),
}


def test_only_completed_result_tables_are_mapped():
    expected = {"analysis_results", *(table for table, _ in SECTIONS.values())}
    assert set(models.Base.metadata.tables) == {f"momentum.{name}" for name in expected}


def test_all_tables_and_foreign_keys_explicitly_target_momentum():
    for table in models.Base.metadata.sorted_tables:
        assert table.schema == "momentum"
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert f"CREATE TABLE momentum.{table.name}" in ddl
        for foreign_key in table.foreign_keys:
            assert foreign_key.target_fullname == "momentum.analysis_results.id"
            assert foreign_key.column.table is models.AnalysisResult.__table__


def test_every_financial_section_has_its_original_relationship():
    relationships = inspect(models.AnalysisResult).relationships
    assert set(relationships.keys()) == set(SECTIONS)
    for name, (table, multiple) in SECTIONS.items():
        relation = relationships[name]
        assert relation.mapper.local_table.name == table
        assert relation.uselist is multiple
        assert relation.back_populates == "result"


def test_correlation_is_required_and_survives_session_deletion():
    table = models.AnalysisResult.__table__
    for name, length in (("session_id", 128), ("invocation_id", 256), ("user_id", 128)):
        assert not table.c[name].nullable
        assert table.c[name].type.length == length
        # Results have a longer lifetime than resumable ADK sessions.
        assert not table.c[name].foreign_keys
    assert any(
        tuple(index.columns.keys()) == ("session_id", "invocation_id")
        for index in table.indexes
    )


def test_multiple_results_for_same_ticker_date_or_session_are_allowed():
    table = models.AnalysisResult.__table__
    assert not any(isinstance(c, UniqueConstraint) for c in table.constraints)
    assert all(not index.unique for index in table.indexes)
    shared = {
        "ticker": "AAPL",
        "analysis_date": date(2026, 1, 1),
        "session_id": str(uuid4()),
        "invocation_id": "invocation",
        "user_id": "requester",
        "llm_provider": "litellm",
        "deep_think_llm": "deep",
        "quick_think_llm": "quick",
    }
    first = models.AnalysisResult(id=uuid4(), **shared)
    second = models.AnalysisResult(id=uuid4(), **shared)
    assert first.id != second.id


def test_financial_relationships_can_be_populated_without_runtime_services():
    result = models.AnalysisResult()
    result.technical_indicators = models.TechnicalIndicators(close_price=123.5)
    result.news_items = [models.NewsItemRow(headline="Example")]
    result.portfolio_decision = models.PortfolioDecisionRow(rating="HOLD")
    result.run_stats = models.RunStats(tokens_in=2**33)
    assert result.technical_indicators.result is result
    assert result.news_items[0].result is result
    assert result.portfolio_decision.rating == "HOLD"
    assert result.run_stats.tokens_in == 2**33


def test_result_timestamps_use_aware_utc_defaults():
    assert models.utc_now().utcoffset().total_seconds() == 0
    for model in (models.AnalysisResult, models.RunStats):
        assert model.__table__.c.created_at.type.timezone
        assert model.__table__.c.created_at.default.arg(None).tzinfo is not None
