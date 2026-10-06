"""Attach an existing PostgreSQL database using a protected administrator file.

Credentials are uploaded via stdin to Secret Manager and never printed, passed
in command arguments or stored in Terraform. Reruns preserve enabled versions.
"""

import argparse
import asyncio
import json
from pathlib import Path
import secrets
import ssl
import subprocess
from urllib.parse import quote, unquote, urlencode, urlparse

import asyncpg


class SecretStore:
    def __init__(self, project, account):
        self.project = project
        self.account = account

    def command(self, *args, data=None):
        result = subprocess.run(
            ["gcloud", *args, f"--project={self.project}", f"--account={self.account}"],
            input=data,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(
                "Secret Manager operation failed; credential details suppressed"
            )
        return result.stdout.strip()

    def existing_version(self, name):
        versions = json.loads(
            self.command(
                "secrets",
                "versions",
                "list",
                f"litellm-{name}",
                "--format=json",
                "--filter=state=ENABLED",
                "--sort-by=~createTime",
                "--limit=1",
            )
        )
        return versions[0]["name"].split("/")[-1] if versions else None

    def upload(self, name, value):
        existing = self.existing_version(name)
        if existing:
            return existing
        version = self.command(
            "secrets",
            "versions",
            "add",
            f"litellm-{name}",
            "--data-file=-",
            "--format=value(name)",
            data=value,
        )
        return version.rsplit("/", 1)[-1]


def existing_password(stored, expected_host, expected_port):
    uri = urlparse(stored)
    if (
        uri.scheme not in ("postgres", "postgresql")
        or uri.hostname != expected_host
        or uri.port != expected_port
        or uri.username != "litellm"
        or uri.path != "/litellm"
        or not uri.password
    ):
        raise ValueError("Existing database secret must match the dedicated target")
    return unquote(uri.password)


async def bootstrap(args):
    if args.admin_file.stat().st_mode & 0o077:
        raise ValueError("Restrict the administrator file permissions to 0600")
    uri = urlparse(json.loads(args.admin_file.read_text())["url"])
    if (
        uri.hostname != args.expected_host
        or not uri.password
        or uri.username != "avnadmin"
    ):
        raise ValueError(
            "Administrator connection must match the explicit expected host"
        )
    tls = ssl.create_default_context(cafile=str(args.ca_file))
    connection = dict(
        host=uri.hostname,
        port=uri.port,
        user=uri.username,
        password=uri.password,
        ssl=tls,
        timeout=30,
    )
    store = SecretStore(args.project, args.account)
    database_version = store.existing_version("database-url")
    salt_version = store.existing_version("salt-key")
    admin = await asyncpg.connect(**connection, database="defaultdb")
    try:
        database_exists = await admin.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname='litellm')"
        )
        role = await admin.fetchrow(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication FROM pg_roles WHERE rolname='litellm'"
        )
        if role and any(role.values()):
            raise ValueError(
                "Dedicated database role must not have administrative privileges"
            )
        if not role:
            await admin.execute("CREATE ROLE litellm LOGIN")
        if not database_exists:
            await admin.execute("CREATE DATABASE litellm OWNER litellm")
        await admin.execute("GRANT litellm TO avnadmin WITH INHERIT FALSE")
        await admin.execute("ALTER DATABASE litellm OWNER TO litellm")
        await admin.execute("REVOKE ALL ON DATABASE litellm FROM PUBLIC")
        await admin.execute("GRANT CONNECT ON DATABASE litellm TO avnadmin")
    finally:
        await admin.close()
    database = await asyncpg.connect(**connection, database="litellm")
    try:
        await database.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        tables = {
            row["tablename"]
            for row in await database.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            )
        }
        if not salt_version:
            encrypted_tables = (
                "LiteLLM_CredentialsTable",
                "LiteLLM_ProxyModelTable",
                "LiteLLM_MCPServerTable",
                "LiteLLM_MCPServerOAuthClient",
                "LiteLLM_MCPUserCredentials",
                "LiteLLM_ManagedObjectTable",
            )
            for table in encrypted_tables:
                if table in tables and await database.fetchval(
                    f'SELECT count(*) FROM "{table}"'
                ):
                    raise ValueError(
                        "Existing encrypted records require recovery of the original salt"
                    )
        if database_version:
            stored = store.command(
                "secrets",
                "versions",
                "access",
                database_version,
                "--secret=litellm-database-url",
            )
            password = existing_password(stored, uri.hostname, uri.port)
        else:
            password = secrets.token_urlsafe(32)
        # Random/validated password is quoted; DDL cannot bind a password parameter.
        escaped = password.replace("'", "''")
        await database.execute(f"ALTER ROLE litellm PASSWORD '{escaped}'")
        await database.execute(
            f"ALTER ROLE litellm CONNECTION LIMIT {args.connection_limit}"
        )
    finally:
        await database.close()
    dedicated = await asyncpg.connect(
        **{**connection, "user": "litellm", "password": password}, database="litellm"
    )
    try:
        async with dedicated.transaction():
            await dedicated.execute(
                "CREATE TEMP TABLE litellm_recovery_check (ok boolean)"
            )
            await dedicated.execute("INSERT INTO litellm_recovery_check VALUES (true)")
            assert await dedicated.fetchval("SELECT ok FROM litellm_recovery_check")
        print(
            "Dedicated PostgreSQL connection verified with TLS, hostname, DDL and writes"
        )
    finally:
        await dedicated.close()
    query = urlencode(
        dict(
            sslmode="require",
            sslcert="/etc/database/ca.pem",
            sslaccept="strict",
            connection_limit=2,
        )
    )
    url = f"postgresql://litellm:{quote(password, safe='')}@{uri.hostname}:{uri.port}/litellm?{query}"
    payloads = {
        "database-url": url,
        "database-ca": args.ca_file.read_text(),
        "master-key": "sk-" + secrets.token_hex(32),
        "salt-key": "sk-" + secrets.token_hex(32),
        "ui-password": secrets.token_urlsafe(32),
    }
    versions = {name: store.upload(name, value) for name, value in payloads.items()}
    print("Enabled Secret Manager version references:", versions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-file", type=Path, required=True)
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--connection-limit", type=int, default=12)
    args = parser.parse_args()
    if not 4 <= args.connection_limit <= 100:
        parser.error("Choose a database role connection limit between 4 and 100")
    asyncio.run(bootstrap(args))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            f"Database bootstrap stopped ({type(error).__name__}); credential details suppressed"
        )
        raise SystemExit(1) from None
