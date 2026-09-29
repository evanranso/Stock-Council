import LeanBadge from "./LeanBadge";
import type { Verdict } from "@/lib/types";

const RATING: Record<Verdict["rating"], { label: string; cls: string }> = {
  strong_buy: { label: "Strong Buy", cls: "bg-emerald-500 text-emerald-950" },
  buy: { label: "Buy", cls: "bg-emerald-400/80 text-emerald-950" },
  hold: { label: "Hold", cls: "bg-zinc-300 text-zinc-900" },
  sell: { label: "Sell", cls: "bg-rose-400/80 text-rose-950" },
  strong_sell: { label: "Strong Sell", cls: "bg-rose-500 text-rose-950" },
};

export default function VerdictPanel({ data }: { data?: Verdict }) {
  if (!data) {
    return (
      <div className="rounded-lg border border-zinc-700 p-6 text-sm text-zinc-500">
        <span className="animate-pulse">The judge is deliberating…</span>
      </div>
    );
  }
  const r = RATING[data.rating];
  return (
    <div className="space-y-5 rounded-lg border border-zinc-600 bg-zinc-900/60 p-6">
      <div className="flex flex-wrap items-center gap-3">
        <span className={`rounded-md px-3 py-1 text-lg font-bold ${r.cls}`}>{r.label}</span>
        <span className="text-sm text-zinc-400">Confidence {data.confidence}/100</span>
      </div>
      <p className="text-zinc-200">{data.summary}</p>

      <div className="grid gap-3 sm:grid-cols-3">
        {(["weeks", "months", "years"] as const).map((h) => (
          <div key={h} className="rounded-md border border-zinc-800 p-3">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase text-zinc-500">{h}</span>
              <LeanBadge lean={data[h].lean} label={`${data[h].lean} · ${data[h].confidence}`} />
            </div>
            <p className="text-sm text-zinc-300">{data[h].rationale}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 text-sm sm:grid-cols-2">
        <List title="Catalysts" items={data.key_catalysts} />
        <List title="Risks" items={data.key_risks} />
        <List title="Dissenting analysts" items={data.dissenting_analysts} />
        <div>
          <div className="mb-1 font-medium text-zinc-300">What would change the verdict</div>
          <p className="text-zinc-400">{data.what_would_change_the_verdict}</p>
        </div>
      </div>
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <div className="mb-1 font-medium text-zinc-300">{title}</div>
      <ul className="list-disc space-y-1 pl-4 text-zinc-400">
        {items.map((x, i) => <li key={i}>{x}</li>)}
      </ul>
    </div>
  );
}
