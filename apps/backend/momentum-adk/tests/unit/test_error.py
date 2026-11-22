"""The error module maps every failure to its job exit code and message."""

import json

from app.utils.error import (
    ERROR_MESSAGES,
    EXIT_CODES,
    AlphaVantageRateLimitError,
    AppError,
    ErrorCode,
    LiteLLMError,
    MomentumBusyError,
)


def test_every_code_has_a_message_and_exit_code():
    for code in ErrorCode:
        assert ERROR_MESSAGES[code]
        assert EXIT_CODES[code] in {1, 75}


def test_busy_is_a_deferral_not_a_failure():
    assert MomentumBusyError().exit_code == 75
    assert MomentumBusyError().message == "Momentum execution capacity is busy"


def test_litellm_error_keeps_only_safe_details():
    error = LiteLLMError(details={"error_type": "ClientError", "upstream_status": 403})
    assert error.error_code is ErrorCode.LITELLM_ERROR
    assert error.exit_code == 1
    assert str(error) == (
        "[LITELLM_ERROR] LiteLLM gateway failed, "
        "details={'error_type': 'ClientError', 'upstream_status': 403}"
    )


def test_rate_limit_error_is_an_app_error():
    error = AlphaVantageRateLimitError("Alpha Vantage rate limit exceeded")
    assert isinstance(error, AppError)
    assert error.error_code is ErrorCode.MARKET_DATA_RATE_LIMITED


def test_worker_reports_busy_with_exit_code_75(monkeypatch, capsys):
    from app import job_runner

    def busy(_request):
        raise MomentumBusyError()

    monkeypatch.setenv(
        "TA_ANALYSIS_REQUEST",
        json.dumps(
            {
                "ticker": "NVDA",
                "analysis_date": "2026-11-20",
                "requested_by": "test",
                "session_id": "00000000-0000-0000-0000-000000000001",
            }
        ),
    )
    monkeypatch.setattr(job_runner, "execute", busy)
    monkeypatch.setattr(job_runner.asyncio, "run", lambda coroutine: coroutine)
    assert job_runner.main() == 75
    busy_event = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert busy_event == {"severity": "WARNING", "event": "momentum_busy"}


def test_worker_failure_event_carries_the_error_code(monkeypatch, capsys):
    from app import job_runner

    monkeypatch.setenv("TA_ANALYSIS_REQUEST", "not-json")
    assert job_runner.main() == 1
    event = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert event == {
        "severity": "ERROR",
        "event": "momentum_failed",
        "error_type": "ValidationError",
        "error_code": "INTERNAL_ERROR",
    }
