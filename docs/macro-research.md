# Macro research tools

The Market Scanner research agent now uses the TradingAgents News Analyst's
macro-first approach. It retrieves structured context and Google Search evidence,
a tool-free critic reviews the research, then a separate agent synthesizes the report. Python still computes all market
values, horizons and historical percentiles. Research does not place orders.

## Tools

| ADK function | Input | Provider and scope |
| --- | --- | --- |
| `get_news` | `asset_key` | Yahoo Finance news tagged with the catalog symbol, from its observation date minus seven days through that date |
| `get_global_news` | none | Yahoo relevance searches for markets, monetary policy, inflation, economy, ECB and energy, over the analysis date's preceding week |
| `get_macro_indicators` | `indicator` | FRED metadata and latest 14 valid observations from a 400-day window, at the analysis date's vintage |
| `get_prediction_markets` | `topic` | Up to six open Polymarket markets by volume, including all outcome probabilities, volume and resolution timestamps |

Function arguments never override Python's analysis date or instrument identity.
The analysis date is UTC; individual news is additionally capped at the asset's
observation date. Yahoo serves recent relevance samples, not a historical archive.
An empty sample does not prove absence of news. Undated, future and unrelated
instrument articles are excluded. News reports cannot explain earlier prices.

FRED aliases: `cpi`, `core_pce`, `unemployment`, `payrolls`, `gdp`, `fedfunds`,
`treasury_2y`, `treasury_10y`, `yield_curve`, `ecb_deposit_rate`, `eurozone_hicp`.
Both metadata and observations specify `realtime_start` and `realtime_end`.
The vintage is capped to the current Chicago date (FRED's clock). Index levels
are not annual inflation rates; observation periods are not release dates.
Live Polymarket odds are withheld whenever the requested date is not today's
UTC date. Resolved/expired markets and malformed outcomes are excluded.
Market-implied probabilities are not facts. Volume does not prove accuracy.

## Configuration and resilience

`MARKET_SCANNER_RESEARCH_TOOLS_ENABLED=true` enables structured research by default.
Set it to `false` to retain Google Search with explicit unavailable tool results.
`FRED_API_KEY` is optional, hidden in settings representations, and must be supplied
through your local ignored `.env` or deployment secret configuration. Never commit it.
No Yahoo or Polymarket API key is required. Configure secrets separately when deploying.

Requests use eight-second network timeouts and at most two attempts; outer coroutine
timeouts also bound threaded I/O. Retries apply to transient HTTP failures; malformed
responses, missing configuration and empty samples become explicit results. TLS
verification is retained. Exception messages and request URLs are excluded from tool
results, so a FRED key is never returned to the model or copied into error logs.
Global/macro calls are cached only within a scan, including concurrent duplicate calls.
The shared 40-call budget includes pending requests. New scans clear the cache.

ADK 2.6.1 and the configured Gemini 3.8 Flash model support these four function tools
alongside `google_search`. The real Vertex combination was exercised locally; older
or alternative models must be checked before replacing the configured model.

## Research critique and arbitration

Workflow: Python collection/calculations → `market_web_researcher` →
`market_research_critic` → `market_synthesizer` → assembly/persistence.

Like TradingAgents' debate agents, the critic has a dedicated prompt and no external
tools. It receives the current snapshot, structured tool results and research prose.
It challenges both optimistic and cautious explanations without forcing disagreement
or a trading stance. This is a single adapted review, not the upstream multi-round
Bull/Bear and risk debate. Configure `CRITIC_THINKING_LEVEL` (default `MEDIUM`) or
`MARKET_SCANNER_CRITIC_THINKING_LEVEL`; it uses the same configured model.

Its required, validated `ResearchCritique` output contains up to three supported
findings, six specific challenges with reasons and suggested revisions, three
observable invalidation conditions and five material data gaps. It is written to
`research_critique` in session state, cleared at collection for a new scan, and supplied
to the synthesizer. Invalid output fails the scan before synthesis or persistence;
there is no silent bypass. The critic adds one model stage and existing agent
callbacks record its start/end. It cannot independently verify external claims.

The synthesizer weighs the review against the original evidence, corrects substantiated
issues and retains supported macro context. Disagreement alone does not force a
cautious regime. The critique stays internal; public report v3 and database schemas
are unchanged. The new report still carries macro context, counter-evidence, gaps
and watch points through the existing fields.

## Report and writing contract

Report v3 gains an optional `macro_overview` (defaults to `null` for old reports):
`context`, up to three `themes`, and `data_gaps`. New synthesis output requires
this section; only the public reader permits it to be absent for older reports. Each macro theme has `title`,
`asset_keys`, `observation`, `development`, `transmission`, `counter_evidence`,
`uncertainty` and `status` (`hypothesis` or `unestablished`). Only successful assets
may appear. The new fields are carried through assembly and stored in the existing
`market_scans.report` JSONB; no database migration is required. Existing summary,
family insights and asset calculations remain available. Consumers with a strict
field allowlist should add `macro_overview` before consuming the extended payload.

The prompt seeks substantive policy/growth/inflation/earnings/geopolitical context,
conditional transmission channels, contradictory evidence and material gaps. It
adapts the upstream Markdown table to structured fields. It never treats a retrieved
headline, co-movement or an unsourced explanation as independently verified causality.
The public policy remains `sources: []`, empty `source_ids`, and no URLs/citation IDs.
Investment recommendations and global regime labels belong to the downstream agent.

## Verification

From `apps/backend/market-scanner-adk`:

```sh
TZ=UTC uv run pytest src/test/unit -q
uv run ruff check src
```

Use the disposable PostgreSQL setup in `database/README.md` for integration tests.
A real scan must additionally prove function calls, schema validation, PostgreSQL
re-read equality, and useful macro content. Passing fixture tests alone does not
prove live report quality or deployment. Upstream attribution and license are in
`apps/backend/market-scanner-adk/third_party/`.

Primary references:
- [TradingAgents Neutral Risk Analyst](https://github.com/TauricResearch/TradingAgents/blob/1394a3f72aa4393e1a98f51b382434c4b4c2d972/tradingagents/agents/risk_mgmt/neutral_debator.py)
- [TradingAgents Research Manager](https://github.com/TauricResearch/TradingAgents/blob/1394a3f72aa4393e1a98f51b382434c4b4c2d972/tradingagents/agents/managers/research_manager.py)
- [TradingAgents News Analyst](https://github.com/TauricResearch/TradingAgents/blob/1394a3f72aa4393e1a98f51b382434c4b4c2d972/tradingagents/agents/analysts/news_analyst.py)
- [FRED observations and real-time periods](https://fred.stlouisfed.org/docs/api/fred/series_observations.html)
- [Polymarket public search](https://docs.polymarket.com/api-reference/search/search-markets-events-and-profiles)
- [Gemini built-in and function tool combination](https://ai.google.dev/gemini-api/docs/generate-content/tool-combination)
