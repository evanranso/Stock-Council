"use client";

import Link from "next/link";

const FAKE = ["NVDA", "MSFT", "COST", "AMD", "JPM", "LLY", "UBER", "SHOP"];

/** The community library for non-subscribers: blurred stand-in cards behind an upgrade prompt. */
export default function LockedLibrary({
  total,
  signedIn,
  compact = false,
  next = "/community",
}: {
  total?: number;
  signedIn: boolean;
  compact?: boolean;
  next?: string;
}) {
  const count = compact ? 6 : 8;
  return (
    // Tall enough that the lock card on top always fits, whatever the screen width.
    <div className={`relative overflow-hidden rounded-2xl ${compact ? "min-h-[260px]" : "min-h-[440px]"}`}>
      <ul aria-hidden className={`pointer-events-none grid select-none gap-3 opacity-40 blur-[3px] grayscale ${compact ? "sm:grid-cols-3" : "lg:grid-cols-2"}`}>
        {FAKE.slice(0, count).map((t, i) => (
          <li key={t} className="card flex items-center gap-4 p-4">
            <div className="min-w-0 flex-1 space-y-2">
              <div className="font-mono text-lg font-bold">{t}</div>
              <div className="h-2 w-3/4 rounded bg-white/15" />
            </div>
            <span className={`rounded-lg px-2.5 py-1 text-xs font-bold ${i % 3 === 1 ? "bg-amber-200 text-amber-950" : "bg-emerald-300/90 text-emerald-950"}`}>
              {i % 3 === 1 ? "Hold" : "Buy"}
            </span>
          </li>
        ))}
      </ul>
      <div className="absolute inset-0 grid place-items-center p-4">
        <div className={`card w-full bg-[#0d0f17]/95 text-center shadow-2xl shadow-black/60 ${compact ? "max-w-sm p-4" : "max-w-md p-6"}`}>
          <div className="text-xl" aria-hidden>
            🔒
          </div>
          <h2 className={`mt-1 font-bold ${compact ? "text-base" : "text-xl"}`}>Community picks are a Plus &amp; Pro perk</h2>
          <p className="mt-1.5 text-sm text-zinc-400">
            {total ? `${total} ${total === 1 ? "analysis" : "analyses"} from the community, ` : "Every analysis from the community, "}
            filterable for the strongest buys and sells.
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <Link
              href="/pricing"
              className="rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-brand-500/25 hover:brightness-110"
            >
              See plans
            </Link>
            {!signedIn && (
              <Link href={`/login?mode=signup&next=${encodeURIComponent(next)}`} className="rounded-lg border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:text-white">
                Sign up free
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
