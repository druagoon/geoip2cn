from __future__ import annotations

import ipaddress
from pathlib import Path

import pytest

from providers.ip2region_xdb import IP2RegionXdbProvider

VECTOR_INDEX_LENGTH = 256 * 256 * 8
HEADER_LENGTH = 256
INDEX_ENTRY_SIZE = 14


def build_xdb_file(path: Path, region: str, start_ip: str, end_ip: str) -> None:
    region_bytes = region.encode("utf-8")
    region_pointer = HEADER_LENGTH + VECTOR_INDEX_LENGTH
    index_pointer = region_pointer + len(region_bytes)

    header = bytearray(HEADER_LENGTH)
    header[8:12] = index_pointer.to_bytes(4, "little")
    header[12:16] = index_pointer.to_bytes(4, "little")
    vector_index = bytes(VECTOR_INDEX_LENGTH)
    index_entry = bytearray(INDEX_ENTRY_SIZE)
    index_entry[0:4] = int(ipaddress.IPv4Address(start_ip)).to_bytes(4, "little")
    index_entry[4:8] = int(ipaddress.IPv4Address(end_ip)).to_bytes(4, "little")
    index_entry[8:10] = len(region_bytes).to_bytes(2, "little")
    index_entry[10:14] = region_pointer.to_bytes(4, "little")

    path.write_bytes(bytes(header) + vector_index + region_bytes + bytes(index_entry))


def test_ip2region_provider_iter_records_parses_xdb(tmp_path: Path) -> None:
    db_file = tmp_path / "ip2region_v4.xdb"
    build_xdb_file(db_file, "中国|安徽省|合肥市|电信|CN", "1.1.1.0", "1.1.1.255")

    provider = IP2RegionXdbProvider(db_file)

    records = list(provider.iter_records())

    assert records[0].network == ipaddress.ip_network("1.1.1.0/24")
    assert records[0].country_code == "CN"
    assert records[0].province == "安徽省"
    assert records[0].city == "合肥市"


def test_ip2region_provider_download_error_stays_sanitized(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    provider = IP2RegionXdbProvider(tmp_path / "ip2region_v4.xdb")

    def fake_download_file(url: str, destination: Path, timeout: int, *, error_context: str) -> None:
        del url, destination, timeout, error_context
        raise RuntimeError("Database download error: provider=ip2region_xdb request_error=Timeout")

    monkeypatch.setattr("providers.ip2region_xdb.download_file", fake_download_file)

    with pytest.raises(
        RuntimeError, match=r"Database download error: provider=ip2region_xdb request_error=Timeout"
    ) as exc_info:
        provider.ensure_database()

    assert "https://" not in str(exc_info.value)
