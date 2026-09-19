import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.observability import JsonFormatter


def test_http_log_contains_trace_fields_without_credentials(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="wallet.http")

    async def send_request() -> int:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/health/live",
                headers={
                    "X-Trace-ID": "log-assertion-trace",
                    "Authorization": "Bearer must-not-appear-in-log",
                },
            )
        return response.status_code

    with ThreadPoolExecutor(max_workers=1) as executor:
        status_code = executor.submit(asyncio.run, send_request()).result()
    assert status_code == 200

    records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "http_request_completed"
    ]
    assert len(records) == 1
    record = records[0]
    assert record.trace_id == "log-assertion-trace"  # type: ignore[attr-defined]
    assert record.method == "GET"  # type: ignore[attr-defined]
    assert record.path == "/health/live"  # type: ignore[attr-defined]
    assert record.status_code == 200  # type: ignore[attr-defined]
    rendered = JsonFormatter().format(record)
    parsed = json.loads(rendered)
    assert parsed["event"] == "http_request_completed"
    assert isinstance(parsed["duration_ms"], float)
    assert "must-not-appear-in-log" not in rendered
