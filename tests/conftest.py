"""Pytest test configuration and fixtures.

Sets up isolated temporary SQLite databases for each test session or function
so that real application databases are never mutated.
"""

import os
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from app.api.routes import get_current_db_path
from app.config import settings
from app.database import init_db
from app.main import app


@pytest.fixture(scope="function")
def temp_db_path(tmp_path: Path) -> str:
    """Provide a path to a brand new isolated SQLite database in a temporary directory."""
    db_file = str(tmp_path / "test_tickets.db")
    init_db(db_file)
    return db_file


@pytest.fixture(scope="function")
def client(temp_db_path: str) -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient configured with the isolated temporary database."""
    # Override the dependency to use the isolated test database
    app.dependency_overrides[get_current_db_path] = lambda: temp_db_path

    # Point global settings to temp path during this test
    original_db_path = settings.DATABASE_PATH
    settings.DATABASE_PATH = temp_db_path

    with TestClient(app) as test_client:
        yield test_client

    # Clean up overrides
    app.dependency_overrides.clear()
    settings.DATABASE_PATH = original_db_path
