from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PerformanceThresholds:
    max_failure_ratio: float
    max_p95_ms: float
    min_requests_per_second: float


def quality_gate_violations(
    *,
    request_count: int,
    failure_ratio: float,
    p95_ms: float,
    requests_per_second: float,
    thresholds: PerformanceThresholds,
) -> list[str]:
    violations: list[str] = []
    if request_count == 0:
        return ["no performance samples were collected"]
    if failure_ratio > thresholds.max_failure_ratio:
        violations.append(
            f"failure ratio {failure_ratio:.4f} exceeds {thresholds.max_failure_ratio:.4f}"
        )
    if p95_ms > thresholds.max_p95_ms:
        violations.append(f"p95 {p95_ms:.2f}ms exceeds {thresholds.max_p95_ms:.2f}ms")
    if requests_per_second < thresholds.min_requests_per_second:
        violations.append(
            f"throughput {requests_per_second:.2f}rps is below "
            f"{thresholds.min_requests_per_second:.2f}rps"
        )
    return violations
