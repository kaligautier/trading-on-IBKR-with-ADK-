"""Translate libpq URL options into verified asyncpg connection arguments."""

import ssl

from sqlalchemy.engine import URL, make_url


def connection_options(
    raw: str, ca_file: str | None = None
) -> tuple[URL, ssl.SSLContext | bool]:
    """Reject ambiguous/insecure remote transport without echoing credentials."""
    try:
        address = make_url(raw)
        _validate_address(address)
        options = address.query
        mode = options.get("sslmode", options.get("ssl"))
        local = address.host in {"127.0.0.1", "localhost", "::1"}
        if mode != "verify-full" and not (local and mode in {None, "disable"}):
            raise ValueError
        ca = options.get("sslrootcert", ca_file)
        if "sslrootcert" in options and mode != "verify-full":
            raise ValueError
        if ca_file and "sslrootcert" in options and ca_file != ca:
            raise ValueError
        tls = ssl.create_default_context(cafile=ca) if mode == "verify-full" else False
        clean = address.difference_update_query(options.keys())
        return clean.set(drivername="postgresql+asyncpg"), tls
    except (ValueError, TypeError, OSError):
        raise ValueError(
            "Configure verified PostgreSQL TLS and a readable CA file"
        ) from None


def _validate_address(address: URL) -> None:
    if (
        address.drivername not in {"postgres", "postgresql", "postgresql+asyncpg"}
        or not address.host
        or not address.database
        or set(address.query) - {"sslmode", "ssl", "sslrootcert"}
        or any(not isinstance(value, str) for value in address.query.values())
        or {"sslmode", "ssl"}.issubset(address.query)
    ):
        raise ValueError
