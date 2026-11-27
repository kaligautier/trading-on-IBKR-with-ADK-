"""Read-only IBKR portfolio data returned by the services and MCP tools."""

from pydantic import BaseModel, ConfigDict

from app.models.identifiers import AccountId


class SessionStatus(BaseModel):
    model_config = ConfigDict(strict=True)

    authenticated: bool
    established: bool
    competing: bool
    connected: bool
    message: str


class Account(BaseModel):
    model_config = ConfigDict(strict=True)

    account_id: AccountId
    title: str | None
    display_name: str | None
    currency: str | None
    account_type: str | None


class AccountSummary(BaseModel):
    model_config = ConfigDict(strict=True)

    account_id: AccountId
    currency: str | None
    net_liquidation: float | None
    total_cash: float | None
    buying_power: float | None
    available_funds: float | None
    gross_position_value: float | None


class Position(BaseModel):
    model_config = ConfigDict(strict=True)

    conid: int
    symbol: str | None
    asset_class: str | None
    quantity: float
    market_price: float | None
    market_value: float | None
    average_cost: float | None
    unrealized_pnl: float | None
    currency: str | None


class Contract(BaseModel):
    model_config = ConfigDict(strict=True)

    conid: int
    symbol: str | None
    company_name: str | None
    exchange: str | None
    security_types: list[str]
