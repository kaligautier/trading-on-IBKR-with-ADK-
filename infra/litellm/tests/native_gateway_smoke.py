"""Offline native Gemini integration through real NGINX and pinned LiteLLM.

Run: python3 infra/litellm/tests/native_gateway_smoke.py
Only the provider HTTP boundary is stubbed; auth, routing, SSE, Redis quotas,
PostgreSQL usage and budgets use the actual deployed implementations.
"""

import json
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time

from smoke import ROOT, docker, image


MODEL = "native-smoke"
GENERATE = f"/v1beta/models/{MODEL}:generateContent"
STREAM = f"/v1beta/models/{MODEL}:streamGenerateContent?alt=sse"
PROMPT_MARKER = "PRIVATE_NATIVE_PROMPT_" + secrets.token_hex(12)
PAYLOAD = {"contents": [{"role": "user", "parts": [{"text": PROMPT_MARKER}]}]}


HTTP_CLIENT = """
import json, sys, urllib.request, urllib.error
route, body, key = json.load(sys.stdin)
headers = {"Content-Type": "application/json"}
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
        # No container can reach Google, metadata credentials or other internet endpoints.
        docker("network", "create", "--internal", prefix)
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
            for _ in range(60):
                if "accepting connections" in docker(
                    "exec", database, "pg_isready", "-U", "litellm", check=False
                ):
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Native test PostgreSQL did not become ready")
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
                "PASS: pinned LiteLLM behind real deployed NGINX; internal offline network",
                flush=True,
            )

            def key(rpm):
                body = {
                    "models": [MODEL],
                    "rpm_limit": rpm,
                    # Same native route scope as bootstrap_scanner_key.py.
                    "allowed_routes": ["/v1beta/models/*"],
                    "duration": "1h",
                    "max_budget": 1,
                }
                with request(bases[0], "/key/generate", body, master) as result:
                    assert result.status == 200, "Cannot provision native virtual key"
                    return json.load(result)["key"]

            native_key = key(20)
            for credential in [None, "sk-invalid-offline-key"]:
                with request(bases[0], GENERATE, PAYLOAD, credential) as result:
                    assert result.status in (401, 403), (
                        "Native route accepted anonymous/invalid key"
                    )
            for route in ["/ui", "/key/info", "/v1/chat/completions"]:
                with request(bases[0], route, PAYLOAD, master) as result:
                    assert result.status == 404, "NGINX allowlist bypassed"
            with request(bases[0], "/key/generate", {}, native_key) as result:
                assert result.status in (401, 403), (
                    "Inference key can provision admin keys"
                )
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
            with request(bases[0], GENERATE, PAYLOAD, native_key) as result:
                assert result.status == 200, (
                    "Native generation failed: " + result.read().decode()
                )
                content = json.load(result)
                assert (
                    content["candidates"][0]["content"]["parts"][0]["text"]
                    == "NATIVE_OK"
                )
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
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                rows = json.loads(
                    sql(
                        "SELECT COALESCE(json_agg(t),'[]'::json) FROM \"LiteLLM_SpendLogs\" t;"
                    )
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
            assert any(
                row.get("call_type") == "agenerate_content_stream" for row in rows
            ), "Native streaming usage was not persisted"
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
                    assert (
                        result.status in (400, 402, 403, 429)
                        and b"budget" in result.read().lower()
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


if __name__ == "__main__":
    main()
