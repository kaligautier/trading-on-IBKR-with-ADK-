"""Unit tests for the httpx IBKR gateway client."""

import httpx
import pytest

from app.clients.ibkr.httpx_ibkr_gateway_client import HttpxIbkrGatewayClient
from app.utils.error import IbkrGatewayError, IbkrSessionError


def build_client(handler) -> tuple[HttpxIbkrGatewayClient, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    transport = httpx.MockTransport(record)
    http = httpx.Client(base_url="https://gateway.test/v1/api", transport=transport)
    return HttpxIbkrGatewayClient(http), requests


class TestHttpxIbkrGatewayClient:
    def should_parse_positions(self):
        client, requests = build_client(
            lambda request: httpx.Response(
                200,
                json=[{"conid": 265598, "ticker": "AAPL", "position": 3, "x": 1}],
            )
        )

        positions = client.get_positions("U1234567", 0)

        assert positions[0].conid == 265598
        assert positions[0].ticker == "AAPL"
        assert positions[0].position == 3
        assert requests[0].url.path == "/v1/api/portfolio/U1234567/positions/0"

    def should_send_a_json_body_on_status_post(self):
        client, requests = build_client(
            lambda request: httpx.Response(200, json={"authenticated": True})
        )

        assert client.get_auth_status().authenticated is True
        assert requests[0].method == "POST"
        assert requests[0].content == b"{}"

    def should_open_the_session_without_competing(self):
        client, requests = build_client(
            lambda request: httpx.Response(200, json={"authenticated": True})
        )

        client.init_brokerage_session()

        assert requests[0].url.path == "/v1/api/iserver/auth/ssodh/init"
        assert requests[0].content == b'{"publish":true,"compete":false}'

    def should_parse_contracts_with_string_conids(self):
        client, _ = build_client(
            lambda request: httpx.Response(
                200,
                json=[
                    {
                        "conid": "265598",
                        "symbol": "AAPL",
                        "companyName": "APPLE INC",
                        "description": "NASDAQ",
                        "sections": [{"secType": "STK"}, {"secType": "OPT"}],
                    }
                ],
            )
        )

        contract = client.search_contracts("AAPL")[0]

        assert contract.conid == 265598
        assert [section.sec_type for section in contract.sections] == ["STK", "OPT"]

    def should_accept_a_contract_without_symbol(self):
        client, _ = build_client(
            lambda request: httpx.Response(
                200, json=[{"conid": 1, "symbol": None, "sections": []}]
            )
        )

        assert client.search_contracts("AAPL")[0].symbol is None

    def should_report_an_unauthenticated_session(self):
        client, _ = build_client(lambda request: httpx.Response(401))

        with pytest.raises(IbkrSessionError) as error:
            client.list_accounts()
        assert error.value.status_code == 503

    def should_report_a_closed_brokerage_session(self):
        client, _ = build_client(
            lambda request: httpx.Response(
                400, json={"error": "Bad Request: no bridge", "statusCode": 400}
            )
        )

        with pytest.raises(IbkrSessionError, match="session/init"):
            client.search_contracts("AAPL")

    def should_report_other_gateway_errors(self):
        client, _ = build_client(lambda request: httpx.Response(500, text="boom"))

        with pytest.raises(IbkrGatewayError) as error:
            client.list_accounts()
        assert error.value.details["gateway_status"] == 500
        assert error.value.status_code == 502

    def should_report_an_unexpected_payload(self):
        client, _ = build_client(lambda request: httpx.Response(200, json={"a": 1}))

        with pytest.raises(IbkrGatewayError, match="Unexpected"):
            client.list_accounts()

    def should_report_an_unreachable_gateway(self):
        def fail(request):
            raise httpx.ConnectError("refused", request=request)

        client, _ = build_client(fail)

        with pytest.raises(IbkrGatewayError):
            client.list_accounts()
