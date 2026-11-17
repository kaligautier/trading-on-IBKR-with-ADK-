"""Rebuild ONLY labelled local fixtures and record the fully migrated release."""

import asyncio
import json
import sys

import asyncpg
import local_domains as domains

sys.path.insert(0, str(domains.ROOT))
from operations.current import capture_current  # noqa: E402


async def main():
    domains.reset()
    for domain in domains.DOMAINS:
        domains.migrate(domain)
        connection = await asyncpg.connect(
            host="127.0.0.1",
            port=int(domains.PORT),
            database=domain,
            user="database_migrator",
            password=domains.PASSWORD,
            ssl=False,
        )
        try:
            state = await capture_current(connection, domains.ROOT, domain)
        finally:
            await connection.close()
        path = domains.ROOT / "domains" / domain / "current.json"
        path.write_text(json.dumps(state, indent=2) + "\n")
        print(f"Recorded {domain}: {len(state['changesets'])} changesets")


if __name__ == "__main__":
    asyncio.run(main())
