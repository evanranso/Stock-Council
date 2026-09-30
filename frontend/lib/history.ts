// Past analyses, saved in this browser (localStorage). Every access is guarded:
// storage can be full, disabled, or unavailable (private windows, previews).
import type { Rating, StoredEvent } from "./types";

const KEY = "stockCouncil.history.v1";
const MAX_ENTRIES = 25;

export interface HistoryEntry {
  id: string;
  ticker: string;
  name: string | null;
  status: "running" | "done";
  savedAt: string;
  rating?: Rating;
  score?: number;
  confidence?: number;
  bottomLine?: string;
  depth?: "quick" | "standard" | "deep";
  events?: StoredEvent[];
}

function read(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as HistoryEntry[]) : [];
  } catch {
    return [];
  }
}

function write(entries: HistoryEntry[]): void {
  let list = entries.slice(0, MAX_ENTRIES);
  // If storage is full, drop the oldest saved reports until it fits.
  while (list.length) {
    try {
      localStorage.setItem(KEY, JSON.stringify(list));
      window.dispatchEvent(new Event("stock-council-history"));
      return;
    } catch {
      list = list.slice(0, -1);
    }
  }
}

export function listHistory(): HistoryEntry[] {
  return read();
}

export function getEntry(id: string): HistoryEntry | undefined {
  return read().find((e) => e.id === id);
}

/** Record that an analysis started, so it shows under Recent even if the tab is closed mid-run. */
export function markRunning(ticker: string, name: string | null): void {
  const entries = read();
  if (entries.some((e) => e.ticker === ticker && e.status === "running")) return;
  write([{ id: `${ticker}-running`, ticker, name, status: "running", savedAt: new Date().toISOString() }, ...entries]);
}

export function saveCompleted(ticker: string, events: StoredEvent[]): string | null {
  const done = events.find((e) => e.type === "done");
  const verdict = events.find((e) => e.type === "verdict");
  const start = events.find((e) => e.type === "start");
  if (!done || !verdict || verdict.type !== "verdict") return null;
  const finished = (done.type === "done" && (done.run?.finished_at || done.run?.started_at)) || new Date().toISOString();
  const id = `${ticker}-${finished}`;
  const entry: HistoryEntry = {
    id,
    ticker,
    name: start && start.type === "start" ? start.company_name : null,
    status: "done",
    savedAt: finished,
    rating: verdict.verdict.rating,
    score: verdict.verdict.score,
    confidence: verdict.verdict.confidence,
    bottomLine: verdict.verdict.bottom_line ?? verdict.verdict.summary,
    depth: start && start.type === "start" ? start.depth : undefined,
    events: events.map(({ cached: _cached, ...e }) => e as StoredEvent),
  };
  const rest = read().filter((e) => e.id !== id && !(e.ticker === ticker && e.status === "running"));
  write([entry, ...rest]);
  return id;
}

export function clearRunning(ticker: string): void {
  write(read().filter((e) => !(e.ticker === ticker && e.status === "running")));
}

export function removeEntry(id: string): void {
  write(read().filter((e) => e.id !== id));
}

export function clearHistory(): void {
  write([]);
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
