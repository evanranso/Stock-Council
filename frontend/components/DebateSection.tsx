import { ANALYST_BY_ID } from "@/lib/analysts";
import type { CaseReport } from "@/lib/types";
import Disclosure from "./Disclosure";

function CaseColumn({ side, data }: { side: "bull" | "bear"; data?: CaseReport }) {
  const bull = side === "bull";
  const points = data?.key_points?.length ? data.key_points : data?.arguments.slice(0, 3).map((a) => a.claim) ?? [];
  return (
    <div className={`card relative overflow-hidden p-5 ${bull ? "border-emerald-400/25" : "border-rose-400/25"}`}>
      <div className={`absolute inset-x-0 top-0 h-1 ${bull ? "bg-gradient-to-r from-emerald-400 to-teal-300" : "bg-gradient-to-r from-rose-400 to-orange-300"}`} />
      <div className="flex items-center gap-2">
        <span className={`grid h-8 w-8 place-items-center rounded-lg text-base ${bull ? "bg-emerald-400/15" : "bg-rose-400/15"}`} aria-hidden>
          {bull ? "🐂" : "🐻"}
        </span>
        <h3 className="text-lg font-semibold">{bull ? "Bull case" : "Bear case"}</h3>
      </div>
      {!data ? (
        <p className="mt-3 text-sm text-zinc-500">Not available.</p>
      ) : (
        <>
          <ul className="mt-4 space-y-2.5">
            {points.map((p, i) => (
              <li key={i} className="flex gap-2.5 text-sm text-zinc-100">
                <span className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px] font-bold ${bull ? "bg-emerald-400/20 text-emerald-300" : "bg-rose-400/20 text-rose-300"}`}>
                  {i + 1}
                </span>
                {p}
              </li>
            ))}
          </ul>
          <div className="mt-4">
            <Disclosure label="Full case & sources" openLabel="Hide full case">
              <div className="space-y-4 text-sm text-zinc-300">
                <p>{data.thesis}</p>
                <div>
                  <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-500">Arguments</h4>
                  <ol className="space-y-2">
                    {data.arguments.map((a, i) => (
                      <li key={i}>
                        <div className="text-zinc-100">
                          {i + 1}. {a.claim}
                        </div>
                        <div className="text-zinc-400">{a.evidence}</div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {a.supporting_analysts.map((id) => (
                            <span key={id} className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-zinc-400">
                              {ANALYST_BY_ID[id]?.icon} {ANALYST_BY_ID[id]?.name ?? id}
                            </span>
                          ))}
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
                {data.catalysts.length > 0 && (
                  <div>
                    <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-500">Catalysts to watch</h4>
                    <ul className="list-disc space-y-1 pl-5">
                      {data.catalysts.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="rounded-lg bg-white/[0.04] p-3">
                  <span className="font-medium text-zinc-100">Weakest point: </span>
                  {data.weakest_point}
                </div>
              </div>
            </Disclosure>
          </div>
        </>
      )}
    </div>
  );
}

export default function DebateSection({ bull, bear }: { bull?: CaseReport; bear?: CaseReport }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <CaseColumn side="bull" data={bull} />
      <CaseColumn side="bear" data={bear} />
    </div>
  );
}
