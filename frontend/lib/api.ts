export const API = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export interface TickerMatch { ticker: string; name: string; exchange: string | null }

/** The server couldn't load its company list (e.g. the SEC is throttling it). Exact tickers still work. */
export class SearchUnavailable extends Error {}

export async function searchTickers(q: string, signal?: AbortSignal): Promise<TickerMatch[]> {
  const res = await fetch(`${API}/api/search?q=${encodeURIComponent(q)}&limit=8`, { signal });
  if (res.status === 503) throw new SearchUnavailable();
  if (!res.ok) return [];
  return res.json();
}

// The free API host sleeps when idle; poke it early so the first search/analysis is fast.
let warmed = false;
export function warmApi(): void {
  if (warmed) return;
  warmed = true;
  fetch(`${API}/api/health`).catch(() => {
    warmed = false;
  });
}

export const TICKER_RE = /^[A-Z][A-Z0-9.\-]{0,9}$/;
