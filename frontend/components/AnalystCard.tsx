"use client";

import { ANALYST_BY_ID, isComingSoon, NO_DATA_TEXT } from "@/lib/analysts";
import type { AnalystEntry } from "@/lib/council";
import { formatValue } from "@/lib/format";
import { HORIZONS } from "@/lib/types";
import { Meter } from "./charts";
import LeanBadge, { leanTone } from "./LeanBadge";

export default function AnalystCard({ id, entry, onOpen }: { id: string; entry?: AnalystEntry; onOpen?: () => void }) {
  const meta = ANALYST_BY_ID[id];
  const op = entry?.report.opinion;
  const soon = !op && isComingSoon(id);
  const metrics = entry?.highlights?.metrics ?? [];
  const series = entry?.highlights?.series;

  return (
    <article className={`card flex flex-col p-4 ${op ? "" : "opacity-70"}`}>
      <header className="flex items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white/5 text-lg" aria-hidden>
          {meta.icon}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold">{meta.name}</h3>
          <p className="text-xs text-zinc-500">{meta.reads}</p>
        </div>
        {op ? <LeanBadge lean={op.stance} /> : soon ? <ComingSoon /> : <span className="text-xs text-zinc-500">no data</span>}
      </header>

      {op ? (
        <>
          <div className="mt-3 flex items-center gap-2">
            <span className="w-20 shrink-0 text-[11px] uppercase tracking-wider text-zinc-500">Conviction</span>
            <Meter value={op.conviction} tone={leanTone(op.stance)} />
            <span className="w-7 text-right text-xs tabular-nums text-zinc-300">{op.conviction}</span>
          </div>
          <button onClick={onOpen} className="mt-3 text-left" title="Read the full breakdown">
            <p className="line-clamp-3 text-sm text-zinc-200 hover:text-white">{op.headline}</p>
          </button>

          {metrics.length > 0 && (
            <dl className="mt-3 grid grid-cols-2 gap-2">
              {metrics.slice(0, 4).map((m) => (
                <div key={m.label} className="rounded-lg bg-white/[0.04] px-2.5 py-1.5">
                  <dt className="truncate text-[11px] text-zinc-500">{m.label}</dt>
                  <dd className="truncate text-sm font-semibold tabular-nums">{formatValue(m.value, m.format)}</dd>
                </div>
              ))}
            </dl>
          )}

          <div className="mt-3 flex flex-wrap gap-1">
            {HORIZONS.map((h) => (
              <LeanBadge key={h} lean={op.outlook[h].lean} label={`${h} ${op.outlook[h].conviction}`} />
            ))}
          </div>

          <div className="mt-auto pt-4">
            <button
              onClick={onOpen}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-sm text-zinc-300 hover:border-brand-400/50 hover:bg-white/5 hover:text-white"
            >
              <span aria-hidden>⤢</span> Full breakdown
            </button>
          </div>
        </>
      ) : (
        <p className="mt-3 text-xs text-zinc-500">
          {soon ? `${meta.name.replace(" Analyst", "")} coverage is joining the council soon.` : entry ? NO_DATA_TEXT : "Waiting…"}
        </p>
      )}
    </article>
  );
}

// Source notes are written for the analysts; hide the setup/plumbing ones (keys, blocked or paid sources) from visitors.
const PLUMBING = /api_key|finnhub|unavailable|blocks|paid|unreachable|fmp|\bkey\b/i;
export function publicNotes(notes: string[]): string[] {
  return notes.filter((n) => !PLUMBING.test(n));
}

export function ComingSoon() {
  return (
    <span className="rounded-full bg-brand-500/15 px-2 py-0.5 text-[11px] font-medium text-brand-300 ring-1 ring-brand-400/30">Coming soon</span>
  );
}
