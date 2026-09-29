"use client";

import { ANALYST_BY_ID } from "@/lib/analysts";
import type { AnalystEntry } from "@/lib/council";
import { formatValue } from "@/lib/format";
import { HORIZONS } from "@/lib/types";
import { BarChart, LineChart, Meter } from "./charts";
import Disclosure from "./Disclosure";
import LeanBadge, { leanTone } from "./LeanBadge";

export default function AnalystCard({ id, entry }: { id: string; entry?: AnalystEntry }) {
  const meta = ANALYST_BY_ID[id];
  const op = entry?.report.opinion;
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
        {op ? <LeanBadge lean={op.stance} /> : <span className="text-xs text-zinc-500">no data</span>}
      </header>

      {op ? (
        <>
          <div className="mt-3 flex items-center gap-2">
            <span className="w-20 shrink-0 text-[11px] uppercase tracking-wider text-zinc-500">Conviction</span>
            <Meter value={op.conviction} tone={leanTone(op.stance)} />
            <span className="w-7 text-right text-xs tabular-nums text-zinc-300">{op.conviction}</span>
          </div>
          <p className="mt-3 line-clamp-3 text-sm text-zinc-200">{op.headline}</p>

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
            <Disclosure>
              <div className="space-y-4 text-sm">
                {series && (series.points.length > 12 ? <LineChart series={series} height={140} /> : <BarChart series={series} height={120} />)}
                <div>
                  <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-500">Key findings</h4>
                  <ul className="space-y-2">
                    {op.key_findings.map((f, i) => (
                      <li key={i} className="flex gap-2">
                        <span aria-hidden className={f.implication === "bullish" ? "text-emerald-400" : f.implication === "bearish" ? "text-rose-400" : "text-zinc-500"}>
                          {f.implication === "bullish" ? "▲" : f.implication === "bearish" ? "▼" : "●"}
                        </span>
                        <span>
                          <span className="text-zinc-200">{f.point}</span> <span className="text-zinc-500">{f.evidence}</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-500">By horizon</h4>
                  <ul className="space-y-1.5 text-zinc-300">
                    {HORIZONS.map((h) => (
                      <li key={h}>
                        <span className="font-medium capitalize text-zinc-100">{h}:</span> {op.outlook[h].rationale}
                      </li>
                    ))}
                  </ul>
                </div>
                {op.risks_to_view.length > 0 && (
                  <div>
                    <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-500">Against this view</h4>
                    <ul className="list-disc space-y-1 pl-4 text-zinc-300">
                      {op.risks_to_view.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <p className="text-zinc-300">
                  <span className="font-medium text-zinc-100">Would change my mind: </span>
                  {op.what_would_change_my_mind}
                </p>
                {metrics.length > 4 && (
                  <dl className="grid grid-cols-2 gap-2">
                    {metrics.slice(4).map((m) => (
                      <div key={m.label} className="rounded-lg bg-white/[0.04] px-2.5 py-1.5">
                        <dt className="text-[11px] text-zinc-500">{m.label}</dt>
                        <dd className="text-sm font-semibold tabular-nums">{formatValue(m.value, m.format)}</dd>
                      </div>
                    ))}
                  </dl>
                )}
                <Sources entry={entry} quality={op.data_quality} />
              </div>
            </Disclosure>
          </div>
        </>
      ) : (
        <p className="mt-3 text-xs text-zinc-500">{entry?.report.error ?? "Waiting…"}</p>
      )}
    </article>
  );
}

function Sources({ entry, quality }: { entry?: AnalystEntry; quality: string }) {
  if (!entry) return null;
  return (
    <div className="rounded-lg border border-white/10 p-2.5 text-xs text-zinc-400">
      <div>
        <span className="text-zinc-500">Sources:</span> {entry.sources.join(", ") || "—"}
      </div>
      <div>
        <span className="text-zinc-500">Data quality:</span> {quality}
        {entry.asOf && (
          <>
            {" "}
            · <span className="text-zinc-500">fetched</span> {new Date(entry.asOf).toLocaleString()}
          </>
        )}
      </div>
      {entry.notes.length > 0 && <div className="mt-1 text-zinc-500">{entry.notes.join(" ")}</div>}
    </div>
  );
}
