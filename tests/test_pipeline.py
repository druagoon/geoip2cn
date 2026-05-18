from __future__ import annotations

import ipaddress
from collections.abc import (
    Iterable,
    Iterator,
    Set,
)
from pathlib import Path
from typing import cast

import pytest

from models import (
    GeoRecord,
    ProviderCapability,
    RecordRule,
)
from providers.base import GeoIPProvider
from providers.ip2region_xdb import IP2RegionXdbProvider
from renderers.nftables import NftablesRenderer
from rules.asn_blacklist import ASNBlacklistRule
from rules.city_whitelist import CityWhitelistRule
from services.pipeline import (
    ExtractionJob,
    NftablesPipeline,
    build_nftables_pipeline,
)
from settings import (
    NFTABLES_GEOIP_BLACKLIST_V4_NAME,
    NFTABLES_GEOIP_WHITELIST_V4_NAME,
)


class StubProvider(GeoIPProvider):
    capabilities = frozenset({ProviderCapability.COUNTRY})

    def __init__(self, name: str) -> None:
        self.name = name

    def ensure_database(self) -> None:
        return None

    def iter_records(self) -> Iterator[GeoRecord]:
        return iter(())


class StubRule:
    required_capabilities: frozenset[ProviderCapability] = frozenset()

    def match(self, record: GeoRecord) -> bool:
        del record
        return False


class StubRenderer(NftablesRenderer):
    def __init__(self) -> None:
        self.calls: list[tuple[set[ipaddress.IPv4Network], set[ipaddress.IPv4Network], Set[ipaddress.IPv4Network]]] = []

    def write(
        self,
        blacklist_v4: Iterable[ipaddress.IPv4Network],
        whitelist_v4: Iterable[ipaddress.IPv4Network],
        allowed_ips: Iterable[ipaddress.IPv4Network] = frozenset(),
        blocked_ips: Iterable[ipaddress.IPv4Network] = frozenset(),
    ) -> None:
        del blocked_ips
        self.calls.append((set(blacklist_v4), set(whitelist_v4), set(allowed_ips)))


def test_nftables_renderer_write_creates_output_directory(tmp_path: Path) -> None:
    template_dir = tmp_path / "templates"
    output_file = tmp_path / "outputs" / "nested" / "nftables.conf"
    template_dir.mkdir(parents=True)
    (template_dir / "nftables.conf").write_text(
        "blacklist={{ geoip_blacklist_v4_networks|join(',') }}\n"
        "whitelist={{ geoip_whitelist_v4_networks|join(',') }}\n",
        encoding="utf-8",
    )

    renderer = NftablesRenderer(template_dir, output_file)

    renderer.write(
        {ipaddress.IPv4Network("1.1.1.0/24")},
        {ipaddress.IPv4Network("2.2.2.0/24")},
    )

    assert output_file.exists()
    assert output_file.read_text(encoding="utf-8") == "blacklist=1.1.1.0/24\nwhitelist=2.2.2.0/24\n"


def test_nftables_pipeline_run_passes_extracted_networks_to_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    blacklist_networks = {ipaddress.IPv4Network("1.1.1.0/24")}
    whitelist_networks = {ipaddress.IPv4Network("2.2.2.0/24")}
    allowed_networks = {ipaddress.IPv4Network("3.3.3.0/24")}
    renderer = StubRenderer()

    jobs: dict[str, set[ipaddress.IPv4Network]] = {
        NFTABLES_GEOIP_BLACKLIST_V4_NAME: blacklist_networks,
        NFTABLES_GEOIP_WHITELIST_V4_NAME: whitelist_networks,
    }

    def fake_extract_ipv4_networks(provider: GeoIPProvider, rule: RecordRule) -> set[ipaddress.IPv4Network]:
        del rule
        return jobs[provider.name]

    monkeypatch.setattr("services.pipeline.extract_ipv4_networks", fake_extract_ipv4_networks)

    pipeline = NftablesPipeline(
        blacklist_job=ExtractionJob(
            NFTABLES_GEOIP_BLACKLIST_V4_NAME,
            StubProvider(NFTABLES_GEOIP_BLACKLIST_V4_NAME),
            cast(RecordRule, StubRule()),
        ),
        whitelist_job=ExtractionJob(
            NFTABLES_GEOIP_WHITELIST_V4_NAME,
            StubProvider(NFTABLES_GEOIP_WHITELIST_V4_NAME),
            cast(RecordRule, StubRule()),
        ),
        renderer=renderer,
        allowed_ips=allowed_networks,
    )

    networks = pipeline.run()

    assert networks.blacklist_v4 == blacklist_networks
    assert networks.whitelist_v4 == whitelist_networks
    assert renderer.calls == [(blacklist_networks, whitelist_networks, allowed_networks)]


def test_build_nftables_pipeline_loads_city_whitelist_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_IPS", "")
    monkeypatch.setenv("ASN_DENYLIST", "AS4134, AS4811")
    monkeypatch.setenv("CITY_WHITELIST", "CN|上海|上海市, CN|江苏省|南京市")

    pipeline = build_nftables_pipeline()

    assert isinstance(pipeline.blacklist_job.rule, ASNBlacklistRule)
    assert isinstance(pipeline.whitelist_job.rule, CityWhitelistRule)
    assert isinstance(pipeline.whitelist_job.provider, IP2RegionXdbProvider)
    assert pipeline.blacklist_job.name == NFTABLES_GEOIP_BLACKLIST_V4_NAME
    assert pipeline.whitelist_job.name == NFTABLES_GEOIP_WHITELIST_V4_NAME
    assert pipeline.blacklist_job.rule.denylist == {"AS4134", "AS4811"}
    assert pipeline.whitelist_job.rule.whitelist == {
        ("cn", "上海", "上海市"),
        ("cn", "江苏省", "南京市"),
    }


def test_build_nftables_pipeline_allows_empty_asn_denylist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_IPS", "")
    monkeypatch.setenv("ASN_DENYLIST", "")
    monkeypatch.setenv("CITY_WHITELIST", "CN|上海|上海市")

    pipeline = build_nftables_pipeline()

    assert isinstance(pipeline.blacklist_job.rule, ASNBlacklistRule)
    assert pipeline.blacklist_job.rule.denylist == set()


def test_build_nftables_pipeline_requires_non_empty_city_whitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_IPS", "")
    monkeypatch.delenv("CITY_WHITELIST", raising=False)

    with pytest.raises(ValueError, match=r"Configuration error: env_var=city_whitelist reason=empty"):
        build_nftables_pipeline()
