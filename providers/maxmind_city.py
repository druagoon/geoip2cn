"""MaxMind GeoLite2 City provider implementation."""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import (
    Any,
)

import maxminddb

from models import (
    GeoRecord,
    ProviderCapability,
)
from providers.base import GeoIPProvider
from settings import (
    MAXMIND_CITY_ASSET_NAME,
    MAXMIND_RELEASE_API_URL,
    REQUEST_TIMEOUT_SECONDS,
)
from utils import (
    dotv_str,
    download_file,
    request_json,
    sha256sum,
)

logger = logging.getLogger(__name__)


class MaxMindCityProvider(GeoIPProvider):
    """Provider for MaxMind GeoLite2 City MMDB data."""

    name = "maxmind_city"
    capabilities = frozenset(
        {
            ProviderCapability.COUNTRY,
            ProviderCapability.PROVINCE,
            ProviderCapability.CITY,
        }
    )

    def __init__(self, db_file: Path) -> None:
        """Initialize the provider with the local MMDB file path."""
        self.db_file = db_file

    def ensure_database(self) -> None:
        """Download and verify the city database when it is missing."""
        if self.db_file.exists():
            return

        release = request_json(
            MAXMIND_RELEASE_API_URL,
            REQUEST_TIMEOUT_SECONDS,
            error_context="Release metadata error: provider=maxmind_city",
        )
        assets = release.get("assets")
        if not isinstance(assets, list):
            raise ValueError("Release metadata error: provider=maxmind_city field=assets reason=invalid_type")

        asset = next(
            (item for item in assets if isinstance(item, dict) and item.get("name") == MAXMIND_CITY_ASSET_NAME),
            None,
        )
        if not asset:
            raise RuntimeError(
                f"Release asset error: provider=maxmind_city asset={MAXMIND_CITY_ASSET_NAME} reason=missing"
            )

        download_url = asset.get("browser_download_url")
        if not isinstance(download_url, str) or not download_url:
            raise ValueError(
                "Release asset error: provider=maxmind_city field=browser_download_url reason=invalid_type"
            )

        logger.info("Database download: provider=maxmind_city source=%s", download_url)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        download_file(
            download_url,
            self.db_file,
            REQUEST_TIMEOUT_SECONDS,
            error_context="Database download error: provider=maxmind_city",
        )

        digest = asset.get("digest", "")
        expected_sha256 = digest.removeprefix("sha256:") if isinstance(digest, str) else ""
        if expected_sha256:
            actual_sha256 = sha256sum(self.db_file)
            if expected_sha256 != actual_sha256:
                raise RuntimeError(
                    "Checksum verification error: "
                    f"provider=maxmind_city expected_sha256={expected_sha256} actual_sha256={actual_sha256}"
                )

    def iter_records(self) -> Iterator[GeoRecord]:
        """Yield normalized IPv4 records from the MaxMind city MMDB."""
        logger.info("Database read: provider=maxmind_city source=%s", self.db_file)
        with maxminddb.open_database(self.db_file) as reader:
            for network, record in reader:
                if isinstance(network, ipaddress.IPv6Network):
                    continue
                try:
                    yield self._to_record(network, record)
                except Exception:
                    continue

    def _to_record(
        self,
        network: str | ipaddress.IPv4Network | ipaddress.IPv6Network,
        data: dict[str, Any],
    ) -> GeoRecord:
        subdivisions = data.get("subdivisions")
        province = ""
        if isinstance(subdivisions, list) and subdivisions:
            first_subdivision = subdivisions[0]
            if isinstance(first_subdivision, dict):
                province = dotv_str(first_subdivision, "names.en")

        parsed_network = (
            network
            if isinstance(network, ipaddress.IPv4Network | ipaddress.IPv6Network)
            else ipaddress.ip_network(network)
        )

        return GeoRecord(
            network=parsed_network,
            country_code=dotv_str(data, "country.iso_code"),
            province=province,
            city=dotv_str(data, "city.names.en"),
        )
