"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { type AccessMode, analyzeUrl, creditsChanged, fetchStatus, getCode, type TickerStatus } from "@/lib/access";
import { authFetch, meChanged, useAuth } from "@/lib/auth";
import { DEFAULT_DEPTHS, type DepthId, type DepthOption, preferredDepth, savePreferredDepth } from "@/lib/depth";
import { replay } from "@/lib/council";
import { clearRunning, markRunning, saveCompleted } from "@/lib/history";
import type { StoredEvent } from "@/lib/types";
import { InviteForm } from "./AccessWidgets";
import DepthPicker from "./DepthPicker";
import FreeToView from "./FreeToView";
import LockedReport, { type Teaser } from "./LockedReport";
import ProgressView from "./ProgressView";
import Report from "./Report";

type Phase =
  | { kind: "checking" }
  | {
      kind: "confirm";
      mode: AccessMode;
      remaining?: number;
      depths: DepthOption[];
      error?: string;
      unlimited?: boolean;
      /** Run fresh even though a (locked) recent report exists. */
      fresh?: boolean;
    }
  | { kind: "gate"; reason: string }
  | { kind: "starting" }
  | { kind: "unreachable" }
  | { kind: "locked"; teaser?: Teaser; signedIn: boolean; remaining?: number | null; depths?: DepthOption[] }
  | { kind: "stream" };

