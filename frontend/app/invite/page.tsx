"use client";

import Link from "next/link";
import { InviteForm, useAccess } from "@/components/AccessWidgets";
import { setCode } from "@/lib/access";

export default function InvitePage() {
  const access = useAccess();
  const invite = access?.valid ? access.invite : null;

  return (
    <div className="mx-auto max-w-lg space-y-6 pt-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Your invite</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Each fresh analysis uses credits by depth: Quick 1, Standard 2, Deep 3. Opening a stock someone analyzed recently, or a report in your History, is always free.
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
