"""SQLite storage: cached runs, verdict history, per-run costs, and invite codes.

Needs a persistent disk in production (see docs/DEPLOY.md); on a free host with
a temporary disk, everything here resets whenever the server restarts.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import time
from typing import Any

from .config import get_settings

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I, easy to read aloud


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(get_settings().cache_path)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS runs (ticker TEXT PRIMARY KEY, created REAL, events TEXT)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS usage (
            ticker TEXT, started REAL, finished REAL, status TEXT, invite_code TEXT,
            calls INTEGER, input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL, detail TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS invites (
            code TEXT PRIMARY KEY, label TEXT, credits_total INTEGER, credits_used INTEGER DEFAULT 0,
            created REAL, disabled INTEGER DEFAULT 0
        )"""
    )
    # Columns added after launch: add them to databases created by older versions.
    _add_column(conn, "runs", "depth", "TEXT DEFAULT 'deep'")
    _add_column(conn, "usage", "depth", "TEXT")
    # Append-only history of every verdict, so the scoring weights can later be
    # checked against what the stock actually did.
    conn.execute(
        """CREATE TABLE IF NOT EXISTS verdicts (
            ticker TEXT, created REAL, reference_price REAL, rating TEXT, score REAL, confidence INTEGER,
            weeks_score REAL, months_score REAL, years_score REAL, run TEXT
        )"""
    )
    return conn


def _add_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    if column not in {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


DEPTH_RANK = {"quick": 0, "standard": 1, "deep": 2}


def record_verdict(run: dict[str, Any]) -> None:
    v = run.get("verdict")
    if not v:
        return
    with _conn() as conn:
        conn.execute(
            "INSERT INTO verdicts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run["ticker"],
                time.time(),
                run.get("reference_price"),
                v["rating"],
                v["score"],
                v["confidence"],
                v["weeks"]["score"],
                v["months"]["score"],
                v["years"]["score"],
                json.dumps(run),
            ),
        )


def get_run(ticker: str, min_depth: str = "quick") -> list[dict[str, Any]] | None:
    """A recent cached run at least as deep as requested (a Deep run can stand in for a Quick request)."""
    ttl = get_settings().cache_ttl_hours * 3600
    with _conn() as conn:
        row = conn.execute("SELECT created, events, depth FROM runs WHERE ticker = ?", (ticker,)).fetchone()
    if not row or time.time() - row["created"] >= ttl:
        return None
    if DEPTH_RANK.get(row["depth"] or "deep", 2) < DEPTH_RANK.get(min_depth, 0):
        return None
    return json.loads(row["events"])


def save_run(ticker: str, events: list[dict[str, Any]], depth: str = "deep") -> None:
    with _conn() as conn:
        conn.execute(
            "REPLACE INTO runs (ticker, created, events, depth) VALUES (?, ?, ?, ?)",
            (ticker, time.time(), json.dumps(events), depth),
        )


def recent_runs(limit: int = 12) -> list[dict[str, Any]]:
    """Tickers with a fresh cached run (free for anyone to view), newest first."""
    cutoff = time.time() - get_settings().cache_ttl_hours * 3600
    with _conn() as conn:
        rows = conn.execute(
            "SELECT ticker, created, events, depth FROM runs WHERE created > ? ORDER BY created DESC LIMIT ?",
            (cutoff, limit),
        ).fetchall()
    out = []
    for row in rows:
        events = json.loads(row["events"])
        start = next((e for e in events if e.get("type") == "start"), {})
        verdict = next((e.get("verdict") for e in events if e.get("type") == "verdict"), None) or {}
        out.append(
            {
                "ticker": row["ticker"],
                "name": start.get("company_name"),
                "rating": verdict.get("rating"),
                "score": verdict.get("score"),
                "analyzed_at": row["created"],
                "depth": row["depth"] or "deep",
            }
        )
    return out


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------


