"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { type Access, CREDITS_EVENT, fetchAccess, getCode, setCode } from "@/lib/access";

/** Keeps the header pill and banners in sync with the server's view of this visitor's credits. */
export function useAccess(): Access | null {
  const [access, setAccess] = useState<Access | null>(null);
  useEffect(() => {
    const load = () => fetchAccess().then(setAccess);
    load();
    window.addEventListener(CREDITS_EVENT, load);
    return () => window.removeEventListener(CREDITS_EVENT, load);
  }, []);
  return access;
}

/** Picks up ?invite=CODE from an invite link on any page, saves it, and says hello. */
export function InviteCapture() {
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => {
    const url = new URL(window.location.href);
    const code = url.searchParams.get("invite");
    if (!code) return;
    url.searchParams.delete("invite");
    window.history.replaceState(null, "", url.toString());
    fetchAccess(code.trim().toUpperCase()).then((a) => {
      if (a?.valid && a.invite) {
        setCode(a.invite.code);
        setMessage({
          ok: true,
          text: `Welcome${a.invite.label ? `, ${a.invite.label}` : ""}! Your invite includes ${a.invite.remaining} free ${a.invite.remaining === 1 ? "credit" : "credits"}. A Quick analysis uses 1, Deep uses 3.`,
        });
      } else {
        setMessage({ ok: false, text: "That invite link isn't valid anymore. Ask for a new one." });
      }
    });
  }, []);
  if (!message) return null;
  return (
    <div className={`border-b px-4 py-2 text-center text-sm ${message.ok ? "border-brand-400/30 bg-brand-500/15 text-brand-100" : "border-rose-400/30 bg-rose-500/10 text-rose-100"}`}>
      {message.text}
      <button onClick={() => setMessage(null)} className="ml-3 text-xs opacity-70 hover:opacity-100" aria-label="Dismiss">
        ✕
      </button>
    </div>
  );
}

/** Header pill: "3 analyses left", or a prompt to add an invite code in invite-only mode. */
export function CreditPill() {
  const access = useAccess();
  if (!access) return null;
  if (access.valid && access.invite) {
    const n = access.invite.remaining;
    return (
      <Link
        href="/invite"
        className={`hidden rounded-full px-3 py-1 text-xs font-medium ring-1 sm:inline-block ${n > 0 ? "bg-brand-500/15 text-brand-200 ring-brand-400/30" : "bg-rose-500/10 text-rose-200 ring-rose-400/30"}`}
        title="Credits left on your invite. Recently analyzed stocks are free to open."
      >
        {n} {n === 1 ? "credit" : "credits"} left
      </Link>
    );
  }
  if (access.mode === "invite") {
    return (
      <Link href="/invite" className="hidden rounded-full bg-white/5 px-3 py-1 text-xs text-zinc-300 ring-1 ring-white/10 hover:text-white sm:inline-block">
        Have an invite?
      </Link>
    );
  }
  return null;
}

/** Enter or change an invite code. */
export function InviteForm({ onDone }: { onDone?: () => void }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const a = await fetchAccess(value.trim().toUpperCase());
    setBusy(false);
    if (a?.valid && a.invite) {
      setCode(a.invite.code);
      setValue("");
      onDone?.();
    } else {
      setError("That code isn't valid. Check it and try again.");
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row">
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="SC-XXXX-XXXX"
        className="flex-1 rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2 font-mono uppercase placeholder:text-zinc-600 focus:border-brand-400/70 focus:outline-none"
        aria-label="Invite code"
      />
      <button disabled={busy || !value.trim()} className="rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
        {busy ? "Checking…" : "Use code"}
      </button>
      {error && <p className="text-sm text-rose-300 sm:basis-full">{error}</p>}
    </form>
  );
}

export function hasCode(): boolean {
  return !!getCode();
}
