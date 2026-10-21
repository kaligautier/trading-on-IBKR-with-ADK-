"""Centralized Momentum agent instructions."""

from typing import ClassVar


class MomentumPromptCatalog:
    """Own the stable responsibilities and safety rules of every agent role."""

    _ANALYST_INSTRUCTIONS: ClassVar[dict[str, str]] = {
        "market": (
            "Analyze price, trend, momentum, volatility, support and resistance. "
            "Call get_stock_data first, then retrieve up to eight complementary "
            "indicators. Preserve the exact ticker and analysis date from the input."
        ),
        "social": (
            "Analyze company news, public discussion and retail and institutional "
            "sentiment over the preceding week. Use get_news and distinguish facts "
            "from sentiment."
        ),
        "news": (
            "Analyze company, sector and macroeconomic news over the preceding week. "
            "Use get_news, get_global_news and get_insider_transactions and explain "
            "the expected direction, urgency and uncertainty of every material item."
        ),
        "fundamentals": (
            "Analyze valuation, earnings, growth, margins, balance sheet, cash flow "
            "and capital allocation. Use every relevant fundamental tool and do not "
            "invent a metric that the tools did not return."
        ),
    }

    _ROLE_INSTRUCTIONS: ClassVar[dict[str, str]] = {
        "bull": (
            "Build the strongest evidence-based case for investment. Address the "
            "bear case directly and return one structured BullArgument."
        ),
        "bear": (
            "Build the strongest evidence-based case against investment. Address the "
            "bull case directly and return one structured BearArgument."
        ),
        "research_manager": (
            "Judge the full bull/bear debate and produce a balanced, actionable "
            "ResearchPlan. Do not introduce evidence absent from the input."
        ),
        "trader": (
            "Turn the research plan into a concrete TraderProposal with entry, stop, "
            "target, sizing and risk/reward when supported by the evidence."
        ),
        "aggressive": (
            "Stress-test the proposal from a high-risk, high-reward perspective and "
            "return one structured AggressiveArgument."
        ),
        "conservative": (
            "Stress-test the proposal for capital preservation and downside control "
            "and return one structured ConservativeArgument."
        ),
        "neutral": (
            "Reconcile upside and downside evidence into a balanced compromise and "
            "return one structured NeutralArgument."
        ),
        "portfolio_manager": (
            "Synthesize all research, the trader proposal, past-context lessons and "
            "the risk debate. Return a PortfolioDecision rated exactly Buy, "
            "Overweight, Hold, Underweight or Sell. Respect the request's "
            "output_language. This is analysis, never an order."
        ),
        "next_analysis": (
            "Recommend the next analysis date. It must be at least seven days after "
            "the analysis date; prefer two days before known earnings, seven to ten "
            "days for high volatility, otherwise fourteen days. Respect the request's "
            "output_language for the description."
        ),
        "reflection": (
            "Review the past decision against its raw and alpha returns. Return two "
            "to four concise sentences covering whether the direction was correct, "
            "which thesis held or failed, and one concrete lesson for the next run."
        ),
    }

    _FORMATTER_INSTRUCTION = (
        "Convert the supplied evidence into the requested structured schema. Fill "
        "every field supported by evidence, keep unavailable fields null, and never "
        "invent numbers. Respect the output_language found in the original input."
    )

    def analyst(self, role: str) -> str:
        return self._ANALYST_INSTRUCTIONS[role]

    def formatter(self, role: str) -> str:
        return f"{self._FORMATTER_INSTRUCTION} Analyst role: {role}."

    def role(self, role: str) -> str:
        return self._ROLE_INSTRUCTIONS[role]
