"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import CommunityCard from "@/components/CommunityCard";
import { type CommunityItem, type CommunityQuery, fetchCommunity } from "@/lib/community";
import { HORIZON_ORDER, HORIZON_TAB, useHorizon } from "@/lib/horizon";

const PAGE = 30;

const DAYS: { id: CommunityQuery["days"]; label: string }[] = [
  { id: "1", label: "24 hours" },
  { id: "7", label: "7 days" },
  { id: "30", label: "30 days" },
  { id: "all", label: "All time" },
];
const RATINGS: { id: CommunityQuery["rating"]; label: string }[] = [
  { id: "all", label: "All" },
  { id: "buy", label: "Buys" },
  { id: "hold", label: "Holds" },
  { id: "sell", label: "Sells" },
];
const DEPTHS: { id: CommunityQuery["depth"]; label: string }[] = [
  { id: "all", label: "Any depth" },
  { id: "quick", label: "⚡ Quick" },
  { id: "standard", label: "⚖️ Standard" },
  { id: "deep", label: "🔬 Deep" },
];
const SORTS: { id: CommunityQuery["sort"]; label: string }[] = [
  { id: "newest", label: "Newest" },
  { id: "bullish", label: "Most bullish" },
  { id: "bearish", label: "Most bearish" },
  { id: "confidence", label: "Highest confidence" },
];

export default function CommunityPage() {
  const [horizon, setHorizon] = useHorizon();
  const [days, setDays] = useState<CommunityQuery["days"]>("30");
  const [rating, setRating] = useState<CommunityQuery["rating"]>("all");
  const [depth, setDepth] = useState<CommunityQuery["depth"]>("all");
  const [sort, setSort] = useState<CommunityQuery["sort"]>("newest");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<CommunityItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const request = useRef(0);

  // Debounce typing in the search box.
  useEffect(() => {
    const t = setTimeout(() => setSearch(q), 250);
    return () => clearTimeout(t);
  }, [q]);

  const query: CommunityQuery = { days, rating, horizon, depth, sort, q: search };
  const key = JSON.stringify(query);

  useEffect(() => {
    const id = ++request.current;
    setItems(null);
    fetchCommunity(query, 0, PAGE).then((r) => {
      if (id !== request.current) return; // a newer filter change won
      setItems(r?.items ?? []);
      setTotal(r?.total ?? 0);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  async function loadMore() {
    if (!items) return;
    setLoadingMore(true);
    const r = await fetchCommunity(query, items.length, PAGE);
    setItems([...items, ...(r?.items ?? [])]);
    setLoadingMore(false);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Community analyses</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Every analysis anyone has run on Stock Council. Filter for the strongest calls, then open any report free with an account. Older reports reflect the
          data at the time they ran.
        </p>
      </div>

      <div className="card space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search ticker or company"
            className="min-w-48 flex-1 rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2 text-sm placeholder:text-zinc-600 focus:border-brand-400/70 focus:outline-none"
            aria-label="Search ticker or company"
          />
          <Segmented label="Timeframe" value={horizon} onChange={setHorizon} options={HORIZON_ORDER.map((h) => ({ id: h, label: HORIZON_TAB[h] }))} />
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
          <Segmented label="Period" value={days} onChange={setDays} options={DAYS} />
          <Segmented label="Rating" value={rating} onChange={setRating} options={RATINGS} />
          <Segmented label="Depth" value={depth} onChange={setDepth} options={DEPTHS} />
          <label className="flex items-center gap-2 text-sm text-zinc-400">
            Sort
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as CommunityQuery["sort"])}
              className="rounded-lg border border-white/15 bg-[#0e1018] px-2 py-1.5 text-sm text-zinc-200 focus:outline-none"
            >
              {SORTS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {items === null ? (
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="card h-20 animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="card p-8 text-center text-zinc-400">
          No analyses match these filters.{" "}
          <Link href="/" className="text-brand-300 hover:underline">
            Analyze a stock
          </Link>{" "}
          to add one.
        </div>
      ) : (
        <>
          <p className="text-sm text-zinc-500">
            {total} {total === 1 ? "analysis" : "analyses"} · ratings shown for the {HORIZON_TAB[horizon].toLowerCase()} timeframe
          </p>
          <ul className="grid gap-2 lg:grid-cols-2">
            {items.map((it) => (
              <li key={it.id}>
                <CommunityCard item={it} horizon={horizon} wide />
              </li>
            ))}
          </ul>
          {items.length < total && (
            <div className="text-center">
              <button
                onClick={loadMore}
                disabled={loadingMore}
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5 hover:text-white disabled:opacity-50"
              >
                {loadingMore ? "Loading…" : `Show more (${total - items.length} left)`}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Segmented<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { id: T; label: string }[];
}) {
  return (
    <div className="flex items-center gap-2" role="radiogroup" aria-label={label}>
      <span className="text-xs uppercase tracking-wider text-zinc-500">{label}</span>
      <div className="flex flex-wrap gap-1">
        {options.map((o) => (
          <button
            key={o.id}
            role="radio"
            aria-checked={o.id === value}
            onClick={() => onChange(o.id)}
            className={`rounded-lg px-2.5 py-1 text-sm transition ${
              o.id === value ? "bg-white text-zinc-900" : "bg-white/5 text-zinc-300 ring-1 ring-white/10 hover:bg-white/10 hover:text-white"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}
