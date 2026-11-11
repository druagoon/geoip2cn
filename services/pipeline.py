"""Pipeline assembly for GeoIP extraction and rendering."""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import TYPE_CHECKING

from providers.ip2region_xdb import IP2RegionXdbProvider
from providers.ipinfo_lite import IPinfoLiteProvider
from renderers.nftables import NftablesRenderer
from rules.asn_blacklist import (
    ASNBlacklistRule,
    parse_asn_denylist,
)
from rules.asn_whitelist import (
    ASNWhitelistRule,
    parse_asn_allowlist,
)
from rules.city_whitelist import (
    CityWhitelistRule,
    parse_city_whitelist,
)
from services.extractors import extract_ipv4_networks_by_rule
from settings import (
    IP2REGION_XDB_FILE,
    IPINFO_DB_FILE,
    NFTABLES_GEOIP_BLACKLIST_V4_NAME,
    NFTABLES_OUTPUT_FILE,
    NFTABLES_TEMPLATE_NAME,
    TEMPLATE_DIR,
    Settings,
    get_settings,
)
from utils import (
    parse_country_codes,
    parse_ipv4_networks,
)

if TYPE_CHECKING:
    from models import RecordRule
    from providers.base import GeoIPProvider

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


@dataclass(frozen=True)
class NftablesPipeline:
    """Pipeline that extracts blacklist/whitelist networks and renders nftables output."""

    blacklist_job: ExtractionJob
    whitelist_jobs: tuple[ExtractionJob, ...]
    renderer: NftablesRenderer
    allowed_ips: AbstractSet[ipaddress.IPv4Network] = frozenset()
    blocked_ips: AbstractSet[ipaddress.IPv4Network] = frozenset()

    def extract(self) -> NftablesNetworks:
        """Extract blacklist and whitelist networks for nftables rendering."""
        jobs_by_provider: dict[GeoIPProvider, list[ExtractionJob]] = {}
        for job in (self.blacklist_job, *self.whitelist_jobs):
            jobs_by_provider.setdefault(job.provider, []).append(job)

        blacklist_v4: set[ipaddress.IPv4Network] = set()
        whitelist_v4: set[ipaddress.IPv4Network] = set()
        for provider, jobs in jobs_by_provider.items():
            logger.info("Extraction jobs start: names=%s provider=%s", [job.name for job in jobs], provider.name)
            results = extract_ipv4_networks_by_rule(provider, tuple(job.rule for job in jobs))
            for job, result in zip(jobs, results, strict=True):
                logger.info("Extraction job result: name=%s ipv4_networks=%d", job.name, len(result))
                if job is self.blacklist_job:
                    blacklist_v4.update(result)
                else:
                    whitelist_v4.update(result)
        networks = NftablesNetworks(blacklist_v4=blacklist_v4, whitelist_v4=whitelist_v4)
        logger.info(
            "Pipeline extract: blacklist_v4=%d whitelist_v4=%d", len(networks.blacklist_v4), len(networks.whitelist_v4)
        )
        return networks

    def run(self) -> NftablesNetworks:
        """Execute extraction and render the nftables configuration."""
        networks = self.extract()
        self.renderer.write(
            networks.blacklist_v4,
            networks.whitelist_v4,
            allowed_ips=self.allowed_ips,
            blocked_ips=self.blocked_ips,
        )
        logger.info("Pipeline run complete")
        return networks


def build_nftables_pipeline() -> NftablesPipeline:
    """Assemble the default nftables extraction and rendering pipeline."""
    settings = get_settings()
    allowed_ips = parse_ipv4_networks(settings.allowed_ips)
    blocked_ips = parse_ipv4_networks(settings.blocked_ips)
    country_codes = frozenset(parse_country_codes(settings.country_codes))
    asn_denylist = parse_asn_denylist(settings.asn_denylist)
    asn_allowlist = parse_asn_allowlist(settings.asn_allowlist)
    city_whitelist = parse_city_whitelist(settings.city_whitelist, env_var=Settings.env_name("city_whitelist"))
    ipinfo_provider = IPinfoLiteProvider(IPINFO_DB_FILE, country_codes=country_codes)
    whitelist_jobs = [
        ExtractionJob(
            "city_whitelist",
            IP2RegionXdbProvider(IP2REGION_XDB_FILE, country_codes=country_codes),
            CityWhitelistRule(city_whitelist),
        ),
    ]
    if asn_allowlist:
        whitelist_jobs.append(ExtractionJob("asn_allowlist", ipinfo_provider, ASNWhitelistRule(asn_allowlist)))
    return NftablesPipeline(
        blacklist_job=ExtractionJob(
            NFTABLES_GEOIP_BLACKLIST_V4_NAME,
            ipinfo_provider,
            ASNBlacklistRule(asn_denylist),
        ),
        whitelist_jobs=tuple(whitelist_jobs),
        renderer=NftablesRenderer(TEMPLATE_DIR, NFTABLES_OUTPUT_FILE, NFTABLES_TEMPLATE_NAME),
        allowed_ips=allowed_ips,
        blocked_ips=blocked_ips,
    )
