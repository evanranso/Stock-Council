"use client";

// The timeframe a visitor cares about. Every report scores weeks, months and years separately;
// this picks which one is the headline rating. Remembered in the browser.
import { useEffect, useState } from "react";
import type { Rating } from "./types";

export type Horizon = "weeks" | "months" | "years";
export const HORIZON_ORDER: Horizon[] = ["weeks", "months", "years"];
export const HORIZON_TAB: Record<Horizon, string> = { weeks: "Weeks", months: "Months", years: "Years" };
export const HORIZON_LONG: Record<Horizon, string> = {
  weeks: "Next few weeks",
  months: "Next few months",
  years: "Next 1–3 years",
};
export const HORIZON_FOR: Record<Horizon, string> = {
  weeks: "for the next few weeks",
  months: "for the next few months",
  years: "for the next 1–3 years",
};
export const DEFAULT_HORIZON: Horizon = "months";

// Mirrors backend/app/scoring.py (LEAN_THRESHOLD, STRONG_THRESHOLD).
export const LEAN_THRESHOLD = 10;
export const STRONG_THRESHOLD = 30;

export function ratingFor(score: number): Rating {
  if (score >= STRONG_THRESHOLD) return "strong_buy";
  if (score >= LEAN_THRESHOLD) return "buy";
  if (score <= -STRONG_THRESHOLD) return "strong_sell";
  if (score <= -LEAN_THRESHOLD) return "sell";
  return "hold";
}

export type HorizonScores = Partial<Record<Horizon, number | null>> | null | undefined;

/** Rating and score for the chosen timeframe; falls back to the old blended values for reports without per-horizon scores. */
export function atHorizon(
  scores: HorizonScores,
  horizon: Horizon,
  fallback: { rating?: Rating | null; score?: number | null },
): { rating: Rating | null; score: number | null } {
  const s = scores?.[horizon];
  if (typeof s === "number") return { rating: ratingFor(s), score: s };
  return { rating: fallback.rating ?? null, score: fallback.score ?? null };
}

const KEY = "stockCouncil.horizon.v1";
const EVENT = "stock-council-horizon";

function read(): Horizon {
  try {
    const v = localStorage.getItem(KEY);
    return v === "weeks" || v === "months" || v === "years" ? v : DEFAULT_HORIZON;
  } catch {
    return DEFAULT_HORIZON;
  }
}

export function setPreferredHorizon(h: Horizon): void {
  try {
    localStorage.setItem(KEY, h);
  } catch {
    /* storage unavailable: the choice just won't persist */
  }
  window.dispatchEvent(new Event(EVENT));
}

/** The visitor's timeframe, kept in sync across every component on the page. */
export function useHorizon(): [Horizon, (h: Horizon) => void] {
  const [h, setH] = useState<Horizon>(DEFAULT_HORIZON);
  useEffect(() => {
    const load = () => setH(read());
    load();
    window.addEventListener(EVENT, load);
    return () => window.removeEventListener(EVENT, load);
  }, []);
  return [h, setPreferredHorizon];
}
