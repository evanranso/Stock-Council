"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchRecent, type RecentRun } from "@/lib/access";
import { DEPTH_ICON } from "@/lib/depth";
import { RATING_LABEL, RATING_STYLE, signed, timeAgo } from "@/lib/format";
import { atHorizon, HORIZON_TAB, useHorizon } from "@/lib/horizon";

/** Stocks anyone analyzed recently: opening them costs nothing. */
export default function FreeToView({ title = "Free to open: recently analyzed", narrow = false }: { title?: string; narrow?: boolean }) {
  const [runs, setRuns] = useState<RecentRun[] | null>(null);
  const [horizon] = useHorizon();
  useEffect(() => {
    fetchRecent().then(setRuns);
  }, []);
  if (!runs?.length) return null;

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      <ul className={`grid gap-3 ${narrow ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3"}`}>
        {runs.map((r) => {
          const at = atHorizon(r.scores, horizon, r);
          return (
          <li key={r.ticker}>
            <Link href={`/analyze?t=${r.ticker}${r.depth ? `&depth=${r.depth}` : ""}`} className="card flex items-center gap-4 p-4 transition hover:border-brand-400/40 hover:bg-white/[0.05]">
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-lg font-bold">{r.ticker}</span>
                  <span className="truncate text-sm text-zinc-400">{r.name}</span>
                </div>
                <p className="mt-1 text-xs text-zinc-500">{timeAgo(new Date(r.analyzed_at * 1000).toISOString())}
                  {r.depth && <> · {DEPTH_ICON[r.depth]} {r.depth}</>} · free
                </p>
              </div>
              {at.rating && (
                <div className="text-right">
                  <span className={`rounded-lg px-2.5 py-1 text-xs font-bold ${RATING_STYLE[at.rating]}`}>{RATING_LABEL[at.rating]}</span>
                  {at.score !== null && (
                    <div className="mt-1 text-xs tabular-nums text-zinc-500">
                      {r.scores ? HORIZON_TAB[horizon].toLowerCase() : "score"} {signed(at.score)}
                    </div>
                  )}
                </div>
              )}
            </Link>
          </li>
          );
        })}
      </ul>
    </section>
  );
}
