"""Provision the dedicated existing-service database and upload secrets privately.

Run with the backend virtualenv (asyncpg). Requires the Aiven CLI to be logged in
and the Terraform foundation to exist. No credentials are printed or put in state.
"""

import asyncio
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import tempfile
import traceback
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import asyncpg
from bootstrap_database import SecretStore, require_recoverable_salt


ACCOUNT = os.environ.get("LITELLM_GCP_ACCOUNT", "")
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
AIVEN_PROJECT = os.environ.get("LITELLM_AIVEN_PROJECT", "")
SERVICE = os.environ.get("LITELLM_AIVEN_SERVICE", "")
DATABASE = "litellm"
ROOT = Path(__file__).resolve().parents[1]


def command(args, data=None):
    result = subprocess.run(args, input=data, capture_output=True, text=True)
    if result.returncode:
        # Aiven and database CLI errors can include credentials or connection URLs.
        raise RuntimeError(f"Command failed: {args[0]} {args[1]} {args[2]}")
    return result.stdout


def avn(*args):
    return command(["avn", *args, "--project", AIVEN_PROJECT])


def service():
    value = json.loads(avn("service", "get", SERVICE, "--json"))
    return value[0] if isinstance(value, list) else value


def service_user(username):
    # Current API requires include_secrets; this CLI version omits the parameter.
    # https://aiven.io/docs/tools/api/secret-redaction
    credentials = json.loads(
        (Path.home() / ".config/aiven/aiven-credentials.json").read_text()
    )
    request = Request(
        f"https://api.aiven.io/v1/project/{AIVEN_PROJECT}/service/{SERVICE}/user/{username}?include_secrets=true",
        headers={"Authorization": "Bearer " + credentials["auth_token"]},
    )
    with urlopen(request, timeout=30) as response:
        user = json.load(response)["user"]
    if not user.get("password") or user["password"] == "<redacted>":
        raise RuntimeError("Aiven did not return the service credential")
    return user


def gcloud(*args, data=None):
    return command(
        [
            "gcloud",
            *args,
            f"--project={PROJECT}",
            f"--account={ACCOUNT}",
        ],
        data=data,
    )


def upload(name, value):
    secret_id = f"litellm-{name}"
    existing = json.loads(
        gcloud(
            "secrets",
            "versions",
            "list",
            secret_id,
            "--format=json",
            "--filter=state=ENABLED",
            "--sort-by=~createTime",
            "--limit=1",
        )
    )
    if existing:
        # In particular, never automatically rotate the encryption salt on reruns.
        return existing[0]["name"].split("/")[-1]
    resource = gcloud(
        "secrets",
        "versions",
        "add",
        secret_id,
        "--data-file=-",
        "--format=value(name)",
        data=value,
    ).strip()
    return resource.split("/")[-1]


