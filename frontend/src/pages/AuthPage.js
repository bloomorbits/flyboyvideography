import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "sonner";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";
import { Btn, Input, Label } from "../components/ui";

const HERO = "https://images.unsplash.com/photo-1597848808461-5db1405e1db1?q=80&w=1600";

// Auth modes:
//   "login"     — email + password sign-in
//   "signup"    — create a new client account (email confirm required)
//   "reset"     — enter email to receive a password-reset link
//   "recovery"  — user arrived here from a reset / invite link, set a new password
export default function AuthPage() {
  const { session, loadProfile } = useAuth();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", full_name: "", company: "" });
  const [busy, setBusy] = useState(false);

  // Detect Supabase recovery flow — the reset/invite email lands here with a
  // hash fragment carrying an `access_token` and `type=recovery`. When we see
  // that, switch to the "recovery" mode so the user can set a fresh password.
  useEffect(() => {
    const hash = typeof window !== "undefined" ? window.location.hash : "";
    if (hash.includes("type=recovery") || hash.includes("type=invite")) {
      setMode("recovery");
    }
  }, []);

  if (session && mode !== "recovery") return <Navigate to="/" replace />;

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (mode === "signup") {
        const { data, error } = await supabase.auth.signUp({
          email: form.email,
          password: form.password,
          options: { data: { full_name: form.full_name, company: form.company } },
        });
        if (error) throw error;
        if (!data.session) {
          toast.info("Check your email to confirm your account, then sign in.");
        } else {
          await loadProfile({ full_name: form.full_name, company: form.company });
          toast.success("Welcome aboard");
        }
      } else if (mode === "reset") {
        // Self-service recovery for both expired invite links and forgotten
        // passwords. Supabase sends a fresh single-use link; when the user
        // clicks it they land back here with type=recovery in the URL hash,
        // and the useEffect above flips us into "recovery" mode automatically.
        const redirectTo = `${window.location.origin}/auth`;
        const { error } = await supabase.auth.resetPasswordForEmail(form.email, { redirectTo });
        if (error) throw error;
        toast.success("Reset link sent — check your email");
        setMode("login");
      } else if (mode === "recovery") {
        const { error } = await supabase.auth.updateUser({ password: form.password });
        if (error) throw error;
        toast.success("Password set — signing you in");
        window.history.replaceState(null, "", "/auth"); // strip the recovery hash
        window.location.href = "/"; // land on dashboard
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email: form.email, password: form.password });
        if (error) throw error;
        toast.success("Signed in");
      }
    } catch (err) {
      toast.error(err.message || "Authentication failed");
    } finally {
      setBusy(false);
    }
  };

  const headline = {
    login: "Sign in",
    signup: "Create your account",
    reset: "Reset your password",
    recovery: "Set a new password",
  }[mode];

  const submitLabel = {
    login: "Sign in",
    signup: "Create account",
    reset: "Send reset link",
    recovery: "Save new password",
  }[mode];

  return (
    <div className="relative z-10 flex min-h-screen">
      <div className="hidden lg:block lg:w-1/2 bg-cover bg-center" style={{ backgroundImage: `url(${HERO})` }} />
      <div className="flex w-full items-center justify-center px-6 py-10 lg:w-1/2">
        <div className="w-full max-w-sm">
          <h1 data-testid="auth-headline" className="font-display text-2xl font-semibold tracking-tight">{headline}</h1>
          <p className="mt-2 text-sm text-zinc-400">
            {mode === "signup" && "Set up your Flyboy Videography client portal."}
            {mode === "login" && "Welcome back to your client portal."}
            {mode === "reset" && "Enter your email and we'll send you a link to set a new password."}
            {mode === "recovery" && "Pick a new password below. This finishes setting up your portal access."}
          </p>
          <form className="mt-8 space-y-4" onSubmit={submit}>
            {mode === "signup" && (
              <>
                <div><Label>Full name</Label><Input data-testid="auth-fullname-input" value={form.full_name} onChange={set("full_name")} required /></div>
                <div><Label>Company (optional)</Label><Input data-testid="auth-company-input" value={form.company} onChange={set("company")} /></div>
              </>
            )}
            {mode !== "recovery" && (
              <div>
                <Label>Email</Label>
                <Input data-testid="auth-email-input" type="email" value={form.email} onChange={set("email")} placeholder="you@company.com" required />
              </div>
            )}
            {mode !== "reset" && (
              <div>
                <Label>{mode === "recovery" ? "New password" : "Password"}</Label>
                <Input data-testid="auth-password-input" type="password" minLength={6} value={form.password} onChange={set("password")} placeholder="••••••••" required />
              </div>
            )}
            <Btn data-testid="auth-submit-btn" type="submit" disabled={busy} className="w-full">
              {busy ? "Working…" : submitLabel}
            </Btn>
          </form>

          {mode === "login" && (
            <button
              data-testid="auth-forgot-password"
              onClick={() => setMode("reset")}
              className="mt-3 text-sm text-zinc-400 underline decoration-dotted underline-offset-4 hover:text-accent"
              style={{ transition: "color 0.15s ease" }}
            >
              Forgot your password?
            </button>
          )}

          {(mode === "login" || mode === "signup") && (
            <button
              data-testid="auth-mode-toggle"
              onClick={() => setMode(mode === "login" ? "signup" : "login")}
              className="mt-6 block text-sm text-zinc-400 underline decoration-line underline-offset-4 hover:text-accent"
              style={{ transition: "color 0.15s ease" }}
            >
              {mode === "login" ? "New client? Create an account" : "Already have an account? Sign in"}
            </button>
          )}

          {mode === "reset" && (
            <button
              data-testid="auth-back-to-login"
              onClick={() => setMode("login")}
              className="mt-6 block text-sm text-zinc-400 underline decoration-line underline-offset-4 hover:text-accent"
              style={{ transition: "color 0.15s ease" }}
            >
              ← Back to sign in
            </button>
          )}

          {/* Bloomorbit Studio credit — same rule as the public site footer. */}
          <p
            data-testid="auth-bloomorbit-credit"
            className="mt-10 text-center text-xs uppercase tracking-[0.25em] text-zinc-500"
          >
            Built by{" "}
            <a
              href="https://bloomorbit.tech"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="auth-bloomorbit-credit-link"
              className="underline decoration-dotted underline-offset-4 hover:text-zinc-200 hover:decoration-solid"
            >
              Bloomorbit Studio
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
