"""Run the current Momentum result tests against the fresh domain, without legacy DDL."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from google.adk.events import Event, EventActions

from app.infrastructure.session_database import create_session_service

# Reuse the current application's complete typed financial fixture and assertions.
source = (
    Path(os.environ["MOMENTUM_ROOT"]) / "tests/integration/test_result_persistence.py"
)
spec = importlib.util.spec_from_file_location("momentum_result_contract", source)
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
persistence = reference.persistence
test_all_sections_commit_with_real_adk_correlation = (
    reference.test_all_sections_commit_with_real_adk_correlation
)
test_failed_section_rolls_back_entire_analysis = (
    reference.test_failed_section_rolls_back_entire_analysis
)


def url(role):
    return f"postgresql://{role}:domain-test-only@127.0.0.1:55461/momentum"


@pytest.fixture
def domain_database():
    return {
        "admin": url("postgres"),
        "sessions_runtime": url("momentum_sessions_writer"),
        "results_runtime": url("momentum_results_writer"),
    }


async def test_current_session_adapter_survives_restart(domain_database):
    session_id = uuid4().hex
    address = domain_database["sessions_runtime"]
    first = await create_session_service(address)
    try:
        session = await first.create_session(
            app_name="momentum", user_id="local-test", session_id=session_id
        )
        await first.append_event(
            session,
            Event(
                author="agent",
                invocation_id="local-proof",
                actions=EventActions(state_delta={"proof": 42}),
            ),
        )
    finally:
        await first.close()
    second = await create_session_service(address)
    try:
        restored = await second.get_session(
            app_name="momentum", user_id="local-test", session_id=session_id
        )
        assert restored.state["proof"] == 42
        assert restored.events[0].invocation_id == "local-proof"
    finally:
        await second.close()


@pytest.mark.parametrize(
    "role,allowed,forbidden,table,count",
    [
        ("momentum_sessions_writer", "_sessions", "_analysis", "analysis_results", 5),
        ("momentum_results_writer", "_analysis", "_sessions", "sessions", 12),
    ],
)
async def test_current_roles_are_separated(role, allowed, forbidden, table, count):
    connection = await asyncpg.connect(url(role))
    try:
        assert await connection.fetchval("SELECT current_database()") == "momentum"
        assert (
            await connection.fetchval(
                "SELECT count(*) FROM pg_tables WHERE schemaname=$1", allowed
            )
            == count
        )
        for query in (
            f"SELECT * FROM {forbidden}.{table}",
            f"CREATE TABLE {allowed}.forbidden(id int)",
            "CREATE TEMP TABLE forbidden(id int)",
            "SELECT * FROM liquibase.databasechangelog",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(query)
    finally:
        await connection.close()
