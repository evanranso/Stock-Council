import { ANALYST_BY_ID } from "@/lib/analysts";
import type { ChallengeReport, Objection } from "@/lib/types";
import Disclosure from "./Disclosure";

const SEVERITY: Record<Objection["severity"], string> = {
  high: "bg-rose-500/15 text-rose-300 ring-rose-400/30",
  medium: "bg-amber-500/15 text-amber-300 ring-amber-400/30",
  low: "bg-zinc-500/15 text-zinc-300 ring-zinc-400/25",
};

function targetName(t: string): string {
  if (t === "bull") return "Bull case";
  if (t === "bear") return "Bear case";
  return ANALYST_BY_ID[t]?.name ?? t;
}

export default function ChallengePanel({ data }: { data?: ChallengeReport }) {
  if (!data) return <div className="card p-5 text-sm text-zinc-500">Not available.</div>;
  const counts = { high: 0, medium: 0, low: 0 };
  data.objections.forEach((o) => counts[o.severity]++);
  const sorted = [...data.objections].sort((a, b) => ["high", "medium", "low"].indexOf(a.severity) - ["high", "medium", "low"].indexOf(b.severity));

  return (
    <div className="card relative overflow-hidden border-amber-400/25 p-5">
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-amber-300 to-orange-400" />
      <div className="flex flex-wrap items-center gap-3">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-amber-400/15 text-base" aria-hidden>
          🧐
        </span>
        <h3 className="text-lg font-semibold">Challenger</h3>
        <div className="ml-auto flex gap-1.5 text-xs">
          {(["high", "medium", "low"] as const).map((s) => (
            <span key={s} className={`rounded-full px-2 py-0.5 ring-1 ${SEVERITY[s]}`}>
              {counts[s]} {s}
            </span>
          ))}
        </div>
      </div>

      <p className="mt-3 text-sm text-zinc-100">{data.headline ?? data.net_assessment}</p>

      <ul className="mt-4 space-y-2">
        {sorted.slice(0, 3).map((o, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <span className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium uppercase ring-1 ${SEVERITY[o.severity]}`}>{o.severity}</span>
            <span className="text-zinc-300">
              <span className="text-zinc-500">vs {targetName(o.target)}:</span> {o.claim_challenged}
            </span>
          </li>
        ))}
      </ul>

      {data.shared_evidence.length > 0 && (
        <div className="mt-4 rounded-lg border border-amber-400/20 bg-amber-400/5 p-3 text-sm">
          <div className="text-xs font-semibold uppercase tracking-wider text-amber-300">Echo chambers found</div>
          {data.shared_evidence.map((g, i) => (
            <p key={i} className="mt-1 text-zinc-300">
              {g.analyst_ids.map((id) => ANALYST_BY_ID[id]?.icon ?? id).join(" ")} all rest on “{g.fact}”, so they count once.
            </p>
          ))}
        </div>
      )}

      <div className="mt-4">
        <Disclosure label={`All ${data.objections.length} objections`} openLabel="Hide objections">
          <ul className="space-y-4 text-sm">
            {sorted.map((o, i) => (
              <li key={i} className="border-l-2 border-white/10 pl-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium uppercase ring-1 ${SEVERITY[o.severity]}`}>{o.severity}</span>
                  <span className="text-xs text-zinc-500">vs {targetName(o.target)}</span>
                </div>
                <p className="mt-1 text-zinc-400">“{o.claim_challenged}”</p>
                <p className="mt-1 text-zinc-200">{o.objection}</p>
                {o.affected_analysts.length > 0 && o.severity !== "low" && (
                  <p className="mt-1 text-xs text-zinc-500">
                    Weight cut for {o.affected_analysts.map((id) => ANALYST_BY_ID[id]?.name ?? id).join(", ")} ({o.horizons.join(", ")})
                  </p>
                )}
              </li>
            ))}
          </ul>
          {data.leans_that_hold_up.length > 0 && (
            <div className="mt-4 text-sm">
              <div className="text-xs font-semibold uppercase tracking-wider text-emerald-300">What holds up</div>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-zinc-300">
                {data.leans_that_hold_up.map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
              </ul>
            </div>
          )}
          <p className="mt-4 text-sm text-zinc-300">{data.net_assessment}</p>
        </Disclosure>
      </div>
    </div>
  );
}
