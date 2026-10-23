"""Exercise worker engine adapters against a disposable TLS server."""

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
component, kind, address = sys.argv[1:]
os.environ.update(
    DATABASE_URL=address,
    MARKET_SCANNER_DATABASE_URL=address,
    LITELLM_API_BASE="http://127.0.0.1:4000",
    LITELLM_API_KEY="synthetic",
    GOOGLE_CLOUD_PROJECT="synthetic",
)


async def main():
    assert component == "scanner"
    sys.path.insert(0, str(ROOT / "apps/backend/market-scanner-adk/src"))
    from app.services.database import get_engine
    from app.services.session_database import ScannerSessionService

    sessions = ScannerSessionService(address) if kind == "session" else None
    engine = sessions.db_engine if sessions else get_engine()
    try:
        async with engine.connect() as connection:
            assert (
                await connection.execute(
                    text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()")
                )
            ).scalar_one()
        print("verified TLS on", kind, "engine")
    finally:
        if sessions:
            await sessions.close()
        await engine.dispose()


try:
    asyncio.run(main())
except Exception as error:
    kinds = []
    while error is not None and len(kinds) < 8:
        kinds.append(type(error).__name__)
        error = error.__context__
    print(", ".join(kinds), "(details suppressed)")
    raise SystemExit(1) from None
