import pytest

from app.components.agents.momentum.catalog import MomentumAgentCatalog
from app.config.llm import LiteLLMGatewayModel, create_model
from app.config.settings import Settings


def test_every_role_uses_injected_gateway():
    config = Settings(
        LITELLM_API_BASE="https://gateway.example", LITELLM_API_KEY="test"
    )
    quick, deep = create_model(config, "quick"), create_model(config, "deep")
    catalog = MomentumAgentCatalog(quick, deep)
    assert len(catalog.role_names) == 12
    for role in catalog.role_names | {"reflection"}:
        model = catalog.agent(role).model
        assert isinstance(model, LiteLLMGatewayModel)
        assert model is (deep if role in catalog.DEEP_ROLES else quick)
    for role in catalog.ANALYST_SCHEMAS:
        assert catalog.agent(f"{role}_collector").model is quick


def test_catalog_rejects_direct_provider_strings():
    with pytest.raises(ValueError, match="gateway"):
        MomentumAgentCatalog("gemini-direct", "gemini-direct")
