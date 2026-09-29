"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import Council from "@/components/Council";
import Report from "@/components/Report";
import TickerSearch from "@/components/TickerSearch";
import { TICKER_RE } from "@/lib/api";
import { replay } from "@/lib/council";
import { getEntry, type HistoryEntry } from "@/lib/history";

// /analyze?t=AAPL          -> live run (or the server's recent cached run)
// /analyze?t=AAPL&run=<id> -> a saved report from this browser's history, no API call
function AnalyzePage() {
  const params = useSearchParams();
  const ticker = (params.get("t") ?? "").trim().toUpperCase();
  const runId = params.get("run");

  if (!TICKER_RE.test(ticker)) {
    return (
      <div className="space-y-4 pt-8 text-center">
        <p className="text-zinc-400">Search for a company to convene the council.</p>
        <TickerSearch autoFocus />
      </div>
    );
  }
  if (runId) return <SavedReport key={runId} id={runId} ticker={ticker} />;
  return <Council key={ticker} ticker={ticker} />;
}

function SavedReport({ id, ticker }: { id: string; ticker: string }) {
  const [entry, setEntry] = useState<HistoryEntry | null | undefined>(undefined);
  useEffect(() => setEntry(getEntry(id) ?? null), [id]);

  if (entry === undefined) return null;
  if (!entry?.events) {
    return (
      <div className="card mx-auto max-w-lg p-6 text-center">
        <p className="text-zinc-300">That saved analysis isn&apos;t in this browser anymore.</p>
        <Link href={`/analyze?t=${ticker}`} className="mt-4 inline-block rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-400">
          Analyze {ticker} now
        </Link>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm text-zinc-400">
        <span className="rounded-full bg-white/5 px-3 py-1">Saved analysis</span>
        <Link href={`/analyze?t=${ticker}`} className="rounded-full border border-white/10 px-3 py-1 hover:border-brand-400/50 hover:text-white">
          Get the latest analysis →
        </Link>
      </div>
      <Report state={replay(ticker, entry.events)} />
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <AnalyzePage />
    </Suspense>
  );
}
