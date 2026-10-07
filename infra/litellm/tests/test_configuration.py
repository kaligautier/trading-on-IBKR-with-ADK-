"""Offline checks for deployment targeting and credential handling."""

import importlib.util
import json
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import httpx

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("target", ["other-host", "user", "database", "port"])
def test_database_rerun_rejects_a_different_target(target):
    # Arrange
    script = load_script("bootstrap_database")
    host = "other.example.com" if target == "other-host" else "db.example.com"
    user = "admin" if target == "user" else "litellm"
    database = "defaultdb" if target == "database" else "litellm"
    port = 5433 if target == "port" else 5432
    stored = f"postgresql://{user}:placeholder@{host}:{port}/{database}"

    # Act / Assert
    with pytest.raises(ValueError, match="dedicated target"):
        script.existing_password(stored, "db.example.com", 5432)


def test_database_rerun_preserves_encoded_password():
    # Arrange
    script = load_script("bootstrap_database")
    stored = "postgresql://litellm:p%2B%27%40ss@db.example.com:5432/litellm"

    # Act
    password = script.existing_password(stored, "db.example.com", 5432)

    # Assert
    assert password == "p+'@ss"


@pytest.mark.parametrize("upload_ok", [True, False])
def test_client_secret_upload_or_revocation(monkeypatch, capsys, upload_ok):
    # Arrange
    script = load_script("bootstrap_scanner_key")
    script.PROJECT = "example-project"
    script.BASE_URL = "https://gateway.example.com"
    script.SECRET = "litellm-client-agent"
    master = secrets.token_hex(32)
    key = "sk-" + secrets.token_hex(32)
    monkeypatch.setenv("LITELLM_MASTER_KEY", master)
    credentials = SimpleNamespace(refresh=lambda _: None, token="placeholder")
    monkeypatch.setattr(script.google.auth, "default", lambda **_: (credentials, None))
    requests = []

    def handle(request):
        requests.append((request.url.path, json.loads(request.content or "{}")))
        if request.url.path.endswith("/versions"):
            return httpx.Response(200, json={"versions": []})
        if request.url.path == "/key/generate":
            return httpx.Response(200, json={"key": key})
        if request.url.path.endswith(":addVersion"):
            return httpx.Response(
                200 if upload_ok else 503,
                json={"name": "projects/example/secrets/agent/versions/1"},
            )
        if request.url.path == "/key/delete":
            return httpx.Response(200, json={})
        raise AssertionError("Unexpected request")

    client_type = httpx.Client
    monkeypatch.setattr(
        script.httpx,
        "Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )

    # Act
    if upload_ok:
        script.main()
    else:
        with pytest.raises(script.BootstrapError, match="HTTP 503"):
            script.main()

    # Assert
    generation = next(body for path, body in requests if path == "/key/generate")
    assert generation["key_alias"].startswith("agent-")
    assert generation["allowed_routes"] == ["/v1beta/models/*"]
    revocations = [body for path, body in requests if path == "/key/delete"]
    assert revocations == ([] if upload_ok else [{"keys": [key]}])
    output = capsys.readouterr().out
    assert key not in output and master not in output


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com/path",
        "https://example.com?key=value",
        "https://example.com#fragment",
    ],
)
def test_client_rejects_unsafe_origin(url):
    # Arrange
    script = load_script("bootstrap_scanner_key")
    script.PROJECT = "example-project"
    script.BASE_URL = url

    # Act / Assert
    with pytest.raises(ValueError, match="HTTPS origin"):
        script.validate_configuration()


def test_client_requires_explicit_project():
    # Arrange
    script = load_script("bootstrap_scanner_key")
    script.PROJECT = ""
    script.BASE_URL = "https://example.com"

    # Act / Assert
    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
        script.validate_configuration()


def test_client_accepts_https_origin():
    # Arrange
    script = load_script("bootstrap_scanner_key")
    script.PROJECT = "example-project"
    script.BASE_URL = "https://example.com"

    # Act
    result = script.validate_configuration()

    # Assert
    assert result is None


def test_provider_upload_keeps_credentials_out_of_arguments_and_output(
    monkeypatch, capsys
):
    # Arrange
    script = load_script("upload_provider_key")
    key = secrets.token_hex(32)
    calls = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "upload",
            "openai",
            "--project",
            "example-project",
            "--account",
            "operator@example.com",
        ],
    )
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(script.getpass, "getpass", lambda _: key)

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            returncode=0, stdout="projects/example/secrets/provider/versions/2"
        )

    monkeypatch.setattr(script.subprocess, "run", run)

    # Act
    script.main()

    # Assert
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert key not in " ".join(args)
    assert kwargs["input"] == key
    assert "--project=example-project" in args
    assert "--account=operator@example.com" in args
    assert key not in capsys.readouterr().out


