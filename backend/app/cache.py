"""Storage: cached runs, verdict history, per-run costs, invite codes, accounts, credits, and saved research.

Uses Postgres (Supabase) when DATABASE_URL is set, otherwise a local SQLite file
(see db.py). All SQL here runs unchanged on both.
"""

from __future__ import annotations

import json
import secrets
import time
from typing import Any

from . import db
from .config import get_settings

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I, easy to read aloud
DEPTH_RANK = {"quick": 0, "standard": 1, "deep": 2}
_ready: set[str] = set()

_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS runs (ticker TEXT PRIMARY KEY, created DOUBLE PRECISION, events TEXT)",
    """CREATE TABLE IF NOT EXISTS usage (
        ticker TEXT, started DOUBLE PRECISION, finished DOUBLE PRECISION, status TEXT, invite_code TEXT,
        calls INTEGER, input_tokens INTEGER, output_tokens INTEGER, cost_usd DOUBLE PRECISION, detail TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS invites (
        code TEXT PRIMARY KEY, label TEXT, credits_total INTEGER, credits_used INTEGER DEFAULT 0,
        created DOUBLE PRECISION, disabled INTEGER DEFAULT 0
    )""",
    # Append-only history of every verdict, so the scoring weights can later be
    # checked against what the stock actually did.
    """CREATE TABLE IF NOT EXISTS verdicts (
        ticker TEXT, created DOUBLE PRECISION, reference_price DOUBLE PRECISION, rating TEXT,
        score DOUBLE PRECISION, confidence INTEGER, weeks_score DOUBLE PRECISION, months_score DOUBLE PRECISION,
        years_score DOUBLE PRECISION, run TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS accounts (
        user_id TEXT PRIMARY KEY, email TEXT, credits_total INTEGER DEFAULT 0, credits_used INTEGER DEFAULT 0,
        free_granted INTEGER DEFAULT 0, created DOUBLE PRECISION
    )""",
    """CREATE TABLE IF NOT EXISTS redemptions (
        user_id TEXT, code TEXT, credits INTEGER, created DOUBLE PRECISION, PRIMARY KEY (user_id, code)
    )""",
    """CREATE TABLE IF NOT EXISTS saved_runs (
        id TEXT PRIMARY KEY, user_id TEXT, run_key TEXT, ticker TEXT, name TEXT, depth TEXT,
        created DOUBLE PRECISION, rating TEXT, score DOUBLE PRECISION, confidence INTEGER, bottom_line TEXT,
        events TEXT, UNIQUE (user_id, run_key)
    )""",
    "CREATE INDEX IF NOT EXISTS saved_runs_user ON saved_runs (user_id, created)",
    # Every completed analysis, kept in full: the community library (newest first, filterable).
    """CREATE TABLE IF NOT EXISTS analyses (
        id TEXT PRIMARY KEY, run_key TEXT UNIQUE, ticker TEXT, name TEXT, depth TEXT, created DOUBLE PRECISION,
        bottom_line TEXT, reference_price DOUBLE PRECISION, summary TEXT, events TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS analyses_created ON analyses (created)",
    # Every Stripe payment that added credits, keyed by the Stripe object (invoice or checkout session),
    # so a webhook delivered twice can never add credits twice.
    """CREATE TABLE IF NOT EXISTS payments (
        id TEXT PRIMARY KEY, user_id TEXT, kind TEXT, plan TEXT, credits INTEGER, amount_cents INTEGER,
        currency TEXT, created DOUBLE PRECISION
    )""",
]


def _db() -> Any:
    """A transaction on the configured database, creating/upgrading tables on first use."""
    key = db.database_url() or get_settings().cache_path
    if key not in _ready:
        with db.connect() as conn:
            for stmt in _SCHEMA:
                conn.execute(stmt)
            # Columns added after launch, for databases created by older versions.
            db.add_column(conn, "runs", "depth", "TEXT DEFAULT 'deep'")
            db.add_column(conn, "usage", "depth", "TEXT")
            db.add_column(conn, "usage", "user_id", "TEXT")
            db.add_column(conn, "saved_runs", "scores", "TEXT")
            _seed_analyses(conn)
            db.add_column(conn, "accounts", "stripe_customer_id", "TEXT")
            db.add_column(conn, "accounts", "plan", "TEXT")
            db.add_column(conn, "accounts", "plan_status", "TEXT")
            db.add_column(conn, "accounts", "subscription_id", "TEXT")
            db.add_column(conn, "accounts", "plan_renews", "DOUBLE PRECISION")
        _ready.add(key)
    return db.connect()


def _seed_analyses(conn: Any) -> None:
    """First time the library exists: fill it from the latest stored run of each stock."""
    if conn.one("SELECT 1 AS x FROM analyses LIMIT 1"):
        return
    for row in conn.all("SELECT ticker, created, events FROM runs"):
        try:
            _insert_analysis(conn, row["ticker"], json.loads(row["events"]), None, row["created"])
        except Exception:  # noqa: BLE001 - a malformed old run shouldn't block startup
            continue


def _max0(expr: str) -> str:
    return f"CASE WHEN {expr} < 0 THEN 0 ELSE {expr} END"


# ---------------------------------------------------------------------------
# Cached runs and verdict history
# ---------------------------------------------------------------------------


def record_verdict(run: dict[str, Any]) -> None:
    v = run.get("verdict")
    if not v:
        return
    with _db() as conn:
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
    with _db() as conn:
        row = conn.one("SELECT created, events, depth FROM runs WHERE ticker = ?", (ticker,))
    if not row or time.time() - row["created"] >= ttl:
        return None
    if DEPTH_RANK.get(row["depth"] or "deep", 2) < DEPTH_RANK.get(min_depth, 0):
        return None
    return json.loads(row["events"])


def save_run(ticker: str, events: list[dict[str, Any]], depth: str = "deep") -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO runs (ticker, created, events, depth) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (ticker) DO UPDATE SET created = excluded.created, events = excluded.events, "
            "depth = excluded.depth",
            (ticker, time.time(), json.dumps(events), depth),
        )


def _summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    start = next((e for e in events if e.get("type") == "start"), {})
    verdict = next((e.get("verdict") for e in events if e.get("type") == "verdict"), None) or {}
    done = next((e.get("run") for e in events if e.get("type") == "done"), None) or {}
    return {
        "name": start.get("company_name"),
        "depth": start.get("depth") or done.get("depth") or "deep",
        "rating": verdict.get("rating"),
        "score": verdict.get("score"),
        # Each horizon's own score, so lists can show the rating for the viewer's chosen timeframe.
        "scores": {h: (verdict.get(h) or {}).get("score") for h in ("weeks", "months", "years")} if verdict else None,
        "confidence": verdict.get("confidence"),
        "bottom_line": verdict.get("bottom_line") or verdict.get("summary"),
        "finished_at": done.get("finished_at") or done.get("started_at"),
    }


# ---------------------------------------------------------------------------
# Community library: every completed analysis, browsable and filterable
# ---------------------------------------------------------------------------

HORIZON_KEYS = ("weeks", "months", "years")


def _insert_analysis(
    conn: Any, ticker: str, events: list[dict[str, Any]], reference_price: float | None, created: float
) -> None:
    s = _summary(events)
    verdict = next((e.get("verdict") for e in events if e.get("type") == "verdict"), None) or {}
    if not verdict:
        return
    summary = {
        "scores": {h: (verdict.get(h) or {}).get("score") for h in HORIZON_KEYS},
        "confidences": {h: (verdict.get(h) or {}).get("confidence") for h in HORIZON_KEYS},
        "rating": verdict.get("rating"),
        "score": verdict.get("score"),
        "confidence": verdict.get("confidence"),
    }
    conn.execute(
        "INSERT INTO analyses (id, run_key, ticker, name, depth, created, bottom_line, reference_price, summary,"
        " events) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (run_key) DO NOTHING",
        (
            secrets.token_urlsafe(9),
            f"{ticker}:{s['finished_at'] or created}",
            ticker,
            s["name"],
            s["depth"],
            created,
            s["bottom_line"],
            reference_price,
            json.dumps(summary),
            json.dumps([{k: v for k, v in e.items() if k != "cached"} for e in events]),
        ),
    )


def save_analysis(ticker: str, events: list[dict[str, Any]], reference_price: float | None = None) -> None:
    with _db() as conn:
        _insert_analysis(conn, ticker, events, reference_price, time.time())


def list_analyses(since: float = 0, limit: int = 2000) -> list[dict[str, Any]]:
    """Newest first, without the (large) events. Filtering and sorting happen in the caller."""
    with _db() as conn:
        rows = conn.all(
            "SELECT id, ticker, name, depth, created, bottom_line, reference_price, summary FROM analyses "
            "WHERE created >= ? ORDER BY created DESC LIMIT ?",
            (since, limit),
        )
    for row in rows:
        row["summary"] = json.loads(row["summary"] or "{}")
    return rows


def get_analysis(aid: str) -> dict[str, Any] | None:
    with _db() as conn:
        row = conn.one("SELECT id, ticker, name, depth, created, events FROM analyses WHERE id = ?", (aid,))
    if not row:
        return None
    return {**row, "events": json.loads(row["events"])}


def recent_runs(limit: int = 12) -> list[dict[str, Any]]:
    """Tickers with a fresh cached run (free for anyone to view), newest first."""
    cutoff = time.time() - get_settings().cache_ttl_hours * 3600
    with _db() as conn:
        rows = conn.all(
            "SELECT ticker, created, events, depth FROM runs WHERE created > ? ORDER BY created DESC LIMIT ?",
            (cutoff, limit),
        )
    out = []
    for row in rows:
        s = _summary(json.loads(row["events"]))
        out.append(
            {
                "ticker": row["ticker"],
                "name": s["name"],
                "rating": s["rating"],
                "score": s["score"],
                "scores": s["scores"],
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
    user_id: str | None = None,
) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO usage (ticker, started, finished, status, invite_code, calls, input_tokens, output_tokens,"
            " cost_usd, detail, depth, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                user_id,
            ),
        )


def usage_stats(recent: int = 50) -> dict[str, Any]:
    now = time.time()
    with _db() as conn:

        def window(seconds: float | None) -> dict[str, Any]:
            since = now - seconds if seconds else 0
            d = (
                conn.one(
                    """SELECT COUNT(*) AS runs, COALESCE(SUM(cost_usd), 0) AS cost,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens, COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END), 0) AS completed
                   FROM usage WHERE started >= ?""",
                    (since,),
                )
                or {}
            )
            d = {k: (float(v) if k == "cost" else int(v)) for k, v in d.items()}
            d["avg_cost_per_completed_run"] = round(d["cost"] / d["completed"], 4) if d["completed"] else None
            d["cost"] = round(d["cost"], 4)
            return d

        rows = conn.all(
            """SELECT u.ticker, u.started, u.finished, u.status, u.calls, u.input_tokens, u.output_tokens,
                      u.cost_usd, u.detail, u.depth, i.label AS invite_label, a.email AS user_email
               FROM usage u
               LEFT JOIN invites i ON i.code = u.invite_code
               LEFT JOIN accounts a ON a.user_id = u.user_id
               ORDER BY u.started DESC LIMIT ?""",
            (recent,),
        )
        signups = conn.one("SELECT COUNT(*) AS n FROM accounts") or {"n": 0}
        return {
            "today": window(24 * 3600),
            "last_7_days": window(7 * 24 * 3600),
            "all_time": window(None),
            "accounts": int(signups["n"]),
            "recent_runs": [{**r, "detail": json.loads(r["detail"] or "[]")} for r in rows],
        }


# ---------------------------------------------------------------------------
# Invite codes: bonus credits an account can redeem once
# ---------------------------------------------------------------------------


def _new_code() -> str:
    body = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    return f"SC-{body[:4]}-{body[4:]}"


def normalize_code(code: str | None) -> str | None:
    return code.strip().upper() if code and code.strip() else None


def create_invite(label: str, credits: int) -> dict[str, Any]:
    code = _new_code()
    with _db() as conn:
        conn.execute(
            "INSERT INTO invites (code, label, credits_total, credits_used, created) VALUES (?, ?, ?, 0, ?)",
            (code, label, credits, time.time()),
        )
    return get_invite(code) or {}


def get_invite(code: str | None) -> dict[str, Any] | None:
    code = normalize_code(code)
    if not code:
        return None
    with _db() as conn:
        d = conn.one("SELECT * FROM invites WHERE code = ?", (code,))
    if not d:
        return None
    d["remaining"] = max(0, d["credits_total"] - d["credits_used"])
    d["disabled"] = bool(d["disabled"])
    return d


def list_invites() -> list[dict[str, Any]]:
    with _db() as conn:
        rows = conn.all("SELECT code FROM invites ORDER BY created DESC")
    return [inv for r in rows if (inv := get_invite(r["code"]))]


def consume_credit(code: str, amount: int = 1) -> bool:
    """Atomically use `amount` credits of an invite (legacy invite-code runs)."""
    with _db() as conn:
        cur = conn.execute(
            "UPDATE invites SET credits_used = credits_used + ? "
            "WHERE code = ? AND disabled = 0 AND credits_used + ? <= credits_total",
            (amount, normalize_code(code), amount),
        )
        return cur.rowcount == 1


def refund_credit(code: str, amount: int = 1) -> None:
    with _db() as conn:
        conn.execute(
            f"UPDATE invites SET credits_used = {_max0('credits_used - ?')} WHERE code = ?",
            (amount, amount, normalize_code(code)),
        )


def update_invite(code: str, *, add_credits: int = 0, disabled: bool | None = None) -> dict[str, Any] | None:
    with _db() as conn:
        if add_credits:
            conn.execute(
                "UPDATE invites SET credits_total = CASE WHEN credits_total + ? < credits_used "
                "THEN credits_used ELSE credits_total + ? END WHERE code = ?",
                (add_credits, add_credits, normalize_code(code)),
            )
        if disabled is not None:
            conn.execute("UPDATE invites SET disabled = ? WHERE code = ?", (int(disabled), normalize_code(code)))
    return get_invite(code)


def redeem_invite(user_id: str, code: str) -> tuple[int, str | None]:
    """Move an invite's remaining credits into an account. Returns (credits added, error message)."""
    invite = get_invite(code)
    if not invite or invite["disabled"]:
        return 0, "That code isn't valid."
    if invite["remaining"] <= 0:
        return 0, "That code has already been used."
    amount = invite["remaining"]
    with _db() as conn:
        # Claim the credits only if nobody else did in the meantime.
        cur = conn.execute(
            "UPDATE invites SET credits_used = credits_total WHERE code = ? AND credits_used = ?",
            (invite["code"], invite["credits_used"]),
        )
        if cur.rowcount != 1:
            return 0, "That code has already been used."
        conn.execute("UPDATE accounts SET credits_total = credits_total + ? WHERE user_id = ?", (amount, user_id))
        conn.execute(
            "INSERT INTO redemptions (user_id, code, credits, created) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (user_id, code) DO NOTHING",
            (user_id, invite["code"], amount, time.time()),
        )
    return amount, None


