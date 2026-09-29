"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchRecent, type RecentRun } from "@/lib/access";
import { RATING_LABEL, RATING_STYLE, signed, timeAgo } from "@/lib/format";

/** Stocks anyone analyzed recently: opening them costs nothing. */
export default function FreeToView({ title = "Free to open: recently analyzed", narrow = false }: { title?: string; narrow?: boolean }) {
  const [runs, setRuns] = useState<RecentRun[] | null>(null);
  useEffect(() => {
    fetchRecent().then(setRuns);
  }, []);
  if (!runs?.length) return null;

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      <ul className={`grid gap-3 ${narrow ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3"}`}>
        {runs.map((r) => (
          <li key={r.ticker}>
            <Link href={`/analyze?t=${r.ticker}`} className="card flex items-center gap-4 p-4 transition hover:border-brand-400/40 hover:bg-white/[0.05]">
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-lg font-bold">{r.ticker}</span>
                  <span className="truncate text-sm text-zinc-400">{r.name}</span>
                </div>
                <p className="mt-1 text-xs text-zinc-500">{timeAgo(new Date(r.analyzed_at * 1000).toISOString())} · free</p>
              </div>
              {r.rating && (
                <div className="text-right">
                  <span className={`rounded-lg px-2.5 py-1 text-xs font-bold ${RATING_STYLE[r.rating]}`}>{RATING_LABEL[r.rating]}</span>
                  {r.score !== null && <div className="mt-1 text-xs tabular-nums text-zinc-500">score {signed(r.score)}</div>}
                </div>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
