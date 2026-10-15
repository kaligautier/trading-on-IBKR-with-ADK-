"""Shared report vocabulary: observations, interpretations and attributable sources."""

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    GetJsonSchemaHandler,
    HttpUrl,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

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


class ReportArbitration(ReportModel):
    """Concise public justification, separate from internal research and critique."""

    decision_rationale: ReportText
    supporting_factors: list[ReportText]
    main_counterargument: ReportText
    invalidation_conditions: list[ReportText]

    @model_validator(mode="after")
    def validate_summary(self):
        if not 1 <= len(self.supporting_factors) <= 3:
            raise ValueError("Arbitration requires one to three supporting factors")
        if len(self.invalidation_conditions) > 3:
            raise ValueError("Arbitration allows at most three invalidation conditions")
        texts = [
            self.decision_rationale,
            self.main_counterargument,
            *self.supporting_factors,
            *self.invalidation_conditions,
        ]
        if any(not text or len(text) > 500 for text in texts):
            raise ValueError("Arbitration text must contain 1 to 500 characters")
        return self

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        schema = super().__get_pydantic_json_schema__(core_schema, handler)
        # Keep provider input schemas compatible; enforce the same bounds when
        # the reader validates persisted JSON using the serialization schema.
        if handler.mode == "serialization":
            properties = schema["properties"]
            text_bounds = {"minLength": 1, "maxLength": 500, "pattern": r"\S"}
            for name in ("decision_rationale", "main_counterargument"):
                properties[name].update(text_bounds)
            for name, minimum in (
                ("supporting_factors", 1),
                ("invalidation_conditions", 0),
            ):
                properties[name].update(minItems=minimum, maxItems=3)
                properties[name]["items"].update(text_bounds)
        return schema


class ReportSummary(ReportModel):
    title: ReportText
    summary: ReportText
    macro_overview: MacroOverview | None = None
    arbitration: ReportArbitration | None = None
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
