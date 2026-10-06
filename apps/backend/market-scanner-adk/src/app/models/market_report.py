"""Shared report vocabulary: observations, interpretations and attributable sources."""

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)

Regime = Literal["risk-on", "cautious", "risk-off"]
Horizon = Literal["1d", "1w", "1m", "3m", "6m", "ytd", "1y", "5y", "level"]
Family = Literal[
    "equities", "volatility", "rates_currencies", "commodities", "crypto", "macro"
]
ASSET_FAMILIES: dict[str, tuple[str, ...]] = {
    "equities": (
        "sp500",
        "nasdaq100",
        "dow",
        "russell2000",
        "msci_world",
        "cac40",
        "stoxx600",
        "ftse100",
        "nikkei225",
        "hang_seng",
    ),
    "volatility": ("vix", "vxn", "vxd", "vixeq", "dspx"),
    "rates_currencies": ("us10y", "dxy", "eurusd", "usdjpy"),
    "commodities": ("gold", "silver", "oil", "natgas"),
    "crypto": ("bitcoin",),
    "macro": ("us_public_debt",),
}


def without_inline_references(value: str) -> str:
    if re.search(r"https?://|\[\d+\.\d+(?:[^\]]*)\]", value):
        raise ValueError("Use source_ids, not URLs or unresolved citation markers")
    return value


ReportText = Annotated[str, AfterValidator(without_inline_references)]


class ReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Interpretation(ReportModel):
    text: ReportText
    status: Literal["documented", "hypothesis", "unestablished"] = Field(
        description="Documented requires a source; "
        "hypothesis indicates an inferred connection."
    )
    source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_documented_sources(self):
        if self.status == "documented" and not self.source_ids:
            raise ValueError("A documented interpretation requires source_ids")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("Duplicate source_ids")
        return self


class AssetInsight(ReportModel):
    asset_key: str
    horizon: Horizon
    observation: ReportText = Field(description="Observation from the snapshot.")
    interpretation: Interpretation


class ThemeInsight(ReportModel):
    family: Family
    observation: ReportText
    interpretation: Interpretation


class ThemeAnalysis(ThemeInsight):
    asset_keys: list[str]


class MacroTheme(ReportModel):
    """Observation, reported context and conditional mechanism remain distinct."""

    title: ReportText
    asset_keys: list[str]
    observation: ReportText
    development: ReportText
    transmission: ReportText
    counter_evidence: ReportText
    uncertainty: ReportText
    status: Literal["hypothesis", "unestablished"]


class MacroOverview(ReportModel):
    context: ReportText
    themes: list[MacroTheme]
    data_gaps: list[ReportText]

    @model_validator(mode="after")
    def validate_theme_scope(self):
        if len(self.themes) > 3 or any(not theme.asset_keys for theme in self.themes):
            raise ValueError(
                "Macro overview requires at most three themes with affected assets"
            )
        return self


class ReportSummary(ReportModel):
    title: ReportText
    summary: ReportText
    macro_overview: MacroOverview | None = None
    regime: Regime = Field(
        description="Diagnosis of the observed universe, without allocation advice."
    )
    horizon: Horizon
    limitations: list[ReportText]
    watch_points: list[ReportText] = Field(default_factory=list)


class ResearchSource(ReportModel):
    id: str
    title: str
    url: HttpUrl
    supported_claims: list[str] = Field(
        default_factory=list,
        description="Response segments linked to this source by the provider; "
        "neither page quotations nor independent verification.",
    )


class ReportScope(ReportModel):
    requested: int
    available: int
    observation_dates: list[date]
    unavailable: list[str]
    stale: list[str]
