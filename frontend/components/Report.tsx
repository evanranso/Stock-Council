"use client";

import { useCallback, useEffect, useState } from "react";
import { ANALYSTS, isComingSoon } from "@/lib/analysts";
import type { CouncilState } from "@/lib/council";
import { formatValue } from "@/lib/format";
import AnalystCard from "./AnalystCard";
import AnalystFocus from "./AnalystFocus";
import ChallengePanel from "./ChallengePanel";
import { BarChart, LineChart, VoteBar } from "./charts";
import DebateSection from "./DebateSection";
import ScoringSection from "./ScoringSection";
import VerdictHero from "./VerdictHero";

const SECTIONS = [
  { id: "verdict", label: "Verdict" },
  { id: "glance", label: "At a glance" },
  { id: "analysts", label: "Analysts" },
  { id: "debate", label: "Bull vs bear" },
  { id: "challenger", label: "Challenger" },
  { id: "scoring", label: "How it was scored" },
];

function SectionTitle({ id, title, sub }: { id: string; title: string; sub?: string }) {
  return (
    <div id={id} className="mb-4 scroll-mt-32">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      {sub && <p className="text-sm text-zinc-500">{sub}</p>}
    </div>
  );
}

export default function Report({ state }: { state: CouncilState }) {
  const { verdict } = state;
  // Full-screen analyst reader. Opening it adds a history entry, so Back (or a phone's back swipe) closes it.
  const [focus, setFocusState] = useState<string | null>(null);
  const readable: string[] = ANALYSTS.map((a) => a.id).filter((id) => state.analysts[id]?.report.opinion);
  const focusIndex = focus ? readable.indexOf(focus) : -1;
  const setFocus = useCallback((id: string) => {
    setFocusState((current) => {
      if (!current) window.history.pushState({ analyst: id }, "");
      return id;
    });
  }, []);
  const closeFocus = useCallback(() => window.history.back(), []);
  useEffect(() => {
    const onPop = () => setFocusState(null);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  if (!verdict) return null;
  const entries = Object.values(state.analysts);
  const opinions = entries.map((e) => e.report.opinion).filter((o) => o !== null);
  const vote = {
    bull: opinions.filter((o) => o.stance === "bullish").length,
    neutral: opinions.filter((o) => o.stance === "neutral").length,
    bear: opinions.filter((o) => o.stance === "bearish").length,
    // "Coming soon" analysts aren't counted as missing data.
    missing: ANALYSTS.filter((a) => !state.analysts[a.id]?.report.opinion && !isComingSoon(a.id)).length,
  };
  const priceSeries = state.analysts.price?.highlights?.series;
  const revenueSeries = state.analysts.financials?.highlights?.series;
  const stats = [
    ...(state.analysts.price?.highlights?.metrics ?? []).filter((m) => ["Last close", "1-year"].includes(m.label)),
    ...(state.analysts.financials?.highlights?.metrics ?? []).filter((m) =>
      ["P/E (TTM)", "Revenue growth (TTM)", "Operating margin (TTM)"].includes(m.label),
    ),
    ...(state.analysts.options?.highlights?.metrics ?? []).filter((m) => m.label === "Implied move"),
  ];

  return (
    <div className="space-y-10">
      <VerdictHero ticker={state.ticker} companyName={state.companyName} verdict={verdict} finishedAt={state.finishedAt} cached={state.cached} depth={state.depth} />

      <nav className="sticky top-[57px] z-20 -mx-4 overflow-x-auto border-b border-white/5 bg-[#07080d]/85 px-4 py-2 backdrop-blur-md" aria-label="Report sections">
        <ul className="flex gap-1.5 text-sm">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a href={`#${s.id}`} className="block whitespace-nowrap rounded-full border border-white/10 px-3 py-1 text-zinc-300 hover:border-brand-400/50 hover:bg-brand-500/10 hover:text-white">
                {s.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <section>
        <SectionTitle id="glance" title="At a glance" sub="The numbers behind the call." />
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="card p-5 lg:col-span-2">
            {priceSeries ? <LineChart series={priceSeries} /> : <p className="text-sm text-zinc-500">No price history available.</p>}
          </div>
          <div className="card flex flex-col gap-5 p-5">
            <div>
              <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-zinc-500">How the analysts lean</h3>
              <VoteBar {...vote} />
            </div>
            {stats.length > 0 && (
              <dl className="grid grid-cols-2 gap-2">
                {stats.map((m) => (
                  <div key={m.label} className="rounded-lg bg-white/[0.04] px-3 py-2">
                    <dt className="text-[11px] text-zinc-500">{m.label}</dt>
                    <dd className="text-base font-semibold tabular-nums">{formatValue(m.value, m.format)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
          {revenueSeries && (
            <div className="card p-5 lg:col-span-3">
              <BarChart series={revenueSeries} width={1100} height={170} />
            </div>
          )}
        </div>
      </section>

      <section>
        <SectionTitle id="analysts" title="The 12 analysts" sub="Each read only its own data. Open a card for the full breakdown and sources." />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {ANALYSTS.map((a) => (
            <AnalystCard key={a.id} id={a.id} entry={state.analysts[a.id]} onOpen={() => setFocus(a.id)} />
          ))}
        </div>
        {focus && focusIndex >= 0 && (
          <AnalystFocus
            id={focus}
            entry={state.analysts[focus]!}
            position={{ index: focusIndex, total: readable.length }}
            onClose={closeFocus}
            onPrev={() => setFocus(readable[(focusIndex - 1 + readable.length) % readable.length])}
            onNext={() => setFocus(readable[(focusIndex + 1) % readable.length])}
          />
        )}
      </section>

      <section>
        <SectionTitle id="debate" title="Bull vs bear" sub="Each side built its strongest honest case from the 12 reports." />
        <DebateSection bull={state.bull} bear={state.bear} />
      </section>

      <section>
        <SectionTitle id="challenger" title="Challenger" sub="Objections to leans that don't hold up. High-severity objections cut an analyst's weight." />
        <ChallengePanel data={state.challenge} />
      </section>

      <section>
        <SectionTitle
          id="scoring"
          title="How it was scored"
          sub="Analyst convictions weighted by relevance and data quality, then cut by the challenger, then nudged (±15 max) by the judge."
        />
        <ScoringSection verdict={verdict} baseline={state.baseline} />
        <p className="mt-3 text-xs text-zinc-500">Scores run from −100 to +100; ±20 is the Buy/Sell line. They measure strength of evidence, not the probability of the stock rising.</p>
      </section>
    </div>
  );
}
