"""Trusted address resolution and caller pseudonymization."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
from dataclasses import dataclass
from ipaddress import IPv4Network, IPv6Network
from typing import Protocol

from fastmcp.server.dependencies import get_http_request


class AddressProvider(Protocol):
    def current(self) -> str: ...


class FingerprintProvider(Protocol):
    def current(self) -> str: ...


@dataclass(frozen=True, slots=True)
class TrustedProxyNetworks:
    """First-class collection of explicitly trusted proxy networks."""

    values: tuple[IPv4Network | IPv6Network, ...]

    @classmethod
    def from_csv(cls, raw_networks: str) -> TrustedProxyNetworks:
        networks = tuple(
            ipaddress.ip_network(raw_network.strip(), strict=False)
            for raw_network in raw_networks.split(",")
            if raw_network.strip()
        )
        return cls(networks)

    def contains(self, raw_address: str) -> bool:
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError:
            return False
        return any(address in network for network in self.values)


class ClientAddressResolver:
    """Resolve the caller without trusting arbitrary forwarding headers."""

    def __init__(self, trusted_networks: TrustedProxyNetworks):
        self._trusted_networks = trusted_networks

    def current(self) -> str:
        try:
            request = get_http_request()
        except RuntimeError:
            return "local"
        client = request.client
        direct_address = client.host if client else "unknown"
        return self.resolve(request, direct_address)

    def resolve(self, request, direct_address: str) -> str:
        if not self._trusted_networks.contains(direct_address):
            return direct_address
        forwarding_chain = request.headers.get("x-forwarded-for", "")
        forwarded_address = self._load_balancer_client(forwarding_chain)
        if forwarded_address is None:
            return direct_address
        return forwarded_address

    @staticmethod
    def _load_balancer_client(forwarding_chain: str) -> str | None:
        addresses = [
            value.strip() for value in forwarding_chain.split(",") if value.strip()
        ]
        if len(addresses) < 2:
            return None
        candidate = addresses[-2]
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            return None
        return candidate


class CallerFingerprint:
    """Create a stable HMAC pseudonym without persisting the raw address."""

    def __init__(self, secret: str, address_provider: AddressProvider):
        if not secret:
            raise ValueError("Suggestion hash secret is required.")
        self._secret = secret.encode()
        self._address_provider = address_provider

    def current(self) -> str:
        raw_address = self._address_provider.current()
        return hmac.new(
            self._secret,
            raw_address.encode(),
            hashlib.sha256,
        ).hexdigest()
