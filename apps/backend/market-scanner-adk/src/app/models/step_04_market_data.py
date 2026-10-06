"""Step 04: final business result; intermediate stages stay in workflow state."""

from pydantic import BaseModel, ConfigDict

from app.models.market_regime import MarketRegime


class MarketData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_regime: MarketRegime
