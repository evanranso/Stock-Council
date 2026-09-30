"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { RATING_LABEL, RATING_STYLE, signed, timeAgo } from "@/lib/format";
import { authFetch, ME_EVENT, useAuth } from "@/lib/auth";
import { DEPTH_ICON } from "@/lib/depth";
import { clearHistory, type HistoryEntry, listHistory, removeEntry } from "@/lib/history";
import type { Rating } from "@/lib/types";

// Signed in: reports live in the account (server). Signed out: in this browser.
type Entry = HistoryEntry & { server?: boolean };

interface SavedRow {
  id: string;
  ticker: string;
  name: string | null;
  depth: HistoryEntry["depth"] | null;
  created: number;
  rating: Rating | null;
  score: number | null;
  confidence: number | null;
  bottom_line: string | null;
}

function fromServer(r: SavedRow): Entry {
  return {
    id: r.id,
    ticker: r.ticker,
    name: r.name,
    status: "done",
    savedAt: new Date(r.created * 1000).toISOString(),
    rating: r.rating ?? undefined,
    score: r.score ?? undefined,
    confidence: r.confidence ?? undefined,
    bottomLine: r.bottom_line ?? undefined,
    depth: r.depth ?? undefined,
    server: true,
  };
}

function href(e: Entry): string {
  if (e.server) return `/analyze?t=${e.ticker}&saved=${encodeURIComponent(e.id)}`;
  return e.status === "done" ? `/analyze?t=${e.ticker}&run=${encodeURIComponent(e.id)}` : `/analyze?t=${e.ticker}`;
}

export default function RecentList({ limit, manage = false }: { limit?: number; manage?: boolean }) {
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const { ready, session } = useAuth();
  const signedIn = !!session;

  useEffect(() => {
    if (!ready || !signedIn) return;
    let cancelled = false;
    const load = () =>
      authFetch("/api/me/history")
        .then((r) => (r.ok ? r.json() : []))
        .then((rows: SavedRow[]) => !cancelled && setEntries(rows.map(fromServer)))
        .catch(() => !cancelled && setEntries([]));
    load();
    window.addEventListener(ME_EVENT, load);
    return () => {
      cancelled = true;
      window.removeEventListener(ME_EVENT, load);
    };
  }, [ready, signedIn]);

  useEffect(() => {
    if (!ready || signedIn) return;
    const load = () => setEntries(listHistory());
    load();
    window.addEventListener("stock-council-history", load);
    window.addEventListener("storage", load);
    return () => {
      window.removeEventListener("stock-council-history", load);
      window.removeEventListener("storage", load);
    };
  }, [ready, signedIn]);

  async function remove(e: Entry) {
    if (!e.server) return removeEntry(e.id);
    setEntries((list) => list?.filter((x) => x.id !== e.id) ?? null);
    await authFetch(`/api/me/history/${encodeURIComponent(e.id)}`, { method: "DELETE" }).catch(() => undefined);
  }
  async function clearAll() {
    if (!signedIn) return clearHistory();
    if (!window.confirm("Delete every saved report from your account?")) return;
    setEntries([]);
    await authFetch("/api/me/history/all", { method: "DELETE" }).catch(() => undefined);
  }

  if (entries === null) return null;
  const shown = limit ? entries.slice(0, limit) : entries;

  if (!shown.length) {
    return manage ? (
      <div className="card p-8 text-center text-zinc-400">
        {signedIn
          ? "No analyses yet. Search for a stock and your reports will be saved to your account."
          : "No analyses yet. Search for a stock and your reports will be saved here, in this browser."}
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
              <p className="mt-1 text-xs text-zinc-500">{e.status === "running" ? "In progress — click to rejoin" : timeAgo(e.savedAt)}
                {e.depth && <> · {DEPTH_ICON[e.depth]} {e.depth}</>}</p>
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
                onClick={() => remove(e)}
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
        <button onClick={clearAll} className="mt-6 text-xs text-zinc-500 hover:text-rose-300">
          Clear all history
        </button>
      )}
    </div>
  );
}
