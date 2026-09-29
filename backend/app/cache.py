"""Tiny SQLite cache so repeat lookups of the same ticker don't re-run 16 model calls."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from .config import get_settings


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(get_settings().cache_path)
    conn.execute("CREATE TABLE IF NOT EXISTS runs (ticker TEXT PRIMARY KEY, created REAL, events TEXT)")
    return conn


def get_run(ticker: str) -> list[dict[str, Any]] | None:
    ttl = get_settings().cache_ttl_hours * 3600
    with _conn() as conn:
        row = conn.execute("SELECT created, events FROM runs WHERE ticker = ?", (ticker,)).fetchone()
    if row and time.time() - row[0] < ttl:
        return json.loads(row[1])
    return None


def save_run(ticker: str, events: list[dict[str, Any]]) -> None:
    with _conn() as conn:
        conn.execute("REPLACE INTO runs VALUES (?, ?, ?)", (ticker, time.time(), json.dumps(events)))
