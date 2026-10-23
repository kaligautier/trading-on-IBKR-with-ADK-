"""Every legacy public financial field round-trips actual writer-shaped SQL rows."""

from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from app.domain.analyses.errors import InvalidStoredAnalysisError
from app.domain.analyses.search import AnalysisSearchParams
from app.presentation.mappers import detail_to_dto, page_to_dto

from .conftest import seed
from .financial_fixture import FIELDS, SUMMARY_FIELDS

TABLES = {
    "technical_indicators": "technical_indicators",
    "fundamentals": "fundamentals",
    "sentiment": "sentiment_results",
    "sentiment_items": "sentiment_items",
    "news": "news_results",
    "news_items": "news_items",
    "research_plan": "research_plans",
    "trader_proposal": "trader_proposals",
    "portfolio_decision": "portfolio_decisions",
    "debate_arguments": "debate_arguments",
    "run_stats": "run_stats",
}
ALIASES = {
    "macd_signal": "macd_signal_state",
    "score": "sentiment_score",
    "round": "round_number",
    "conviction": "conviction_level",
}


@pytest.mark.parametrize("nulls", [False, True])
async def test_complete_projection_from_independent_legacy_snapshot(
    admin, service, nulls
):
    await seed(admin)
    await admin.execute(
        "UPDATE _analysis.analysis_results SET next_analysis_date=$1, "
        "next_analysis_desc=$2",
        None if nulls else date(2026, 10, 25),
        None if nulls else "synthetic follow-up",
    )
    reader, _ = service
    expected = {}
    for table_index, (section, table) in enumerate(TABLES.items(), start=1):
        columns = await admin.fetch(
            """SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema='_analysis' AND table_name=$1
            ORDER BY ordinal_position""",
            table,
        )
        values = {}
        for index, column in enumerate(columns, start=1):
            name = column["column_name"]
            value = fixture_value(column, table_index, index)
            values[name] = None if nulls and column["is_nullable"] == "YES" else value
        names = ",".join(values)
        placeholders = ",".join(f"${index}" for index in range(1, len(values) + 1))
        statement = f"INSERT INTO _analysis.{table} ({names}) VALUES ({placeholders})"  # noqa: S608 -- fixed TABLES
        await admin.execute(statement, *values.values())
        expected[section] = {
            name: values[ALIASES.get(name, name)] for name in FIELDS[section]
        }
    expected["sentiment"]["items"] = [expected.pop("sentiment_items")]
    expected["news"]["items"] = [expected.pop("news_items")]
    expected["debate_arguments"] = [expected["debate_arguments"]]
    result = detail_to_dto(await reader.get(UUID(int=1))).model_dump(mode="json")
    for section, value in expected.items():
        assert result[section] == value, section
    assert result["created_at"] == "2026-10-22T12:00:00Z"
    assert result["id"] == str(UUID(int=1)) and result["ticker"] == "T000"
    assert result["llm_provider"] == "test-provider"
    assert result["deep_think_llm"] == "test-deep"
    assert result["quick_think_llm"] == "test-quick"
    assert result["next_analysis_date"] == (None if nulls else "2026-10-25")
    assert result["next_analysis_desc"] == (None if nulls else "synthetic follow-up")
    assert not {"session_id", "invocation_id", "user_id"} & result.keys()
    summarized = page_to_dto(
        await reader.list(
            AnalysisSearchParams.from_parameters("history", None, None, 20, "")
        )
    ).items[0]
    for field, (section, source) in SUMMARY_FIELDS.items():
        assert getattr(summarized, field) == expected[section][source], field
    assert summarized.trader_entry == expected["trader_proposal"]["entry_price"]
    assert summarized.entry_price == expected["portfolio_decision"]["entry_price"]
    assert summarized.rsi == expected["technical_indicators"]["rsi"]
    assert summarized.pe_ratio == expected["fundamentals"]["pe_ratio"]


async def test_invalid_stored_values_and_singleton_duplicates(admin, service):
    await seed(admin)
    reader, engine = service
    await admin.execute(
        """INSERT INTO _analysis.technical_indicators
        (id,result_id,ticker,analysis_date,rsi)
        VALUES($1,$1,'T000','2026-10-22','NaN')""",
        UUID(int=1),
    )
    for operation in (
        lambda: reader.get(UUID(int=1)),
        lambda: reader.list(
            AnalysisSearchParams.from_parameters("history", None, None, 20, "")
        ),
    ):
        with pytest.raises(InvalidStoredAnalysisError):
            await operation()
    await admin.execute("""UPDATE _analysis.technical_indicators SET rsi=5;
        INSERT INTO _analysis.technical_indicators(id,result_id,ticker,analysis_date)
        SELECT '00000000-0000-0000-0000-000000000002',result_id,ticker,analysis_date
        FROM _analysis.technical_indicators""")
    with pytest.raises(InvalidStoredAnalysisError):
        await reader.get(UUID(int=1))
    assert engine.pool.checkedout() == 0


def fixture_value(column, table_index, index):
    name, kind = column["column_name"], column["data_type"]
    if name == "id":
        value = UUID(int=table_index + 1)
    elif name == "result_id":
        value = UUID(int=1)
    elif kind == "date":
        value = date(2026, 10, 22)
    elif kind == "timestamp with time zone":
        value = datetime(2026, 10, 22, tzinfo=UTC)
    elif kind in {"double precision", "real"}:
        value = table_index * 100 + index + 0.25
    elif kind in {"integer", "bigint"}:
        value = index
    else:
        value = f"v{index}"
    return value
