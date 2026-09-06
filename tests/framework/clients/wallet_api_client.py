import json as json_module
import logging
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

import allure
import requests

logger = logging.getLogger(__name__)


class WalletApiClient:
    """A small reusable HTTP client for the wallet service."""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._session = requests.Session()
        self._session.trust_env = False

    def request(
        self,
        method: str,
        path: str,
        *,
        api_key: str | None = None,
        trace_id: str | None = None,
        extra_headers: dict[str, str] | None = None,
        json: Any = None,
    ) -> requests.Response:
        request_trace_id = trace_id or uuid4().hex
        headers = {"X-Trace-ID": request_trace_id}
        if api_key is not None:
            headers["Authorization"] = f"Bearer {api_key}"
        headers.update(extra_headers or {})

        with allure.step(f"{method.upper()} {path}"):
            if json is not None:
                allure.attach(
                    _safe_json(json),
                    name="request.json",
                    attachment_type=allure.attachment_type.JSON,
                )
            started_at = perf_counter()
            response = self._session.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                json=json,
                timeout=self._timeout_seconds,
            )
            elapsed_ms = (perf_counter() - started_at) * 1000
            allure.attach(
                _safe_response_body(response),
                name=f"response-{response.status_code}.json",
                attachment_type=allure.attachment_type.JSON,
            )
            allure.attach(
                f"trace_id={request_trace_id}\nelapsed_ms={elapsed_ms:.2f}",
                name="request-metadata.txt",
                attachment_type=allure.attachment_type.TEXT,
            )
        logger.info(
            "wallet_api method=%s path=%s status=%s trace_id=%s elapsed_ms=%.2f",
            method.upper(),
            path,
            response.status_code,
            request_trace_id,
            elapsed_ms,
        )
        return response

    def get_liveness(self, trace_id: str | None = None) -> requests.Response:
        return self.request("GET", "/health/live", trace_id=trace_id)

    def create_user(self, email: str) -> requests.Response:
        return self.request("POST", "/api/v1/users", json={"email": email})

    def create_wallet(self, user_id: UUID, api_key: str) -> requests.Response:
        return self.request(
            "POST",
            f"/api/v1/users/{user_id}/wallets",
            api_key=api_key,
        )

    def get_wallet(
        self,
        wallet_id: UUID,
        api_key: str | None,
    ) -> requests.Response:
        return self.request(
            "GET",
            f"/api/v1/wallets/{wallet_id}",
            api_key=api_key,
        )

    def deposit(
        self,
        wallet_id: UUID,
        amount: str | float,
        api_key: str,
        trace_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> requests.Response:
        return self.request(
            "POST",
            f"/api/v1/wallets/{wallet_id}/deposits",
            api_key=api_key,
            trace_id=trace_id,
            extra_headers={"Idempotency-Key": idempotency_key or f"deposit-{uuid4().hex}"},
            json={"amount": amount},
        )

    def withdraw(
        self,
        wallet_id: UUID,
        amount: str,
        api_key: str,
        idempotency_key: str | None = None,
    ) -> requests.Response:
        return self.request(
            "POST",
            f"/api/v1/wallets/{wallet_id}/withdrawals",
            api_key=api_key,
            extra_headers={"Idempotency-Key": idempotency_key or f"withdraw-{uuid4().hex}"},
            json={"amount": amount},
        )

    def transfer(
        self,
        source_wallet_id: UUID,
        destination_wallet_id: UUID,
        amount: str,
        api_key: str,
        idempotency_key: str | None = None,
    ) -> requests.Response:
        return self.request(
            "POST",
            "/api/v1/transfers",
            api_key=api_key,
            extra_headers={"Idempotency-Key": idempotency_key or f"transfer-{uuid4().hex}"},
            json={
                "source_wallet_id": str(source_wallet_id),
                "destination_wallet_id": str(destination_wallet_id),
                "amount": amount,
            },
        )

    def get_transaction(
        self,
        transaction_id: UUID,
        api_key: str,
    ) -> requests.Response:
        return self.request(
            "GET",
            f"/api/v1/transactions/{transaction_id}",
            api_key=api_key,
        )

    def refund(
        self,
        transaction_id: UUID,
        amount: str,
        api_key: str,
        idempotency_key: str | None = None,
    ) -> requests.Response:
        return self.request(
            "POST",
            f"/api/v1/transactions/{transaction_id}/refunds",
            api_key=api_key,
            extra_headers={"Idempotency-Key": idempotency_key or f"refund-{uuid4().hex}"},
            json={"amount": amount},
        )

    def start_channel_deposit(
        self,
        wallet_id: UUID,
        amount: str,
        api_key: str,
        idempotency_key: str | None = None,
    ) -> requests.Response:
        return self.request(
            "POST",
            f"/api/v1/wallets/{wallet_id}/channel-deposits",
            api_key=api_key,
            extra_headers={"Idempotency-Key": idempotency_key or f"channel-deposit-{uuid4().hex}"},
            json={"amount": amount},
        )

    def send_channel_callback(
        self,
        transaction_id: UUID,
        event_id: str,
        channel_status: str,
        channel_token: str = "local-test-channel-token",
    ) -> requests.Response:
        return self.request(
            "POST",
            "/api/v1/callbacks/channel",
            extra_headers={"X-Channel-Token": channel_token},
            json={
                "event_id": event_id,
                "transaction_id": str(transaction_id),
                "status": channel_status,
            },
        )

    def close(self) -> None:
        self._session.close()


def _safe_response_body(response: requests.Response) -> str:
    try:
        return _safe_json(response.json())
    except ValueError:
        return response.text


def _safe_json(value: Any) -> str:
    return json_module.dumps(
        redact_sensitive_data(value),
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def redact_sensitive_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "***REDACTED***"
                if key.lower() in {"api_key", "authorization", "password", "secret"}
                else redact_sensitive_data(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    return value
