"""Bounded, read-only requests to public market-data providers."""

import ssl
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi


class PublicDataHttpClient:
    def __init__(self, opener: Callable = urlopen) -> None:
        self._opener = opener
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())

    def get_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": "DeepCopy-MarketScanner/2"})
        for attempt in range(2):
            try:
                with self._opener(
                    request, timeout=15, context=self._ssl_context
                ) as response:
                    body = response.read(10_000_001)
                    if len(body) > 10_000_000:
                        raise ValueError("Provider response exceeds 10 MB")
                    return body.decode("utf-8-sig")
            except HTTPError as error:
                if attempt or (error.code != 429 and error.code < 500):
                    raise
            except (URLError, TimeoutError, ConnectionError):
                if attempt:
                    raise
        raise RuntimeError("Unreachable request state")
