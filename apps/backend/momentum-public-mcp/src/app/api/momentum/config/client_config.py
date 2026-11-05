"""Construct the Momentum client with its transport and authentication."""

from app.api.auth import backend_headers, create_identity_headers
from app.api.config import create_http_client
from app.api.momentum.client.momentum_client import MomentumClient
from app.api.momentum.client.signing import SuggestionSigner
from app.api.momentum.config.settings import MomentumApiSettings


def create_momentum_client(settings: MomentumApiSettings) -> MomentumClient:
    client = create_http_client(
        settings.MOMENTUM_API_URL,
        headers=backend_headers(
            settings.MOMENTUM_API_TOKEN, use_iam=settings.MOMENTUM_API_USE_IAM
        ),
    )
    return MomentumClient(
        client=client,
        signer=SuggestionSigner(settings.SUGGESTION_HASH_SECRET.get_secret_value()),
        identity_headers=create_identity_headers(
            client, settings.MOMENTUM_API_URL, use_iam=settings.MOMENTUM_API_USE_IAM
        ),
    )
