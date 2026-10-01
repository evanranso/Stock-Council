"use client";

import Link from "next/link";
import { DEPTH_ICON, type DepthId } from "@/lib/depth";
import { RATING_LABEL, RATING_STYLE, signed, timeAgo } from "@/lib/format";
import { atHorizon, HORIZON_FOR, type HorizonScores, useHorizon } from "@/lib/horizon";
import type { Rating } from "@/lib/types";

export interface Teaser {
  name?: string | null;
  depth?: DepthId | null;
  scores?: HorizonScores;
  rating?: Rating | null;
  score?: number | null;
  bottom_line?: string | null;
  finished_at?: string | null;
  running?: boolean;
}

/** A report for account holders only: the headline shows, the rest is greyed out behind a sign-up prompt. */
export default function LockedReport({ ticker, teaser, next }: { ticker: string; teaser?: Teaser; next: string }) {
  const [horizon] = useHorizon();
  const at = teaser ? atHorizon(teaser.scores, horizon, teaser) : { rating: null, score: null };
  const nextParam = encodeURIComponent(next);

  return (
    <div className="space-y-4">
      <section className="card fade-up p-6 sm:p-8">
        <p className="text-sm text-zinc-400">
          {teaser?.running ? "Being analyzed right now" : "Community analysis"}
          {teaser?.finished_at && <> · {timeAgo(teaser.finished_at)}</>}
          {teaser?.depth && (
            <span className="ml-2 rounded-full bg-white/5 px-2 py-0.5 text-xs text-zinc-300">
              {DEPTH_ICON[teaser.depth]} {teaser.depth[0].toUpperCase() + teaser.depth.slice(1)} analysis
            </span>
          )}
        </p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl">
          {ticker}
          {teaser?.name && <span className="ml-3 align-middle text-lg font-normal text-zinc-400">{teaser.name}</span>}
        </h1>
        {at.rating && (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <span className={`rounded-xl px-4 py-1.5 text-xl font-bold shadow-lg ${RATING_STYLE[at.rating]}`}>{RATING_LABEL[at.rating]}</span>
            <span className="text-sm text-zinc-400">
              {HORIZON_FOR[horizon]}
              {at.score !== null && <> · score {signed(at.score)}</>}
            </span>
          </div>
        )}
        {teaser?.bottom_line && <p className="mt-4 max-w-2xl text-lg leading-snug text-zinc-100">{teaser.bottom_line}</p>}
      </section>

      <div className="relative overflow-hidden rounded-2xl">
        {/* Greyed-out stand-in for the full report: reasons, 12 analysts, bull vs bear, challenger, scoring. */}
        <div aria-hidden className="pointer-events-none select-none space-y-4 opacity-40 blur-[3px] grayscale">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="card h-36" />
            <div className="card h-36" />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="card space-y-2 p-4">
                <div className="h-3 w-1/2 rounded bg-white/20" />
                <div className="h-2 w-full rounded bg-white/10" />
                <div className="h-2 w-4/5 rounded bg-white/10" />
                <div className="h-2 w-2/3 rounded bg-white/10" />
              </div>
            ))}
          </div>
          <div className="card h-40" />
        </div>
        <div className="absolute inset-0 grid place-items-center p-4">
          <div className="card w-full max-w-md bg-[#0d0f17]/95 p-6 text-center shadow-2xl shadow-black/60">
            <div className="text-2xl" aria-hidden>
              🔒
            </div>
            <h2 className="mt-2 text-xl font-bold">
              {teaser?.running ? "Sign in to watch this analysis live" : "Sign in to see the full community analysis"}
            </h2>
            <p className="mt-2 text-sm text-zinc-400">
              All 12 analyst reports, the bull and bear cases, the challenger, and how it was scored. Free with an account, and new accounts get
              free credits to run their own.
            </p>
            <div className="mt-5 flex justify-center gap-3">
              <Link
                href={`/login?mode=signup&next=${nextParam}`}
                className="rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-5 py-2.5 font-semibold text-white shadow-lg shadow-brand-500/25 hover:brightness-110"
              >
                Sign up free
              </Link>
              <Link href={`/login?next=${nextParam}`} className="rounded-lg border border-white/10 px-5 py-2.5 text-zinc-300 hover:text-white">
                Log in
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
