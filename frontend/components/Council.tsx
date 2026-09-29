"use client";

import { useEffect, useReducer } from "react";
import AnalystCard from "./AnalystCard";
import CaseCard from "./CaseCard";
import ChallengePanel from "./ChallengePanel";
import VerdictPanel from "./VerdictPanel";
import { ANALYSTS } from "@/lib/analysts";
import type { AnalystReport, CaseReport, ChallengeReport, CouncilEvent, Verdict } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface State {
  companyName: string | null;
  reports: Record<string, AnalystReport>;
  stage: "analysts" | "debate" | "challenge" | "verdict" | "done";
  bull?: CaseReport;
  bear?: CaseReport;
  challenge?: ChallengeReport;
  verdict?: Verdict;
  cached: boolean;
  error?: string;
}

const initial: State = { companyName: null, reports: {}, stage: "analysts", cached: false };

function reducer(state: State, event: CouncilEvent & { cached?: boolean }): State {
  const s = { ...state, cached: state.cached || !!event.cached };
  switch (event.type) {
    case "start":
      return { ...s, companyName: event.company_name };
    case "analyst":
      return { ...s, reports: { ...s.reports, [event.report.analyst_id]: event.report } };
    case "stage":
      return { ...s, stage: event.stage };
    case "case":
      return { ...s, [event.side]: event.case };
    case "challenge":
      return { ...s, challenge: event.challenge };
    case "verdict":
      return { ...s, verdict: event.verdict };
    case "done":
      return { ...s, stage: "done" };
    case "error":
      return { ...s, error: event.message };
  }
}

export default function Council({ ticker }: { ticker: string }) {
  const [state, dispatch] = useReducer(reducer, initial);

  useEffect(() => {
    const source = new EventSource(`${API}/api/analyze/${encodeURIComponent(ticker)}`);
    let finished = false;
    source.onmessage = (msg) => {
      const event = JSON.parse(msg.data) as CouncilEvent;
      dispatch(event);
      if (event.type === "done" || event.type === "error") {
        finished = true;
        source.close();
      }
    };
    source.onerror = () => {
      // EventSource auto-reconnects, which would start a second (paid) run. Never let it.
      source.close();
      if (!finished) dispatch({ type: "error", message: "Lost connection to the council (or hit the rate limit)." });
    };
    return () => source.close();
  }, [ticker]);

  const debating = state.stage !== "analysts";
  const done = Object.keys(state.reports).length;

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-3xl font-bold">{ticker}</h1>
        {state.companyName && <p className="text-zinc-400">{state.companyName}</p>}
        {state.cached && <p className="mt-1 text-xs text-zinc-500">Showing a recent cached run.</p>}
      </div>

      {state.error && (
        <div className="rounded-md border border-rose-800 bg-rose-950/40 p-3 text-sm text-rose-200">{state.error}</div>
      )}

      <section>
        <SectionTitle n={1} title="Independent analysts" note={`${done}/12 reported`} />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {ANALYSTS.map((a) => (
            <AnalystCard key={a.id} name={a.name} reads={a.reads} report={state.reports[a.id]} />
          ))}
        </div>
      </section>

      {debating && (
        <section>
          <SectionTitle n={2} title="Bull vs. bear" />
          <div className="grid gap-4 md:grid-cols-2">
            <CaseCard side="bull" data={state.bull} />
            <CaseCard side="bear" data={state.bear} />
          </div>
        </section>
      )}

      {(state.stage === "challenge" || state.stage === "verdict" || state.stage === "done") && (
        <section>
          <SectionTitle n={3} title="Challenger" />
          <ChallengePanel data={state.challenge} />
        </section>
      )}

      {(state.stage === "verdict" || state.stage === "done") && (
        <section>
          <SectionTitle n={4} title="Verdict" />
          <VerdictPanel data={state.verdict} />
        </section>
      )}

      <p className="text-xs text-zinc-600">
        AI-generated research from public data. Not investment advice. Data can be delayed or incomplete.
      </p>
    </div>
  );
}

function SectionTitle({ n, title, note }: { n: number; title: string; note?: string }) {
  return (
    <div className="mb-3 flex items-baseline gap-3">
      <span className="text-xs font-semibold text-zinc-500">0{n}</span>
      <h2 className="text-xl font-semibold">{title}</h2>
      {note && <span className="text-xs text-zinc-500">{note}</span>}
    </div>
  );
}
