"use client";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { BOOKABLE_PACKAGES, DEPOSIT_PERCENTAGE, findPackage, findTier } from "../../lib/booking-packages";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

const gbp = (n) => `£${Number(n).toFixed(2).replace(/\.00$/, "")}`;

function isoDate(d) {
  return d.toISOString().slice(0, 10);
}

// Simple month-grid picker. We render 12 months ahead of today; blocked dates
// come from GET /api/booking/availability and are visually disabled.
function DatePicker({ blocked, value, onChange }) {
  const [monthOffset, setMonthOffset] = useState(0);
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const cursor = new Date(today.getFullYear(), today.getMonth() + monthOffset, 1);
  const monthLabel = cursor.toLocaleDateString("en-GB", { month: "long", year: "numeric" });

  // Build the visible grid — 42 cells (6 weeks × 7 days), starting from
  // Monday of the week containing the 1st of the month.
  const firstDay = new Date(cursor);
  const firstWeekday = (firstDay.getDay() + 6) % 7; // Mon=0
  const gridStart = new Date(cursor);
  gridStart.setDate(1 - firstWeekday);

  const cells = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    cells.push(d);
  }

  const blockedSet = useMemo(() => new Set(blocked), [blocked]);

  return (
    <div data-testid="booking-datepicker" className="rounded-lg border border-ink/15 bg-cream p-4">
      <div className="mb-3 flex items-center justify-between">
        <button
          type="button"
          data-testid="datepicker-prev"
          onClick={() => setMonthOffset((m) => Math.max(0, m - 1))}
          disabled={monthOffset === 0}
          className="rounded-full border border-ink/20 px-3 py-1 font-mono text-xs disabled:opacity-30"
        >
          ← Prev
        </button>
        <span data-testid="datepicker-month" className="font-mono text-xs uppercase tracking-widest text-ink/70">
          {monthLabel}
        </span>
        <button
          type="button"
          data-testid="datepicker-next"
          onClick={() => setMonthOffset((m) => Math.min(17, m + 1))}
          disabled={monthOffset >= 17}
          className="rounded-full border border-ink/20 px-3 py-1 font-mono text-xs disabled:opacity-30"
        >
          Next →
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center font-mono text-[10px] uppercase tracking-widest text-ink/50">
        {["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"].map((d) => (<div key={d}>{d}</div>))}
      </div>

      <div className="mt-2 grid grid-cols-7 gap-1">
        {cells.map((d) => {
          const iso = isoDate(d);
          const isCurrentMonth = d.getMonth() === cursor.getMonth();
          const isPast = d < today;
          const isBlocked = blockedSet.has(iso);
          const selectable = isCurrentMonth && !isPast && !isBlocked;
          const isSelected = value === iso;
          return (
            <button
              key={iso}
              type="button"
              data-testid={`day-${iso}`}
              data-blocked={isBlocked ? "1" : undefined}
              data-selectable={selectable ? "1" : undefined}
              disabled={!selectable}
              onClick={() => selectable && onChange(iso)}
              className={`aspect-square rounded text-sm transition-colors ${
                isSelected
                  ? "bg-ink text-cream font-semibold"
                  : selectable
                  ? "hover:bg-dune text-ink"
                  : "text-ink/25 line-through"
              } ${!isCurrentMonth ? "opacity-30" : ""}`}
              aria-label={iso + (isBlocked ? " (booked)" : "")}
            >
              {d.getDate()}
            </button>
          );
        })}
      </div>

      <p className="mt-3 font-mono text-[10px] uppercase tracking-widest text-ink/50">
        Struck-through days are unavailable. Bookings open 18 months ahead.
      </p>
    </div>
  );
}

export default function BookPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-cream pt-24 text-center text-ink/50">Loading…</main>}>
      <BookPageInner />
    </Suspense>
  );
}

