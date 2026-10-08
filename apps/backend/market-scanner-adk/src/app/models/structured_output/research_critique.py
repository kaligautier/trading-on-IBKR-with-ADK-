"""Internal, tool-free review consumed by the market synthesizer."""

from typing import Annotated, Literal

from pydantic import Field

from app.models.market_report import ReportModel, ReportText

CritiqueText = Annotated[ReportText, Field(min_length=1, max_length=700)]


class ResearchChallenge(ReportModel):
    claim: CritiqueText
    concern: Literal[
        "unsupported_fact",
        "timing_mismatch",
        "causal_overreach",
        "contradictory_evidence",
    ]
    reasoning: CritiqueText
    suggested_revision: CritiqueText


class ResearchCritique(ReportModel):
    supported_findings: list[CritiqueText] = Field(max_length=3)
    challenges: list[ResearchChallenge] = Field(max_length=6)
    invalidation_conditions: list[CritiqueText] = Field(max_length=3)
    data_gaps: list[CritiqueText] = Field(max_length=5)
