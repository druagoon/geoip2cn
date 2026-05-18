"""ip2region XDB provider implementation."""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Iterator
from pathlib import Path

from models import (
    GeoRecord,
    ProviderCapability,
)
from providers.base import GeoIPProvider
from settings import (
    IP2REGION_XDB_DOWNLOAD_URL,
    REQUEST_TIMEOUT_SECONDS,
)
from utils import download_file

logger = logging.getLogger(__name__)

HEADER_INDEX_START_OFFSET = 8
HEADER_INDEX_END_OFFSET = 12
INDEX_ENTRY_SIZE = 14


class IP2RegionXdbProvider(GeoIPProvider):
    """Provider for ip2region IPv4 XDB data."""

    name = "ip2region_xdb"
    capabilities = frozenset(
        {
            ProviderCapability.COUNTRY,
            ProviderCapability.PROVINCE,
            ProviderCapability.CITY,
        }
    )

    def __init__(self, db_file: Path) -> None:
        self.db_file = db_file

    def ensure_database(self) -> None:
        if self.db_file.exists():
            return

        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Database download: provider=ip2region_xdb source=%s", IP2REGION_XDB_DOWNLOAD_URL)
        download_file(
            IP2REGION_XDB_DOWNLOAD_URL,
            self.db_file,
            REQUEST_TIMEOUT_SECONDS,
            error_context="Database download error: provider=ip2region_xdb",
        )

    def iter_records(self) -> Iterator[GeoRecord]:
        logger.info("Database read: provider=ip2region_xdb source=%s", self.db_file)
        data = self.db_file.read_bytes()
        index_start = int.from_bytes(data[HEADER_INDEX_START_OFFSET : HEADER_INDEX_START_OFFSET + 4], "little")
        index_end = int.from_bytes(data[HEADER_INDEX_END_OFFSET : HEADER_INDEX_END_OFFSET + 4], "little")

        if index_start <= 0 or index_end < index_start:
            raise ValueError("XDB parse error: provider=ip2region_xdb field=index_range reason=invalid")

        for offset in range(index_start, index_end + 1, INDEX_ENTRY_SIZE):
            entry = data[offset : offset + INDEX_ENTRY_SIZE]
            if len(entry) != INDEX_ENTRY_SIZE:
                raise ValueError("XDB parse error: provider=ip2region_xdb field=index_entry reason=truncated")

            start_ip = ipaddress.IPv4Address(int.from_bytes(entry[0:4], "little"))
            end_ip = ipaddress.IPv4Address(int.from_bytes(entry[4:8], "little"))
            region_length = int.from_bytes(entry[8:10], "little")
            region_pointer = int.from_bytes(entry[10:14], "little")
            region_string = data[region_pointer : region_pointer + region_length].decode("utf-8")
            _, province, city, country_code = self._parse_region(region_string)
            logger.debug(
                "Parsed record: provider=ip2region_xdb start_ip=%s end_ip=%s country_code=%s province=%s city=%s",
                start_ip,
                end_ip,
                country_code,
                province,
                city,
            )

            for network in ipaddress.summarize_address_range(start_ip, end_ip):
                yield GeoRecord(
                    network=network,
                    country_code=country_code,
                    province=province,
                    city=city,
                )

    def _parse_region(self, region: str) -> tuple[str, str, str, str]:
        parts = region.split("|")
        country = self._normalize_region_part(parts, 0)
        province = self._normalize_region_part(parts, 1)
        city = self._normalize_region_part(parts, 2)
        country_code = self._normalize_region_part(parts, 4).upper()
        if not country_code:
            country_code = country.upper()
        return country, province, city, country_code

    @staticmethod
    def _normalize_region_part(parts: list[str], index: int) -> str:
        if index >= len(parts):
            return ""
        value = parts[index].strip()
        return "" if value == "0" else value