function BookPageInner() {
  const searchParams = useSearchParams();
  const [step, setStep] = useState(1); // 1 = pick package, 2 = details + pay
  const [packageId, setPackageId] = useState("");
  const [tierName, setTierName] = useState("");
  const [eventDate, setEventDate] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [eventNotes, setEventNotes] = useState("");
  const [blocked, setBlocked] = useState([]);
  const [availLoading, setAvailLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Pre-populate from ?package=…&tier=… when the visitor arrived via a
  // Services page tier CTA. Only runs once on mount; if the URL specifies
  // a nonsense package we silently ignore and leave the flow empty.
  const prefilledOnce = useRef(false);
  useEffect(() => {
    if (prefilledOnce.current) return;
    prefilledOnce.current = true;
    const qp = searchParams.get("package");
    const qt = searchParams.get("tier") ?? "";
    if (!qp) return;
    const pkg = findPackage(qp);
    if (!pkg) return;
    setPackageId(pkg.id);
    // If the tier query param is missing or doesn't match, fall back to the
    // first tier (safe default — every package has at least one).
    const wantedTier = pkg.tiers.find((t) => t.name === qt);
    setTierName((wantedTier || pkg.tiers[0]).name);
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setAvailLoading(true);
        const r = await fetch(`${API_BASE}/api/booking/availability`);
        if (!r.ok) throw new Error(`availability HTTP ${r.status}`);
        const j = await r.json();
        if (!cancelled) setBlocked(j.blocked_dates || []);
      } catch (e) {
        if (!cancelled) setError("Couldn't load availability. Please refresh.");
      } finally {
        if (!cancelled) setAvailLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const { pkg, tier } = findTier(packageId, tierName);
  const canProceedToStep2 = pkg && tier && eventDate;
  const priceTotal = tier?.price || 0;
  const priceDeposit = priceTotal * DEPOSIT_PERCENTAGE;

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!fullName.trim() || !email.trim()) {
      setError("Name and email are required.");
      return;
    }
    setSubmitting(true);
    try {
      const r = await fetch(`${API_BASE}/api/booking/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          package_id: packageId,
          tier_name: tierName,
          event_date: eventDate,
          email: email.trim(),
          full_name: fullName.trim(),
          phone: phone.trim() || null,
          event_notes: eventNotes.trim() || null,
          origin_url: window.location.origin,
        }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(j.detail || `Something went wrong (HTTP ${r.status}). Try again.`);
        setSubmitting(false);
        return;
      }
      window.location.href = j.checkout_url;
    } catch (e) {
      setError("Network error. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-cream pt-24 text-ink">
      <div className="mx-auto max-w-3xl px-6 pb-24">
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-ink/60">Book your date</p>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight md:text-5xl">
          Lock in your date in two steps
        </h1>
        <p className="mt-4 max-w-xl text-base leading-relaxed text-ink/70">
          Pick your package and date, then pay a {Math.round(DEPOSIT_PERCENTAGE * 100)}% deposit to secure it.
          Balance is due 3 days before your event.
        </p>

        <ol className="mt-8 flex gap-3 font-mono text-[10px] uppercase tracking-widest text-ink/60">
          <li data-testid="step-indicator-1" className={step >= 1 ? "text-ink" : ""}>
            1 · Package &amp; date
          </li>
          <li aria-hidden>→</li>
          <li data-testid="step-indicator-2" className={step >= 2 ? "text-ink" : ""}>
            2 · Your details &amp; payment
          </li>
        </ol>

        {step === 1 && (
          <div className="mt-10 space-y-8">
            <div>
              <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70">Pick a package</label>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                {BOOKABLE_PACKAGES.map((p) => (
                  <button
                    type="button"
                    key={p.id}
                    data-testid={`pkg-${p.id}`}
                    onClick={() => { setPackageId(p.id); setTierName(p.tiers[0].name); }}
                    className={`rounded-lg border p-4 text-left transition-colors ${
                      packageId === p.id ? "border-ink bg-sand" : "border-ink/15 hover:border-ink/40"
                    }`}
                  >
                    <p className="font-display text-lg font-semibold">{p.title}</p>
                    <p className="mt-1 font-mono text-xs uppercase tracking-widest text-ink/50">
                      {p.tiers.length > 1
                        ? `from ${gbp(Math.min(...p.tiers.map((t) => t.price)))}`
                        : gbp(p.tiers[0].price)}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            {pkg && pkg.tiers.length > 1 && (
              <div>
                <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70">Pick a tier</label>
                <div className="mt-3 grid gap-3 md:grid-cols-3">
                  {pkg.tiers.map((t) => (
                    <button
                      type="button"
                      key={t.name}
                      data-testid={`tier-${t.name.toLowerCase()}`}
                      onClick={() => setTierName(t.name)}
                      className={`rounded-lg border p-4 text-left transition-colors ${
                        tierName === t.name ? "border-ink bg-sand" : "border-ink/15 hover:border-ink/40"
                      }`}
                    >
                      <p className="font-display text-base font-semibold">{t.name}</p>
                      <p className="mt-1 font-mono text-xl font-bold">{gbp(t.price)}</p>
                      <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-ink/50">
                        {t.coverage}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {pkg && (
              <div>
                <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70">Pick a date</label>
                {availLoading ? (
                  <p data-testid="availability-loading" className="mt-3 text-sm text-ink/60">Loading available dates…</p>
                ) : (
                  <div className="mt-3">
                    <DatePicker blocked={blocked} value={eventDate} onChange={setEventDate} />
                  </div>
                )}
              </div>
            )}

            <div className="flex items-center justify-between border-t border-ink/10 pt-6">
              <p className="font-mono text-xs uppercase tracking-widest text-ink/60">
                {tier ? (
                  <>Deposit today: <span className="text-ink">{gbp(priceDeposit)}</span> · Balance: {gbp(priceTotal - priceDeposit)}</>
                ) : (
                  "Select a package to see the deposit"
                )}
              </p>
              <button
                type="button"
                data-testid="step1-next"
                onClick={() => canProceedToStep2 && setStep(2)}
                disabled={!canProceedToStep2}
                className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-3 text-sm font-medium text-cream transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
              >
                Continue <span aria-hidden className="font-mono">→</span>
              </button>
            </div>
          </div>
        )}

        {step === 2 && pkg && tier && (
          <form onSubmit={handleSubmit} className="mt-10 space-y-6">
            <div className="rounded-lg border border-ink/15 bg-sand p-5">
              <p className="font-mono text-[10px] uppercase tracking-widest text-ink/60">Your booking</p>
              <p className="mt-2 font-display text-xl font-semibold">
                {pkg.title}{tier.name ? ` — ${tier.name}` : ""}
              </p>
              <p className="mt-1 font-mono text-sm text-ink/70">
                {tier.coverage} · {new Date(eventDate).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
              </p>
              <p className="mt-3 font-mono text-sm text-ink/80">
                Total {gbp(priceTotal)} · Deposit today <span className="font-semibold text-ink">{gbp(priceDeposit)}</span>
              </p>
              <button
                type="button"
                data-testid="step2-back"
                onClick={() => setStep(1)}
                className="mt-3 font-mono text-xs uppercase tracking-widest text-ink/60 underline underline-offset-4"
              >
                Change
              </button>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="fullName">Full name *</label>
                <input
                  id="fullName"
                  data-testid="input-full-name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  className="mt-2 w-full rounded-lg border border-ink/20 bg-cream px-4 py-3 text-sm focus:border-ink focus:outline-none"
                />
              </div>
              <div>
                <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="email">Email *</label>
                <input
                  id="email"
                  type="email"
                  data-testid="input-email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="mt-2 w-full rounded-lg border border-ink/20 bg-cream px-4 py-3 text-sm focus:border-ink focus:outline-none"
                />
              </div>
              <div className="md:col-span-2">
                <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="phone">Phone (optional)</label>
                <input
                  id="phone"
                  data-testid="input-phone"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="mt-2 w-full rounded-lg border border-ink/20 bg-cream px-4 py-3 text-sm focus:border-ink focus:outline-none"
                />
              </div>
              <div className="md:col-span-2">
                <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="notes">Anything we should know? (optional)</label>
                <textarea
                  id="notes"
                  data-testid="input-notes"
                  rows={4}
                  value={eventNotes}
                  onChange={(e) => setEventNotes(e.target.value)}
                  className="mt-2 w-full rounded-lg border border-ink/20 bg-cream px-4 py-3 text-sm focus:border-ink focus:outline-none"
                />
              </div>
            </div>

            <p className="text-xs leading-relaxed text-ink/60">
              By continuing, you agree to our <a className="underline" href="/terms">Terms</a> and{" "}
              <a className="underline" href="/privacy">Privacy Policy</a>. The remaining balance will be
              invoiced 5–7 days before your event and is due 3 days before.
            </p>

            {error && (
              <p data-testid="booking-error" role="alert" className="rounded-lg bg-red-100 px-4 py-3 text-sm text-red-800">
                {error}
              </p>
            )}

            <div className="flex flex-col-reverse gap-3 border-t border-ink/10 pt-6 sm:flex-row sm:items-center sm:justify-end">
              <button
                type="submit"
                data-testid="pay-deposit-btn"
                disabled={submitting}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-ink px-6 py-3 text-sm font-medium text-cream transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {submitting ? "Redirecting to Stripe…" : `Pay ${gbp(priceDeposit)} deposit →`}
              </button>
            </div>
          </form>
        )}
      </div>
    </main>
  );
}
