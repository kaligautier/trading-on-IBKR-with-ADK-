"""Shared HTTP transport boundaries, without network calls."""

import ssl
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from app.client.public_data_http_client import PublicDataHttpClient


def should_retry_a_temporary_network_error_once_with_a_timeout():
    calls = []

    def open_url(request, *, timeout, context):
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True
        calls.append(timeout)
        if len(calls) == 1:
            raise URLError("temporary failure")
        return BytesIO(b"DATE,CLOSE\n")

    assert (
        PublicDataHttpClient(open_url).get_text("https://example.test")
        == "DATE,CLOSE\n"
    )
    assert calls == [15, 15]


def should_not_retry_a_missing_resource():
    calls = []

    def open_url(request, *, timeout, context):
        calls.append(timeout)
        raise HTTPError(request.full_url, 404, "Not found", {}, None)

    with pytest.raises(HTTPError):
        PublicDataHttpClient(open_url).get_text("https://example.test")
    assert calls == [15]


def should_stop_after_two_temporary_failures():
    calls = []

    def open_url(request, *, timeout, context):
        calls.append(timeout)
        raise URLError("temporary failure")

    with pytest.raises(URLError):
        PublicDataHttpClient(open_url).get_text("https://example.test")
    assert calls == [15, 15]
