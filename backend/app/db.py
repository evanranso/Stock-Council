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


def diagnose() -> dict[str, Any]:
    """Why can't we reach Postgres? Checks the URL's shape and tries one direct connection.

    Returns only hints and yes/no facts, never the password or the full connection string.
    """
    from urllib.parse import unquote

    import psycopg

    url = (database_url() or "").strip()
    # Parse by hand: urlparse rejects some passwords (e.g. with [ ]), which is itself worth reporting.
    scheme, _, rest = url.partition("://")
    creds, _, hostpart = rest.rpartition("@")
    user, _, password = creds.partition(":")
    hostport = hostpart.split("/", 1)[0].split("?", 1)[0]
    host, _, port = hostport.partition(":")
    raw_pw = unquote(password)
    facts: dict[str, Any] = {
        "scheme_ok": scheme in ("postgres", "postgresql"),
        "pooler_host": host.endswith("pooler.supabase.com"),
        "direct_host": host.startswith("db.") and host.endswith(".supabase.co"),
        "port": int(port) if port.isdigit() else None,
        "user_has_project_ref": "." in user,
        "password_placeholder": "YOUR-PASSWORD" in raw_pw.upper(),
        "password_has_unencoded_symbols": any(c in password for c in "[]@#/?"),
    }
    hints = []
    if not facts["scheme_ok"]:
        hints.append("DATABASE_URL should start with postgresql:// (copy the URI format from Supabase).")
    if facts["password_has_unencoded_symbols"] and not facts["password_placeholder"]:
        hints.append(
            "The password contains symbols ([ ] @ # / ?) that break the connection string. Reset the database "
            "password in Supabase to one with only letters and numbers, then update DATABASE_URL."
        )
    if facts["pooler_host"] and facts["port"] not in (6543, 5432):
        hints.append("The pooler port should be 6543 (Transaction pooler).")
    if facts["direct_host"]:
        hints.append(
            "This is the 'Direct connection' string (db.<ref>.supabase.co), which is IPv6-only and unreachable "
            "from Render. Use Connect -> Transaction pooler instead (host ends in pooler.supabase.com, port 6543)."
        )
    if facts["password_placeholder"]:
        hints.append("The password is still the [YOUR-PASSWORD] placeholder. Put your real database password in.")
    if facts["pooler_host"] and not facts["user_has_project_ref"]:
        hints.append("With the pooler, the user must be postgres.<project-ref>, not just postgres.")
    try:
        with psycopg.connect(url, connect_timeout=10, prepare_threshold=None) as conn:
            conn.execute("SELECT 1")
        facts["direct_connect"] = "ok"
    except Exception as exc:  # noqa: BLE001 - classify, never echo the raw message (it can include the host/user)
        msg = str(exc).lower()
        facts["direct_connect"] = type(exc).__name__
        if "password authentication failed" in msg:
            hints.append(
                "Wrong database password. Reset it in Supabase (Database -> Settings) and update DATABASE_URL. "
                "If the password has symbols like @ # / ? %, pick one with only letters and numbers."
            )
        elif "tenant or user not found" in msg:
            hints.append("The pooler doesn't recognize the user: it must be postgres.<project-ref>.")
        elif "network is unreachable" in msg or "cannot assign requested address" in msg:
            hints.append("Network unreachable (usually the IPv6-only direct connection). Use the Transaction pooler.")
        elif "connection refused" in msg:
            hints.append("Connection refused: the host or port is wrong. Copy the Transaction pooler string again.")
        elif "timeout" in msg or "timed out" in msg:
            hints.append("Connection timed out: check the host and port (pooler: port 6543).")
        elif "could not translate host name" in msg or "name or service not known" in msg:
            hints.append("The host name doesn't exist: copy the connection string again from Supabase.")
        elif "invalid" in msg and ("dsn" in msg or "uri" in msg or "connection" in msg):
            hints.append("The connection string is malformed. Copy it again; symbols in the password can break it.")
    facts["hints"] = hints or ["No obvious problem found in the connection string's shape."]
    return facts
