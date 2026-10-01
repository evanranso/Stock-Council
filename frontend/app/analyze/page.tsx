"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import Council from "@/components/Council";
import Report from "@/components/Report";
import TickerSearch from "@/components/TickerSearch";
import { TICKER_RE } from "@/lib/api";
import { authFetch, useAuth } from "@/lib/auth";
import { fetchCommunityAnalysis } from "@/lib/community";
import { replay } from "@/lib/council";
import { isDepth } from "@/lib/depth";
import { getEntry } from "@/lib/history";
import type { StoredEvent } from "@/lib/types";

// /analyze?t=AAPL          -> live run (or the server's recent cached run)
// /analyze?t=AAPL&run=<id> -> a saved report from this browser's history, no API call
// /analyze?t=AAPL&saved=<id> -> a saved report from the signed-in account
// /analyze?t=AAPL&community=<id> -> any past analysis from the community library (free)
function AnalyzePage() {
  const params = useSearchParams();
  const ticker = (params.get("t") ?? "").trim().toUpperCase();
  const runId = params.get("run");
  const savedId = params.get("saved");
  const communityId = params.get("community");
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
  if (communityId) return <SavedReport key={`c-${communityId}`} id={communityId} ticker={ticker} source="community" />;
  if (savedId) return <SavedReport key={`s-${savedId}`} id={savedId} ticker={ticker} source="account" />;
  if (runId) return <SavedReport key={runId} id={runId} ticker={ticker} />;
  return <Council key={`${ticker}-${depth ?? ""}`} ticker={ticker} requestedDepth={depth} />;
}

function SavedReport({ id, ticker, source = "local" }: { id: string; ticker: string; source?: "local" | "account" | "community" }) {
  const account = source === "account";
  const [events, setEvents] = useState<StoredEvent[] | null | undefined>(undefined);
  const [needsAccount, setNeedsAccount] = useState(false);
  const { ready, session } = useAuth();
  const signedIn = !!session;
  useEffect(() => {
    if (source === "community") {
      if (!ready) return;
      if (!signedIn) {
        setNeedsAccount(true);
        return;
      }
      setNeedsAccount(false);
      fetchCommunityAnalysis(id).then((r) => {
        if (r === "sign_in") return setNeedsAccount(true);
        setEvents(r?.events ?? null);
      });
      return;
    }
    if (!account) return setEvents(getEntry(id)?.events ?? null);
    if (!ready) return;
    if (!signedIn) return setEvents(null);
    authFetch(`/api/me/history/${encodeURIComponent(id)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((run) => setEvents(run?.events ?? null))
      .catch(() => setEvents(null));
  }, [id, source, account, ready, signedIn]);

  if (needsAccount) return <CommunityGate ticker={ticker} id={id} />;
  if (events === undefined) return <div className="card h-40 animate-pulse" />;
  if (!events) {
    return (
      <div className="card mx-auto max-w-lg p-6 text-center">
        <p className="text-zinc-300">
          {source === "community"
            ? "That analysis couldn't be found."
            : account
              ? signedIn
                ? "That saved analysis isn't in your account anymore."
                : "Log in to see your saved analyses."
              : "That saved analysis isn't in this browser anymore."}
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
        <span className="rounded-full bg-white/5 px-3 py-1">{source === "community" ? "Community analysis" : "Saved analysis"}</span>
        <Link href={`/analyze?t=${ticker}`} className="rounded-full border border-white/10 px-3 py-1 hover:border-brand-400/50 hover:text-white">
          Get the latest analysis →
        </Link>
      </div>
      <Report state={replay(ticker, events)} />
    </div>
  );
}

/** Community reports are for account holders: invite visitors to sign up, then bring them right back. */
function CommunityGate({ ticker, id }: { ticker: string; id: string }) {
  const next = encodeURIComponent(`/analyze?t=${ticker}&community=${id}`);
  return (
    <div className="card fade-up mx-auto max-w-xl p-6 text-center sm:p-8">
      <p className="text-sm text-brand-300">{ticker} · community analysis</p>
      <h1 className="mt-1 text-2xl font-bold">Create a free account to read this analysis</h1>
      <p className="mt-2 text-zinc-400">
        Every report in the community library is free to read with an account. New accounts also get free credits to run their own analyses.
      </p>
      <div className="mt-6 flex justify-center gap-3">
        <Link href={`/login?mode=signup&next=${next}`} className="rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-5 py-2.5 font-semibold text-white shadow-lg shadow-brand-500/25 hover:brightness-110">
          Sign up free
        </Link>
        <Link href={`/login?next=${next}`} className="rounded-lg border border-white/10 px-5 py-2.5 text-zinc-300 hover:text-white">
          Log in
        </Link>
      </div>
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
