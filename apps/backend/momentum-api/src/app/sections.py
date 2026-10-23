"""Explicit financial projection from DeepCopy 38d0736; no ORM serialization."""

from pydantic import BaseModel, ConfigDict, Field


class FinancialModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, allow_inf_nan=False, populate_by_name=True
    )


class TechnicalIndicators(FinancialModel):
    close_price: float | None = None
    close_signal: str | None = None
    close_comment: str | None = None
    sma_50: float | None = None
    sma_50_signal: str | None = None
    sma_50_comment: str | None = None
    sma_200: float | None = None
    sma_200_signal: str | None = None
    sma_200_comment: str | None = None
    ema_10: float | None = None
    ema_10_signal: str | None = None
    ema_10_comment: str | None = None
    rsi: float | None = None
    rsi_signal: str | None = None
    rsi_comment: str | None = None
    macd: float | None = None
    macd_signal: str | None = Field(default=None, validation_alias="macd_signal_state")
    macd_comment: str | None = None
    macd_signal_val: float | None = None
    macd_histogram: float | None = None
    boll_upper: float | None = None
    boll_upper_signal: str | None = None
    boll_upper_comment: str | None = None
    boll_lower: float | None = None
    boll_lower_signal: str | None = None
    boll_lower_comment: str | None = None
    atr: float | None = None
    atr_signal: str | None = None
    atr_comment: str | None = None
    vwma: float | None = None
    vwma_signal: str | None = None
    vwma_comment: str | None = None
    mfi: float | None = None
    mfi_signal: str | None = None
    mfi_comment: str | None = None
    trend_direction: str | None = None
    momentum_state: str | None = None
    volatility_regime: str | None = None
    key_support: float | None = None
    key_resistance: float | None = None
    actionable_recommendation: str | None = None
    summary_short: str | None = None


class Fundamentals(FinancialModel):
    market_cap: float | None = None
    pe_ratio: float | None = None
    forward_pe: float | None = None
    peg_ratio: float | None = None
    eps_ttm: float | None = None
    forward_eps: float | None = None
    revenue: float | None = None
    net_income: float | None = None
    profit_margin: float | None = None
    operating_margin: float | None = None
    roe: float | None = None
    roa: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    free_cash_flow: float | None = None
    total_cash: float | None = None
    capex: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    financial_health: str | None = None
    growth_outlook: str | None = None
    valuation_assessment: str | None = None
    summary_short: str | None = None


class SentimentItem(FinancialModel):
    topic: str
    score: float | None = Field(default=None, validation_alias="sentiment_score")
    impact: str
    comment: str


class Sentiment(FinancialModel):
    overall_sentiment: float | None = None
    overall_signal: str | None = None
    retail_sentiment: str | None = None
    institutional_sentiment: str | None = None
    key_risk: str | None = None
    key_catalyst: str | None = None
    summary_short: str | None = None
    items: list[SentimentItem] = Field(default_factory=list)


class NewsItem(FinancialModel):
    category: str
    headline: str
    impact: str
    comment: str


class News(FinancialModel):
    overall_impact: str | None = None
    macro_environment: str | None = None
    sector_momentum: str | None = None
    key_catalyst: str | None = None
    key_risk: str | None = None
    summary_short: str | None = None
    items: list[NewsItem] = Field(default_factory=list)


class ResearchPlan(FinancialModel):
    recommendation: str
    rationale: str
    strategic_actions: str


class TraderProposal(FinancialModel):
    action: str
    reasoning: str
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    position_sizing: str | None = None
    risk_reward_ratio: str | None = None


class PortfolioDecision(FinancialModel):
    rating: str
    executive_summary: str
    investment_thesis: str
    price_target: float | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    position_size: float | None = None
    position_size_description: str | None = None
    time_horizon_months: float | None = None
    time_horizon_description: str | None = None
    risk_reward_ratio: float | None = None
    risk_reward_description: str | None = None


class DebateArgument(FinancialModel):
    debate_type: str
    role: str
    round: int = Field(validation_alias="round_number")
    thesis: str | None = None
    conviction: str | None = Field(default=None, validation_alias="conviction_level")
    stance: str | None = None
    target_price: float | None = None
    key_data_point: str | None = None


class RunStats(FinancialModel):
    agents_total: int
    agents_completed: int
    llm_calls: int
    tool_calls: int
    tokens_in: int
    tokens_out: int
    reports_total: int
    reports_completed: int
    duration_seconds: float
