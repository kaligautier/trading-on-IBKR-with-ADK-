"""Independently verify a completed result with the read/insert runtime login."""

import asyncio
import json
import os
import sys

import asyncpg

from app.infrastructure.models import Base


async def verify(session_id):
    connection = await asyncpg.connect(os.environ["MOMENTUM_RESULT_DATABASE_URL"])
    try:
        result = await connection.fetchrow(
            "SELECT id, ticker, invocation_id, llm_provider, created_at "
            "FROM _analysis.analysis_results WHERE session_id=$1 "
            "ORDER BY created_at DESC LIMIT 1",
            session_id,
        )
        if result is None:
            raise RuntimeError("No committed analysis for this session")
        assert result["llm_provider"] == "litellm"
        counts = {}
        for table in Base.metadata.sorted_tables:
            if table.name == "analysis_results":
                continue
            counts[table.name] = await connection.fetchval(
                f"SELECT count(*) FROM {table.fullname} WHERE result_id=$1",
                result["id"],
            )
        for name in (
            "research_plans",
            "trader_proposals",
            "portfolio_decisions",
            "run_stats",
        ):
            assert counts[name] == 1
        stats = dict(
            await connection.fetchrow(
                "SELECT llm_calls, tool_calls, tokens_in, tokens_out, duration_seconds "
                "FROM _analysis.run_stats WHERE result_id=$1",
                result["id"],
            )
        )
        assert stats["llm_calls"] > 0 and stats["tokens_out"] > 0
        print(
            json.dumps(
                {"result": dict(result), "counts": counts, "stats": stats},
                default=str,
                indent=2,
            )
        )
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(verify(sys.argv[1]))
