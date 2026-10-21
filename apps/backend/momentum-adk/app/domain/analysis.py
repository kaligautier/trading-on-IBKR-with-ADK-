"""Pydantic schemas for all Momentum agents and persistence renderers.

Every agent produces a typed Pydantic model. The render functions convert them
to markdown for backward compatibility with the existing pipeline.
Typed payloads are retained for PostgreSQL persistence.
Ported from DeepCopy 38d0736 with string wrapping for the local style rules.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# ===========================================================================
# Shared types
# ===========================================================================


class PortfolioRating(str, Enum):
    BUY = "Buy"
    OVERWEIGHT = "Overweight"
    HOLD = "Hold"
    UNDERWEIGHT = "Underweight"
    SELL = "Sell"


class TraderAction(str, Enum):
    BUY = "Buy"
    HOLD = "Hold"
    SELL = "Sell"


# ===========================================================================
# 1. MARKET ANALYST
# ===========================================================================


class IndicatorAnalysis(BaseModel):
    """A single technical indicator with value + LLM interpretation."""

    value: Optional[float] = Field(
        default=None, description="Numeric value of the indicator."
    )
    signal: Optional[str] = Field(
        default=None,
        description="Short signal label: Bullish, Bearish, Overbought, Oversold, "
        "Neutral, High Volatility, Low Volatility, Resistance, Support.",
    )
    interpretation: Optional[str] = Field(
        default=None,
        description="One-sentence actionable interpretation for traders.",
    )


class MarketAnalysis(BaseModel):
    """Structured output from the Market Analyst."""

    close_price: Optional[IndicatorAnalysis] = Field(
        default=None, description="Latest closing price."
    )
    sma_50: Optional[IndicatorAnalysis] = Field(
        default=None, description="50-day Simple Moving Average."
    )
    sma_200: Optional[IndicatorAnalysis] = Field(
        default=None, description="200-day Simple Moving Average."
    )
    ema_10: Optional[IndicatorAnalysis] = Field(default=None, description="10-day EMA.")
    rsi: Optional[IndicatorAnalysis] = Field(
        default=None, description="14-period RSI (0-100)."
    )
    macd: Optional[IndicatorAnalysis] = Field(
        default=None, description="MACD line value."
    )
    macd_signal_line: Optional[IndicatorAnalysis] = Field(
        default=None, description="MACD signal line value."
    )
    macd_histogram: Optional[IndicatorAnalysis] = Field(
        default=None, description="MACD histogram value."
    )
    boll_upper: Optional[IndicatorAnalysis] = Field(
        default=None, description="Bollinger upper band."
    )
    boll_lower: Optional[IndicatorAnalysis] = Field(
        default=None, description="Bollinger lower band."
    )
    atr: Optional[IndicatorAnalysis] = Field(
        default=None, description="Average True Range (volatility)."
    )
    vwma: Optional[IndicatorAnalysis] = Field(
        default=None, description="Volume-Weighted Moving Average."
    )
    mfi: Optional[IndicatorAnalysis] = Field(
        default=None, description="Money Flow Index (0-100)."
    )
    trend_direction: Optional[str] = Field(
        default=None,
        description=(
            "One of: Strong Uptrend, Uptrend, Sideways, Downtrend, Strong Downtrend."
        ),
    )
    momentum_state: Optional[str] = Field(
        default=None,
        description="One of: Accelerating, Stable, Decelerating, Reversing.",
    )
    volatility_regime: Optional[str] = Field(
        default=None, description="One of: Low, Normal, High, Extreme."
    )
    key_support: Optional[float] = Field(
        default=None, description="Key support price level."
    )
    key_resistance: Optional[float] = Field(
        default=None, description="Key resistance price level."
    )
    actionable_recommendation: Optional[str] = Field(
        default=None,
        description="One of: Buy Now, Buy on Pullback, Hold, Take Profits, Sell.",
    )
    summary_short: Optional[str] = Field(
        default=None, description="2-3 sentence market summary."
    )
    summary_long: Optional[str] = Field(
        default=None,
        description="Detailed analysis with actionable insights, 2-3 paragraphs.",
    )


def render_market_analysis(a: MarketAnalysis) -> str:
    rows = []
    for name, label in [
        ("close_price", "Close"),
        ("sma_50", "SMA 50"),
        ("sma_200", "SMA 200"),
        ("ema_10", "EMA 10"),
        ("rsi", "RSI"),
        ("macd", "MACD"),
        ("macd_signal_line", "MACD Signal"),
        ("macd_histogram", "MACD Hist"),
        ("boll_upper", "Boll Upper"),
        ("boll_lower", "Boll Lower"),
        ("atr", "ATR"),
        ("vwma", "VWMA"),
        ("mfi", "MFI"),
    ]:
        ind = getattr(a, name)
        if ind is not None:
            rows.append(
                f"| **{label}** | {ind.value} | {ind.signal} | {ind.interpretation} |"
            )
    table = (
        "| Indicator | Value | Signal | Interpretation |\n"
        "| :--- | :--- | :--- | :--- |\n" + "\n".join(rows)
    )
    summary = a.summary_long or ""
    recommendation = (a.actionable_recommendation or "N/A").upper()
    return f"{summary}\n\n{table}\n\nFINAL TRANSACTION PROPOSAL: **{recommendation}**"


# ===========================================================================
# 2. FUNDAMENTALS ANALYST
# ===========================================================================


class FundamentalMetric(BaseModel):
    """A single fundamental metric with value + LLM interpretation."""

    value: Optional[float] = Field(
        default=None, description="Numeric value of the metric."
    )
    unit: Optional[str] = Field(
        default=None, description="Unit: USD, %, x, ratio, or Bn USD."
    )
    trend: Optional[str] = Field(
        default=None, description="One of: rising, stable, declining."
    )
    comment: Optional[str] = Field(
        default=None, description="One-sentence interpretation."
    )


class FundamentalsAnalysis(BaseModel):
    """Structured output from the Fundamentals Analyst."""

    # Valuation
    market_cap: Optional[FundamentalMetric] = Field(
        default=None, description="Market capitalization."
    )
    pe_ratio: Optional[FundamentalMetric] = Field(
        default=None, description="Trailing P/E ratio."
    )
    forward_pe: Optional[FundamentalMetric] = Field(
        default=None, description="Forward P/E ratio."
    )
    peg_ratio: Optional[FundamentalMetric] = Field(
        default=None, description="PEG ratio."
    )
    price_to_book: Optional[FundamentalMetric] = Field(
        default=None, description="Price-to-book ratio."
    )
    # Earnings
    eps_ttm: Optional[FundamentalMetric] = Field(
        default=None, description="EPS trailing twelve months."
    )
    forward_eps: Optional[FundamentalMetric] = Field(
        default=None, description="Forward EPS estimate."
    )
    # Revenue & Profit
    revenue: Optional[FundamentalMetric] = Field(
        default=None, description="Total revenue TTM."
    )
    gross_profit: Optional[FundamentalMetric] = Field(
        default=None, description="Gross profit."
    )
    ebitda: Optional[FundamentalMetric] = Field(default=None, description="EBITDA.")
    net_income: Optional[FundamentalMetric] = Field(
        default=None, description="Net income TTM."
    )
    # Margins
    profit_margin: Optional[FundamentalMetric] = Field(
        default=None, description="Net profit margin (decimal)."
    )
    operating_margin: Optional[FundamentalMetric] = Field(
        default=None, description="Operating margin (decimal)."
    )
    # Returns
    roe: Optional[FundamentalMetric] = Field(
        default=None, description="Return on equity (decimal)."
    )
    roa: Optional[FundamentalMetric] = Field(
        default=None, description="Return on assets (decimal)."
    )
    # Balance sheet
    debt_to_equity: Optional[FundamentalMetric] = Field(
        default=None, description="Debt-to-equity ratio."
    )
    current_ratio: Optional[FundamentalMetric] = Field(
        default=None, description="Current ratio."
    )
    total_cash: Optional[FundamentalMetric] = Field(
        default=None, description="Total cash and equivalents."
    )
    free_cash_flow: Optional[FundamentalMetric] = Field(
        default=None, description="Free cash flow."
    )
    # Capital allocation
    capex: Optional[FundamentalMetric] = Field(
        default=None, description="Capital expenditures."
    )
    buyback_amount: Optional[FundamentalMetric] = Field(
        default=None, description="Share buyback amount."
    )
    dividend_yield: Optional[FundamentalMetric] = Field(
        default=None, description="Dividend yield (decimal)."
    )
    beta: Optional[FundamentalMetric] = Field(
        default=None, description="Beta coefficient."
    )
    # Price context
    week_52_high: Optional[FundamentalMetric] = Field(
        default=None, description="52-week high price."
    )
    week_52_low: Optional[FundamentalMetric] = Field(
        default=None, description="52-week low price."
    )
    # Summary
    financial_health: Optional[str] = Field(
        default=None, description="One of: Excellent, Strong, Adequate, Weak, Critical."
    )
    growth_outlook: Optional[str] = Field(
        default=None,
        description="One of: Very Strong, Strong, Moderate, Slow, Declining.",
    )
    valuation_assessment: Optional[str] = Field(
        default=None,
        description=(
            "One of: Undervalued, Fair Value, Slightly Overvalued, Overvalued, Bubble."
        ),
    )
    summary_short: Optional[str] = Field(
        default=None, description="2-3 sentence fundamentals summary."
    )
    summary_long: Optional[str] = Field(
        default=None, description="Detailed fundamental analysis, 2-3 paragraphs."
    )


def render_fundamentals_analysis(a: FundamentalsAnalysis) -> str:
    rows = []
    for name, label in [
        ("market_cap", "Market Cap"),
        ("pe_ratio", "P/E"),
        ("forward_pe", "Fwd P/E"),
        ("peg_ratio", "PEG"),
        ("price_to_book", "P/B"),
        ("eps_ttm", "EPS TTM"),
        ("forward_eps", "Fwd EPS"),
        ("revenue", "Revenue"),
        ("gross_profit", "Gross Profit"),
        ("ebitda", "EBITDA"),
        ("net_income", "Net Income"),
        ("profit_margin", "Profit Margin"),
        ("operating_margin", "Op Margin"),
        ("roe", "ROE"),
        ("roa", "ROA"),
        ("debt_to_equity", "D/E"),
        ("current_ratio", "Current Ratio"),
        ("total_cash", "Cash"),
        ("free_cash_flow", "FCF"),
        ("capex", "CapEx"),
        ("buyback_amount", "Buybacks"),
        ("dividend_yield", "Div Yield"),
        ("beta", "Beta"),
        ("week_52_high", "52w High"),
        ("week_52_low", "52w Low"),
    ]:
        m = getattr(a, name)
        if m is not None:
            rows.append(
                f"| **{label}** | {m.value} {m.unit} | {m.trend} | {m.comment} |"
            )
    table = (
        "| Metric | Value | Trend | Comment |\n| :--- | :--- | :--- | :--- |\n"
        + "\n".join(rows)
    )
    summary = a.summary_long or ""
    return f"{summary}\n\n{table}"


# ===========================================================================
# 3. SENTIMENT ANALYST
# ===========================================================================


class SentimentItem(BaseModel):
    """A single sentiment topic."""

    topic: Optional[str] = Field(
        default=None,
        description="Topic or theme (e.g. 'Anthropic partnership', 'EU regulation').",
    )
    sentiment_score: Optional[float] = Field(
        default=None,
        description="Score from -1.0 (very negative) to 1.0 (very positive).",
    )
    impact: Optional[str] = Field(
        default=None,
        description=(
            "One of: very_positive, positive, neutral, negative, very_negative."
        ),
    )
    source_type: Optional[str] = Field(
        default=None,
        description="One of: social_media, institutional, news, analyst, insider.",
    )
    comment: Optional[str] = Field(
        default=None, description="One-sentence explanation of this sentiment driver."
    )


class SentimentAnalysis(BaseModel):
    """Structured output from the Sentiment / Social Media Analyst."""

    overall_sentiment: Optional[float] = Field(
        default=None, description="Overall sentiment score from -1.0 to 1.0."
    )
    overall_signal: Optional[str] = Field(
        default=None,
        description=(
            "One of: Extremely Bullish, Bullish, Neutral, Bearish, Extremely Bearish."
        ),
    )
    retail_sentiment: Optional[str] = Field(
        default=None,
        description="One of: Very Positive, Positive, Mixed, Negative, Very Negative.",
    )
    institutional_sentiment: Optional[str] = Field(
        default=None,
        description="One of: Very Positive, Positive, Mixed, Negative, Very Negative.",
    )
    items: list[SentimentItem] = Field(
        description="List of sentiment topics identified (5-10 items)."
    )
    key_risk_from_sentiment: Optional[str] = Field(
        default=None,
        description="Main risk identified from sentiment analysis, one sentence.",
    )
    key_catalyst_from_sentiment: Optional[str] = Field(
        default=None,
        description="Main catalyst identified from sentiment, one sentence.",
    )
    summary_short: Optional[str] = Field(
        default=None, description="2-3 sentence sentiment summary."
    )
    summary_long: Optional[str] = Field(
        default=None, description="Detailed sentiment analysis, 2-3 paragraphs."
    )


def render_sentiment_analysis(a: SentimentAnalysis) -> str:
    rows = []
    for item in a.items:
        rows.append(
            f"| {item.topic} | {item.sentiment_score} | {item.impact}"
            f" | {item.source_type} | {item.comment} |"
        )
    table = (
        "| Topic | Score | Impact | Source | Comment |\n"
        "| :--- | :--- | :--- | :--- | :--- |\n" + "\n".join(rows)
    )
    signal = a.overall_signal or "N/A"
    sentiment = a.overall_sentiment if a.overall_sentiment is not None else "N/A"
    summary = a.summary_long or ""
    return f"{summary}\n\nOverall: **{signal}** ({sentiment})\n\n{table}"


# ===========================================================================
# 4. NEWS ANALYST
# ===========================================================================


class NewsItem(BaseModel):
    """A single news event."""

    category: Optional[str] = Field(
        default=None,
        description=(
            "One of: earnings, partnership, regulation, litigation, energy, "
            "macro, competition, product, other."
        ),
    )
    headline: Optional[str] = Field(
        default=None, description="Short headline summarizing the news."
    )
    impact: Optional[str] = Field(
        default=None,
        description=(
            "One of: very_positive, positive, neutral, negative, very_negative."
        ),
    )
    urgency: Optional[str] = Field(
        default=None,
        description="One of: immediate, short_term, medium_term, long_term.",
    )
    comment: Optional[str] = Field(
        default=None, description="One-sentence explanation of market impact."
    )


class NewsAnalysis(BaseModel):
    """Structured output from the News Analyst."""

    overall_impact: Optional[str] = Field(
        default=None,
        description=(
            "One of: Very Positive, Positive, Neutral, Negative, Very Negative."
        ),
    )
    macro_environment: Optional[str] = Field(
        default=None, description="One of: Risk-On, Neutral, Risk-Off."
    )
    sector_momentum: Optional[str] = Field(
        default=None, description="One of: Strong, Moderate, Weak, Negative."
    )
    items: list[NewsItem] = Field(
        description="List of news items identified (5-10 items)."
    )
    key_catalyst: Optional[str] = Field(
        default=None,
        description="Single most important positive catalyst, one sentence.",
    )
    key_risk: Optional[str] = Field(
        default=None, description="Single most important risk factor, one sentence."
    )
    summary_short: Optional[str] = Field(
        default=None, description="2-3 sentence news summary."
    )
    summary_long: Optional[str] = Field(
        default=None, description="Detailed news analysis, 2-3 paragraphs."
    )


def render_news_analysis(a: NewsAnalysis) -> str:
    rows = []
    for item in a.items:
        rows.append(
            f"| {item.category} | {item.headline} | {item.impact}"
            f" | {item.urgency} | {item.comment} |"
        )
    table = (
        "| Category | Headline | Impact | Urgency | Comment |\n"
        "| :--- | :--- | :--- | :--- | :--- |\n" + "\n".join(rows)
    )
    summary = a.summary_long or ""
    overall = a.overall_impact or "N/A"
    macro = a.macro_environment or "N/A"
    sector = a.sector_momentum or "N/A"
    return (
        f"{summary}\n\nOverall: **{overall}** | Macro: {macro}"
        f" | Sector: {sector}\n\n{table}"
    )


# ===========================================================================
# 5. BULL RESEARCHER
# ===========================================================================


class BullArgument(BaseModel):
    """Structured output from the Bull Researcher (one round)."""

    thesis: Optional[str] = Field(
        default=None, description="Core bull thesis in 2-3 sentences."
    )
    growth_drivers: Optional[list[str]] = Field(
        default=None, description="3-5 specific growth catalysts with data points."
    )
    competitive_advantages: Optional[list[str]] = Field(
        default=None, description="2-4 competitive moats or advantages."
    )
    bear_rebuttals: Optional[list[str]] = Field(
        default=None,
        description="2-4 direct rebuttals to bear arguments with evidence.",
    )
    target_price: Optional[float] = Field(
        default=None, description="Bull target price."
    )
    target_upside_pct: Optional[float] = Field(
        default=None, description="Expected upside percentage."
    )
    conviction_level: Optional[str] = Field(
        default=None, description="One of: Very High, High, Moderate, Low."
    )
    key_data_point: Optional[str] = Field(
        default=None,
        description="Single most compelling data point supporting the bull case.",
    )
    argument_full: Optional[str] = Field(
        default=None, description="Full conversational argument text, 3-5 paragraphs."
    )


def render_bull_argument(a: BullArgument) -> str:
    return f"Bull Analyst: {a.argument_full or ''}"


# ===========================================================================
# 6. BEAR RESEARCHER
# ===========================================================================


class BearArgument(BaseModel):
    """Structured output from the Bear Researcher (one round)."""

    thesis: Optional[str] = Field(
        default=None, description="Core bear thesis in 2-3 sentences."
    )
    risk_factors: Optional[list[str]] = Field(
        default=None, description="3-5 specific risk factors with data points."
    )
    valuation_concerns: Optional[list[str]] = Field(
        default=None, description="2-4 valuation or overpricing concerns."
    )
    bull_rebuttals: Optional[list[str]] = Field(
        default=None,
        description="2-4 direct rebuttals to bull arguments with evidence.",
    )
    downside_target: Optional[float] = Field(
        default=None, description="Bear target / re-entry price."
    )
    downside_risk_pct: Optional[float] = Field(
        default=None, description="Expected downside percentage."
    )
    conviction_level: Optional[str] = Field(
        default=None, description="One of: Very High, High, Moderate, Low."
    )
    key_data_point: Optional[str] = Field(
        default=None,
        description="Single most compelling data point supporting the bear case.",
    )
    argument_full: Optional[str] = Field(
        default=None, description="Full conversational argument text, 3-5 paragraphs."
    )


def render_bear_argument(a: BearArgument) -> str:
    return f"Bear Analyst: {a.argument_full or ''}"


# ===========================================================================
# 7. RESEARCH MANAGER (judge of bull/bear debate)
# ===========================================================================


class ResearchPlan(BaseModel):
    """Structured investment plan from the Research Manager."""

    recommendation: PortfolioRating = Field(
        description="Exactly one of Buy / Overweight / Hold / Underweight / Sell.",
    )
    rationale: Optional[str] = Field(
        default=None,
        description=(
            "Summary of key points from both sides, ending with which arguments won."
        ),
    )
    strategic_actions: Optional[str] = Field(
        default=None,
        description="Concrete steps for the trader including position sizing.",
    )


def render_research_plan(plan: ResearchPlan) -> str:
    parts = [f"**Recommendation**: {plan.recommendation.value}"]
    if plan.rationale is not None:
        parts.extend(["", f"**Rationale**: {plan.rationale}"])
    if plan.strategic_actions is not None:
        parts.extend(["", f"**Strategic Actions**: {plan.strategic_actions}"])
    return "\n".join(parts)


# ===========================================================================
# 8. TRADER
# ===========================================================================


class TraderProposal(BaseModel):
    """Structured transaction proposal from the Trader."""

    action: TraderAction = Field(description="Exactly one of Buy / Hold / Sell.")
    reasoning: Optional[str] = Field(
        default=None, description="2-4 sentence case for this action."
    )
    entry_price: Optional[float] = Field(
        default=None, description="Entry price target."
    )
    stop_loss: Optional[float] = Field(default=None, description="Stop-loss price.")
    take_profit: Optional[float] = Field(
        default=None, description="Take-profit target price."
    )
    position_sizing: Optional[str] = Field(
        default=None, description="Sizing guidance, e.g. '5% of portfolio'."
    )
    risk_reward_ratio: Optional[str] = Field(
        default=None, description="Risk/reward ratio, e.g. '1:3'."
    )


def render_trader_proposal(p: TraderProposal) -> str:
    parts = [f"**Action**: {p.action.value}"]
    if p.reasoning is not None:
        parts.extend(["", f"**Reasoning**: {p.reasoning}"])
    if p.entry_price is not None:
        parts.extend(["", f"**Entry Price**: {p.entry_price}"])
    if p.stop_loss is not None:
        parts.extend(["", f"**Stop Loss**: {p.stop_loss}"])
    if p.take_profit is not None:
        parts.extend(["", f"**Take Profit**: {p.take_profit}"])
    if p.position_sizing:
        parts.extend(["", f"**Position Sizing**: {p.position_sizing}"])
    if p.risk_reward_ratio:
        parts.extend(["", f"**Risk/Reward**: {p.risk_reward_ratio}"])
    parts.extend(["", f"FINAL TRANSACTION PROPOSAL: **{p.action.value.upper()}**"])
    return "\n".join(parts)


# ===========================================================================
# 9. AGGRESSIVE RISK ANALYST
# ===========================================================================


class AggressiveArgument(BaseModel):
    """Structured output from the Aggressive Risk Analyst (one round)."""

    stance: Optional[str] = Field(
        default=None, description="One of: Strong Buy, Buy, Lean Buy."
    )
    thesis: Optional[str] = Field(
        default=None, description="Core aggressive thesis in 2-3 sentences."
    )
    upside_catalysts: Optional[list[str]] = Field(
        default=None, description="3-5 reasons the upside outweighs the risk."
    )
    conservative_rebuttals: Optional[list[str]] = Field(
        default=None, description="2-4 rebuttals to conservative concerns."
    )
    neutral_rebuttals: Optional[list[str]] = Field(
        default=None, description="2-4 rebuttals to neutral caution."
    )
    recommended_position_size: Optional[str] = Field(
        default=None, description="Recommended position size, e.g. '5% overweight'."
    )
    recommended_entry: Optional[float] = Field(
        default=None, description="Recommended entry price."
    )
    conviction_level: Optional[str] = Field(
        default=None, description="One of: Very High, High, Moderate."
    )
    argument_full: Optional[str] = Field(
        default=None, description="Full conversational argument text, 3-5 paragraphs."
    )


def render_aggressive_argument(a: AggressiveArgument) -> str:
    return f"Aggressive Analyst: {a.argument_full or ''}"


# ===========================================================================
# 10. CONSERVATIVE RISK ANALYST
# ===========================================================================


class ConservativeArgument(BaseModel):
    """Structured output from the Conservative Risk Analyst (one round)."""

    stance: Optional[str] = Field(
        default=None, description="One of: Sell, Reduce, Wait, Hold with Caution."
    )
    thesis: Optional[str] = Field(
        default=None, description="Core conservative thesis in 2-3 sentences."
    )
    risk_factors: Optional[list[str]] = Field(
        default=None, description="3-5 specific risk factors with data."
    )
    aggressive_rebuttals: Optional[list[str]] = Field(
        default=None, description="2-4 rebuttals to aggressive arguments."
    )
    neutral_rebuttals: Optional[list[str]] = Field(
        default=None, description="2-4 rebuttals to neutral position."
    )
    recommended_position_size: Optional[str] = Field(
        default=None, description="Recommended position size, e.g. '2% max'."
    )
    recommended_entry: Optional[float] = Field(
        default=None, description="Recommended entry price (lower than current)."
    )
    max_acceptable_risk: Optional[str] = Field(
        default=None, description="Maximum acceptable drawdown, e.g. '10% from entry'."
    )
    conviction_level: Optional[str] = Field(
        default=None, description="One of: Very High, High, Moderate."
    )
    argument_full: Optional[str] = Field(
        default=None, description="Full conversational argument text, 3-5 paragraphs."
    )


def render_conservative_argument(a: ConservativeArgument) -> str:
    return f"Conservative Analyst: {a.argument_full or ''}"


# ===========================================================================
# 11. NEUTRAL RISK ANALYST
# ===========================================================================


class NeutralArgument(BaseModel):
    """Structured output from the Neutral Risk Analyst (one round)."""

    stance: Optional[str] = Field(
        default=None, description="One of: Lean Buy, Balanced, Lean Sell."
    )
    thesis: Optional[str] = Field(
        default=None, description="Core balanced thesis in 2-3 sentences."
    )
    agreed_with_aggressive: Optional[list[str]] = Field(
        default=None, description="2-3 points where aggressive analyst is right."
    )
    agreed_with_conservative: Optional[list[str]] = Field(
        default=None, description="2-3 points where conservative analyst is right."
    )
    proposed_compromise: Optional[str] = Field(
        default=None, description="Proposed middle-ground strategy in 2-3 sentences."
    )
    recommended_position_size: Optional[str] = Field(
        default=None,
        description="Recommended position size, e.g. '3% initial, scale to 5%'.",
    )
    recommended_entry: Optional[float] = Field(
        default=None, description="Recommended entry price."
    )
    scaling_strategy: Optional[str] = Field(
        default=None,
        description="How to scale in/out, e.g. 'Buy 50% at 347, 50% if RSI < 60'.",
    )
    conviction_level: Optional[str] = Field(
        default=None, description="One of: High, Moderate, Low."
    )
    argument_full: Optional[str] = Field(
        default=None, description="Full conversational argument text, 3-5 paragraphs."
    )


def render_neutral_argument(a: NeutralArgument) -> str:
    return f"Neutral Analyst: {a.argument_full or ''}"


# ===========================================================================
# 12. PORTFOLIO MANAGER (final decision)
# ===========================================================================


class PortfolioDecision(BaseModel):
    """Structured final decision from the Portfolio Manager."""

    rating: PortfolioRating = Field(
        description="Exactly one of Buy / Overweight / Hold / Underweight / Sell."
    )
    executive_summary: Optional[str] = Field(
        default=None,
        description=(
            "Concise action plan: entry, sizing, risk levels, horizon. 2-4 sentences."
        ),
    )
    investment_thesis: Optional[str] = Field(
        default=None, description="Detailed reasoning anchored in debate evidence."
    )
    price_target: Optional[float] = Field(default=None, description="Target price.")
    entry_price: Optional[float] = Field(
        default=None, description="Recommended entry price."
    )
    stop_loss: Optional[float] = Field(default=None, description="Stop-loss price.")
    position_size: Optional[float] = Field(
        default=None,
        description="Position size as decimal, e.g. 0.05 for 5% of portfolio.",
    )
    position_size_description: Optional[str] = Field(
        default=None,
        description=(
            "Position size rationale, e.g. 'Maintain current exposure; 0% "
            "additional allocation'. Max 200 chars."
        ),
    )
    time_horizon_months: Optional[float] = Field(
        default=None,
        description="Holding period in months, e.g. 9.0 for 6-12 months midpoint.",
    )
    time_horizon_description: Optional[str] = Field(
        default=None,
        description=(
            "Holding period rationale, e.g. '6-12 months pending earnings "
            "catalyst'. Max 200 chars."
        ),
    )
    risk_reward_ratio: Optional[float] = Field(
        default=None, description="Risk/reward ratio as a float, e.g. 3.0 means 1:3."
    )
    risk_reward_description: Optional[str] = Field(
        default=None,
        description=(
            "Risk/reward assessment summary, e.g. 'Favorable asymmetry with "
            "limited downside'. Max 200 chars."
        ),
    )
    key_monitor_triggers: Optional[list[str]] = Field(
        default=None, description="2-3 events that would change the thesis."
    )


def render_pm_decision(d: PortfolioDecision) -> str:
    parts = [f"**Rating**: {d.rating.value}"]
    if d.executive_summary is not None:
        parts.extend(["", f"**Executive Summary**: {d.executive_summary}"])
    if d.investment_thesis is not None:
        parts.extend(["", f"**Investment Thesis**: {d.investment_thesis}"])
    if d.price_target is not None:
        parts.extend(["", f"**Price Target**: {d.price_target}"])
    if d.entry_price is not None:
        parts.extend(["", f"**Entry Price**: {d.entry_price}"])
    if d.stop_loss is not None:
        parts.extend(["", f"**Stop Loss**: {d.stop_loss}"])
    if d.position_size is not None:
        parts.extend(
            [
                "",
                f"**Position Size**: {d.position_size:.0%}"
                f" — {d.position_size_description or ''}",
            ]
        )
    if d.time_horizon_months is not None:
        horizon = d.time_horizon_description or f"{d.time_horizon_months:g} months"
        parts.extend(["", f"**Time Horizon**: {horizon}"])
    if d.risk_reward_ratio is not None:
        parts.extend(
            [
                "",
                f"**Risk/Reward**: 1:{d.risk_reward_ratio:.1f}"
                f" — {d.risk_reward_description or ''}",
            ]
        )
    if d.key_monitor_triggers:
        triggers = ", ".join(d.key_monitor_triggers)
        parts.extend(["", f"**Monitor Triggers**: {triggers}"])
    return "\n".join(parts)
