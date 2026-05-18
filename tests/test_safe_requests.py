from __future__ import annotations

from pathlib import Path

import pytest

from providers.ipinfo_lite import IPinfoLiteProvider
from providers.maxmind_city import MaxMindCityProvider


def test_ipinfo_provider_download_error_does_not_expose_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    secret_token = "super-secret-token"
    provider = IPinfoLiteProvider(tmp_path / "ipinfo_lite.mmdb")

    monkeypatch.setenv("ipinfo_token", secret_token)

    def fake_download_file(url: str, destination: Path, timeout: int, *, error_context: str) -> None:
        del destination, timeout, error_context
        assert secret_token in url
        raise RuntimeError("Database download error: provider=ipinfo_lite request_error=Timeout")

    monkeypatch.setattr("providers.ipinfo_lite.download_file", fake_download_file)

    with pytest.raises(
        RuntimeError, match=r"Database download error: provider=ipinfo_lite request_error=Timeout"
    ) as exc_info:
        provider.ensure_database()

    assert secret_token not in str(exc_info.value)


def test_maxmind_provider_release_error_stays_sanitized(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    provider = MaxMindCityProvider(tmp_path / "GeoLite2-City.mmdb")

    def fake_request_json(url: str, timeout: int, *, error_context: str) -> dict[str, object]:
        del url, timeout, error_context
        raise RuntimeError("Release metadata error: provider=maxmind_city request_error=ConnectionError")

    monkeypatch.setattr("providers.maxmind_city.request_json", fake_request_json)

    with pytest.raises(
        RuntimeError, match=r"Release metadata error: provider=maxmind_city request_error=ConnectionError"
    ) as exc_info:
        provider.ensure_database()

    assert "https://" not in str(exc_info.value)
