from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    from settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
