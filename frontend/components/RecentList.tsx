"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { RATING_LABEL, RATING_STYLE, signed, timeAgo } from "@/lib/format";
import { clearHistory, type HistoryEntry, listHistory, removeEntry } from "@/lib/history";

function href(e: HistoryEntry): string {
  return e.status === "done" ? `/analyze?t=${e.ticker}&run=${encodeURIComponent(e.id)}` : `/analyze?t=${e.ticker}`;
}

export default function RecentList({ limit, manage = false }: { limit?: number; manage?: boolean }) {
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null);

  useEffect(() => {
    const load = () => setEntries(listHistory());
    load();
    window.addEventListener("stock-council-history", load);
    window.addEventListener("storage", load);
    return () => {
      window.removeEventListener("stock-council-history", load);
      window.removeEventListener("storage", load);
    };
  }, []);

  if (entries === null) return null;
  const shown = limit ? entries.slice(0, limit) : entries;

  if (!shown.length) {
    return manage ? (
      <div className="card p-8 text-center text-zinc-400">
        No analyses yet. Search for a stock and your reports will be saved here, in this browser.
      </div>
    ) : (
      <p className="text-sm text-zinc-500">Analyses you run will show up here.</p>
    );
  }

  return (
    <div>
      <ul className={`grid gap-3 ${manage ? "" : "sm:grid-cols-2 lg:grid-cols-3"}`}>
        {shown.map((e) => (
          <li key={e.id} className="card group relative flex items-center gap-4 p-4 transition hover:border-brand-400/40 hover:bg-white/[0.05]">
            <Link href={href(e)} className="absolute inset-0 rounded-2xl" aria-label={`Open ${e.ticker} analysis`} />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-lg font-bold">{e.ticker}</span>
                <span className="truncate text-sm text-zinc-400">{e.name}</span>
              </div>
              {manage && e.bottomLine && <p className="mt-1 line-clamp-2 text-sm text-zinc-300">{e.bottomLine}</p>}
              <p className="mt-1 text-xs text-zinc-500">{e.status === "running" ? "In progress — click to rejoin" : timeAgo(e.savedAt)}</p>
            </div>
            {e.status === "done" && e.rating ? (
              <div className="text-right">
                <span className={`rounded-lg px-2.5 py-1 text-xs font-bold ${RATING_STYLE[e.rating]}`}>{RATING_LABEL[e.rating]}</span>
                {e.score !== undefined && <div className="mt-1 text-xs tabular-nums text-zinc-500">score {signed(e.score)}</div>}
              </div>
            ) : (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-300/30 border-t-brand-300" aria-label="In progress" />
            )}
            {manage && (
              <button
                onClick={() => removeEntry(e.id)}
                className="relative z-10 rounded-lg px-2 py-1 text-xs text-zinc-500 hover:bg-white/10 hover:text-rose-300"
                aria-label={`Remove ${e.ticker} from history`}
              >
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>
      {manage && (
        <button onClick={() => clearHistory()} className="mt-6 text-xs text-zinc-500 hover:text-rose-300">
          Clear all history
        </button>
      )}
    </div>
  );
}
