// Analysis depth tiers. The server sends the live list (credit prices can change); this is the fallback.
export type DepthId = "quick" | "standard" | "deep";

export interface DepthOption {
  id: DepthId;
  label: string;
  credits: number;
  blurb: string;
  analyst_model?: string;
  debate_model?: string;
}

export const DEFAULT_DEPTHS: DepthOption[] = [
  { id: "quick", label: "Quick", credits: 1, blurb: "A fast first read. Same 12 data sources and debate, with a lighter model throughout." },
  { id: "standard", label: "Standard", credits: 2, blurb: "Analysts on a lighter model; the debate, challenger and judge on the most capable one." },
  { id: "deep", label: "Deep", credits: 3, blurb: "The most capable model for every agent. The most nuanced read." },
];

export const DEPTH_TIME: Record<DepthId, string> = { quick: "~1–2 min", standard: "~2–3 min", deep: "~3–5 min" };
export const DEPTH_ICON: Record<DepthId, string> = { quick: "⚡", standard: "⚖️", deep: "🔬" };
export const DEPTH_RANK: Record<DepthId, number> = { quick: 0, standard: 1, deep: 2 };

const KEY = "stockCouncil.depth.v1";

export function isDepth(v: unknown): v is DepthId {
  return v === "quick" || v === "standard" || v === "deep";
}

export function preferredDepth(): DepthId {
  try {
    const v = localStorage.getItem(KEY);
    return isDepth(v) ? v : "standard";
  } catch {
    return "standard";
  }
}

export function savePreferredDepth(d: DepthId): void {
  try {
    localStorage.setItem(KEY, d);
  } catch {
    /* ignore */
  }
}

export function modelName(id?: string): string {
  if (!id) return "";
  if (id.includes("opus")) return "Opus";
  if (id.includes("sonnet")) return "Sonnet";
  if (id.includes("haiku")) return "Haiku";
  return id;
}
