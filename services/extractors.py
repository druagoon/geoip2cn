"""Application services for GeoIP network extraction."""

from __future__ import annotations

import ipaddress
import logging
import time

from models import RecordRule
from providers.base import GeoIPProvider

logger = logging.getLogger(__name__)


def validate_provider_rule_compatibility(provider: GeoIPProvider, rule: RecordRule) -> None:
    """Ensure the provider exposes the capabilities required by the rule."""
    if provider.supports(rule.required_capabilities):
        return

    missing = sorted(set(rule.required_capabilities) - set(provider.capabilities))
    raise ValueError(f"Provider compatibility error: provider={provider.name} missing_capabilities={','.join(missing)}")


def extract_ipv4_networks(provider: GeoIPProvider, rule: RecordRule) -> set[ipaddress.IPv4Network]:
    """Extract IPv4 networks from a provider using a rule."""
    started_at = time.perf_counter()
    validate_provider_rule_compatibility(provider, rule)
    provider.ensure_database()
    networks: set[ipaddress.IPv4Network] = set()
    match_record = rule.match
    add_network = networks.add
    for record in provider.iter_records():
        network = record.network
        if isinstance(network, ipaddress.IPv4Network) and match_record(record):
            add_network(network)

    elapsed_seconds = time.perf_counter() - started_at
    logger.info(
        "Extraction result: provider=%s ipv4_networks=%d elapsed_seconds=%.3f",
        provider.name,
        len(networks),
        elapsed_seconds,
    )
    return networks


def extract_blacklist_networks(provider: GeoIPProvider, rule: RecordRule) -> set[ipaddress.IPv4Network]:
    """Extract blacklist networks using the configured provider and rule."""
    return extract_ipv4_networks(provider, rule)


def extract_whitelist_networks(provider: GeoIPProvider, rule: RecordRule) -> set[ipaddress.IPv4Network]:
    """Extract whitelist networks using the configured provider and rule."""
    return extract_ipv4_networks(provider, rule)
