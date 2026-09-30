"use client";

import { useCallback, useEffect, useState } from "react";
import type { Invite } from "@/lib/access";
import { API } from "@/lib/api";
import { useAuth } from "@/lib/auth";
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
  user_email?: string | null;
  depth: string | null;
  detail: { agent: string; model: string; input_tokens: number; output_tokens: number; cost_usd: number }[];
}
interface Account {
  user_id: string;
  email: string | null;
  credits_total: number;
  credits_used: number;
  remaining: number;
  free_granted: boolean;
  created: number;
}
interface Stats {
  today: Window;
  last_7_days: Window;
  all_time: Window;
  recent_runs: RunRow[];
  live_runs: string[];
  accounts?: number;
  settings: Record<string, string | number>;
}

const usd = (n: number | null | undefined, digits = 2) => (n === null || n === undefined ? "—" : `$${n.toFixed(digits)}`);

export default function AdminPage() {
  const [key, setKey] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const { me, token } = useAuth();
  // Admins signed in with their own account (ADMIN_EMAILS) don't need the key.
  const bearer = me?.is_admin ? token : null;
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
      const auth: Record<string, string> = bearer ? { Authorization: `Bearer ${bearer}` } : { "X-Admin-Key": key ?? "" };
      const res = await fetch(`${API}${path}`, { ...init, headers: { "Content-Type": "application/json", ...auth, ...init?.headers } });
      if (res.status === 401) throw new Error(bearer ? "Your account isn't an admin." : "Wrong admin key.");
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `Error ${res.status}`);
      return res.json();
    },
    [key, bearer],
  );

  const load = useCallback(async () => {
    if (!key && !bearer) return;
    try {
      const [s, i, a] = await Promise.all([
        call("/api/admin/stats"),
        call("/api/admin/invites"),
        call("/api/admin/accounts").catch(() => []),
      ]);
      setStats(s);
      setInvites(i);
      setAccounts(a);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [key, bearer, call]);

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

  if (!key && !bearer) {
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
            {stats.settings.access_mode === "accounts" ? "Accounts" : stats.settings.access_mode === "invite" ? "Invite-only" : "Open to everyone"} · {stats.settings.model}
            {stats.accounts !== undefined && <> · {stats.accounts} accounts</>}
          </span>
        )}
        <button onClick={load} className="ml-auto rounded-lg border border-white/10 px-3 py-1.5 text-sm text-zinc-300 hover:text-white">
          Refresh
        </button>
        {!bearer && (
          <button onClick={() => saveKey(null)} className="rounded-lg px-3 py-1.5 text-sm text-zinc-500 hover:text-white">
            Sign out
          </button>
        )}
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

      {stats?.settings.access_mode === "accounts" && <AccountManager accounts={accounts} call={call} reload={load} />}

      <InviteManager invites={invites} call={call} reload={load} defaultCredits={Number(stats?.settings.default_invite_credits ?? 3)} />

      {stats && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Recent runs</h2>
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wider text-zinc-500">
                <tr>
                  {["Ticker", "When", "Depth", "Status", "Who", "Calls", "Tokens in / out", "Cost"].map((h) => (
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
                    <td colSpan={8} className="px-4 py-6 text-center text-zinc-500">
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
        <td className="px-4 py-2.5 capitalize text-zinc-300">{r.depth ?? "deep"}</td>
        <td className="px-4 py-2.5">
          <span className={r.status === "done" ? "text-emerald-300" : "text-rose-300"}>{r.status}</span>
        </td>
        <td className="max-w-48 truncate px-4 py-2.5 text-zinc-400">{r.user_email ?? r.invite_label ?? "—"}</td>
        <td className="px-4 py-2.5 tabular-nums">{r.calls}</td>
        <td className="px-4 py-2.5 tabular-nums text-zinc-400">
          {(r.input_tokens / 1000).toFixed(0)}k / {(r.output_tokens / 1000).toFixed(0)}k
        </td>
        <td className="px-4 py-2.5 font-semibold tabular-nums">{usd(r.cost_usd, 3)}</td>
      </tr>
      {open && (
        <tr className="bg-black/20">
          <td colSpan={8} className="px-4 py-3">
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

function AccountManager({
  accounts,
  call,
  reload,
}: {
  accounts: Account[];
  call: (path: string, init?: RequestInit) => Promise<unknown>;
  reload: () => void;
}) {
  const [filter, setFilter] = useState("");
  const shown = accounts.filter((a) => !filter || (a.email ?? "").toLowerCase().includes(filter.toLowerCase()));
  async function add(a: Account, n: number) {
    await call(`/api/admin/accounts/${encodeURIComponent(a.user_id)}/credits`, { method: "POST", body: JSON.stringify({ add: n }) });
    reload();
  }
  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold">Accounts</h2>
        <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter by email" className="ml-auto rounded-lg border border-white/15 bg-white/[0.04] px-3 py-1.5 text-sm focus:outline-none" aria-label="Filter accounts" />
      </div>
      <div className="card max-h-96 overflow-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wider text-zinc-500">
            <tr>
              {["Email", "Joined", "Credits used", "Left", ""].map((h) => (
                <th key={h} className="px-4 py-3 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((a) => (
              <tr key={a.user_id} className="border-t border-white/5">
                <td className="max-w-64 truncate px-4 py-2.5">{a.email ?? a.user_id}</td>
                <td className="px-4 py-2.5 text-zinc-400">{timeAgo(new Date(a.created * 1000).toISOString())}</td>
                <td className="px-4 py-2.5 tabular-nums">
                  {a.credits_used} / {a.credits_total}
                  {!a.free_granted && <span className="ml-1 text-xs text-zinc-500">(no free credits: daily cap)</span>}
                </td>
                <td className="px-4 py-2.5 font-semibold tabular-nums">{a.remaining}</td>
                <td className="px-4 py-2.5">
                  <div className="flex justify-end gap-1.5 text-xs">
                    <button onClick={() => add(a, 2)} className="rounded-md border border-white/10 px-2 py-1 text-zinc-300 hover:text-white">
                      +2
                    </button>
                    <button onClick={() => add(a, 10)} className="rounded-md bg-brand-500/15 px-2 py-1 text-brand-200 hover:bg-brand-500/25">
                      +10 credits
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!shown.length && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-zinc-500">
                  No accounts yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
