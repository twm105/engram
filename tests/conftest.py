"""Shared test fixtures."""

import os
import tempfile

import pytest


@pytest.fixture
def tmp_db_path(tmp_path):
    """Return a temporary database file path."""
    return str(tmp_path / "test.db")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Ensure no env vars leak between tests."""
    monkeypatch.delenv("ENGRAM_DB", raising=False)
    monkeypatch.delenv("ENGRAM_PROJECT", raising=False)
