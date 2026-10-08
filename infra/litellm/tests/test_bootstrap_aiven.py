"""Aiven reruns must validate retained connection secrets before changing SQL."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import quote

import pytest


@pytest.fixture
def aiven_bootstrap(monkeypatch, tmp_path):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    for name, value in {
        "LITELLM_GCP_ACCOUNT": "operator@example.com",
        "GOOGLE_CLOUD_PROJECT": "example-project",
        "LITELLM_AIVEN_PROJECT": "example-aiven",
        "LITELLM_AIVEN_SERVICE": "database",
        "LITELLM_AIVEN_ACCOUNT": "operator@example.com",
        "LITELLM_AIVEN_HOST": "db.example.com",
    }.items():
        monkeypatch.setenv(name, value)
    spec = importlib.util.spec_from_file_location(
        "aiven_bootstrap_review", scripts / "bootstrap_aiven.py"
    )
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    script.ROOT = tmp_path
    (tmp_path / "config").mkdir()
    release = tmp_path / "config/release.local.tfvars"
    release.write_text('stage = "service"\nsecret_versions = { salt-key = "1" }')
    original_release = release.read_text()
    password = "p+'@ss"
    stored = {
        "database-url": (
            f"postgresql://litellm:{quote(password, safe='')}@db.example.com:5432/litellm"
        ),
        "database-ca": "original-ca",
        "salt-key": "original-salt",
    }
    monkeypatch.setattr(
        script, "command", lambda *_: json.dumps({"user": "operator@example.com"})
    )
    monkeypatch.setattr(
        script,
        "service",
        lambda: {
            "state": "RUNNING",
            "service_uri_params": {
                "host": "db.example.com",
                "port": 5432,
                "user": "avnadmin",
            },
            "users": [{"username": "litellm"}],
        },
    )
    monkeypatch.setattr(script, "service_user", lambda _: {"password": password})
    mutations = []

    def avn(*args):
        if "ca-get" in args:
            Path(args[-1]).write_text("original-ca\n")
        elif "create" in " ".join(args):
            mutations.append(args)
        return json.dumps(["litellm"])

    monkeypatch.setattr(script, "avn", avn)
    monkeypatch.setattr(script.ssl, "create_default_context", lambda **_: object())
    connection = MagicMock()
    connection.fetchrow = AsyncMock(return_value={"rolsuper": False})
    connection.fetchval = AsyncMock(return_value=True)
    connection.execute = AsyncMock()
    connection.close = AsyncMock()
    connect = AsyncMock(return_value=connection)
    monkeypatch.setattr(script.asyncpg, "connect", connect)
    monkeypatch.setattr(
        script.SecretStore,
        "existing_version",
        lambda _, name: "1" if name in stored else None,
    )
    monkeypatch.setattr(
        script.SecretStore,
        "command",
        lambda _, *args, **kwargs: stored[args[4].removeprefix("--secret=litellm-")],
    )
    uploaded = {}

    def upload(name, value):
        if name not in stored:
            uploaded[name] = value
        return "1"

    monkeypatch.setattr(script, "upload", upload)
    return script, stored, connect, uploaded, mutations, release, original_release


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mismatch", ["host", "port", "user", "database", "password", "ca"]
)
async def test_aiven_rejects_retained_connection_mismatch_before_writes(
    aiven_bootstrap, mismatch, capsys
):
    script, stored, connect, uploaded, mutations, release, original = aiven_bootstrap
    if mismatch == "ca":
        stored["database-ca"] = "different-ca"
    else:
        replacements = {
            "host": ("db.example.com", "other.example.com"),
            "port": (":5432/", ":5433/"),
            "user": ("litellm:", "other:"),
            "database": ("/litellm", "/other"),
            "password": ("p%2B%27%40ss", "different-password"),
        }
        stored["database-url"] = stored["database-url"].replace(*replacements[mismatch])

    with pytest.raises(ValueError):
        await script.main()

    assert connect.await_count == 0
    assert uploaded == {} and mutations == []
    assert stored["salt-key"] == "original-salt"
    assert release.read_text() == original
    assert "verified" not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_aiven_valid_retained_connection_preserves_secrets(
    aiven_bootstrap, capsys
):
    script, stored, connect, uploaded, mutations, release, original = aiven_bootstrap
    await script.main()
    assert connect.call_args.kwargs["password"] == "p+'@ss"
    assert stored["salt-key"] == "original-salt"
    assert "database-url" not in uploaded and "database-ca" not in uploaded
    assert mutations == [] and release.read_text() == original
    output = capsys.readouterr().out
    assert "verified" in output
    assert stored["database-url"] not in output and "original-salt" not in output
