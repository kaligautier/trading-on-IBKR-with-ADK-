"""Offline native Gemini integration through real NGINX and pinned LiteLLM.

Run: python3 infra/litellm/tests/native_gateway_smoke.py
Only the provider HTTP boundary is stubbed; auth, routing, SSE, Redis quotas,
PostgreSQL usage and budgets use the actual deployed implementations.
"""

import json
import hashlib
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time

from smoke import ROOT, docker, image
from terraform_policy_smoke import TerraformPolicy


MODEL = "native-smoke"
GENERATE = f"/v1beta/models/{MODEL}:generateContent"
STREAM = f"/v1beta/models/{MODEL}:streamGenerateContent?alt=sse"
PROMPT_MARKER = "PRIVATE_NATIVE_PROMPT_" + secrets.token_hex(12)
PAYLOAD = {"contents": [{"role": "user", "parts": [{"text": PROMPT_MARKER}]}]}


HTTP_CLIENT = """
import json, sys, urllib.request, urllib.error
route, body, key = json.load(sys.stdin)
# Match the ADK GenAI client: its required SDK key is a placeholder, while
# Authorization contains the actual virtual key. Verify bearer precedence.
headers = {"Content-Type": "application/json", "x-goog-api-key": "litellm-proxy"}
if key: headers["Authorization"] = "Bearer " + key
req = urllib.request.Request("http://127.0.0.1:4000" + route,
    data=json.dumps(body).encode() if body is not None else None, headers=headers)
try: response = urllib.request.urlopen(req, timeout=20)
except urllib.error.HTTPError as error: response = error
print(json.dumps({"status": response.status, "headers": dict(response.headers)}), flush=True)
with response:
    for line in response:
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
"""


