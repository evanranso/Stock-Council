import ScoreBar, { signed } from "./ScoreBar";
import { HORIZONS, type Scores } from "@/lib/types";

// Live formula scores while the debate runs, before the judge has ruled.
export default function ScoreStrip({ scores, label }: { scores: Scores; label: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 p-4">
      <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">{label}</div>
      <div className="grid gap-4 sm:grid-cols-3">
        {HORIZONS.map((h) => (
          <div key={h}>
            <div className="mb-1 flex justify-between text-sm">
              <span className="capitalize text-zinc-400">{h}</span>
              <span className="font-mono">{signed(scores[h].score)}</span>
            </div>
            <ScoreBar score={scores[h].score} />
            <div className="mt-1 text-xs text-zinc-500">confidence {scores[h].confidence}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
