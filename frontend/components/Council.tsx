"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { API } from "@/lib/api";
import { replay } from "@/lib/council";
import { clearRunning, markRunning, saveCompleted } from "@/lib/history";
import type { StoredEvent } from "@/lib/types";
import ProgressView from "./ProgressView";
import Report from "./Report";

// Live analysis: streams events from the API, shows progress, then the full report.
export default function Council({ ticker }: { ticker: string }) {
  const [events, setEvents] = useState<StoredEvent[]>([]);
  const state = useMemo(() => replay(ticker, events), [ticker, events]);
  const saved = useRef(false);

  useEffect(() => {
    saved.current = false;
    setEvents([]);
    const source = new EventSource(`${API}/api/analyze/${encodeURIComponent(ticker)}`);
    const received: StoredEvent[] = [];
    let finished = false;

    source.onmessage = (msg) => {
      const event = JSON.parse(msg.data) as StoredEvent;
      received.push(event);
      setEvents([...received]);
      if (event.type === "start" && !event.cached) markRunning(ticker, event.company_name);
      if (event.type === "done" || event.type === "error") {
        finished = true;
        source.close();
        if (event.type === "done" && !saved.current) {
          saved.current = true;
          saveCompleted(ticker, received);
        }
        if (event.type === "error") clearRunning(ticker);
      }
    };
    source.onerror = () => {
      // EventSource auto-reconnects; the server would just replay, but close to keep things simple.
      source.close();
      if (!finished) {
        received.push({ type: "error", message: "Lost connection to the council. It may still be running: refresh in a minute." });
        setEvents([...received]);
      }
    };
    return () => source.close();
  }, [ticker]);

  if (state.stage === "done" && state.verdict) return <Report state={state} />;

  return (
    <div className="space-y-4">
      {state.error && (
        <div className="card flex flex-wrap items-center gap-3 border-rose-400/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          <span>{state.error}</span>
          <Link href="/" className="ml-auto rounded-lg border border-white/15 px-3 py-1 text-xs hover:bg-white/10">
            Back to search
          </Link>
        </div>
      )}
      <ProgressView state={state} />
    </div>
  );
}
