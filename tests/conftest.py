import os
import sys

# Must set env vars BEFORE any project imports (yandex.py raises RuntimeError)
os.environ.setdefault("YANDEX_DISK_TOKEN", "__test__")
os.environ.setdefault("SCRAPPER_API_KEY", "test-key")

# Add project root and src/ to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def api_headers():
    return {"X-API-Key": "test-key"}
