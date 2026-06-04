"""ASN blacklist matching rules."""

from __future__ import annotations

from models import (
    GeoRecord,
    ProviderCapability,
)
from utils import split_comma


def parse_asn_denylist(value: str) -> tuple[str, ...]:
    """Parse a comma-separated ASN denylist into normalized values."""
    return tuple(split_comma(value, callback=str.upper))


class ASNBlacklistRule:
    """Match denylisted ASNs."""

    required_capabilities = frozenset({ProviderCapability.COUNTRY, ProviderCapability.ASN})

    def __init__(self, denylist: tuple[str, ...] = ()) -> None:
        """Store the denylist as a normalized uppercase set."""
        self.denylist = {item.upper() for item in denylist}

    def match(self, record: GeoRecord) -> bool:
        """Return whether a Chinese record belongs to a denylisted ASN."""
        return record.country_code.upper() == "CN" and record.asn.upper() in self.denylist
