"use client";

import { useState } from "react";
import LeanBadge from "./LeanBadge";
import type { AnalystReport } from "@/lib/types";

export default function AnalystCard({
  name,
  reads,
  report,
  sources,
}: {
  name: string;
  reads: string;
  report?: AnalystReport;
  sources?: string[];
}) {
  const [open, setOpen] = useState(false);
  const op = report?.opinion;

  return (
    <div className="flex flex-col rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-semibold">{name}</div>
          <div className="text-xs text-zinc-500">{reads}</div>
        </div>
        {!report && <span className="animate-pulse text-xs text-zinc-500">reading…</span>}
        {op && <LeanBadge lean={op.stance} label={`${op.stance} · ${op.conviction}`} />}
        {report && !op && <span className="text-xs text-zinc-500">no data</span>}
      </div>

      {op && <p className="text-sm text-zinc-300">{op.headline}</p>}
      {report && !op && <p className="text-xs text-zinc-500">{report.error}</p>}

      {op && (
        <>
          <div className="mt-3 flex gap-1 text-[11px]">
            {(["weeks", "months", "years"] as const).map((h) => (
              <LeanBadge key={h} lean={op.outlook[h].lean} label={`${h} ${op.outlook[h].conviction}`} />
            ))}
          </div>
          <button onClick={() => setOpen(!open)} className="mt-3 self-start text-xs text-zinc-400 hover:text-zinc-200">
            {open ? "Hide detail" : "Show detail"}
          </button>
          {open && (
            <div className="mt-2 space-y-3 text-xs text-zinc-400">
              <ul className="space-y-2">
                {op.key_findings.map((f, i) => (
                  <li key={i}>
                    <span className="text-zinc-200">{f.point}</span> <span className="text-zinc-500">({f.evidence})</span>
                  </li>
                ))}
              </ul>
              {op.risks_to_view.length > 0 && (
                <div>
                  <div className="font-medium text-zinc-300">Against this view</div>
                  <ul className="list-disc pl-4">
                    {op.risks_to_view.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              )}
              <div>
                <span className="font-medium text-zinc-300">Would change my mind: </span>
                {op.what_would_change_my_mind}
              </div>
              <div className="text-zinc-500">
                Data quality: {op.data_quality}
                {sources && sources.length > 0 && <> · Sources: {sources.join(", ")}</>}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
