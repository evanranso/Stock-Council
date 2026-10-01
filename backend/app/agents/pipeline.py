"""Runs the full council and yields progress events as each piece finishes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from .. import scoring, usage
from ..config import get_settings
from ..data import _yf, sec
from ..data.base import in_thread
from ..data.highlights import highlights, scope
from ..data.registry import ADAPTERS
from ..depth import get_depth
from ..schemas import AnalystReport, CouncilRun, DataPacket, HorizonScore
from . import debate
from .specialists import SPECIALISTS, run_specialist

Event = dict[str, Any]


async def run_council(ticker: str, depth: str | None = None) -> AsyncIterator[Event]:
    settings = get_settings()
    profile = get_depth(depth)
    run = CouncilRun(
        ticker=ticker,
        company_name=await _company_name(ticker),
        started_at=datetime.now(UTC),
        model=profile.debate_model,
        depth=profile.id,
    )
    yield {
        "type": "start",
        "ticker": ticker,
        "company_name": run.company_name,
        "depth": profile.id,
        "analysts": [{"id": s.id, "name": s.name} for s in SPECIALISTS],
    }

    # Stage 1: fetch each packet and run its specialist; all 12 in parallel, fully isolated.
    # Each analyst also reports what it's doing ("fetching", "fetched" with what it found,
    # "reading"), so people can watch the research happen instead of a spinner.
    limit = asyncio.Semaphore(settings.max_parallel_agents)
    feed: asyncio.Queue[Event] = asyncio.Queue()

    def step(spec_id: str, name: str, **extra: Any) -> None:
        feed.put_nowait({"type": "analyst_progress", "analyst_id": spec_id, "step": name, **extra})

    async def one(spec) -> tuple[DataPacket, AnalystReport]:
        step(spec.id, "fetching")
        packet = await ADAPTERS[spec.segment](ticker)
        step(
            spec.id,
            "fetched",
            status=packet.status,
            sources=packet.sources,
            found=scope(packet),
            metrics=[m.model_dump() if hasattr(m, "model_dump") else m for m in highlights(packet)["metrics"][:2]],
        )
        async with limit:
            if packet.status != "unavailable":
                step(spec.id, "reading")
            return packet, await run_specialist(spec, packet, profile.analyst_effort, profile.analyst_model)

    async def run_one(spec) -> None:
        try:
            packet, report = await one(spec)
        except Exception as exc:  # noqa: BLE001 - adapters are guarded; this is a last resort
            packet = DataPacket(segment=spec.segment, ticker=ticker, status="unavailable", notes=[str(exc)])
            report = AnalystReport(
                analyst_id=spec.id, analyst_name=spec.name, packet_status="unavailable", error=str(exc)
            )
        feed.put_nowait({"type": "_done", "packet": packet, "report": report})

    tasks = [asyncio.create_task(run_one(s)) for s in SPECIALISTS]
    remaining = len(tasks)
    while remaining:
        event = await feed.get()
        if event["type"] != "_done":
            yield event
            continue
        remaining -= 1
        packet, report = event["packet"], event["report"]
        run.analysts.append(report)
        if packet.segment == "price":
            # Logged with the verdict so later runs can check how the call played out.
            run.reference_price = packet.data.get("last_close")
        yield {
            "type": "analyst",
            "report": report.model_dump(mode="json"),
            "sources": packet.sources,
            "notes": packet.notes,
            "as_of": packet.as_of.isoformat(),
            "highlights": highlights(packet),
        }

    order = {s.id: i for i, s in enumerate(SPECIALISTS)}
    run.analysts.sort(key=lambda r: order[r.analyst_id])
    if sum(r.opinion is not None for r in run.analysts) < 3:
        yield {"type": "error", "message": "Too few analysts could form an opinion to hold a debate."}
        return

    # The raw formula, before the debate touches it.
    baseline = scoring.score_all(run.analysts)
    yield {"type": "scores", "phase": "baseline", "scores": _dump(baseline)}

    # Stage 2: bull and bear build their cases independently of each other.
    yield {"type": "stage", "stage": "debate"}
    effort, model = profile.debate_effort, profile.debate_model
    run.bull, run.bear = await asyncio.gather(
        debate.advocate("bull", ticker, run.analysts, effort, model),
        debate.advocate("bear", ticker, run.analysts, effort, model),
    )
    yield {"type": "case", "side": "bull", "case": run.bull.model_dump(mode="json")}
    yield {"type": "case", "side": "bear", "case": run.bear.model_dump(mode="json")}

    # Stage 3: the challenger objects to whatever doesn't hold up.
    yield {"type": "stage", "stage": "challenge"}
    run.challenge = await debate.challenge(ticker, run.analysts, run.bull, run.bear, effort, model)
    yield {"type": "challenge", "challenge": run.challenge.model_dump(mode="json")}

    # The formula again, with the challenger's penalties and echo-chamber collapses applied.
    adjusted = scoring.score_all(run.analysts, run.challenge)
    yield {"type": "scores", "phase": "adjusted", "scores": _dump(adjusted)}

    # Stage 4: the judge may nudge each horizon within a fixed band; the rating comes from the numbers.
    yield {"type": "stage", "stage": "verdict"}
    ruling = await debate.judge(ticker, run.analysts, run.bull, run.bear, run.challenge, adjusted, effort, model)
    run.verdict = scoring.assemble_verdict(adjusted, ruling)
    run.finished_at = datetime.now(UTC)
    tracker = usage.current()
    run.usage = tracker.summary() if tracker else None
    yield {"type": "verdict", "verdict": run.verdict.model_dump(mode="json")}
    yield {"type": "done", "run": run.model_dump(mode="json")}


async def _company_name(ticker: str) -> str | None:
    try:
        company = await sec.company_info(ticker)
        if company and company.get("name"):
            return company["name"]
    except Exception:  # noqa: BLE001 - the name is cosmetic; fall back to Yahoo
        pass
    info = await in_thread(_yf.info, ticker)
    return info.get("longName") or info.get("shortName")


def _dump(scores: dict[str, HorizonScore]) -> dict[str, Any]:
    return {h: s.model_dump(mode="json") for h, s in scores.items()}
