"""Abstract base classes for GeoIP providers."""

from __future__ import annotations

from abc import (
    ABC,
    abstractmethod,
)
from collections.abc import Iterator

from models import (
    GeoRecord,
    ProviderCapability,
)


class GeoIPProvider(ABC):
    """Common interface for GeoIP data providers."""

    name: str
    capabilities: frozenset[ProviderCapability]
    country_codes: frozenset[str] = frozenset()

    def __init__(self, country_codes: frozenset[str] = frozenset()) -> None:
        """Store optional country-code allowlist for early record filtering."""
        self.country_codes = country_codes

    @abstractmethod
    def ensure_database(self) -> None:
        """Ensure the backing database is available locally."""

    @abstractmethod
    def iter_records(self) -> Iterator[GeoRecord]:
        """Yield normalized GeoIP records from the provider."""

    def supports(self, capabilities: frozenset[ProviderCapability]) -> bool:
        """Return whether the provider supports all requested capabilities."""
        return capabilities.issubset(self.capabilities)

    def supports_country_code(self, country_code: str) -> bool:
        """Return whether a country code is allowed by the configured filter."""
        return not self.country_codes or country_code.upper() in self.country_codes
