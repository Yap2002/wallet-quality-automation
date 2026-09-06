from pathlib import Path

import pytest

from scripts.run_newman import _newman_executable, _newman_timeout_seconds


def test_newman_executable_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    executable = tmp_path / "newman"
    executable.touch()
    monkeypatch.setenv("NEWMAN_EXECUTABLE", str(executable))

    assert _newman_executable() == executable


def test_newman_executable_reports_missing_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing_executable = tmp_path / "missing-newman"
    monkeypatch.setenv("NEWMAN_EXECUTABLE", str(missing_executable))

    with pytest.raises(FileNotFoundError, match="npm ci"):
        _newman_executable()


@pytest.mark.parametrize("invalid_timeout", ["not-a-number", "0", "-1"])
def test_newman_timeout_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
    invalid_timeout: str,
) -> None:
    monkeypatch.setenv("NEWMAN_TIMEOUT_SECONDS", invalid_timeout)

    with pytest.raises(ValueError, match="NEWMAN_TIMEOUT_SECONDS"):
        _newman_timeout_seconds()
