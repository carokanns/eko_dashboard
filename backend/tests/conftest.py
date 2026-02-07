from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.cache import cache
from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    cache.clear()
