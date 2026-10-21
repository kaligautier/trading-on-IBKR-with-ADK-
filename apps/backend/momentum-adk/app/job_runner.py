"""Run one real Momentum workflow and commit its correlated result."""

import asyncio
import json
import logging
import os

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config.llm import create_model
from app.config.rate_limit import ModelRequestGate
from app.config.settings import Settings
from app.config.storage import MomentumStorage
from app.domain.contracts import AnalysisRequest
from app.infrastructure.memory.log import MemoryLogConfiguration, TradingMemoryLog
from app.infrastructure.result_repository import PostgresResultRepository
from app.infrastructure.result_writer import ModelMetadata, PostgresResultWriter
from app.services.execution import MomentumExecutionService
from app.services.memory import MarketOutcomeResolver, TradingMemoryService
from app.services.runtime import MomentumRuntimeFactory


def database_address(value: str):
    address = make_url(value)
    if address.drivername not in {"postgres", "postgresql", "postgresql+asyncpg"}:
        raise ValueError("PostgreSQL is required")
    if address.database != "momentum":
        raise ValueError("The dedicated momentum database is required")
    address = address.set(drivername="postgresql+asyncpg")
    if "sslmode" in address.query:
        mode = address.query["sslmode"]
        address = address.difference_update_query(["sslmode"])
        address = address.update_query_dict({"ssl": mode})
    return address


async def execute(request: AnalysisRequest):
    config = Settings()
    session_url = os.environ["MOMENTUM_SESSION_DATABASE_URL"]
    database_address(session_url)
    result_url = database_address(os.environ["MOMENTUM_RESULT_DATABASE_URL"])
    gate = ModelRequestGate()
    models = [
        create_model(config, config.MOMENTUM_QUICK_MODEL, gate),
        create_model(config, config.MOMENTUM_DEEP_MODEL, gate),
    ]
    runtime = None
    database = create_async_engine(
        result_url,
        pool_size=1,
        max_overflow=0,
        pool_timeout=5,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "timeout": 10,
            "server_settings": {
                "search_path": "_analysis, pg_catalog",
                "statement_timeout": "30000",
                "idle_in_transaction_session_timeout": "30000",
            },
        },
    )
    try:
        runtime = await MomentumRuntimeFactory(*models, session_url).create()
        storage = MomentumStorage.from_environment()
        memory = TradingMemoryService(
            TradingMemoryLog(MemoryLogConfiguration(storage.memory_log_path)),
            MarketOutcomeResolver(),
        )
        execution = await MomentumExecutionService(runtime.engine, memory).execute(
            request
        )
        writer = PostgresResultWriter(
            ModelMetadata(
                "litellm",
                config.MOMENTUM_DEEP_MODEL,
                config.MOMENTUM_QUICK_MODEL,
            )
        )
        await PostgresResultRepository(
            async_sessionmaker(database, expire_on_commit=False),
            writer,
        ).save(execution)
        memory.complete(request, execution.result)
        print(
            json.dumps(
                {
                    "event": "momentum_completed",
                    "ticker": request.ticker,
                    "session_id": execution.session_id,
                    "invocation_id": execution.invocation_id,
                    "signal": execution.result.signal,
                    "run_stats": execution.result.run_stats.model_dump(mode="json"),
                }
            ),
            flush=True,
        )
        return execution
    finally:
        if runtime is not None:
            await runtime.session_service.close()
        await database.dispose()
        for model in models:
            if "api_client" in model.__dict__:
                await model.api_client.aio.aclose()
                model.api_client.close()


def main():
    logging.basicConfig(level=logging.WARNING)
    try:
        request = AnalysisRequest.model_validate_json(os.environ["TA_ANALYSIS_REQUEST"])
        print(
            json.dumps(
                {
                    "event": "momentum_started",
                    "ticker": request.ticker,
                    "session_id": str(request.session_id),
                }
            ),
            flush=True,
        )
        asyncio.run(execute(request))
        return 0
    except Exception as error:
        # URLs, model prompts and upstream response bodies never enter this log.
        print(
            json.dumps(
                {"event": "momentum_failed", "error_type": type(error).__name__}
            ),
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
