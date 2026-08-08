import { useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "sonner";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";
import { Btn, Input, Label } from "../components/ui";

const HERO = "https://images.unsplash.com/photo-1597848808461-5db1405e1db1?q=80&w=1600";

export default function AuthPage() {
  const { session, loadProfile } = useAuth();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", full_name: "", company: "" });
  const [busy, setBusy] = useState(false);

  if (session) return <Navigate to="/" replace />;

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

  return (
    <div className="relative z-10 flex min-h-screen">
      <div className="relative hidden flex-1 lg:block">
        <img src={HERO} alt="Studio camera rig" className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-r from-transparent to-ink" />
        <div className="absolute bottom-12 left-12 max-w-md">
          <p className="font-mono text-[11px] font-bold uppercase tracking-[0.35em] text-accent">Production, delivered</p>
          <h2 className="mt-3 font-display text-5xl font-extrabold tracking-tighter">Every cut. Every note. One place.</h2>
        </div>
      </div>
      <div className="flex w-full items-center justify-center px-8 lg:w-[520px]">
        <div className="rise w-full max-w-sm">
          <p className="font-display text-2xl font-extrabold tracking-tighter">
            FLYBOY<span className="text-accent">/</span>VIDEO
          </p>
          <h1 className="mt-8 font-display text-3xl font-bold tracking-tight">
            {mode === "login" ? "Sign in to your portal" : "Create your account"}
          </h1>
          <form onSubmit={submit} className="mt-8 space-y-5">
            {mode === "signup" && (
              <>
                <div>
                  <Label>Full name</Label>
                  <Input data-testid="signup-name-input" value={form.full_name} onChange={set("full_name")} placeholder="Ava Director" required />
                </div>
                <div>
                  <Label>Company</Label>
                  <Input data-testid="signup-company-input" value={form.company} onChange={set("company")} placeholder="Acme Media" />
                </div>
              </>
            )}
            <div>
              <Label>Email</Label>
              <Input data-testid="auth-email-input" type="email" value={form.email} onChange={set("email")} placeholder="you@company.com" required />
            </div>
            <div>
              <Label>Password</Label>
              <Input data-testid="auth-password-input" type="password" minLength={6} value={form.password} onChange={set("password")} placeholder="••••••••" required />
            </div>
            <Btn data-testid="auth-submit-btn" type="submit" disabled={busy} className="w-full">
              {busy ? "Working…" : mode === "login" ? "Sign in" : "Create account"}
            </Btn>
          </form>
          <button
            data-testid="auth-mode-toggle"
            onClick={() => setMode(mode === "login" ? "signup" : "login")}
            className="mt-6 text-sm text-zinc-400 underline decoration-line underline-offset-4 hover:text-accent"
            style={{ transition: "color 0.15s ease" }}
          >
            {mode === "login" ? "New client? Create an account" : "Already have an account? Sign in"}
          </button>

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
