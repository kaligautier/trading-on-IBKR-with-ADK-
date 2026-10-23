"""Verify real reader isolation before an administrator bootstraps managed PG."""

import argparse
import asyncio
import ssl
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import asyncpg


async def verify(url: str) -> bool:
    """Return whether the managed template1 exception was actually verified."""
    target = urlsplit(url)
    query = parse_qs(target.query)
    if (
        target.scheme not in {"postgres", "postgresql"}
        or not target.hostname
        or target.hostname.startswith("/")
        or not target.password
    ):
        raise ValueError("An explicit PostgreSQL host and credential are required")
    if target.username != "momentum_results_reader" or target.path != "/momentum":
        raise ValueError("Expected the dedicated Momentum reader")
    if query.get("sslmode") != ["verify-full"]:
        raise ValueError("Verified TLS is required")
    ca = query.get("sslrootcert", [None])[0]
    tls = ssl.create_default_context(cafile=ca)
    options = {
        "host": target.hostname,
        "port": target.port,
        "user": unquote(target.username),
        "password": unquote(target.password or ""),
        "ssl": tls,
        "timeout": 10,
        "command_timeout": 10,
        "server_settings": {"default_transaction_read_only": "on"},
    }
    connection = await asyncpg.connect(database="momentum", **options)
    try:
        databases = await connection.fetch(
            "SELECT datname,datistemplate,pg_get_userbyid(datdba) AS owner "
            "FROM pg_database WHERE datallowconn AND datname <> 'momentum'"
        )
    finally:
        await connection.close()
    template_denied = False
    for database in databases:
        try:
            other = await asyncpg.connect(database=database["datname"], **options)
        except asyncpg.InsufficientPrivilegeError:
            continue
        except asyncpg.InvalidAuthorizationSpecificationError as error:
            # Bad credentials, TLS errors and timeouts never count as isolation.
            if "pg_hba.conf rejects connection" not in str(error):
                raise ValueError("Unexpected connection refusal") from None
            if database["datname"] == "template1":
                if not database["datistemplate"] or database["owner"] != "postgres":
                    raise ValueError("Unexpected template1 ownership") from None
                template_denied = True
        else:
            await other.close()
            raise ValueError("Reader can connect outside Momentum")
    return template_denied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reader-url-file", type=Path, required=True)
    args = parser.parse_args()
    path = args.reader_url_file
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        parser.error("Use a regular private credential file (0600)")
    try:
        denied = asyncio.run(verify(path.read_text().strip()))
    except Exception:
        parser.exit(
            1, "Reader network isolation verification failed; details suppressed.\n"
        )
    if denied:
        print("SET momentum_reader.template1_pg_hba_denied = 'on';")


if __name__ == "__main__":
    main()