class ContainerResponse:
    """Read real HTTP frames inside the isolated Docker network, including SSE."""

    def __init__(self, container, route, body, key):
        self.process = subprocess.Popen(
            ["docker", "exec", "-i", container, "python", "-u", "-c", HTTP_CLIENT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.process.stdin.write(json.dumps([route, body, key]).encode())
        self.process.stdin.close()
        metadata = self.process.stdout.readline()
        if not metadata:
            self.process.wait()
            raise OSError("Offline native HTTP client could not reach gateway")
        metadata = json.loads(metadata)
        self.status, self.headers = metadata["status"], metadata["headers"]

    def read(self):
        return self.process.stdout.read()

    def readline(self):
        return self.process.stdout.readline()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.read()
        self.process.stdout.close()
        self.process.wait(timeout=25)


def request(base, route, body=None, key=None):
    return ContainerResponse(base, route, body, key)


def ready(container, base):
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        if docker("inspect", "--format", "{{.State.Running}}", container) != "true":
            raise RuntimeError("Native proxy exited during startup")
        try:
            with request(base, "/health/readiness") as result:
                if result.status == 200:
                    return
        except OSError:
            pass
        time.sleep(2)
    raise RuntimeError("Native proxy did not become ready")


def main():
    prefix = "litellm-native-" + secrets.token_hex(4)
    database, redis, provider = [
        prefix + suffix for suffix in ["-db", "-redis", "-provider"]
    ]
    proxies = [prefix + "-proxy", prefix + "-sibling"]
    gateways = [prefix + "-gateway", prefix + "-sibling-gateway"]
    containers = gateways + proxies + [provider, database, redis]
    proxy_image = image("proxy_digest", "litellm")
    digest = re.search(
        r'default\s*=\s*"(sha256:[0-9a-f]{64})"',
        (ROOT / "gateway_routes.tf").read_text(),
    )[1]
    gateway_image = "ghcr.io/nginx/nginx-unprivileged@" + digest
    master = "sk-" + secrets.token_hex(32)

    def sql(query):
        return docker(
            "exec",
            database,
            "psql",
            "-U",
            "litellm",
            "-d",
            "litellm",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-c",
            query,
        )

    with tempfile.TemporaryDirectory(prefix=prefix) as directory:
        path = Path(directory)
        settings = json.loads((ROOT / "config/runtime-settings.json").read_text())
        config = {
            "model_list": [
                {
                    "model_name": alias,
                    "litellm_params": {
                        "model": "gemini/gemini-2.5-flash",
                        "api_key": "offline-only",
                        "api_base": f"http://{provider}:8080",
                    },
                }
                for alias in [MODEL, "forbidden-model"]
            ],
            "general_settings": {
                **settings["general_settings"],
                "master_key": "os.environ/LITELLM_MASTER_KEY",
                "database_url": "os.environ/DATABASE_URL",
                "database_connection_pool_limit": 2,
                "allow_requests_on_db_unavailable": False,
                "proxy_batch_write_at": 1,
                "proxy_budget_rescheduler_min_time": 1,
                "proxy_budget_rescheduler_max_time": 2,
            },
            "litellm_settings": {
                **settings["litellm_settings"],
                "max_budget": 1,
                "budget_duration": "30d",
            },
            "router_settings": {
                **settings["router_settings"],
                "redis_host": "os.environ/REDIS_HOST",
                "redis_port": "os.environ/REDIS_PORT",
            },
        }
        (path / "config.json").write_text(json.dumps(config))
        env = {
            "DATABASE_URL": f"postgresql://litellm:offline-only@{database}:5432/litellm",
            "LITELLM_MASTER_KEY": master,
            "LITELLM_SALT_KEY": "sk-" + secrets.token_hex(32),
            "DISABLE_SCHEMA_UPDATE": "true",
            "LITELLM_MODE": "PRODUCTION",
            "REDIS_HOST": redis,
            "REDIS_PORT": "6379",
            "LITELLM_LOG": "WARNING",
        }
        (path / "runtime.env").write_text(
            "".join(f"{key}={value}\n" for key, value in env.items())
        )
        (path / "runtime.env").chmod(0o600)
        (path / "migration.env").write_text(
            "DATABASE_URL=" + env["DATABASE_URL"] + "\n"
        )
        (path / "migration.env").chmod(0o600)
        # No cloud credentials: model calls target only the local provider stub.
        # A loopback-only published port lets the host Terraform provider connect.
        docker("network", "create", prefix)
        try:
            docker(
                "run",
                "-d",
                "--name",
                database,
                "--network",
                prefix,
                "-e",
                "POSTGRES_USER=litellm",
                "-e",
                "POSTGRES_DB=litellm",
                "-e",
                "POSTGRES_PASSWORD=offline-only",
                "postgres:17",
            )
            docker("run", "-d", "--name", redis, "--network", prefix, "redis:7-alpine")
            docker(
                "create",
                "--name",
                provider,
                "--network",
                prefix,
                "--entrypoint",
                "python",
                proxy_image,
                "/tmp/native_provider_stub.py",
            )
            docker(
                "cp",
                str(Path(__file__).with_name("native_provider_stub.py")),
                provider + ":/tmp/native_provider_stub.py",
            )
            docker("start", provider)
            wait_for_postgres(database)
            docker(
                "run",
                "--rm",
                "--network",
                prefix,
                "--env-file",
                str(path / "migration.env"),
                image("migrations_digest", "litellm-migrations"),
            )
            bases = []
            for proxy, gateway in zip(proxies, gateways):
                docker(
                    "create",
                    "--name",
                    proxy,
                    "-p",
                    "127.0.0.1::4000",
                    "--network",
                    prefix,
                    "--env-file",
                    str(path / "runtime.env"),
                    proxy_image,
                    "--config",
                    "/tmp/litellm-config.yaml",
                    "--port",
                    "4001",
                    "--num_workers",
                    "1",
                )
                docker(
                    "cp", str(path / "config.json"), proxy + ":/tmp/litellm-config.yaml"
                )
                docker("start", proxy)
                docker(
                    "create",
                    "--name",
                    gateway,
                    "--network",
                    "container:" + proxy,
                    "--entrypoint",
                    "nginx",
                    gateway_image,
                    "-c",
                    "/tmp/gateway-nginx.conf",
                    "-g",
                    "daemon off;",
                )
                docker(
                    "cp",
                    str(ROOT / "config/gateway-nginx.conf"),
                    gateway + ":/tmp/gateway-nginx.conf",
                )
                docker("start", gateway)
                base = proxy
                ready(proxy, base)
                bases.append(base)
            print(
                "PASS: pinned LiteLLM behind real deployed NGINX; local provider stub",
                flush=True,
            )

            def key(rpm, team=True):
                body = {
                    "models": [MODEL],
                    "rpm_limit": rpm,
                    # Same native route scope as the Terraform policy.
                    "allowed_routes": ["/v1beta/models/*"],
                    "duration": "1h",
                    **({"key_alias": "legacy-scanner"} if not team else {}),
                    "team_id": "agents" if team else None,
                    "max_budget": 3,
                    "budget_duration": "1d",
                }
                with request(bases[0], "/key/generate", body, master) as result:
                    assert result.status == 200, "Cannot provision native virtual key"
                    return json.load(result)["key"]

            port = json.loads(docker("inspect", proxies[0]))[0]["NetworkSettings"][
                "Ports"
            ]["4000/tcp"][0]["HostPort"]
            policy = TerraformPolicy(path, "http://127.0.0.1:" + port, master, [MODEL])
            legacy_key = key(20, team=False)
            legacy_token = hashlib.sha256(legacy_key.encode()).hexdigest()
            sql(
                f"""UPDATE "LiteLLM_VerificationToken" SET spend = 2.5, budget_duration = '30d', max_budget = 10 WHERE token = '{legacy_token}';"""
            )
            expiry = sql(
                f"""SELECT expires FROM "LiteLLM_VerificationToken" WHERE token = '{legacy_token}';"""
            )
            weekly_key = "sk-" + secrets.token_hex(32)
            terraform_agents = {
                "scanner": {"existing_token_id": legacy_token},
                "weekly": {"max_budget": 4, "budget_duration": "7d"},
            }
            terraform_keys = {"scanner": legacy_key, "weekly": weekly_key}
            policy.apply(terraform_agents, terraform_keys)
            policy.run("state", "rm", "module.policy.litellm_team.agents")
            policy.env["TF_VAR_import_team"] = "true"
            for budget in [0, 5]:
                sql(
                    f"""UPDATE "LiteLLM_TeamTable" SET max_budget = {budget} WHERE team_id = 'agents';"""
                )
                policy.reject_team_budget()
            sql(
                """UPDATE "LiteLLM_TeamTable" SET max_budget = NULL WHERE team_id = 'agents';"""
            )
            policy.apply(terraform_agents, terraform_keys, import_team=True)
            print(
                "PASS: zero/positive team caps rejected; null budget restored without key changes",
                flush=True,
            )
            assert (
                float(
                    sql(
                        f"""SELECT spend FROM "LiteLLM_VerificationToken" WHERE token = '{legacy_token}';"""
                    )
                )
                == 2.5
            )
            assert (
                sql(
                    f"""SELECT expires FROM "LiteLLM_VerificationToken" WHERE token = '{legacy_token}';"""
                )
                == expiry
            )
            assert (
                sql(
                    f"""SELECT key_alias FROM "LiteLLM_VerificationToken" WHERE token = '{legacy_token}';"""
                )
                == "legacy-scanner"
            )
            print(
                "PASS: real Terraform import/migration, weekly key creation, preserved spend/expiry, no-op and secret-free state",
                flush=True,
            )

            native_key = key(20)
            verify_access_controls(bases, native_key, master)
            verify_native_responses(bases, native_key)
            limited_key = key(2)
            statuses = []
            for base in [bases[0], bases[1], bases[0]]:
                with request(base, GENERATE, PAYLOAD, limited_key) as result:
                    statuses.append(result.status)
            assert statuses == [200, 200, 429], f"Native shared RPM failed: {statuses}"
            print(
                "PASS: native Gemini RPM quota shared across two proxy instances",
                flush=True,
            )
            rows = verify_persisted_usage(sql)
            budget_key, other_agent = legacy_key, weekly_key
            token = hashlib.sha256(budget_key.encode()).hexdigest()
            assert "UPDATE 1" in sql(
                'UPDATE "LiteLLM_VerificationToken" SET spend = 3.01 '
                f"WHERE token = '{token}';"
            )
            for index, (proxy, gateway) in enumerate(zip(proxies, gateways)):
                docker("stop", gateway)
                docker("restart", proxy)
                docker("start", gateway)
                ready(proxy, proxy)
                with request(proxy, GENERATE, PAYLOAD, budget_key) as result:
                    error = json.loads(result.read()).get("error", {})
                    assert (
                        result.status == 422 and error.get("type") == "budget_exceeded"
                    ), "Daily agent budget did not deny inference"
                with request(proxy, GENERATE, PAYLOAD, other_agent) as result:
                    assert result.status == 200, (
                        "One agent exhausted another agent's budget"
                    )
            current_port = json.loads(docker("inspect", proxies[0]))[0][
                "NetworkSettings"
            ]["Ports"]["4000/tcp"][0]["HostPort"]
            policy.env["TF_VAR_base_url"] = "http://127.0.0.1:" + current_port
            policy.apply(terraform_agents, terraform_keys)
            assert (
                float(
                    sql(
                        f"""SELECT spend FROM "LiteLLM_VerificationToken" WHERE token = '{token}';"""
                    )
                )
                >= 3
            ), "Reconciliation cleared spend"
            assert "UPDATE 1" in sql(
                "UPDATE \"LiteLLM_VerificationToken\" SET budget_reset_at = NOW() - INTERVAL '1 minute' "
                f"WHERE token = '{token}';"
            )
            wait_for_budget_reset(sql, token)
            # Flush process-local auth caches, then verify the persisted renewal.
            for proxy, gateway in zip(proxies, gateways):
                docker("stop", gateway)
                docker("restart", proxy)
                docker("start", gateway)
                ready(proxy, proxy)
                with request(proxy, GENERATE, PAYLOAD, budget_key) as result:
                    assert result.status == 200, "Agent budget did not renew"
            print(
                "PASS: agents team, independent $3 daily budgets, preserved spend and elapsed-window renewal",
                flush=True,
            )
            assert "UPDATE 1" in sql(
                "UPDATE \"LiteLLM_UserTable\" SET spend = 1.01 WHERE user_id = 'litellm-proxy-budget';"
            )
            # Stop the sidecar before restarting its network namespace owner.
            for index, (proxy, gateway) in enumerate(zip(proxies, gateways)):
                docker("stop", gateway)
                docker("restart", proxy)
                docker("start", gateway)
                bases[index] = proxy
                ready(proxy, bases[index])
                with request(bases[index], GENERATE, PAYLOAD, native_key) as result:
                    error = json.loads(result.read()).get("error", {})
                    assert (
                        result.status == 422 and error.get("type") == "budget_exceeded"
                    ), (
                        "Persisted global budget did not deny native requests after restart"
                    )
            rows_after_restart = json.loads(
                sql(
                    "SELECT COALESCE(json_agg(t),'[]'::json) FROM \"LiteLLM_SpendLogs\" t;"
                )
            )
            assert len(rows_after_restart) >= len(
                rows
            ) and PROMPT_MARKER not in json.dumps(rows_after_restart)
            print(
                "PASS: persisted global budget denies native inference on both restarted proxies",
                flush=True,
            )
        finally:
            docker("rm", "-f", *containers, check=False)
            docker("network", "rm", prefix, check=False)


def verify_access_controls(bases, native_key, master):
    for credential in [None, "sk-invalid-offline-key"]:
        with request(bases[0], GENERATE, PAYLOAD, credential) as result:
            assert result.status in (401, 403), (
                "Native route accepted anonymous/invalid key"
            )
    for route in ["/ui", "/v1/chat/completions"]:
        with request(bases[0], route, PAYLOAD, master) as result:
            assert result.status == 404, "NGINX allowlist bypassed"
    with request(bases[0], "/key/generate", {}, native_key) as result:
        assert result.status in (401, 403), "Inference key can provision admin keys"
    for route, body in [
        ("/key/info", None),
        ("/team/info", None),
        ("/key/update", {}),
        ("/team/new", {}),
        ("/team/update", {}),
        ("/team/delete", {}),
    ]:
        with request(bases[0], route, body, native_key) as result:
            assert result.status in (401, 403), "Inference key reached administration"
    with request(
        bases[0],
        "/v1beta/models/forbidden-model:generateContent",
        PAYLOAD,
        native_key,
    ) as result:
        assert result.status in (401, 403), "Native model allowlist bypassed"
    print(
        "PASS: native auth, model restrictions and deployed NGINX allowlist",
        flush=True,
    )


def verify_native_responses(bases, native_key):
    with request(bases[0], GENERATE, PAYLOAD, native_key) as result:
        assert result.status == 200, (
            "Native generation failed: " + result.read().decode()
        )
        content = json.load(result)
        assert content["candidates"][0]["content"]["parts"][0]["text"] == "NATIVE_OK"
        assert content["usageMetadata"]["totalTokenCount"] == 30
    started = time.monotonic()
    with request(bases[0], STREAM, PAYLOAD, native_key) as result:
        assert result.status == 200, (
            "Native streaming failed: " + result.read().decode()
        )
        assert "text/event-stream" in result.headers["Content-Type"]
        frames, arrived = [], []
        while line := result.readline():
            if line.startswith(b"data: "):
                arrived.append(time.monotonic())
                frames.append(json.loads(line[6:]))
        assert len(frames) == 2, "Native stream lost Gemini SSE frames"
        # Measure data frames, not EOF: the provider only pauses BETWEEN
        # frames. Buffering headers and the entire body collapses this gap.
        assert arrived[1] - arrived[0] >= 0.8, (
            "Native SSE frames were buffered until completion"
        )
        print(
            f"Native SSE timing: first frame {arrived[0] - started:.2f}s "
            f"after request; frame gap {arrived[1] - arrived[0]:.2f}s",
            flush=True,
        )
        text = "".join(
            frame["candidates"][0]["content"]["parts"][0].get("text", "")
            for frame in frames
        )
        assert (
            text == "NATIVE_STREAM_OK"
            and frames[-1]["usageMetadata"]["totalTokenCount"] == 30
        )
    print(
        "PASS: native generateContent and incremental Gemini SSE with usage",
        flush=True,
    )


def verify_persisted_usage(sql):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        rows = json.loads(
            sql("SELECT COALESCE(json_agg(t),'[]'::json) FROM \"LiteLLM_SpendLogs\" t;")
        )
        global_spend = float(
            sql(
                'SELECT COALESCE(MAX(spend), 0) FROM "LiteLLM_UserTable" '
                "WHERE user_id = 'litellm-proxy-budget';"
            )
        )
        if (
            len([row for row in rows if row.get("total_tokens") == 30]) >= 4
            and global_spend > 0
        ):
            break
        time.sleep(1)
    else:
        raise AssertionError(
            "Native usage or global budget spend did not persist to PostgreSQL"
        )
    assert PROMPT_MARKER not in json.dumps(rows), (
        "Native prompt persisted in spend logs"
    )
    assert any(row.get("call_type") == "agenerate_content_stream" for row in rows), (
        "Native streaming usage was not persisted"
    )
    assert any(row.get("spend", 0) > 0 for row in rows), (
        "Native usage has no cost accounting"
    )
    print(
        "PASS: native usage and spend persist without prompt payloads",
        flush=True,
    )
    print(
        "PASS: native requests increment persisted global budget spend",
        flush=True,
    )
    return rows


def wait_for_budget_reset(sql, token):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if (
            float(
                sql(
                    f"""SELECT spend FROM "LiteLLM_VerificationToken" WHERE token = '{token}';"""
                )
            )
            < 3
        ):
            break
        time.sleep(1)
    else:
        raise AssertionError("Daily budget scheduler did not reset an elapsed window")


def wait_for_postgres(database):
    for _ in range(60):
        if "accepting connections" in docker(
            "exec", database, "pg_isready", "-U", "litellm", check=False
        ):
            break
        time.sleep(1)
    else:
        raise RuntimeError("Native test PostgreSQL did not become ready")


if __name__ == "__main__":
    main()
