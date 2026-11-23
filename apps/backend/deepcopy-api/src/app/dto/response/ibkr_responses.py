"""Deepcopy API responses for the read-only IBKR routes."""

from pydantic import BaseModel


class SessionStatusResponse(BaseModel):
    authenticated: bool
    established: bool
    competing: bool
    connected: bool
    message: str


class AccountResponse(BaseModel):
    account_id: str
    title: str | None
    display_name: str | None
    currency: str | None
    account_type: str | None


class AccountSummaryResponse(BaseModel):
    account_id: str
    currency: str | None
    net_liquidation: float | None
    total_cash: float | None
    buying_power: float | None
    available_funds: float | None
    gross_position_value: float | None


class PositionResponse(BaseModel):
    conid: int
    symbol: str | None
    asset_class: str | None
    quantity: float
    market_price: float | None
    market_value: float | None
    average_cost: float | None
    unrealized_pnl: float | None
    currency: str | None


class ContractResponse(BaseModel):
    conid: int
    symbol: str | None
    company_name: str | None
    exchange: str | None
    security_types: list[str]
