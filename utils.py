"""Shared utility helpers."""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import time
from collections.abc import (
    Callable,
    Generator,
)
from pathlib import Path
from typing import (
    Any,
    overload,
)

import requests

logger = logging.getLogger(__name__)


def dotv(data: dict[str, Any], key: str, default: Any = None) -> Any:
    """Get a nested dictionary value using dot notation."""
    part = key.split(".")
    last = part.pop()
    for value in part:
        data = data.get(value) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Lookup error: expected_type=dict actual_type={type(data).__name__}")
    return data.get(last, default)


def dotv_str(data: dict[str, Any], key: str, default: str = "") -> str:
    """Get a nested dictionary value as a string using dot notation."""
    value = dotv(data, key, default)
    return value if isinstance(value, str) else default


@overload
def split_comma(value: str, *, strip: bool = True, callback: None = None) -> Generator[str, None, None]: ...


@overload
def split_comma[T](value: str, *, strip: bool = True, callback: Callable[[str], T]) -> Generator[T, None, None]: ...


def split_comma[T](
    value: str, *, strip: bool = True, callback: Callable[[str], T] | None = None
) -> Generator[str | T, None, None]:
    """Yield non-empty comma-separated items, optionally stripped and transformed."""
    for item in value.split(","):
        parsed_item = item.strip() if strip else item
        if not parsed_item:
            continue

        if callback is None:
            yield parsed_item
            continue

        yield callback(parsed_item)


def parse_ipv4_networks(value: str) -> set[ipaddress.IPv4Network]:
    """Parse a comma-separated list of IPv4 CIDRs, trimming whitespace."""
    networks: set[ipaddress.IPv4Network] = set()
    for cidr in split_comma(value):
        network = ipaddress.ip_network(cidr, strict=False)
        if not isinstance(network, ipaddress.IPv4Network):
            raise ValueError(f"Network parse error: expected_type=IPv4Network actual_type={type(network).__name__}")
        networks.add(network)

    return networks


def sha256sum(filename: Path) -> str:
    """Calculate the SHA256 digest for a file."""
    hash_value = hashlib.sha256()
    with filename.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(8192), b""):
            hash_value.update(chunk)
    return hash_value.hexdigest()


def request_json(url: str, timeout: int, *, error_context: str) -> dict[str, Any]:
    """Fetch JSON data without leaking request details in errors."""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code >= 400:
            raise RuntimeError(f"{error_context}: status_code={response.status_code}")
        data = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"{error_context}: request_error={type(exc).__name__}") from None

    if not isinstance(data, dict):
        raise ValueError(f"Response parse error: expected_type=dict actual_type={type(data).__name__}")
    return data


def download_file(url: str, destination: Path, timeout: int, *, error_context: str) -> None:
    """Download a file without leaking request details in errors."""
    started_at = time.perf_counter()
    try:
        with requests.get(url, stream=True, timeout=timeout) as response:
            if response.status_code >= 400:
                raise RuntimeError(f"{error_context}: status_code={response.status_code}")
            with destination.open("wb") as file_obj:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file_obj.write(chunk)
    except requests.RequestException as exc:
        raise RuntimeError(f"{error_context}: request_error={type(exc).__name__}") from None

    elapsed_seconds = time.perf_counter() - started_at
    logger.info("Download result: destination=%s elapsed_seconds=%.3f", destination, elapsed_seconds)
