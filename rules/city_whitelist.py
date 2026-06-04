"""City whitelist matching rules."""

from __future__ import annotations

from dataclasses import dataclass

from models import (
    GeoRecord,
    ProviderCapability,
)
from settings import Settings
from utils import split_comma


@dataclass(frozen=True)
class Region:
    """Normalized region tuple used by the city whitelist rule."""

    country: str
    province: str
    city: str

    @classmethod
    def normalized(cls, country: str, province: str, city: str) -> Region:
        """Build a region with lowercase country, province, and city names."""
        return cls(
            country=country.lower(),
            province=province.lower(),
            city=city.lower(),
        )


def parse_city_whitelist(value: str, *, env_var: str = Settings.env_name("city_whitelist")) -> tuple[Region, ...]:
    """Parse and validate the configured city whitelist string."""

    def parse_region(region: str) -> Region:
        parts = list(filter(None, (part.strip() for part in region.split("|"))))
        if len(parts) != 3:
            raise ValueError(f"City whitelist parse error: env_var={env_var} region={region} reason=invalid_format")
        return Region.normalized(*parts)

    whitelist = tuple(split_comma(value, callback=parse_region))

    if not whitelist:
        raise ValueError(f"Configuration error: env_var={env_var} reason=empty")

    return whitelist


class CityWhitelistRule:
    """Match records against a target region allowlist."""

    required_capabilities = frozenset(
        {
            ProviderCapability.COUNTRY,
            ProviderCapability.PROVINCE,
            ProviderCapability.CITY,
        }
    )

    def __init__(self, whitelist: list[Region] | tuple[Region, ...]) -> None:
        """Store the whitelist as normalized region tuples."""
        if not whitelist:
            raise ValueError("City whitelist configuration error: reason=empty")

        self.whitelist = {(item.country, item.province, item.city) for item in whitelist}

    def match(self, record: GeoRecord) -> bool:
        """Return whether a record belongs to one of the whitelisted regions."""
        return (
            record.country_code.lower(),
            record.province.lower(),
            record.city.lower(),
        ) in self.whitelist
