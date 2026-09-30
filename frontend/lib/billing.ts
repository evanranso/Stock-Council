// Stripe billing: plans for the pricing page, and redirects to Stripe's hosted checkout / billing portal.
import { API } from "./api";
import { authFetch } from "./auth";

export interface PlanPrice {
  amount: number;
  currency: string;
  interval: string | null;
}
export interface Plan {
  id: "plus" | "pro" | "topup";
  name: string;
  kind: "subscription" | "payment";
  credits: number;
  blurb: string;
  price: PlanPrice | null;
}

export async function fetchPlans(): Promise<{ enabled: boolean; plans: Plan[] } | null> {
  try {
    const res = await fetch(`${API}/api/billing/plans`);
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}

/** Ask the server for a Stripe page (checkout or billing portal) and go there. Returns an error message on failure. */
async function goTo(path: string, body?: object): Promise<{ error: string; reason?: string } | null> {
  try {
    const res = await authFetch(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.url) {
      window.location.href = data.url;
      return null;
    }
    const detail = data.detail;
    return {
      error: typeof detail === "string" ? detail : (detail?.message ?? "Something went wrong. Try again in a minute."),
      reason: detail?.reason,
    };
  } catch {
    return { error: "Couldn't reach the server. Try again in a minute." };
  }
}

export const startCheckout = (plan: string) => goTo("/api/billing/checkout", { plan });
export const openPortal = () => goTo("/api/billing/portal");

export function money(p: PlanPrice | null): string {
  if (!p) return "";
  const amount = new Intl.NumberFormat(undefined, { style: "currency", currency: p.currency.toUpperCase() }).format(p.amount);
  return p.interval ? `${amount}/${p.interval === "month" ? "mo" : p.interval}` : amount;
}
