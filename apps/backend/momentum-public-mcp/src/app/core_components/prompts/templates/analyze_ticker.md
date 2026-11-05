Summarize the existing Momentum analysis for the provided ticker.
1. Call momentum_latest_analyses with the provided ticker, then read its items and call momentum_get_analysis with the returned analysis ID. If items is empty but next_page_token is nonempty, call momentum_latest_analyses again with that page_token and the same ticker. Only an empty next_page_token ends the list; if no analysis exists, state that clearly.
2. Read momentum://market_scanner/market-scans/latest for market context.
3. Present the thesis, supporting evidence, risks and missing data. Cite the analysis ID, analysis date and scan date. Distinguish the report's conclusions from your own interpretation.
Use existing reports only; do not submit a suggestion or start an analysis.
