import type { ChallengeReport } from "@/lib/types";

const SEVERITY = { low: "text-zinc-400", medium: "text-amber-300", high: "text-rose-300" } as const;

export default function ChallengePanel({ data }: { data?: ChallengeReport }) {
  return (
    <div className="rounded-lg border border-amber-700/50 bg-zinc-900/40 p-5">
      <h3 className="mb-2 text-lg font-semibold">Challenger</h3>
      {!data ? (
        <p className="animate-pulse text-sm text-zinc-500">Looking for leans that don&apos;t hold up…</p>
      ) : (
        <div className="space-y-4 text-sm">
          <ul className="space-y-3">
            {data.objections.map((o, i) => (
              <li key={i}>
                <div className={`text-xs font-semibold uppercase ${SEVERITY[o.severity]}`}>
                  {o.severity} · vs {o.target}
                </div>
                <div className="text-zinc-400">&ldquo;{o.claim_challenged}&rdquo;</div>
                <div className="text-zinc-200">{o.objection}</div>
                {o.affected_analysts.length > 0 && o.severity !== "low" && (
                  <div className="mt-1 text-xs text-zinc-500">
                    Weight cut for {o.affected_analysts.join(", ")} ({o.horizons.join(", ")})
                  </div>
                )}
              </li>
            ))}
          </ul>
          <div className="text-zinc-400">
            <span className="font-medium text-zinc-300">Echo chambers: </span>
            {data.shared_evidence.length === 0
              ? "none found."
              : data.shared_evidence.map((g, i) => (
                  <div key={i} className="mt-1">
                    {g.analyst_ids.join(", ")} all rest on &ldquo;{g.fact}&rdquo;, counted once.
                  </div>
                ))}
          </div>
          {data.leans_that_hold_up.length > 0 && (
            <div className="text-zinc-400">
              <span className="font-medium text-zinc-300">Holds up: </span>
              {data.leans_that_hold_up.join("; ")}
            </div>
          )}
          <p className="text-zinc-300">{data.net_assessment}</p>
        </div>
      )}
    </div>
  );
}
