"""Runtime settings for the GeoIP extraction pipeline."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import (
    BaseSettings,
)

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "db"
OUTPUT_DIR = BASE_DIR / "outputs"
TEMPLATE_DIR = BASE_DIR / "templates"

IPINFO_DB_FILE = DB_DIR / "ipinfo_lite.mmdb"
MAXMIND_CITY_DB_FILE = DB_DIR / "GeoLite2-City.mmdb"
IP2REGION_XDB_FILE = DB_DIR / "ip2region_v4.xdb"
NFTABLES_OUTPUT_FILE = OUTPUT_DIR / "nftables.conf"
NFTABLES_TEMPLATE_NAME = "nftables.conf"
NFTABLES_GEOIP_BLACKLIST_V4_NAME = "geoip_blacklist_v4"
NFTABLES_GEOIP_WHITELIST_V4_NAME = "geoip_whitelist_v4"

REQUEST_TIMEOUT_SECONDS = 300
DEFAULT_LOG_LEVEL = "INFO"

IPINFO_LITE_DOWNLOAD_URL = "https://ipinfo.io/data/ipinfo_lite.mmdb?token={token}"
IP2REGION_XDB_DOWNLOAD_URL = "https://raw.githubusercontent.com/lionsoul2014/ip2region/master/data/ip2region_v4.xdb"
MAXMIND_RELEASE_API_URL = "https://api.github.com/repos/P3TERX/GeoLite.mmdb/releases/latest"
MAXMIND_CITY_ASSET_NAME = "GeoLite2-City.mmdb"


class Settings(BaseSettings):
    """Environment-backed settings for the extraction pipeline."""

    allowed_ips: str = ""
    blocked_ips: str = ""
    asn_denylist: str = ""
    city_whitelist: str = ""
    ipinfo_token: str | None = None
    log_level: str = DEFAULT_LOG_LEVEL

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> str:
        """Normalize the configured log level to an uppercase string."""
        if value is None:
            return DEFAULT_LOG_LEVEL
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or DEFAULT_LOG_LEVEL
        raise TypeError("Configuration error: env_var=log_level reason=invalid_type")

    @classmethod
    def env_name(cls, field_name: str) -> str:
        """Return the environment variable name for a settings field."""
        if field_name in cls.model_fields:
            return field_name
        raise ValueError(f"Settings field error: field={field_name} reason=missing_field")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached runtime settings instance."""
    return Settings()
