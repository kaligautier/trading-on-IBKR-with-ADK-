"""Manage one domain's current baseline and subsequent Liquibase migrations."""

import argparse
import asyncio
import json
import os
import re
from pathlib import Path
import ssl
import subprocess
import sys
import uuid
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

import asyncpg

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from operations.catalog import require_baseline, snapshot  # noqa: E402

IMAGE = "local/deepcopy-database:5.0.4"
BASELINE_TAG = "aiven-20261023"


def connection_parameters(raw, domain, ca_file):
    url = urlsplit(raw)
    options = parse_qs(url.query)
    if (
        url.scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}
        or not url.hostname
        or not url.username
        or url.path != "/" + domain
        or url.fragment
        or set(options) - {"sslmode", "sslrootcert", "ssl"}
        or any(len(value) != 1 for value in options.values())
    ):
        raise ValueError("Use an explicit PostgreSQL URL for the selected domain")
    local = url.hostname in {"localhost", "127.0.0.1", "::1"}
    mode = options.get("sslmode", options.get("ssl", [None]))[0]
    if not local and mode != "verify-full":
        raise ValueError("Remote connections require sslmode=verify-full")
    ca = ca_file or options.get("sslrootcert", [None])[0]
    tls = (
        ssl.create_default_context(cafile=str(ca) if ca else None)
        if mode == "verify-full"
        else False
    )
    return dict(
        host=url.hostname,
        port=url.port or 5432,
        user=unquote(url.username),
        password=unquote(url.password or ""),
        database=domain,
        ssl=tls,
        timeout=10,
        server_settings={
            "application_name": "domain-database-manager",
            "statement_timeout": "30000",
        },
    )


