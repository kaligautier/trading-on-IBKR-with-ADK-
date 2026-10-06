# TradingAgents attribution

The research adapter and macro research prompt are derived from
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents),
commit `1394a3f72aa4393e1a98f51b382434c4b4c2d972`, licensed under Apache-2.0.
A copy of the upstream license is in `TradingAgents-LICENSE`.

Adapted files: `src/app/client/market_research_client.py` and
`src/app/instructions/templates/market_scanner/asset_web_researcher_instruction.j2`.
Upstream sources: News Analyst, Yahoo news, FRED and Polymarket vendors.

Scanner changes: ADK functions replace LangChain decorators; bounded JSON data
replaces Markdown reports; dates are supplied by Python; stricter date/outcome
validation, per-scan cache, missing-data results and safe error messages;
macro prose is adapted to the English unsourced JSON contract. No upstream
LangGraph workflow or trading/portfolio execution is included.
