"""Step 01: collected external observations and their provenance."""

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, FiniteFloat


class ExternalMarketObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_on: date
    # Treasury amounts remain decimal strings, exactly as supplied by its API.
    value: FiniteFloat | str


class ExternalMarketAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    symbol: str
    kind: Literal["market", "macro"]
    unit: str | None
    source: str
    source_url: str
    value_field: str | None
    retrieved_at: AwareDatetime
    status: Literal["success", "error"]
    observations: list[ExternalMarketObservation] = Field(default_factory=list)
    error: str | None = None


class ExternalMarketData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assets: dict[str, ExternalMarketAsset]
