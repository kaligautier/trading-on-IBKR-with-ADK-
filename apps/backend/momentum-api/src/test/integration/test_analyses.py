"""Latest selection precedes filtering/cursors; detail uses every typed section."""

from datetime import UTC, datetime
from uuid import UUID

import httpx

from app.application import create_app
from app.config import Settings
from app.query import Query

from .conftest import BASE, seed


def latest(token="", size=17, view="latest", rating=None):
    return Query.from_parameters(view, None, rating, size, token)


async def rate(admin, result_id, rating="Buy"):
    await admin.execute(
        """INSERT INTO _analysis.portfolio_decisions
        (id,result_id,ticker,analysis_date,rating,executive_summary,investment_thesis)
        SELECT $1,id,ticker,analysis_date,$2,'synthetic summary','synthetic thesis'
        FROM _analysis.analysis_results WHERE id=$1""",
        result_id,
        rating,
    )


async def test_latest_ties_filter_after_winner_and_all_pages(admin, service):
    reader, _ = service
    await seed(admin, 125)
    for index in range(125):
        await rate(admin, UUID(int=index + 1))
    # A second result for T000, same timestamp: UUID determines the winner.
    await admin.execute(
        """INSERT INTO _analysis.analysis_results
        SELECT session_id,invocation_id,user_id,$1,ticker,analysis_date,llm_provider,
               deep_think_llm,quick_think_llm,next_analysis_date,next_analysis_desc,created_at
        FROM _analysis.analysis_results WHERE id=$2""",
        UUID(int=1000),
        UUID(int=1),
    )
    await rate(admin, UUID(int=1000), "Sell")
    results = []
    token = ""
    while True:
        page = await reader.list(latest(token))
        results.extend(page.items)
        token = page.next_page_token
        if not token:
            break
    assert len(results) == len({item.ticker for item in results}) == 125
    assert results[0].id == UUID(int=1000)
    recommended = []
    token = ""
    while True:
        page = await reader.list(latest(token, view="recommendations"))
        recommended.extend(page.items)
        token = page.next_page_token
        if not token:
            break
    assert len(recommended) == 124
    assert "T000" not in {item.ticker for item in recommended}
    assert (await reader.list(latest(rating="Sell"))).items[0].id == UUID(int=1000)
    assert (
        await reader.list(Query.from_parameters("history", "T000", None, 20, ""))
    ).items[1].id == UUID(int=1)


async def test_new_winner_moves_ahead_of_cursor_as_documented(admin, service):
    reader, _ = service
    await seed(admin, 3)
    first = await reader.list(latest(size=1))
    await admin.execute(
        "UPDATE _analysis.analysis_results SET created_at=$1 WHERE id=$2",
        datetime(2026, 10, 23, tzinfo=UTC),
        UUID(int=1),
    )
    remaining = await reader.list(latest(first.next_page_token))
    assert [item.id for item in remaining.items] == [UUID(int=2)]
    assert (await reader.list(latest())).items[0].id == UUID(int=1)


async def test_actual_http_operations_and_private_fields(admin, service):
    reader, _ = service
    await seed(admin)
    settings = Settings(
        DATABASE_URL=BASE.format("momentum_results_reader"),
        API_TOKEN="disposable-reader-token",
    )
    app = create_app(settings)
    app.state.service = reader
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer disposable-reader-token"},
    ) as client:
        for path in [
            "/v1/analyses",
            "/v1/analyses/latest",
            "/v1/recommendations",
            "/v1/analyses/" + str(UUID(int=1)),
            "/ready",
        ]:
            response = await client.get(path)
            assert response.status_code == 200, response.text
            assert (
                "private-session" not in response.text
                and "user_id" not in response.text
            )
            assert (await client.head(path)).content == b""
            assert (await client.options(path)).status_code == 204
        detail = (await client.get("/v1/analyses/" + str(UUID(int=1)))).json()
        assert detail["fundamentals"] is None and detail["debate_arguments"] == []
        assert (
            await client.get("/v1/analyses/" + str(UUID(int=999)))
        ).status_code == 404
        assert (await client.get("/v1/analyses/not-a-uuid")).status_code == 400
        assert (await client.get("/v1/analyses?page_size=101")).status_code == 400
        assert (
            await client.get("/v1/analyses?ticker=T000&ticker=OTHER")
        ).status_code == 400
        assert (await client.get("/v1/analyses?rating=Buy")).status_code == 400
        assert (await client.get("/v1/analyses/latest?rating=???")).status_code == 400
