import pytest

from tests.framework.clients.wallet_api_client import WalletApiClient

pytestmark = pytest.mark.smoke


def test_liveness_over_real_http(
    wallet_api_client: WalletApiClient,
) -> None:
    trace_id = "smoke-health-real-http"

    response = wallet_api_client.get_liveness(trace_id=trace_id)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Trace-ID"] == trace_id
    assert response.url.startswith("http://127.0.0.1:")
