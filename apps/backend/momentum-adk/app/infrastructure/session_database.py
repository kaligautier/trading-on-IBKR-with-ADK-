"""Migrated, bounded PostgreSQL sessions for the pinned ADK JSON schema."""

from google.adk.sessions import DatabaseSessionService
from google.adk.sessions.database_session_service import BaseV1
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url


def _check_schema(connection):
    inspector = inspect(connection)
    for table in BaseV1.metadata.sorted_tables:
        columns = inspector.get_columns(table.name, schema="_sessions")
        if {c["name"] for c in columns} != set(table.columns.keys()):
            raise ValueError("Session columns do not match the pinned SDK")
        primary_key = inspector.get_pk_constraint(table.name, schema="_sessions")
        if primary_key["constrained_columns"] != list(table.primary_key.columns.keys()):
            raise ValueError("Session primary key does not match the pinned SDK")
        indexes = {
            i["name"] for i in inspector.get_indexes(table.name, schema="_sessions")
        }
        if not {i.name for i in table.indexes}.issubset(indexes):
            raise ValueError("Session indexes do not match the pinned SDK")
        expected = {
            (
                tuple(e.parent.name for e in fk.elements),
                tuple(e.column.name for e in fk.elements),
                fk.referred_table.name,
                fk.ondelete,
            )
            for fk in table.foreign_key_constraints
        }
        actual = {
            (
                tuple(fk["constrained_columns"]),
                tuple(fk["referred_columns"]),
                fk["referred_table"],
                fk["options"].get("ondelete"),
            )
            for fk in inspector.get_foreign_keys(table.name, schema="_sessions")
            if fk["referred_schema"] in (None, "_sessions")
        }
        if actual != expected:
            raise ValueError("Session foreign keys do not match the pinned SDK")
    version = connection.execute(
        text(
            "SELECT value FROM _sessions.adk_internal_metadata "
            "WHERE key='schema_version'"
        )
    ).scalar_one()
    if version != "1":
        raise ValueError("Session schema version must be 1")


async def create_session_service(database_url: str) -> DatabaseSessionService:
    """Fail before SDK preparation if Liquibase objects are missing or outdated."""
    service = None
    try:
        address = make_url(database_url)
        if address.drivername not in {"postgresql", "postgres", "postgresql+asyncpg"}:
            raise ValueError("PostgreSQL is required")
        address = address.set(drivername="postgresql+asyncpg")
        if "sslmode" in address.query:
            mode = address.query["sslmode"]
            address = address.difference_update_query(["sslmode"])
            address = address.update_query_dict({"ssl": mode})
        service = DatabaseSessionService(
            db_url=address.render_as_string(hide_password=False),
            pool_size=1,
            max_overflow=0,
            pool_timeout=5,
            hide_parameters=True,
            connect_args={
                "timeout": 10,
                "server_settings": {
                    "search_path": "_sessions, pg_catalog",
                    "statement_timeout": "30000",
                    "idle_in_transaction_session_timeout": "30000",
                },
            },
        )
        async with service.db_engine.connect() as connection:
            await connection.run_sync(_check_schema)
        # All tables/indexes/version already exist; stock SDK checks need no DDL.
        await service.prepare_tables()
        return service
    except Exception:
        if service is not None:
            await service.close()
        raise RuntimeError(
            "Momentum session migrations are required or unavailable"
        ) from None