# ---------------------------------------------------------------------------
# Accounts and credits (one account per Supabase user)
# ---------------------------------------------------------------------------


def _account_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": row["user_id"],
        "email": row["email"],
        "credits_total": row["credits_total"],
        "credits_used": row["credits_used"],
        "remaining": max(0, row["credits_total"] - row["credits_used"]),
        "free_granted": bool(row["free_granted"]),
        "created": row["created"],
        "plan": row.get("plan"),
        "plan_status": row.get("plan_status"),
        "plan_renews": row.get("plan_renews"),
        "has_billing": bool(row.get("stripe_customer_id")),
    }


def get_account(user_id: str) -> dict[str, Any] | None:
    with _db() as conn:
        row = conn.one("SELECT * FROM accounts WHERE user_id = ?", (user_id,))
    return _account_view(row) if row else None


def ensure_account(user_id: str, email: str | None, free_credits: int, daily_free_cap: int) -> dict[str, Any]:
    """Create the account on first sign-in, granting the free credits once (subject to a daily cap)."""
    existing = get_account(user_id)
    if existing:
        return existing
    now = time.time()
    with _db() as conn:
        granted_today = conn.one(
            "SELECT COUNT(*) AS n FROM accounts WHERE free_granted = 1 AND created >= ?", (now - 86400,)
        ) or {"n": 0}
        grant = free_credits if daily_free_cap <= 0 or int(granted_today["n"]) < daily_free_cap else 0
        conn.execute(
            "INSERT INTO accounts (user_id, email, credits_total, credits_used, free_granted, created) "
            "VALUES (?, ?, ?, 0, ?, ?) ON CONFLICT (user_id) DO NOTHING",
            (user_id, email, grant, 1 if grant else 0, now),
        )
    return get_account(user_id) or {}


