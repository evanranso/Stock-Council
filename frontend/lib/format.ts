import type { MetricFormat, Rating } from "./types";

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });

export function formatValue(value: number | string | null | undefined, format: MetricFormat): string {
  if (value === null || value === undefined || value === "") return "—";
  if (format === "text") return String(value);
  if (format === "date") {
    const d = new Date(`${String(value).slice(0, 10)}T00:00:00`);
    return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  switch (format) {
    case "usd":
      return usd.format(n);
    case "usd_big":
      return bigUsd(n);
    case "pct":
      return `${n > 0 ? "+" : ""}${(n * 100).toFixed(1)}%`;
    case "rate":
      return `${n.toFixed(2)}%`;
    case "int":
      return Math.round(n).toLocaleString("en-US");
    default:
      return n.toFixed(2);
  }
}

export function bigUsd(n: number): string {
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

export function signed(n: number): string {
  return `${n > 0 ? "+" : ""}${n.toFixed(0)}`;
}

export const RATING_LABEL: Record<Rating, string> = {
  strong_buy: "Strong Buy",
  buy: "Buy",
  hold: "Hold",
  sell: "Sell",
  strong_sell: "Strong Sell",
};

export const RATING_STYLE: Record<Rating, string> = {
  strong_buy: "bg-emerald-400 text-emerald-950",
  buy: "bg-emerald-300/90 text-emerald-950",
  hold: "bg-amber-200 text-amber-950",
  sell: "bg-rose-300/90 text-rose-950",
  strong_sell: "bg-rose-400 text-rose-950",
};

export function timeAgo(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}d ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
