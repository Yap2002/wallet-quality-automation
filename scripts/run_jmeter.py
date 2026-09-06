import csv
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import TextIO

import requests

from tests.framework.config import TestSettings
from tests.tools.cleanup_jmeter_data import cleanup_jmeter_run

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    settings = TestSettings.from_environment()
    run_id = str(int(time.time()))
    threads = int(os.getenv("JMETER_THREADS", "3"))
    loops = int(os.getenv("JMETER_LOOPS", "5"))
    port = _available_port()
    output_root = PROJECT_ROOT / "performance-results"
    report_directory = output_root / "jmeter-html"
    result_file = output_root / "jmeter-results.jtl"
    shutil.rmtree(report_directory, ignore_errors=True)
    result_file.unlink(missing_ok=True)
    output_root.mkdir(exist_ok=True)

    with tempfile.TemporaryFile(mode="w+t") as server_log:
        process = _start_server(port, settings.database_url, server_log)
        try:
            _wait_until_healthy(port, process, server_log)
            command = [
                "jmeter",
                "-n",
                "-t",
                "performance/wallet-api.jmx",
                "-l",
                str(result_file),
                "-e",
                "-o",
                str(report_directory),
                "-Jhost=127.0.0.1",
                "-Jhttp.nonProxyHosts=localhost|127.*",
                f"-Jport={port}",
                f"-Jrun_id={run_id}",
                f"-Jthreads={threads}",
                "-Jramp_up=1",
                f"-Jloops={loops}",
            ]
            jmeter_result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
            if jmeter_result.returncode != 0:
                return jmeter_result.returncode
            return 1 if _failed_sample_count(result_file) else 0
        finally:
            cleanup_jmeter_run(settings.database_url, run_id, threads)
            _stop_process(process)


def _available_port() -> int:
    with socket.socket() as available_socket:
        available_socket.bind(("127.0.0.1", 0))
        return int(available_socket.getsockname()[1])


def _start_server(port: int, database_url: str, server_log: TextIO) -> subprocess.Popen[str]:
    environment = os.environ.copy()
    environment.update({"APP_ENV": "test", "DATABASE_URL": database_url})
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
    port: int,
    process: subprocess.Popen[str],
    server_log: TextIO,
) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            server_log.seek(0)
            raise RuntimeError(server_log.read())
        try:
            if requests.get(f"http://127.0.0.1:{port}/health/live", timeout=0.5).status_code == 200:
                return
        except requests.RequestException:
            time.sleep(0.1)
    raise RuntimeError("JMeter target service did not become healthy")


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _failed_sample_count(result_file: Path) -> int:
    with result_file.open(newline="", encoding="utf-8") as source:
        return sum(row.get("success", "false").lower() != "true" for row in csv.DictReader(source))


if __name__ == "__main__":
    raise SystemExit(main())
