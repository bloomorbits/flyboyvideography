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

      <div className="grid grid-cols-7 gap-1 text-center font-mono text-[10px] uppercase tracking-widest text-ink/70">
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

      <p className="mt-3 font-mono text-[10px] uppercase tracking-widest text-ink/70">
        Struck-through days are unavailable. Bookings open 18 months ahead.
      </p>
    </div>
  );
}

export default function BookPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-cream pt-24 text-center text-ink/70">Loading…</main>}>
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
  // Consent capture (Migrations 010 + 010B, session 11) — frontend UX only;
  // server-side enforcement lives in /api/booking/checkout.
  const [tcAccepted, setTcAccepted] = useState(false);
  const [modelReleaseOptedIn, setModelReleaseOptedIn] = useState(true); // opt-out model, pre-checked
  const [minorsInvolved, setMinorsInvolved] = useState(false);
  const [guardianName, setGuardianName] = useState("");
  const [safeguardingAccepted, setSafeguardingAccepted] = useState(false);
  // Compulsory booking details (Migration 021 / Step 2). Server enforces these
  // with per-field 422s; the mirror below is UX only.
  const [venueName, setVenueName] = useState("");
  const [venueTbc, setVenueTbc] = useState(false);
  const [eventCity, setEventCity] = useState("");
  const [eventPostcode, setEventPostcode] = useState("");
  const [eventStartTime, setEventStartTime] = useState("");
  const [guestCount, setGuestCount] = useState("");
  const [secondaryName, setSecondaryName] = useState("");
  const [secondaryPhone, setSecondaryPhone] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const fieldRefs = useRef({});
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

  // Client-side mirror of the server's required-field rules (booking.py). Keep
  // the messages identical to the server so the experience is seamless.
  function validateDetails() {
    const errs = {};
    if (!fullName.trim()) errs.full_name = "Please enter your full name.";
    if (!email.trim()) errs.email = "Please enter your email.";
    if (!phone.trim()) errs.phone = "A contact phone number is required.";
    if (!eventStartTime.trim()) errs.event_start_time = "An event start time is required.";
    if (!eventCity.trim()) errs.event_city = "The event town or city is required.";
    if (!venueTbc && !venueName.trim()) errs.venue_name = "Enter the venue name, or tick 'venue to be confirmed'.";
    if (!venueTbc && !eventPostcode.trim()) errs.event_postcode = "A venue postcode is required when the venue is known.";
    return errs;
  }

  // Pay button mirrors the server rules so it only enables when a submit would pass.
  const detailsComplete =
    !!fullName.trim() && !!email.trim() && !!phone.trim() && !!eventStartTime.trim() &&
    !!eventCity.trim() && (venueTbc || (!!venueName.trim() && !!eventPostcode.trim()));

  function focusField(name) {
    const el = fieldRefs.current[name];
    if (el && typeof el.focus === "function") {
      el.focus();
      if (typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }

  function clearFieldError(name) {
    setFieldErrors((prev) => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    const clientErrs = validateDetails();
    if (Object.keys(clientErrs).length) {
      setFieldErrors(clientErrs);
      focusField(Object.keys(clientErrs)[0]);
      setError("Please fix the highlighted fields.");
      return;
    }
    setFieldErrors({});
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
          // Compulsory booking details (Migration 021 / Step 2)
          venue_name: venueTbc ? null : (venueName.trim() || null),
          venue_tbc: venueTbc,
          event_city: eventCity.trim() || null,
          event_postcode: eventPostcode.trim() || null,
          event_start_time: eventStartTime || null,
          guest_count: guestCount === "" ? null : Number(guestCount),
          secondary_contact_name: secondaryName.trim() || null,
          secondary_contact_phone: secondaryPhone.trim() || null,
          // Consent (server also enforces — frontend is UX)
          tc_accepted: tcAccepted,
          model_release_opted_in: modelReleaseOptedIn,
          minors_involved: minorsInvolved,
          safeguarding_guardian_name: minorsInvolved ? guardianName.trim() : null,
          safeguarding_consent_accepted: minorsInvolved ? safeguardingAccepted : false,
        }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) {
        // New per-field 422 shape: { detail: { errors: [{ field, message }] } }
        if (j && j.detail && typeof j.detail === "object" && Array.isArray(j.detail.errors)) {
          const fe = {};
          j.detail.errors.forEach((er) => { if (er && er.field) fe[er.field] = er.message; });
          setFieldErrors(fe);
          const first = j.detail.errors[0]?.field;
          if (first) focusField(first);
          setError("Please fix the highlighted fields.");
        } else {
          setError((typeof j.detail === "string" && j.detail) || `Something went wrong (HTTP ${r.status}). Try again.`);
        }
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
                    <p className="mt-1 font-mono text-xs uppercase tracking-widest text-ink/70">
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
                      <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-ink/70">
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
                  ref={(el) => (fieldRefs.current.full_name = el)}
                  value={fullName}
                  autoComplete="name"
                  onChange={(e) => { setFullName(e.target.value); clearFieldError("full_name"); }}
                  required
                  className={`mt-2 w-full rounded-lg border bg-cream px-4 py-3 text-sm min-h-[44px] focus:border-ink focus:outline-none ${fieldErrors.full_name ? "border-red-400" : "border-ink/20"}`}
                />
                {fieldErrors.full_name && <p data-testid="error-full_name" role="alert" className="mt-1 font-mono text-xs text-red-700">{fieldErrors.full_name}</p>}
              </div>
              <div>
                <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="email">Email *</label>
                <input
                  id="email"
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  data-testid="input-email"
                  ref={(el) => (fieldRefs.current.email = el)}
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); clearFieldError("email"); }}
                  required
                  className={`mt-2 w-full rounded-lg border bg-cream px-4 py-3 text-sm min-h-[44px] focus:border-ink focus:outline-none ${fieldErrors.email ? "border-red-400" : "border-ink/20"}`}
                />
                {fieldErrors.email && <p data-testid="error-email" role="alert" className="mt-1 font-mono text-xs text-red-700">{fieldErrors.email}</p>}
              </div>
              <div className="md:col-span-2">
                <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="phone">Phone *</label>
                <input
                  id="phone"
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  data-testid="input-phone"
                  ref={(el) => (fieldRefs.current.phone = el)}
                  value={phone}
                  onChange={(e) => { setPhone(e.target.value); clearFieldError("phone"); }}
                  placeholder="e.g. 07911 123456"
                  className={`mt-2 w-full rounded-lg border bg-cream px-4 py-3 text-sm min-h-[44px] focus:border-ink focus:outline-none ${fieldErrors.phone ? "border-red-400" : "border-ink/20"}`}
                />
                {fieldErrors.phone && <p data-testid="error-phone" role="alert" className="mt-1 font-mono text-xs text-red-700">{fieldErrors.phone}</p>}
              </div>
            </div>

            {/* --- Event details (Migration 021 / Step 2) --- */}
            <fieldset className="space-y-4 rounded-lg border border-ink/15 bg-sand p-5">
              <legend className="px-2 font-mono text-[10px] uppercase tracking-widest text-ink/60">Event details</legend>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="md:col-span-2">
                  <label className="flex items-center gap-3 text-sm text-ink/90" style={{ minHeight: 44 }}>
                    <input
                      type="checkbox"
                      data-testid="venue-tbc"
                      checked={venueTbc}
                      onChange={(e) => {
                        setVenueTbc(e.target.checked);
                        if (e.target.checked) { clearFieldError("venue_name"); clearFieldError("event_postcode"); }
                      }}
                      className="h-5 w-5 shrink-0 rounded border-ink/30"
                    />
                    <span>Venue to be confirmed — I don&apos;t have the venue yet</span>
                  </label>
                </div>

                <div>
                  <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="venueName">
                    Venue name {venueTbc ? "" : "*"}
                  </label>
                  <input
                    id="venueName"
                    data-testid="input-venue-name"
                    ref={(el) => (fieldRefs.current.venue_name = el)}
                    value={venueName}
                    disabled={venueTbc}
                    autoComplete="off"
                    onChange={(e) => { setVenueName(e.target.value); clearFieldError("venue_name"); }}
                    placeholder={venueTbc ? "Not needed yet" : "e.g. The Grand Hall"}
                    className={`mt-2 w-full rounded-lg border bg-cream px-4 py-3 text-sm min-h-[44px] focus:border-ink focus:outline-none disabled:opacity-40 ${fieldErrors.venue_name ? "border-red-400" : "border-ink/20"}`}
                  />
                  {fieldErrors.venue_name && <p data-testid="error-venue_name" role="alert" className="mt-1 font-mono text-xs text-red-700">{fieldErrors.venue_name}</p>}
                </div>

                <div>
                  <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="eventPostcode">
                    Venue postcode {venueTbc ? "" : "*"}
                  </label>
                  <input
                    id="eventPostcode"
                    data-testid="input-postcode"
                    ref={(el) => (fieldRefs.current.event_postcode = el)}
                    value={eventPostcode}
                    disabled={venueTbc}
                    autoComplete="postal-code"
                    onChange={(e) => { setEventPostcode(e.target.value); clearFieldError("event_postcode"); }}
                    placeholder={venueTbc ? "Not needed yet" : "e.g. M1 1AA"}
                    className={`mt-2 w-full rounded-lg border bg-cream px-4 py-3 text-sm min-h-[44px] focus:border-ink focus:outline-none disabled:opacity-40 ${fieldErrors.event_postcode ? "border-red-400" : "border-ink/20"}`}
                  />
                  {fieldErrors.event_postcode && <p data-testid="error-event_postcode" role="alert" className="mt-1 font-mono text-xs text-red-700">{fieldErrors.event_postcode}</p>}
                </div>

                <div>
                  <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="eventCity">Town / city *</label>
                  <input
                    id="eventCity"
                    data-testid="input-city"
                    ref={(el) => (fieldRefs.current.event_city = el)}
                    value={eventCity}
                    autoComplete="address-level2"
                    onChange={(e) => { setEventCity(e.target.value); clearFieldError("event_city"); }}
                    placeholder="e.g. Manchester"
                    className={`mt-2 w-full rounded-lg border bg-cream px-4 py-3 text-sm min-h-[44px] focus:border-ink focus:outline-none ${fieldErrors.event_city ? "border-red-400" : "border-ink/20"}`}
                  />
                  {fieldErrors.event_city && <p data-testid="error-event_city" role="alert" className="mt-1 font-mono text-xs text-red-700">{fieldErrors.event_city}</p>}
                </div>

                <div>
                  <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="eventStartTime">Start time *</label>
                  <input
                    id="eventStartTime"
                    type="time"
                    data-testid="input-start-time"
                    ref={(el) => (fieldRefs.current.event_start_time = el)}
                    value={eventStartTime}
                    onChange={(e) => { setEventStartTime(e.target.value); clearFieldError("event_start_time"); }}
                    className={`mt-2 w-full rounded-lg border bg-cream px-4 py-3 text-sm min-h-[44px] focus:border-ink focus:outline-none ${fieldErrors.event_start_time ? "border-red-400" : "border-ink/20"}`}
                  />
                  {fieldErrors.event_start_time && <p data-testid="error-event_start_time" role="alert" className="mt-1 font-mono text-xs text-red-700">{fieldErrors.event_start_time}</p>}
                </div>

                <div>
                  <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="guestCount">Approx. guest count (optional)</label>
                  <input
                    id="guestCount"
                    type="number"
                    inputMode="numeric"
                    min="0"
                    data-testid="input-guest-count"
                    value={guestCount}
                    onChange={(e) => setGuestCount(e.target.value)}
                    placeholder="e.g. 80"
                    className="mt-2 w-full rounded-lg border border-ink/20 bg-cream px-4 py-3 text-sm min-h-[44px] focus:border-ink focus:outline-none"
                  />
                </div>
              </div>
            </fieldset>

            {/* --- Secondary contact (optional) --- */}
            <fieldset className="space-y-4 rounded-lg border border-ink/15 bg-sand p-5">
              <legend className="px-2 font-mono text-[10px] uppercase tracking-widest text-ink/60">Secondary contact (optional)</legend>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="secondaryName">Name</label>
                  <input
                    id="secondaryName"
                    data-testid="input-secondary-name"
                    value={secondaryName}
                    autoComplete="off"
                    onChange={(e) => setSecondaryName(e.target.value)}
                    placeholder="e.g. a partner or planner"
                    className="mt-2 w-full rounded-lg border border-ink/20 bg-cream px-4 py-3 text-sm min-h-[44px] focus:border-ink focus:outline-none"
                  />
                </div>
                <div>
                  <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="secondaryPhone">Phone</label>
                  <input
                    id="secondaryPhone"
                    type="tel"
                    inputMode="tel"
                    autoComplete="off"
                    data-testid="input-secondary-phone"
                    ref={(el) => (fieldRefs.current.secondary_contact_phone = el)}
                    value={secondaryPhone}
                    onChange={(e) => { setSecondaryPhone(e.target.value); clearFieldError("secondary_contact_phone"); }}
                    placeholder="e.g. 07911 222333"
                    className={`mt-2 w-full rounded-lg border bg-cream px-4 py-3 text-sm min-h-[44px] focus:border-ink focus:outline-none ${fieldErrors.secondary_contact_phone ? "border-red-400" : "border-ink/20"}`}
                  />
                  {fieldErrors.secondary_contact_phone && <p data-testid="error-secondary_contact_phone" role="alert" className="mt-1 font-mono text-xs text-red-700">{fieldErrors.secondary_contact_phone}</p>}
                </div>
              </div>
            </fieldset>

            <div>
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

            <p className="text-xs leading-relaxed text-ink/60">
              The remaining balance will be invoiced 5–7 days before your event and is due 3 days before.
            </p>

            {/* --- Consent capture (Migrations 010 + 010B, session 11) --- */}
            <fieldset className="space-y-4 rounded-lg border border-ink/15 bg-sand p-5">
              <legend className="px-2 font-mono text-[10px] uppercase tracking-widest text-ink/60">
                Consent
              </legend>

              <label className="flex items-start gap-3 text-sm text-ink/90">
                <input
                  type="checkbox"
                  data-testid="consent-tc"
                  checked={tcAccepted}
                  onChange={(e) => setTcAccepted(e.target.checked)}
                  className="mt-1 h-4 w-4 shrink-0 rounded border-ink/30"
                  required
                />
                <span>
                  I&apos;ve read and agree to the{" "}
                  <a className="underline" href="/terms" target="_blank" rel="noreferrer">
                    Booking Terms &amp; Conditions
                  </a>
                  . <span className="text-ink/60">(Required)</span>
                </span>
              </label>

              <label className="flex items-start gap-3 text-sm text-ink/90">
                <input
                  type="checkbox"
                  data-testid="consent-model-release"
                  checked={modelReleaseOptedIn}
                  onChange={(e) => setModelReleaseOptedIn(e.target.checked)}
                  className="mt-1 h-4 w-4 shrink-0 rounded border-ink/30"
                />
                <span>
                  I&apos;m happy for Flyboy Videography to use content from my session on their portfolio and social media, per the{" "}
                  <a className="underline" href="/model-release" target="_blank" rel="noreferrer">
                    Model &amp; Talent Release
                  </a>
                  . <span className="text-ink/60">(Uncheck to opt out — this never affects your deliverables.)</span>
                </span>
              </label>

              <div className="space-y-3 pt-1">
                <p className="text-sm font-medium text-ink">
                  Will anyone under 18 appear in this session?
                </p>
                <div className="flex gap-6">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="minors"
                      data-testid="minors-no"
                      checked={!minorsInvolved}
                      onChange={() => setMinorsInvolved(false)}
                      className="h-4 w-4"
                    />
                    <span>No</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="minors"
                      data-testid="minors-yes"
                      checked={minorsInvolved}
                      onChange={() => setMinorsInvolved(true)}
                      className="h-4 w-4"
                    />
                    <span>Yes</span>
                  </label>
                </div>
              </div>

              {minorsInvolved && (
                <div className="space-y-3 rounded-md border border-ink/10 bg-cream p-4">
                  <div>
                    <label
                      className="font-mono text-[11px] uppercase tracking-widest text-ink/70"
                      htmlFor="guardianName"
                    >
                      Guardian&apos;s full name *
                    </label>
                    <input
                      id="guardianName"
                      data-testid="input-guardian-name"
                      value={guardianName}
                      onChange={(e) => setGuardianName(e.target.value)}
                      className="mt-2 w-full rounded-lg border border-ink/20 bg-cream px-4 py-3 text-sm focus:border-ink focus:outline-none"
                      placeholder="Parent or legal guardian"
                    />
                  </div>
                  <label className="flex items-start gap-3 text-sm text-ink/90">
                    <input
                      type="checkbox"
                      data-testid="consent-safeguarding"
                      checked={safeguardingAccepted}
                      onChange={(e) => setSafeguardingAccepted(e.target.checked)}
                      className="mt-1 h-4 w-4 shrink-0 rounded border-ink/30"
                    />
                    <span>
                      As parent or legal guardian, I give consent per the{" "}
                      <a className="underline" href="/safeguarding-consent" target="_blank" rel="noreferrer">
                        Children &amp; Safeguarding Consent
                      </a>{" "}
                      page. <span className="text-ink/60">(Required)</span>
                    </span>
                  </label>
                </div>
              )}
            </fieldset>

            {error && (
              <p data-testid="booking-error" role="alert" className="rounded-lg bg-red-100 px-4 py-3 text-sm text-red-800">
                {error}
              </p>
            )}

            <div className="flex flex-col-reverse gap-3 border-t border-ink/10 pt-6 sm:flex-row sm:items-center sm:justify-end">
              <button
                type="submit"
                data-testid="pay-deposit-btn"
                disabled={
                  submitting ||
                  !tcAccepted ||
                  !detailsComplete ||
                  (minorsInvolved && (!guardianName.trim() || !safeguardingAccepted))
                }
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
