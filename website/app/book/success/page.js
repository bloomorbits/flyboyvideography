"use client";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";
const MAX_POLLS = 20;   // ≈ 40s total
const POLL_MS = 2000;

// Wrapping the search-param reader in a Suspense boundary lets Next 15 avoid
// bailing out to CSR-only rendering for the whole /book/success route.
import { Suspense } from "react";

function SuccessInner() {
  const params = useSearchParams();
  const sessionId = params.get("session_id");
  // Branch the copy on whether this is a deposit payment (default, the
  // client just booked) or a balance payment (the client already had a
  // booking and just settled the remaining balance). Both flows land here
  // because they share the same `/api/booking/status/{session_id}` polling
  // contract; only the wording differs.
  const isBalance = params.get("kind") === "balance";
  const [state, setState] = useState({ status: "checking", payment_status: "checking" });
  const [attempts, setAttempts] = useState(0);
  const [error, setError] = useState("");
  const timerRef = useRef(null);

  useEffect(() => {
    if (!sessionId) {
      setError("Missing session_id.");
      return;
    }
    let cancelled = false;

    async function tick(n) {
      if (cancelled) return;
      try {
        const r = await fetch(`${API_BASE}/api/booking/status/${sessionId}`);
        const j = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
        if (cancelled) return;
        setState({ status: j.status, payment_status: j.payment_status });
        setAttempts(n);
        const done = j.payment_status === "paid"
          || j.payment_status === "refunded"
          || j.status === "failed"
          || j.status === "expired";
        if (done) return;
        if (n < MAX_POLLS) {
          timerRef.current = setTimeout(() => tick(n + 1), POLL_MS);
        }
      } catch (e) {
        if (!cancelled) setError(String(e.message || e));
      }
    }
    tick(1);
    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [sessionId]);

  const paid = state.payment_status === "paid";
  const refunded = state.payment_status === "refunded";
  const pending = !paid && !refunded && !error && attempts <= MAX_POLLS;

  return (
    <div className="mx-auto max-w-2xl px-6 pb-24 pt-24">
      <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-ink/60">Booking status</p>

      {paid && !isBalance && (
        <>
          <h1 data-testid="success-headline-paid" className="mt-2 font-display text-4xl font-bold tracking-tight md:text-5xl">
            Your date is locked in.
          </h1>
          <p className="mt-4 text-base leading-relaxed text-ink/70">
            Payment received. A confirmation email is on its way with a link to set up your
            portal password — that&apos;s where you&apos;ll review your films and pay the balance.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/"
              data-testid="success-home-cta"
              className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-medium text-cream hover:opacity-90"
            >
              Back to the site →
            </Link>
          </div>
        </>
      )}

      {paid && isBalance && (
        <>
          <h1 data-testid="success-headline-balance-paid" className="mt-2 font-display text-4xl font-bold tracking-tight md:text-5xl">
            Balance settled — you&apos;re all set.
          </h1>
          <p className="mt-4 text-base leading-relaxed text-ink/70">
            Payment received. Your booking is now paid in full and we&apos;re on for the day.
            A receipt will land in your inbox shortly. If you have any last-minute details
            or a running order to share, hit reply on any of our emails — we read every one.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/"
              data-testid="success-balance-home-cta"
              className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-medium text-cream hover:opacity-90"
            >
              Back to the site →
            </Link>
          </div>
        </>
      )}

      {refunded && (
        <>
          <h1 data-testid="success-headline-refunded" className="mt-2 font-display text-4xl font-bold tracking-tight md:text-5xl">
            That date was just taken — we&apos;ve refunded you.
          </h1>
          <p className="mt-4 text-base leading-relaxed text-ink/70">
            Another client secured this date at the same moment. Your deposit has been fully
            refunded to your original payment method (usually 5–10 business days). Pick another date
            and we&apos;ll get you booked in.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/book"
              data-testid="refund-rebook-cta"
              className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-medium text-cream hover:opacity-90"
            >
              Pick another date →
            </Link>
          </div>
        </>
      )}

      {pending && (
        <>
          <h1 data-testid="success-headline-pending" className="mt-2 font-display text-4xl font-bold tracking-tight md:text-5xl">
            Confirming your payment…
          </h1>
          <p className="mt-4 text-base leading-relaxed text-ink/70">
            Stripe is telling us the good news any second. Don&apos;t close this tab — this page
            updates itself.
          </p>
          <p className="mt-6 font-mono text-xs uppercase tracking-widest text-ink/40">
            Check {attempts} of {MAX_POLLS}
          </p>
        </>
      )}

      {(state.status === "failed" || state.status === "expired") && !paid && !refunded && (
        <>
          <h1 className="mt-2 font-display text-4xl font-bold tracking-tight md:text-5xl">
            Payment didn&apos;t go through.
          </h1>
          <p className="mt-4 text-base leading-relaxed text-ink/70">
            No charge was made. Head back to the booking page and try again — your date is
            still open unless someone else grabs it first.
          </p>
          <div className="mt-8">
            <Link
              href="/book"
              className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-medium text-cream hover:opacity-90"
            >
              Try again →
            </Link>
          </div>
        </>
      )}

      {error && (
        <p data-testid="success-error" role="alert" className="mt-6 rounded-lg bg-red-100 px-4 py-3 text-sm text-red-800">
          {error}
        </p>
      )}
    </div>
  );
}

export default function SuccessPage() {
  return (
    <main className="min-h-screen bg-cream text-ink">
      <Suspense fallback={<div className="pt-24 text-center text-ink/70">Loading…</div>}>
        <SuccessInner />
      </Suspense>
    </main>
  );
}
