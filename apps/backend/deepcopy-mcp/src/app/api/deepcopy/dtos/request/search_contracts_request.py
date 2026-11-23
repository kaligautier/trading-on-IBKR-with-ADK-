"""Query parameters for the Deepcopy API contract search."""

from pydantic import BaseModel, ConfigDict

from app.models.identifiers import Symbol


class SearchContractsRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    symbol: Symbol
