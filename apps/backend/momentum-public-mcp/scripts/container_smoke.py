"""Check the built runtime image and its real stateless HTTP entrypoint."""

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from uuid import uuid4

from verify_live import VERSION, rpc


def docker(*arguments):
    return subprocess.check_output(["docker", *arguments], text=True).strip()


def wait_for_health(endpoint):
    for _ in range(100):
        try:
            with urllib.request.urlopen(endpoint + "/health", timeout=1) as response:
                assert json.load(response)["status"] == "healthy"
                return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(0.1)
    raise RuntimeError("Container health endpoint did not become available")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    args = parser.parse_args()
    user = docker("image", "inspect", args.image, "--format", "{{.Config.User}}")
    assert user not in {"", "0", "root"}, "Runtime must use a non-root user"
    name = "mcp-smoke-" + uuid4().hex[:12]
    docker(
        "run",
        "--detach",
        "--rm",
        "--name",
        name,
        "--publish",
        "127.0.0.1::8080",
        "--env",
        "SUGGESTION_HASH_SECRET=disposable-container-smoke",
        "--env",
        "MOMENTUM_API_USE_IAM=false",
        args.image,
    )
    try:
        port = docker("port", name, "8080/tcp").rsplit(":", 1)[1]
        endpoint = "http://127.0.0.1:" + port
        wait_for_health(endpoint)
        discovery = rpc(endpoint + "/", "server/discover")
        assert VERSION in discovery["supportedVersions"]
        assert len(rpc(endpoint + "/", "tools/list")["tools"]) == 7
        invalid = rpc(
            endpoint + "/",
            "tools/call",
            {
                "name": "get_analysis",
                "arguments": {"analysis_id": "invalid-uuid"},
            },
        )
        assert invalid["isError"]
        packages = json.loads(
            docker(
                "exec",
                name,
                "python",
                "-c",
                (
                    "import importlib.metadata as m,json; "
                    "print(json.dumps({d.metadata['Name'].lower():d.version "
                    "for d in m.distributions()}))"
                ),
            )
        )
        assert packages["fastmcp"] == packages["fastmcp-slim"] == "4.1.3"
        assert not {"hatchling", "pytest", "ruff"} & packages.keys()
        print(
            json.dumps(
                {
                    "image": args.image,
                    "user": user,
                    "protocol": VERSION,
                    "tools": 7,
                    "validation_error": True,
                    "runtime_only": True,
                }
            )
        )
    finally:
        docker("stop", name)


if __name__ == "__main__":
    main()
