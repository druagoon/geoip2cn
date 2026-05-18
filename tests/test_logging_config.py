from __future__ import annotations

import pytest

from logging_config import build_logging_config
from settings import get_settings


def test_build_logging_config_defaults_to_info_when_log_level_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    get_settings.cache_clear()

    config = build_logging_config()

    assert config["root"]["level"] == "INFO"
    assert config["handlers"]["console"]["level"] == "INFO"


def test_build_logging_config_defaults_to_info_when_log_level_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "   ")
    get_settings.cache_clear()

    config = build_logging_config()

    assert config["root"]["level"] == "INFO"
    assert config["handlers"]["console"]["level"] == "INFO"


def test_build_logging_config_uses_environment_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "debug")
    get_settings.cache_clear()

    config = build_logging_config()

    assert config["root"]["level"] == "DEBUG"
    assert config["handlers"]["console"]["level"] == "DEBUG"
