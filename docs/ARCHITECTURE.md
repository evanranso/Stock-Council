# Architecture

## Principles

1. **Isolation before debate.** Each specialist gets one `DataPacket` and a system prompt that forbids
   outside knowledge. No specialist sees another's data or opinion. This is enforced in code (one API
   call per specialist, built only from its packet) and covered by `tests/test_pipeline.py`.
2. **Evidence, not votes.** Bull and bear advocates build from the specialists' written reports and must
   cite `analyst_id`s. The challenger hunts for overstated claims, stale or thin data, horizon mixing, and
   **echo chambers** (several arguments that are really one underlying fact). The judge weighs evidence
   and the challenger's objections, not a head count.
3. **Honest gaps.** If a source is down or needs a paid plan, the adapter returns `status="unavailable"`
   and the specialist is skipped (no model call, no invented opinion). The UI shows "no data".
4. **Structured everything.** Every agent returns a Pydantic schema via structured outputs, so the UI
   renders reliably and runs can be cached and compared.

## Pipeline

```
run_council(ticker)
 ├─ stage 1: for each of 12 specialists (parallel, capped by MAX_PARALLEL_AGENTS)
 │     packet = ADAPTERS[segment](ticker)   -> DataPacket
 │     opinion = Claude(system=persona, user=packet) -> AnalystOpinion
 ├─ stage 2: bull, bear = Claude(reports) in parallel -> CaseReport x2
 ├─ stage 3: challenge = Claude(reports, bull, bear)  -> ChallengeReport
 └─ stage 4: verdict = Claude(reports, bull, bear, challenge) -> Verdict
```

Events streamed to the browser (SSE): `start`, `analyst` (x12), `stage`, `case` (x2), `challenge`,
`verdict`, `done`, or `error`.

## Data sources (free tier)

| Segment | Source | Key needed | Notes |
|---|---|---|---|
| price | Yahoo Finance via `yfinance` | no | indicators computed in `data/indicators.py` |
| financials | SEC XBRL company facts + Yahoo valuation | no | annual 10-K values, 5 years |
| analysts | Yahoo + Finnhub recommendation trend | Finnhub optional | |
| earnings | Yahoo estimates/revisions + Finnhub surprises | Finnhub optional | |
| insiders | Finnhub insider transactions (Form 4) | Finnhub (falls back to Yahoo) | open-market P/S separated from grants |
| congress | Finnhub congressional trading | **paid plan** | no reliable free source; reports gap honestly |
| news | Finnhub company news | Finnhub (falls back to Yahoo) | last 21 days |
| filings | SEC EDGAR submissions + documents | no | risk factors, MD&A, recent 8-Ks |
| institutions | Yahoo (13F-derived) + short interest | no | up to a quarter stale |
| options | Yahoo option chains | no | delayed |
| economy | FRED | FRED (free) | 12 series |
| related | Yahoo + Finnhub peers | Finnhub optional | beta/correlation vs sector, peers, macro |

Paid upgrades to consider later, each behind the same adapter interface: Polygon or FMP (prices,
fundamentals), Quiver Quantitative (congress, lobbying), ORATS or Unusual Whales (options flow).

## Model and cost

- Default model `claude-opus-5-5` (set `CLAUDE_MODEL`). Specialists run at `medium` effort; the debate
  runs at `high`.
- Requests opt into server-side refusal fallbacks (`fallbacks: "default"`), so a safety-classifier
  decline retries on Anthropic's recommended fallback model instead of failing the run.
- 16 calls per run. Mitigations: per-ticker cache, per-IP hourly rate limit, and no call for
  specialists with unavailable data.

## Roadmap

- [ ] Verify every adapter live against real tickers (large cap, small cap, ETF, foreign ADR).
- [ ] Persist runs in Postgres; public shareable run URLs (`/r/{run_id}`) and history per ticker.
- [ ] Price chart on the ticker page (weekly closes are already in the price packet).
- [ ] Track verdict accuracy over time (did the weeks/months calls play out?).
- [ ] Auth + per-user quotas before wide sharing; background job queue so runs survive page reloads.
- [ ] Deploy: frontend to Vercel, API to Render/Railway/Fly, with `ALLOWED_ORIGINS` set to the site URL.
