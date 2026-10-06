"""Offline checks for deployment targeting and credential handling."""

import importlib.util
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    script.ACCOUNT = "operator@example.com"
    script.PROJECT = "example-project"
    script.BASE_URL = url

    # Act / Assert
    with pytest.raises(ValueError, match="HTTPS origin"):
        script.validate_configuration()


def test_client_requires_explicit_account():
    # Arrange
    script = load_script("bootstrap_scanner_key")
    script.ACCOUNT = ""
    script.PROJECT = "example-project"
    script.BASE_URL = "https://example.com"

    # Act / Assert
    with pytest.raises(ValueError, match="LITELLM_GCP_ACCOUNT"):
        script.validate_configuration()


def test_client_accepts_https_origin():
    # Arrange
    script = load_script("bootstrap_scanner_key")
    script.ACCOUNT = "operator@example.com"
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
