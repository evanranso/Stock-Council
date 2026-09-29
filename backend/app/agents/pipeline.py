"""Runs the full council and yields progress events as each piece finishes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from ..config import get_settings
from ..data import _yf
from ..data.base import in_thread
from ..data.registry import ADAPTERS
from ..schemas import AnalystReport, CouncilRun, DataPacket
from . import debate
from .specialists import SPECIALISTS, run_specialist

Event = dict[str, Any]


async def run_council(ticker: str) -> AsyncIterator[Event]:
    settings = get_settings()
    info = await in_thread(_yf.info, ticker)
    run = CouncilRun(
        ticker=ticker,
        company_name=info.get("longName") or info.get("shortName"),
        started_at=datetime.now(UTC),
        model=settings.claude_model,
    )
    yield {
        "type": "start",
        "ticker": ticker,
        "company_name": run.company_name,
        "analysts": [{"id": s.id, "name": s.name} for s in SPECIALISTS],
    }

    # Stage 1: fetch each packet and run its specialist; all 12 in parallel, fully isolated.
    limit = asyncio.Semaphore(settings.max_parallel_agents)

    async def one(spec) -> tuple[DataPacket, AnalystReport]:
        packet = await ADAPTERS[spec.segment](ticker)
        async with limit:
            return packet, await run_specialist(spec, packet, settings.specialist_effort)

    tasks = [asyncio.create_task(one(s)) for s in SPECIALISTS]
    for done in asyncio.as_completed(tasks):
        packet, report = await done
        run.analysts.append(report)
        yield {
            "type": "analyst",
            "report": report.model_dump(mode="json"),
            "sources": packet.sources,
            "notes": packet.notes,
        }

    order = {s.id: i for i, s in enumerate(SPECIALISTS)}
    run.analysts.sort(key=lambda r: order[r.analyst_id])
    if sum(r.opinion is not None for r in run.analysts) < 3:
        yield {"type": "error", "message": "Too few analysts could form an opinion to hold a debate."}
        return

    # Stage 2: bull and bear build their cases independently of each other.
    yield {"type": "stage", "stage": "debate"}
    effort = settings.debate_effort
    run.bull, run.bear = await asyncio.gather(
        debate.advocate("bull", ticker, run.analysts, effort),
        debate.advocate("bear", ticker, run.analysts, effort),
    )
    yield {"type": "case", "side": "bull", "case": run.bull.model_dump(mode="json")}
    yield {"type": "case", "side": "bear", "case": run.bear.model_dump(mode="json")}

    # Stage 3: the challenger objects to whatever doesn't hold up.
    yield {"type": "stage", "stage": "challenge"}
    run.challenge = await debate.challenge(ticker, run.analysts, run.bull, run.bear, effort)
    yield {"type": "challenge", "challenge": run.challenge.model_dump(mode="json")}

    # Stage 4: the verdict.
    yield {"type": "stage", "stage": "verdict"}
    run.verdict = await debate.judge(ticker, run.analysts, run.bull, run.bear, run.challenge, effort)
    run.finished_at = datetime.now(UTC)
    yield {"type": "verdict", "verdict": run.verdict.model_dump(mode="json")}
    yield {"type": "done", "run": run.model_dump(mode="json")}
