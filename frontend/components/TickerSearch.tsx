"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { SearchUnavailable, searchTickers, TICKER_RE, type TickerMatch, warmApi } from "@/lib/api";

// Type a company name or ticker ("apple" -> AAPL) and pick from the dropdown.
export default function TickerSearch({ size = "lg", autoFocus = false }: { size?: "lg" | "sm"; autoFocus?: boolean }) {
  const router = useRouter();
  const listId = useId();
  const box = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<TickerMatch[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [loading, setLoading] = useState(false);
  const [slow, setSlow] = useState(false);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setMatches([]);
      setLoading(false);
      return;
    }
    const ctrl = new AbortController();
    setLoading(true);
    setSlow(false);
    const slowTimer = setTimeout(() => setSlow(true), 2500);
    const t = setTimeout(async () => {
      try {
        const found = await searchTickers(q, ctrl.signal);
        setMatches(found);
        setActive(found.length ? 0 : -1);
        setUnavailable(false);
      } catch (err) {
        if (err instanceof SearchUnavailable) {
          setMatches([]);
          setUnavailable(true);
        }
        /* otherwise aborted or offline: keep the last list */
      } finally {
        if (!ctrl.signal.aborted) {
          setLoading(false);
          setSlow(false);
        }
      }
    }, 140);
    return () => {
      ctrl.abort();
      clearTimeout(t);
      clearTimeout(slowTimer);
    };
  }, [query]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  function go(ticker: string) {
    setOpen(false);
    setQuery("");
    router.push(`/analyze?t=${encodeURIComponent(ticker)}`);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, matches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Escape") {
      setOpen(false);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const pick = matches[active];
      const typed = query.trim().toUpperCase();
      if (pick) go(pick.ticker);
      else if (TICKER_RE.test(typed)) go(typed);
    }
  }

  const lg = size === "lg";
  const showList = open && query.trim().length > 0;

  return (
    <div ref={box} className={`relative ${lg ? "mx-auto w-full max-w-xl" : "w-full"}`}>
      <div
        className={`flex items-center gap-2 rounded-xl border border-white/15 bg-white/[0.04] transition focus-within:border-brand-400/70 focus-within:bg-white/[0.06] focus-within:ring-4 focus-within:ring-brand-500/15 ${
          lg ? "px-4 py-3 shadow-2xl shadow-brand-500/10" : "px-3 py-1.5"
        }`}
      >
        <svg aria-hidden viewBox="0 0 20 20" className={`${lg ? "h-5 w-5" : "h-4 w-4"} shrink-0 text-zinc-500`} fill="currentColor">
          <path
            fillRule="evenodd"
            d="M9 3.5a5.5 5.5 0 1 0 3.3 9.9l3.15 3.15a.75.75 0 1 0 1.06-1.06l-3.15-3.15A5.5 5.5 0 0 0 9 3.5ZM5 9a4 4 0 1 1 8 0 4 4 0 0 1-8 0Z"
          />
        </svg>
        <input
          value={query}
          autoFocus={autoFocus}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            warmApi();
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
          placeholder={lg ? "Search a company or ticker — try “apple” or “NVDA”" : "Search stocks…"}
          className={`min-w-0 flex-1 bg-transparent placeholder:text-zinc-500 focus:outline-none ${lg ? "text-lg" : "text-sm"}`}
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-label="Search for a stock by company name or ticker"
        />
        {loading && <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-zinc-600 border-t-brand-400" />}
        {lg && (
          <button
            type="button"
            onClick={() => (matches[active] ? go(matches[active].ticker) : TICKER_RE.test(query.trim().toUpperCase()) && go(query.trim().toUpperCase()))}
            className="rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-brand-500/25 hover:brightness-110"
          >
            Analyze
          </button>
        )}
      </div>

      {showList && (
        <ul
          id={listId}
          role="listbox"
          className="absolute left-0 right-0 z-40 mt-2 max-h-80 overflow-auto rounded-xl border border-white/10 bg-[#0e1018]/95 p-1 shadow-2xl backdrop-blur-md"
        >
          {matches.map((m, i) => (
            <li
              key={m.ticker}
              role="option"
              aria-selected={i === active}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                go(m.ticker);
              }}
              className={`flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-left ${i === active ? "bg-brand-500/15" : ""}`}
            >
              <span className="w-16 shrink-0 font-mono text-sm font-semibold text-brand-300">{m.ticker}</span>
              <span className="min-w-0 flex-1 truncate text-sm text-zinc-200">{m.name}</span>
              {m.exchange && <span className="shrink-0 text-xs text-zinc-500">{m.exchange}</span>}
            </li>
          ))}
          {!loading && matches.length === 0 && (
            <li className="px-3 py-2 text-sm text-zinc-500">
              {unavailable ? "Company-name search is down for a minute. Type an exact ticker and press Enter." : "No matches."}{" "}
              {TICKER_RE.test(query.trim().toUpperCase()) && (
                <button className="text-brand-300 hover:underline" onMouseDown={() => go(query.trim().toUpperCase())}>
                  Analyze “{query.trim().toUpperCase()}”{unavailable ? "" : " anyway"}
                </button>
              )}
            </li>
          )}
          {loading && matches.length === 0 && (
            <li className="px-3 py-2 text-sm text-zinc-500">{slow ? "Waking up the server (first search can take ~30s)…" : "Searching…"}</li>
          )}
        </ul>
      )}
    </div>
  );
}
