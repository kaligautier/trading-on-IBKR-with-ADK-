"""Synthetic worker process: acquire, hold, cancel or reject a real admission lock."""

import asyncio
import os
import sys

from sqlalchemy import text

os.environ.update(LITELLM_API_BASE="http://127.0.0.1:4000", LITELLM_API_KEY="synthetic")


async def main():
    component, mode = sys.argv[1:]
    if component == "scanner":
        from app.config.settings import settings
        from app.services.admission import ScannerBusyError, admit_scan, result_bind
        from app.services.database import close_database

        settings.DATABASE_URL = os.environ["PROBE_URL"]
        admission, busy, cleanup = admit_scan, ScannerBusyError, close_database
    else:
        from app.infrastructure.admission import MomentumBusy, admit_execution
        from app.job_runner import create_result_engine

        engine = create_result_engine(os.environ["PROBE_URL"])
        admission, busy, cleanup = (
            lambda: admit_execution(engine),
            MomentumBusy,
            engine.dispose,
        )
    try:
        async with admission() as connection:
            if component == "scanner":
                assert result_bind() is connection
            assert not connection.in_transaction()
            print("acquired", flush=True)
            if mode == "hold":
                await asyncio.to_thread(sys.stdin.readline)
            elif mode == "cancel":
                raise asyncio.CancelledError()
            elif mode == "write":
                async with connection.begin():
                    assert await connection.scalar(text("SELECT 1")) == 1
    except busy:
        print("busy", flush=True)
        return 75
    except asyncio.CancelledError:
        print("cancelled", flush=True)
    finally:
        await cleanup()
    return 0


raise SystemExit(asyncio.run(main()))
