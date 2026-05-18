"""Shared domain models for GeoIP extraction."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


@dataclass(frozen=True)
class GeoRecord:
    network: ipaddress.IPv4Network | ipaddress.IPv6Network
    country_code: str = ""
    asn: str = ""
    province: str = ""
    city: str = ""


class ProviderCapability(StrEnum):
    COUNTRY = "country"
    ASN = "asn"
    PROVINCE = "province"
    CITY = "city"


class RecordRule(Protocol):
    required_capabilities: frozenset[ProviderCapability]

    def match(self, record: GeoRecord) -> bool: ...
