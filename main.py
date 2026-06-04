"""Unified entrypoint for rendering nftables GeoIP IPv4 configuration."""

from __future__ import annotations

from logging_config import setup_logging
from services.pipeline import build_nftables_pipeline


def main() -> None:
    """Run the default GeoIP extraction pipeline."""
    setup_logging()
    build_nftables_pipeline().run()


if __name__ == "__main__":
    main()
