"""HTTP API. Run with: uvicorn app.main:app --reload"""

from __future__ import annotations

import asyncio
import hmac
import json
import re
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import cache, search, usage
from .agents.pipeline import run_council
from .agents.specialists import SPECIALISTS
from .config import get_settings
from .data.registry import ADAPTERS
from .depth import DEFAULT_DEPTH, all_depths, get_depth

app = FastAPI(title="Stock Council API")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Key"],
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
async def health() -> dict[str, Any]:
    return {"ok": True, "model": settings.claude_model}


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
    return await search.search(q[:60], min(max(limit, 1), 20))


# ---------------------------------------------------------------------------
# Access: credits and what's free to view
# ---------------------------------------------------------------------------


def _public_invite(invite: dict[str, Any] | None) -> dict[str, Any] | None:
    if not invite:
        return None
    return {k: invite[k] for k in ("code", "label", "credits_total", "credits_used", "remaining", "disabled")}


@app.get("/api/access")
async def access(code: str | None = None) -> dict[str, Any]:
    """What this visitor can do: access mode and, with a code, their credits."""
    invite = cache.get_invite(code)
    return {
        "mode": settings.access_mode,
        "invite": _public_invite(invite),
        "valid": bool(invite and not invite["disabled"]),
        "depths": [d.public() for d in all_depths()],
        "default_depth": DEFAULT_DEPTH,
    }


@app.get("/api/status/{ticker}")
async def status(ticker: str, code: str | None = None, depth: str | None = None) -> dict[str, Any]:
    """Would opening this ticker at this depth be free (running, or recently analyzed at least this deep)?"""
    symbol = _ticker(ticker)
    profile = get_depth(depth)
    if symbol in _live:
        return {"free": True, "reason": "running", "depth": _live[symbol].depth}
    if cache.get_run(symbol, profile.id) is not None:
        return {"free": True, "reason": "cached"}
    invite = cache.get_invite(code)
    return {
        "free": False,
        "reason": None,
        "mode": settings.access_mode,
        "invite": _public_invite(invite),
        "depths": [d.public() for d in all_depths()],
    }


@app.get("/api/recent")
async def recent() -> list[dict[str, Any]]:
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
        self, symbol: str, invite_code: str | None = None, depth: str = DEFAULT_DEPTH, credits: int = 0
    ) -> None:
        self.symbol = symbol
        self.invite_code = invite_code
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
            if completed:
                cache.save_run(self.symbol, self.events, self.depth)
                cache.record_verdict(self.events[-1]["run"])
            elif self.invite_code:
                cache.refund_credit(self.invite_code, self.credits)  # don't charge for a run that failed
            try:
                cache.record_usage(
                    self.symbol,
                    started,
                    "done" if completed else "failed",
                    self.invite_code,
                    tracker.summary(),
                    self.depth,
                )
            except Exception:  # noqa: BLE001 - accounting must never break a run
                pass
            await self.publish(None)
            _live.pop(self.symbol, None)

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
    cached = None if (refresh or live) else cache.get_run(symbol, profile.id)
    refusal: AccessDenied | None = None
    if live is None and cached is None:
        # A fresh run costs money: check the invite, the per-visitor and daily limits, then charge its credits.
        try:
            invite = _check_invite(code, profile.credits)
            _check_rate_limit(_client_ip(request))
            _check_daily_budget()
            if invite and not cache.consume_credit(invite["code"], profile.credits):
                raise AccessDenied("no_credits", "You don't have enough credits left for this depth.")
        except AccessDenied as exc:
            refusal = exc
        else:
            charged = profile.credits if invite else 0
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


# ---------------------------------------------------------------------------
# Admin: costs and invite codes (requires ADMIN_KEY)
# ---------------------------------------------------------------------------


def _require_admin(key: str | None) -> None:
    if not settings.admin_key:
        raise HTTPException(404, "Admin is disabled (set ADMIN_KEY).")
    if not key or not hmac.compare_digest(key, settings.admin_key):
        raise HTTPException(401, "Wrong admin key.")


class NewInvite(BaseModel):
    label: str = Field(default="", max_length=80)
    credits: int | None = Field(default=None, ge=1, le=10_000)


class InviteChange(BaseModel):
    add_credits: int = Field(default=0, ge=-10_000, le=10_000)
    disabled: bool | None = None


@app.get("/api/admin/stats")
async def admin_stats(x_admin_key: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_admin_key)
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
        },
    }


@app.get("/api/admin/invites")
async def admin_list_invites(x_admin_key: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _require_admin(x_admin_key)
    return cache.list_invites()


@app.post("/api/admin/invites")
async def admin_create_invite(body: NewInvite, x_admin_key: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_admin_key)
    return cache.create_invite(body.label.strip(), body.credits or settings.default_invite_credits)


@app.post("/api/admin/invites/{code}")
async def admin_update_invite(
    code: str, body: InviteChange, x_admin_key: str | None = Header(default=None)
) -> dict[str, Any]:
    _require_admin(x_admin_key)
    invite = cache.update_invite(code, add_credits=body.add_credits, disabled=body.disabled)
    if not invite:
        raise HTTPException(404, "No such invite code.")
    return invite
