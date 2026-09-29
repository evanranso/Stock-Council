"use client";

import { useCallback, useEffect, useState } from "react";
import type { Invite } from "@/lib/access";
import { API } from "@/lib/api";
import { timeAgo } from "@/lib/format";

const KEY = "stockCouncil.admin.v1";

interface Window {
  runs: number;
  completed: number;
  cost: number;
  input_tokens: number;
  output_tokens: number;
  avg_cost_per_completed_run: number | null;
}
interface RunRow {
  ticker: string;
  started: number;
  finished: number;
  status: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  invite_label: string | null;
  detail: { agent: string; model: string; input_tokens: number; output_tokens: number; cost_usd: number }[];
}
interface Stats {
  today: Window;
  last_7_days: Window;
  all_time: Window;
  recent_runs: RunRow[];
  live_runs: string[];
  settings: Record<string, string | number>;
}

const usd = (n: number | null | undefined, digits = 2) => (n === null || n === undefined ? "—" : `$${n.toFixed(digits)}`);

export default function AdminPage() {
  const [key, setKey] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      setKey(localStorage.getItem(KEY));
    } catch {
      /* no storage: enter the key each visit */
    }
  }, []);

  const call = useCallback(
    async (path: string, init?: RequestInit) => {
      const res = await fetch(`${API}${path}`, { ...init, headers: { "Content-Type": "application/json", "X-Admin-Key": key ?? "", ...init?.headers } });
      if (res.status === 401) throw new Error("Wrong admin key.");
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `Error ${res.status}`);
      return res.json();
    },
    [key],
  );

  const load = useCallback(async () => {
    if (!key) return;
    try {
      const [s, i] = await Promise.all([call("/api/admin/stats"), call("/api/admin/invites")]);
      setStats(s);
      setInvites(i);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [key, call]);

  useEffect(() => {
    load();
  }, [load]);

  function saveKey(k: string | null) {
    setKey(k);
    try {
      if (k) localStorage.setItem(KEY, k);
      else localStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  }

  if (!key) {
    return (
      <div className="mx-auto max-w-md space-y-4 pt-8">
        <h1 className="text-2xl font-bold">Admin</h1>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            saveKey(draft.trim());
          }}
          className="card flex gap-2 p-4"
        >
          <input type="password" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="ADMIN_KEY" className="flex-1 rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2 focus:outline-none" aria-label="Admin key" />
          <button className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white">Sign in</button>
        </form>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold tracking-tight">Admin</h1>
        {stats && (
          <span className="rounded-full bg-white/5 px-3 py-1 text-xs text-zinc-400">
            {stats.settings.access_mode === "invite" ? "Invite-only" : "Open to everyone"} · {stats.settings.model}
          </span>
        )}
        <button onClick={load} className="ml-auto rounded-lg border border-white/10 px-3 py-1.5 text-sm text-zinc-300 hover:text-white">
          Refresh
        </button>
        <button onClick={() => saveKey(null)} className="rounded-lg px-3 py-1.5 text-sm text-zinc-500 hover:text-white">
          Sign out
        </button>
      </div>
      {error && <div className="card border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</div>}

      {stats && (
        <section className="grid gap-3 md:grid-cols-3">
          {(
            [
              ["Last 24 hours", stats.today],
              ["Last 7 days", stats.last_7_days],
              ["All time", stats.all_time],
            ] as const
          ).map(([label, w]) => (
            <div key={label} className="card p-5">
              <div className="text-xs uppercase tracking-wider text-zinc-500">{label}</div>
              <div className="mt-1 text-3xl font-bold tabular-nums">{usd(w.cost)}</div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                <div>
                  <div className="text-xs text-zinc-500">Fresh runs</div>
                  <div className="tabular-nums">
                    {w.completed}
                    {w.runs > w.completed && <span className="text-xs text-zinc-500"> (+{w.runs - w.completed} failed)</span>}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-zinc-500">Avg cost / run</div>
                  <div className="tabular-nums">{usd(w.avg_cost_per_completed_run)}</div>
                </div>
                <div className="col-span-2 text-xs text-zinc-500">
                  {(w.input_tokens / 1e6).toFixed(2)}M in · {(w.output_tokens / 1e6).toFixed(2)}M out tokens
                </div>
              </div>
            </div>
          ))}
        </section>
      )}

      <InviteManager invites={invites} call={call} reload={load} defaultCredits={Number(stats?.settings.default_invite_credits ?? 3)} />

      {stats && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Recent runs</h2>
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wider text-zinc-500">
                <tr>
                  {["Ticker", "When", "Status", "Invite", "Calls", "Tokens in / out", "Cost"].map((h) => (
                    <th key={h} className="px-4 py-3 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {stats.recent_runs.map((r) => (
                  <RunRowView key={`${r.ticker}-${r.started}`} r={r} />
                ))}
                {!stats.recent_runs.length && (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center text-zinc-500">
                      No fresh runs recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function RunRowView({ r }: { r: RunRow }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <tr className="cursor-pointer border-t border-white/5 hover:bg-white/[0.03]" onClick={() => setOpen(!open)}>
        <td className="px-4 py-2.5 font-mono font-semibold">{r.ticker}</td>
        <td className="px-4 py-2.5 text-zinc-400">{timeAgo(new Date(r.started * 1000).toISOString())}</td>
        <td className="px-4 py-2.5">
          <span className={r.status === "done" ? "text-emerald-300" : "text-rose-300"}>{r.status}</span>
        </td>
        <td className="px-4 py-2.5 text-zinc-400">{r.invite_label ?? "—"}</td>
        <td className="px-4 py-2.5 tabular-nums">{r.calls}</td>
        <td className="px-4 py-2.5 tabular-nums text-zinc-400">
          {(r.input_tokens / 1000).toFixed(0)}k / {(r.output_tokens / 1000).toFixed(0)}k
        </td>
        <td className="px-4 py-2.5 font-semibold tabular-nums">{usd(r.cost_usd, 3)}</td>
      </tr>
      {open && (
        <tr className="bg-black/20">
          <td colSpan={7} className="px-4 py-3">
            <div className="grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2 lg:grid-cols-3">
              {r.detail.map((d, i) => (
                <div key={i} className="flex justify-between gap-3">
                  <span className="text-zinc-400">
                    {d.agent} <span className="text-zinc-600">{d.model}</span>
                  </span>
                  <span className="tabular-nums">
                    {(d.input_tokens / 1000).toFixed(1)}k/{(d.output_tokens / 1000).toFixed(1)}k · {usd(d.cost_usd, 3)}
                  </span>
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function InviteManager({
  invites,
  call,
  reload,
  defaultCredits,
}: {
  invites: Invite[];
  call: (path: string, init?: RequestInit) => Promise<unknown>;
  reload: () => void;
  defaultCredits: number;
}) {
  const [label, setLabel] = useState("");
  const [credits, setCredits] = useState("");
  const [copied, setCopied] = useState<string | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    await call("/api/admin/invites", { method: "POST", body: JSON.stringify({ label, credits: credits ? Number(credits) : null }) });
    setLabel("");
    setCredits("");
    reload();
  }
  async function change(code: string, body: object) {
    await call(`/api/admin/invites/${code}`, { method: "POST", body: JSON.stringify(body) });
    reload();
  }
  function copy(code: string) {
    const link = `${window.location.origin}/?invite=${code}`;
    navigator.clipboard?.writeText(link).catch(() => undefined);
    setCopied(code);
    setTimeout(() => setCopied(null), 1500);
  }

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">Invite codes</h2>
      <form onSubmit={create} className="card mb-3 flex flex-wrap gap-2 p-4">
        <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Who is it for? (e.g. Sam)" className="min-w-40 flex-1 rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2 text-sm focus:outline-none" aria-label="Invite label" />
        <input value={credits} onChange={(e) => setCredits(e.target.value.replace(/\D/g, ""))} placeholder={`${defaultCredits} credits`} className="w-28 rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2 text-sm focus:outline-none" aria-label="Credits" />
        <button className="rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-4 py-2 text-sm font-semibold text-white">Create invite</button>
      </form>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wider text-zinc-500">
            <tr>
              {["For", "Code", "Used", "Status", ""].map((h) => (
                <th key={h} className="px-4 py-3 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {invites.map((inv) => (
              <tr key={inv.code} className="border-t border-white/5">
                <td className="px-4 py-2.5">{inv.label || "—"}</td>
                <td className="px-4 py-2.5 font-mono">{inv.code}</td>
                <td className="px-4 py-2.5 tabular-nums">
                  {inv.credits_used} / {inv.credits_total}
                </td>
                <td className="px-4 py-2.5">{inv.disabled ? <span className="text-rose-300">disabled</span> : <span className="text-emerald-300">active</span>}</td>
                <td className="px-4 py-2.5">
                  <div className="flex justify-end gap-1.5 text-xs">
                    <button onClick={() => copy(inv.code)} className="rounded-md bg-brand-500/15 px-2 py-1 text-brand-200 hover:bg-brand-500/25">
                      {copied === inv.code ? "Copied!" : "Copy invite link"}
                    </button>
                    <button onClick={() => change(inv.code, { add_credits: 3 })} className="rounded-md border border-white/10 px-2 py-1 text-zinc-300 hover:text-white">
                      +3 credits
                    </button>
                    <button onClick={() => change(inv.code, { disabled: !inv.disabled })} className="rounded-md border border-white/10 px-2 py-1 text-zinc-400 hover:text-white">
                      {inv.disabled ? "Enable" : "Disable"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!invites.length && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-zinc-500">
                  No invites yet. Create one above, then copy the link and send it.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
