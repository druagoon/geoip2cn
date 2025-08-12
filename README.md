<!-- markdownlint-disable MD033 MD036 -->
<h1>geoip2cn</h1>

Extracts Chinese IP networks and domain-specific IP zones from the IPInfo GeoIP database.

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
- Extracts IPv4 and IPv6 networks for China (`CN` country code).
- Aggregates and saves IP zones by country and by selected AS domains.
- Outputs zone files for use in firewall, routing, or filtering applications.

## Requirements

### System Dependencies

- Python 3.12+

### Python Dependencies

- [maxminddb](https://pypi.org/project/maxminddb/)
- [requests](https://pypi.org/project/requests/)

### Develop Dependencies

- [uv](https://github.com/astral-sh/uv)

### Configuration

- An IPInfo API token (set as environment variable `IPINFO_TOKEN`)

## Usage

1. Initialize environment:

    ```shell
    make init
    ```

2. Install dev dependencies:

   ```shell
   make dev
   ```

3. Set your IPInfo token:

   ```shell
   export IPINFO_TOKEN=your_token_here
   ```

4. Run the script:

   ```shell
   make run
   ```

5. Output zone files will be saved under the `data/` directory:
   - `data/countries/ipv4/cn.zone`
   - `data/countries/ipv6/cn.zone`
   - `data/domains/ipv4/aggregated.zone`
   - `data/domains/ipv6/aggregated.zone`

## Customization

- You can modify the list of filtered AS domains and names in `ipinfo_lite.py` (`AS_DOMAINS`, `AS_NAME_KEYWORDS`).
