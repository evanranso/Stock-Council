import Link from "next/link";
import RecentList from "@/components/RecentList";
import TickerSearch from "@/components/TickerSearch";
import { ComingSoon } from "@/components/AnalystCard";
import { ANALYSTS, isComingSoon } from "@/lib/analysts";

const STEPS = [
  { icon: "🔍", title: "12 independent reads", text: "Each analyst sees only its own data: charts, filings, insiders, options, macro and more." },
  { icon: "⚔️", title: "Bull vs bear", text: "Two advocates build the strongest honest case each way from the 12 reports." },
  { icon: "🧐", title: "The challenger", text: "Calls out thin evidence and echo chambers, and cuts the weight of weak arguments." },
  { icon: "⚖️", title: "One verdict", text: "A transparent score for weeks, months and years, with every driver shown." },
];

export default function Home() {
  return (
    <div className="space-y-16">
      <section className="space-y-6 pt-10 text-center">
        <p className="inline-flex items-center gap-2 rounded-full border border-brand-400/30 bg-brand-500/10 px-3 py-1 text-xs font-medium text-brand-300">
          <span className="h-1.5 w-1.5 rounded-full bg-brand-300" /> AI research council for any US stock
        </p>
        <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
          Twelve analysts.
          <br />
          <span className="brand-text">No echo chamber.</span>
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-zinc-400">
          Independent AI analysts each study one slice of the data, argue it out, and deliver a verdict you can trace back to every number.
        </p>
        <div className="pt-2">
          <TickerSearch autoFocus />
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">Recent analyses</h2>
          <Link href="/history" className="text-sm text-brand-300 hover:underline">
            View all →
          </Link>
        </div>
        <RecentList limit={6} />
      </section>

      <section>
        <h2 className="mb-4 text-lg font-semibold">How it works</h2>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.title} className="card p-5">
              <div className="flex items-center gap-2">
                <span className="text-xl" aria-hidden>
                  {s.icon}
                </span>
                <span className="text-xs font-semibold text-zinc-500">STEP {i + 1}</span>
              </div>
              <h3 className="mt-2 font-semibold">{s.title}</h3>
              <p className="mt-1 text-sm text-zinc-400">{s.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-semibold">The council</h2>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {ANALYSTS.map((a) => (
            <div key={a.id} className="card flex items-center gap-3 p-3">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-white/5 text-lg" aria-hidden>
                {a.icon}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{a.name}</div>
                <div className="text-xs text-zinc-500">{a.reads}</div>
              </div>
              {isComingSoon(a.id) && <ComingSoon />}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
