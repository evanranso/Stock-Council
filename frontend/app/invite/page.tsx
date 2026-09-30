"use client";

import Link from "next/link";
import { useState } from "react";
import { InviteForm, redeemCode, useAccess, useDepthCosts } from "@/components/AccessWidgets";
import { setCode } from "@/lib/access";
import { useAuth } from "@/lib/auth";

export default function InvitePage() {
  const access = useAccess();
  if (access?.mode === "accounts") return <RedeemPage />;
  return <LegacyInvitePage />;
}

/** Accounts: redeem a code, adding its credits to your account. */
function RedeemPage() {
  const costs = useDepthCosts();
  const { ready, session, me } = useAuth();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setResult(await redeemCode(value));
    setBusy(false);
    setValue("");
  }

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Redeem a code</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Codes add credits to your account. Fresh analyses use credits by depth: {costs.text}. Opening a stock someone analyzed recently, or a
          report in your History, is always free.
        </p>
      </div>
      {!ready ? null : !session ? (
        <div className="card space-y-3 p-6 text-sm text-zinc-300">
          <p>Log in or create a free account first, then redeem your code here.</p>
          <div className="flex gap-2">
            <Link href="/login?mode=signup&next=/invite" className="rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-4 py-2 font-semibold text-white">
              Sign up free
            </Link>
            <Link href="/login?next=/invite" className="rounded-lg border border-white/10 px-4 py-2 text-zinc-300 hover:text-white">
              Log in
            </Link>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="card space-y-4 p-6">
          <p className="text-sm text-zinc-400">
            You have <span className="font-semibold text-white">{me?.remaining ?? "…"}</span> credits.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="SC-XXXX-XXXX"
              className="flex-1 rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2 font-mono uppercase placeholder:text-zinc-600 focus:border-brand-400/70 focus:outline-none"
              aria-label="Code"
            />
            <button disabled={busy || value.trim().length < 4} className="rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
              {busy ? "Redeeming…" : "Redeem"}
            </button>
          </div>
          {result && <p className={`rounded-lg px-3 py-2 text-sm ${result.ok ? "bg-emerald-500/10 text-emerald-200" : "bg-rose-500/10 text-rose-200"}`}>{result.text}</p>}
        </form>
      )}
    </div>
  );
}

function LegacyInvitePage() {
  const access = useAccess();
  const costs = useDepthCosts();
  const invite = access?.valid ? access.invite : null;

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Your invite</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Each fresh analysis uses credits by depth: {costs.text}. Opening a stock someone analyzed recently, or a report in your History, is always free.
        </p>
      </div>

      {invite ? (
        <div className="card space-y-4 p-6">
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-lg">{invite.code}</span>
            {invite.label && <span className="text-sm text-zinc-400">{invite.label}</span>}
          </div>
          <div>
            <div className="mb-1 flex justify-between text-sm">
              <span className="text-zinc-400">Credits left</span>
              <span className="font-semibold">
                {invite.remaining} of {invite.credits_total}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-accent-500" style={{ width: `${(invite.remaining / Math.max(1, invite.credits_total)) * 100}%` }} />
            </div>
          </div>
          <div className="flex gap-2">
            <Link href="/" className="rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-4 py-2 text-sm font-semibold text-white">
              Analyze a stock
            </Link>
            <button onClick={() => setCode(null)} className="rounded-lg border border-white/10 px-4 py-2 text-sm text-zinc-400 hover:text-white">
              Use a different code
            </button>
          </div>
        </div>
      ) : (
        <div className="card space-y-3 p-6">
          <p className="text-sm text-zinc-300">Enter the invite code you were sent.</p>
          <InviteForm />
          {access?.mode === "open" && <p className="text-xs text-zinc-500">Invites aren&apos;t required right now, so you can analyze stocks without one.</p>}
        </div>
      )}
    </div>
  );
}
