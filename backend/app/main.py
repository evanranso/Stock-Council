"""HTTP API. Run with: uvicorn app.main:app --reload"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import cache
from .agents.pipeline import run_council
from .agents.specialists import SPECIALISTS
from .config import get_settings
from .data.registry import ADAPTERS

app = FastAPI(title="Stock Council API")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex,
    allow_methods=["GET"],
    allow_headers=["*"],
)

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_recent_runs: dict[str, deque[float]] = defaultdict(deque)
_daily_runs: dict[str, int] = {}


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
        raise HTTPException(
            429, "The council has hit today's analysis limit. Cached tickers still work; try again tomorrow."
        )
    if today not in _daily_runs:
        _daily_runs.clear()  # drop previous days
    _daily_runs[today] = _daily_runs.get(today, 0) + 1


def _ticker(raw: str) -> str:
    t = raw.strip().upper()
    if not TICKER_RE.match(t):
        raise HTTPException(400, "Invalid ticker symbol.")
    return t


def _check_rate_limit(ip: str) -> None:
    window = _recent_runs[ip]
    now = time.time()
    while window and now - window[0] > 3600:
        window.popleft()
    if len(window) >= settings.rate_limit_per_hour:
        raise HTTPException(429, "Rate limit reached. Try again later, or look up a ticker someone already ran.")
    window.append(now)


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


@app.get("/api/analyze/{ticker}")
async def analyze(ticker: str, request: Request, refresh: bool = False) -> StreamingResponse:
    symbol = _ticker(ticker)
    cached = None if refresh else cache.get_run(symbol)
    refusal: str | None = None
    if cached is None:
        try:
            _check_rate_limit(_client_ip(request))
            _check_daily_budget()
        except HTTPException as exc:
            # Browsers' EventSource can't read an error status, so send the reason as an event.
            refusal = str(exc.detail)

    async def stream() -> AsyncIterator[str]:
        if refusal is not None:
            yield _sse({"type": "error", "message": refusal})
            return
        if cached is not None:
            for event in cached:
                yield _sse({**event, "cached": True})
            return
        events: list[dict[str, Any]] = []
        try:
            async for event in run_council(symbol):
                events.append(event)
                yield _sse(event)
        except Exception as exc:  # noqa: BLE001 - surface failures to the UI instead of a dead stream
            yield _sse({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
            return
        if events and events[-1]["type"] == "done":
            cache.save_run(symbol, events)
            cache.record_verdict(events[-1]["run"])

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
