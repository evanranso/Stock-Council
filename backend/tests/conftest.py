import dataclasses

import pytest

from app import cache, db, search


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Every test gets its own empty SQLite file instead of the real one."""
    settings = dataclasses.replace(cache.get_settings(), cache_path=str(tmp_path / "test.db"))
    monkeypatch.setattr(cache, "get_settings", lambda: settings)
    monkeypatch.setattr(db, "get_settings", lambda: settings)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return settings


@pytest.fixture(autouse=True)
def no_search_download(monkeypatch):
    """The server warms the company list on startup; tests never download it."""

    async def empty():
        return []

    monkeypatch.setattr(search, "ensure_index", empty)
