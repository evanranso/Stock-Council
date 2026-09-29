// Folds the stream of council events into page state. Used for live runs and saved history alike.
import type { AnalystReport, CaseReport, ChallengeReport, Highlights, Scores, StoredEvent, Verdict } from "./types";

export interface AnalystEntry {
  report: AnalystReport;
  sources: string[];
  notes: string[];
  asOf?: string;
  highlights?: Highlights;
}

export type Stage = "connecting" | "analysts" | "debate" | "challenge" | "verdict" | "done";

export interface CouncilState {
  ticker: string;
  companyName: string | null;
  stage: Stage;
  analysts: Record<string, AnalystEntry>;
  baseline?: Scores;
  adjusted?: Scores;
  bull?: CaseReport;
  bear?: CaseReport;
  challenge?: ChallengeReport;
  verdict?: Verdict;
  finishedAt?: string;
  cached: boolean;
  error?: string;
}

export function initialState(ticker: string): CouncilState {
  return { ticker, companyName: null, stage: "connecting", analysts: {}, cached: false };
}

export function reduce(state: CouncilState, event: StoredEvent): CouncilState {
  const s = { ...state, cached: state.cached || !!event.cached };
  switch (event.type) {
    case "start":
      return { ...s, companyName: event.company_name, stage: "analysts" };
    case "analyst":
      return {
        ...s,
        stage: s.stage === "connecting" ? "analysts" : s.stage,
        analysts: {
          ...s.analysts,
          [event.report.analyst_id]: {
            report: event.report,
            sources: event.sources,
            notes: event.notes,
            asOf: event.as_of,
            highlights: event.highlights,
          },
        },
      };
    case "scores":
      return { ...s, [event.phase]: event.scores };
    case "stage":
      return { ...s, stage: event.stage };
    case "case":
      return { ...s, [event.side]: event.case };
    case "challenge":
      return { ...s, challenge: event.challenge };
    case "verdict":
      return { ...s, verdict: event.verdict };
    case "done":
      return { ...s, stage: "done", finishedAt: event.run?.finished_at ?? s.finishedAt };
    case "error":
      return { ...s, error: event.message };
  }
}

export function replay(ticker: string, events: StoredEvent[]): CouncilState {
  return events.reduce(reduce, initialState(ticker));
}

/** 0-100 progress for the loading bar, driven by real milestones. */
export function progress(state: CouncilState): number {
  const n = Object.keys(state.analysts).length;
  switch (state.stage) {
    case "connecting":
      return 2;
    case "analysts":
      return 5 + Math.round((55 * n) / 12);
    case "debate":
      return 62 + (state.bull ? 8 : 0) + (state.bear ? 8 : 0);
    case "challenge":
      return state.challenge ? 88 : 80;
    case "verdict":
      return state.verdict ? 99 : 91;
    case "done":
      return 100;
  }
}
