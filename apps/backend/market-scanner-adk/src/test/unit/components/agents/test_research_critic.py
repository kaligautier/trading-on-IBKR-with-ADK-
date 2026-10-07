"""The critique is a bounded review of supplied evidence, without external tools."""

import pytest
from pydantic import ValidationError

from app.models.structured_output.research_critique import ResearchCritique


def critique_payload():
    return {
        "supported_findings": ["The snapshot shows rising equities."],
        "challenges": [
            {
                "claim": "A rate cut caused the equity move.",
                "concern": "unsupported_fact",
                "reasoning": "The rate dataset is unavailable.",
                "suggested_revision": "Leave the catalyst unestablished.",
            }
        ],
        "invalidation_conditions": ["Equities reverse their observed direction."],
        "data_gaps": ["No macro series is available."],
    }


def should_accept_an_empty_review_without_manufacturing_disagreement():
    # Arrange
    payload = {key: [] for key in critique_payload()}
    # Act
    review = ResearchCritique.model_validate(payload)
    # Assert
    assert review.model_dump() == payload


@pytest.mark.parametrize(
    "field,value",
    [
        ("concern", "verified_cause"),
        ("reasoning", "https://example.org/source"),
        ("claim", "   "),
    ],
)
def should_reject_invalid_review_claims(field, value):
    # Arrange
    payload = critique_payload()
    payload["challenges"][0][field] = value
    # Act
    with pytest.raises(ValidationError) as error:
        ResearchCritique.model_validate(payload)
    # Assert
    assert field in str(error.value)


@pytest.mark.parametrize(
    "field,limit",
    [
        ("supported_findings", 3),
        ("challenges", 6),
        ("invalidation_conditions", 3),
        ("data_gaps", 5),
    ],
)
def should_bound_the_review_before_synthesis(field, limit):
    # Arrange
    payload = critique_payload()
    payload[field] = payload[field] * (limit + 1)
    # Act
    with pytest.raises(ValidationError) as error:
        ResearchCritique.model_validate(payload)
    # Assert
    assert field in str(error.value)


def should_configure_a_separate_critic_without_external_tools():
    # Arrange
    from app.components.agents.market_scanner.agent import critic
    from app.components.callbacks.after_agent import record_agent_end
    from app.components.callbacks.before_agent import record_agent_start
    from app.config.settings import settings

    # Act
    thinking = critic.generate_content_config.thinking_config
    # Assert
    assert critic.name == "market_research_critic"
    assert critic.tools == []
    assert critic.include_contents == "none"
    assert critic.mode == "single_turn"
    assert critic.output_schema is ResearchCritique
    assert critic.output_key == "research_critique"
    assert critic.model.model == settings.MODEL
    assert thinking.thinking_level == settings.CRITIC_THINKING_LEVEL
    assert critic.before_agent_callback is record_agent_start
    assert critic.after_agent_callback is record_agent_end


@pytest.mark.parametrize(
    "invalid",
    [
        {"unsupported": "field"},
        {"supported_findings": ["A"] * 4},
        {"challenges": [{"claim": "Incomplete issue"}]},
    ],
)
async def should_stop_before_synthesis_and_persistence_when_the_critique_is_invalid(
    monkeypatch,
    invalid,
):
    # Arrange
    import json
    from unittest.mock import AsyncMock

    from google.adk.models import LlmResponse
    from google.adk.models.google_llm import Gemini
    from google.genai import types

    from app.components.agents.market_scanner import agent as scanner
    from test.unit.components.agents.test_regime_workflow import market_data, run_graph

    data, requests = market_data(), []
    monkeypatch.setattr(scanner.market_data_collection_service, "collect", lambda: data)
    save = AsyncMock()
    monkeypatch.setattr(scanner.MarketScanPersistence, "save", save)

    async def respond(_self, llm_request, stream=False):
        requests.append(llm_request)
        output = "Research about the supplied snapshot."
        if llm_request.config.response_schema is ResearchCritique:
            payload = critique_payload()
            payload.update(invalid)
            output = json.dumps(payload)
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=output)])
        )

    monkeypatch.setattr(Gemini, "generate_content_async", respond)
    # Act
    with pytest.raises(ValueError):
        await run_graph()
    # Assert
    assert len(requests) == 2
    assert requests[-1].config.response_schema is ResearchCritique
    save.assert_not_called()
