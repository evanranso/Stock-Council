import TickerSearch from "@/components/TickerSearch";
import { ANALYSTS } from "@/lib/analysts";

export default function Home() {
  return (
    <div className="space-y-12">
      <section className="space-y-4 pt-8 text-center">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Twelve analysts. No echo chamber.</h1>
        <p className="mx-auto max-w-2xl text-zinc-400">
          Each AI analyst reads only its own slice of the data and forms an independent view. Then a bull and a bear
          argue it out, a challenger calls out weak reasoning, and a judge delivers a verdict for the weeks, months,
          and years ahead.
        </p>
        <TickerSearch />
      </section>

      <section>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-500">The council</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {ANALYSTS.map((a) => (
            <div key={a.id} className="rounded-lg border border-zinc-800 p-3">
              <div className="text-sm font-medium">{a.name}</div>
              <div className="text-xs text-zinc-500">{a.reads}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
