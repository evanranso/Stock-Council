import { ANALYST_BY_ID } from "@/lib/analysts";
import { signed } from "@/lib/format";
import { HORIZONS, type Scores, type Verdict } from "@/lib/types";
import Disclosure from "./Disclosure";
import ScoreBar from "./ScoreBar";

const STEP = "rounded-lg bg-white/[0.04] px-2 py-1 text-center";

// How each horizon's number was built: analysts -> challenger penalties -> judge nudge -> final.
export default function ScoringSection({ verdict, baseline }: { verdict: Verdict; baseline?: Scores }) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {HORIZONS.map((h) => {
        const v = verdict[h];
        const drivers = v.scoring.contributions.filter((c) => Math.abs(c.points) >= 0.5);
        const maxPts = Math.max(1, ...drivers.map((c) => Math.abs(c.points)));
        return (
          <div key={h} className="card p-4">
            <div className="flex items-baseline justify-between">
              <h3 className="font-semibold capitalize">{h}</h3>
              <span className="text-2xl font-bold tabular-nums">{signed(v.score)}</span>
            </div>
            <div className="mt-2">
              <ScoreBar score={v.score} marker={v.formula_score} />
            </div>
            <div className="mt-3 flex items-center gap-1 text-[11px] text-zinc-400">
              {baseline && (
                <>
                  <span className={STEP}>
                    Analysts
                    <br />
                    <b className="text-zinc-100">{signed(baseline[h].score)}</b>
                  </span>
                  <span aria-hidden>→</span>
                </>
              )}
              <span className={STEP}>
                Challenged
                <br />
                <b className="text-zinc-100">{signed(v.formula_score)}</b>
              </span>
              <span aria-hidden>→</span>
              <span className={STEP}>
                Judge
                <br />
                <b className="text-zinc-100">{v.adjustment ? signed(v.adjustment) : "±0"}</b>
              </span>
              <span aria-hidden>→</span>
              <span className={`${STEP} bg-brand-500/15`}>
                Final
                <br />
                <b className="text-zinc-100">{signed(v.score)}</b>
              </span>
            </div>
            <p className="mt-2 text-xs text-zinc-500">Confidence {v.confidence}/100</p>

            <div className="mt-3">
              <Disclosure label="What drove this" openLabel="Hide drivers">
                <ul className="space-y-1.5 text-xs">
                  {drivers.map((c) => (
                    <li key={c.analyst_id} className="grid grid-cols-[1fr_5rem_2.5rem] items-center gap-2">
                      <span className="truncate text-zinc-300" title={c.penalties.join("\n")}>
                        {ANALYST_BY_ID[c.analyst_id]?.icon} {ANALYST_BY_ID[c.analyst_id]?.name ?? c.analyst_id}
                        {c.penalties.length > 0 && <span className="text-amber-400"> *</span>}
                      </span>
                      <span className="relative h-1.5 rounded-full bg-white/10">
                        <span
                          className={`absolute inset-y-0 rounded-full ${c.points >= 0 ? "left-1/2 bg-emerald-400" : "right-1/2 bg-rose-400"}`}
                          style={{ width: `${(Math.abs(c.points) / maxPts) * 50}%` }}
                        />
                      </span>
                      <span className={`text-right font-mono ${c.points >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                        {c.points >= 0 ? "+" : ""}
                        {c.points.toFixed(1)}
                      </span>
                    </li>
                  ))}
                </ul>
                {drivers.some((c) => c.penalties.length) && <p className="mt-2 text-[11px] text-zinc-500">* weight cut by the challenger (hover for why)</p>}
                {v.adjustment !== 0 && (
                  <p className="mt-2 text-xs text-zinc-400">
                    <span className="text-zinc-200">Judge {signed(v.adjustment)}:</span> {v.adjustment_reason}
                  </p>
                )}
              </Disclosure>
            </div>
          </div>
        );
      })}
    </div>
  );
}
