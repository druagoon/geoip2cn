"""ASN whitelist matching rules."""

from __future__ import annotations

from models import (
    GeoRecord,
    ProviderCapability,
)
from utils import split_comma


def parse_asn_allowlist(value: str) -> tuple[str, ...]:
    """Parse a comma-separated ASN allowlist into normalized values."""
    return tuple(split_comma(value, callback=str.upper))


class ASNWhitelistRule:
    """Match allowlisted ASNs regardless of country."""

    required_capabilities = frozenset({ProviderCapability.ASN})

    def __init__(self, allowlist: tuple[str, ...] = ()) -> None:
        """Store the allowlist as a normalized uppercase set."""
        self.allowlist = frozenset(item.upper() for item in allowlist)

    def match(self, record: GeoRecord) -> bool:
        """Return whether a record belongs to an allowlisted ASN."""
        return record.asn.upper() in self.allowlist