def liquibase(domain, parameters, command, ca_file=None):
    query = {"sslmode": "verify-full"} if parameters["ssl"] else {}
    extra = []
    if parameters["host"] in {"localhost", "127.0.0.1", "::1"}:
        extra += ["--network", "host"]
    if ca_file:
        query["sslrootcert"] = "/run/database-ca.pem"
        extra += ["--volume", f"{Path(ca_file).resolve()}:/run/database-ca.pem:ro"]
    host = parameters["host"]
    if ":" in host:
        host = f"[{host}]"
    address = f"jdbc:postgresql://{host}:{parameters['port']}/{domain}"
    if query:
        address += "?" + urlencode(query)
    settings = {
        "LIQUIBASE_COMMAND_URL": address,
        "LIQUIBASE_COMMAND_USERNAME": parameters["user"],
        "LIQUIBASE_COMMAND_PASSWORD": parameters["password"],
        "LIQUIBASE_COMMAND_CHANGELOG_FILE": f"domains/{domain}/changelog.yaml",
        "LIQUIBASE_LIQUIBASE_SCHEMA_NAME": "liquibase",
    }
    container = "deepcopy-liquibase-" + uuid.uuid4().hex
    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--name",
                container,
                *extra,
                "--volume",
                f"{ROOT}:/liquibase/changelog:ro",
                *[arg for key in settings for arg in ("--env", key)],
                IMAGE,
                *command,
            ],
            env={**os.environ, **settings},
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        cleanup = subprocess.run(
            ["docker", "rm", "--force", container],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if cleanup.returncode and "No such container" not in cleanup.stderr:
            raise RuntimeError(
                f"Liquibase interrupted; could not remove {container}"
            ) from None
        raise RuntimeError(
            "Liquibase interrupted; migration container removed"
        ) from None
    if result.returncode:
        raise RuntimeError("Liquibase failed; connection details suppressed")
    # JDBC diagnostics may contain credentials. Only expose output for SQL previews,
    # whose generated SQL must be reviewed before a migration.
    if command[0] == "update-sql":
        print(result.stdout)
    elif command[0] == "status":
        for line in (result.stdout + "\n" + result.stderr).splitlines():
            count = re.match(
                r"\s*(\d+ changesets? (?:have|has) not been applied)", line
            )
            if count:
                print(count.group(1))
            elif line.strip().endswith(("is up to date", "is up to date.")):
                print(f"{domain}: up to date")
            elif re.fullmatch(
                r"\s*domains/[A-Za-z0-9_./-]+::[A-Za-z0-9_-]+::[A-Za-z0-9_-]+", line
            ):
                print(line.strip())
    else:
        print(f"{domain}: {' '.join(command)} succeeded")


async def execute(args):
    raw = os.environ.get("DATABASE_URL", "")
    if args.url_file:
        if (
            args.url_file.is_symlink()
            or not args.url_file.is_file()
            or args.url_file.stat().st_mode & 0o077
        ):
            raise ValueError("Use a regular private URL file with permissions 0600")
        raw = args.url_file.read_text().strip()
    parameters = connection_parameters(raw, args.domain, args.ca_file)
    if args.action in {"verify", "adopt"}:
        connection = await asyncpg.connect(**parameters)
        try:
            definitions = await snapshot(connection)
            manifest = json.loads((ROOT / "domains.json").read_text())
            require_baseline(definitions, manifest[args.domain]["fingerprint"])
            await require_runtime_access(
                connection, manifest[args.domain]["runtime_roles"]
            )
        finally:
            await connection.close()
        print(
            f"{args.domain}: schema, ownership, constraints, indexes and grants match Aiven baseline"
        )
        if args.action == "verify":
            return
    if parameters["user"] != "database_migrator":
        raise ValueError("Migrations require the database_migrator identity")
    commands = {
        "status": ["status", "--verbose"],
        "plan": ["update-sql"],
        "migrate": ["update"],
        "baseline": ["update-to-tag", "--tag=" + BASELINE_TAG],
        "adopt": ["changelog-sync-to-tag", "--tag=" + BASELINE_TAG],
    }
    ca = args.ca_file or parse_qs(urlsplit(raw).query).get("sslrootcert", [None])[0]
    liquibase(args.domain, parameters, commands[args.action], ca)


async def require_runtime_access(connection, roles):
    """An identical schema is insufficient if runtime logins can become owners."""
    for role, limit in roles.items():
        state = await connection.fetchrow(
            """
            SELECT r.rolconnlimit, r.rolcanlogin,
              (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolbypassrls
               OR r.rolreplication OR r.rolinherit) AS elevated,
              EXISTS(SELECT FROM pg_auth_members WHERE member=r.oid) AS memberships,
              has_database_privilege(r.oid,current_database(),'CONNECT') AS can_connect,
              has_database_privilege(r.oid,current_database(),'CREATE,TEMP') AS can_create,
              EXISTS(SELECT FROM pg_database d WHERE d.datallowconn AND NOT d.datistemplate
                AND d.datname<>current_database()
                AND has_database_privilege(r.oid,d.oid,'CONNECT')) AS cross_domain,
              has_schema_privilege(r.oid,'public','CREATE') AS public_create
            FROM pg_roles r WHERE r.rolname=$1
        """,
            role,
        )
        if (
            not state
            or state["rolconnlimit"] != limit
            or not state["rolcanlogin"]
            or state["elevated"]
            or state["memberships"]
            or not state["can_connect"]
            or state["can_create"]
            or state["cross_domain"]
            or state["public_create"]
        ):
            raise ValueError(
                f"Runtime role {role} differs from the isolated Aiven access policy"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("verify", "status", "plan", "baseline", "migrate", "adopt")
    )
    parser.add_argument(
        "--domain", required=True, choices=("market_scanner", "momentum")
    )
    parser.add_argument("--url-file", type=Path)
    parser.add_argument("--ca-file", type=Path)
    args = parser.parse_args()
    try:
        asyncio.run(execute(args))
    except (ValueError, RuntimeError) as error:
        parser.exit(1, str(error) + "\n")
    except Exception as error:
        parser.exit(
            1,
            f"Database operation failed ({type(error).__name__}); details suppressed\n",
        )


if __name__ == "__main__":
    main()
