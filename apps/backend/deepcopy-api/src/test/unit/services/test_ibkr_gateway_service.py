"""Unit tests for the read-only IBKR gateway service."""

import httpx
import pytest

from app.services.ibkr_gateway_service import IbkrGatewayService
from app.utils.error import IbkrGatewayError, IbkrSessionError, InvalidInputError


def build_service(handler) -> tuple[IbkrGatewayService, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    client = httpx.Client(
        base_url="https://gateway.test/v1/api", transport=httpx.MockTransport(record)
    )
    return IbkrGatewayService(client), requests


class TestIbkrGatewayService:
    def should_read_positions_of_an_account(self):
        service, requests = build_service(
            lambda request: httpx.Response(200, json=[{"conid": 265598}])
        )

        assert service.get_positions("U1234567") == [{"conid": 265598}]
        assert requests[0].method == "GET"
        assert requests[0].url.path == "/v1/api/portfolio/U1234567/positions/0"

    def should_send_a_json_body_on_status_post(self):
        service, requests = build_service(
            lambda request: httpx.Response(200, json={"authenticated": True})
        )

        assert service.session_status() == {"authenticated": True}
        assert requests[0].method == "POST"
        assert requests[0].content == b"{}"

    def should_open_the_session_without_competing(self):
        service, requests = build_service(
            lambda request: httpx.Response(200, json={"authenticated": True})
        )

        service.init_session()

        assert requests[0].url.path == "/v1/api/iserver/auth/ssodh/init"
        assert requests[0].content == b'{"publish":true,"compete":false}'

    def should_normalize_the_searched_symbol(self):
        service, requests = build_service(lambda request: httpx.Response(200, json=[]))

        service.search_contracts(" aapl ")

        assert requests[0].content == b'{"symbol":"AAPL"}'

    @pytest.mark.parametrize("account_id", ["", "u123", "U1/../x", "U" * 21])
    def should_reject_an_invalid_account_id(self, account_id):
        service, requests = build_service(lambda request: httpx.Response(200))

        with pytest.raises(InvalidInputError):
            service.get_summary(account_id)
        assert requests == []

    def should_reject_a_negative_page(self):
        service, _ = build_service(lambda request: httpx.Response(200))

        with pytest.raises(InvalidInputError):
            service.get_positions("U1234567", page=-1)

    @pytest.mark.parametrize("symbol", ["", "AA PL", "A" * 13, "AAPL;DROP"])
    def should_reject_an_invalid_symbol(self, symbol):
        service, _ = build_service(lambda request: httpx.Response(200))

        with pytest.raises(InvalidInputError):
            service.search_contracts(symbol)

    def should_report_an_unauthenticated_session(self):
        service, _ = build_service(lambda request: httpx.Response(401))

        with pytest.raises(IbkrSessionError) as error:
            service.list_accounts()
        assert error.value.status_code == 503

    def should_report_a_closed_brokerage_session(self):
        service, _ = build_service(
            lambda request: httpx.Response(
                400, json={"error": "Bad Request: no bridge", "statusCode": 400}
            )
        )

        with pytest.raises(IbkrSessionError, match="session/init"):
            service.search_contracts("AAPL")

    def should_report_other_gateway_errors(self):
        service, _ = build_service(lambda request: httpx.Response(500, text="boom"))

        with pytest.raises(IbkrGatewayError) as error:
            service.list_accounts()
        assert error.value.details["gateway_status"] == 500
        assert error.value.status_code == 502

    def should_report_an_unreachable_gateway(self):
        def fail(request):
            raise httpx.ConnectError("refused", request=request)

        service, _ = build_service(fail)

        with pytest.raises(IbkrGatewayError):
            service.list_accounts()
