"""HTTP API. Run with: uvicorn app.main:app --reload"""

from __future__ import annotations

import asyncio
import hmac
import json
import re
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import cache, search, usage
from .agents.pipeline import run_council
from .agents.specialists import SPECIALISTS
from .auth import User, optional_user, require_user, verify_token
from .config import get_settings
from .data.registry import ADAPTERS
from .depth import DEFAULT_DEPTH, all_depths, get_depth


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Load the company list in the background so the first searches are instant.
    warm = asyncio.create_task(search.ensure_index())
    yield
    warm.cancel()


app = FastAPI(title="Stock Council API", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Admin-Key", "Authorization"],
)

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_recent_runs: dict[str, deque[float]] = defaultdict(deque)
_daily_runs: dict[str, int] = {}


class AccessDenied(Exception):
    """Why a fresh analysis can't start. `reason` lets the website show the right prompt."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def _client_ip(request: Request) -> str:
    if settings.trust_proxy:
        # The proxy appends the address it saw; earlier entries can be forged by the client.
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _check_daily_budget() -> None:
    if settings.max_runs_per_day <= 0:
        return
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if _daily_runs.get(today, 0) >= settings.max_runs_per_day:
        raise AccessDenied(
            "daily_limit", "The council has hit today's analysis limit. Recently analyzed stocks still work."
        )
    if today not in _daily_runs:
        _daily_runs.clear()  # drop previous days
    _daily_runs[today] = _daily_runs.get(today, 0) + 1


def _check_rate_limit(ip: str) -> None:
    window = _recent_runs[ip]
    now = time.time()
    while window and now - window[0] > 3600:
        window.popleft()
    if len(window) >= settings.rate_limit_per_hour:
        raise AccessDenied("rate_limit", "You've started a lot of analyses in the last hour. Try again a bit later.")
    window.append(now)


def _check_invite(code: str | None, credits: int = 1) -> dict[str, Any] | None:
    """In invite mode, a fresh analysis needs a valid code with enough credits left (not yet charged)."""
    if settings.access_mode != "invite":
        return None
    invite = cache.get_invite(code)
    if not invite or invite["disabled"]:
        raise AccessDenied("invite_required", "Stock Council is invite-only right now. Enter your invite code.")
    if invite["remaining"] < credits:
        raise AccessDenied("no_credits", "You don't have enough credits left for this depth.")
    return invite


def _ticker(raw: str) -> str:
    t = raw.strip().upper()
    if not TICKER_RE.match(t):
        raise HTTPException(400, "Invalid ticker symbol.")
    return t


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


@app.get("/api/health")
def health(db: bool = False) -> dict[str, Any]:
    """Liveness. With ?db=1, also time a database round trip (to diagnose a slow or unreachable database)."""
    out: dict[str, Any] = {"ok": True, "model": settings.claude_model}
    if db:
        started = time.time()
        try:
            cache.recent_runs(limit=1)
            out["database"] = {"ok": True, "kind": "postgres" if cache.db.is_postgres() else "sqlite"}
        except Exception as exc:  # noqa: BLE001 - report, don't crash
            out["ok"] = False
            out["database"] = {"ok": False, "error": type(exc).__name__}
            if cache.db.is_postgres():
                out["database"]["diagnosis"] = cache.db.diagnose()
        out["database"]["ms"] = round((time.time() - started) * 1000)
    return out


@app.get("/api/analysts")
async def analysts() -> list[dict[str, str]]:
    return [{"id": s.id, "name": s.name, "segment": s.segment} for s in SPECIALISTS]


@app.get("/api/data/{ticker}/{segment}")
async def raw_data(ticker: str, segment: str) -> dict[str, Any]:
    """Debug view: exactly what one specialist would see."""
    if segment not in ADAPTERS:
        raise HTTPException(404, f"Unknown segment. Options: {sorted(ADAPTERS)}")
    return (await ADAPTERS[segment](_ticker(ticker))).model_dump(mode="json")


@app.get("/api/search")
async def search_tickers(q: str = "", limit: int = 8) -> list[dict[str, Any]]:
    """Autocomplete: match a ticker or company name ("apple" -> AAPL)."""
    if not q.strip():
        return []
    if not await search.ensure_index():
        raise HTTPException(503, "Company search is temporarily unavailable.")
    return await search.search(q[:60], min(max(limit, 1), 20))


# ---------------------------------------------------------------------------
# Access: credits and what's free to view
# ---------------------------------------------------------------------------


def _public_invite(invite: dict[str, Any] | None) -> dict[str, Any] | None:
    if not invite:
        return None
    return {k: invite[k] for k in ("code", "label", "credits_total", "credits_used", "remaining", "disabled")}


@app.get("/api/access")
def access(code: str | None = None) -> dict[str, Any]:
    """What this visitor can do: access mode and, with a code, their credits."""
    invite = cache.get_invite(code)
    return {
        "mode": settings.access_mode,
        "invite": _public_invite(invite),
        "valid": bool(invite and not invite["disabled"]),
        "depths": [d.public() for d in all_depths()],
        "default_depth": DEFAULT_DEPTH,
        "free_credits": settings.free_credits,
    }


def _account_for(user: User) -> dict[str, Any]:
    return cache.ensure_account(user.id, user.email, settings.free_credits, settings.free_signups_per_day)


@app.get("/api/status/{ticker}")
def status(
    ticker: str, code: str | None = None, depth: str | None = None, user: User | None = Depends(optional_user)
) -> dict[str, Any]:
    """Would opening this ticker at this depth be free (running, or recently analyzed at least this deep)?"""
    symbol = _ticker(ticker)
    profile = get_depth(depth)
    if symbol in _live:
        return {"free": True, "reason": "running", "depth": _live[symbol].depth}
    if cache.get_run(symbol, profile.id) is not None:
        return {"free": True, "reason": "cached"}
    invite = cache.get_invite(code)
    account = _account_for(user) if user else None
    return {
        "free": False,
        "reason": None,
        "mode": settings.access_mode,
        "invite": _public_invite(invite),
        "signed_in": user is not None,
        "remaining": account["remaining"] if account else None,
        "depths": [d.public() for d in all_depths()],
    }


@app.get("/api/recent")
def recent() -> list[dict[str, Any]]:
    """Stocks analyzed recently: free for anyone to open."""
    return cache.recent_runs()


# ---------------------------------------------------------------------------
# Council runs
# ---------------------------------------------------------------------------


class LiveRun:
    """A council run that lives on the server, independent of any one browser tab.

    Leaving the page doesn't cancel the (paid) work: the run keeps going, and
    reopening the ticker replays everything so far and follows the rest.
    """

    def __init__(
        self,
        symbol: str,
        invite_code: str | None = None,
        depth: str = DEFAULT_DEPTH,
        credits: int = 0,
        user_id: str | None = None,
    ) -> None:
        self.symbol = symbol
        self.invite_code = invite_code
        self.user_id = user_id
        self.depth = depth
        self.credits = credits
        self.events: list[dict[str, Any]] = []
        self.done = False
        self.changed = asyncio.Condition()
        self.task: asyncio.Task | None = None

    async def publish(self, event: dict[str, Any] | None) -> None:
        async with self.changed:
            if event is None:
                self.done = True
            else:
                self.events.append(event)
            self.changed.notify_all()

    async def drive(self) -> None:
        tracker = usage.start()  # every Claude call in this run is costed against it
        started = time.time()
        try:
            async for event in run_council(self.symbol, self.depth):
                await self.publish(event)
        except Exception as exc:  # noqa: BLE001 - surface failures to the UI instead of a dead stream
            await self.publish({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            completed = bool(self.events) and self.events[-1]["type"] == "done"
            await asyncio.to_thread(self._store, completed, started, tracker.summary())
            await self.publish(None)
            _live.pop(self.symbol, None)

    def _store(self, completed: bool, started: float, costs: dict[str, Any]) -> None:
        """Save the finished run (or refund a failed one) and log its cost. Runs on a worker thread."""
        try:
            if completed:
                cache.save_run(self.symbol, self.events, self.depth)
                cache.record_verdict(self.events[-1]["run"])
                if self.user_id:
                    cache.save_for_user(self.user_id, self.symbol, self.events)
            elif self.invite_code:
                cache.refund_credit(self.invite_code, self.credits)  # don't charge for a run that failed
            elif self.user_id and self.credits:
                cache.refund_account_credits(self.user_id, self.credits)
        except Exception:  # noqa: BLE001 - storage hiccups must not leave followers hanging
            pass
        try:
            cache.record_usage(
                self.symbol,
                started,
                "done" if completed else "failed",
                self.invite_code,
                costs,
                self.depth,
                self.user_id,
            )
        except Exception:  # noqa: BLE001 - accounting must never break a run
            pass

    async def follow(self) -> AsyncIterator[dict[str, Any]]:
        sent = 0
        while True:
            async with self.changed:
                await self.changed.wait_for(lambda n=sent: len(self.events) > n or self.done)
                batch, finished = self.events[sent:], self.done
            for event in batch:
                yield event
            sent += len(batch)
            if finished and sent == len(self.events):
                return


_live: dict[str, LiveRun] = {}


@app.get("/api/analyze/{ticker}")
async def analyze(
    ticker: str, request: Request, refresh: bool = False, code: str | None = None, depth: str | None = None
) -> StreamingResponse:
    symbol = _ticker(ticker)
    profile = get_depth(depth)
    live = _live.get(symbol)
    # Storage calls run on a worker thread so a slow database never freezes the whole server.
    cached = None if (refresh or live) else await asyncio.to_thread(cache.get_run, symbol, profile.id)
    live = live or _live.get(symbol)  # a run may have started while we looked
    refusal: AccessDenied | None = None
    if live is None and cached is None and settings.access_mode == "accounts":
        # With accounts, fresh runs start only through POST /api/analyze/{ticker}/start (signed in).
        refusal = AccessDenied("sign_in", "Sign in to run a fresh analysis.")
    elif live is None and cached is None:
        # A fresh run costs money: check the invite, the per-visitor and daily limits, then charge its credits.
        try:
            invite = await asyncio.to_thread(_check_invite, code, profile.credits)
            _check_rate_limit(_client_ip(request))
            _check_daily_budget()
            if invite and not await asyncio.to_thread(cache.consume_credit, invite["code"], profile.credits):
                raise AccessDenied("no_credits", "You don't have enough credits left for this depth.")
        except AccessDenied as exc:
            refusal = exc
        else:
            charged = profile.credits if invite else 0
            if symbol in _live:  # someone else started it meanwhile: follow theirs, refund ours
                live = _live[symbol]
                if charged:
                    await asyncio.to_thread(cache.refund_credit, invite["code"], charged)
            else:
                live = _live[symbol] = LiveRun(symbol, invite["code"] if invite else None, profile.id, charged)
                live.task = asyncio.create_task(live.drive())

    async def stream() -> AsyncIterator[str]:
        if refusal is not None:
            # Browsers' EventSource can't read an error status, so send the reason as an event.
            yield _sse({"type": "error", "message": refusal.message, "reason": refusal.reason})
            return
        if cached is not None:
            for event in cached:
                yield _sse({**event, "cached": True})
            return
        assert live is not None
        async for event in live.follow():
            yield _sse(event)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.post("/api/analyze/{ticker}/start")
async def start_analysis(
    ticker: str, request: Request, depth: str | None = None, user: User = Depends(require_user)
) -> dict[str, Any]:
    """Start a fresh, paid run for a signed-in user (or report that it's already running / cached)."""
    symbol = _ticker(ticker)
    profile = get_depth(depth)
    if symbol in _live:
        return {"state": "running", "depth": _live[symbol].depth}
    if await asyncio.to_thread(cache.get_run, symbol, profile.id) is not None:
        return {"state": "cached"}
    account = await asyncio.to_thread(_account_for, user)
    try:
        if account["remaining"] < profile.credits:
            raise AccessDenied("no_credits", "You don't have enough credits for this depth.")
        _check_rate_limit(f"user:{user.id}")
        _check_rate_limit(_client_ip(request))
        _check_daily_budget()
        if not await asyncio.to_thread(cache.consume_account_credits, user.id, profile.credits):
            raise AccessDenied("no_credits", "You don't have enough credits for this depth.")
    except AccessDenied as exc:
        raise HTTPException(
            402 if exc.reason == "no_credits" else 429, {"reason": exc.reason, "message": exc.message}
        ) from exc
    if symbol in _live:  # someone else started it while we were charging: refund, follow theirs
        await asyncio.to_thread(cache.refund_account_credits, user.id, profile.credits)
        return {"state": "running", "depth": _live[symbol].depth, "remaining": account["remaining"]}
    live = _live[symbol] = LiveRun(symbol, None, profile.id, profile.credits, user.id)
    live.task = asyncio.create_task(live.drive())
    return {"state": "started", "depth": profile.id, "remaining": account["remaining"] - profile.credits}


# ---------------------------------------------------------------------------
# Signed-in user: account, credits, saved research
# ---------------------------------------------------------------------------


class Redeem(BaseModel):
    code: str = Field(min_length=4, max_length=40)


class SaveCached(BaseModel):
    ticker: str
    depth: str | None = None


class ImportEntry(BaseModel):
    ticker: str
    events: list[dict[str, Any]] = Field(max_length=200)


class ImportBody(BaseModel):
    entries: list[ImportEntry] = Field(max_length=25)


@app.get("/api/me")
def me(user: User = Depends(require_user)) -> dict[str, Any]:
    account = _account_for(user)
    return {**account, "is_admin": user.is_admin, "free_credits": settings.free_credits}


@app.post("/api/me/redeem")
def redeem(body: Redeem, user: User = Depends(require_user)) -> dict[str, Any]:
    _account_for(user)
    added, error = cache.redeem_invite(user.id, body.code)
    if error:
        raise HTTPException(400, error)
    return {"added": added, **(cache.get_account(user.id) or {})}


@app.get("/api/me/history")
def my_history(user: User = Depends(require_user)) -> list[dict[str, Any]]:
    return cache.list_saved(user.id)


@app.get("/api/me/history/{rid}")
def my_saved_run(rid: str, user: User = Depends(require_user)) -> dict[str, Any]:
    run = cache.get_saved(user.id, rid)
    if not run:
        raise HTTPException(404, "Not found.")
    return run


@app.delete("/api/me/history/{rid}")
def delete_my_run(rid: str, user: User = Depends(require_user)) -> dict[str, bool]:
    cache.delete_saved(user.id, None if rid == "all" else rid)
    return {"ok": True}


@app.post("/api/me/history/save")
def save_cached_for_me(body: SaveCached, user: User = Depends(require_user)) -> dict[str, Any]:
    """Keep a copy of a recently analyzed (cached) stock in this account's history."""
    events = cache.get_run(_ticker(body.ticker), get_depth(body.depth).id if body.depth else "quick")
    if not events:
        raise HTTPException(404, "No recent analysis to save.")
    return {"id": cache.save_for_user(user.id, _ticker(body.ticker), events)}


@app.post("/api/me/history/import")
def import_history(body: ImportBody, user: User = Depends(require_user)) -> dict[str, int]:
    """Move reports saved in this browser (before signing in) into the account."""
    saved = 0
    for entry in body.entries:
        if len(json.dumps(entry.events)) > 2_000_000:
            continue
        if cache.save_for_user(user.id, _ticker(entry.ticker), entry.events):
            saved += 1
    return {"imported": saved}


# ---------------------------------------------------------------------------
# Admin: costs and invite codes (requires ADMIN_KEY)
# ---------------------------------------------------------------------------


def _require_admin(key: str | None, authorization: str | None = None) -> None:
    """Admin = the ADMIN_KEY header, or a signed-in user whose email is in ADMIN_EMAILS."""
    if key and settings.admin_key and hmac.compare_digest(key, settings.admin_key):
        return
    if authorization and authorization.lower().startswith("bearer ") and verify_token(authorization[7:]).is_admin:
        return
    if not settings.admin_key and not settings.admin_emails:
        raise HTTPException(404, "Admin is disabled (set ADMIN_KEY or ADMIN_EMAILS).")
    raise HTTPException(401, "Not an admin.")


class NewInvite(BaseModel):
    label: str = Field(default="", max_length=80)
    credits: int | None = Field(default=None, ge=1, le=10_000)


class InviteChange(BaseModel):
    add_credits: int = Field(default=0, ge=-10_000, le=10_000)
    disabled: bool | None = None


@app.get("/api/admin/stats")
def admin_stats(
    x_admin_key: str | None = Header(default=None), authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    _require_admin(x_admin_key, authorization)
    return {
        **cache.usage_stats(),
        "live_runs": list(_live),
        "runs_started_today": sum(_daily_runs.values()),
        "settings": {
            "model": settings.claude_model,
            "access_mode": settings.access_mode,
            "max_runs_per_day": settings.max_runs_per_day,
            "rate_limit_per_hour": settings.rate_limit_per_hour,
            "cache_ttl_hours": settings.cache_ttl_hours,
            "default_invite_credits": settings.default_invite_credits,
            "free_credits": settings.free_credits,
            "free_signups_per_day": settings.free_signups_per_day,
        },
    }


@app.get("/api/admin/invites")
def admin_list_invites(
    x_admin_key: str | None = Header(default=None), authorization: str | None = Header(default=None)
) -> list[dict[str, Any]]:
    _require_admin(x_admin_key, authorization)
    return cache.list_invites()


@app.post("/api/admin/invites")
def admin_create_invite(
    body: NewInvite, x_admin_key: str | None = Header(default=None), authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    _require_admin(x_admin_key, authorization)
    return cache.create_invite(body.label.strip(), body.credits or settings.default_invite_credits)


@app.post("/api/admin/invites/{code}")
def admin_update_invite(
    code: str,
    body: InviteChange,
    x_admin_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_admin(x_admin_key, authorization)
    invite = cache.update_invite(code, add_credits=body.add_credits, disabled=body.disabled)
    if not invite:
        raise HTTPException(404, "No such invite code.")
    return invite


class CreditChange(BaseModel):
    add: int = Field(ge=-10_000, le=10_000)


@app.get("/api/admin/accounts")
def admin_accounts(
    x_admin_key: str | None = Header(default=None), authorization: str | None = Header(default=None)
) -> list[dict[str, Any]]:
    _require_admin(x_admin_key, authorization)
    return cache.list_accounts()


@app.post("/api/admin/accounts/{user_id}/credits")
def admin_account_credits(
    user_id: str,
    body: CreditChange,
    x_admin_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_admin(x_admin_key, authorization)
    account = cache.add_account_credits(user_id, body.add)
    if not account:
        raise HTTPException(404, "No such account.")
    return account
