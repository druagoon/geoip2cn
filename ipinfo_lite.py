"""Extracts IP networks from the GeoIP database."""

import datetime
import ipaddress
import logging
import logging.config
import os
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import (
    dataclass,
    fields,
)
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    Optional,
    TypeAlias,
    TypeVar,
    overload,
)

import maxminddb
import requests

# Define the base directory of the script
BASE_DIR = Path(__file__).resolve().parent

# Define the directory for the IP database
DB_DIR = BASE_DIR / "db"

# Define the file path for the IP database
DB_FILE = DB_DIR / "ipinfo_lite.mmdb"

# Define the directory for data files
DATA_DIR = BASE_DIR / "data"

# Define the directory for log files
LOG_DIR = BASE_DIR / "logs"

# Define the db record log file path
DB_LOG_FILE = LOG_DIR / "db.log"

# Define logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] %(levelname)s: %(message)s",
            "class": "ipinfo_lite.RFC3339Formatter",
        },
        "raw": {
            "format": "%(message)s",
            "class": "ipinfo_lite.RFC3339Formatter",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "standard",
        },
        "db": {
            "class": "logging.FileHandler",
            "level": "INFO",
            "formatter": "raw",
            "filename": DB_LOG_FILE,
            "mode": "w",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "main": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "db": {
            "handlers": ["db"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

logger = logging.getLogger("main")
db_logger = logging.getLogger("db")


@dataclass
class AsDomain:
    domain: str
    is_filter: bool = True
    use_as_name: bool = False


# Define the AS Domains
AS_DOMAINS = (
    AsDomain("10086.cn"),
    AsDomain("chinamobile.com"),
    AsDomain("chinaunicom.cn"),
    AsDomain("189.cn"),
    AsDomain("chinatelecom.cn", use_as_name=True),
    AsDomain("chinatelecom.com.cn", use_as_name=True),
    AsDomain("360.cn"),
    AsDomain("360.net"),
    AsDomain("baidu.com"),
    AsDomain("qq.com"),
    AsDomain("tencent.com"),
    AsDomain("huawei.com"),
    AsDomain("huaweicloud.com"),
    AsDomain("alibabacloud.com"),
    AsDomain("alibabagroup.com"),
    AsDomain("bytedance.com"),
    AsDomain("volcengine.com"),
)


# Mapping of AS domains to AsDomain objects
AS_DOMAIN_KV = {v.domain: v for v in AS_DOMAINS}

# Define the AS Name keywords and the regex pattern
AS_NAME_KEYWORDS = [
    "Beijing",
    "Tianjin",
    "Hebei",
    "Jiangsu",
    "Nanjing",
    "Sichuan",
    "SHAANXI",
    "Xiamen",
    "Shandong",
    "Qingdao",
    "Jinan",
    "Guizhou",
    "Guangdong",
    "NINGXIA",
    "Yunnan",
    "Cloud Computing Corporation",
]
REGEX_AS_NAME = re.compile(
    rf"\b{'|'.join(re.escape(x) for x in AS_NAME_KEYWORDS)}\b",
    re.I,
)


@dataclass
class IPInfo:
    continent: str = ""
    continent_code: str = ""
    country: str = ""
    country_code: str = ""
    as_domain: str = ""
    as_name: str = ""
    asn: str = ""

    @classmethod
    def from_dict(cls, data: dict):
        names = {f.name for f in fields(cls)}
        items = {k: v for k, v in data.items() if k in names}
        return cls(**items)

    def is_cn(self) -> bool:
        """Check if the country is China."""
        return self.country_code == "CN"

    def is_filter_domain(self) -> bool:
        """Check if the AS domain is in the filter list."""
        if self.as_domain:
            if (obj := AS_DOMAIN_KV.get(self.as_domain)) and obj.is_filter:
                if obj.use_as_name:
                    return bool(REGEX_AS_NAME.search(self.as_name))
                return True
        return False


# Define type aliases for IP networks
T = TypeVar("T")
IPNetwork: TypeAlias = ipaddress.IPv4Network | ipaddress.IPv6Network


@overload
def dotv(data: Dict, key: Any) -> Optional[Any]: ...
@overload
def dotv(data: Dict, key: Any, default: T) -> T: ...
def dotv(data: Dict, key: Any, default: Any = None) -> Any:
    """Return the value of key which contains dot.

    >>> data = {'a': {'b': {'c': 'foo'}}}
    >>> dotv(data, 'a.b')
    {'c': 'foo'}
    >>> dotv(data, 'a.b.c')
    'foo'
    """
    part = key.split(".")
    last = part.pop()
    for v in part:
        data = data.get(v) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict but got {type(data).__name__}")
    return data.get(last, default)


class RFC3339Formatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.datetime.fromtimestamp(record.created, datetime.timezone.utc).astimezone()
        return dt.isoformat(timespec="seconds")


def init_logging():
    """Initialize logging configuration."""
    if not LOG_DIR.exists():
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(LOGGING)


def clean():
    """Clean up the data directory."""
    logger.info(f"Cleaning up {DATA_DIR}...")
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)


def ensure_file_dir_exists(file_path: Path) -> None:
    """Ensure the directory for the file exists."""
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)


def download_ip_database(db_file: Path) -> None:
    """Download the IP database from network."""
    token = os.getenv("IPINFO_TOKEN")
    if not token:
        raise ValueError("IPINFO_TOKEN environment variable is not set.")

    logger.info(f"DB file: {db_file}")
    if not db_file.parent.exists():
        db_file.parent.mkdir(parents=True, exist_ok=True)
    if db_file.exists():
        with maxminddb.open_database(db_file) as reader:
            metadata = reader.metadata()
            dt = datetime.datetime.fromtimestamp(metadata.build_epoch, datetime.timezone.utc)
            today = datetime.datetime.combine(datetime.date.today(), datetime.time.min, datetime.timezone.utc)
            logger.info("Database file already exists. Checking if it is up to date...")
            logger.info(f"Build time: {dt.isoformat()}")
            if dt >= today:
                return

    logger.info("Downloading IP database...")
    download_url = f"https://ipinfo.io/data/ipinfo_lite.mmdb?token={token}"
    with requests.get(download_url, stream=True) as response:
        response.raise_for_status()
        with open(db_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def save_zone_file(zone_file: Path, networks: Iterable[IPNetwork]) -> None:
    """Save the IP networks to a zone file."""
    count = 0
    ensure_file_dir_exists(zone_file)
    with open(zone_file, "w") as f:
        for net in networks:
            f.write(f"{net}\n")
            count += 1
    logger.info(f"Saved {count:<5} networks to {zone_file}")


def extract_ip_networks(db_file: Path) -> None:
    logger.info(f"Extracting IP networks from {db_file}")
    countries = defaultdict(lambda: defaultdict(set))
    domains = defaultdict(lambda: defaultdict(set))
    with maxminddb.open_database(db_file) as reader:
        for network, record in reader:
            try:
                ip = IPInfo.from_dict(record)
                if ip.is_cn():
                    db_logger.info(f"{network=} {record=}")
                    net = ipaddress.ip_network(network)
                    if not isinstance(net, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
                        continue
                    ipv = f"ipv{net.version}"
                    countries[ip.country_code.lower()][ipv].add(net)
                    if ip.is_filter_domain():
                        domains[ip.as_domain.lower()][ipv].add(net)
            except Exception:
                continue

        ip_versions = ["ipv4", "ipv6"]
        for version in ip_versions:
            for c, ip_networks in countries.items():
                if version in ip_networks:
                    zone_file = DATA_DIR / "countries" / version / f"{c}.zone"
                    save_zone_file(zone_file, ipaddress.collapse_addresses(ip_networks[version]))

            domain_aggregated_file = DATA_DIR / "domains" / version / "aggregated.zone"
            ensure_file_dir_exists(domain_aggregated_file)
            with open(domain_aggregated_file, "w") as af:
                for d, ip_networks in domains.items():
                    if version in ip_networks:
                        zone_file = DATA_DIR / "domains" / version / f"{d}.zone"
                        save_zone_file(zone_file, ipaddress.collapse_addresses(ip_networks[version]))
                        shutil.copyfileobj(open(zone_file, "r"), af)


def main():
    init_logging()
    clean()
    download_ip_database(DB_FILE)
    extract_ip_networks(DB_FILE)


if __name__ == "__main__":
    main()
