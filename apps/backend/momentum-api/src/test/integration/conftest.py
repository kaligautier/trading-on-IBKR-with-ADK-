"""Mandatory real database tests, restricted to the labelled localhost fixture."""

import json
import os
import shutil
import subprocess
from uuid import UUID

import asyncpg
import pytest

from app.config import Settings
from app.database import create_engine
from app.repository import AnalysisRepository
from app.service import AnalysisService

BASE = "postgresql://{}:local-only@127.0.0.1:55451/momentum"


@pytest.fixture(scope="session", autouse=True)
def local_database():
    if os.getenv("MOMENTUM_API_TEST_DATABASE") != "1":
        pytest.fail(
            "Run bash scripts/test_database.sh verify; integration tests are mandatory"
        )
    docker = shutil.which("docker")
    assert docker is not None
    metadata = json.loads(
        subprocess.check_output(  # noqa: S603 -- fixed inspection of our fixture
            [docker, "inspect", "momentum-api-test-db"], text=True
        )
    )[0]
    assert metadata["Config"]["Labels"]["org.deepcopy.momentum-api-test"] == "true"
    assert metadata["NetworkSettings"]["Ports"]["5432/tcp"] == [
        {"HostIp": "127.0.0.1", "HostPort": "55451"}
    ]


@pytest.fixture
async def admin(local_database):
    connection = await asyncpg.connect(BASE.format("postgres"))
    await connection.execute("TRUNCATE _analysis.analysis_results CASCADE")
    try:
        yield connection
    finally:
        await connection.execute("TRUNCATE _analysis.analysis_results CASCADE")
        await connection.close()


@pytest.fixture
async def service(admin):
    settings = Settings(
        DATABASE_URL=BASE.format("momentum_results_reader"),
        API_TOKEN="disposable-test-token",
    )
    engine = create_engine(settings)
    try:
        yield AnalysisService(AnalysisRepository(engine)), engine
    finally:
        await engine.dispose()


async def seed(connection, count=1):
    await connection.executemany(
        """
        INSERT INTO _analysis.analysis_results
        (id, ticker, analysis_date, llm_provider, deep_think_llm, quick_think_llm,
         created_at, session_id, invocation_id, user_id)
        VALUES ($1,$2,'2026-10-22','test-provider','test-deep','test-quick',
                '2026-10-22T12:00:00Z','private-session','private-invocation','private-user')
    """,
        [(UUID(int=index + 1), f"T{index:03}") for index in range(count)],
    )
