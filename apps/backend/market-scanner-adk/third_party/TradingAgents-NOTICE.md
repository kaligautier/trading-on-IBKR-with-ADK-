# TradingAgents attribution

The research adapter, macro research prompt and research critique prompt are derived from
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents),
commit `1394a3f72aa4393e1a98f51b382434c4b4c2d972`, licensed under Apache-2.0.
A copy of the upstream license is in `TradingAgents-LICENSE`.

Adapted files: `src/app/client/market_research_client.py` and
`src/app/instructions/templates/market_scanner/asset_web_researcher_instruction.j2`,
`src/app/instructions/templates/market_scanner/market_research_critic_instruction.j2`
and the research arbitration section of
`src/app/instructions/templates/market_scanner/market_synthesizer_instruction.j2`.
Upstream sources: News Analyst, Yahoo news, FRED and Polymarket vendors;
Bull/Bear Researchers, Neutral Risk Analyst and Research Manager.

Scanner changes: ADK functions replace LangChain decorators; bounded JSON data
replaces Markdown reports; dates are supplied by Python; stricter date/outcome
validation, per-scan cache, missing-data results and safe error messages;
macro prose is adapted to the English unsourced JSON contract; a single bounded,
tool-free critique replaces the upstream investment debate and passes structured
findings to the synthesizer. This is an adaptation, not the full trading workflow. No upstream
LangGraph workflow or trading/portfolio execution is included.
