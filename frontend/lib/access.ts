// Invite codes and credits. The code lives in this browser; the server is the source of truth for credits.
import { API } from "./api";
import { authFetch } from "./auth";
import type { DepthId, DepthOption } from "./depth";
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
export type AccessMode = "open" | "invite" | "accounts";
export interface Access {
  mode: AccessMode;
  invite: Invite | null;
  valid: boolean;
  depths?: DepthOption[];
  default_depth?: DepthId;
  free_credits?: number;
}
export interface TickerStatus {
  free: boolean;
  reason: "running" | "cached" | null;
  mode?: AccessMode;
  invite?: Invite | null;
  signed_in?: boolean;
  remaining?: number | null;
  unlimited?: boolean;
  depth?: DepthId;
  depths?: DepthOption[];
}
export interface RecentRun {
  ticker: string;
  name: string | null;
  rating: Rating | null;
  score: number | null;
  scores?: Partial<Record<"weeks" | "months" | "years", number | null>> | null;
  analyzed_at: number;
  depth?: DepthId;
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

export async function fetchStatus(
  ticker: string,
  depth: DepthId,
  code = getCode(),
  timeoutMs = 45_000,
): Promise<TickerStatus | null> {
  // Give up eventually (a sleeping free server takes up to ~50s to wake) instead of waiting forever.
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    // Sends the sign-in token when there is one, so the server can report this account's credits.
    const res = await authFetch(withCode(`/api/status/${encodeURIComponent(ticker)}?depth=${depth}`, code), { signal: ctrl.signal });
    return res.ok ? res.json() : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
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

export function analyzeUrl(ticker: string, depth: DepthId, code = getCode()): string {
  return withCode(`${API}/api/analyze/${encodeURIComponent(ticker)}?depth=${depth}`, code);
}
