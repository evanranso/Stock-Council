"use client";

import Link from "next/link";
import { ANALYST_BY_ID } from "@/lib/analysts";
import { DEPTH_ICON, type DepthId } from "@/lib/depth";
import { RATING_LABEL, RATING_STYLE, signed } from "@/lib/format";
import { HORIZON_FOR, HORIZON_LONG, HORIZON_ORDER, HORIZON_TAB, ratingFor, useHorizon } from "@/lib/horizon";
import { HORIZONS, type Rating, type Verdict } from "@/lib/types";
import { Meter, ScoreGauge } from "./charts";
import Disclosure from "./Disclosure";
import ScoreBar from "./ScoreBar";

const HORIZON_LABEL = HORIZON_LONG;

function glow(rating: Rating): string {
  if (rating.includes("buy")) return "from-emerald-500/20 via-emerald-500/5";
  if (rating.includes("sell")) return "from-rose-500/20 via-rose-500/5";
  return "from-amber-400/15 via-amber-400/5";
}

export default function VerdictHero({
  ticker,
  companyName,
  verdict,
  finishedAt,
  cached,
  depth,
}: {
  ticker: string;
  companyName: string | null;
  verdict: Verdict;
  finishedAt?: string;
  cached?: boolean;
  depth?: DepthId;
}) {
  const [horizon, setHorizon] = useHorizon();
  const chosen = verdict[horizon];
  // Ratings come from each horizon's score (recomputed here so older reports use the current bands).
  const rating = ratingFor(chosen.score);
  const reasonsFor = verdict.reasons_for ?? verdict.key_catalysts.slice(0, 3);
  const reasonsAgainst = verdict.reasons_against ?? verdict.key_risks.slice(0, 3);

  return (
    <section id="verdict" className={`card fade-up relative overflow-hidden bg-gradient-to-br ${glow(rating)} to-transparent p-6 sm:p-8`}>
      <div className="flex flex-wrap items-start gap-6">
        <div className="min-w-0 flex-1">
          <p className="text-sm text-zinc-400">
            The council&apos;s verdict
            {finishedAt && <> · {new Date(finishedAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</>}
            {cached && <> · recent saved run</>}
            {depth && (
              <span className="ml-2 rounded-full bg-white/5 px-2 py-0.5 text-xs text-zinc-300">
                {DEPTH_ICON[depth]} {depth[0].toUpperCase() + depth.slice(1)} analysis
              </span>
            )}
          </p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl">
            {ticker}
            {companyName && <span className="ml-3 align-middle text-lg font-normal text-zinc-400">{companyName}</span>}
          </h1>
          <div className="mt-4 flex flex-wrap items-center gap-2" role="radiogroup" aria-label="Your timeframe">
            <span className="mr-1 text-xs uppercase tracking-wider text-zinc-500">Your timeframe</span>
            {HORIZON_ORDER.map((h) => (
              <button
                key={h}
                role="radio"
                aria-checked={h === horizon}
                onClick={() => setHorizon(h)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  h === horizon ? "bg-white text-zinc-900 shadow" : "bg-white/5 text-zinc-300 ring-1 ring-white/10 hover:bg-white/10 hover:text-white"
                }`}
              >
                {HORIZON_TAB[h]}
              </button>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <span className={`rounded-xl px-4 py-1.5 text-xl font-bold shadow-lg ${RATING_STYLE[rating]}`}>{RATING_LABEL[rating]}</span>
            <span className="text-sm text-zinc-400">{HORIZON_FOR[horizon]}</span>
            <div className="w-40">
              <div className="mb-1 flex justify-between text-xs text-zinc-400">
                <span>Confidence</span>
                <span className="font-semibold text-zinc-100">{chosen.confidence}/100</span>
              </div>
              <Meter value={chosen.confidence} />
            </div>
          </div>
          <p className="mt-4 max-w-2xl text-lg leading-snug text-zinc-100">{verdict.bottom_line ?? verdict.summary}</p>
          <p className="mt-2 max-w-2xl text-sm text-zinc-400">
            <span className="font-medium text-zinc-200">{HORIZON_LONG[horizon]}: </span>
            {chosen.rationale}
          </p>
        </div>
        <div className="flex flex-col items-center">
          <ScoreGauge score={chosen.score} />
          <span className="text-xs text-zinc-500">Score · {HORIZON_TAB[horizon].toLowerCase()}</span>
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl bg-emerald-400/[0.06] p-4 ring-1 ring-emerald-400/20">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-emerald-300">Why</h2>
          <ul className="mt-2 space-y-1.5 text-sm text-zinc-200">
            {reasonsFor.map((r, i) => (
              <li key={i} className="flex gap-2">
                <span aria-hidden className="text-emerald-400">✓</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl bg-rose-400/[0.06] p-4 ring-1 ring-rose-400/20">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-rose-300">What could go wrong</h2>
          <ul className="mt-2 space-y-1.5 text-sm text-zinc-200">
            {reasonsAgainst.map((r, i) => (
              <li key={i} className="flex gap-2">
                <span aria-hidden className="text-rose-400">!</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {HORIZONS.map((h) => (
          <button
            key={h}
            onClick={() => setHorizon(h)}
            aria-pressed={h === horizon}
            className={`rounded-xl border p-3 text-left transition ${
              h === horizon ? "border-brand-400/60 bg-brand-500/[0.08]" : "border-white/10 bg-black/20 hover:border-white/25"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-zinc-400">{HORIZON_LABEL[h]}</span>
              <span className={`rounded-md px-2 py-0.5 text-xs font-bold ${RATING_STYLE[ratingFor(verdict[h].score)]}`}>
                {RATING_LABEL[ratingFor(verdict[h].score)]} {signed(verdict[h].score)}
              </span>
            </div>
            <div className="mt-2.5">
              <ScoreBar score={verdict[h].score} />
            </div>
            <p className="mt-2 line-clamp-2 text-xs text-zinc-400">{verdict[h].rationale}</p>
          </button>
        ))}
      </div>

      {depth && depth !== "deep" && (
        <div className="mt-5 flex flex-wrap items-center gap-3 rounded-xl border border-brand-400/25 bg-brand-500/[0.07] px-4 py-3 text-sm">
          <span className="text-zinc-300">
            This was a {depth === "quick" ? "Quick" : "Standard"} analysis. A Deep analysis uses the most capable model for every agent.
          </span>
          <Link href={`/analyze?t=${ticker}&depth=deep`} className="ml-auto rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-3 py-1.5 font-semibold text-white">
            🔬 Go deeper
          </Link>
        </div>
      )}

      <div className="mt-5">
        <Disclosure label="Full verdict" openLabel="Hide full verdict">
          <div className="grid gap-5 text-sm text-zinc-300 md:grid-cols-2">
            <p className="md:col-span-2">{verdict.summary}</p>
            {HORIZONS.map((h) => (
              <p key={h}>
                <span className="font-medium text-zinc-100">{HORIZON_LABEL[h]}: </span>
                {verdict[h].rationale}
              </p>
            ))}
            <List title="Catalysts" items={verdict.key_catalysts} />
            <List title="Key risks" items={verdict.key_risks} />
            <List
              title="Analysts the verdict disagrees with"
              items={verdict.dissenting_analysts.map((d) => {
                const [id, ...rest] = d.split(":");
                return ANALYST_BY_ID[id.trim()] ? `${ANALYST_BY_ID[id.trim()].name}:${rest.join(":")}` : d;
              })}
            />
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-zinc-500">What would change the verdict</h4>
              <p>{verdict.what_would_change_the_verdict}</p>
            </div>
          </div>
        </Disclosure>
      </div>
    </section>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-zinc-500">{title}</h4>
      <ul className="list-disc space-y-1 pl-4">
        {items.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
    </div>
  );
}
