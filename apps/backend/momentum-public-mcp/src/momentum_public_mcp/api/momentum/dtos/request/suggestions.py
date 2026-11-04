"""JSON body sent to POST /suggestions."""

from pydantic import BaseModel, ConfigDict


class SuggestionRequest(BaseModel):
    """Only caller-supplied public fields belong in the request body."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    reason: str = ""
