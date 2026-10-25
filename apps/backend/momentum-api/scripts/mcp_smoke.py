"""Real loopback MCP -> Momentum API -> owned PostgreSQL fixture, using Postman.

The API's Cloud Run ingress is emulated only on loopback; this test proves HTTP
and persistence, not IAM. The separate container smoke verifies bearer auth.
"""

import asyncio
import json
import os
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from uuid import UUID

import asyncpg

ROOT = Path(__file__).resolve().parents[4]
API = ROOT / "apps/backend/momentum-api"
MCP = ROOT / "apps/backend/momentum-public-mcp"
DATABASE = "postgresql://postgres:local-only@127.0.0.1:55473/momentum"
ANALYSIS = UUID("11111111-1111-1111-1111-111111111111")


def ready(port: int, process: subprocess.Popen) -> None:
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Fixture HTTP server exited")
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.1)
    raise RuntimeError("Fixture HTTP server did not become ready")


async def seed() -> None:
    connection = await asyncpg.connect(DATABASE)
    try:
        async with connection.transaction():
            assert not await connection.fetchval(
                "SELECT EXISTS(SELECT FROM _analysis.analysis_results WHERE id=$1)",
                ANALYSIS,
            )
            assert not await connection.fetchval(
                "SELECT EXISTS(SELECT FROM _suggestions.ticker_suggestions "
                "WHERE symbol='MSFT')"
            )
            await connection.execute(
                """
                INSERT INTO _analysis.analysis_results
                  (id,ticker,analysis_date,created_at,llm_provider,deep_think_llm,
                   quick_think_llm,session_id,invocation_id,user_id)
                VALUES ($1,'AAPL','2026-10-23','2026-10-23T12:00:00Z','test',
                        'test','test','fixture','fixture','fixture')
            """,
                ANALYSIS,
            )
            await connection.execute(
                """
                INSERT INTO _analysis.portfolio_decisions
                    (id,result_id,ticker,analysis_date,rating,
                     executive_summary,investment_thesis)
                VALUES (gen_random_uuid(),$1,'AAPL','2026-10-23','Buy',
                        'Synthetic local fixture','Synthetic local fixture')
            """,
                ANALYSIS,
            )
    finally:
        await connection.close()


async def verify_and_clean(success: bool) -> None:
    connection = await asyncpg.connect(DATABASE)
    try:
        row = await connection.fetchrow("""
            SELECT id,status,reason,suggested_by FROM _suggestions.ticker_suggestions
            WHERE symbol='MSFT'
        """)
        if success:
            assert row and row["status"] == "pending"
            assert row["reason"] == "MCP migration test"
            assert len(row["suggested_by"]) == 64
            print("Independent PostgreSQL read confirms committed pending suggestion.")
        if row and row["reason"] == "MCP migration test":
            await connection.execute(
                "DELETE FROM _suggestions.ticker_suggestions WHERE id=$1", row["id"]
            )
        await connection.execute(
            "DELETE FROM _analysis.portfolio_decisions WHERE result_id=$1", ANALYSIS
        )
        await connection.execute(
            "DELETE FROM _analysis.analysis_results WHERE id=$1", ANALYSIS
        )
    finally:
        await connection.close()


def main() -> None:
    metadata = json.loads(
        subprocess.check_output(
            ["docker", "inspect", "momentum-current-api-test-db"],
            text=True,
        )
    )[0]
    assert metadata["Config"]["Labels"]["org.deepcopy.momentum-api-test"] == "true"
    assert metadata["NetworkSettings"]["Ports"]["5432/tcp"] == [
        {"HostIp": "127.0.0.1", "HostPort": "55473"}
    ]
    for port in (8184, 8185):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    asyncio.run(seed())
    processes = []
    success = False
    with (
        tempfile.TemporaryDirectory(prefix="momentum-mcp-smoke-") as directory,
        (Path(directory) / "servers.log").open("w") as log,
    ):
        try:
            shared = {**os.environ, "SUGGESTION_HASH_SECRET": "loopback-smoke-only"}
            api = subprocess.Popen(
                [
                    str(API / ".venv/bin/python"),
                    "-m",
                    "uvicorn",
                    "app.main:create_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8184",
                ],
                cwd=API,
                env={
                    **shared,
                    "DATABASE_URL": DATABASE.replace(
                        "postgres:local", "momentum_results_reader:local"
                    ),
                    "AUTH_MODE": "cloud_run",
                    "K_SERVICE": "loopback-test-only",
                },
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            processes.append(api)
            ready(8184, api)
            mcp = subprocess.Popen(
                [
                    str(MCP / ".venv/bin/python"),
                    "-c",
                    "from momentum_public_mcp.main import application; "
                    "from momentum_public_mcp.protocol import create_http_app; "
                    "import uvicorn; uvicorn.run(create_http_app(application.mcp), "
                    "host='127.0.0.1', port=8185, proxy_headers=False)",
                ],
                cwd=MCP,
                env={
                    **shared,
                    "PORT": "8185",
                    "MOMENTUM_API_USE_IAM": "false",
                    "MOMENTUM_API_URL": "http://127.0.0.1:8184",
                    "MARKET_SCANNER_API_URL": "http://127.0.0.1:8184",
                },
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            processes.append(mcp)
            ready(8185, mcp)
            collection = json.loads(
                (MCP / "tests/postman/mcp.postman_collection.json").read_text()
            )
            omitted = {
                "latest_market_scan",
                "Sanitized upstream failure",
                "Cold-start latency",
            }
            collection["item"] = [
                i for i in collection["item"] if i["name"] not in omitted
            ]
            path = Path(directory) / "collection.json"
            path.write_text(json.dumps(collection))
            subprocess.run(
                [
                    "postman",
                    "collection",
                    "run",
                    str(path),
                    "--env-var",
                    "mcpUrl=http://127.0.0.1:8185",
                    "--report-events=false",
                ],
                check=True,
            )
            success = True
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGINT)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
            asyncio.run(verify_and_clean(success))


if __name__ == "__main__":
    main()
