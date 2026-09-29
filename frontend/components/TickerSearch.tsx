"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function TickerSearch() {
  const router = useRouter();
  const [value, setValue] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const ticker = value.trim().toUpperCase();
    if (/^[A-Z][A-Z0-9.\-]{0,9}$/.test(ticker)) router.push(`/t/${encodeURIComponent(ticker)}`);
  }

  return (
    <form onSubmit={submit} className="mx-auto flex max-w-md gap-2">
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Enter a ticker, e.g. NVDA"
        className="flex-1 rounded-md border border-zinc-700 bg-zinc-900 px-4 py-2 uppercase placeholder:normal-case placeholder:text-zinc-500 focus:border-zinc-400 focus:outline-none"
        aria-label="Ticker symbol"
      />
      <button type="submit" className="rounded-md bg-zinc-100 px-4 py-2 font-medium text-zinc-900 hover:bg-white">
        Convene
      </button>
    </form>
  );
}
