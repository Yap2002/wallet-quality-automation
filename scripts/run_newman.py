import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import TextIO
from uuid import uuid4

import requests

from tests.framework.config import TestSettings
from tests.tools.cleanup_postman_data import cleanup_postman_run

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NEWMAN_TIMEOUT_SECONDS = 120.0


def main() -> int:
    settings = TestSettings.from_environment()
    run_id = f"{int(time.time())}-{uuid4().hex[:8]}"
    process: subprocess.Popen[str] | None = None

    with tempfile.TemporaryFile(mode="w+t") as server_log:
        try:
            base_url = settings.base_url
            if base_url is None:
                port = _find_available_port()
                base_url = f"http://127.0.0.1:{port}"
                process = _start_server(port, settings.database_url, server_log)
            _wait_until_healthy(
                base_url,
                settings.startup_timeout_seconds,
                process,
                server_log,
            )

            result_directory = PROJECT_ROOT / "newman-results"
            result_directory.mkdir(exist_ok=True)
            result = subprocess.run(
                [
                    str(_newman_executable()),
                    "run",
                    "postman/wallet-api.postman_collection.json",
                    "-e",
                    "postman/local.postman_environment.json",
                    "--env-var",
                    f"base_url={base_url}",
                    "--env-var",
                    f"run_id={run_id}",
                    "--reporters",
                    "cli,junit",
                    "--reporter-junit-export",
                    "newman-results/wallet-api-report.xml",
                ],
                cwd=PROJECT_ROOT,
                check=False,
                timeout=_newman_timeout_seconds(),
            )
            return result.returncode
        finally:
            cleanup_postman_run(settings.database_url, run_id)
            if process is not None:
                _stop_process(process)


def _find_available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as available_socket:
        available_socket.bind(("127.0.0.1", 0))
        return int(available_socket.getsockname()[1])


def _newman_executable() -> Path:
    configured = os.getenv("NEWMAN_EXECUTABLE", "").strip()
    executable = (
        Path(configured).expanduser()
        if configured
        else PROJECT_ROOT / "node_modules" / ".bin" / "newman"
    )
    if not executable.exists():
        raise FileNotFoundError(
            f"Newman executable was not found at {executable}. Run 'npm ci' first or set "
            "NEWMAN_EXECUTABLE."
        )
    return executable


def _newman_timeout_seconds() -> float:
    raw_timeout = os.getenv("NEWMAN_TIMEOUT_SECONDS", str(DEFAULT_NEWMAN_TIMEOUT_SECONDS))
    try:
        timeout_seconds = float(raw_timeout)
    except ValueError as error:
        raise ValueError("NEWMAN_TIMEOUT_SECONDS must be a number") from error
    if timeout_seconds <= 0:
        raise ValueError("NEWMAN_TIMEOUT_SECONDS must be greater than zero")
    return timeout_seconds


def _start_server(
    port: int,
    database_url: str,
    server_log: TextIO,
) -> subprocess.Popen[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": database_url,
            "PYTHONUNBUFFERED": "1",
        }
    )
    return subprocess.Popen(
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


def _wait_until_healthy(
    base_url: str,
    timeout_seconds: float,
    process: subprocess.Popen[str] | None,
    server_log: TextIO,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "service did not respond"
    with requests.Session() as health_session:
        health_session.trust_env = False
        while time.monotonic() < deadline:
            if process is not None and process.poll() is not None:
                raise RuntimeError(
                    f"wallet service exited during startup:\n{_read_log(server_log)}"
                )
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
    raise RuntimeError(
        f"wallet service was not healthy within {timeout_seconds}s: "
        f"{last_error}\n{_read_log(server_log)}"
    )


def _read_log(server_log: TextIO) -> str:
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


if __name__ == "__main__":
    raise SystemExit(main())
