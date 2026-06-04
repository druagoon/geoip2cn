"""IPinfo Lite provider implementation."""

from __future__ import annotations

import datetime
import ipaddress
import logging
from collections.abc import Iterator
from pathlib import Path

import maxminddb

from models import (
    GeoRecord,
    ProviderCapability,
)
from providers.base import GeoIPProvider
from settings import (
    IPINFO_LITE_DOWNLOAD_URL,
    REQUEST_TIMEOUT_SECONDS,
    Settings,
    get_settings,
)
from utils import download_file

logger = logging.getLogger(__name__)


class IPinfoLiteProvider(GeoIPProvider):
    """Provider for IPinfo Lite MMDB data."""

    name = "ipinfo_lite"
    capabilities = frozenset({ProviderCapability.COUNTRY, ProviderCapability.ASN})

    def __init__(self, db_file: Path, country_codes: frozenset[str] = frozenset()) -> None:
        """Initialize the provider with the local MMDB file path."""
        self.db_file = db_file
        self.country_codes = country_codes

    def ensure_database(self) -> None:
        """Refresh the MMDB when a token is configured and the data is stale."""
        token = get_settings().ipinfo_token
        if not token:
            raise ValueError(f"Configuration error: env_var={Settings.env_name('ipinfo_token')} reason=missing")

        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        if self.db_file.exists():
            with maxminddb.open_database(self.db_file) as reader:
                metadata = reader.metadata()
                build_time = datetime.datetime.fromtimestamp(metadata.build_epoch, datetime.UTC)
                today = datetime.datetime.combine(datetime.date.today(), datetime.time.min, datetime.UTC)
                logger.info("Database status: provider=ipinfo_lite build_time=%s", build_time.isoformat())
                if build_time >= today:
                    return

            logger.info("Database download: provider=ipinfo_lite target=%s", self.db_file)
        download_url = IPINFO_LITE_DOWNLOAD_URL.format(token=token)
        download_file(
            download_url,
            self.db_file,
            REQUEST_TIMEOUT_SECONDS,
            error_context="Database download error: provider=ipinfo_lite",
        )

    def iter_records(self) -> Iterator[GeoRecord]:
        """Yield normalized IPv4 records from the IPinfo MMDB."""
        logger.info("Database read: provider=ipinfo_lite source=%s", self.db_file)
        with maxminddb.open_database(self.db_file) as reader:
            for network, record in reader:
                if isinstance(network, ipaddress.IPv6Network):
                    continue
                try:
                    geo_record = self._to_record(network, record)
                    if not self.supports_country_code(geo_record.country_code):
                        continue
                    logger.debug("Read record: provider=ipinfo_lite network=%s record=%s", network, record)
                    yield geo_record
                except Exception:
                    continue

    def _to_record(
        self,
        network: str | ipaddress.IPv4Network | ipaddress.IPv6Network,
        data: dict[str, object],
    ) -> GeoRecord:
        parsed_network = (
            network
            if isinstance(network, ipaddress.IPv4Network | ipaddress.IPv6Network)
            else ipaddress.ip_network(network)
        )
        return GeoRecord(
            network=parsed_network,
            country_code=str(data.get("country_code", "")),
            asn=str(data.get("asn", "")),
            province=str(data.get("province", "")),
            city=str(data.get("city", "")),
        )
