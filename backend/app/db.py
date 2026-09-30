"""One small database layer for both backends.

Production uses Postgres (Supabase) via DATABASE_URL; local development and
tests use a SQLite file. SQL in this app is written once, in a subset both
understand: `?` placeholders (translated for Postgres), INSERT ... ON CONFLICT,
and CASE instead of dialect-specific functions.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .config import get_settings

_pool = None
_pool_lock = threading.Lock()


def database_url() -> str | None:
    return os.getenv("DATABASE_URL") or None


def is_postgres() -> bool:
    return database_url() is not None


def _pg_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            # prepare_threshold=None: Supabase's pooler (PgBouncer) can't use server-side prepared statements.
            # Timeouts everywhere: a dead or slow connection must fail fast, never hang a request.
            _pool = ConnectionPool(
                database_url(),
                min_size=1,
                max_size=8,
                timeout=15,  # wait at most 15s for a free connection
                max_idle=120,  # close idle connections before Supabase's pooler silently drops them
                check=ConnectionPool.check_connection,  # test each connection before handing it out
                kwargs={
                    "row_factory": dict_row,
                    "prepare_threshold": None,
                    "autocommit": False,
                    "connect_timeout": 10,
                    "keepalives": 1,
                    "keepalives_idle": 30,
                    "keepalives_interval": 10,
                    "keepalives_count": 3,
                    "tcp_user_timeout": 20000,  # ms: a dropped network connection errors instead of hanging
                },
                open=True,
            )
        return _pool


class Conn:
    """Thin wrapper so callers use one API: execute(sql, params) with `?` placeholders."""

    def __init__(self, raw: Any, postgres: bool) -> None:
        self.raw = raw
        self.postgres = postgres

    def execute(self, sql: str, params: tuple | list = ()) -> Any:
        if self.postgres:
            sql = sql.replace("?", "%s")
        return self.raw.execute(sql, params)

    def one(self, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
        row = self.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def all(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self.execute(sql, params).fetchall()]


@contextmanager
def connect() -> Iterator[Conn]:
    """A transaction: commits on success, rolls back on error."""
    if is_postgres():
        with _pg_pool().connection() as raw:
            with raw.transaction():
                yield Conn(raw, True)
        return
    raw = sqlite3.connect(get_settings().cache_path)
    raw.row_factory = sqlite3.Row
    try:
        with raw:
            yield Conn(raw, False)
    finally:
        raw.close()


def add_column(conn: Conn, table: str, column: str, decl: str) -> None:
    """Add a column to a table created by an older version of the app (no-op if present)."""
    if conn.postgres:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {decl}")
        return
    if column not in {r["name"] for r in conn.all(f"PRAGMA table_info({table})")}:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
