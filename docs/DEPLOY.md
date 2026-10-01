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

---

## Accounts (Supabase): sign-up, free credits, saved history

Visitors create an account with email + password, verify their email, and get `FREE_CREDITS`
(default 4 = 2 Standard analyses). Every fresh run is charged to the signed-in account on the
server; a failed run is refunded. Reports are saved to the account's History. Opening a recently
analyzed stock stays free for everyone, signed in or not.

**Supabase dashboard (one time):**
1. **Authentication → Sign In / Providers → Email:** enable, with **Confirm email** on.
2. **Authentication → URL Configuration:** Site URL = your site (e.g.
   `https://stock-council.evanranaso.workers.dev`). Redirect URLs: add `https://<your-site>/login**`
   (and `http://localhost:3000/login**` for local testing).
3. **Authentication → Attack Protection:** enable CAPTCHA with Cloudflare Turnstile and paste the
   Turnstile **secret** key there (never in the code or chat). The site key is public and lives in
   `frontend/lib/supabase.ts`.
4. **Before launch:** Supabase's built-in email sender only sends a few emails per hour. Set up
   custom SMTP (e.g. Resend with your own domain) under **Authentication → Emails → SMTP Settings**.

**Render → `stock-council-api` → Environment:**
- `DATABASE_URL` = Supabase → **Connect** → *Transaction pooler* connection string (with your DB password).
- `SUPABASE_URL` = `https://<project-ref>.supabase.co`
- `ADMIN_EMAILS` = your email, so **Admin** appears in your account menu.
- Remove `ACCESS_MODE` (it defaults to `accounts` once `SUPABASE_URL` is set), or set it to `accounts`.
- Optional: `FREE_CREDITS` (4), `FREE_SIGNUPS_PER_DAY` (20).

With `DATABASE_URL` set, everything (accounts, credits, history, costs, cache) lives in Supabase, so
the Render server no longer needs a persistent disk.

The frontend's public Supabase URL, publishable key, and Turnstile site key default to this
project's values in `frontend/lib/supabase.ts`; override them with `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_TURNSTILE_SITE_KEY` build variables if needed.

Invite codes still work with accounts: a signed-in user redeems one at **Redeem a code** (or by
opening an invite link) and its credits are added to their account, once per code.

---

## Payments (Stripe)

Three products: **Plus** and **Pro** (monthly subscriptions that add credits every month) and a
one-time **Credit pack**. People pay on Stripe's hosted checkout page; credits are added only when
Stripe's signed webhook confirms the payment, once per invoice or checkout session. Plan changes,
cancellation, card updates and invoices happen in Stripe's customer portal. Unused credits roll over.

Set it up in **Test mode** first (toggle at the top of the Stripe dashboard):

1. **Product catalog → Add product**, three times:
   - "Stock Council Plus": recurring, monthly, $9.99 (10 credits)
   - "Stock Council Pro": recurring, monthly, $24.99 (30 credits)
   - "Stock Council Credit pack": one-off, $5.99 (5 credits)

   Open each product and copy its **price ID** (`price_...`).
2. **Developers → API keys:** copy the **Secret key** (`sk_test_...`).
3. **Developers → Webhooks → Add destination:** endpoint
   `https://stock-council-api.onrender.com/api/stripe/webhook`, events:
   `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `invoice.paid`,
   `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`.
   Copy its **Signing secret** (`whsec_...`).
4. **Settings → Billing → Customer portal:** activate it; allow canceling, updating payment
   methods, and switching between the Plus and Pro prices.
5. **Render → Environment:** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PLUS`,
   `STRIPE_PRICE_PRO`, `STRIPE_PRICE_TOPUP`, and `SITE_URL` (your site, e.g.
   `https://stock-council.evanranaso.workers.dev`). Optional: `PLUS_CREDITS` (10), `PRO_CREDITS` (30),
   `TOPUP_CREDITS` (5).
6. Test on `/pricing` with card `4242 4242 4242 4242`, any future date, any CVC.

**Going live:** switch Stripe to Live mode and repeat steps 1–4 there (live products, live secret
key, a live webhook with its own signing secret), then replace the five values in Render.

The admin page shows revenue and profit (revenue minus Claude costs) for 24h / 7d / all time, and
recent payments. To price for profit, compare "Avg cost / run" per depth with what a credit sells for.

**Measured costs (Oct 2026):** Quick $0.46, Standard $0.80, Deep $1.13 per fresh run (about 130k input
tokens). Per credit at 1/2/3 credits: $0.46 / $0.40 / $0.38. The defaults above keep roughly 40–60%
margin after Stripe fees even if every credit is spent, and more from cached (free) views costing nothing.

---

## Trials: invite codes, credits, and cost tracking (without accounts)

1. **Give the server a persistent disk first.** Invite codes, credits, and cost logs are stored in
   SQLite. On Render's free plan the disk is wiped on every restart or deploy (and the free server
   restarts whenever it wakes from sleep), so codes would vanish. In Render → `stock-council-api`:
   upgrade to **Starter**, then **Disks → Add disk**: mount path `/data`, 1 GB. Then set
   `CACHE_PATH=/data/stock_council.db` in Environment.
2. **Set in Render → Environment:**
   - `ADMIN_KEY` = a long random password (e.g. from a password manager). Never share it.
   - `ACCESS_MODE` = `invite`
   - `DEFAULT_INVITE_CREDITS` = `3` (optional; this is the default)
3. **Open `https://<your-site>/admin`**, sign in with the admin key, and:
   - Create an invite for yourself with lots of credits (e.g. 500) and open its link, so your own
     runs don't hit the gate.
   - Create one invite per tester (label = their name), click **Copy invite link**, and send it.
4. The admin page shows cost per run (tokens and dollars, per agent), totals for 24h / 7d / all time,
   and each invite's usage. **+3 credits** tops someone up; **Disable** cuts a code off.

How credits work: one credit = one fresh analysis. Opening a stock anyone analyzed within
`CACHE_TTL_HOURS`, or a report in your History, is free. A run that fails is refunded automatically.
Costs are estimates from token counts × list prices in `backend/app/usage.py`; your Anthropic
console is the source of truth for billing.

### Analysis depth

Visitors pick a depth before each fresh run (`backend/app/depth.py`):

| Depth | Analysts | Debate, challenger, judge | Credits (env var) |
|---|---|---|---|
| Quick | `CHEAP_MODEL` (Sonnet 5.5), low effort | `CHEAP_MODEL` | `CREDITS_QUICK` = 1 |
| Standard (default) | `CHEAP_MODEL` | `CLAUDE_MODEL` (Opus 5.5) | `CREDITS_STANDARD` = 2 |
| Deep | `CLAUDE_MODEL` | `CLAUDE_MODEL` | `CREDITS_DEEP` = 3 |

A cached run serves any request of equal or lower depth for free. The admin page shows depth
and cost for every run, so you can compare real costs per tier. `DEFAULT_INVITE_CREDITS`
defaults to 6. Existing invites keep their totals; top them up with **+3 credits** if needed.
