"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import Council from "@/components/Council";
import TickerSearch from "@/components/TickerSearch";

// Shareable as /analyze?t=AAPL. A query string (not /t/AAPL) keeps the site fully static.
function AnalyzePage() {
  const ticker = (useSearchParams().get("t") ?? "").trim().toUpperCase();
  if (!/^[A-Z][A-Z0-9.\-]{0,9}$/.test(ticker)) {
    return (
      <div className="space-y-4 pt-8 text-center">
        <p className="text-zinc-400">Enter a ticker to convene the council.</p>
        <TickerSearch />
      </div>
    );
  }
  return <Council key={ticker} ticker={ticker} />;
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <AnalyzePage />
    </Suspense>
  );
}
