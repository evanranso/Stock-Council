"""Stages 2-4: bull and bear advocates, the challenger, and the judge.

None of these agents see raw data, only the specialists' written reports, so
the debate is about the evidence the specialists surfaced.
"""

from __future__ import annotations

import json

from ..schemas import AnalystReport, CaseReport, ChallengeReport, Verdict
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
- Specialists whose stance doesn't follow from their own findings.
Also say which leans survive scrutiny. Severity 'high' means the claim should
not carry weight in the verdict. Horizons in play: {HORIZONS}.
"""

JUDGE_PROMPT = f"""\
You are the JUDGE of an investment council. You have twelve independent
specialist reports, a bull case, a bear case, and a challenger's objections.
Deliver the verdict.

- Weigh evidence, not votes. Six weak neutral reports do not outweigh one
  strong, well-evidenced finding; claims the challenger rated 'high' severity
  should carry little weight unless you explain why the objection fails.
- Give a separate lean and confidence for each horizon: {HORIZONS}. It is
  normal for them to differ.
- Confidence must reflect data quality and disagreement. Missing analysts and
  split councils should lower it.
- List dissenting analysts by analyst_id with a short reason.
- Write the summary for a smart non-professional investor. No hype.
This is research, not personalized financial advice.
"""


async def advocate(side: str, ticker: str, reports: list[AnalystReport], effort: str) -> CaseReport:
    user = (
        f"Ticker: {ticker}\n\n<specialist_reports>\n{render_reports(reports)}\n</specialist_reports>\n\n"
        f"Make the {side} case."
    )
    return await structured(_advocate_prompt(side), user, CaseReport, effort)


async def challenge(
    ticker: str, reports: list[AnalystReport], bull: CaseReport, bear: CaseReport, effort: str
) -> ChallengeReport:
    user = (
        f"Ticker: {ticker}\n\n<specialist_reports>\n{render_reports(reports)}\n</specialist_reports>\n\n"
        f"<bull_case>{bull.model_dump_json()}</bull_case>\n\n<bear_case>{bear.model_dump_json()}</bear_case>\n\n"
        "Challenge every lean that doesn't hold up."
    )
    return await structured(CHALLENGER_PROMPT, user, ChallengeReport, effort)


async def judge(
    ticker: str,
    reports: list[AnalystReport],
    bull: CaseReport,
    bear: CaseReport,
    objections: ChallengeReport,
    effort: str,
) -> Verdict:
    user = (
        f"Ticker: {ticker}\n\n<specialist_reports>\n{render_reports(reports)}\n</specialist_reports>\n\n"
        f"<bull_case>{bull.model_dump_json()}</bull_case>\n\n<bear_case>{bear.model_dump_json()}</bear_case>\n\n"
        f"<challenger>{objections.model_dump_json()}</challenger>\n\nDeliver the verdict."
    )
    return await structured(JUDGE_PROMPT, user, Verdict, effort)
