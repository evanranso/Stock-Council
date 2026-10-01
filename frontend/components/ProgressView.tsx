"use client";

import { useEffect, useState } from "react";
import { ANALYST_BY_ID, ANALYSTS, isComingSoon } from "@/lib/analysts";
import { ComingSoon } from "./AnalystCard";
import { type AnalystProgress, type CouncilState, type FeedItem, progress } from "@/lib/council";
import { formatValue } from "@/lib/format";
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
  const latest = state.feed[state.feed.length - 1];
  const activity =
    state.stage === "connecting"
      ? "Connecting to the council (the server may take ~30s to wake up)…"
      : state.stage === "analysts" && latest
        ? feedText(latest)
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

      {state.stage === "analysts" && state.feed.length > 0 && <Feed items={state.feed} />}

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

/** "SEC Filings Analyst found 179 filings in the last 12 months (SEC EDGAR)" */
function feedText(item: FeedItem): string {
  const a = ANALYST_BY_ID[item.analystId];
  if (!a) return "";
  if (item.step === "reading") return `${a.name} is weighing what it found${item.found[0] ? `: ${item.found[0]}` : ""}…`;
  if (item.status === "unavailable") return `${a.name} found no usable data`;
  if (item.found.length) return `${a.name} pulled ${item.found[0]}${item.sources[0] ? ` from ${item.sources[0]}` : ""}`;
  return `${a.name} pulled its data${item.sources[0] ? ` from ${item.sources.join(", ")}` : ""}`;
}

/** The newest findings across all analysts, newest first. */
function Feed({ items }: { items: FeedItem[] }) {
  const recent = items.filter((i) => i.step === "fetched").slice(-4).reverse();
  if (!recent.length) return null;
  return (
    <ul className="mt-4 space-y-1.5 rounded-xl border border-white/10 bg-black/20 p-3 text-xs" aria-label="Live research feed">
      {recent.map((item, n) => {
        const a = ANALYST_BY_ID[item.analystId];
        return (
          <li key={item.id} className={`fade-up flex items-start gap-2 ${n === 0 ? "text-zinc-200" : "text-zinc-500"}`}>
            <span aria-hidden>{a?.icon}</span>
            <span className="min-w-0">
              <span className="font-medium">{a?.name}</span>{" "}
              {item.status === "unavailable" ? "found no usable data" : item.found.length ? `pulled ${item.found.join(" · ")}` : "pulled its data"}
              {item.status !== "unavailable" && item.sources.length > 0 && <span className="text-zinc-500"> — {item.sources.join(", ")}</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** One analyst while the council runs: what it's pulling, what it found, then its view. */
function AnalystLive({ id, state }: { id: string; state: CouncilState }) {
  const a = ANALYST_BY_ID[id];
  const entry = state.analysts[id];
  const live: AnalystProgress | undefined = state.progress[id];
  const op = entry?.report.opinion;
  const found = live?.found ?? [];
  const sources = entry?.sources ?? live?.sources ?? [];
  const metrics = live?.metrics ?? entry?.highlights?.metrics.slice(0, 2) ?? [];
  const noData = (live?.status === "unavailable" || (entry && !op)) && !isComingSoon(id);

  let status: React.ReactNode;
  if (op) status = <LeanBadge lean={op.stance} label={`${op.stance} ${op.conviction}`} />;
  else if (isComingSoon(id)) status = <ComingSoon />;
  else if (noData) status = <span className="text-zinc-500">no data available</span>;
  else if (live?.step === "reading") status = <Working text="Weighing the evidence" />;
  else if (live?.step === "fetched") status = <Working text="Queued to analyze" />;
  else status = <Working text={a.pulling ?? "Gathering data"} />;

  return (
    <div className={`rounded-xl border p-3 transition ${op ? "fade-up border-white/10 bg-white/[0.03]" : live?.step === "reading" ? "border-brand-400/30 bg-brand-500/[0.04]" : "border-white/5"}`}>
      <div className="flex items-center gap-2">
        <span className={`text-lg ${op || noData || isComingSoon(id) ? "" : "animate-pulse"}`} aria-hidden>
          {a.icon}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-zinc-200">{a.name}</span>
      </div>
      <div className="mt-1.5 text-xs">{status}</div>
      {found.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-[11px] text-zinc-400">
          {found.map((f) => (
            <li key={f} className="flex gap-1.5">
              <span className="text-emerald-400" aria-hidden>
                ✓
              </span>
              {f}
            </li>
          ))}
        </ul>
      )}
      {metrics.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {metrics.map((m) => (
            <span key={m.label} className="rounded-md bg-white/5 px-1.5 py-0.5 text-[11px] text-zinc-300">
              {m.label} <span className="font-semibold tabular-nums text-zinc-100">{formatValue(m.value, m.format)}</span>
            </span>
          ))}
        </div>
      )}
      {sources.length > 0 && <div className="mt-2 truncate text-[10px] text-zinc-500">Source: {sources.join(", ")}</div>}
    </div>
  );
}

function Working({ text }: { text: string }) {
  return (
    <span className="flex items-center gap-1.5 text-zinc-400">
      <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-brand-300/30 border-t-brand-300" />
      {text}…
    </span>
  );
}
