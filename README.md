# Stock Council

Twelve independent AI analysts each read **one** slice of a stock's data and form their own view. Then a
bull and a bear argue it out, a challenger objects to any lean that doesn't hold up, and a judge delivers
a verdict with separate outlooks for the next **weeks, months, and years**.

The design goal is to avoid an AI echo chamber: specialists never see each other's data or opinions, so
stage 1 produces twelve genuinely independent reads, not one read repeated twelve times.

```
            ┌── Technical ── price charts
            ├── Fundamental ── financial statements (SEC XBRL)
            ├── Sell-Side ── analyst targets
            ├── Earnings ── estimates & revisions
            ├── Insider ── Form 4 trades
 ticker ───►├── Congress ── STOCK Act trades          (12 isolated calls)
            ├── News ── headlines
            ├── Filings ── 10-K/10-Q/8-K text
            ├── Institutional ── 13F + short interest
            ├── Options ── P/C, IV, skew, max pain
            ├── Macro ── FRED
            └── Cross-Market ── sector, peers, rates, VIX
                        │
                        ▼
              Bull case ║ Bear case      (built from the 12 reports)
                        ▼
                   Challenger           (objects to weak/duplicated evidence)
                        ▼
                     Verdict            (rating + weeks / months / years)
```

## Repo layout

| Path | What it is |
|---|---|
| `backend/app/data/` | One adapter per data segment. Each returns a `DataPacket`. |
| `backend/app/agents/specialists.py` | The 12 analyst personas and their isolation rules. |
| `backend/app/agents/debate.py` | Bull, bear, challenger, and judge prompts. |
| `backend/app/agents/pipeline.py` | Orchestration; streams events as each agent finishes. |
| `backend/app/main.py` | FastAPI: `/api/analyze/{ticker}` (Server-Sent Events), cache, rate limit. |
| `frontend/` | Next.js + Tailwind UI that renders the council live. |
| `docs/ARCHITECTURE.md` | Design notes, data sources, cost, and roadmap. |

## Running locally

You need Python 3.11+ and Node 20+.

```bash
cp .env.example .env          # add ANTHROPIC_API_KEY (+ free Finnhub and FRED keys)

# API
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload            # http://localhost:8000

# Web (new terminal)
cd frontend
cp .env.local.example .env.local
npm install
npm run dev                               # http://localhost:3000
```

Useful while developing: `GET http://localhost:8000/api/data/AAPL/price` shows exactly what one
analyst would see (swap `price` for any segment).

Tests: `cd backend && pytest` · Lint: `ruff check . && ruff format --check .` · Frontend: `npm run lint && npm run build`

## Deploying

The website goes on Cloudflare Pages (free) and the agent server on Render. Step-by-step
instructions are in [`docs/DEPLOY.md`](docs/DEPLOY.md).

## Cost

A full run is 16 model calls (12 specialists + bull + bear + challenger + judge). Runs are cached per
ticker (`CACHE_TTL_HOURS`) and rate-limited per IP (`RATE_LIMIT_PER_HOUR`), so shared links replay the
cached result instead of paying again. Tune `SPECIALIST_EFFORT` / `DEBATE_EFFORT` to trade depth for cost.

## Disclaimer

Stock Council is a research and education tool. Its output is AI-generated from public, possibly
delayed or incomplete data, and is not investment advice.
