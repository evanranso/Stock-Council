// The community library: every completed analysis on the site.
import { API } from "./api";
import type { DepthId } from "./depth";
import type { Horizon } from "./horizon";
import type { Rating, StoredEvent } from "./types";

export interface CommunityItem {
  id: string;
  ticker: string;
  name: string | null;
  depth: DepthId | null;
  created: number;
  bottom_line: string | null;
  reference_price: number | null;
  score: number;
  rating: Rating;
  confidence: number | null;
}

export interface CommunityQuery {
  days: "1" | "7" | "30" | "90" | "all";
  rating: "all" | "buy" | "sell" | "hold";
  horizon: Horizon;
  depth: "all" | DepthId;
  sort: "newest" | "bullish" | "bearish" | "confidence";
  q: string;
}

export async function fetchCommunity(query: CommunityQuery, offset = 0, limit = 30): Promise<{ total: number; items: CommunityItem[] } | null> {
  const params = new URLSearchParams({ ...query, offset: String(offset), limit: String(limit) });
  try {
    const res = await fetch(`${API}/api/community?${params}`);
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}

export async function fetchCommunityAnalysis(id: string): Promise<{ ticker: string; events: StoredEvent[] } | null> {
  try {
    const res = await fetch(`${API}/api/community/${encodeURIComponent(id)}`);
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}

export function communityHref(item: { id: string; ticker: string }): string {
  return `/analyze?t=${item.ticker}&community=${encodeURIComponent(item.id)}`;
}
