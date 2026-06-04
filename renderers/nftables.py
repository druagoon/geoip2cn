"""Render nftables.conf from the Jinja2 template."""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Iterable
from pathlib import Path

from jinja2 import (
    Environment,
    FileSystemLoader,
)

from settings import (
    NFTABLES_GEOIP_BLACKLIST_V4_NAME,
    NFTABLES_GEOIP_WHITELIST_V4_NAME,
)

logger = logging.getLogger(__name__)


class NftablesRenderer:
    """Renderer for nftables configuration output."""

    def __init__(self, template_dir: Path, output_file: Path, template_name: str = "nftables.conf") -> None:
        """Initialize the renderer with template and output locations."""
        self.template_dir = template_dir
        self.output_file = output_file
        self.template_name = template_name

    def collapse_networks(self, networks: Iterable[ipaddress.IPv4Network]) -> list[ipaddress.IPv4Network]:
        """Collapse and sort IPv4 networks for stable output."""
        collapsed = ipaddress.collapse_addresses(networks)
        return sorted(collapsed, key=lambda net: (int(net.network_address), net.prefixlen))

    def render(
        self,
        blacklist_v4: Iterable[ipaddress.IPv4Network],
        whitelist_v4: Iterable[ipaddress.IPv4Network],
        allowed_ips: Iterable[ipaddress.IPv4Network] = (),
        blocked_ips: Iterable[ipaddress.IPv4Network] = (),
    ) -> str:
        """Render nftables configuration text from the template."""
        environment = Environment(loader=FileSystemLoader(self.template_dir), trim_blocks=True, lstrip_blocks=True)
        template = environment.get_template(self.template_name)
        return template.render(
            geoip_blacklist_v4_name=NFTABLES_GEOIP_BLACKLIST_V4_NAME,
            geoip_whitelist_v4_name=NFTABLES_GEOIP_WHITELIST_V4_NAME,
            geoip_blacklist_v4_networks=[str(net) for net in self.collapse_networks(blacklist_v4)],
            geoip_whitelist_v4_networks=[str(net) for net in self.collapse_networks(whitelist_v4)],
            allowed_ips=[str(net) for net in self.collapse_networks(allowed_ips)],
            blocked_ips=[str(net) for net in self.collapse_networks(blocked_ips)],
        )

    def write(
        self,
        blacklist_v4: Iterable[ipaddress.IPv4Network],
        whitelist_v4: Iterable[ipaddress.IPv4Network],
        allowed_ips: Iterable[ipaddress.IPv4Network] = (),
        blocked_ips: Iterable[ipaddress.IPv4Network] = (),
    ) -> None:
        """Render and write nftables configuration to disk."""
        rendered_config = self.render(blacklist_v4, whitelist_v4, allowed_ips, blocked_ips)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.output_file.write_text(rendered_config + "\n", encoding="utf-8")
        logger.info("Render output: file=%s template=%s", self.output_file, self.template_dir / self.template_name)
