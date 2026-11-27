"""Run one Momentum worker step in its own process (admission lock or TLS engine).

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
    from app.infrastructure.admission import MomentumBusyError, admit_execution
    from app.job_runner import create_result_engine

    engine = create_result_engine(os.environ["PROBE_URL"])
    try:
        async with admit_execution(engine) as connection:
            assert not connection.in_transaction()
            print("acquired", flush=True)
            if mode == "hold":
                await asyncio.to_thread(sys.stdin.readline)
            elif mode == "cancel":
                raise asyncio.CancelledError()
            elif mode == "write":
                async with connection.begin():
                    assert await connection.scalar(text("SELECT 1")) == 1
    except MomentumBusyError:
        print("busy", flush=True)
        return 75
    except asyncio.CancelledError:
        print("cancelled", flush=True)
    finally:
        await engine.dispose()
    return 0


async def tls(kind: str) -> int:
    address = os.environ["PROBE_URL"]
    os.environ["DATABASE_URL"] = address
    from app.infrastructure.session_database import create_session_service
    from app.job_runner import create_result_engine

    sessions = await create_session_service(address) if kind == "session" else None
    engine = sessions.db_engine if sessions else create_result_engine(address)
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
