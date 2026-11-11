from __future__ import annotations

import ipaddress

import pytest

from models import GeoRecord
from rules.asn_whitelist import (
    ASNWhitelistRule,
    parse_asn_allowlist,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(" as13335, as15169 ,, ", ("AS13335", "AS15169")), ("", ())],
)
def test_parse_asn_allowlist(value: str, expected: tuple[str, ...]) -> None:
    assert parse_asn_allowlist(value) == expected


@pytest.mark.parametrize(
    ("allowlist", "asn", "country", "expected"),
    [
        (("as13335",), "AS13335", "CN", True),
        (("AS13335",), "as13335", "US", True),
        (("AS13335",), "AS15169", "CN", False),
        (("AS13335",), "", "CN", False),
        ((), "AS13335", "CN", False),
    ],
)
def test_asn_whitelist_matches_only_configured_asns(
    allowlist: tuple[str, ...], asn: str, country: str, expected: bool
) -> None:
    record = GeoRecord(ipaddress.IPv4Network("192.0.2.0/24"), country_code=country, asn=asn)

    assert ASNWhitelistRule(allowlist).match(record) is expected
