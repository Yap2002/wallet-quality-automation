import asyncio
from concurrent.futures import ThreadPoolExecutor

from httpx import ASGITransport, AsyncClient

from app.main import app


def test_liveness_endpoint() -> None:
    async def request_liveness() -> tuple[int, dict[str, str]]:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/health/live")
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=1) as executor:
        status_code, response_body = executor.submit(asyncio.run, request_liveness()).result()

    assert status_code == 200
    assert response_body == {"status": "ok"}


def test_openapi_declares_http_bearer_security_scheme() -> None:
    schema = app.openapi()

    security_scheme = schema["components"]["securitySchemes"]["HTTPBearer"]
    assert security_scheme["type"] == "http"
    assert security_scheme["scheme"] == "bearer"
    assert schema["paths"]["/api/v1/wallets/{wallet_id}"]["get"]["security"] == [{"HTTPBearer": []}]
