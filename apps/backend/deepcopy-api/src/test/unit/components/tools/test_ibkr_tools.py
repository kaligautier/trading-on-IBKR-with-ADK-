"""Unit tests for the IBKR ADK tool wrappers."""

from unittest.mock import patch

import pytest

from app.components.tools.custom import ibkr_tools
from app.dto.response.ibkr_responses import ContractResponse
from app.utils.error import IbkrSessionError, ToolExecutionError


class TestIbkrTools:
    def should_return_plain_dicts_from_the_service(self, mock_tool_context):
        contract = ContractResponse(
            conid=1,
            symbol="AAPL",
            company_name=None,
            exchange="NASDAQ",
            security_types=["STK"],
        )
        with patch.object(ibkr_tools, "ibkr_portfolio_service") as service:
            service.search_contracts.return_value = [contract]

            result = ibkr_tools.search_contracts("AAPL", mock_tool_context)

        assert result == [contract.model_dump()]
        service.search_contracts.assert_called_once_with("AAPL")

    def should_wrap_service_errors(self, mock_tool_context):
        with patch.object(ibkr_tools, "ibkr_portfolio_service") as service:
            service.list_accounts.side_effect = IbkrSessionError("not signed in")

            with pytest.raises(ToolExecutionError, match="not signed in"):
                ibkr_tools.list_accounts(mock_tool_context)
