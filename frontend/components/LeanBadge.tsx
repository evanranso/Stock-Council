import type { Lean } from "@/lib/types";

const STYLES: Record<Lean, string> = {
  bullish: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  bearish: "bg-rose-500/15 text-rose-300 ring-rose-500/30",
  neutral: "bg-zinc-500/15 text-zinc-300 ring-zinc-500/30",
};

export default function LeanBadge({ lean, label }: { lean: Lean; label?: string }) {
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ring-1 ${STYLES[lean]}`}>
      {label ?? lean}
    </span>
  );
}
