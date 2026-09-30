"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { analyzeUrl, creditsChanged, fetchStatus, getCode, type TickerStatus } from "@/lib/access";
import { DEFAULT_DEPTHS, type DepthId, type DepthOption, preferredDepth, savePreferredDepth } from "@/lib/depth";
import { replay } from "@/lib/council";
import { clearRunning, markRunning, saveCompleted } from "@/lib/history";
import type { StoredEvent } from "@/lib/types";
import { InviteForm } from "./AccessWidgets";
import DepthPicker from "./DepthPicker";
import FreeToView from "./FreeToView";
import ProgressView from "./ProgressView";
import Report from "./Report";

type Phase =
  | { kind: "checking" }
  | { kind: "confirm"; mode: "open" | "invite"; remaining?: number; depths: DepthOption[] }
  | { kind: "gate"; reason: string }
  | { kind: "stream" };

// Live analysis: checks whether this is free or costs credits, lets the visitor pick a depth,
// streams events from the API, then shows the report.
export default function Council({ ticker, requestedDepth }: { ticker: string; requestedDepth?: DepthId }) {
  const [phase, setPhase] = useState<Phase>({ kind: "checking" });
  const [depth, setDepth] = useState<DepthId>(requestedDepth ?? "standard");
  const [events, setEvents] = useState<StoredEvent[]>([]);
  const state = useMemo(() => replay(ticker, events), [ticker, events]);
  const saved = useRef(false);

  // 1. Is opening this ticker free (running, or recently analyzed at least this deep)? If not, ask first.
  useEffect(() => {
    let cancelled = false;
    const wanted = requestedDepth ?? preferredDepth();
    setDepth(wanted);
    setPhase({ kind: "checking" });
    fetchStatus(ticker, wanted).then((s: TickerStatus | null) => {
      if (cancelled) return;
      if (!s || s.free) return setPhase({ kind: "stream" }); // server unreachable: let the stream report it
      const depths = s.depths?.length ? s.depths : DEFAULT_DEPTHS;
      if (s.mode === "invite") {
        const inv = s.invite;
        if (!inv || inv.disabled) return setPhase({ kind: "gate", reason: "invite_required" });
        if (inv.remaining < Math.min(...depths.map((d) => d.credits))) return setPhase({ kind: "gate", reason: "no_credits" });
        return setPhase({ kind: "confirm", mode: "invite", remaining: inv.remaining, depths });
      }
      setPhase({ kind: "confirm", mode: "open", depths });
    });
    return () => {
      cancelled = true;
    };
  }, [ticker, requestedDepth]);

  // 2. Stream the council.
  useEffect(() => {
    if (phase.kind !== "stream") return;
    saved.current = false;
    setEvents([]);
    const source = new EventSource(analyzeUrl(ticker, depth));
    const received: StoredEvent[] = [];
    let finished = false;

    source.onmessage = (msg) => {
      const event = JSON.parse(msg.data) as StoredEvent;
      if (event.type === "error" && event.reason && ["invite_required", "no_credits"].includes(event.reason)) {
        finished = true;
        source.close();
        setPhase({ kind: "gate", reason: event.reason });
        return;
      }
      received.push(event);
      setEvents([...received]);
      if (event.type === "start" && !event.cached) {
        markRunning(ticker, event.company_name);
        creditsChanged();
      }
      if (event.type === "done" || event.type === "error") {
        finished = true;
        source.close();
        creditsChanged(); // a failed run is refunded server-side
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
  }, [ticker, phase.kind, depth]);

  if (phase.kind === "checking") return <div className="card h-40 animate-pulse" />;
  if (phase.kind === "confirm")
    return (
      <ConfirmRun
        ticker={ticker}
        phase={phase}
        initial={depth}
        onRun={(d) => {
          savePreferredDepth(d);
          setDepth(d);
          setPhase({ kind: "stream" });
        }}
      />
    );
  if (phase.kind === "gate") return <Gate ticker={ticker} reason={phase.reason} onUnlocked={() => setPhase({ kind: "checking" })} />;
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

function ConfirmRun({
  ticker,
  phase,
  initial,
  onRun,
}: {
  ticker: string;
  phase: Extract<Phase, { kind: "confirm" }>;
  initial: DepthId;
  onRun: (d: DepthId) => void;
}) {
  const credits = phase.mode === "invite";
  const affordable = (d: DepthOption) => !credits || (phase.remaining ?? 0) >= d.credits;
  const start = phase.depths.find((d) => d.id === initial && affordable(d)) ?? [...phase.depths].reverse().find(affordable) ?? phase.depths[0];
  const [choice, setChoice] = useState<DepthId>(start.id);
  const [freeDepths, setFreeDepths] = useState<DepthId[]>([]);

  // A lighter tier may already be cached (free); label it.
  useEffect(() => {
    Promise.all(phase.depths.map((d) => fetchStatus(ticker, d.id).then((s) => (s?.free ? d.id : null)))).then((ids) =>
      setFreeDepths(ids.filter((x): x is DepthId => x !== null)),
    );
  }, [ticker, phase.depths]);

  const chosen = phase.depths.find((d) => d.id === choice) ?? start;
  const isFree = freeDepths.includes(chosen.id);
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="card fade-up p-6 sm:p-8">
        <p className="text-sm text-brand-300">Fresh analysis</p>
        <h1 className="mt-1 text-3xl font-bold">{ticker}</h1>
        <p className="mt-2 text-zinc-400">
          How deep should the council go? Every depth uses the same 12 data sources, debate, challenger and verdict. Deeper means more capable
          models and more nuance.
        </p>
        <div className="mt-5">
          <DepthPicker options={phase.depths} value={choice} onChange={setChoice} showCredits={credits} remaining={phase.remaining} freeDepths={freeDepths} />
        </div>
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button onClick={() => onRun(chosen.id)} className="rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-5 py-2.5 font-semibold text-white shadow-lg shadow-brand-500/25 hover:brightness-110">
            {isFree ? `Open ${chosen.label} analysis (free)` : `Run ${chosen.label} analysis${credits ? ` · ${chosen.credits} ${chosen.credits === 1 ? "credit" : "credits"}` : ""}`}
          </button>
          <Link href="/" className="rounded-lg border border-white/10 px-5 py-2.5 text-zinc-300 hover:text-white">
            Cancel
          </Link>
          {credits && <span className="ml-auto text-sm text-zinc-500">{phase.remaining} credits left</span>}
        </div>
        {credits && <p className="mt-4 text-xs text-zinc-500">If the analysis fails, the credits are refunded automatically.</p>}
      </div>
      <FreeToView narrow />
    </div>
  );
}

function Gate({ ticker, reason, onUnlocked }: { ticker: string; reason: string; onUnlocked: () => void }) {
  const outOfCredits = reason === "no_credits";
  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div className="card fade-up p-6 sm:p-8">
        <p className="text-sm text-brand-300">{ticker}</p>
        <h1 className="mt-1 text-2xl font-bold">{outOfCredits ? "You're out of credits" : "Stock Council is invite-only for now"}</h1>
        <p className="mt-2 text-zinc-400">
          {outOfCredits
            ? "Thanks for trying it! Paid plans are coming soon. Meanwhile, stocks the council analyzed recently are still free to open, and so is everything in your History."
            : "Enter your invite code to run a fresh analysis. Stocks the council analyzed recently are free to open without one."}
        </p>
        {!outOfCredits && (
          <div className="mt-5">
            <InviteForm onDone={onUnlocked} />
          </div>
        )}
        {outOfCredits && getCode() && (
          <Link href="/invite" className="mt-4 inline-block text-sm text-brand-300 hover:underline">
            Have another code?
          </Link>
        )}
      </div>
      <FreeToView narrow />
    </div>
  );
}
