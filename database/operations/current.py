"""Verify the current release without rewriting its immutable adoption baseline."""

import hashlib
import json

from operations.catalog import fingerprint, snapshot


def source_digest(root, domain):
    paths = list((root / "domains" / domain).rglob("*.sql"))
    paths += list((root / "domains" / domain).rglob("*.yaml"))
    if domain == "momentum":
        paths += list((root / "changelog/momentum-unified").rglob("*.sql"))
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


async def history(connection):
    return [
        dict(row)
        for row in await connection.fetch("""
        SELECT id, author, filename, md5sum, exectype
        FROM liquibase.databasechangelog ORDER BY filename, id, author
    """)
    ]


async def capture_current(connection, root, domain):
    schema, rows = await read_current(connection)
    return {
        "source_digest": source_digest(root, domain),
        "fingerprint": schema,
        "changesets": [
            {key: row[key] for key in ("id", "author", "filename", "md5sum")}
            for row in rows
        ],
    }


async def read_current(connection):
    """Read schema and migration history in the same consistent, read-only view."""
    async with connection.transaction(isolation="repeatable_read", readonly=True):
        schema = await snapshot(connection, include_column_grants=True)
        return fingerprint(schema), await history(connection)


async def require_current(connection, root, domain):
    expected = json.loads((root / "domains" / domain / "current.json").read_text())
    if expected["source_digest"] != source_digest(root, domain):
        raise ValueError(
            "Current schema manifest is stale; regenerate from local migrations"
        )
    schema, rows = await read_current(connection)
    if schema != expected["fingerprint"]:
        raise ValueError("Schema differs from the current migrated release")
    actual = {(row["id"], row["author"], row["filename"]): row for row in rows}
    # Adoption retains legacy rows. Every changeset in this release must still
    # be present with the exact checksum produced by a clean Liquibase replay.
    for change in expected["changesets"]:
        key = (change["id"], change["author"], change["filename"])
        row = actual.get(key)
        if (
            not row
            or row["md5sum"] != change["md5sum"]
            or row["exectype"] not in {"EXECUTED", "RERAN", "MARK_RAN"}
        ):
            raise ValueError(
                "Migration history is missing or differs from the current release"
            )
