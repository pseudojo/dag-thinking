"""Shared pytest fixtures for dag-thinking tests."""

import pytest

from src.db import init_db


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path
