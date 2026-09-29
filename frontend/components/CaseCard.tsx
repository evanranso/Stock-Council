import type { CaseReport } from "@/lib/types";

export default function CaseCard({ side, data }: { side: "bull" | "bear"; data?: CaseReport }) {
  const accent = side === "bull" ? "border-emerald-700/60" : "border-rose-700/60";
  return (
    <div className={`rounded-lg border ${accent} bg-zinc-900/40 p-5`}>
      <h3 className="mb-2 text-lg font-semibold capitalize">{side} case</h3>
      {!data ? (
        <p className="animate-pulse text-sm text-zinc-500">Building the argument…</p>
      ) : (
        <div className="space-y-4 text-sm">
          <p className="text-zinc-200">{data.thesis}</p>
          <ol className="list-decimal space-y-2 pl-5 text-zinc-300">
            {data.arguments.map((a, i) => (
              <li key={i}>
                {a.claim} <span className="text-xs text-zinc-500">[{a.supporting_analysts.join(", ")}]</span>
              </li>
            ))}
          </ol>
          {data.catalysts.length > 0 && (
            <div className="text-zinc-400">
              <div className="mb-1 font-medium text-zinc-300">Catalysts</div>
              <ul className="list-disc space-y-1 pl-5">
                {data.catalysts.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="text-zinc-400">
            <span className="font-medium text-zinc-300">Weakest point: </span>
            {data.weakest_point}
          </div>
        </div>
      )}
    </div>
  );
}
