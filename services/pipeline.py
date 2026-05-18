"""Pipeline assembly for GeoIP extraction and rendering."""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Set
from dataclasses import dataclass

from models import RecordRule
from providers.base import GeoIPProvider
from providers.ip2region_xdb import IP2RegionXdbProvider
from providers.ipinfo_lite import IPinfoLiteProvider
from renderers.nftables import NftablesRenderer
from rules.asn_blacklist import (
    ASNBlacklistRule,
    parse_asn_denylist,
)
from rules.city_whitelist import (
    CityWhitelistRule,
    parse_city_whitelist,
)
from services.extractors import extract_ipv4_networks
from settings import (
    IP2REGION_XDB_FILE,
    IPINFO_DB_FILE,
    NFTABLES_GEOIP_BLACKLIST_V4_NAME,
    NFTABLES_GEOIP_WHITELIST_V4_NAME,
    NFTABLES_OUTPUT_FILE,
    NFTABLES_TEMPLATE_NAME,
    TEMPLATE_DIR,
    Settings,
    get_settings,
)
from utils import parse_ipv4_networks

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NftablesNetworks:
    """Extracted IPv4 network sets used to render nftables output."""

    blacklist_v4: set[ipaddress.IPv4Network]
    whitelist_v4: set[ipaddress.IPv4Network]


@dataclass(frozen=True)
class ExtractionJob:
    """One extraction unit combining a provider with a matching rule."""

    name: str
    provider: GeoIPProvider
    rule: RecordRule

    def run(self) -> set[ipaddress.IPv4Network]:
        """Execute the extraction job and return IPv4 networks."""
        logger.info("Extraction job start: name=%s provider=%s", self.name, self.provider.name)
        return extract_ipv4_networks(self.provider, self.rule)


@dataclass(frozen=True)
class NftablesPipeline:
    """Pipeline that extracts blacklist/whitelist networks and renders nftables output."""

    blacklist_job: ExtractionJob
    whitelist_job: ExtractionJob
    renderer: NftablesRenderer
    allowed_ips: Set[ipaddress.IPv4Network] = frozenset()

    def extract(self) -> NftablesNetworks:
        """Extract blacklist and whitelist networks for nftables rendering."""
        networks = NftablesNetworks(
            blacklist_v4=self.blacklist_job.run(),
            whitelist_v4=self.whitelist_job.run(),
        )
        logger.info(
            "Pipeline extract: blacklist_v4=%d whitelist_v4=%d", len(networks.blacklist_v4), len(networks.whitelist_v4)
        )
        return networks

    def run(self) -> NftablesNetworks:
        """Execute extraction and render the nftables configuration."""
        networks = self.extract()
        self.renderer.write(networks.blacklist_v4, networks.whitelist_v4, allowed_ips=self.allowed_ips)
        logger.info("Pipeline run complete")
        return networks


def build_nftables_pipeline() -> NftablesPipeline:
    """Assemble the default nftables extraction and rendering pipeline."""
    settings = get_settings()
    allowed_ips = parse_ipv4_networks(settings.allowed_ips)
    asn_denylist = parse_asn_denylist(settings.asn_denylist)
    city_whitelist = parse_city_whitelist(settings.city_whitelist, env_var=Settings.env_name("city_whitelist"))
    return NftablesPipeline(
        blacklist_job=ExtractionJob(
            NFTABLES_GEOIP_BLACKLIST_V4_NAME,
            IPinfoLiteProvider(IPINFO_DB_FILE),
            ASNBlacklistRule(asn_denylist),
        ),
        whitelist_job=ExtractionJob(
            NFTABLES_GEOIP_WHITELIST_V4_NAME,
            IP2RegionXdbProvider(IP2REGION_XDB_FILE),
            CityWhitelistRule(city_whitelist),
        ),
        renderer=NftablesRenderer(TEMPLATE_DIR, NFTABLES_OUTPUT_FILE, NFTABLES_TEMPLATE_NAME),
        allowed_ips=allowed_ips,
    )
