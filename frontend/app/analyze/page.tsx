"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import Council from "@/components/Council";
import Report from "@/components/Report";
import TickerSearch from "@/components/TickerSearch";
import { TICKER_RE } from "@/lib/api";
import { authFetch, useAuth } from "@/lib/auth";
import { replay } from "@/lib/council";
import { isDepth } from "@/lib/depth";
import { getEntry } from "@/lib/history";
import type { StoredEvent } from "@/lib/types";

// /analyze?t=AAPL          -> live run (or the server's recent cached run)
// /analyze?t=AAPL&run=<id> -> a saved report from this browser's history, no API call
// /analyze?t=AAPL&saved=<id> -> a saved report from the signed-in account
function AnalyzePage() {
  const params = useSearchParams();
  const ticker = (params.get("t") ?? "").trim().toUpperCase();
  const runId = params.get("run");
  const savedId = params.get("saved");
  const depthParam = params.get("depth");
  const depth = isDepth(depthParam) ? depthParam : undefined;

  if (!TICKER_RE.test(ticker)) {
    return (
      <div className="space-y-4 pt-8 text-center">
        <p className="text-zinc-400">Search for a company to convene the council.</p>
        <TickerSearch autoFocus />
      </div>
    );
  }
  if (savedId) return <SavedReport key={`s-${savedId}`} id={savedId} ticker={ticker} account />;
  if (runId) return <SavedReport key={runId} id={runId} ticker={ticker} />;
  return <Council key={`${ticker}-${depth ?? ""}`} ticker={ticker} requestedDepth={depth} />;
}

function SavedReport({ id, ticker, account = false }: { id: string; ticker: string; account?: boolean }) {
  const [events, setEvents] = useState<StoredEvent[] | null | undefined>(undefined);
  const { ready, session } = useAuth();
  const signedIn = !!session;
  useEffect(() => {
    if (!account) return setEvents(getEntry(id)?.events ?? null);
    if (!ready) return;
    if (!signedIn) return setEvents(null);
    authFetch(`/api/me/history/${encodeURIComponent(id)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((run) => setEvents(run?.events ?? null))
      .catch(() => setEvents(null));
  }, [id, account, ready, signedIn]);

  if (events === undefined) return <div className="card h-40 animate-pulse" />;
  if (!events) {
    return (
      <div className="card mx-auto max-w-lg p-6 text-center">
        <p className="text-zinc-300">
          {account ? (signedIn ? "That saved analysis isn't in your account anymore." : "Log in to see your saved analyses.") : "That saved analysis isn't in this browser anymore."}
        </p>
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
      <Report state={replay(ticker, events)} />
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
