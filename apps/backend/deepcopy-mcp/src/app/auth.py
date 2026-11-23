"""Verify externally issued tokens with FastMCP's maintained verifier."""

import math
import time
from typing import TypeGuard

from fastmcp.server.auth import AccessToken, AuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier

from app.config.settings import Settings


def _is_numeric_date(value: object) -> TypeGuard[int | float]:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and (not isinstance(value, float) or math.isfinite(value))
    )


class ExpiringJWTVerifier(JWTVerifier):
    """Keep signature/issuer/audience checks upstream, require expiry as well."""

    async def verify_token(self, token: str) -> AccessToken | None:
        verified = await super().verify_token(token)
        if verified is None:
            return None
        expires = verified.claims.get("exp")
        not_before = verified.claims.get("nbf", 0)
        if not _is_numeric_date(expires) or not _is_numeric_date(not_before):
            return None
        now = time.time()
        if expires <= now or not_before > now:
            return None
        return verified


def create_auth(settings: Settings) -> AuthProvider | None:
    if settings.auth_mode == "none":
        return None
    return ExpiringJWTVerifier(
        jwks_uri=str(settings.jwt_jwks_uri),
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        algorithm="RS256",
        required_scopes=settings.required_scopes,
    )
