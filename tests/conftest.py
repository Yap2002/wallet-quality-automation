import os
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO

import pytest
import requests
from sqlalchemy import Engine, create_engine

from tests.framework.clients.wallet_api_client import WalletApiClient
from tests.framework.config import TestSettings
from tests.framework.database import DatabaseClient
from tests.framework.factories import TestDataFactory
from tests.framework.logging import configure_test_logging
from tests.framework.steps import WalletSteps

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def pytest_configure() -> None:
    configure_test_logging()


@pytest.fixture(scope="session")
def test_settings() -> TestSettings:
    return TestSettings.from_environment()


@pytest.fixture(scope="session")
def live_service_url(test_settings: TestSettings) -> Iterator[str]:
    if test_settings.base_url is not None:
        _wait_until_healthy(
            test_settings.base_url,
            test_settings.startup_timeout_seconds,
        )
        yield test_settings.base_url
        return

    port = _find_available_port()
    base_url = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": test_settings.database_url,
            "PYTHONUNBUFFERED": "1",
        }
    )

    with tempfile.TemporaryFile(mode="w+t") as server_log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            _wait_until_healthy(
                base_url,
                test_settings.startup_timeout_seconds,
                process,
                server_log,
            )
            yield base_url
        finally:
            _stop_process(process)


@pytest.fixture
def wallet_api_client(
    live_service_url: str,
    test_settings: TestSettings,
) -> Iterator[WalletApiClient]:
    client = WalletApiClient(
        base_url=live_service_url,
        timeout_seconds=test_settings.request_timeout_seconds,
    )
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="session")
def test_database_engine(test_settings: TestSettings) -> Iterator[Engine]:
    engine = create_engine(test_settings.database_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def database_client(test_database_engine: Engine) -> DatabaseClient:
    return DatabaseClient(test_database_engine)


@pytest.fixture
def wallet_steps(wallet_api_client: WalletApiClient) -> WalletSteps:
    return WalletSteps(wallet_api_client)


@pytest.fixture
def test_data_factory(
    wallet_steps: WalletSteps,
    database_client: DatabaseClient,
) -> Iterator[TestDataFactory]:
    factory = TestDataFactory(wallet_steps, database_client)
    try:
        yield factory
    finally:
        factory.cleanup()


def _find_available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as available_socket:
        available_socket.bind(("127.0.0.1", 0))
        return int(available_socket.getsockname()[1])


def _wait_until_healthy(
    base_url: str,
    timeout_seconds: float,
    process: subprocess.Popen[str] | None = None,
    server_log: TextIO | None = None,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "service did not respond"
    with requests.Session() as health_session:
        health_session.trust_env = False
        while time.monotonic() < deadline:
            if process is not None and process.poll() is not None:
                pytest.fail(f"wallet service exited during startup:\n{_read_log(server_log)}")
            try:
                response = health_session.get(
                    f"{base_url}/health/live",
                    timeout=0.5,
                )
                if response.status_code == 200:
                    return
                last_error = f"health endpoint returned {response.status_code}"
            except requests.RequestException as error:
                last_error = str(error)
            time.sleep(0.1)

    pytest.fail(
        f"wallet service was not healthy within {timeout_seconds}s: "
        f"{last_error}\n{_read_log(server_log)}"
    )


def _read_log(server_log: TextIO | None) -> str:
    if server_log is None:
        return "no local server log is available"
    server_log.flush()
    server_log.seek(0)
    return server_log.read()


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
