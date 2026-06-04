from __future__ import annotations

import ipaddress
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest

from providers.ipinfo_lite import IPinfoLiteProvider
from providers.maxmind_city import MaxMindCityProvider


class DummyDatabase:
    def __init__(self, rows: list[tuple[str, dict[str, object]]]) -> None:
        self.rows = rows

    def __enter__(self) -> DummyDatabase:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def __iter__(self) -> Iterator[tuple[str, dict[str, object]]]:
        return iter(self.rows)


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


def test_ipinfo_provider_iter_records_skips_unmatched_country_codes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider = IPinfoLiteProvider(tmp_path / "ipinfo_lite.mmdb", country_codes=frozenset({"CN"}))
    rows = [
        ("1.1.1.0/24", {"country_code": "CN", "asn": "AS4134"}),
        ("2.2.2.0/24", {"country_code": "US", "asn": "AS15169"}),
    ]

    monkeypatch.setattr(
        "providers.ipinfo_lite.maxminddb.open_database",
        lambda db_file: DummyDatabase(cast(list[tuple[str, dict[str, object]]], rows)),
    )

    records = list(provider.iter_records())

    assert [record.network for record in records] == [ipaddress.ip_network("1.1.1.0/24")]
    assert [record.country_code for record in records] == ["CN"]


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