// Live analysis: checks whether this is free or costs credits, lets the visitor pick a depth,
// streams events from the API, then shows the report.
export default function Council({ ticker, requestedDepth }: { ticker: string; requestedDepth?: DepthId }) {
  const [phase, setPhase] = useState<Phase>({ kind: "checking" });
  const [depth, setDepth] = useState<DepthId>(requestedDepth ?? "standard");
  const [events, setEvents] = useState<StoredEvent[]>([]);
  const state = useMemo(() => replay(ticker, events), [ticker, events]);
  const saved = useRef(false);
  const { ready, session, me } = useAuth();
  const [attempt, setAttempt] = useState(0);
  const signedIn = !!session;

  // 1. Is opening this ticker free (running, or recently analyzed at least this deep)? If not, ask first.
  useEffect(() => {
    if (!ready) return; // wait until we know whether this visitor is signed in
    let cancelled = false;
    const wanted = requestedDepth ?? preferredDepth();
    setDepth(wanted);
    setPhase({ kind: "checking" });
    fetchStatus(ticker, wanted).then((s: TickerStatus | null) => {
      if (cancelled) return;
      if (!s) return setPhase({ kind: "unreachable" });
      if (s.free && s.locked)
        return setPhase({ kind: "locked", teaser: s.teaser, signedIn: !!s.signed_in, remaining: s.remaining, depths: s.depths });
      if (s.free) return setPhase({ kind: "stream" });
      const depths = s.depths?.length ? s.depths : DEFAULT_DEPTHS;
      const cheapest = Math.min(...depths.map((d) => d.credits));
      if (s.mode === "accounts") {
        if (!s.signed_in) return setPhase({ kind: "gate", reason: "sign_in" });
        if (s.unlimited) return setPhase({ kind: "confirm", mode: "accounts", depths, unlimited: true });
        if ((s.remaining ?? 0) < cheapest) return setPhase({ kind: "gate", reason: "no_credits" });
        return setPhase({ kind: "confirm", mode: "accounts", remaining: s.remaining ?? 0, depths });
      }
      if (s.mode === "invite") {
        const inv = s.invite;
        if (!inv || inv.disabled) return setPhase({ kind: "gate", reason: "invite_required" });
        if (inv.remaining < cheapest) return setPhase({ kind: "gate", reason: "no_credits" });
        return setPhase({ kind: "confirm", mode: "invite", remaining: inv.remaining, depths });
      }
      setPhase({ kind: "confirm", mode: "open", depths });
    });
    return () => {
      cancelled = true;
    };
  }, [ticker, requestedDepth, ready, signedIn, attempt]);

  // 2. Stream the council.
  useEffect(() => {
    if (phase.kind !== "stream") return;
    saved.current = false;
    setEvents([]);
    const received: StoredEvent[] = [];
    let finished = false;
    let source: EventSource | null = null;
    let closed = false;

    // EventSource can't send the sign-in header, so signed-in pages get a short-lived pass for the URL.
    const open = async () => {
      let url = analyzeUrl(ticker, depth);
      if (signedIn) {
        try {
          const res = await authFetch("/api/stream-ticket", { method: "POST" });
          if (res.ok) url += `&ticket=${encodeURIComponent((await res.json()).ticket)}`;
        } catch {
          /* fall through: the server will answer "sign in" */
        }
      }
      if (closed) return;
      source = new EventSource(url);
      attach(source);
    };

    const attach = (source: EventSource) => {

    source.onmessage = (msg) => {
      const event = JSON.parse(msg.data) as StoredEvent;
      if (event.type === "error" && event.reason === "upgrade") {
        finished = true;
        source.close();
        setPhase({ kind: "locked", signedIn });
        return;
      }
      if (event.type === "error" && event.reason && ["invite_required", "no_credits", "sign_in"].includes(event.reason)) {
        finished = true;
        source.close();
        setPhase({ kind: "gate", reason: event.reason });
        return;
      }
      received.push(event);
      setEvents([...received]);
      if (event.type === "start" && !event.cached) {
        if (!signedIn) markRunning(ticker, event.company_name);
        creditsChanged();
      }
      if (event.type === "done" || event.type === "error") {
        finished = true;
        source.close();
        creditsChanged(); // a failed run is refunded server-side
        if (signedIn) meChanged();
        if (event.type === "done" && !saved.current) {
          saved.current = true;
          if (signedIn) {
            // Keep it in this account's history (a no-op if the server already saved it for us).
            const start = received.find((e) => e.type === "start");
            const runDepth = start && start.type === "start" ? start.depth : depth;
            authFetch("/api/me/history/save", { method: "POST", body: JSON.stringify({ ticker, depth: runDepth }) }).catch(() => undefined);
          } else {
            saveCompleted(ticker, received);
          }
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
    };
    open();
    return () => {
      closed = true;
      source?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker, phase.kind, depth]);

  // Signed-in accounts: charge and start the run on the server first (EventSource can't send a token), then follow it.
  async function startAccountRun(d: DepthId, depths: DepthOption[], remaining?: number, fresh = false) {
    setPhase({ kind: "starting" });
    try {
      const res = await authFetch(`/api/analyze/${encodeURIComponent(ticker)}/start?depth=${d}${fresh ? "&fresh=1" : ""}`, { method: "POST" });
      const body = await res.json().catch(() => ({}));
      if (res.ok) {
        meChanged();
        // Someone else's run is in progress and this account can't watch it: show that instead.
        if (body?.locked) return setPhase({ kind: "locked", teaser: { running: true, depth: body.depth }, signedIn: true });
        return setPhase({ kind: "stream" });
      }
      const reason = body?.detail?.reason;
      if (reason === "upgrade") return setPhase({ kind: "locked", signedIn: true, remaining, depths });
      if (res.status === 401 || res.status === 403) return setPhase({ kind: "gate", reason: res.status === 403 ? "verify_email" : "sign_in" });
      if (reason === "no_credits") return setPhase({ kind: "gate", reason: "no_credits" });
      const message = body?.detail?.message ?? (typeof body?.detail === "string" ? body.detail : "Couldn't start the analysis. Try again in a minute.");
      setPhase({ kind: "confirm", mode: "accounts", depths, remaining, error: message, unlimited: me?.unlimited });
    } catch {
      setPhase({ kind: "confirm", mode: "accounts", depths, remaining, error: "Couldn't reach the server. Try again in a minute.", unlimited: me?.unlimited });
    }
  }

  if (phase.kind === "checking" || phase.kind === "starting") return <Waiting />;
  if (phase.kind === "locked") {
    const depths = phase.depths?.length ? phase.depths : DEFAULT_DEPTHS;
    const cheapest = Math.min(...depths.map((d) => d.credits));
    const runOwn = () =>
      (phase.remaining ?? 0) < cheapest
        ? setPhase({ kind: "gate", reason: "no_credits" })
        : setPhase({ kind: "confirm", mode: "accounts", remaining: phase.remaining ?? 0, depths, fresh: true });
    return (
      <LockedReport
        ticker={ticker}
        teaser={phase.teaser}
        next={`/analyze?t=${ticker}`}
        signedIn={phase.signedIn}
        onRunOwn={phase.signedIn ? runOwn : undefined}
      />
    );
  }
  if (phase.kind === "unreachable")
    return (
      <div className="card mx-auto max-w-xl space-y-3 p-6 text-center">
        <h1 className="text-xl font-semibold">The server isn&apos;t responding</h1>
        <p className="text-sm text-zinc-400">It may still be waking up or restarting after an update. This usually clears within a minute.</p>
        <button onClick={() => setAttempt((n) => n + 1)} className="rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-5 py-2 font-semibold text-white">
          Try again
        </button>
      </div>
    );
  if (phase.kind === "confirm")
    return (
      <ConfirmRun
        ticker={ticker}
        phase={phase}
        initial={depth}
        onRun={(d, free) => {
          savePreferredDepth(d);
          setDepth(d);
          if (phase.mode === "accounts" && (!free || phase.fresh)) startAccountRun(d, phase.depths, phase.remaining, phase.fresh);
          else setPhase({ kind: "stream" });
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
  onRun: (d: DepthId, free: boolean) => void;
}) {
  const credits = (phase.mode === "invite" || phase.mode === "accounts") && !phase.unlimited;
  const affordable = (d: DepthOption) => !credits || (phase.remaining ?? 0) >= d.credits;
  const start = phase.depths.find((d) => d.id === initial && affordable(d)) ?? [...phase.depths].reverse().find(affordable) ?? phase.depths[0];
  const [choice, setChoice] = useState<DepthId>(start.id);
  const [freeDepths, setFreeDepths] = useState<DepthId[]>([]);

  // A lighter tier may already be cached (free); label it.
  useEffect(() => {
    // A recent report you can't open (someone else's, no Plus/Pro) isn't free for you.
    Promise.all(phase.depths.map((d) => fetchStatus(ticker, d.id).then((s) => (s?.free && !s.locked && !phase.fresh ? d.id : null)))).then((ids) =>
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
          <button onClick={() => onRun(chosen.id, isFree)} className="rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-5 py-2.5 font-semibold text-white shadow-lg shadow-brand-500/25 hover:brightness-110">
            {isFree ? `Open ${chosen.label} analysis (free)` : `Run ${chosen.label} analysis${credits ? ` · ${chosen.credits} ${chosen.credits === 1 ? "credit" : "credits"}` : ""}`}
          </button>
          <Link href="/" className="rounded-lg border border-white/10 px-5 py-2.5 text-zinc-300 hover:text-white">
            Cancel
          </Link>
          {phase.unlimited && <span className="ml-auto text-sm text-zinc-500">Admin account · unlimited, no credits used</span>}
          {credits && (
            <span className="ml-auto text-sm text-zinc-500">
              {phase.remaining} credits left
              {phase.mode === "accounts" && (
                <>
                  {" · "}
                  <Link href="/pricing" className="text-brand-300 hover:underline">
                    get more
                  </Link>
                </>
              )}
            </span>
          )}
        </div>
        {phase.error && <p className="mt-4 rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-200">{phase.error}</p>}
        {credits && <p className="mt-4 text-xs text-zinc-500">If the analysis fails, the credits are refunded automatically.</p>}
      </div>
      <FreeToView narrow />
    </div>
  );
}

function Gate({ ticker, reason, onUnlocked }: { ticker: string; reason: string; onUnlocked: () => void }) {
  const { session, me } = useAuth();
  const next = encodeURIComponent(`/analyze?t=${ticker}`);
  const primary = "rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-5 py-2.5 font-semibold text-white shadow-lg shadow-brand-500/25 hover:brightness-110";
  const secondary = "rounded-lg border border-white/10 px-5 py-2.5 text-zinc-300 hover:text-white";

  let title: string;
  let body: React.ReactNode;
  let actions: React.ReactNode = null;
  if (reason === "sign_in") {
    title = "Create a free account to run this analysis";
    body = `New accounts get ${me?.free_credits ?? 4} free credits: that's 2 Standard analyses. Just verify your email. Stocks the council analyzed recently stay free to open without an account.`;
    actions = (
      <div className="mt-6 flex flex-wrap gap-3">
        <Link href={`/login?mode=signup&next=${next}`} className={primary}>
          Sign up free
        </Link>
        <Link href={`/login?next=${next}`} className={secondary}>
          Log in
        </Link>
      </div>
    );
  } else if (reason === "verify_email") {
    title = "Verify your email first";
    body = "Open the link we emailed you, then come back to this page. Check your spam folder if you don't see it.";
  } else if (reason === "no_credits") {
    title = "You're out of credits";
    body = session
      ? "Get more credits to run fresh analyses. A plan adds credits every month, or buy a one-time pack. Stocks analyzed recently and everything in your History stay free to open."
      : "Thanks for trying it! Meanwhile, stocks the council analyzed recently are still free to open, and so is everything in your History.";
    actions = session ? (
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Link href="/pricing" className={primary}>
          Get more credits
        </Link>
        <Link href="/history" className={secondary}>
          Your history
        </Link>
        <Link href="/invite" className="text-sm text-zinc-400 hover:text-white">
          Have a code?
        </Link>
      </div>
    ) : getCode() ? (
      <Link href="/invite" className="mt-4 inline-block text-sm text-brand-300 hover:underline">
        Have another code?
      </Link>
    ) : null;
  } else {
    title = "Stock Council is invite-only for now";
    body = "Enter your invite code to run a fresh analysis. Stocks the council analyzed recently are free to open without one.";
    actions = (
      <div className="mt-5">
        <InviteForm onDone={onUnlocked} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div className="card fade-up p-6 sm:p-8">
        <p className="text-sm text-brand-300">{ticker}</p>
        <h1 className="mt-1 text-2xl font-bold">{title}</h1>
        <p className="mt-2 text-zinc-400">{body}</p>
        {actions}
      </div>
      <FreeToView narrow />
    </div>
  );
}

/** Loading placeholder that explains a long wait (free hosting sleeps when idle). */
function Waiting() {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 4000);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className="card grid h-40 animate-pulse place-items-center p-6 text-center text-sm text-zinc-400">
      {slow ? "Waking up the server. The first visit after a quiet spell can take up to a minute…" : ""}
    </div>
  );
}
