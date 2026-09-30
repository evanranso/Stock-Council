"""Stages 2-4: bull and bear advocates, the challenger, and the judge.

None of these agents see raw data, only the specialists' written reports, so
the debate is about the evidence the specialists surfaced.
"""

from __future__ import annotations

import json

from ..schemas import AnalystReport, CaseReport, ChallengeReport, Horizon, HorizonScore, JudgeRuling
from ..scoring import LEAN_THRESHOLD, MAX_JUDGE_ADJUSTMENT, STRONG_THRESHOLD
from .llm import structured

HORIZONS = "weeks (1-4 weeks), months (1-6 months), and years (1-3 years)"


def render_reports(reports: list[AnalystReport]) -> str:
    blocks = []
    for r in reports:
        if r.opinion is None:
            blocks.append(f'<report analyst_id="{r.analyst_id}" name="{r.analyst_name}">NO OPINION: {r.error}</report>')
        else:
            body = json.dumps(r.opinion.model_dump(), separators=(",", ":"))
            blocks.append(
                f'<report analyst_id="{r.analyst_id}" name="{r.analyst_name}" data="{r.packet_status}">{body}</report>'
            )
    return "\n".join(blocks)


def _advocate_prompt(side: str) -> str:
    other = "bear" if side == "bull" else "bull"
    return f"""\
You are the {side.upper()} advocate on an investment council. Twelve independent
specialists each studied one slice of data about a stock. Build the strongest
honest {side} case from their reports.

Rules:
- Use only what the reports contain. Cite analyst_ids for every argument.
- Prefer evidence from several independent analysts over one loud one.
- Do not misstate an analyst's view. If a {other}ish analyst's finding can be
  fairly read in your favor, explain why; don't pretend it isn't {other}ish.
- Cover the horizons: {HORIZONS}.
- Be candid in weakest_point. An advocate who hides their weak spot loses the room.
"""


CHALLENGER_PROMPT = f"""\
You are the CHALLENGER on an investment council. Your only job is to object
when a lean doesn't hold up. You are not bullish or bearish.

You will see twelve specialist reports, the bull case, and the bear case.
Attack weak reasoning wherever it is:
- Claims that cite an analyst who didn't actually say that, or overstate conviction.
- Arguments built on thin, stale, or 'partial'/'poor' data.
- Echo chamber: several arguments that are really the same underlying fact
  counted multiple times (e.g. price momentum, analyst upgrades, and bullish
  news all reacting to the same earnings beat). Name the shared root.
- Horizon mixing: short-term signals used to justify long-term claims or vice versa.
- Specialists whose horizon views don't follow from their own findings.

Your objections change the numbers. The verdict is computed by a formula over
each analyst's per-horizon lean and conviction:
- For each objection, list the analyst_ids it undermines in affected_analysts
  and the horizons it applies to. 'high' halves that analyst's weight, 'medium'
  cuts it 20%, 'low' is noted only. An objection to an advocate's framing
  affects no analyst unless the underlying analyst view is itself wrong.
- Report every echo chamber as a shared_evidence group; each group is
  collapsed so it counts as one analyst.
Be precise and fair: penalize only what is actually weak, and say which leans
survive scrutiny. Horizons in play: {HORIZONS}.
"""

JUDGE_PROMPT = f"""\
You are the JUDGE of an investment council. You have twelve independent
specialist reports, a bull case, a bear case, the challenger's objections, and
the council's FORMULA SCORES: for each horizon ({HORIZONS}), a score from -100
(strongly bearish) to +100 (strongly bullish) computed from the analysts'
convictions, weighted by relevance and data quality, after the challenger's
penalties.

Your job is to check the formula and explain the result:
- You may adjust each horizon's score by at most {MAX_JUDGE_ADJUSTMENT} points
  either way. Adjust only for something the formula cannot see: a single
  finding that should dominate (e.g. going-concern language in a filing), an
  objection the formula over- or under-penalized, or a contribution that
  misreads the reports. Otherwise use 0 and say "Formula stands."
- The rating and leans are derived from the final numbers (|score| below
  {LEAN_THRESHOLD} is neutral/Hold, {STRONG_THRESHOLD}+ is strong). Argue for the number, not a label.
- Explain each horizon in plain English, including its main drivers.
- List dissenting analysts as "analyst_id: reason".
- Write the summary for a smart non-professional investor. No hype.
This is research, not personalized financial advice.
"""


async def advocate(
    side: str, ticker: str, reports: list[AnalystReport], effort: str, model: str | None = None
) -> CaseReport:
    user = (
        f"Ticker: {ticker}\n\n<specialist_reports>\n{render_reports(reports)}\n</specialist_reports>\n\n"
        f"Make the {side} case."
    )
    return await structured(_advocate_prompt(side), user, CaseReport, effort, label=side, model=model)


async def challenge(
    ticker: str,
    reports: list[AnalystReport],
    bull: CaseReport,
    bear: CaseReport,
    effort: str,
    model: str | None = None,
) -> ChallengeReport:
    user = (
        f"Ticker: {ticker}\n\n<specialist_reports>\n{render_reports(reports)}\n</specialist_reports>\n\n"
        f"<bull_case>{bull.model_dump_json()}</bull_case>\n\n<bear_case>{bear.model_dump_json()}</bear_case>\n\n"
        "Challenge every lean that doesn't hold up."
    )
    return await structured(CHALLENGER_PROMPT, user, ChallengeReport, effort, label="challenger", model=model)


def render_scores(scores: dict[Horizon, HorizonScore]) -> str:
    lines = []
    for h, s in scores.items():
        lines.append(
            f"{h}: score {s.score:+.1f}, confidence {s.confidence}, "
            f"evidence {s.evidence:.2f}, agreement {s.agreement:.2f}"
        )
        for c in s.contributions:
            penalties = f" | penalties: {'; '.join(c.penalties)}" if c.penalties else ""
            lines.append(
                f"  {c.analyst_id}: {c.lean} {c.conviction}, weight {c.weight}, points {c.points:+.1f}{penalties}"
            )
    return "\n".join(lines)


async def judge(
    ticker: str,
    reports: list[AnalystReport],
    bull: CaseReport,
    bear: CaseReport,
    objections: ChallengeReport,
    scores: dict[Horizon, HorizonScore],
    effort: str,
    model: str | None = None,
) -> JudgeRuling:
    user = (
        f"Ticker: {ticker}\n\n<specialist_reports>\n{render_reports(reports)}\n</specialist_reports>\n\n"
        f"<bull_case>{bull.model_dump_json()}</bull_case>\n\n<bear_case>{bear.model_dump_json()}</bear_case>\n\n"
        f"<challenger>{objections.model_dump_json()}</challenger>\n\n"
        f"<formula_scores>\n{render_scores(scores)}\n</formula_scores>\n\nDeliver your ruling."
    )
    return await structured(JUDGE_PROMPT, user, JudgeRuling, effort, label="judge", model=model)
