# Deploying Stock Council

Two pieces, two free hosts:

| Piece | What it is | Host | Cost |
|---|---|---|---|
| Website (`frontend/`) | Static pages | **Cloudflare Pages** | Free |
| Agent server (`backend/`) | Python server that fetches data and calls Claude | **Render** | Free to start ($7/mo to stay awake) |
| Claude usage | 16 model calls per new analysis | Anthropic | Roughly $1–2 per new ticker |

Why not host everything on Cloudflare? The agent server is Python with data libraries
(pandas, yfinance) and long-running streams. Cloudflare's server platform doesn't run that
well, so it lives on Render and the website on Cloudflare calls it.

Do the steps in order: the website needs the server's URL, and the server needs the website's URL.

---

## Before you start

1. **Anthropic key.** At console.anthropic.com → API Keys, create a key. Never paste it into a
   chat, an issue, or a file in the repo.
2. **Set a spending limit.** In console.anthropic.com → Billing / Limits, set a monthly cap (for
   example $20). This is your real safety net once the link is public.
3. Optional, free: a Finnhub key (finnhub.io) and a FRED key (fred.stlouisfed.org).

## Step 1: Agent server on Render (about 10 minutes)

1. Sign up at render.com with your GitHub account.
2. Click **New → Blueprint**, choose the `Stock-Council` repo, and click **Apply**. Render reads
   `render.yaml` and creates `stock-council-api`.
3. It will ask for the secret values:
   - `ANTHROPIC_API_KEY`: your key
   - `FINNHUB_API_KEY`, `FRED_API_KEY`: paste them, or leave them blank for now
   - `SEC_USER_AGENT`: `StockCouncil your-email@example.com` (SEC requires a contact email)
   - `ALLOWED_ORIGINS`: leave it as `http://localhost:3000` for now; you'll fix it in step 3
4. Wait for the deploy to go green. Copy the URL, which looks like
   `https://stock-council-api.onrender.com`.
5. Check it: open `https://stock-council-api.onrender.com/api/health`. You should see
   `{"ok":true,...}`.

## Step 2: Website on Cloudflare Pages (about 5 minutes)

The site deploys as a Cloudflare **Worker** serving static files (`frontend/wrangler.jsonc`).

1. In the Cloudflare dashboard, go to **Workers & Pages → Create → Import a repository** and pick the
   `Stock-Council` repo. Name the project `stock-council`.
2. In **Settings → Build**:
   - Root directory: `frontend`
   - Build command: `npm run build`
   - Deploy command: `npx wrangler deploy`
3. In **Settings → Build → Variables and secrets** (the *build* variables, not the runtime ones),
   add `NEXT_PUBLIC_API_URL` = your Render URL from step 1 (no trailing slash) and
   `NODE_VERSION` = `22`. The URL is baked into the site at build time, so it must be a build variable.
4. Redeploy: **Deployments → latest → Retry build**, or push a commit.
5. In **Settings → Domains & Routes**, make sure the `workers.dev` route is enabled. Your site is
   `https://stock-council.<your-subdomain>.workers.dev`.

## Step 3: Connect them

In Render → `stock-council-api` → **Environment**, set `ALLOWED_ORIGINS` to your site URL, for
example `https://stock-council.evanranaso.workers.dev`. Save; Render redeploys automatically. If you
add a custom domain later, add it too, comma-separated.

Open the site, enter a ticker, and the council should run. Share links look like
`https://stock-council.evanranaso.workers.dev/analyze?t=AAPL`.

---

## Things to know

- **Free Render servers sleep** after about 15 minutes idle. The first visit after that takes
  roughly a minute to wake up. Upgrading the service to Starter ($7/mo) keeps it awake.
- **The cache and verdict history reset** whenever the free server restarts or redeploys, because
  its disk is temporary. To keep history (needed for accuracy tracking later), upgrade to Starter
  and add a Render **Disk** (1 GB is plenty) mounted at `/data`, then set `CACHE_PATH=/data/stock_council.db`.
- **Cost controls built in:**
  - `RATE_LIMIT_PER_HOUR` (10 new analyses per visitor per hour)
  - `MAX_RUNS_PER_DAY` (40 new analyses per day across everyone)
  - Cached tickers (within `CACHE_TTL_HOURS`) are free to view again
  - Keep the Anthropic spending cap on as well.
- **Yahoo Finance sometimes rate-limits cloud servers.** If the price, options, or related-market
  analysts start showing "no data" in production, that's the likely cause. The fix is a paid data
  provider behind the same adapter.
- **Updates deploy automatically:** pushing to `main` rebuilds both the Render server and the
  Cloudflare site.
