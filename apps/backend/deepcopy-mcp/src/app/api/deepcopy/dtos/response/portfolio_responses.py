"""Wire responses from the Deepcopy API /ibkr routes."""

from pydantic import BaseModel, ConfigDict, Field, RootModel

from app.models.identifiers import AccountId


class SessionStatusResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    authenticated: bool
    established: bool
    competing: bool
    connected: bool
    message: str = Field(max_length=500)


class AccountResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    account_id: AccountId
    title: str | None = Field(max_length=200)
    display_name: str | None = Field(max_length=200)
    currency: str | None = Field(max_length=10)
    account_type: str | None = Field(max_length=50)


class AccountSummaryResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    account_id: AccountId
    currency: str | None = Field(max_length=10)
    net_liquidation: float | None
    total_cash: float | None
    buying_power: float | None
    available_funds: float | None
    gross_position_value: float | None


class PositionResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    conid: int
    symbol: str | None = Field(max_length=100)
    asset_class: str | None = Field(max_length=20)
    quantity: float
    market_price: float | None
    market_value: float | None
    average_cost: float | None
    unrealized_pnl: float | None
    currency: str | None = Field(max_length=10)


class ContractResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    conid: int
    symbol: str | None = Field(max_length=50)
    company_name: str | None = Field(max_length=200)
    exchange: str | None = Field(max_length=50)
    security_types: list[str] = Field(max_length=50)


class AccountsResponse(RootModel[list[AccountResponse]]):
    pass


class PositionsResponse(RootModel[list[PositionResponse]]):
    pass


class ContractsResponse(RootModel[list[ContractResponse]]):
    pass
