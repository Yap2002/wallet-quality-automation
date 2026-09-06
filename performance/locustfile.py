import os
from uuid import uuid4

from locust import HttpUser, between, events, task
from locust.env import Environment

from performance.quality_gate import PerformanceThresholds, quality_gate_violations


@events.quitting.add_listener
def enforce_performance_quality_gate(environment: Environment, **_: object) -> None:
    total = environment.stats.total
    violations = quality_gate_violations(
        request_count=total.num_requests,
        failure_ratio=total.fail_ratio,
        p95_ms=float(total.get_response_time_percentile(0.95) or 0),
        requests_per_second=total.total_rps,
        thresholds=PerformanceThresholds(
            max_failure_ratio=float(os.getenv("PERF_MAX_FAILURE_RATIO", "0.01")),
            max_p95_ms=float(os.getenv("PERF_MAX_P95_MS", "500")),
            min_requests_per_second=float(os.getenv("PERF_MIN_RPS", "1")),
        ),
    )
    if violations:
        environment.process_exit_code = 1
        for violation in violations:
            print(f"PERFORMANCE QUALITY GATE FAILED: {violation}")


class WalletApiUser(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self) -> None:
        run_id = uuid4().hex
        user_response = self.client.post(
            "/api/v1/users",
            json={"email": f"locust-{run_id}@example.com"},
            name="POST /users",
        )
        user_response.raise_for_status()
        user = user_response.json()
        self.api_key = user["api_key"]
        wallet_response = self.client.post(
            f"/api/v1/users/{user['id']}/wallets",
            headers=self._headers(),
            name="POST /users/:id/wallets",
        )
        wallet_response.raise_for_status()
        self.wallet_id = wallet_response.json()["id"]

    @task(4)
    def query_balance(self) -> None:
        with self.client.get(
            f"/api/v1/wallets/{self.wallet_id}",
            headers=self._headers(),
            name="GET /wallets/:id",
            catch_response=True,
        ) as response:
            if response.status_code != 200 or "balance" not in response.json():
                response.failure(f"unexpected wallet response: {response.text}")

    @task(1)
    def deposit(self) -> None:
        with self.client.post(
            f"/api/v1/wallets/{self.wallet_id}/deposits",
            headers=self._headers(idempotency_key=f"locust-{uuid4().hex}"),
            json={"amount": "0.01"},
            name="POST /wallets/:id/deposits",
            catch_response=True,
        ) as response:
            if response.status_code != 201:
                response.failure(f"deposit failed: {response.text}")

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        return headers
