"""Bounded ADK sessions in a Liquibase-owned PostgreSQL schema."""

import os

from google.adk.sessions import DatabaseSessionService
from google.adk.sessions.database_session_service import BaseV1
from sqlalchemy import inspect, text
from sqlalchemy.pool import NullPool

from app.services.postgres_tls import connection_options


def _check_schema(connection):
    inspector = inspect(connection)
    for table in BaseV1.metadata.sorted_tables:
        columns = inspector.get_columns(table.name, schema="_sessions")
        if {column["name"] for column in columns} != set(table.columns.keys()):
            raise ValueError("Session columns do not match the pinned SDK")
        primary = inspector.get_pk_constraint(table.name, schema="_sessions")
        if primary["constrained_columns"] != list(table.primary_key.columns.keys()):
            raise ValueError("Session primary key does not match the pinned SDK")
        indexes = inspector.get_indexes(table.name, schema="_sessions")
        if not {index.name for index in table.indexes}.issubset(
            {index["name"] for index in indexes}
        ):
            raise ValueError("Session indexes do not match the pinned SDK")
    version = connection.execute(
        text(
            "SELECT value FROM _sessions.adk_internal_metadata "
            "WHERE key='schema_version'"
        )
    ).scalar_one()
    if version != "1":
        raise ValueError("Session schema version must be 1")


class ScannerSessionService(DatabaseSessionService):
    """Validate before the SDK can attempt table creation, including lazy API use."""

    def __init__(self, database_url: str):
        try:
            address, tls = connection_options(
                database_url, os.getenv("DATABASE_CA_FILE")
            )
            super().__init__(
                address.render_as_string(hide_password=False),
                poolclass=NullPool,
                hide_parameters=True,
                connect_args={
                    "ssl": tls,
                    "timeout": 10,
                    "server_settings": {
                        "search_path": "_sessions, pg_catalog",
                        "application_name": "market-scanner-sessions",
                        "statement_timeout": "30000",
                        "idle_in_transaction_session_timeout": "30000",
                    },
                },
            )
        except Exception:
            raise ValueError("Configure PostgreSQL for Scanner sessions") from None
        self._schema_verified = False

    async def prepare_tables(self) -> None:
        try:
            if not self._schema_verified:
                async with self.db_engine.connect() as connection:
                    await connection.run_sync(_check_schema)
                self._schema_verified = True
            await super().prepare_tables()
        except Exception:
            await self.close()
            raise RuntimeError(
                "Scanner session migrations are required or unavailable"
            ) from None


def registered_session_service(_uri, **kwargs):
    """ADK's public registry passes the per-application service instance."""
    return kwargs["scanner_session_service"]
