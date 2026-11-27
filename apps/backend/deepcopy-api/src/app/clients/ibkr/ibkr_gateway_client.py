"""Contract of a read-only IBKR Client Portal gateway client."""

from abc import ABC, abstractmethod

from app.dto.ibkr.ibkr_dtos import (
    IbkrAccountDto,
    IbkrAuthStatusDto,
    IbkrContractDto,
    IbkrPositionDto,
    IbkrSummaryValueDto,
)


class IbkrGatewayClient(ABC):
    """Read-only gateway operations. Implementations never place orders."""

    @abstractmethod
    def get_auth_status(self) -> IbkrAuthStatusDto: ...

    @abstractmethod
    def init_brokerage_session(self) -> IbkrAuthStatusDto: ...

    @abstractmethod
    def list_accounts(self) -> list[IbkrAccountDto]: ...

    @abstractmethod
    def get_account_summary(
        self, account_id: str
    ) -> dict[str, IbkrSummaryValueDto]: ...

    @abstractmethod
    def get_positions(self, account_id: str, page: int) -> list[IbkrPositionDto]: ...

    @abstractmethod
    def search_contracts(self, symbol: str) -> list[IbkrContractDto]: ...
