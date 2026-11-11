from __future__ import annotations

import ipaddress
from collections.abc import (
    Iterable,
    Iterator,
    Set as AbstractSet,
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
from providers.ipinfo_lite import IPinfoLiteProvider
from renderers.nftables import NftablesRenderer
from rules.asn_blacklist import ASNBlacklistRule
from rules.asn_whitelist import ASNWhitelistRule
from rules.city_whitelist import CityWhitelistRule
from services.extractors import extract_ipv4_networks_by_rule
from services.pipeline import (
    ExtractionJob,
    NftablesPipeline,
    build_nftables_pipeline,
)
from settings import (
    NFTABLES_GEOIP_BLACKLIST_V4_NAME,
    NFTABLES_GEOIP_WHITELIST_V4_NAME,
    TEMPLATE_DIR,
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
        self.calls: list[
            tuple[
                set[ipaddress.IPv4Network],
                set[ipaddress.IPv4Network],
                AbstractSet[ipaddress.IPv4Network],
                AbstractSet[ipaddress.IPv4Network],
            ]
        ] = []

    def write(
        self,
        blacklist_v4: Iterable[ipaddress.IPv4Network],
        whitelist_v4: Iterable[ipaddress.IPv4Network],
        allowed_ips: Iterable[ipaddress.IPv4Network] = frozenset(),
        blocked_ips: Iterable[ipaddress.IPv4Network] = frozenset(),
    ) -> None:
        self.calls.append((set(blacklist_v4), set(whitelist_v4), set(allowed_ips), set(blocked_ips)))


def test_grouped_extraction_validates_all_rules_before_database_access(monkeypatch: pytest.MonkeyPatch) -> None:
    database_checks: list[str] = []

    def ensure_database(provider: StubProvider) -> None:
        database_checks.append(provider.name)

    monkeypatch.setattr(StubProvider, "ensure_database", ensure_database)
    provider = StubProvider("country_only")

    with pytest.raises(ValueError, match=r"provider=country_only missing_capabilities=asn"):
        extract_ipv4_networks_by_rule(provider, (StubRule(), ASNWhitelistRule(("AS13335",))))

    assert database_checks == []


def test_nftables_renderer_write_creates_output_directory(tmp_path: Path) -> None:
    template_dir = tmp_path / "templates"
    output_file = tmp_path / "outputs" / "nested" / "nftables.conf"
    template_dir.mkdir(parents=True)
    (template_dir / "nftables.conf").write_text(
        "blacklist={{ geoip_blacklist_v4_networks|join(',') }}\n"
        "whitelist={{ geoip_whitelist_v4_networks|join(',') }}\n"
        "allowed={{ allowed_ips|join(',') }}\n"
        "blocked={{ blocked_ips|join(',') }}\n",
        encoding="utf-8",
    )

    renderer = NftablesRenderer(template_dir, output_file)

    renderer.write(
        {ipaddress.IPv4Network("1.1.1.0/24")},
        {ipaddress.IPv4Network("2.2.2.0/24")},
        {ipaddress.IPv4Network("3.3.3.0/24")},
        {ipaddress.IPv4Network("4.4.4.0/24")},
    )

    assert output_file.exists()
    assert output_file.read_text(encoding="utf-8") == (
        "blacklist=1.1.1.0/24\nwhitelist=2.2.2.0/24\nallowed=3.3.3.0/24\nblocked=4.4.4.0/24\n"
    )


def test_nftables_pipeline_run_passes_extracted_networks_to_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    blacklist_networks = {ipaddress.IPv4Network("1.1.1.0/24")}
    whitelist_networks = {ipaddress.IPv4Network("2.2.2.0/24")}
    allowed_networks = {ipaddress.IPv4Network("3.3.3.0/24")}
    blocked_networks = {ipaddress.IPv4Network("4.4.4.0/24")}
    renderer = StubRenderer()

    jobs: dict[str, set[ipaddress.IPv4Network]] = {
        NFTABLES_GEOIP_BLACKLIST_V4_NAME: blacklist_networks,
        NFTABLES_GEOIP_WHITELIST_V4_NAME: whitelist_networks,
    }

    def fake_extract_ipv4_networks_by_rule(
        provider: GeoIPProvider, rules: tuple[RecordRule, ...]
    ) -> tuple[set[ipaddress.IPv4Network], ...]:
        assert len(rules) == 1
        return (jobs[provider.name],)

    monkeypatch.setattr("services.pipeline.extract_ipv4_networks_by_rule", fake_extract_ipv4_networks_by_rule)

    pipeline = NftablesPipeline(
        blacklist_job=ExtractionJob(
            NFTABLES_GEOIP_BLACKLIST_V4_NAME,
            StubProvider(NFTABLES_GEOIP_BLACKLIST_V4_NAME),
            cast(RecordRule, StubRule()),
        ),
        whitelist_jobs=(
            ExtractionJob(
                NFTABLES_GEOIP_WHITELIST_V4_NAME,
                StubProvider(NFTABLES_GEOIP_WHITELIST_V4_NAME),
                cast(RecordRule, StubRule()),
            ),
        ),
        renderer=renderer,
        allowed_ips=allowed_networks,
        blocked_ips=blocked_networks,
    )

    networks = pipeline.run()

    assert networks.blacklist_v4 == blacklist_networks
    assert networks.whitelist_v4 == whitelist_networks
    assert renderer.calls == [(blacklist_networks, whitelist_networks, allowed_networks, blocked_networks)]


def test_build_nftables_pipeline_loads_city_whitelist_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_IPS", "3.3.3.0/24,\n# trusted range\r\n 6.6.6.0/24")
    monkeypatch.setenv("BLOCKED_IPS", "4.4.4.0/24,\r# blocked range\r5.5.5.0/24")
    monkeypatch.setenv("COUNTRY_CODES", " cn, us ")
    monkeypatch.setenv("ASN_DENYLIST", "AS4134,\n  # ignored ASN\r\nAS4811")
    monkeypatch.setenv("ASN_ALLOWLIST", "as13335,\n # ignored ASN\r\n AS15169")
    monkeypatch.setenv("CITY_WHITELIST", "CN|上海|上海市,\r\n# ignored region\n CN|江苏省|南京市")

    pipeline = build_nftables_pipeline()

    assert len(pipeline.whitelist_jobs) == 2
    asn_job = pipeline.whitelist_jobs[1]
    assert asn_job.name == "asn_allowlist"
    assert isinstance(asn_job.provider, IPinfoLiteProvider)
    assert asn_job.provider.country_codes == frozenset({"CN", "US"})
    assert isinstance(asn_job.rule, ASNWhitelistRule)
    assert asn_job.rule.allowlist == {"AS13335", "AS15169"}
    assert isinstance(pipeline.blacklist_job.rule, ASNBlacklistRule)
    assert isinstance(pipeline.whitelist_jobs[0].rule, CityWhitelistRule)
    assert isinstance(pipeline.whitelist_jobs[0].provider, IP2RegionXdbProvider)
    assert pipeline.blacklist_job.name == NFTABLES_GEOIP_BLACKLIST_V4_NAME
    assert pipeline.whitelist_jobs[0].name == "city_whitelist"
    assert pipeline.allowed_ips == {ipaddress.IPv4Network("3.3.3.0/24"), ipaddress.IPv4Network("6.6.6.0/24")}
    assert pipeline.blocked_ips == {ipaddress.IPv4Network("4.4.4.0/24"), ipaddress.IPv4Network("5.5.5.0/24")}
    assert pipeline.blacklist_job.provider.country_codes == frozenset({"CN", "US"})
    assert pipeline.whitelist_jobs[0].provider.country_codes == frozenset({"CN", "US"})
    assert pipeline.blacklist_job.rule.denylist == {"AS4134", "AS4811"}
    assert pipeline.whitelist_jobs[0].rule.whitelist == {
        ("cn", "上海", "上海市"),
        ("cn", "江苏省", "南京市"),
    }


def test_build_nftables_pipeline_allows_empty_asn_denylist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_IPS", "")
    monkeypatch.setenv("BLOCKED_IPS", "")
    monkeypatch.setenv("COUNTRY_CODES", "")
    monkeypatch.setenv("ASN_DENYLIST", "")
    monkeypatch.setenv("ASN_ALLOWLIST", "")
    monkeypatch.setenv("CITY_WHITELIST", "CN|上海|上海市")

    pipeline = build_nftables_pipeline()

    assert isinstance(pipeline.blacklist_job.rule, ASNBlacklistRule)
    assert len(pipeline.whitelist_jobs) == 1
    assert pipeline.blacklist_job.rule.denylist == set()
    assert pipeline.blacklist_job.provider.country_codes == frozenset()


def test_build_nftables_pipeline_requires_non_empty_city_whitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASN_ALLOWLIST", "AS13335")
    monkeypatch.setenv("ALLOWED_IPS", "")
    monkeypatch.setenv("BLOCKED_IPS", "")
    monkeypatch.setenv("CITY_WHITELIST", "  # ignored region\r\n\n\t# another ignored region")

    with pytest.raises(ValueError, match=r"Configuration error: env_var=city_whitelist reason=empty"):
        build_nftables_pipeline()


@pytest.mark.parametrize(
    ("country_codes", "expected_whitelist"),
    [
        ("", {"192.0.2.0/25", "192.0.2.128/25", "198.51.100.0/24"}),
        ("US", {"198.51.100.0/24"}),
        ("CN", {"192.0.2.0/25", "192.0.2.128/25"}),
    ],
)
def test_pipeline_merges_ipinfo_asns_and_cities_into_rendered_whitelist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, country_codes: str, expected_whitelist: set[str]
) -> None:
    monkeypatch.setenv("ALLOWED_IPS", "")
    monkeypatch.setenv("BLOCKED_IPS", "")
    monkeypatch.setenv("ASN_ALLOWLIST", "as13335")
    monkeypatch.setenv("ASN_DENYLIST", "AS13335")
    monkeypatch.setenv("CITY_WHITELIST", "CN|上海|上海市")
    monkeypatch.setenv("COUNTRY_CODES", country_codes)
    ipinfo_records = (
        GeoRecord(ipaddress.ip_network("192.0.2.0/25"), country_code="CN", asn="AS13335"),
        GeoRecord(ipaddress.ip_network("198.51.100.0/24"), country_code="US", asn="AS13335"),
        GeoRecord(ipaddress.ip_network("203.0.113.0/24"), country_code="CN", asn="AS15169"),
        GeoRecord(ipaddress.ip_network("2001:db8::/32"), country_code="US", asn="AS13335"),
    )
    city_records = (
        GeoRecord(ipaddress.ip_network("192.0.2.0/25"), country_code="CN", province="上海", city="上海市"),
        GeoRecord(ipaddress.ip_network("192.0.2.128/25"), country_code="CN", province="上海", city="上海市"),
        GeoRecord(ipaddress.ip_network("203.0.113.0/24"), country_code="CN", province="江苏省", city="南京市"),
    )

    database_checks: list[str] = []
    database_reads: list[str] = []

    def ipinfo_iter_records(provider: IPinfoLiteProvider) -> Iterator[GeoRecord]:
        database_reads.append(provider.name)
        return (record for record in ipinfo_records if provider.supports_country_code(record.country_code))

    def city_iter_records(provider: IP2RegionXdbProvider) -> Iterator[GeoRecord]:
        database_reads.append(provider.name)
        return (record for record in city_records if provider.supports_country_code(record.country_code))

    def ensure_database(provider: GeoIPProvider) -> None:
        database_checks.append(provider.name)

    monkeypatch.setattr(IPinfoLiteProvider, "ensure_database", ensure_database)
    monkeypatch.setattr(IP2RegionXdbProvider, "ensure_database", ensure_database)
    monkeypatch.setattr(IPinfoLiteProvider, "iter_records", ipinfo_iter_records)
    monkeypatch.setattr(IP2RegionXdbProvider, "iter_records", city_iter_records)
    pipeline = build_nftables_pipeline()
    output_file = tmp_path / "nftables.conf"
    renderer = NftablesRenderer(TEMPLATE_DIR, output_file)
    pipeline = NftablesPipeline(pipeline.blacklist_job, pipeline.whitelist_jobs, renderer)

    networks = pipeline.run()

    assert database_checks == ["ipinfo_lite", "ip2region_xdb"]
    assert database_reads == ["ipinfo_lite", "ip2region_xdb"]
    assert networks.whitelist_v4 == {ipaddress.IPv4Network(value) for value in expected_whitelist}
    assert networks.blacklist_v4 == (set() if country_codes == "US" else {ipaddress.IPv4Network("192.0.2.0/25")})
    rendered = output_file.read_text(encoding="utf-8")
    whitelist_set = rendered.split("set geoip_whitelist_v4 {", 1)[1].split("\n\t}", 1)[0]
    assert ("192.0.2.0/24" in whitelist_set) is (country_codes != "US")
    assert ("198.51.100.0/24" in whitelist_set) is (country_codes != "CN")
    assert "192.0.2.0/25" not in whitelist_set
    assert "203.0.113.0/24" not in whitelist_set
    assert "2001:db8" not in whitelist_set
    assert rendered.index("ip saddr @geoip_blacklist_v4 drop") < rendered.index("ip saddr != @geoip_whitelist_v4 drop")
