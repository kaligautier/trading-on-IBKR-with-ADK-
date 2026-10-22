"""Explicit remote Scanner cutover actions; never reset Momentum or LiteLLM.

Credentials, Aiven token and logs belong in ignored mode-0600 local files.
Use inspect before bootstrap/migrate/publish/cleanup; cleanup only after rollout.
"""

import argparse
import asyncio
import json
import os
import ssl
import subprocess
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import asyncpg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("market_scanner_writer", "market_scanner_reader")
TABLES = ("market_scan_horizons", "market_scan_assets", "market_scans")


def command(args, *, data=None, env=None):
    result = subprocess.run(args, input=data, env=env, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{args[0]} {args[1]} failed; output suppressed")
    return result.stdout


def private_write(path, value):
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w"
    ) as f:
        f.write(value)
    path.chmod(0o600)


def private_config(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError("Credential files must be regular private files (0600)")
    return dotenv_values(path)


class Cutover:
    def __init__(self, args):
        self.args = args
        self.config = private_config(args.credentials)
        self.target = urlsplit(self.config["MIGRATION_DATABASE_URL"])
        if (
            self.target.username != "database_migrator"
            or self.target.path != "/defaultdb"
        ):
            raise ValueError("Expected the existing defaultdb migration identity")
        for key, role in zip(
            ("MARKET_SCANNER_DATABASE_URL", "MARKET_SCANNER_READER_DATABASE_URL"),
            ROLES,
            strict=True,
        ):
            value = urlsplit(self.config[key])
            if (value.hostname, value.port, value.username, value.path) != (
                self.target.hostname,
                self.target.port,
                role,
                "/defaultdb",
            ):
                raise ValueError("Existing Scanner credentials do not match the target")
        self.token = private_config(args.token_env)["AIVEN_AUTH_TOKEN"]
        self.tls = ssl.create_default_context(cafile=str(args.ca))

    def api(self, path):
        request = Request(
            "https://api.aiven.io/v1" + path,
            headers={"Authorization": "Bearer " + self.token},
        )
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def administrator(self):
        prefix = "/project/" + quote(self.args.aiven_project, safe="")
        services = self.api(prefix + "/service")["services"]
        matches = [
            s
            for s in services
            if s.get("service_uri_params", {}).get("host") == self.target.hostname
            or urlsplit(s.get("service_uri", "")).hostname == self.target.hostname
        ]
        if len(matches) != 1 or matches[0]["state"] != "RUNNING":
            raise ValueError("Expected one running service matching the deployed host")
        user = self.api(
            prefix
            + "/service/"
            + matches[0]["service_name"]
            + "/user/avnadmin?include_secrets=true"
        )["user"]
        if not user.get("password") or user["password"] == "<redacted>":
            raise ValueError("Administrator credential unavailable")
        return user["password"]

    async def connect(self, database, *, admin=False):
        if database not in {"defaultdb", "market_scanner", "momentum"}:
            raise ValueError("Database is outside the reviewed scope")
        return await asyncpg.connect(
            host=self.target.hostname,
            port=self.target.port,
            database=database,
            user="avnadmin" if admin else self.target.username,
            password=self.administrator() if admin else unquote(self.target.password),
            ssl=self.tls,
            timeout=15,
            command_timeout=30,
            server_settings={"application_name": "scanner-domain-cutover"},
        )

    async def inspect(self):
        c = await self.connect("defaultdb", admin=True)
        try:
            report = {
                "databases": [
                    r[0]
                    for r in await c.fetch(
                        "SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY 1"
                    )
                ],
                "connections": [
                    dict(r)
                    for r in await c.fetch(
                        "SELECT datname,usename,application_name,state,count(*) "
                        "FROM pg_stat_activity WHERE backend_type='client backend' "
                        "GROUP BY 1,2,3,4 ORDER BY 1,2"
                    )
                ],
                "max_connections": await c.fetchval("SHOW max_connections"),
            }
            print(json.dumps(report, default=str))
        finally:
            await c.close()

    async def bootstrap(self):
        c = await self.connect("defaultdb", admin=True)
        try:
            if await c.fetchval(
                "SELECT 1 FROM pg_database WHERE datname='market_scanner'"
            ):
                raise ValueError(
                    "market_scanner already exists; inspect it, never reset automatically"
                )
            await c.execute("CREATE DATABASE market_scanner")
        finally:
            await c.close()
        c = await self.connect("market_scanner", admin=True)
        try:
            await c.execute((ROOT / "scanner-bootstrap.sql").read_text())
        finally:
            await c.close()
        c = await self.connect("market_scanner")
        try:
            await c.execute((ROOT / "scanner-migrator-bootstrap.sql").read_text())
        finally:
            await c.close()
        print("Created market_scanner and scoped roles; no existing domain was reset.")

    def migrate(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LIQUIBASE_")}
        env.update(
            LIQUIBASE_COMMAND_URL=(
                f"jdbc:postgresql://{self.target.hostname}:"
                f"{self.target.port}/market_scanner?"
                "sslmode=verify-full&sslrootcert=/run/database-ca.pem"
            ),
            LIQUIBASE_COMMAND_USERNAME="database_migrator",
            LIQUIBASE_COMMAND_PASSWORD=unquote(self.target.password),
            LIQUIBASE_COMMAND_CHANGELOG_FILE="db.changelog-scanner.yaml",
            LIQUIBASE_LIQUIBASE_SCHEMA_NAME="liquibase",
        )
        for action in ("validate", "update-sql", "update", "update"):
            result = command(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--volume",
                    f"{ROOT / 'changelog'}:/liquibase/changelog:ro",
                    "--volume",
                    f"{self.args.ca.resolve()}:/run/database-ca.pem:ro",
                    *[
                        a
                        for k in env
                        if k.startswith("LIQUIBASE_")
                        for a in ("--env", k)
                    ],
                    "local/deep-copy-liquibase:5.0.4",
                    action,
                ],
                env=env,
            )
            if action == "update-sql":
                if (
                    result.count("CREATE TABLE _sessions.") != 5
                    or result.count("CREATE TABLE _analysis.") != 3
                ):
                    raise ValueError("Unexpected migration preview")
            private_write(
                self.args.evidence / f"scanner-{action}.log",
                result.replace(self.target.password, "[REDACTED]").replace(
                    unquote(self.target.password), "[REDACTED]"
                ),
            )
        print("Scanner fresh migrations applied and second update completed.")

    def publish(self):
        versions = {}
        for key, secret in (
            ("MARKET_SCANNER_DATABASE_URL", "market-scanner-database-url"),
            (
                "MARKET_SCANNER_READER_DATABASE_URL",
                "market-scanner-reader-database-url",
            ),
        ):
            reader = secret == "market-scanner-reader-database-url"
            service = "market-scanner-api" if reader else "market-scanner-adk"
            env_name = "DATABASE_URL" if reader else "MARKET_SCANNER_DATABASE_URL"
            deployed = json.loads(
                command(
                    [
                        "gcloud",
                        "run",
                        "services",
                        "describe",
                        service,
                        "--project=" + self.args.gcp_project,
                        "--region=europe-west1",
                        "--format=json",
                    ]
                )
            )
            entries = deployed["spec"]["template"]["spec"]["containers"][0]["env"]
            ref = next(e for e in entries if e["name"] == env_name)["valueFrom"][
                "secretKeyRef"
            ]
            if ref["name"] != secret:
                raise ValueError("Unexpected deployed secret reference")
            current = command(
                [
                    "gcloud",
                    "secrets",
                    "versions",
                    "access",
                    ref["key"],
                    "--secret=" + secret,
                    "--project=" + self.args.gcp_project,
                ]
            ).strip()
            address = urlsplit(current)
            expected = urlsplit(self.config[key])
            if (address.hostname, address.port, address.username, address.password) != (
                expected.hostname,
                expected.port,
                expected.username,
                expected.password,
            ) or address.path != "/defaultdb":
                raise ValueError("Deployed credentials differ from the reviewed source")
            # Retain the deployed password and all TLS options exactly.
            url = urlunsplit(address._replace(path="/market_scanner"))
            versions[secret] = (
                command(
                    [
                        "gcloud",
                        "secrets",
                        "versions",
                        "add",
                        secret,
                        "--project=" + self.args.gcp_project,
                        "--data-file=-",
                        "--format=value(name)",
                    ],
                    data=url,
                )
                .strip()
                .split("/")[-1]
            )
        private_write(self.args.evidence / "secret-versions.json", json.dumps(versions))
        print(json.dumps(versions))

    def verify_rollout(self):
        images = json.loads((self.args.evidence / "images.json").read_text())
        for kind, name, image_key, url_key in (
            (
                "services",
                "market-scanner-adk",
                "scanner",
                "MARKET_SCANNER_DATABASE_URL",
            ),
            ("services", "market-scanner-api", "reader", "DATABASE_URL"),
            ("jobs", "market-scanner-daily", "scanner", "MARKET_SCANNER_DATABASE_URL"),
        ):
            data = json.loads(
                command(
                    [
                        "gcloud",
                        "run",
                        kind,
                        "describe",
                        name,
                        "--project=" + self.args.gcp_project,
                        "--region=europe-west1",
                        "--format=json",
                    ]
                )
            )
            template = data["spec"]["template"]["spec"]
            if kind == "jobs":
                template = template["template"]["spec"]
            else:
                status = data["status"]
                ready = status["latestReadyRevisionName"]
                generation = data.get("metadata", {}).get("generation")
                if (
                    generation is None
                    or str(status.get("observedGeneration")) != str(generation)
                    or status.get("latestCreatedRevisionName") != ready
                    or not any(
                        c.get("type") == "Ready" and c.get("status") == "True"
                        for c in status.get("conditions", [])
                    )
                ):
                    raise ValueError("The reviewed service revision is not ready")
                traffic = data["status"]["traffic"]
                if (
                    sum(
                        t.get("percent", 0)
                        for t in traffic
                        if t.get("revisionName") == ready
                    )
                    != 100
                ):
                    raise ValueError("An older service revision still has traffic")
            container = template["containers"][0]
            env = {item["name"]: item for item in container["env"]}
            if (
                container["image"] != images[image_key]
                or env["DATABASE_SCHEMA"]["value"] != "_analysis"
            ):
                raise ValueError("Reviewed image and analysis schema are not deployed")
            ref = env[url_key]["valueFrom"]["secretKeyRef"]
            raw = command(
                [
                    "gcloud",
                    "secrets",
                    "versions",
                    "access",
                    ref["key"],
                    "--secret=" + ref["name"],
                    "--project=" + self.args.gcp_project,
                ]
            ).strip()
            address = urlsplit(raw)
            if (address.hostname, address.port, address.path) != (
                self.target.hostname,
                self.target.port,
                "/market_scanner",
            ):
                raise ValueError("A deployed consumer still targets another database")
        executions = json.loads(
            command(
                [
                    "gcloud",
                    "run",
                    "jobs",
                    "executions",
                    "list",
                    "--job=market-scanner-daily",
                    "--project=" + self.args.gcp_project,
                    "--region=europe-west1",
                    "--format=json",
                ]
            )
        )
        if any(not e.get("status", {}).get("completionTime") for e in executions):
            raise ValueError("Wait for Scanner executions to finish before cleanup")
        proof = json.loads((self.args.evidence / "verified-scan.json").read_text())
        if not any(
            e["metadata"]["name"] == proof["execution"]
            and e.get("status", {}).get("succeededCount") == 1
            for e in executions
        ):
            raise ValueError(
                "A verified successful fresh scan is required before cleanup"
            )

    async def cleanup(self):
        self.verify_rollout()
        proof = json.loads((self.args.evidence / "verified-scan.json").read_text())
        current = await self.connect("market_scanner")
        try:
            if not await current.fetchval(
                "SELECT EXISTS(SELECT FROM _analysis.market_scans r "
                "JOIN _sessions.sessions s ON r.session_id='scheduled:' || s.id "
                "WHERE s.id=$1 AND r.id::text=$2)",
                proof["execution"],
                proof["scan_id"],
            ):
                raise ValueError("The fresh report and session must still exist")
        finally:
            await current.close()
        admin = await self.connect("defaultdb", admin=True)
        try:
            old = await admin.fetch(
                "SELECT pid,usename,application_name,state FROM pg_stat_activity "
                "WHERE datname='defaultdb' AND usename=ANY($1)",
                list(ROLES),
            )
            for row in old:
                if row["state"] != "idle" or row["application_name"] not in {
                    "market-scanner-api",
                    "market-scanner-adk",
                }:
                    raise ValueError("Unknown or busy old consumer; cleanup refused")
            for row in old:
                await admin.fetchval("SELECT pg_terminate_backend($1)", row["pid"])
        finally:
            await admin.close()
        c = await self.connect("defaultdb")
        try:
            async with c.transaction():
                await c.execute("SET LOCAL lock_timeout='5s'")
                tables = await c.fetch(
                    "SELECT tablename FROM pg_tables WHERE schemaname='market_scanner'"
                )
                history = await c.fetch(
                    "SELECT id,author FROM liquibase.databasechangelog"
                )
                if {r[0] for r in tables} != set(TABLES) or [
                    tuple(r) for r in history
                ] != [("market-scanner-001", "deep-copy")]:
                    raise ValueError("Legacy inventory changed; cleanup refused")
                for table in TABLES:
                    await c.execute("DROP TABLE market_scanner." + table)
                await c.execute("DROP SCHEMA market_scanner")
                await c.execute(
                    "DROP TABLE liquibase.databasechangeloglock, liquibase.databasechangelog"
                )
                await c.execute("DROP SCHEMA liquibase")
        finally:
            await c.close()
        admin = await self.connect("defaultdb", admin=True)
        try:
            await admin.execute((ROOT / "retire-defaultdb-access.sql").read_text())
        finally:
            await admin.close()
        print(
            "Removed only legacy Scanner tables/schema and its isolated history from defaultdb."
        )


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("inspect", "bootstrap", "migrate", "publish", "cleanup")
    )
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--token-env", type=Path, required=True)
    parser.add_argument("--ca", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--aiven-project", required=True)
    parser.add_argument("--gcp-project", required=True)
    args = parser.parse_args()
    cutover = Cutover(args)
    if args.action in {"migrate", "publish"}:
        getattr(cutover, args.action)()
    else:
        await getattr(cutover, args.action)()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        print(f"Stopped: {type(error).__name__}; secret-bearing details suppressed.")
        raise SystemExit(1) from None
