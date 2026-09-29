import dataclasses

import pytest

from app import cache


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Every test gets its own empty SQLite file instead of the real one."""
    settings = dataclasses.replace(cache.get_settings(), cache_path=str(tmp_path / "test.db"))
    monkeypatch.setattr(cache, "get_settings", lambda: settings)
    return settings
