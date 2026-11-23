"""Unit tests for the IBKR ADK tool wrappers."""

from unittest.mock import patch

import pytest

from app.components.tools.custom import ibkr_tools
from app.utils.error import IbkrSessionError, ToolExecutionError


class TestIbkrTools:
    def should_delegate_positions_to_the_service(self, mock_tool_context):
        with patch.object(ibkr_tools, "ibkr_gateway") as gateway:
            gateway.get_positions.return_value = [{"conid": 1}]

            result = ibkr_tools.get_positions("U1234567", mock_tool_context)

        assert result == [{"conid": 1}]
        gateway.get_positions.assert_called_once_with("U1234567")

    def should_wrap_service_errors(self, mock_tool_context):
        with patch.object(ibkr_tools, "ibkr_gateway") as gateway:
            gateway.list_accounts.side_effect = IbkrSessionError("not signed in")

            with pytest.raises(ToolExecutionError, match="not signed in"):
                ibkr_tools.list_accounts(mock_tool_context)
