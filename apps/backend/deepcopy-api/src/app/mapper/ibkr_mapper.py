"""Map IBKR gateway DTOs to Deepcopy API responses."""

from app.dto.ibkr.ibkr_dtos import (
    IbkrAccountDto,
    IbkrAuthStatusDto,
    IbkrContractDto,
    IbkrPositionDto,
    IbkrSummaryValueDto,
)
from app.dto.response.ibkr_responses import (
    AccountResponse,
    AccountSummaryResponse,
    ContractResponse,
    PositionResponse,
    SessionStatusResponse,
)


def to_session_status(dto: IbkrAuthStatusDto) -> SessionStatusResponse:
    return SessionStatusResponse(
        authenticated=dto.authenticated,
        established=dto.established,
        competing=dto.competing,
        connected=dto.connected,
        message=dto.message,
    )


def to_account(dto: IbkrAccountDto) -> AccountResponse:
    return AccountResponse(
        account_id=dto.account_id,
        title=dto.account_title,
        display_name=dto.display_name,
        currency=dto.currency,
        account_type=dto.account_type,
    )


def to_account_summary(
    account_id: str, values: dict[str, IbkrSummaryValueDto]
) -> AccountSummaryResponse:
    def amount(key: str) -> float | None:
        value = values.get(key)
        return None if value is None or value.is_null else value.amount

    net_liquidation = values.get("netliquidation")
    return AccountSummaryResponse(
        account_id=account_id,
        currency=net_liquidation.currency if net_liquidation else None,
        net_liquidation=amount("netliquidation"),
        total_cash=amount("totalcashvalue"),
        buying_power=amount("buyingpower"),
        available_funds=amount("availablefunds"),
        gross_position_value=amount("grosspositionvalue"),
    )


def to_position(dto: IbkrPositionDto) -> PositionResponse:
    return PositionResponse(
        conid=dto.conid,
        symbol=dto.ticker or dto.contract_desc,
        asset_class=dto.asset_class,
        quantity=dto.position,
        market_price=dto.market_price,
        market_value=dto.market_value,
        average_cost=dto.average_cost,
        unrealized_pnl=dto.unrealized_pnl,
        currency=dto.currency,
    )


def to_contract(dto: IbkrContractDto) -> ContractResponse:
    return ContractResponse(
        conid=dto.conid,
        symbol=dto.symbol,
        company_name=dto.company_name,
        exchange=dto.description,
        security_types=[section.sec_type for section in dto.sections],
    )