def consume_account_credits(user_id: str, amount: int) -> bool:
    with _db() as conn:
        cur = conn.execute(
            "UPDATE accounts SET credits_used = credits_used + ? "
            "WHERE user_id = ? AND credits_used + ? <= credits_total",
            (amount, user_id, amount),
        )
        return cur.rowcount == 1


def refund_account_credits(user_id: str, amount: int) -> None:
    with _db() as conn:
        conn.execute(
            f"UPDATE accounts SET credits_used = {_max0('credits_used - ?')} WHERE user_id = ?",
            (amount, amount, user_id),
        )


def add_account_credits(user_id: str, amount: int) -> dict[str, Any] | None:
    with _db() as conn:
        conn.execute("UPDATE accounts SET credits_total = credits_total + ? WHERE user_id = ?", (amount, user_id))
    return get_account(user_id)


def list_accounts(limit: int = 200) -> list[dict[str, Any]]:
    with _db() as conn:
        rows = conn.all("SELECT * FROM accounts ORDER BY created DESC LIMIT ?", (limit,))
    return [_account_view(r) for r in rows]


# ---------------------------------------------------------------------------
# Payments (Stripe)
# ---------------------------------------------------------------------------


def stripe_customer(user_id: str) -> str | None:
    with _db() as conn:
        row = conn.one("SELECT stripe_customer_id FROM accounts WHERE user_id = ?", (user_id,))
    return row["stripe_customer_id"] if row else None


