import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app


def test_liveness_endpoint() -> None:
    async def request_liveness() -> tuple[int, dict[str, str]]:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get("/health/live")
        return response.status_code, response.json()

    status_code, response_body = asyncio.run(request_liveness())

    assert status_code == 200
    assert response_body == {"status": "ok"}
