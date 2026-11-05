"""Momentum suggestion caller assertion."""

import hashlib
import hmac


class SuggestionSigner:
    """Authenticate a pseudonymous caller assertion to Momentum API."""

    def __init__(self, secret: str):
        if not secret:
            raise ValueError("Suggestion hash secret is required.")
        self._secret = secret.encode()

    def headers(self, caller_fingerprint: str) -> dict[str, str]:
        signature = hmac.new(
            self._secret,
            caller_fingerprint.encode(),
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-Momentum-Caller": caller_fingerprint,
            "X-Momentum-Signature": signature,
        }
