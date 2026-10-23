"""Real transactions under the dedicated, INSERT/SELECT-only result login."""

from datetime import date
from uuid import uuid4

import asyncpg
import pytest
from google.adk.events import Event
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.contracts import RunStatistics, WorkflowExecution, WorkflowResult
from app.infrastructure.models import Base
from app.infrastructure.result_repository import PostgresResultRepository
from app.infrastructure.result_writer import (
    FundamentalsSectionWriter,
    IndicatorColumns,
    ModelMetadata,
    PostgresResultWriter,
)
from app.infrastructure.session_database import create_session_service


def complete_execution():
    structured = {
        "Market Analyst": {
            name: {"value": 12.5, "signal": "Bullish", "interpretation": "Synthetic"}
            for name in IndicatorColumns.INDICATORS
        },
        "Fundamentals Analyst": {
            name: {
                "value": 42.0,
                "unit": "USD",
                "trend": "stable",
                "comment": "Synthetic",
            }
            for name in FundamentalsSectionWriter.METRICS
        },
        "Sentiment Analyst": {
            "overall_sentiment": 0.5,
            "key_risk_from_sentiment": "Risk",
            "key_catalyst_from_sentiment": "Catalyst",
            "items": [
                {
                    "topic": "Synthetic topic",
                    "sentiment_score": 0.5,
                    "impact": "low",
                    "source_type": "social",
                    "comment": "Synthetic",
                }
            ],
        },
        "News Analyst": {
            "overall_impact": "positive",
            "items": [
                {
                    "category": "earnings",
                    "headline": "Synthetic headline",
                    "impact": "low",
                    "urgency": "low",
                    "comment": "Synthetic",
                }
            ],
        },
        "Research Manager": {
            "recommendation": "Buy",
            "rationale": "Synthetic",
            "strategic_actions": "Observe",
        },
        "Trader": {
            "action": "Buy",
            "reasoning": "Synthetic",
            "entry_price": 12.5,
            "position_sizing": "small",
        },
        "Portfolio Manager": {
            "rating": "Buy",
            "executive_summary": "Synthetic verification only",
            "investment_thesis": "Synthetic",
            "price_target": 15.0,
            "position_size": 2.0,
        },
    }
    for role in (
        "Bull Researcher",
        "Bear Researcher",
        "Aggressive Analyst",
        "Conservative Analyst",
        "Neutral Analyst",
    ):
        structured[role] = [
            {"thesis": "Synthetic", "downside_target": 8.0},
            {"target_price": 0.0},
        ]
    return WorkflowExecution(
        user_id="persistence-test",
        session_id=str(uuid4()),
        invocation_id=str(uuid4()),
        result=WorkflowResult(
            ticker="NVDA",
            analysis_date=date(2026, 1, 1),
            signal="Buy",
            final_decision="Synthetic verification only",
            reports={},
            structured=structured,
            next_analysis_date=date(2026, 1, 2),
            next_analysis_desc="Synthetic follow-up",
            run_stats=RunStatistics(
                agents_total=12,
                agents_completed=12,
                reports_total=4,
                reports_completed=4,
                tokens_in=2**33,
                duration_seconds=1.5,
            ),
        ),
    )


