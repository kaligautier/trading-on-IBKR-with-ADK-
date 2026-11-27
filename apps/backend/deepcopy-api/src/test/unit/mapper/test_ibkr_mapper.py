"""Unit tests for the IBKR mapper."""

from app.dto.ibkr.ibkr_dtos import (
    IbkrAccountDto,
    IbkrContractDto,
    IbkrPositionDto,
    IbkrSummaryValueDto,
)
from app.mapper import ibkr_mapper


class TestIbkrMapper:
    def should_map_an_account(self):
        dto = IbkrAccountDto.model_validate(
            {"accountId": "U1", "accountTitle": "T", "displayName": "D", "type": "X"}
        )

        response = ibkr_mapper.to_account(dto)

        assert response.account_id == "U1"
        assert response.title == "T"
        assert response.account_type == "X"

    def should_map_summary_amounts_and_skip_null_values(self):
        values = {
            "netliquidation": IbkrSummaryValueDto(amount=1000.0, currency="EUR"),
            "totalcashvalue": IbkrSummaryValueDto(amount=250.0, currency="EUR"),
            "buyingpower": IbkrSummaryValueDto(amount=9.0, is_null=True),
        }

        response = ibkr_mapper.to_account_summary("U1", values)

        assert response.currency == "EUR"
        assert response.net_liquidation == 1000.0
        assert response.total_cash == 250.0
        assert response.buying_power is None
        assert response.gross_position_value is None

    def should_prefer_the_ticker_as_position_symbol(self):
        with_ticker = IbkrPositionDto(conid=1, ticker="AAPL", contract_desc="APPLE")
        without_ticker = IbkrPositionDto(conid=2, contract_desc="APPLE")

        assert ibkr_mapper.to_position(with_ticker).symbol == "AAPL"
        assert ibkr_mapper.to_position(without_ticker).symbol == "APPLE"

    def should_map_a_contract(self):
        dto = IbkrContractDto.model_validate(
            {
                "conid": 265598,
                "symbol": "AAPL",
                "description": "NASDAQ",
                "sections": [{"secType": "STK"}],
            }
        )

        response = ibkr_mapper.to_contract(dto)

        assert response.exchange == "NASDAQ"
        assert response.security_types == ["STK"]
