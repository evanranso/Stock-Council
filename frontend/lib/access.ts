// Invite codes and credits. The code lives in this browser; the server is the source of truth for credits.
import { API } from "./api";
import type { Rating } from "./types";

const KEY = "stockCouncil.invite.v1";
export const CREDITS_EVENT = "stock-council-credits";

export interface Invite {
  code: string;
  label: string;
  credits_total: number;
  credits_used: number;
  remaining: number;
  disabled: boolean;
}
export interface Access {
  mode: "open" | "invite";
  invite: Invite | null;
  valid: boolean;
}
export interface TickerStatus {
  free: boolean;
  reason: "running" | "cached" | null;
  mode?: "open" | "invite";
  invite?: Invite | null;
}
export interface RecentRun {
  ticker: string;
  name: string | null;
  rating: Rating | null;
  score: number | null;
  analyzed_at: number;
}

export function getCode(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setCode(code: string | null): void {
  try {
    if (code) localStorage.setItem(KEY, code.trim().toUpperCase());
    else localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: the code just won't persist */
  }
  window.dispatchEvent(new Event(CREDITS_EVENT));
}

export function creditsChanged(): void {
  window.dispatchEvent(new Event(CREDITS_EVENT));
}

function withCode(url: string, code: string | null): string {
  return code ? `${url}${url.includes("?") ? "&" : "?"}code=${encodeURIComponent(code)}` : url;
}

export async function fetchAccess(code = getCode()): Promise<Access | null> {
  try {
    const res = await fetch(withCode(`${API}/api/access`, code));
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}

export async function fetchStatus(ticker: string, code = getCode()): Promise<TickerStatus | null> {
  try {
    const res = await fetch(withCode(`${API}/api/status/${encodeURIComponent(ticker)}`, code));
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}

export async function fetchRecent(): Promise<RecentRun[]> {
  try {
    const res = await fetch(`${API}/api/recent`);
    return res.ok ? res.json() : [];
  } catch {
    return [];
  }
}

export function analyzeUrl(ticker: string, code = getCode()): string {
  return withCode(`${API}/api/analyze/${encodeURIComponent(ticker)}`, code);
}