def record_usage(
    ticker: str,
    started: float,
    status: str,
    invite_code: str | None,
    summary: dict[str, Any],
    depth: str | None = None,
) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO usage (ticker, started, finished, status, invite_code, calls, input_tokens, output_tokens,"
            " cost_usd, detail, depth) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ticker,
                started,
                time.time(),
                status,
                invite_code,
                summary.get("calls", 0),
                summary.get("input_tokens", 0),
                summary.get("output_tokens", 0),
                summary.get("cost_usd", 0.0),
                json.dumps(summary.get("by_agent", [])),
                depth,
            ),
        )


def usage_stats(recent: int = 50) -> dict[str, Any]:
    now = time.time()
    with _conn() as conn:

        def window(seconds: float | None) -> dict[str, Any]:
            since = now - seconds if seconds else 0
            row = conn.execute(
                """SELECT COUNT(*) AS runs, COALESCE(SUM(cost_usd), 0) AS cost,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens, COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(status = 'done'), 0) AS completed
                   FROM usage WHERE started >= ?""",
                (since,),
            ).fetchone()
            d = dict(row)
            d["avg_cost_per_completed_run"] = round(d["cost"] / d["completed"], 4) if d["completed"] else None
            d["cost"] = round(d["cost"], 4)
            return d

        rows = conn.execute(
            """SELECT u.ticker, u.started, u.finished, u.status, u.calls, u.input_tokens, u.output_tokens,
                      u.cost_usd, u.detail, u.depth, i.label AS invite_label
               FROM usage u LEFT JOIN invites i ON i.code = u.invite_code
               ORDER BY u.started DESC LIMIT ?""",
            (recent,),
        ).fetchall()
        return {
            "today": window(24 * 3600),
            "last_7_days": window(7 * 24 * 3600),
            "all_time": window(None),
            "recent_runs": [{**dict(r), "detail": json.loads(r["detail"] or "[]")} for r in rows],
        }


# ---------------------------------------------------------------------------
# Invite codes and credits (one credit = one fresh analysis)
# ---------------------------------------------------------------------------


def _new_code() -> str:
    body = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    return f"SC-{body[:4]}-{body[4:]}"


def create_invite(label: str, credits: int) -> dict[str, Any]:
    code = _new_code()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO invites (code, label, credits_total, credits_used, created) VALUES (?, ?, ?, 0, ?)",
            (code, label, credits, time.time()),
        )
    return get_invite(code) or {}


def normalize_code(code: str | None) -> str | None:
    return code.strip().upper() if code and code.strip() else None


def get_invite(code: str | None) -> dict[str, Any] | None:
    code = normalize_code(code)
    if not code:
        return None
    with _conn() as conn:
        row = conn.execute("SELECT * FROM invites WHERE code = ?", (code,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["remaining"] = max(0, d["credits_total"] - d["credits_used"])
    d["disabled"] = bool(d["disabled"])
    return d


def list_invites() -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute("SELECT code FROM invites ORDER BY created DESC").fetchall()
    return [inv for r in rows if (inv := get_invite(r["code"]))]


def consume_credit(code: str, amount: int = 1) -> bool:
    """Atomically use `amount` credits. False if the code is unknown, disabled, or short of credits."""
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE invites SET credits_used = credits_used + ? "
            "WHERE code = ? AND disabled = 0 AND credits_used + ? <= credits_total",
            (amount, normalize_code(code), amount),
        )
        return cur.rowcount == 1


def refund_credit(code: str, amount: int = 1) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE invites SET credits_used = MAX(0, credits_used - ?) WHERE code = ?",
            (amount, normalize_code(code)),
        )


def update_invite(code: str, *, add_credits: int = 0, disabled: bool | None = None) -> dict[str, Any] | None:
    with _conn() as conn:
        if add_credits:
            conn.execute(
                "UPDATE invites SET credits_total = MAX(credits_used, credits_total + ?) WHERE code = ?",
                (add_credits, normalize_code(code)),
            )
        if disabled is not None:
            conn.execute("UPDATE invites SET disabled = ? WHERE code = ?", (int(disabled), normalize_code(code)))
    return get_invite(code)
