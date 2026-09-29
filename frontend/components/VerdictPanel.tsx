"use client";

import { useState } from "react";
import LeanBadge from "./LeanBadge";
import ScoreBar, { signed } from "./ScoreBar";
import { ANALYSTS } from "@/lib/analysts";
import { HORIZONS, type HorizonVerdict, type Verdict } from "@/lib/types";

const RATING: Record<Verdict["rating"], { label: string; cls: string }> = {
  strong_buy: { label: "Strong Buy", cls: "bg-emerald-500 text-emerald-950" },
  buy: { label: "Buy", cls: "bg-emerald-400/80 text-emerald-950" },
  hold: { label: "Hold", cls: "bg-zinc-300 text-zinc-900" },
  sell: { label: "Sell", cls: "bg-rose-400/80 text-rose-950" },
  strong_sell: { label: "Strong Sell", cls: "bg-rose-500 text-rose-950" },
};

const NAMES: Record<string, string> = Object.fromEntries(ANALYSTS.map((a) => [a.id, a.name]));

export default function VerdictPanel({ data }: { data?: Verdict }) {
  if (!data) {
    return (
      <div className="rounded-lg border border-zinc-700 p-6 text-sm text-zinc-500">
        <span className="animate-pulse">The judge is reviewing the formula…</span>
      </div>
    );
  }
  const r = RATING[data.rating];
  return (
    <div className="space-y-5 rounded-lg border border-zinc-600 bg-zinc-900/60 p-6">
      <div className="flex flex-wrap items-center gap-3">
        <span className={`rounded-md px-3 py-1 text-lg font-bold ${r.cls}`}>{r.label}</span>
        <span className="font-mono text-lg">{signed(data.score)}</span>
        <span className="text-sm text-zinc-400">Confidence {data.confidence}/100</span>
      </div>
      <p className="text-zinc-200">{data.summary}</p>

      <div className="grid gap-3 md:grid-cols-3">
        {HORIZONS.map((h) => (
          <HorizonCard key={h} name={h} v={data[h]} />
        ))}
      </div>

      <div className="grid gap-4 text-sm sm:grid-cols-2">
        <List title="Catalysts" items={data.key_catalysts} />
        <List title="Risks" items={data.key_risks} />
        <List title="Dissenting analysts" items={data.dissenting_analysts} />
        <div>
          <div className="mb-1 font-medium text-zinc-300">What would change the verdict</div>
          <p className="text-zinc-400">{data.what_would_change_the_verdict}</p>
        </div>
      </div>

      <p className="text-xs text-zinc-500">
        How this is scored: each analyst&apos;s conviction for each horizon is weighted by how relevant its data is
        to that horizon and by data quality. The challenger&apos;s objections cut weights, and the judge may adjust
        the result by at most 15 points with a stated reason. Scores run from −100 to +100, with ±20 as the
        Buy/Sell line. They measure strength of evidence, not the probability that the stock rises.
      </p>
    </div>
  );
}

function HorizonCard({ name, v }: { name: string; v: HorizonVerdict }) {
  const [open, setOpen] = useState(false);
  const drivers = v.scoring.contributions.filter((c) => Math.abs(c.points) >= 0.5);
  return (
    <div className="rounded-md border border-zinc-800 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase text-zinc-500">{name}</span>
        <LeanBadge lean={v.lean} label={`${signed(v.score)} · conf ${v.confidence}`} />
      </div>
      <ScoreBar score={v.score} marker={v.formula_score} />
      <div className="mt-2 text-xs text-zinc-500">
        Formula {signed(v.formula_score)}
        {v.adjustment !== 0 && ` → judge ${signed(v.adjustment)}: ${v.adjustment_reason}`}
      </div>
      <p className="mt-2 text-sm text-zinc-300">{v.rationale}</p>
      <button onClick={() => setOpen(!open)} className="mt-2 text-xs text-zinc-400 hover:text-zinc-200">
        {open ? "Hide drivers" : "What drove this"}
      </button>
      {open && (
        <ul className="mt-2 space-y-1 text-xs">
          {drivers.map((c) => (
            <li key={c.analyst_id} className="flex justify-between gap-2">
              <span className="text-zinc-400" title={c.penalties.join("\n")}>
                {NAMES[c.analyst_id] ?? c.analyst_id}
                {c.penalties.length > 0 && <span className="text-amber-400"> *</span>}
              </span>
              <span className={`font-mono ${c.points >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                {c.points >= 0 ? "+" : ""}
                {c.points.toFixed(1)}
              </span>
            </li>
          ))}
          {drivers.some((c) => c.penalties.length > 0) && (
            <li className="pt-1 text-zinc-500">* weight reduced by the challenger (hover for why)</li>
          )}
        </ul>
      )}
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <div className="mb-1 font-medium text-zinc-300">{title}</div>
      <ul className="list-disc space-y-1 pl-4 text-zinc-400">
        {items.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
    </div>
  );
}
