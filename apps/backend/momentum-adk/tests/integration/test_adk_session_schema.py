"""The pinned ADK runs against migrations with DML-only runtime credentials."""

import asyncpg
import pytest
from google.adk.events import Event, EventActions
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.infrastructure.session_database import create_session_service


async def test_real_adk_session_events_resume_and_delete(migrated_database):
    statements = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(Engine, "before_cursor_execute", record_statement)
    service = None
    try:
        service = await create_session_service(migrated_database["momentum_writer"])
        session = await service.create_session(
            app_name="momentum",
            user_id="test-operator",
            session_id="session-1",
            state={"ticker": "NVDA", "app:language": "English"},
        )
        await service.append_event(
            session,
            Event(
                author="analyst",
                invocation_id="invocation-1",
                actions=EventActions(state_delta={"step": "research"}),
            ),
        )
        restored = await service.get_session(
            app_name="momentum",
            user_id="test-operator",
            session_id="session-1",
        )
        assert restored.state["ticker"] == "NVDA"
        assert restored.state["step"] == "research"
        assert restored.events[0].invocation_id == "invocation-1"
        assert (
            len(
                (
                    await service.list_sessions(
                        app_name="momentum",
                        user_id="test-operator",
                    )
                ).sessions
            )
            == 1
        )
        await service.delete_session(
            app_name="momentum",
            user_id="test-operator",
            session_id="session-1",
        )
        assert (
            await service.get_session(
                app_name="momentum",
                user_id="test-operator",
                session_id="session-1",
            )
            is None
        )
        assert not {"CREATE", "ALTER", "DROP", "GRANT"}.intersection(statements)
    finally:
        event.remove(Engine, "before_cursor_execute", record_statement)
        if service is not None:
            await service.close()


@pytest.mark.parametrize("mutation", ["index", "version"])
async def test_missing_migrations_fail_without_repair(migrated_database, mutation):
    admin = await asyncpg.connect(migrated_database["admin"])
    try:
        async with admin.transaction():
            if mutation == "index":
                await admin.execute(
                    "DROP INDEX momentum.idx_events_app_user_session_ts"
                )
            else:
                await admin.execute(
                    "UPDATE momentum.adk_internal_metadata SET value='0'"
                )
        with pytest.raises(RuntimeError, match="session migrations are required"):
            await create_session_service(migrated_database["momentum_writer"])
    finally:
        if mutation == "index":
            await admin.execute(
                "CREATE INDEX idx_events_app_user_session_ts ON momentum.events "
                "(app_name, user_id, session_id, timestamp DESC)"
            )
        else:
            await admin.execute("UPDATE momentum.adk_internal_metadata SET value='1'")
        await admin.close()
