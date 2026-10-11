"""Unit tests for the market scanner ADK workflow."""

from pathlib import Path

import app.components.agents as agents_package


class TestMarketScannerWorkflow:
    def should_expose_only_the_market_scanner_application(self):
        agents_directory = Path(agents_package.__file__).parent
        discovered_applications = {
            path.name
            for path in agents_directory.iterdir()
            if path.is_dir() and (path / "agent.py").is_file()
        }

        assert discovered_applications == {"market_scanner"}

    def should_expose_the_adk_discovery_module(self):
        from app.components.agents.market_scanner.agent import root_agent

        assert root_agent.name == "market_scanner"

    def should_expose_a_named_workflow(self):
        from google.adk import Workflow

        from app.components.agents.market_scanner.agent import root_agent
        from app.config.settings import settings

        assert isinstance(root_agent, Workflow)
        assert root_agent.name == settings.AGENT_NAME

    def should_configure_the_web_researcher(self):
        from app.components.agents.market_scanner.agent import researcher
        from app.components.callbacks.after_agent import record_agent_end
        from app.components.callbacks.before_agent import record_agent_start
        from app.components.callbacks.tool_callbacks import (
            record_tool_end,
            record_tool_start,
        )
        from app.config.constants import STATE_WEB_ANALYSIS
        from app.config.settings import settings

        assert researcher.name == "market_web_researcher"
        assert researcher.model.model == settings.MODEL
        assert researcher.model.client_kwargs["vertexai"] is False
        assert researcher.model.client_kwargs["enterprise"] is False
        assert researcher.model.client_kwargs["http_options"].base_url == (
            settings.LITELLM_API_BASE.rstrip("/")
        )
        assert researcher.after_model_callback is None
        assert researcher.mode == "single_turn"
        assert researcher.instruction
        assert researcher.output_key == STATE_WEB_ANALYSIS
        assert len(researcher.tools) == 5
        assert researcher.before_agent_callback is record_agent_start
        assert researcher.after_agent_callback is record_agent_end
        assert researcher.before_tool_callback is record_tool_start
        assert researcher.after_tool_callback is record_tool_end

    def should_configure_the_market_synthesizer(self):
        from app.components.agents.market_scanner.agent import synthesizer
        from app.components.callbacks.after_agent import record_agent_end
        from app.components.callbacks.before_agent import record_agent_start
        from app.config.constants import STATE_MARKET_ANALYSIS
        from app.config.settings import settings
        from app.models.structured_output.unsourced_market_analysis import (
            UnsourcedMarketAnalysis,
        )

        assert synthesizer.name == "market_synthesizer"
        assert synthesizer.model.model == settings.MODEL
        assert synthesizer.mode == "single_turn"
        assert synthesizer.instruction
        assert synthesizer.output_key == STATE_MARKET_ANALYSIS
        assert synthesizer.output_schema is UnsourcedMarketAnalysis
        assert synthesizer.before_agent_callback is record_agent_start
        assert synthesizer.after_agent_callback is record_agent_end

    def should_prepare_assess_assemble_and_persist_market_data(self):
        from app.components.agents.market_scanner.agent import (
            assemble_market_data,
            get_market_data,
            persist_market_scan,
        )

        assert get_market_data.name == "get_market_data"
        assert assemble_market_data.name == "assemble_market_data"
        assert persist_market_scan.name == "persist_market_scan"
