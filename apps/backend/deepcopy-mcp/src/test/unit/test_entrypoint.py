import logging
from unittest.mock import Mock

import pytest

from app.main import main
from app.utils.logger import configure_logging


@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_cli_configures_transport(monkeypatch, transport):
    server = Mock()
    monkeypatch.setattr("app.main.create_server", lambda _: server)
    monkeypatch.setattr("app.main.configure_logging", lambda _: None)
    monkeypatch.setattr("sys.argv", ["deepcopy-mcp", "--transport", transport])
    main()
    kwargs = server.run.call_args.kwargs
    assert kwargs["transport"] == transport
    if transport == "http":
        assert kwargs["stateless_http"] is True
        assert kwargs["host_origin_protection"] is True
        assert kwargs["allowed_hosts"] == ["127.0.0.1", "localhost"]


def test_logs_use_stderr_not_protocol_stdout(capsys):
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    try:
        configure_logging("INFO")
        logging.getLogger("app.test").info("test event")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert '"message": "test event"' in captured.err
    finally:
        root.handlers = old_handlers
        root.setLevel(old_level)