async def main():
    required = [
        "LITELLM_GCP_ACCOUNT",
        "GOOGLE_CLOUD_PROJECT",
        "LITELLM_AIVEN_PROJECT",
        "LITELLM_AIVEN_SERVICE",
        "LITELLM_AIVEN_ACCOUNT",
        "LITELLM_AIVEN_HOST",
    ]
    if any(not os.environ.get(name) for name in required):
        raise ValueError("Set all deployment variables documented in README.md")
    identity = json.loads(command(["avn", "user", "info", "--json"]))
    identity = identity[0] if isinstance(identity, list) else identity
    if identity.get("user") != os.environ["LITELLM_AIVEN_ACCOUNT"]:
        raise RuntimeError("Unexpected Aiven identity")
    metadata = service()
    params = metadata["service_uri_params"]
    if (
        metadata["state"] != "RUNNING"
        or params["host"] != os.environ["LITELLM_AIVEN_HOST"]
    ):
        raise RuntimeError("Unexpected Aiven service")

    with tempfile.TemporaryDirectory(prefix="litellm-ca-") as directory:
        ca = Path(directory) / "ca.pem"
        avn("project", "ca-get", "--target-filepath", str(ca))
        tls = ssl.create_default_context(cafile=str(ca))
        admin_user = service_user(params["user"])
        connect = dict(
            host=params["host"],
            port=int(params["port"]),
            ssl=tls,
            user=params["user"],
            password=admin_user["password"],
            timeout=30,
        )
        users = {user["username"] for user in metadata["users"]}
        databases = json.loads(avn("service", "database-list", SERVICE, "--json"))
        if DATABASE not in users:
            avn("service", "user-create", SERVICE, "--username", DATABASE)
        if DATABASE not in databases:
            avn("service", "database-create", SERVICE, "--dbname", DATABASE)
        user = service_user(DATABASE)

        admin = await asyncpg.connect(**connect, database="defaultdb")
        try:
            role = await admin.fetchrow(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication FROM pg_roles WHERE rolname=$1",
                DATABASE,
            )
            if any(role.values()):
                raise RuntimeError(
                    "Dedicated database user unexpectedly has administrative privileges"
                )
            await admin.execute("GRANT litellm TO avnadmin WITH INHERIT FALSE")
            await admin.execute("ALTER ROLE litellm CONNECTION LIMIT 12")
            await admin.execute("ALTER DATABASE litellm OWNER TO litellm")
            await admin.execute("REVOKE ALL ON DATABASE litellm FROM PUBLIC")
            await admin.execute("GRANT CONNECT ON DATABASE litellm TO avnadmin")
        finally:
            await admin.close()

        connection = await asyncpg.connect(
            **{**connect, "user": DATABASE, "password": user["password"]},
            database=DATABASE,
        )
        try:
            salt_version = SecretStore(PROJECT, ACCOUNT).existing_version("salt-key")
            await require_recoverable_salt(connection, salt_version)
            await connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            # Verify DDL/write/read with a connection-local temporary table.
            async with connection.transaction():
                await connection.execute(
                    "CREATE TEMP TABLE litellm_bootstrap_check (ok boolean)"
                )
                await connection.execute(
                    "INSERT INTO litellm_bootstrap_check VALUES (true)"
                )
                assert await connection.fetchval(
                    "SELECT ok FROM litellm_bootstrap_check"
                )
            print(
                "Dedicated Aiven database verified with certificate and hostname validation.",
                flush=True,
            )
        finally:
            await connection.close()

        query = urlencode(
            dict(
                sslmode="require",
                sslcert="/etc/database/ca.pem",
                sslaccept="strict",
                connection_limit=2,
            )
        )
        url = (
            f"postgresql://{DATABASE}:{quote(user['password'], safe='')}@"
            f"{params['host']}:{params['port']}/{DATABASE}?{query}"
        )
        payloads = {
            "database-url": url,
            "database-ca": ca.read_text(),
            "master-key": "sk-" + secrets.token_hex(32),
            "salt-key": "sk-" + secrets.token_hex(32),
            "ui-password": secrets.token_urlsafe(32),
        }
        versions = {name: upload(name, value) for name, value in payloads.items()}
    release = ROOT / "config" / "release.local.tfvars"
    if release.exists():
        print(
            "Existing release.local.tfvars preserved; enabled secret versions:",
            versions,
        )
    else:
        content = 'stage = "migrations"\nsecret_versions = {\n'
        content += "".join(
            f'  {name} = "{version}"\n' for name, version in versions.items()
        )
        content += f'}}\niap_members = ["user:{ACCOUNT}"]\n'
        fd = os.open(release, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
        print(
            "Secret versions uploaded; release.local.tfvars contains only version references."
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(
            f"Bootstrap stopped ({type(exc).__name__}); secret-bearing details suppressed."
        )
        for frame in traceback.extract_tb(exc.__traceback__):
            print(f"  {Path(frame.filename).name}:{frame.lineno} in {frame.name}")
        raise SystemExit(1) from None
