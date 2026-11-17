"""Only positively verified credentials and explicit denials attest isolation."""

import runpy
from pathlib import Path
from unittest.mock import AsyncMock

import asyncpg
import pytest

VERIFY = runpy.run_path(
    str(Path(__file__).resolve().parents[3] / "scripts/verify_reader_network.py")
)["verify"]
URL = (
    "postgresql://momentum_results_reader:local-only@localhost:5432/momentum"
    "?sslmode=verify-full"
)


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (
            asyncpg.InvalidAuthorizationSpecificationError(
                "pg_hba.conf rejects connection"
            ),
            True,
        ),
        (asyncpg.InsufficientPrivilegeError("permission denied"), False),
        (asyncpg.InvalidPasswordError("bad credential"), None),
        (asyncpg.InvalidAuthorizationSpecificationError("unknown rejection"), None),
        (TimeoutError(), None),
        (None, None),
    ],
)
async def test_network_attestation_never_confuses_failures_with_denial(
    monkeypatch, failure, expected
):
    primary = AsyncMock()
    primary.fetch.return_value = [
        {"datname": "template1", "datistemplate": True, "owner": "postgres"}
    ]
    other = AsyncMock()
    connect = AsyncMock(side_effect=[primary, failure or other])
    monkeypatch.setattr(asyncpg, "connect", connect)
    if expected is None:
        with pytest.raises((ValueError, asyncpg.InvalidPasswordError, TimeoutError)):
            await VERIFY(URL)
    else:
        assert await VERIFY(URL) is expected
    primary.close.assert_awaited_once()
    if failure is None:
        other.close.assert_awaited_once()


async def test_network_verifier_requires_successful_momentum_connection(monkeypatch):
    connect = AsyncMock(side_effect=asyncpg.InvalidPasswordError("bad credential"))
    monkeypatch.setattr(asyncpg, "connect", connect)
    with pytest.raises(asyncpg.InvalidPasswordError):
        await VERIFY(URL)
    assert connect.await_count == 1


@pytest.mark.parametrize(
    "url",
    [
        URL.replace("localhost:5432", ""),
        URL.replace("postgresql://", "https://"),
        URL.replace(":local-only@", "@"),
        URL.replace("verify-full", "require"),
    ],
)
async def test_network_verifier_rejects_ambiguous_or_unverified_targets(
    monkeypatch, url
):
    connect = AsyncMock()
    monkeypatch.setattr(asyncpg, "connect", connect)
    with pytest.raises(ValueError):
        await VERIFY(url)
    connect.assert_not_awaited()
