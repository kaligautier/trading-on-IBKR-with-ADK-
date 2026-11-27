"""Real subprocesses and sockets: exercise the installed CLI and wire protocol."""

import asyncio
import os
import socket
import sys
from pathlib import Path

import httpx
import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


def api_env(deepcopy_api) -> dict[str, str]:
    config, _ = deepcopy_api
    return {
        "MCP_DEEPCOPY_API__BASE_URL": config["base_url"],
        "MCP_DEEPCOPY_API__TOKEN": config["token"],
    }


async def assert_portfolio(client):
    assert len(await client.list_tools()) == 5
    result = await client.call_tool("deepcopy_search_contracts", {"symbol": "AAPL"})
    assert result.structured_content["result"][0]["conid"] == 265598
    assert "never place" in (await client.read_resource("guide://deepcopy"))[0].text
    prompt = await client.get_prompt("review_portfolio", {"question": "Cash?"})
    assert "Cash?" in prompt.messages[0].content.text


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_stdio(deepcopy_api, mode):
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "app.main"],
        env=os.environ | api_env(deepcopy_api),
    )
    async with Client(transport, mode=mode, timeout=10) as client:
        await assert_portfolio(client)


async def test_fastmcp_project_configuration(deepcopy_api):
    root = Path(__file__).resolve().parents[3]
    transport = StdioTransport(
        command=str(Path(sys.executable).parent / "fastmcp"),
        args=["run", str(root / "fastmcp.json"), "--skip-env"],
        cwd=str(root),
        env={
            "MCP_ENVIRONMENT": "local",
            "MCP_AUTH_MODE": "none",
            "MCP_TRANSPORT": "stdio",
        }
        | api_env(deepcopy_api),
    )
    async with Client(transport, timeout=10) as client:
        await assert_portfolio(client)


@pytest.fixture
async def http_server(tmp_path, deepcopy_api):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log_path = tmp_path / "server.log"
    with log_path.open("wb") as log:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.main",
            "--transport",
            "http",
            env=os.environ | {"MCP_PORT": str(port)} | api_env(deepcopy_api),
            stdout=log,
            stderr=log,
        )
        try:
            async with httpx.AsyncClient() as probe:
                for _ in range(100):
                    if process.returncode is not None:
                        pytest.fail(log_path.read_text())
                    try:
                        response = await probe.get(
                            f"http://127.0.0.1:{port}/health", timeout=0.5
                        )
                        if response.status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    await asyncio.sleep(0.05)
                else:
                    pytest.fail(
                        "HTTP server did not become healthy: " + log_path.read_text()
                    )
            yield f"http://127.0.0.1:{port}"
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=10)
                except TimeoutError:
                    process.kill()
                    await process.wait()


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_streamable_http(http_server, mode):
    async with Client(http_server + "/mcp", mode=mode, timeout=10) as client:
        await assert_portfolio(client)


async def test_cli_rejects_unauthenticated_production():
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.main",
        "--transport",
        "http",
        env=os.environ | {"MCP_ENVIRONMENT": "production"},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
    assert process.returncode != 0
    assert not stdout
    assert b"Production requires JWT authentication" in stderr