@pytest.fixture
async def persistence(domain_database):
    engine = create_async_engine(
        domain_database["results_runtime"].replace(
            "postgresql://", "postgresql+asyncpg://"
        ),
        pool_size=1,
        max_overflow=0,
        hide_parameters=True,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    writer = PostgresResultWriter(ModelMetadata("litellm", "deep", "quick"))
    try:
        yield factory, writer
    finally:
        await engine.dispose()


@pytest.mark.parametrize("trader_reasoning", ["Synthetic", None])
async def test_all_sections_commit_with_real_adk_correlation(
    persistence, domain_database, trader_reasoning
):
    factory, writer = persistence
    execution = complete_execution()
    execution.result.structured["Trader"]["reasoning"] = trader_reasoning
    service = await create_session_service(domain_database["sessions_runtime"])
    verifier = await asyncpg.connect(domain_database["admin"])
    try:
        session = await service.create_session(
            app_name="momentum",
            user_id=execution.user_id,
            session_id=execution.session_id,
        )
        await service.append_event(
            session, Event(author="analyst", invocation_id=execution.invocation_id)
        )
        await PostgresResultRepository(factory, writer).save(execution)
        parent = await verifier.fetchrow(
            "SELECT * FROM _analysis.analysis_results WHERE invocation_id=$1",
            execution.invocation_id,
        )
        assert (parent["session_id"], parent["user_id"]) == (
            execution.session_id,
            execution.user_id,
        )
        assert parent["next_analysis_date"] == date(2026, 1, 2)
        assert parent["created_at"].tzinfo is not None
        sections = {}
        for table in Base.metadata.sorted_tables:
            if table.name == "analysis_results":
                continue
            rows = await verifier.fetch(
                f"SELECT * FROM {table.fullname} WHERE result_id=$1", parent["id"]
            )
            assert len(rows) == (10 if table.name == "debate_arguments" else 1)
            sections[table.name] = rows
        market = sections["technical_indicators"][0]
        for target in IndicatorColumns.INDICATORS.values():
            assert market[target] == 12.5
            assert market[IndicatorColumns._signal_column(target)] == "Bullish"
            assert market[IndicatorColumns._comment_column(target)] == "Synthetic"
        fundamentals = sections["fundamentals"][0]
        for metric in FundamentalsSectionWriter.METRICS:
            assert fundamentals[metric] == 42.0
            assert fundamentals[f"{metric}_trend"] == "stable"
            assert fundamentals[f"{metric}_comment"] == "Synthetic"
        assert fundamentals["market_cap_unit"] == "USD"
        assert sections["sentiment_results"][0]["key_risk"] == "Risk"
        assert sections["sentiment_items"][0]["topic"] == "Synthetic topic"
        assert sections["news_items"][0]["headline"] == "Synthetic headline"
        assert sections["research_plans"][0]["strategic_actions"] == "Observe"
        assert sections["trader_proposals"][0]["entry_price"] == 12.5
        assert sections["trader_proposals"][0]["reasoning"] == (trader_reasoning or "")
        assert sections["portfolio_decisions"][0]["price_target"] == 15.0
        assert sections["run_stats"][0]["tokens_in"] == 2**33
        assert {
            (r["role"], r["round_number"], r["target_price"])
            for r in sections["debate_arguments"]
        } == {
            (role, number, target)
            for role in ("bull", "bear", "aggressive", "conservative", "neutral")
            for number, target in ((1, 8.0), (2, 0.0))
        }
        # Repeating the ticker/date and correlation is allowed, without deduplication.
        await PostgresResultRepository(factory, writer).save(execution)
        await service.delete_session(
            app_name="momentum",
            user_id=execution.user_id,
            session_id=execution.session_id,
        )
        assert (
            await verifier.fetchval(
                "SELECT count(*) FROM _analysis.analysis_results "
                "WHERE invocation_id=$1",
                execution.invocation_id,
            )
            == 2
        )
    finally:
        await service.close()
        await verifier.close()


@pytest.mark.parametrize("failure", ["mapping", "constraint", "after_flush"])
async def test_failed_section_rolls_back_entire_analysis(
    persistence, domain_database, failure
):
    factory, writer = persistence
    execution = complete_execution()
    if failure == "mapping":
        execution.result.structured["Fundamentals Analyst"] = ["invalid"]
    elif failure == "constraint":
        execution.result.structured["News Analyst"]["items"][0]["impact"] = "x" * 21

    class FailingAfterFlush:
        async def write(self, session, item):
            await writer.write(session, item)
            await session.flush()
            raise RuntimeError("Injected section failure after database writes")

    verifier = await asyncpg.connect(domain_database["admin"])
    try:
        before = {
            t.name: await verifier.fetchval(f"SELECT count(*) FROM {t.fullname}")
            for t in Base.metadata.sorted_tables
        }
        selected = FailingAfterFlush() if failure == "after_flush" else writer
        expected = {
            "mapping": AttributeError,
            "constraint": DBAPIError,
            "after_flush": RuntimeError,
        }[failure]
        with pytest.raises(expected):
            await PostgresResultRepository(factory, selected).save(execution)
        after = {
            t.name: await verifier.fetchval(f"SELECT count(*) FROM {t.fullname}")
            for t in Base.metadata.sorted_tables
        }
        assert after == before
        assert (
            await verifier.fetchval(
                "SELECT count(*) FROM _analysis.analysis_results "
                "WHERE invocation_id=$1",
                execution.invocation_id,
            )
            == 0
        )
        # A new transaction still succeeds after the failure.
        await PostgresResultRepository(factory, writer).save(complete_execution())
    finally:
        await verifier.close()


async def test_optional_contract_fields_flush_without_fabricated_scores(persistence):
    from app.domain.analysis import (
        NewsItem,
        PortfolioDecision,
        ResearchPlan,
        SentimentItem,
    )

    factory, writer = persistence
    execution = complete_execution()
    execution.result.structured.update(
        {
            "Sentiment Analyst": {"items": [SentimentItem().model_dump()]},
            "News Analyst": {"items": [NewsItem().model_dump()]},
            "Research Manager": ResearchPlan(recommendation="Hold").model_dump(
                mode="json"
            ),
            "Portfolio Manager": PortfolioDecision(rating="Hold").model_dump(
                mode="json"
            ),
        }
    )
    async with factory() as session:
        try:
            await writer.write(session, execution)
            await session.flush()
            score = await session.scalar(
                text(
                    "SELECT sentiment_score FROM _analysis.sentiment_items "
                    "WHERE result_id=(SELECT id FROM _analysis.analysis_results "
                    "WHERE invocation_id=:invocation)"
                ),
                {"invocation": execution.invocation_id},
            )
            assert score is None
        finally:
            await session.rollback()
