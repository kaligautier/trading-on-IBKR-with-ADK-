"""Run the real MCP against local Postman upstreams, then clean up both groups."""

import argparse
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ready(url, process):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError(f"Server exited with {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except urllib.error.HTTPError:
            return  # A defined HTTP error still proves the listener is up.
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.1)
    raise RuntimeError(f"Server did not listen at {url}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulation-port", type=int, default=4907)
    parser.add_argument("--mcp-port", type=int, default=8107)
    args = parser.parse_args()
    for port in (args.simulation_port, args.mcp_port):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))  # Never test an unrelated existing server.
    processes = []
    with tempfile.TemporaryDirectory(prefix="mcp-simulation-") as directory:
        log_path = Path(directory) / "upstreams.ndjson"
        with log_path.open("w+") as log:
            try:
                sim = subprocess.Popen(
                    [
                        "postman",
                        "simulation",
                        "run",
                        "tests/postman/readers.sim.yaml",
                        "--port",
                        str(args.simulation_port),
                        "--output",
                        "ndjson",
                    ],
                    cwd=ROOT,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                processes.append(sim)
                base = f"http://127.0.0.1:{args.simulation_port}"
                ready(base, sim)
                env = {
                    **os.environ,
                    "PORT": str(args.mcp_port),
                    "MOMENTUM_API_URL": base + "/momentum",
                    "MARKET_SCANNER_API_URL": base + "/scanner",
                    "MOMENTUM_API_USE_IAM": "false",
                    "MOMENTUM_API_TOKEN": "disposable-momentum-token",
                    "MARKET_SCANNER_API_TOKEN": "disposable-scanner-token",
                    "SUGGESTION_HASH_SECRET": "disposable-simulation-only",
                }
                app = subprocess.Popen(
                    [sys.executable, "-m", "momentum_public_mcp.main"],
                    cwd=ROOT,
                    env=env,
                    start_new_session=True,
                )
                processes.append(app)
                endpoint = f"http://127.0.0.1:{args.mcp_port}"
                ready(endpoint + "/health", app)
                subprocess.run(
                    [
                        "postman",
                        "collection",
                        "run",
                        "tests/postman/mcp.postman_collection.json",
                        "--env-var",
                        f"mcpUrl={endpoint}",
                        "--report-events=false",
                    ],
                    cwd=ROOT,
                    check=True,
                )
                log.flush()
                evidence = log_path.read_text()
                for member in ("momentum", "scanner"):
                    if f'"routeKey":"{member}","method"' not in evidence:
                        raise RuntimeError(f"No actual request to {member}")
                print("Verified HTTP requests to both upstream simulation members.")
            finally:
                for process in reversed(processes):
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGINT)
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait()


if __name__ == "__main__":
    main()
