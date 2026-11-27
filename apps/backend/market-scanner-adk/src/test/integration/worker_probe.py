"""Run one scanner worker step in its own process (admission lock or TLS engine).

Executed by test_worker_processes.py, never collected by pytest. Prints a single
outcome line; credentials and error details are never printed.
"""

import asyncio
import os
import sys

from sqlalchemy import text

os.environ.setdefault("LITELLM_API_BASE", "http://127.0.0.1:4000")
os.environ.setdefault("LITELLM_API_KEY", "synthetic")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "synthetic")


async def admission(mode: str) -> int:
    from app.config.settings import settings
    from app.services.admission import ScannerBusyError, admit_scan, result_bind
    from app.services.database import close_database

    settings.DATABASE_URL = os.environ["PROBE_URL"]
    try:
        async with admit_scan() as connection:
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
    except ScannerBusyError:
        print("busy", flush=True)
        return 75
    except asyncio.CancelledError:
        print("cancelled", flush=True)
    finally:
        await close_database()
    return 0


async def tls(kind: str) -> int:
    address = os.environ["PROBE_URL"]
    os.environ["DATABASE_URL"] = os.environ["MARKET_SCANNER_DATABASE_URL"] = address
    from app.services.database import get_engine
    from app.services.session_database import ScannerSessionService

    sessions = ScannerSessionService(address) if kind == "session" else None
    engine = sessions.db_engine if sessions else get_engine()
    try:
        async with engine.connect() as connection:
            query = text("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
            assert (await connection.execute(query)).scalar_one()
        print("verified TLS on", kind, "engine")
    finally:
        if sessions:
            await sessions.close()
        await engine.dispose()
    return 0


def main() -> int:
    step, mode = sys.argv[1:]
    try:
        return asyncio.run(admission(mode) if step == "admission" else tls(mode))
    except Exception as error:  # Report exception types only, never their text.
        kinds = []
        while error is not None and len(kinds) < 8:
            kinds.append(type(error).__name__)
            error = error.__context__
        print(", ".join(kinds), "(details suppressed)", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
