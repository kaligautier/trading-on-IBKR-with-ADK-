"""Hold the reviewed fleet allocation using synthetic local PostgreSQL clients."""

import asyncio
import json

import asyncpg


async def main():
    connections = []
    # Workers already hold their result/admission connections in other processes.
    clients = [
        ("market_scanner_writer", "market_scanner"),  # ADK session
        ("momentum_sessions_writer", "momentum"),
        ("market_scanner_reader", "market_scanner"),
        ("momentum_results_reader", "momentum"),
        ("litellm", "postgres"),  # admin
        ("litellm", "postgres"),  # gateway
        ("capacity_provider", "postgres"),
        ("market_scanner_writer", "market_scanner"),  # admission probe
        ("momentum_results_writer", "momentum"),  # admission probe
        ("capacity_operator", "postgres"),  # must remain usable at peak
    ]
    try:
        for role, database in clients:
            connections.append(
                await asyncpg.connect(
                    host="127.0.0.1",
                    port=55474,
                    user=role,
                    password="domain-test-only",
                    database=database,
                    ssl=False,
                    timeout=5,
                )
            )
        assert not await connections[7].fetchval(
            "SELECT pg_try_advisory_lock(73192001)"
        )
        assert not await connections[8].fetchval(
            "SELECT pg_try_advisory_lock(73192002)"
        )
        operator = connections[-1]
        assert await operator.fetchval("SHOW max_connections") == "15"
        assert await operator.fetchval("SHOW superuser_reserved_connections") == "3"
        count = await operator.fetchval(
            "SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend'"
        )
        assert count == 12, count
        # Provider and operator fit; migration must wait for the offline phase.
        assert await connections[6].fetchval("SELECT 1") == 1
        assert await operator.fetchval("SELECT 1") == 1
        try:
            extra = await asyncpg.connect(
                host="127.0.0.1",
                port=55474,
                user="database_migrator",
                password="domain-test-only",
                database="postgres",
                ssl=False,
                timeout=5,
            )
        except asyncpg.TooManyConnectionsError:
            pass
        else:
            await extra.close()
            raise AssertionError(
                "Migration unexpectedly fitted during the full runtime peak"
            )
        print(
            json.dumps(
                {
                    "ordinary_connections": count,
                    "operator": "usable",
                    "provider": "counted",
                    "migration": "requires offline phase",
                }
            )
        )
    finally:
        await asyncio.gather(*(connection.close() for connection in connections))


asyncio.run(main())
