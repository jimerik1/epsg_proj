"""Pytest fixtures for GIGS compliance tests."""
from pathlib import Path
from typing import Iterator

import pytest
import requests

API_ROOT = "http://localhost:3001"


def _resolve_dataset_root() -> Path:
    env_root = Path("docs/standards/GIGS_Test_Dataset_v2.1")
    if env_root.exists():
        return env_root
    raise RuntimeError("GIGS dataset not found. Update path in tests/gigs/conftest.py.")


@pytest.fixture(scope="session")
def gigs_dataset_root() -> Path:
    """Path to the extracted GIGS test dataset."""
    return _resolve_dataset_root()


@pytest.fixture(scope="session")
def api_session() -> Iterator[requests.Session]:
    """Session for calling the FastAPI service during GIGS tests."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    yield session
    session.close()


@pytest.fixture(scope="session")
def api_root() -> str:
    """Base URL for the CRS Transformation API."""
    return API_ROOT
