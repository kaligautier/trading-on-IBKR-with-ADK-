"""Path and query parameters for the Deepcopy API account reads."""

from pydantic import BaseModel, ConfigDict

from app.models.identifiers import AccountId, Page


class GetAccountRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    account_id: AccountId


class GetPositionsRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    account_id: AccountId
    page: Page = 0
