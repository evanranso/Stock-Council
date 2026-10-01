"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useDepthCosts } from "@/components/AccessWidgets";
import { meChanged, useAuth } from "@/lib/auth";
import { fetchPlans, money, openPortal, type Plan, startCheckout } from "@/lib/billing";
import { DEPTH_ICON } from "@/lib/depth";

function PricingPage() {
  const params = useSearchParams();
  const { ready, session, me } = useAuth();
  const costs = useDepthCosts();
  const [plans, setPlans] = useState<{ enabled: boolean; plans: Plan[] } | null | undefined>(undefined);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const success = params.get("success") === "1";

  useEffect(() => {
    fetchPlans().then(setPlans);
  }, []);

  // Back from Stripe: credits arrive by webhook a few seconds later. Refresh until they show up.
  useEffect(() => {
    if (!success || !session) return;
    let tries = 0;
    const t = setInterval(() => {
      meChanged();
      if (++tries >= 15) clearInterval(t);
    }, 2000);
    return () => clearInterval(t);
  }, [success, session]);

  async function buy(plan: Plan) {
    setBusy(plan.id);
    setError(null);
    const hasPlan = plan.kind === "subscription" && me?.plan && me.plan_status !== "canceled";
    const failed = hasPlan ? await openPortal() : await startCheckout(plan.id);
    if (failed) {
      setBusy(null);
      if (failed.reason === "has_subscription") {
        const again = await openPortal();
        if (again) setError(again.error);
      } else setError(failed.error);
    }
  }

  async function manage() {
    setBusy("portal");
    const failed = await openPortal();
    if (failed) {
      setBusy(null);
      setError(failed.error);
    }
  }

  const activePlan = me?.plan && me.plan_status !== "canceled" ? me.plan : null;

  return (
    <div className="mx-auto max-w-5xl space-y-10 pt-4">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">Pricing</h1>
        <p className="mx-auto mt-3 max-w-2xl text-zinc-400">
          Pay for the analyses you run. Every stock someone analyzed recently is free to open, and failed analyses are refunded automatically.
        </p>
        <div className="mt-5 inline-flex flex-wrap justify-center gap-2 text-sm">
          {costs.depths.map((c) => (
            <span key={c.id} className="rounded-full bg-white/5 px-3 py-1 text-zinc-300 ring-1 ring-white/10">
              {DEPTH_ICON[c.id]} {c.label} = {c.credits} {c.credits === 1 ? "credit" : "credits"}
            </span>
          ))}
        </div>
      </div>

      {success && (
        <div className="card border-emerald-400/30 bg-emerald-500/10 p-4 text-center text-emerald-100">
          Payment received. Thank you! Your credits are added within a few seconds; your balance below updates on its own.
        </div>
      )}
      {params.get("canceled") === "1" && <div className="card p-4 text-center text-sm text-zinc-400">Checkout canceled. You weren&apos;t charged.</div>}
      {error && <div className="card border-rose-400/30 bg-rose-500/10 p-4 text-center text-sm text-rose-100">{error}</div>}

      {session && me && (
        <div className="card flex flex-wrap items-center gap-4 p-5">
          <div className="flex-1">
            <div className="text-sm text-zinc-400">Your balance</div>
            <div className="text-2xl font-bold tabular-nums">
              {me.unlimited ? "Unlimited (admin)" : `${me.remaining} ${me.remaining === 1 ? "credit" : "credits"}`}
            </div>
            {activePlan && (
              <div className="mt-1 text-sm text-zinc-400">
                {activePlan === "pro" ? "Pro" : "Plus"} plan
                {me.plan_status === "canceling"
                  ? ` · ends ${me.plan_renews ? new Date(me.plan_renews * 1000).toLocaleDateString() : "at period end"}`
                  : me.plan_status === "past_due"
                    ? " · payment failed, update your card"
                    : me.plan_renews
                      ? ` · renews ${new Date(me.plan_renews * 1000).toLocaleDateString()}`
                      : ""}
              </div>
            )}
          </div>
          {me.has_billing && (
            <button onClick={manage} disabled={busy !== null} className="rounded-lg border border-white/15 px-4 py-2 text-sm text-zinc-200 hover:bg-white/10 disabled:opacity-50">
              {busy === "portal" ? "Opening…" : "Manage billing"}
            </button>
          )}
        </div>
      )}

      {plans === undefined ? (
        <div className="grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="card h-72 animate-pulse" />
          ))}
        </div>
      ) : !plans?.enabled ? (
        <div className="card p-8 text-center text-zinc-400">Paid plans are coming soon. New accounts get free credits to try it.</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {plans.plans.map((p) => {
            const featured = p.id === "pro";
            const current = activePlan === p.id;
            const perCredit = p.price ? p.price.amount / p.credits : null;
            let label = p.kind === "subscription" ? `Get ${p.name}` : "Buy credits";
            if (current) label = "Manage your plan";
            else if (activePlan && p.kind === "subscription") label = `Switch to ${p.name}`;
            return (
              <div
                key={p.id}
                className={`card relative flex flex-col p-6 ${featured ? "border-brand-400/50 bg-brand-500/[0.07] shadow-xl shadow-brand-500/10" : ""}`}
              >
                {featured && (
                  <span className="absolute -top-3 left-6 rounded-full bg-gradient-to-r from-brand-500 to-accent-500 px-3 py-0.5 text-xs font-semibold text-white">
                    Best value
                  </span>
                )}
                <div className="flex items-baseline justify-between gap-2">
                  <h2 className="text-xl font-semibold">{p.name}</h2>
                  {current && <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-300">Your plan</span>}
                </div>
                <p className="mt-1 text-sm text-zinc-400">{p.blurb}</p>
                <div className="mt-5 text-3xl font-bold">{money(p.price) || "—"}</div>
                <ul className="mt-5 flex-1 space-y-2 text-sm text-zinc-300">
                  <li>
                    <span className="font-semibold text-white">{p.credits} credits</span>
                    {p.kind === "subscription" ? " every month" : ", one time"}
                  </li>
                  <li>
                    ≈ {Math.floor(p.credits / costs.credits("standard"))} Standard or {Math.floor(p.credits / costs.credits("quick"))} Quick
                    analyses
                  </li>
                  {perCredit !== null && <li className="text-zinc-500">{money({ ...p.price!, amount: perCredit, interval: null })} per credit</li>}
                  <li className="text-zinc-500">{p.kind === "subscription" ? "Unused credits roll over. Cancel anytime." : "Credits never expire."}</li>
                </ul>
                {!ready ? null : !session ? (
                  <Link
                    href="/login?mode=signup&next=/pricing"
                    className="mt-6 rounded-lg bg-white/10 px-4 py-2.5 text-center font-semibold text-white hover:bg-white/15"
                  >
                    Sign up to buy
                  </Link>
                ) : (
                  <button
                    onClick={() => (current ? manage() : buy(p))}
                    disabled={busy !== null}
                    className={`mt-6 rounded-lg px-4 py-2.5 font-semibold text-white disabled:opacity-50 ${
                      featured ? "bg-gradient-to-r from-brand-500 to-accent-500 shadow-lg shadow-brand-500/25 hover:brightness-110" : "bg-white/10 hover:bg-white/15"
                    }`}
                  >
                    {busy === p.id ? "Opening checkout…" : label}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      <p className="text-center text-xs text-zinc-500">
        Payments are processed securely by Stripe. Stock Council never sees your card details.
      </p>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <PricingPage />
    </Suspense>
  );
}