def set_stripe_customer(user_id: str, customer_id: str) -> None:
    with _db() as conn:
        conn.execute("UPDATE accounts SET stripe_customer_id = ? WHERE user_id = ?", (customer_id, user_id))


def clear_billing(user_id: str) -> None:
    """Forget a Stripe customer and plan that no longer exist (e.g. sandbox ones after switching to live keys)."""
    with _db() as conn:
        conn.execute(
            "UPDATE accounts SET stripe_customer_id = NULL, plan = NULL, plan_status = NULL, subscription_id = NULL, "
            "plan_renews = NULL WHERE user_id = ?",
            (user_id,),
        )


def user_for_customer(customer_id: str) -> str | None:
    with _db() as conn:
        row = conn.one("SELECT user_id FROM accounts WHERE stripe_customer_id = ?", (customer_id,))
    return row["user_id"] if row else None


def set_subscription(
    user_id: str, plan: str | None, status: str | None, subscription_id: str | None, renews: float | None
) -> None:
    with _db() as conn:
        conn.execute(
            "UPDATE accounts SET plan = ?, plan_status = ?, subscription_id = ?, plan_renews = ? WHERE user_id = ?",
            (plan, status, subscription_id, renews, user_id),
        )


def grant_payment(key: str, user_id: str, kind: str, plan: str, credits: int, amount_cents: int, currency: str) -> bool:
    """Add a payment's credits exactly once per Stripe object. Returns False if it was already counted."""
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO payments (id, user_id, kind, plan, credits, amount_cents, currency, created) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO NOTHING",
            (key, user_id, kind, plan, credits, amount_cents, currency, time.time()),
        )
        if cur.rowcount != 1:
            return False
        conn.execute("UPDATE accounts SET credits_total = credits_total + ? WHERE user_id = ?", (credits, user_id))
    return True


