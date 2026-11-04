"""Query DTO sent to the Momentum paginated reader endpoints."""

from pydantic import BaseModel, ConfigDict


class AnalysisPageRequest(BaseModel):
    """Wire parameters; omitted filters stay absent from the HTTP query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ticker: str | None = None
    rating: str | None = None
    page_size: int = 100
    page_token: str = ""
