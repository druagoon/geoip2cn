<!-- markdownlint-disable MD033 MD036 -->
<h1>geoip2cn</h1>

Updates `nftables.conf` with IPv4 GeoIP blacklist and whitelist sets, plus explicit allow/block IPv4 sets.

**Table of Contents**

- [Features](#features)
- [Requirements](#requirements)
  - [System Dependencies](#system-dependencies)
  - [Python Dependencies](#python-dependencies)
  - [Develop Dependencies](#develop-dependencies)
  - [Configuration](#configuration)
- [Usage](#usage)
- [Customization](#customization)

## Features

- Downloads the latest IPInfo Lite MaxMindDB database (requires IPINFO_TOKEN).
- Downloads the ip2region XDB database for city-based whitelisting.
- Extracts `geoip_blacklist_v4` via `providers/ipinfo_lite.py` and `rules/asn_blacklist.py`.
- Extracts `geoip_whitelist_v4` via `providers/ip2region_xdb.py` and `rules/city_whitelist.py`.
- Parses optional `allowed_ips`, `blocked_ips`, and `country_codes` settings in `services/pipeline.py` before rendering.
- Assembles the default run through `services/pipeline.py`, which wires extraction jobs to the nftables renderer.
- Renders `templates/nftables.conf` to `outputs/nftables.conf`, including `allowed_ips` and `blocked_ips` nftables sets.
- Uses layered `providers/`, `rules/`, `services/`, and `renderers/` modules so data sources, extraction flow, and output formats can evolve independently.

## Requirements

### System Dependencies

- Python 3.12+

### Python Dependencies

- [maxminddb](https://pypi.org/project/maxminddb/)
- [requests](https://pypi.org/project/requests/)
- [Jinja2](https://pypi.org/project/Jinja2/)

### Develop Dependencies

- [uv](https://github.com/astral-sh/uv)

### Configuration

- An IPInfo API token (set as environment variable `ipinfo_token`; uppercase `IPINFO_TOKEN` also works)
- An allowlist string (set as environment variable `allowed_ips`; uppercase `ALLOWED_IPS` also works) using comma-separated IPv4 CIDR entries such as `203.0.113.4/32,198.51.100.0/24`; this value may be empty
- A blocklist string (set as environment variable `blocked_ips`; uppercase `BLOCKED_IPS` also works) using comma-separated IPv4 CIDR entries such as `1.2.3.4/32,5.6.7.0/24`; this value may be empty
- A country code filter string (set as environment variable `country_codes`; uppercase `COUNTRY_CODES` also works) using comma-separated ISO country codes such as `CN,US`; this value may be empty
- An ASN denylist string (set as environment variable `asn_denylist`; uppercase `ASN_DENYLIST` also works) using the format `AS4134,AS4811,AS56005`; this value may be empty
- A city whitelist string (set as environment variable `city_whitelist`; uppercase `CITY_WHITELIST` also works) using the format `country|province|city,country|province|city`
- An optional log level (set as environment variable `log_level`; uppercase `LOG_LEVEL` also works), for example `INFO` or `DEBUG`
- For ip2region-backed city matching, use the country, province, and city names stored in the database for the target region, for example `CN|上海|上海市`

## Usage

1. Initialize environment:

   ```shell
   make init
   ```

2. Install dev dependencies:

   ```shell
   make dev
   ```

3. Set your runtime environment variables:

   ```shell
   export IPINFO_TOKEN=your_token_here
   export ALLOWED_IPS=203.0.113.4/32
   export ASN_DENYLIST=AS4134,AS4811
   export BLOCKED_IPS=1.2.3.4/32,5.6.7.0/24
   export COUNTRY_CODES=CN,US
   export CITY_WHITELIST='CN|上海|上海市'
   export LOG_LEVEL=INFO
   ```

4. Run the script:

   ```shell
   make run
   ```

   This command will:
   - download or reuse `db/ipinfo_lite.mmdb`
   - download or reuse `db/ip2region_v4.xdb`
   - extract `geoip_blacklist_v4` networks
   - extract `geoip_whitelist_v4` networks
   - parse optional `allowed_ips`, `blocked_ips`, and `country_codes` filters
   - render `templates/nftables.conf` to `outputs/nftables.conf`

## Customization

- You can add explicit source allow rules through the `allowed_ips` environment variable using comma-separated IPv4 CIDR entries such as `203.0.113.4/32`; these entries are rendered into the `allowed_ips` nftables set.
- You can modify the ASN blacklist through the `asn_denylist` environment variable using comma-separated ASN values such as `AS4134,AS4811`; leaving it empty disables ASN blacklist matches.
- You can add explicit source drop rules through the `blocked_ips` environment variable using comma-separated IPv4 CIDR entries such as `1.2.3.4/32,5.6.7.0/24`; these entries are rendered into the `blocked_ips` nftables set.
- You can restrict both providers to specific country codes through the `country_codes` environment variable using comma-separated ISO country codes such as `CN,US`; leaving it empty keeps all countries.
- You can modify the city whitelist targets through the `city_whitelist` environment variable using `country|province|city` entries separated by commas.
- You can adjust runtime logging verbosity through the `log_level` environment variable.
- The city whitelist is matched against ip2region region strings, so country, province, and city values should use the names stored in that database for the target region.
- Runtime paths, URLs, environment variable names, and template/output settings live in `settings.py`.
- Logging initialization and the hardcoded log format live in `logging_config.py`, while the runtime log level is loaded from environment-backed settings.
- Extraction orchestration helpers live in `services/extractors.py`.
- The default application assembly lives in `services/pipeline.py`.
- Provider implementations live under `providers/`, and the nftables output layer lives under `renderers/nftables.py`.
