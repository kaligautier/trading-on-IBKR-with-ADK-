"""Run the local reader APIs and optionally MCP; Ctrl-C stops owned processes."""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
READERS = (("momentum-api", 8000), ("market-scanner-api", 8003))


def read_env(service):
    path = ROOT.parent / service / ".env"
    if not path.is_file():
        raise RuntimeError(f"Configure {path} first; see README local setup.")
    return {key: value for key, value in dotenv_values(path).items() if value}


def check_ports(ports):
    for port in ports:
        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", port))
        except OSError:
            raise RuntimeError(
                f"Port {port} unavailable. Stop its server first, or use "
                "`just apis` if MCP is already running."
            ) from None


def stop(processes):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    for process in reversed(processes):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


def interrupted(_signum, _frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apis-only", action="store_true")
    parser.add_argument("--mcp-port", type=int, default=8080)
    args = parser.parse_args()
    ports = [port for _, port in READERS]
    if not args.apis_only:
        ports.append(args.mcp_port)
    check_ports(ports)
    configs = {service: read_env(service) for service, _ in READERS}
    inherited = {
        key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"
    }
    commands = []
    for service, port in READERS:
        commands.append(
            (
                service,
                [
                    "uv",
                    "run",
                    "--frozen",
                    "uvicorn",
                    "app.main:create_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--no-access-log",
                ],
                {**inherited, **configs[service], "AUTH_MODE": "token"},
            )
        )
    if not args.apis_only:
        env = {
            **inherited,
            **read_env(ROOT.name),
            "PORT": str(args.mcp_port),
            "MOMENTUM_API_URL": "http://127.0.0.1:8000",
            "MARKET_SCANNER_API_URL": "http://127.0.0.1:8003",
            "MOMENTUM_API_USE_IAM": "false",
            "MOMENTUM_API_TOKEN": configs["momentum-api"].get("API_TOKEN", ""),
            "MARKET_SCANNER_API_TOKEN": configs["market-scanner-api"].get(
                "API_TOKEN", ""
            ),
            "SUGGESTION_HASH_SECRET": configs["momentum-api"].get(
                "SUGGESTION_HASH_SECRET", ""
            ),
        }
        commands.append((ROOT.name, [sys.executable, "-m", "app.main"], env))
    processes = []
    signal.signal(signal.SIGTERM, interrupted)
    try:
        for service, command, env in commands:
            processes.append(
                subprocess.Popen(
                    command, cwd=ROOT.parent / service, env=env, start_new_session=True
                )
            )
        print("Local stack starting; Ctrl-C stops these processes.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.2)
        raise RuntimeError("A service exited; stopping the other local services.")
    except KeyboardInterrupt:
        pass
    finally:
        stop(processes)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        sys.exit(1)
