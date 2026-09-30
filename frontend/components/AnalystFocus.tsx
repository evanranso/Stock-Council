"use client";

import { useEffect, useRef } from "react";
import { ANALYST_BY_ID } from "@/lib/analysts";
import type { AnalystEntry } from "@/lib/council";
import { formatValue } from "@/lib/format";
import { HORIZONS, type Lean } from "@/lib/types";
import { publicNotes } from "./AnalystCard";
import { BarChart, LineChart, Meter } from "./charts";
import LeanBadge, { leanTone } from "./LeanBadge";

const HORIZON_LABEL: Record<string, string> = { weeks: "Next few weeks", months: "Next few months", years: "Next few years" };
const IMPLICATION: Record<Lean, { mark: string; cls: string; label: string }> = {
  bullish: { mark: "▲", cls: "border-emerald-400/25 bg-emerald-500/[0.06]", label: "text-emerald-300" },
  bearish: { mark: "▼", cls: "border-rose-400/25 bg-rose-500/[0.06]", label: "text-rose-300" },
  neutral: { mark: "●", cls: "border-white/10 bg-white/[0.03]", label: "text-zinc-400" },
};

/** One analyst's full report, full screen and in large type. ←/→ move between analysts, Esc closes. */
export default function AnalystFocus({
  id,
  entry,
  onClose,
  onPrev,
  onNext,
  position,
}: {
  id: string;
  entry: AnalystEntry;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
  position: { index: number; total: number };
}) {
  const meta = ANALYST_BY_ID[id];
  const op = entry.report.opinion;
  const metrics = entry.highlights?.metrics ?? [];
  const series = entry.highlights?.series;
  const scroller = useRef<HTMLDivElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);

  // Keyboard, focus, and no page scrolling underneath while open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft") onPrev();
      else if (e.key === "ArrowRight") onNext();
    };
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [onClose, onPrev, onNext]);

  // New analyst: start at the top.
  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 });
    closeBtn.current?.focus({ preventScroll: true });
  }, [id]);

  if (!op) return null;
  const notes = publicNotes(entry.notes);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#07080d]/95 backdrop-blur-md" role="dialog" aria-modal="true" aria-label={`${meta.name} full breakdown`}>
      {/* Top bar */}
      <div className="border-b border-white/10 bg-[#07080d]/80">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/5 text-xl" aria-hidden>
            {meta.icon}
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-lg font-semibold">{meta.name}</h2>
            <p className="text-xs text-zinc-500">
              Reads: {meta.reads} · {position.index + 1} of {position.total}
            </p>
          </div>
          <div className="hidden items-center gap-1 sm:flex">
            <NavButton onClick={onPrev} label="Previous analyst">
              ← Prev
            </NavButton>
            <NavButton onClick={onNext} label="Next analyst">
              Next →
            </NavButton>
          </div>
          <button
            ref={closeBtn}
            onClick={onClose}
            className="ml-1 grid h-9 w-9 place-items-center rounded-lg border border-white/10 text-zinc-300 hover:bg-white/10 hover:text-white"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
      </div>

      <div ref={scroller} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl space-y-8 px-4 py-8">
          {/* Their take */}
          <section className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm uppercase tracking-wider text-zinc-500">Overall</span>
              <LeanBadge lean={op.stance} />
              <div className="flex min-w-48 flex-1 items-center gap-2 sm:max-w-sm">
                <span className="text-xs uppercase tracking-wider text-zinc-500">Conviction</span>
                <Meter value={op.conviction} tone={leanTone(op.stance)} />
                <span className="w-8 text-right text-sm tabular-nums text-zinc-200">{op.conviction}</span>
              </div>
            </div>
            <p className="text-xl leading-relaxed text-zinc-100 sm:text-2xl sm:leading-relaxed">{op.headline}</p>
          </section>

          {/* Numbers and chart */}
          {(metrics.length > 0 || series) && (
            <section className="grid gap-4 lg:grid-cols-5">
              {metrics.length > 0 && (
                <dl className={`grid grid-cols-2 gap-3 ${series ? "lg:col-span-2" : "sm:grid-cols-4 lg:col-span-5"}`}>
                  {metrics.map((m) => (
                    <div key={m.label} className="rounded-xl bg-white/[0.04] px-4 py-3">
                      <dt className="text-xs text-zinc-500">{m.label}</dt>
                      <dd className="mt-0.5 text-xl font-semibold tabular-nums">{formatValue(m.value, m.format)}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {series && (
                <div className={`card p-5 ${metrics.length ? "lg:col-span-3" : "lg:col-span-5"}`}>
                  {series.points.length > 12 ? <LineChart series={series} height={240} /> : <BarChart series={series} height={220} />}
                </div>
              )}
            </section>
          )}

          {/* Findings */}
          {op.key_findings.length > 0 && (
            <section>
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-400">What they found</h3>
              <ul className="grid gap-3 md:grid-cols-2">
                {op.key_findings.map((f, i) => {
                  const s = IMPLICATION[f.implication] ?? IMPLICATION.neutral;
                  return (
                    <li key={i} className={`rounded-xl border p-4 ${s.cls}`}>
                      <div className="flex gap-2.5">
                        <span aria-hidden className={`mt-0.5 ${s.label}`}>
                          {s.mark}
                        </span>
                        <div className="space-y-1.5">
                          <p className="font-medium leading-snug text-zinc-100">{f.point}</p>
                          <p className="text-sm leading-relaxed text-zinc-400">{f.evidence}</p>
                          <p className={`text-xs font-medium uppercase tracking-wider ${s.label}`}>{f.implication}</p>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {/* Outlook by timeframe */}
          <section>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-400">Outlook by timeframe</h3>
            <div className="grid gap-3 md:grid-cols-3">
              {HORIZONS.map((h) => {
                const v = op.outlook[h];
                return (
                  <div key={h} className="card space-y-3 p-5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold">{HORIZON_LABEL[h] ?? h}</span>
                      <LeanBadge lean={v.lean} />
                    </div>
                    <div className="flex items-center gap-2">
                      <Meter value={v.conviction} tone={leanTone(v.lean)} />
                      <span className="w-8 text-right text-sm tabular-nums text-zinc-300">{v.conviction}</span>
                    </div>
                    <p className="leading-relaxed text-zinc-200">{v.rationale}</p>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Doubts */}
          <section className="grid gap-3 md:grid-cols-2">
            {op.risks_to_view.length > 0 && (
              <div className="card p-5">
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-zinc-400">Risks to this view</h3>
                <ul className="list-disc space-y-2 pl-5 leading-relaxed text-zinc-200">
                  {op.risks_to_view.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="card p-5">
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-zinc-400">What would change their mind</h3>
              <p className="leading-relaxed text-zinc-200">{op.what_would_change_my_mind}</p>
            </div>
          </section>

          {/* Sources */}
          <section className="rounded-xl border border-white/10 p-4 text-sm text-zinc-400">
            <div>
              <span className="text-zinc-500">Sources:</span> {entry.sources.join(", ") || "—"}
            </div>
            <div className="mt-1">
              <span className="text-zinc-500">Data quality:</span> {op.data_quality}
              {entry.asOf && (
                <>
                  {" "}
                  · <span className="text-zinc-500">fetched</span> {new Date(entry.asOf).toLocaleString()}
                </>
              )}
            </div>
            {notes.length > 0 && <div className="mt-1 text-zinc-500">{notes.join(" ")}</div>}
          </section>

          {/* Mobile prev/next */}
          <div className="flex justify-between gap-2 sm:hidden">
            <NavButton onClick={onPrev} label="Previous analyst">
              ← Prev
            </NavButton>
            <NavButton onClick={onNext} label="Next analyst">
              Next →
            </NavButton>
          </div>
        </div>
      </div>
    </div>
  );
}

function NavButton({ onClick, label, children }: { onClick: () => void; label: string; children: React.ReactNode }) {
  return (
    <button onClick={onClick} aria-label={label} className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-zinc-300 hover:bg-white/10 hover:text-white">
      {children}
    </button>
  );
}
