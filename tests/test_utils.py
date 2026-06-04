from __future__ import annotations

import ipaddress
from pathlib import Path

import pytest
import requests

from rules.asn_blacklist import parse_asn_denylist
from rules.city_whitelist import (
    Region,
    parse_city_whitelist,
)
from utils import (
    dotv_str,
    download_file,
    parse_country_codes,
    parse_ipv4_networks,
    request_json,
    split_comma,
)

TEST_TIMEOUT_SECONDS = 1


class DummyResponse:
    def __init__(self, status_code: int, payload: object | None = None, chunks: list[bytes] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self._chunks = chunks or []

    def __enter__(self) -> DummyResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def json(self) -> object:
        return self._payload

    def iter_content(self, chunk_size: int) -> list[bytes]:
        del chunk_size
        return self._chunks


def test_request_json_hides_url_on_request_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    secret_url = "https://example.com/data?token=super-secret-token"

    def fake_get(url: str, timeout: int) -> DummyResponse:
        del timeout
        raise requests.ConnectionError(f"failed for {url}")

    monkeypatch.setattr("utils.requests.get", fake_get)

    with pytest.raises(
        RuntimeError, match=r"Release metadata error: provider=maxmind_city: request_error=ConnectionError"
    ) as exc_info:
        request_json(secret_url, TEST_TIMEOUT_SECONDS, error_context="Release metadata error: provider=maxmind_city")

    assert secret_url not in str(exc_info.value)
    assert "super-secret-token" not in str(exc_info.value)


def test_request_json_hides_url_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    secret_url = "https://example.com/data?token=super-secret-token"

    def fake_get(url: str, timeout: int) -> DummyResponse:
        del url, timeout
        return DummyResponse(status_code=403, payload={})

    monkeypatch.setattr("utils.requests.get", fake_get)

    with pytest.raises(
        RuntimeError, match=r"Release metadata error: provider=maxmind_city: status_code=403"
    ) as exc_info:
        request_json(secret_url, TEST_TIMEOUT_SECONDS, error_context="Release metadata error: provider=maxmind_city")

    assert secret_url not in str(exc_info.value)
    assert "super-secret-token" not in str(exc_info.value)


def test_download_file_hides_url_on_request_exception(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    secret_url = "https://example.com/file?token=super-secret-token"
    destination = tmp_path / "download.bin"

    def fake_get(url: str, stream: bool, timeout: int) -> DummyResponse:
        del stream, timeout
        raise requests.Timeout(f"timed out for {url}")

    monkeypatch.setattr("utils.requests.get", fake_get)

    with pytest.raises(
        RuntimeError, match=r"Database download error: provider=ipinfo_lite: request_error=Timeout"
    ) as exc_info:
        download_file(
            secret_url,
            destination,
            TEST_TIMEOUT_SECONDS,
            error_context="Database download error: provider=ipinfo_lite",
        )

    assert secret_url not in str(exc_info.value)
    assert "super-secret-token" not in str(exc_info.value)


def test_download_file_hides_url_on_http_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    secret_url = "https://example.com/file?token=super-secret-token"
    destination = tmp_path / "download.bin"

    def fake_get(url: str, stream: bool, timeout: int) -> DummyResponse:
        del url, stream, timeout
        return DummyResponse(status_code=401)

    monkeypatch.setattr("utils.requests.get", fake_get)

    with pytest.raises(
        RuntimeError, match=r"Database download error: provider=ipinfo_lite: status_code=401"
    ) as exc_info:
        download_file(
            secret_url,
            destination,
            TEST_TIMEOUT_SECONDS,
            error_context="Database download error: provider=ipinfo_lite",
        )

    assert secret_url not in str(exc_info.value)
    assert "super-secret-token" not in str(exc_info.value)


def test_dotv_str_returns_nested_string_value() -> None:
    data = {"city": {"names": {"en": "Shanghai"}}}

    assert dotv_str(data, "city.names.en") == "Shanghai"


def test_dotv_str_falls_back_for_non_string_value() -> None:
    data = {"city": {"names": {"en": 123}}}

    assert dotv_str(data, "city.names.en", default="") == ""


def test_parse_ipv4_networks_trims_whitespace() -> None:
    networks = parse_ipv4_networks(" 10.0.0.0/24,  192.168.0.1/32 ,\t172.16.0.0/16 ")

    assert networks == {
        ipaddress.ip_network("10.0.0.0/24"),
        ipaddress.ip_network("192.168.0.1/32"),
        ipaddress.ip_network("172.16.0.0/16"),
    }


def test_parse_country_codes_trims_whitespace_and_normalizes_case() -> None:
    codes = parse_country_codes(" cn,  us, ,jp ")

    assert codes == {"CN", "US", "JP"}


def test_parse_country_codes_allows_empty_value() -> None:
    assert parse_country_codes("") == set()


def test_split_comma_trims_whitespace_and_skips_empty_items() -> None:
    items = tuple(split_comma(" foo, ,  bar ,,\tbaz "))

    assert items == ("foo", "bar", "baz")


def test_split_comma_applies_callback() -> None:
    items = tuple(split_comma(" as4134, as4811 ", callback=str.upper))

    assert items == ("AS4134", "AS4811")


def test_split_comma_preserves_whitespace_when_strip_disabled() -> None:
    items = tuple(split_comma(" foo, ,  bar ", strip=False))

    assert items == (" foo", " ", "  bar ")


def test_parse_asn_denylist_normalizes_to_uppercase() -> None:
    denylist = parse_asn_denylist(" as4134, as4811 ")

    assert denylist == ("AS4134", "AS4811")


def test_parse_city_whitelist_trims_whitespace() -> None:
    whitelist = parse_city_whitelist(" cn|shanghai|shanghai , cn|jiangsu|nanjing ")

    assert whitelist == (
        Region("cn", "shanghai", "shanghai"),
        Region("cn", "jiangsu", "nanjing"),
    )


def test_parse_city_whitelist_normalizes_to_lowercase() -> None:
    whitelist = parse_city_whitelist(" CN|Shanghai|Shanghai , Cn|Jiangsu|Nanjing ")

    assert whitelist == (
        Region("cn", "shanghai", "shanghai"),
        Region("cn", "jiangsu", "nanjing"),
    )


def test_parse_city_whitelist_rejects_empty_value() -> None:
    with pytest.raises(ValueError, match=r"Configuration error: env_var=city_whitelist reason=empty"):
        parse_city_whitelist("")
