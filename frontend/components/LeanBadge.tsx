import type { Lean } from "@/lib/types";

const STYLES: Record<Lean, string> = {
  bullish: "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30",
  bearish: "bg-rose-500/15 text-rose-300 ring-rose-400/30",
  neutral: "bg-zinc-500/15 text-zinc-300 ring-zinc-400/25",
};
const ARROW: Record<Lean, string> = { bullish: "▲", bearish: "▼", neutral: "●" };

export default function LeanBadge({ lean, label, arrow = true }: { lean: Lean; label?: string; arrow?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${STYLES[lean]}`}>
      {arrow && <span aria-hidden className="text-[9px]">{ARROW[lean]}</span>}
      {label ?? lean}
    </span>
  );
}

export function leanTone(lean: Lean): "bull" | "bear" | "neutral" {
  return lean === "bullish" ? "bull" : lean === "bearish" ? "bear" : "neutral";
}
