"""Cloud Run Job entry point: execute ADK directly and exit after persistence."""

import asyncio
import logging
import os
from contextlib import aclosing
from uuid import uuid4

from google.adk.apps import App
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.components.agents.market_scanner import root_agent
from app.config.constants import MARKET_SCANNER, PERSIST_MARKET_SCAN
from app.config.settings import settings
from app.models.step_04_market_data import MarketData
from app.services.database import close_database
from app.utils.error import AppError, LiteLLMError
from app.utils.logger import config_logger

logger = logging.getLogger(__name__)


async def run_scan() -> dict[str, str | int]:
    """Use a fresh in-memory session; retain the business report in PostgreSQL."""
    if not settings.DATABASE_URL:
        raise RuntimeError("Database persistence is not configured")
    session_id = os.getenv("CLOUD_RUN_EXECUTION") or str(uuid4())
    marker = f"scheduled:{session_id}"
    report = None
    async with Runner(
        app=App(name=MARKET_SCANNER, root_agent=root_agent),
        session_service=InMemorySessionService(),
    ) as runner:
        await runner.session_service.create_session(
            app_name=MARKET_SCANNER,
            user_id="scheduler",
            session_id=session_id,
            state={"session_id": marker},
        )
        async with aclosing(
            runner.run_async(
                user_id="scheduler",
                session_id=session_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text="Run the complete daily market scan.")],
                ),
            )
        ) as events:
            async for event in events:
                if event.error_code:
                    if event.error_code == LiteLLMError.__name__:
                        raise LiteLLMError()
                    raise RuntimeError("ADK workflow failed")
                if event.node_name == PERSIST_MARKET_SCAN and event.output:
                    report = MarketData.model_validate(event.output).market_regime
    if report is None or not report.assets:
        raise RuntimeError("Workflow ended without a persisted report")
    return {"session_id": session_id, "marker": marker, "assets": len(report.assets)}


async def main() -> int:
    try:
        result = await run_scan()
        logger.info(
            "scheduled scan completed",
            extra={"event": "scheduled_scan.completed", **result},
        )
        return 0
    except Exception as error:
        error_details = (
            {"error_code": error.error_code.name, "error_details": error.details}
            if isinstance(error, AppError)
            else {}
        )
        logger.error(
            "scheduled scan failed",
            extra={
                "event": "scheduled_scan.failed",
                "error_type": type(error).__name__,
                **error_details,
            },
        )
        return 1
    finally:
        await close_database()


if __name__ == "__main__":
    config_logger()
    raise SystemExit(asyncio.run(main()))
