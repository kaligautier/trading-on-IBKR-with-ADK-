"""Check real release-image HTTP and Postman against our synthetic local database."""

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[4]
DB = "momentum-current-api-test-db"
BASE = "http://127.0.0.1:55474"
IMAGE = sys.argv[1] if len(sys.argv) > 1 else "local/momentum-api:verify"


def docker(*args: str) -> str:
    return subprocess.check_output(["docker", *args], text=True).strip()


def call(path: str, method: str = "GET", **headers: str):
    try:
        return urlopen(Request(BASE + path, headers=headers, method=method), timeout=5)  # noqa: S310 -- fixed loopback
    except HTTPError as response:
        return response


def main() -> None:
    fixture = json.loads(docker("inspect", DB))[0]
    assert fixture["Config"]["Labels"]["org.deepcopy.momentum-api-test"] == "true"
    assert docker("port", DB, "8080/tcp") == "127.0.0.1:55474"
    name, analysis_id, credential = (
        "momentum-smoke-" + uuid4().hex[:12],
        str(uuid4()),
        uuid4().hex,
    )
    auth = {"Authorization": "Bearer " + credential}
    docker(
        "exec",
        DB,
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "momentum_results_writer",
        "-d",
        "momentum",
        "-c",
        "INSERT INTO _analysis.analysis_results "  # noqa: S608 -- generated UUID only
        "(id,ticker,analysis_date,created_at,llm_provider,deep_think_llm,quick_think_llm,"
        "session_id,invocation_id,user_id) VALUES "
        f"('{analysis_id}','FIXTURE','2026-10-22','2026-10-22T12:00:00Z',"
        "'synthetic','test','test','fixture-session','fixture-invocation','fixture-user')",
    )
    try:
        docker(
            "run",
            "--rm",
            "--detach",
            "--name",
            name,
            "--network",
            "container:" + DB,
            "--env",
            "DATABASE_URL=postgresql://momentum_results_reader:local-only@localhost/momentum",
            "--env",
            "API_TOKEN=" + credential,
            IMAGE,
        )
        for _ in range(100):
            try:
                if call("/health").status == 200:
                    break
            except OSError:
                pass
            time.sleep(0.1)
        else:
            raise AssertionError("Release image did not become healthy")
        assert docker("exec", name, "id", "-u") == "10001"
        missing = call("/v1/analyses")
        assert missing.status == 401 and missing.read() == b""
        detail = call("/v1/analyses/" + analysis_id, **auth)
        assert detail.status == 200
        body = detail.read()
        assert json.loads(body)["id"] == analysis_id and b"fixture-user" not in body
        tag = detail.headers["ETag"]
        head = call("/v1/analyses/" + analysis_id, method="HEAD", **auth)
        assert head.status == 200 and head.read() == b""
        assert head.headers["ETag"] == tag and int(
            head.headers["Content-Length"]
        ) == len(body)
        cached = call("/v1/analyses/" + analysis_id, **auth, **{"If-None-Match": tag})
        assert cached.status == 304 and cached.read() == b""
        assert "Content-Length" not in cached.headers and cached.headers["ETag"] == tag
        schema = json.load(call("/openapi.json", **auth))
        expected = json.loads(
            (ROOT / "apps/backend/momentum-api/openapi.json").read_text()
        )
        assert schema == expected
        subprocess.run(
            [
                "postman",
                "collection",
                "run",
                str(ROOT / "docs/postman/momentum-api.postman_collection.json"),
                "--env-var",
                "momentum_api_base_url=" + BASE,
                "--env-var",
                "api_token=" + credential,
                "--env-var",
                "analysis_id=" + analysis_id,
                "--no-report-events",
            ],
            check=True,
        )
        traced = call(
            "/health",
            traceparent="00-1234567890abcdef1234567890abcdef-1234567890abcdef-01",
        )
        assert traced.status == 200
        logs = subprocess.check_output(
            ["docker", "logs", name], stderr=subprocess.STDOUT, text=True
        )
        events = [
            json.loads(line) for line in logs.splitlines() if line.startswith("{")
        ]
        request = next(
            event
            for event in events
            if event.get("request_id") == traced.headers["Request-ID"]
        )
        assert request["event"] == "request_completed"
        assert request["trace_id"] == "1234567890abcdef1234567890abcdef"
        assert request["parent_span_id"] == "1234567890abcdef"
        assert credential not in logs and "fixture-user" not in logs
        print(
            "Release image: non-root, storage, auth, HEAD/304, "
            "exact OpenAPI, structured logs and Postman passed."
        )
    finally:
        subprocess.run(["docker", "stop", name], check=False, capture_output=True)
        docker(
            "exec",
            DB,
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "momentum",
            "-c",
            f"DELETE FROM _analysis.analysis_results WHERE id='{analysis_id}'",  # noqa: S608 -- generated UUID only
        )


if __name__ == "__main__":
    main()
