"use client";

// Signed-in state for the whole site: the Supabase session, and this account's credits from our API.
import type { Session } from "@supabase/supabase-js";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { API } from "./api";
import { listHistory, removeEntry } from "./history";
import { supabase } from "./supabase";

export interface Me {
  user_id: string;
  email: string | null;
  credits_total: number;
  credits_used: number;
  remaining: number;
  free_granted: boolean;
  is_admin: boolean;
  unlimited?: boolean;
  /** Plus/Pro (or admin): the community library and other people's recent reports. */
  community?: boolean;
  free_credits: number;
  plan?: "plus" | "pro" | null;
  plan_status?: string | null;
  plan_renews?: number | null;
  has_billing?: boolean;
}

interface AuthState {
  ready: boolean;
  session: Session | null;
  me: Me | null;
  token: string | null;
  refreshMe: () => Promise<void>;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthState>({
  ready: false,
  session: null,
  me: null,
  token: null,
  refreshMe: async () => undefined,
  signOut: async () => undefined,
});

export const ME_EVENT = "stock-council-me";

/** fetch() to our API with the signed-in user's token attached. */
export async function authFetch(path: string, init: RequestInit = {}, token?: string | null): Promise<Response> {
  const t = token ?? (await supabase().auth.getSession()).data.session?.access_token ?? null;
  const headers = new Headers(init.headers);
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return fetch(`${API}${path}`, { ...init, headers });
}

/** Reports saved in this browser before signing in move into the account (once). */
async function importLocalHistory(token: string): Promise<void> {
  const local = listHistory().filter((e) => e.status === "done" && e.events?.length);
  if (!local.length) return;
  const res = await authFetch(
    "/api/me/history/import",
    { method: "POST", body: JSON.stringify({ entries: local.slice(0, 25).map((e) => ({ ticker: e.ticker, events: e.events })) }) },
    token,
  );
  if (res.ok) local.forEach((e) => removeEntry(e.id));
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const token = session?.access_token ?? null;

  const loadMe = useCallback(async (t: string | null) => {
    if (!t) return setMe(null);
    try {
      const res = await authFetch("/api/me", {}, t);
      setMe(res.ok ? await res.json() : null);
    } catch {
      setMe(null);
    }
  }, []);

  useEffect(() => {
    const sb = supabase();
    sb.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setReady(true);
    });
    const { data } = sb.auth.onAuthStateChange((event, s) => {
      setSession(s);
      setReady(true);
      if (event === "SIGNED_IN" && s) importLocalHistory(s.access_token).catch(() => undefined);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    loadMe(token);
  }, [token, loadMe]);

  useEffect(() => {
    const reload = () => loadMe(token);
    window.addEventListener(ME_EVENT, reload);
    return () => window.removeEventListener(ME_EVENT, reload);
  }, [token, loadMe]);

  const value = useMemo<AuthState>(
    () => ({
      ready,
      session,
      me,
      token,
      refreshMe: () => loadMe(token),
      signOut: async () => {
        await supabase().auth.signOut();
        setMe(null);
      },
    }),
    [ready, session, me, token, loadMe],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  return useContext(Ctx);
}

export function meChanged(): void {
  window.dispatchEvent(new Event(ME_EVENT));
}
