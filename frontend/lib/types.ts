// Mirrors backend/app/schemas.py. Fields added later are optional so older saved runs still render.
export type Lean = "bullish" | "bearish" | "neutral";
export type Horizon = "weeks" | "months" | "years";
export const HORIZONS: Horizon[] = ["weeks", "months", "years"];

export interface HorizonView { lean: Lean; conviction: number; rationale: string }
export interface Finding { point: string; evidence: string; implication: Lean }

export interface AnalystOpinion {
  stance: Lean;
  conviction: number;
  headline: string;
  key_findings: Finding[];
  risks_to_view: string[];
  what_would_change_my_mind: string;
  data_quality: "good" | "partial" | "poor";
  outlook: Record<Horizon, HorizonView>;
}

export interface AnalystReport {
  analyst_id: string;
  analyst_name: string;
  packet_status: "ok" | "partial" | "unavailable";
  opinion: AnalystOpinion | null;
  error: string | null;
}

export type MetricFormat = "usd" | "usd_big" | "pct" | "rate" | "num" | "int" | "date" | "text";
export interface Metric { label: string; value: number | string; format: MetricFormat }
export interface Series { label: string; format: MetricFormat; points: { t: string; v: number }[] }
export interface Highlights { metrics: Metric[]; series: Series | null }

export interface Argument { claim: string; supporting_analysts: string[]; evidence: string }
export interface CaseReport {
  thesis: string;
  arguments: Argument[];
  catalysts: string[];
  weakest_point: string;
  key_points?: string[];
}

export interface Objection {
  target: string;
  claim_challenged: string;
  objection: string;
  severity: "low" | "medium" | "high";
  affected_analysts: string[];
  horizons: Horizon[];
}
export interface SharedEvidence { fact: string; analyst_ids: string[] }
export interface ChallengeReport {
  objections: Objection[];
  leans_that_hold_up: string[];
  shared_evidence: SharedEvidence[];
  net_assessment: string;
  headline?: string;
}

export interface Contribution {
  analyst_id: string;
  lean: Lean;
  conviction: number;
  weight: number;
  points: number;
  penalties: string[];
}
export interface HorizonScore {
  horizon: Horizon;
  score: number;
  confidence: number;
  evidence: number;
  agreement: number;
  contributions: Contribution[];
}
export type Scores = Record<Horizon, HorizonScore>;

export interface HorizonVerdict {
  lean: Lean;
  score: number;
  formula_score: number;
  adjustment: number;
  adjustment_reason: string;
  confidence: number;
  rationale: string;
  scoring: HorizonScore;
}
export type Rating = "strong_buy" | "buy" | "hold" | "sell" | "strong_sell";
export interface Verdict {
  rating: Rating;
  score: number;
  confidence: number;
  bottom_line?: string;
  reasons_for?: string[];
  reasons_against?: string[];
  summary: string;
  weeks: HorizonVerdict;
  months: HorizonVerdict;
  years: HorizonVerdict;
  key_catalysts: string[];
  key_risks: string[];
  dissenting_analysts: string[];
  what_would_change_the_verdict: string;
}

export type CouncilEvent =
  | { type: "start"; ticker: string; company_name: string | null; depth?: "quick" | "standard" | "deep"; analysts: { id: string; name: string }[] }
  | {
      type: "analyst";
      report: AnalystReport;
      sources: string[];
      notes: string[];
      as_of?: string;
      highlights?: Highlights;
    }
  | { type: "scores"; phase: "baseline" | "adjusted"; scores: Scores }
  | { type: "stage"; stage: "debate" | "challenge" | "verdict" }
  | { type: "case"; side: "bull" | "bear"; case: CaseReport }
  | { type: "challenge"; challenge: ChallengeReport }
  | { type: "verdict"; verdict: Verdict }
  | { type: "done"; run?: { ticker: string; finished_at?: string; started_at?: string } }
  | { type: "error"; message: string; reason?: string };

export type StoredEvent = CouncilEvent & { cached?: boolean };
