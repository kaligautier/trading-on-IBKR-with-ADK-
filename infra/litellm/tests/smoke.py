"""Exercise the pinned upstream images against disposable local PostgreSQL.

Run from any directory: python3 infra/litellm/tests/smoke.py
Requires Docker. Uses no cloud credentials and makes no model inference calls.
"""

import http.cookiejar
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
VARIABLES = (ROOT / "variables.tf").read_text()


def image(variable, name):
    block = VARIABLES.split(f'variable "{variable}"', 1)[1]
    digest = re.search(r'default\s*=\s*"(sha256:[0-9a-f]{64})"', block)[1]
    return f"ghcr.io/berriai/{name}@{digest}"


def docker(*args, check=True):
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(f"Docker {args[0]} failed: {result.stderr[-1500:]}")
    return result.stdout.strip()


def main():
    prefix = f"litellm-smoke-{secrets.token_hex(4)}"
    database, proxy = f"{prefix}-db", f"{prefix}-proxy"
    redis, sibling = f"{prefix}-redis", f"{prefix}-sibling"
    master = "sk-" + secrets.token_hex(32)
    password = secrets.token_hex(24)
    migrations = image("migrations_digest", "litellm-migrations")
    proxy_image = image("proxy_digest", "litellm")
    cookies = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))

    with tempfile.TemporaryDirectory(prefix="litellm-smoke-") as temporary:
        path = Path(temporary)
        config = {
            "model_list": [
                {
                    "model_name": "smoke-model",
                    "litellm_params": {
                        "model": "vertex_ai/gemini-3.8-flash",
                        "vertex_project": "local-smoke-only",
                        "vertex_location": "eu",
                    },
                }
            ],
            "general_settings": {
                "master_key": "os.environ/LITELLM_MASTER_KEY",
                "database_url": "os.environ/DATABASE_URL",
                "database_connection_pool_limit": 2,
                "allow_requests_on_db_unavailable": False,
                "store_model_in_db": True,
            },
        }
        settings = json.loads((ROOT / "config/runtime-settings.json").read_text())
        config["general_settings"].update(settings["general_settings"])
        config["litellm_settings"] = settings["litellm_settings"]
        config["litellm_settings"].update({"max_budget": 1, "budget_duration": "30d"})
        config["router_settings"] = settings["router_settings"]
        config["router_settings"].update(
            {
                "redis_host": "os.environ/REDIS_HOST",
                "redis_port": "os.environ/REDIS_PORT",
            }
        )
        # Offline upstream response exercises proxy auth/routing without paid calls.
        config["model_list"].append(
            {
                "model_name": "provider-smoke",
                "litellm_params": {
                    "model": "openai/gpt-4o-mini",
                    "api_key": "os.environ/OPENAI_API_KEY",
                    "mock_response": "PROVIDER_OK",
                },
            }
        )
        (path / "config.json").write_text(json.dumps(config))
        env = {
            "DATABASE_URL": f"postgresql://litellm:local-smoke-only@{database}:5432/litellm?connection_limit=2",
            "LITELLM_MASTER_KEY": master,
            "LITELLM_SALT_KEY": "sk-" + secrets.token_hex(32),
            "UI_USERNAME": "admin",
            "UI_PASSWORD": password,
            "DISABLE_SCHEMA_UPDATE": "true",
            "STORE_MODEL_IN_DB": "True",
            "DOCS_URL": "/docs",
            "ROOT_REDIRECT_URL": "/ui",
            "LITELLM_LOG": "INFO",
            "LITELLM_MODE": "PRODUCTION",
            "OPENAI_API_KEY": "local-smoke-only",
            "REDIS_HOST": redis,
            "REDIS_PORT": "6378",
            "REDIS_SSL": "true",
            "REDIS_SSL_CA_CERTS": "/tmp/redis-ca.pem",
            "REDIS_SSL_CERT_REQS": "required",
            "REDIS_SSL_CHECK_HOSTNAME": "true",
            "REDIS_USERNAME": "default",
            "REDIS_PASSWORD": "local-smoke-only",
        }
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(path / "redis.key"),
                "-out",
                str(path / "redis.crt"),
                "-subj",
                "/CN=" + redis,
                "-addext",
                "subjectAltName=DNS:" + redis,
                "-days",
                "1",
            ],
            check=True,
            capture_output=True,
        )
        os.chmod(path / "redis.key", 0o600)
        (path / "runtime.env").write_text("".join(f"{k}={v}\n" for k, v in env.items()))
        (path / "migration.env").write_text(f"DATABASE_URL={env['DATABASE_URL']}\n")
        os.chmod(path / "runtime.env", 0o600)
        os.chmod(path / "migration.env", 0o600)
        docker("network", "create", prefix)
        try:
            docker(
                "create",
                "--name",
                redis,
                "--network",
                prefix,
                "--user",
                "0",
                "--entrypoint",
                "redis-server",
                "redis:7-alpine",
                "--requirepass",
                "local-smoke-only",
                "--port",
                "0",
                "--tls-port",
                "6378",
                "--tls-cert-file",
                "/tmp/redis.crt",
                "--tls-key-file",
                "/tmp/redis.key",
                "--tls-ca-cert-file",
                "/tmp/redis.crt",
                "--tls-auth-clients",
                "no",
                "--save",
                "",
                "--appendonly",
                "no",
            )
            for filename in ["redis.crt", "redis.key"]:
                docker("cp", str(path / filename), redis + ":/tmp/" + filename)
            docker("start", redis)
            for _ in range(30):
                if (
                    docker(
                        "exec",
                        redis,
                        "redis-cli",
                        "--no-auth-warning",
                        "-a",
                        "local-smoke-only",
                        "--tls",
                        "-p",
                        "6378",
                        "--cacert",
                        "/tmp/redis.crt",
                        "ping",
                        check=False,
                    )
                    == "PONG"
                ):
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError("Redis TLS did not become ready")
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
                "POSTGRES_PASSWORD=local-smoke-only",
                "postgres:17",
            )
            for _ in range(60):
                if "accepting connections" in docker(
                    "exec", database, "pg_isready", "-U", "litellm", check=False
                ):
                    break
                time.sleep(1)
            else:
                raise RuntimeError("PostgreSQL did not become ready")
            for attempt in range(2):
                docker(
                    "run",
                    "--rm",
                    "--network",
                    prefix,
                    "--env-file",
                    str(path / "migration.env"),
                    migrations,
                )
                print(
                    f"PASS: official migration job, execution {attempt + 1}", flush=True
                )
            docker(
                "create",
                "--name",
                proxy,
                "--network",
                prefix,
                "--env-file",
                str(path / "runtime.env"),
                "-p",
                "127.0.0.1::4000",
                proxy_image,
                "--config",
                "/tmp/litellm-config.yaml",
                "--port",
                "4000",
                "--num_workers",
                "1",
            )
            # Docker VM hosts may not share the host's temporary directory.
            docker("cp", str(path / "config.json"), f"{proxy}:/tmp/litellm-config.yaml")
            docker("cp", str(path / "redis.crt"), f"{proxy}:/tmp/redis-ca.pem")
            docker("start", proxy)
            base = "http://" + docker("port", proxy, "4000/tcp")

            def request(route, body=None, auth=None, form=False):
                headers = {}
                if auth:
                    headers["Authorization"] = f"Bearer {auth}"
                if body is not None:
                    headers["Content-Type"] = (
                        "application/x-www-form-urlencoded"
                        if form
                        else "application/json"
                    )
                    body = (
                        urllib.parse.urlencode(body) if form else json.dumps(body)
                    ).encode()
                req = urllib.request.Request(base + route, data=body, headers=headers)
                try:
                    with client.open(req, timeout=15) as response:
                        return response.status, response.read(), response.geturl()
                except urllib.error.HTTPError as error:
                    return error.code, error.read(), error.geturl()

            def ready(container=proxy):
                deadline = time.monotonic() + 240
                last_result = "No HTTP response"
                while time.monotonic() < deadline:
                    if (
                        docker("inspect", "--format", "{{.State.Running}}", container)
                        != "true"
                    ):
                        raise RuntimeError("Proxy exited during startup")
                    try:
                        status, _, _ = request("/health/readiness")
                        last_result = f"HTTP {status}"
                        if status == 200:
                            return
                    except (OSError, urllib.error.URLError) as error:
                        last_result = str(error)
                    time.sleep(2)
                raise RuntimeError(f"Proxy did not become ready: {last_result}")

            ready()
            status, body, _ = request("/ui/")
            assert status == 200 and b"<html" in body.lower(), "UI HTML unavailable"
            assets = re.findall(rb'<script[^>]+src="([^"]+)"', body)
            assert assets, "UI contains no JavaScript assets"
            for asset in assets[:3]:
                route = urllib.parse.urlsplit(asset.decode()).path
                assert request(route)[0] == 200, f"UI asset unavailable: {route}"
            print("PASS: readiness, UI HTML and JavaScript assets", flush=True)
            assert request("/v1/models")[0] in (401, 403), (
                "API accepts anonymous requests"
            )
            status, body, _ = request("/v1/models", auth=master)
            assert status == 200 and "smoke-model" in body.decode(), (
                "Configured model missing"
            )
            print(
                "PASS: anonymous API denied; master key lists the configured model",
                flush=True,
            )
            status, body, url = request(
                "/login", {"username": "admin", "password": password}, form=True
            )
            assert status == 200 and (
                "token=" in url or any(c.name == "token" for c in cookies)
            ), "Admin login did not establish a session"
            print("PASS: Admin UI login establishes a session", flush=True)
            status, body, _ = request(
                "/key/generate",
                {
                    "key_alias": "smoke-persistence",
                    "duration": "1h",
                    "max_budget": 1,
                    "models": ["provider-smoke"],
                    "rpm_limit": 10,
                    "allowed_routes": ["/v1/chat/completions"],
                },
                auth=master,
            )
            assert status == 200, "Could not create a virtual key"
            key = json.loads(body)["key"]
            # Do not let the admin browser session authenticate these API checks.
            cookies.clear()
            payload = {
                "model": "provider-smoke",
                "messages": [{"role": "user", "content": "privacy-smoke"}],
            }
            status, body, _ = request("/v1/chat/completions", payload, auth=key)
            assert status == 200 and b"PROVIDER_OK" in body, (
                "Scoped provider inference failed"
            )
            assert request("/key/generate", {"key_alias": "forbidden"}, auth=key)[
                0
            ] in (401, 403), "Inference key can create admin keys"
            payload["model"] = "smoke-model"
            assert request("/v1/chat/completions", payload, auth=key)[0] in (
                401,
                403,
            ), "Model allowlist bypassed"
            print(
                "PASS: provider routing, inference-only routes and model restrictions",
                flush=True,
            )
            docker("restart", proxy)
            # Docker can allocate a different ephemeral host port on restart.
            restarted_base = "http://" + docker("port", proxy, "4000/tcp")
            print(
                f"Restart changed ephemeral port: {restarted_base != base}", flush=True
            )
            base = restarted_base
            ready()
            status, body, _ = request(
                "/key/info?" + urllib.parse.urlencode({"key": key}), auth=master
            )
            assert status == 200 and "smoke-persistence" in body.decode(), (
                "Virtual key did not survive restart"
            )
            print("PASS: virtual key persists across proxy restart", flush=True)
            docker(
                "create",
                "--name",
                sibling,
                "--network",
                prefix,
                "--env-file",
                str(path / "runtime.env"),
                "-p",
                "127.0.0.1::4000",
                proxy_image,
                "--config",
                "/tmp/litellm-config.yaml",
                "--port",
                "4000",
                "--num_workers",
                "1",
            )
            docker(
                "cp", str(path / "config.json"), f"{sibling}:/tmp/litellm-config.yaml"
            )
            docker("cp", str(path / "redis.crt"), f"{sibling}:/tmp/redis-ca.pem")
            docker("start", sibling)
            first_base = base
            base = "http://" + docker("port", sibling, "4000/tcp")
            ready(sibling)
            sibling_base = base
            base = first_base
            status, body, _ = request(
                "/key/generate",
                {
                    "models": ["provider-smoke"],
                    "rpm_limit": 2,
                    "allowed_routes": ["/v1/chat/completions"],
                },
                auth=master,
            )
            assert status == 200
            limited_key = json.loads(body)["key"]
            payload["model"] = "provider-smoke"
            statuses = []
            for endpoint in [first_base, sibling_base, first_base]:
                base = endpoint
                statuses.append(
                    request("/v1/chat/completions", payload, auth=limited_key)[0]
                )
            assert statuses == [200, 200, 429], (
                f"Cross-instance RPM limit failed: {statuses}"
            )
            print(
                "PASS: two proxy instances enforce a shared RPM quota over verified Redis TLS",
                flush=True,
            )
            tls_check = """
import certifi
import os
from urllib.parse import urlencode
from litellm._redis import get_redis_client
from redis.exceptions import ConnectionError
query = urlencode({
    "ssl_ca_certs": os.environ["REDIS_SSL_CA_CERTS"],
    "ssl_cert_reqs": "required",
    "ssl_check_hostname": "true",
})
os.environ["REDIS_URL"] = (
    "rediss://default:local-smoke-only@" + os.environ["REDIS_HOST"] + ":6378?" + query
)
url_client = get_redis_client()
assert url_client.connection_pool.connection_kwargs["ssl_check_hostname"] is True
assert url_client.ping() is True
print("PASS: REDIS_URL preserves explicit TLS options and authenticates")
del os.environ["REDIS_URL"]
try:
    get_redis_client(ssl_ca_certs=certifi.where()).ping()
except ConnectionError as error:
    assert "CERTIFICATE_VERIFY_FAILED" in str(error)
    print("PASS: Redis rejects an untrusted server certificate")
else:
    raise AssertionError("Redis TLS certificate verification was bypassed")
"""
            print(docker("exec", proxy, "python", "-c", tls_check), flush=True)
            # Arrange: simulate overspend only in this disposable test database.
            updated = docker(
                "exec", database, "psql", "-U", "litellm", "-d", "litellm",
                "-v", "ON_ERROR_STOP=1", "-c",
                'UPDATE "LiteLLM_UserTable" SET spend = 1.01 '
                "WHERE user_id = 'litellm-proxy-budget';",
            )
            assert "UPDATE 1" in updated, "Global budget aggregate was not initialized"
            # Restart to reload persisted spend instead of waiting for cache expiry.
            for container in [proxy, sibling]:
                docker("restart", container)
                base = "http://" + docker("port", container, "4000/tcp")
                ready(container)
                # Act / Assert: a valid, under-budget key is blocked by the global cap.
                status, body, _ = request("/v1/chat/completions", payload, auth=key)
                assert status in (400, 402, 403, 429) and b"budget" in body.lower(), (
                    "Global budget did not block inference on " + container
                )
            print("PASS: global budget blocks inference on both proxies after restart", flush=True)
        except Exception:
            result = subprocess.run(
                ["docker", "logs", "--tail", "60", proxy],
                capture_output=True,
                text=True,
            )
            diagnostic = result.stdout + result.stderr
            for key in (
                "DATABASE_URL",
                "LITELLM_MASTER_KEY",
                "LITELLM_SALT_KEY",
                "UI_PASSWORD",
            ):
                diagnostic = diagnostic.replace(env[key], "[REDACTED]")
            diagnostic = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", diagnostic)
            diagnostic = re.sub(r"(token|key)=[^\s&\"]+", r"\1=[REDACTED]", diagnostic)
            print(diagnostic, flush=True)
            raise
        finally:
            # Only containers and network created by this test are removed.
            docker("rm", "-f", proxy, sibling, database, redis, check=False)
            docker("network", "rm", prefix, check=False)


if __name__ == "__main__":
    main()