def test_oauth_rejects_another_project_before_authentication(monkeypatch, tmp_path):
    # Arrange
    script = load_script("configure_iap_oauth")
    credentials = tmp_path / "client.json"
    credentials.write_text(
        '{"web": {"project_id": "foreign-project", "client_id": "123-test"}}'
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "oauth",
            str(credentials),
            "--project",
            "example-project",
            "--project-number",
            "123",
            "--account",
            "operator@example.com",
        ],
    )
    calls = []
    monkeypatch.setattr(
        script.subprocess, "check_output", lambda *a, **k: calls.append(a)
    )

    # Act / Assert
    with pytest.raises(ValueError, match="selected project"):
        script.main()
    assert calls == []


@pytest.mark.asyncio
async def test_database_decodes_administrator_password(monkeypatch, tmp_path):
    # Arrange
    script = load_script("bootstrap_database")
    admin = tmp_path / "admin.json"
    admin.write_text(
        json.dumps(
            {"url": "postgresql://avnadmin:p%2B%27%40ss@db.example.com:5432/defaultdb"}
        )
    )
    admin.chmod(0o600)
    args = SimpleNamespace(
        admin_file=admin,
        ca_file=tmp_path / "ca.pem",
        expected_host="db.example.com",
        project="example-project",
        account="owner",
    )
    connect = AsyncMock(side_effect=RuntimeError("stop before database writes"))
    monkeypatch.setattr(script.asyncpg, "connect", connect)
    monkeypatch.setattr(script.ssl, "create_default_context", lambda **_: object())
    monkeypatch.setattr(script.SecretStore, "existing_version", lambda *_: None)

    # Act
    with pytest.raises(RuntimeError, match="stop before database writes"):
        await script.bootstrap(args)

    # Assert
    assert connect.call_args.kwargs["password"] == "p+'@ss"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "salt_exists,encrypted_rows", [(False, 1), (False, 0), (True, 1)]
)
async def test_aiven_preserves_salt_for_encrypted_records(
    monkeypatch, tmp_path, salt_exists, encrypted_rows
):
    # Arrange
    monkeypatch.syspath_prepend(str(SCRIPTS))
    script = load_script("bootstrap_aiven")
    for name in [
        "LITELLM_GCP_ACCOUNT",
        "GOOGLE_CLOUD_PROJECT",
        "LITELLM_AIVEN_PROJECT",
        "LITELLM_AIVEN_SERVICE",
        "LITELLM_AIVEN_ACCOUNT",
        "LITELLM_AIVEN_HOST",
    ]:
        monkeypatch.setenv(name, "example")
    script.ROOT = tmp_path
    (tmp_path / "config").mkdir()
    (tmp_path / "config/release.local.tfvars").write_text('stage = "service"')
    monkeypatch.setattr(script, "command", lambda *_: json.dumps({"user": "example"}))
    monkeypatch.setattr(
        script,
        "service",
        lambda: {
            "state": "RUNNING",
            "service_uri_params": {"host": "example", "port": 5432, "user": "avnadmin"},
            "users": [{"username": "litellm"}],
        },
    )
    monkeypatch.setattr(script, "service_user", lambda _: {"password": "placeholder"})

    def avn(*args):
        if "ca-get" in args:
            Path(args[-1]).write_text("placeholder-ca")
        return json.dumps(["litellm"])

    monkeypatch.setattr(script, "avn", avn)
    monkeypatch.setattr(script.ssl, "create_default_context", lambda **_: object())
    connection = MagicMock()
    connection.fetchrow = AsyncMock(return_value={"rolsuper": False})
    connection.fetch = AsyncMock(
        return_value=[{"tablename": "LiteLLM_CredentialsTable"}]
    )
    connection.fetchval = AsyncMock(
        side_effect=lambda query: (encrypted_rows if "count(*)" in query else True)
    )
    connection.execute = AsyncMock()
    connection.close = AsyncMock()
    monkeypatch.setattr(script.asyncpg, "connect", AsyncMock(return_value=connection))
    uploads = MagicMock(return_value="1")
    monkeypatch.setattr(script, "upload", uploads)
    monkeypatch.setattr(
        script.SecretStore, "existing_version", lambda *_: "1" if salt_exists else None
    )

    # Act
    if encrypted_rows and not salt_exists:
        with pytest.raises(ValueError, match="original salt"):
            await script.main()
    else:
        await script.main()

    # Assert
    if encrypted_rows and not salt_exists:
        uploads.assert_not_called()
    else:
        assert uploads.call_count == 5
    assert connection.close.await_count >= 1