def revenue(since: float | None = None) -> dict[str, Any]:
    with _db() as conn:
        row = conn.one(
            "SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents), 0) AS cents, COALESCE(SUM(credits), 0) AS credits "
            "FROM payments WHERE created >= ?",
            (since or 0,),
        ) or {"n": 0, "cents": 0, "credits": 0}
    return {
        "payments": int(row["n"]),
        "revenue": round(int(row["cents"]) / 100, 2),
        "credits_sold": int(row["credits"]),
    }


def list_payments(limit: int = 50) -> list[dict[str, Any]]:
    with _db() as conn:
        return conn.all(
            "SELECT p.*, a.email FROM payments p LEFT JOIN accounts a ON a.user_id = p.user_id "
            "ORDER BY p.created DESC LIMIT ?",
            (limit,),
        )


# ---------------------------------------------------------------------------
# Saved research (each account's history of reports)
# ---------------------------------------------------------------------------


def save_for_user(user_id: str, ticker: str, events: list[dict[str, Any]]) -> str | None:
    s = _summary(events)
    if s["rating"] is None:
        return None
    run_key = f"{ticker}:{s['finished_at'] or ''}"
    rid = secrets.token_urlsafe(9)
    with _db() as conn:
        conn.execute(
            "INSERT INTO saved_runs (id, user_id, run_key, ticker, name, depth, created, rating, score, confidence,"
            " bottom_line, events, scores) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT (user_id, run_key) DO NOTHING",
            (
                rid,
                user_id,
                run_key,
                ticker,
                s["name"],
                s["depth"],
                time.time(),
                s["rating"],
                s["score"],
                s["confidence"],
                s["bottom_line"],
                json.dumps(events),
                json.dumps(s["scores"]) if s["scores"] else None,
            ),
        )
        row = conn.one("SELECT id FROM saved_runs WHERE user_id = ? AND run_key = ?", (user_id, run_key))
    return row["id"] if row else None


