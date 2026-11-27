"""IBKR Client Portal gateway response DTOs.

Field names follow the gateway JSON; unknown fields are ignored.
"""

from pydantic import BaseModel, ConfigDict, Field


class IbkrDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class IbkrAuthStatusDto(IbkrDto):
    authenticated: bool = False
    established: bool = False
    competing: bool = False
    connected: bool = False
    message: str = ""


class IbkrAccountDto(IbkrDto):
    account_id: str = Field(alias="accountId")
    account_title: str | None = Field(default=None, alias="accountTitle")
    display_name: str | None = Field(default=None, alias="displayName")
    currency: str | None = None
    account_type: str | None = Field(default=None, alias="type")


class IbkrSummaryValueDto(IbkrDto):
    amount: float | None = None
    currency: str | None = None
    value: str | None = None
    is_null: bool = Field(default=False, alias="isNull")


class IbkrPositionDto(IbkrDto):
    conid: int
    contract_desc: str | None = Field(default=None, alias="contractDesc")
    ticker: str | None = None
    asset_class: str | None = Field(default=None, alias="assetClass")
    position: float = 0.0
    market_price: float | None = Field(default=None, alias="mktPrice")
    market_value: float | None = Field(default=None, alias="mktValue")
    average_cost: float | None = Field(default=None, alias="avgCost")
    unrealized_pnl: float | None = Field(default=None, alias="unrealizedPnl")
    currency: str | None = None


class IbkrContractSectionDto(IbkrDto):
    sec_type: str = Field(alias="secType")


class IbkrContractDto(IbkrDto):
    conid: int
    symbol: str | None = None
    company_name: str | None = Field(default=None, alias="companyName")
    description: str | None = None
    sections: list[IbkrContractSectionDto] = Field(default_factory=list)
