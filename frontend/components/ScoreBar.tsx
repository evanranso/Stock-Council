// A -100..+100 bar: bearish fills left of center in red, bullish fills right in green.
export default function ScoreBar({ score, marker }: { score: number; marker?: number }) {
  const pct = Math.min(Math.abs(score), 100) / 2;
  const bull = score >= 0;
  return (
    <div className="relative h-2 w-full rounded-full bg-zinc-800" role="img" aria-label={`score ${score.toFixed(0)}`}>
      <div className="absolute inset-y-0 left-1/2 w-px bg-zinc-600" />
      <div
        className={`absolute inset-y-0 rounded-full ${bull ? "bg-emerald-400" : "bg-rose-400"}`}
        style={bull ? { left: "50%", width: `${pct}%` } : { right: "50%", width: `${pct}%` }}
      />
      {marker !== undefined && marker !== score && (
        <div
          className="absolute -top-1 h-4 w-0.5 bg-zinc-300"
          style={{ left: `${50 + Math.max(-100, Math.min(100, marker)) / 2}%` }}
          title={`formula ${marker.toFixed(0)}`}
        />
      )}
    </div>
  );
}

export function signed(n: number): string {
  return `${n > 0 ? "+" : ""}${n.toFixed(0)}`;
}
