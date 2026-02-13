from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.core.cache import cache
from app.core.provider_monitor import provider_monitor

os.environ.setdefault("APP_DISABLE_SCHEDULER", "1")

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    cache.clear()
    provider_monitor.clear()
