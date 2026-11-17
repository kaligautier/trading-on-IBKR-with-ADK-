"""Security boundary tests for public caller pseudonymization."""

import ipaddress
from types import SimpleNamespace

from momentum_public_mcp.security import (
    CallerFingerprint,
    ClientAddressResolver,
    TrustedProxyNetworks,
)


class StaticAddressResolver:
    def current(self) -> str:
        return "203.0.113.42"


def test_caller_fingerprint_is_stable_and_hides_the_raw_address() -> None:
    fingerprint = CallerFingerprint("test-secret", StaticAddressResolver())

    first_value = fingerprint.current()
    second_value = fingerprint.current()

    assert first_value == second_value
    assert "203.0.113.42" not in first_value
    assert len(first_value) == 64


def test_resolver_uses_the_trusted_proxy_right_edge() -> None:
    networks = TrustedProxyNetworks((ipaddress.ip_network("10.0.0.0/8"),))
    resolver = ClientAddressResolver(networks)
    request = SimpleNamespace(
        headers={"x-forwarded-for": "198.51.100.9, 203.0.113.42, 10.0.0.3"}
    )

    address = resolver.resolve(request, "10.0.0.2")

    assert address == "203.0.113.42"


def test_resolver_ignores_forwarding_from_an_untrusted_peer() -> None:
    networks = TrustedProxyNetworks((ipaddress.ip_network("10.0.0.0/8"),))
    resolver = ClientAddressResolver(networks)
    request = SimpleNamespace(headers={"x-forwarded-for": "203.0.113.42"})

    address = resolver.resolve(request, "192.0.2.10")

    assert address == "192.0.2.10"