def list_saved(user_id: str, limit: int = 100) -> list[dict[str, Any]]:
    with _db() as conn:
        rows = conn.all(
            "SELECT id, ticker, name, depth, created, rating, score, confidence, bottom_line, scores, "
            "CASE WHEN scores IS NULL THEN events END AS events FROM saved_runs "
            "WHERE user_id = ? ORDER BY created DESC LIMIT ?",
            (user_id, limit),
        )
    for row in rows:
        # Reports saved before per-horizon scores were stored: read them from the saved events.
        raw, events = row.pop("scores"), row.pop("events")
        row["scores"] = json.loads(raw) if raw else _summary(json.loads(events))["scores"] if events else None
    return rows


def get_saved(user_id: str, rid: str) -> dict[str, Any] | None:
    with _db() as conn:
        row = conn.one("SELECT * FROM saved_runs WHERE user_id = ? AND id = ?", (user_id, rid))
    if not row:
        return None
    return {**row, "events": json.loads(row["events"])}


def delete_saved(user_id: str, rid: str | None = None) -> None:
    with _db() as conn:
        if rid:
            conn.execute("DELETE FROM saved_runs WHERE user_id = ? AND id = ?", (user_id, rid))
        else:
            conn.execute("DELETE FROM saved_runs WHERE user_id = ?", (user_id,))
