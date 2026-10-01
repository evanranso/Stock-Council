"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import Turnstile from "@/components/Turnstile";
import { useAuth } from "@/lib/auth";
import { supabase } from "@/lib/supabase";

type Mode = "login" | "signup" | "forgot" | "reset";

/** Only same-site paths, so a crafted link can't bounce people to another site after logging in. */
function safeNext(raw: string | null): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
}

const TITLES: Record<Mode, string> = {
  login: "Log in",
  signup: "Create your free account",
  forgot: "Reset your password",
  reset: "Choose a new password",
};

function LoginPage() {
  const params = useSearchParams();
  const router = useRouter();
  const { ready, session, me } = useAuth();
  const next = safeNext(params.get("next"));
  const initial = params.get("mode");
  const [mode, setMode] = useState<Mode>(initial === "signup" || initial === "forgot" || initial === "reset" ? initial : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [captcha, setCaptcha] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [unconfirmed, setUnconfirmed] = useState(false);

  // Header links (Log in / Sign up free) change ?mode= without remounting this page: follow the URL.
  useEffect(() => {
    if (initial === "login" || initial === "signup" || initial === "forgot" || initial === "reset") {
      setMode(initial);
      setError(null);
      setNotice(null);
      setUnconfirmed(false);
    }
  }, [initial]);

  // Arriving from a password-reset email: Supabase signs the visitor in for recovery.
  useEffect(() => {
    const { data } = supabase().auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY") setMode("reset");
    });
    return () => data.subscription.unsubscribe();
  }, []);

  // Already signed in (including right after clicking the verification link): go where they were headed.
  useEffect(() => {
    if (ready && session && mode !== "reset") router.replace(next);
  }, [ready, session, mode, next, router]);

  const redirect = (extra: string) => `${window.location.origin}/login?${extra}&next=${encodeURIComponent(next)}`;

  function switchTo(m: Mode) {
    setMode(m);
    setError(null);
    setNotice(null);
    setUnconfirmed(false);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    setUnconfirmed(false);
    const auth = supabase().auth;
    const captchaToken = captcha ?? undefined;
    try {
      if (mode === "signup") {
        if (password.length < 8) throw new Error("Use at least 8 characters for your password.");
        const { error: err } = await auth.signUp({ email, password, options: { captchaToken, emailRedirectTo: redirect("verified=1") } });
        if (err) throw err;
        setNotice(`Almost there! We sent a verification link to ${email}. Open it to activate your account and your free credits. Check spam if it doesn't show up in a minute.`);
      } else if (mode === "login") {
        const { error: err } = await auth.signInWithPassword({ email, password, options: { captchaToken } });
        if (err) {
          if (/confirm/i.test(err.message)) setUnconfirmed(true);
          throw err;
        }
      } else if (mode === "forgot") {
        const { error: err } = await auth.resetPasswordForEmail(email, { captchaToken, redirectTo: redirect("mode=reset") });
        if (err) throw err;
        setNotice(`If ${email} has an account, a reset link is on its way.`);
      } else {
        if (password.length < 8) throw new Error("Use at least 8 characters for your password.");
        const { error: err } = await auth.updateUser({ password });
        if (err) throw err;
        setNotice("Password updated. You're signed in.");
        router.replace(next);
      }
    } catch (err) {
      setError(friendly((err as Error).message));
    } finally {
      setBusy(false);
      setResetKey((k) => k + 1); // captcha tokens are single-use
    }
  }

  async function resend() {
    setBusy(true);
    const { error: err } = await supabase().auth.resend({
      type: "signup",
      email,
      options: { captchaToken: captcha ?? undefined, emailRedirectTo: redirect("verified=1") },
    });
    setBusy(false);
    setResetKey((k) => k + 1);
    if (err) setError(friendly(err.message));
    else {
      setUnconfirmed(false);
      setError(null);
      setNotice(`Sent a new verification link to ${email}.`);
    }
  }

  const needsCaptcha = mode !== "reset";
  const needsPassword = mode !== "forgot";
  const inputCls =
    "w-full rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2.5 placeholder:text-zinc-600 focus:border-brand-400/70 focus:outline-none";

  if (ready && session && mode !== "reset") {
    return <div className="card mx-auto mt-10 max-w-md p-6 text-center text-zinc-400">Signed in as {me?.email ?? session.user.email}. Redirecting…</div>;
  }

  return (
    <div className="mx-auto max-w-md space-y-6 pt-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{TITLES[mode]}</h1>
        {mode === "signup" && (
          <p className="mt-2 text-sm text-zinc-400">
            Free accounts get <span className="font-semibold text-brand-200">2 Standard analyses</span> (4 credits) once your email is verified. Your reports are
            saved to your account.
          </p>
        )}
        {params.get("verified") && !session && <p className="mt-2 text-sm text-emerald-300">Email verified. Log in to get started.</p>}
      </div>

      <form onSubmit={submit} className="card space-y-4 p-6">
        {mode !== "reset" && (
          <label className="block space-y-1.5">
            <span className="text-sm text-zinc-300">Email</span>
            <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value.trim())} className={inputCls} placeholder="you@example.com" />
          </label>
        )}
        {needsPassword && (
          <label className="block space-y-1.5">
            <span className="flex justify-between text-sm text-zinc-300">
              {mode === "reset" ? "New password" : "Password"}
              {mode === "login" && (
                <button type="button" onClick={() => switchTo("forgot")} className="text-xs text-brand-300 hover:underline">
                  Forgot password?
                </button>
              )}
            </span>
            <input
              type="password"
              required
              minLength={mode === "login" ? undefined : 8}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputCls}
              placeholder={mode === "login" ? "" : "At least 8 characters"}
            />
          </label>
        )}
        {needsCaptcha && <Turnstile onToken={setCaptcha} resetKey={resetKey} />}

        {error && <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-200">{error}</p>}
        {unconfirmed && (
          <button type="button" disabled={busy || !captcha} onClick={resend} className="text-sm text-brand-300 hover:underline disabled:opacity-50">
            Resend the verification email
          </button>
        )}
        {notice && <p className="rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">{notice}</p>}

        <button
          disabled={busy || (needsCaptcha && !captcha)}
          className="w-full rounded-lg bg-gradient-to-r from-brand-500 to-accent-500 px-4 py-2.5 font-semibold text-white shadow-lg shadow-brand-500/25 hover:brightness-110 disabled:opacity-50"
        >
          {busy ? "One moment…" : mode === "signup" ? "Create account" : mode === "login" ? "Log in" : mode === "forgot" ? "Send reset link" : "Save password"}
        </button>
        {mode === "signup" && (
          <p className="text-center text-xs text-zinc-500">
            By creating an account you agree to the{" "}
            <Link href="/terms" className="text-brand-300 hover:underline">
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link href="/privacy" className="text-brand-300 hover:underline">
              Privacy Policy
            </Link>
            . Stock Council is research, not investment advice.
          </p>
        )}
        {needsCaptcha && !captcha && <p className="text-center text-xs text-zinc-500">Waiting for the quick bot check…</p>}
      </form>

      <p className="text-center text-sm text-zinc-400">
        {mode === "signup" ? (
          <>
            Already have an account?{" "}
            <button onClick={() => switchTo("login")} className="text-brand-300 hover:underline">
              Log in
            </button>
          </>
        ) : mode === "reset" ? null : (
          <>
            New here?{" "}
            <button onClick={() => switchTo("signup")} className="text-brand-300 hover:underline">
              Create a free account
            </button>
          </>
        )}
      </p>
      <p className="text-center text-xs text-zinc-600">
        <Link href="/" className="hover:text-zinc-400">
          ← Back to Stock Council
        </Link>
      </p>
    </div>
  );
}

function friendly(message: string): string {
  if (/invalid login credentials/i.test(message)) return "That email and password don't match.";
  if (/confirm/i.test(message)) return "Your email isn't verified yet. Open the link we sent you (check spam), or resend it below.";
  if (/captcha/i.test(message)) return "The bot check expired. Wait for it to refresh, then try again.";
  if (/rate limit|too many/i.test(message)) return "Too many attempts. Wait a few minutes and try again.";
  if (/already registered/i.test(message)) return "That email already has an account. Log in instead.";
  return message;
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <LoginPage />
    </Suspense>
  );
}
