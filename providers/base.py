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

    @abstractmethod
    def ensure_database(self) -> None:
        """Ensure the backing database is available locally."""

    @abstractmethod
    def iter_records(self) -> Iterator[GeoRecord]:
        """Yield normalized GeoIP records from the provider."""

    def supports(self, capabilities: frozenset[ProviderCapability]) -> bool:
        """Return whether the provider supports all requested capabilities."""
        return capabilities.issubset(self.capabilities)
