"use client";

import { useEffect, useRef, useState } from "react";
import { ANALYST_BY_ID, ANALYSTS, isComingSoon } from "@/lib/analysts";
import { ComingSoon } from "./AnalystCard";
import { type CouncilState, progress } from "@/lib/council";
import { DEPTH_ICON } from "@/lib/depth";
import LeanBadge from "./LeanBadge";

const STEPS = [
  { key: "analysts", label: "12 analysts research independently" },
  { key: "debate", label: "Bull and bear build their cases" },
  { key: "challenge", label: "Challenger attacks weak reasoning" },
  { key: "verdict", label: "Judge delivers the verdict" },
] as const;
const ORDER = ["connecting", "analysts", "debate", "challenge", "verdict", "done"];

export default function ProgressView({ state }: { state: CouncilState }) {
  const target = progress(state);
  const [shown, setShown] = useState(0);
  const [tick, setTick] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  // Ease toward the real milestone, and creep slowly while waiting so the bar never looks frozen.
  useEffect(() => {
    const id = setInterval(() => {
      setShown((s) => (s < target ? Math.min(target, s + Math.max(0.6, (target - s) * 0.18)) : Math.min(s + 0.04, target + 4, 99)));
      setElapsed((e) => e + 0.2);
    }, 200);
    return () => clearInterval(id);
  }, [target]);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 2600);
    return () => clearInterval(id);
  }, []);

  const pending = ANALYSTS.filter((a) => !state.analysts[a.id]);
  const done = ANALYSTS.length - pending.length;
  const stageIdx = ORDER.indexOf(state.stage);
  const activity =
    state.stage === "connecting"
      ? "Connecting to the council (the server may take ~30s to wake up)…"
      : state.stage === "analysts" && pending.length
        ? `${pending[tick % pending.length].name} is ${pending[tick % pending.length].task}…`
        : state.stage === "debate"
          ? "The bull and bear advocates are weighing all 12 reports…"
          : state.stage === "challenge"
            ? "The challenger is hunting for weak and double-counted evidence…"
            : "The judge is checking the formula and writing the verdict…";

  return (
    <div className="card fade-up overflow-hidden p-6 sm:p-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-brand-300">
            Convening the council{state.depth && <> · {DEPTH_ICON[state.depth]} {state.depth[0].toUpperCase() + state.depth.slice(1)}</>}
          </p>
          <h1 className="text-3xl font-bold tracking-tight">
            {state.ticker}
            {state.companyName && <span className="ml-3 text-lg font-normal text-zinc-400">{state.companyName}</span>}
          </h1>
        </div>
        <div className="text-right text-sm text-zinc-400">
          <div className="text-2xl font-semibold tabular-nums text-zinc-100">{Math.floor(shown)}%</div>
          <div className="tabular-nums">{Math.floor(elapsed / 60)}:{String(Math.floor(elapsed % 60)).padStart(2, "0")} elapsed · usually 2–4 min</div>
        </div>
      </div>

      <div className="mt-5 h-3 w-full overflow-hidden rounded-full bg-white/10" role="progressbar" aria-valuenow={Math.floor(shown)} aria-valuemin={0} aria-valuemax={100}>
        <div className="relative h-full rounded-full bg-gradient-to-r from-brand-500 via-accent-500 to-fuchsia-400 transition-[width] duration-300" style={{ width: `${shown}%` }}>
          <div className="shimmer absolute inset-0" />
        </div>
      </div>
      <p className="mt-3 min-h-5 text-sm text-zinc-300" aria-live="polite">
        {activity}
      </p>

      <ol className="mt-6 grid gap-2 sm:grid-cols-4">
        {STEPS.map((step, i) => {
          const idx = ORDER.indexOf(step.key);
          const status = stageIdx > idx ? "done" : stageIdx === idx ? "active" : "todo";
          return (
            <li
              key={step.key}
              className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm ${
                status === "active" ? "border-brand-400/50 bg-brand-500/10 text-white" : status === "done" ? "border-emerald-400/30 text-zinc-300" : "border-white/10 text-zinc-500"
              }`}
            >
              <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px]">
                {status === "done" ? (
                  <span className="text-emerald-400">✓</span>
                ) : status === "active" ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-300/30 border-t-brand-300" />
                ) : (
                  <span className="text-zinc-600">{i + 1}</span>
                )}
              </span>
              <span>
                {step.label}
                {step.key === "analysts" && status !== "todo" && <span className="text-zinc-500"> ({done}/12)</span>}
              </span>
            </li>
          );
        })}
      </ol>

      <div className="mt-6 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {ANALYSTS.map((a) => (
          <AnalystLive key={a.id} id={a.id} state={state} />
        ))}
      </div>

      <p className="mt-6 text-xs text-zinc-500">
        You can leave this page. The analysis keeps running on the server, and you can come back to it from{" "}
        <span className="text-zinc-300">History</span>.
      </p>
    </div>
  );
}

/** Holds each value on screen for at least `ms`, so quick successive updates don't flicker. */
function useSteady<T>(value: T, ms = 2200): T {
  const [shown, setShown] = useState(value);
  const since = useRef(0);
  useEffect(() => {
    if (Object.is(value, shown)) return;
    const wait = Math.max(0, since.current + ms - Date.now());
    const t = setTimeout(() => {
      since.current = Date.now();
      setShown(value);
    }, wait);
    return () => clearTimeout(t);
  }, [value, shown, ms]);
  return shown;
}

/** "SEC filings" stays "SEC filings"; "Price charts" becomes "price charts". */
function lower(text: string): string {
  return text
    .split(" ")
    .map((w) => (w.length > 1 && w === w.toUpperCase() ? w : w.toLowerCase()))
    .join(" ");
}

/** One sentence about what the analyst is looking at right now. */
function sentence(id: string, state: CouncilState): string {
  const a = ANALYST_BY_ID[id];
  const live = state.progress[id];
  const entry = state.analysts[id];
  const what = live?.found?.[0];
  if (isComingSoon(id)) return `${a.reads} coverage is coming soon.`;
  if (entry && !entry.report.opinion) return "No usable data for this stock.";
  if (entry) return what ? `Read ${what}.` : `Finished reading ${lower(a.reads)}.`;
  if (live?.status === "unavailable") return "No usable data for this stock.";
  if (live?.step === "reading" || live?.step === "fetched") return what ? `Reading ${what}…` : `Reading ${lower(a.reads)}…`;
  return `${a.pulling ?? "Gathering data"}…`;
}

/** One analyst while the council runs: a fixed-size card with one line about what it's doing. */
function AnalystLive({ id, state }: { id: string; state: CouncilState }) {
  const a = ANALYST_BY_ID[id];
  const op = state.analysts[id]?.report.opinion;
  const line = useSteady(sentence(id, state));
  const finished = useSteady(!!state.analysts[id]);
  const soon = isComingSoon(id);

  return (
    <div className={`flex h-[74px] flex-col justify-center rounded-xl border px-3 transition-colors duration-700 ${finished && op ? "border-white/10 bg-white/[0.03]" : "border-white/5"}`}>
      <div className="flex items-center gap-2">
        <span className={`text-lg ${finished || soon ? "" : "animate-pulse opacity-70"}`} aria-hidden>
          {a.icon}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-zinc-200">{a.name}</span>
        <span className="shrink-0 text-[11px]">
          {soon ? (
            <ComingSoon />
          ) : finished && op ? (
            <LeanBadge lean={op.stance} label={`${op.stance} ${op.conviction}`} />
          ) : finished ? (
            <span className="text-zinc-500">no data</span>
          ) : (
            <span className="block h-3 w-3 animate-spin rounded-full border-2 border-brand-300/30 border-t-brand-300" aria-label="working" />
          )}
        </span>
      </div>
      <p key={line} className="fade-up mt-1 truncate pl-7 text-xs text-zinc-400" title={line}>
        {line}
      </p>
    </div>
  );
}
