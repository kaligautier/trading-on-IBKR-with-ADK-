import ssl

import pytest


def test_use_verified_tls_without_forwarding_libpq_keywords():
    from app.infrastructure.postgres_tls import connection_options

    address, tls = connection_options(
        "postgresql://writer:private@db.example/momentum?sslmode=verify-full"
    )
    assert address.query == {}
    assert isinstance(tls, ssl.SSLContext)
    assert tls.check_hostname
    assert tls.verify_mode == ssl.CERT_REQUIRED


@pytest.mark.parametrize(
    "query",
    [
        "",
        "?sslmode=require",
        "?sslmode=disable",
        "?ssl=prefer",
        "?sslmode=verify-ca",
        "?sslmode=verify-full&ssl=disable",
        "?sslmode=verify-full&sslmode=disable",
        "?sslmode=verify-full&unexpected=x",
    ],
)
def test_reject_remote_insecure_or_ambiguous_options_without_leaking(query):
    from app.infrastructure.postgres_tls import connection_options

    with pytest.raises(ValueError) as error:
        connection_options("postgresql://writer:private@db.example/momentum" + query)
    assert "private" not in str(error.value)
    assert "db.example" not in str(error.value)


def test_consume_ca_option_and_reject_unreadable_ca(tmp_path):
    from app.infrastructure.postgres_tls import connection_options

    with pytest.raises(ValueError, match="PostgreSQL"):
        connection_options(
            "postgresql://writer:private@db.example/momentum?sslmode=verify-full"
            f"&sslrootcert={tmp_path / 'missing.pem'}"
        )


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]"])
def test_allow_explicit_local_development_without_tls(host):
    from app.infrastructure.postgres_tls import connection_options

    address, tls = connection_options(
        f"postgresql://writer@{host}/momentum?sslmode=disable"
    )
    assert tls is False
    assert address.query == {}
