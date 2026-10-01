"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { CreditPill, useAccess, useDepthCosts } from "./AccessWidgets";

/** Header: credits + account dropdown when signed in, "Log in / Sign up free" otherwise. */
export default function AccountMenu() {
  const access = useAccess();
  const costs = useDepthCosts();
  const { ready, session, me, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  // Show the account buttons unless the server says accounts are off. If it's still waking up
  // (free hosting sleeps), we don't know yet, and hiding "Log in" would strand visitors.
  if (access && access.mode !== "accounts") return <CreditPill />;
  if (!ready) return <span className="h-7 w-24" />;

  if (!session) {
    // Come back to the current page after logging in. Read at click time: the page may have changed
    // since this rendered. On the login page itself, keep where it was already headed.
    const go = (mode: "login" | "signup") => (e: React.MouseEvent) => {
      e.preventDefault();
      const here = window.location.pathname.startsWith("/login")
        ? new URLSearchParams(window.location.search).get("next")
        : window.location.pathname + window.location.search;
      router.push(`/login?mode=${mode}${here ? `&next=${encodeURIComponent(here)}` : ""}`);
    };
    return (
      <div className="flex items-center gap-1">
        <Link href="/login?mode=login" onClick={go("login")} className="rounded-lg px-3 py-1.5 text-zinc-300 hover:bg-white/5 hover:text-white">
          Log in
        </Link>
        <Link
          href="/login?mode=signup"
          onClick={go("signup")}
          className="rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-3 py-1.5 font-semibold text-white shadow shadow-brand-500/25 hover:brightness-110"
        >
          Sign up free
        </Link>
      </div>
    );
  }

  const n = me?.remaining;
  const email = me?.email ?? session.user.email ?? "";
  return (
    <div ref={box} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-full bg-white/5 py-1 pl-1 pr-3 ring-1 ring-white/10 hover:bg-white/10"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="grid h-6 w-6 place-items-center rounded-full bg-gradient-to-br from-brand-500 to-accent-500 text-xs font-bold uppercase text-white">
          {email.slice(0, 1) || "?"}
        </span>
        {me?.unlimited ? (
          <span className="text-xs font-medium text-brand-200">Unlimited</span>
        ) : (
          n !== undefined && (
            <span className={`text-xs font-medium tabular-nums ${n > 0 ? "text-brand-200" : "text-rose-200"}`}>
              {n} {n === 1 ? "credit" : "credits"}
            </span>
          )
        )}
      </button>
      {open && (
        <div role="menu" className="absolute right-0 mt-2 w-64 overflow-hidden rounded-xl border border-white/10 bg-[#0d0f17] shadow-2xl shadow-black/50">
          <div className="border-b border-white/10 px-4 py-3">
            <div className="truncate text-sm text-zinc-200">{email}</div>
            <div className="mt-0.5 text-xs text-zinc-500">
              {me?.unlimited ? "Admin: unlimited analyses" : `${n ?? "…"} credits left · ${costs.text}`}
            </div>
          </div>
          <MenuLink href="/pricing">{me?.plan && me.plan_status !== "canceled" ? "Plan & credits" : "Buy credits"}</MenuLink>
          <MenuLink href="/history">Your history</MenuLink>
          <MenuLink href="/invite">Redeem a code</MenuLink>
          {me?.is_admin && <MenuLink href="/admin">Admin</MenuLink>}
          <button onClick={() => signOut()} role="menuitem" className="block w-full border-t border-white/10 px-4 py-2.5 text-left text-sm text-zinc-400 hover:bg-white/5 hover:text-white">
            Log out
          </button>
        </div>
      )}
    </div>
  );
}

function MenuLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} role="menuitem" className="block px-4 py-2.5 text-sm text-zinc-300 hover:bg-white/5 hover:text-white">
      {children}
    </Link>
  );
}
