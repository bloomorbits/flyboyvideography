"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { BOOKABLE_PACKAGES, findPackage } from "../../lib/booking-packages";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

export default function ContactPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-cream pt-24 text-center text-ink/70">Loading…</main>}>
      <ContactInner />
    </Suspense>
  );
}

function ContactInner() {
  const searchParams = useSearchParams();
  const preselectedPackage = searchParams.get("package") || "";
  const preselectedSubject = searchParams.get("subject") || "";

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [packageId, setPackageId] = useState(preselectedPackage);
  const [eventDate, setEventDate] = useState("");
  const [message, setMessage] = useState(preselectedSubject ? `${preselectedSubject}\n\n` : "");
  const [submitting, setSubmitting] = useState(false);
  const [state, setState] = useState({ status: "idle", error: "" });

  // If the preselected package is valid, populate; otherwise leave blank.
  useEffect(() => {
    if (preselectedPackage && findPackage(preselectedPackage)) {
      setPackageId(preselectedPackage);
    }
  }, [preselectedPackage]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !message.trim()) {
      setState({ status: "idle", error: "Name, email and message are required." });
      return;
    }
    setSubmitting(true);
    setState({ status: "submitting", error: "" });
    try {
      const r = await fetch(`${API_BASE}/api/contact/enquire`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          package_id: packageId || null,
          event_date: eventDate || null,
          message: message.trim(),
          source_url: typeof window !== "undefined" ? window.location.href : null,
        }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) {
        setState({ status: "idle", error: j.detail || `Something went wrong (HTTP ${r.status}).` });
        setSubmitting(false);
        return;
      }
      setState({ status: "sent", error: "" });
    } catch (e) {
      setState({ status: "idle", error: "Network error. Please try again." });
    } finally {
      setSubmitting(false);
    }
  }

  if (state.status === "sent") {
    return (
      <main className="min-h-screen bg-cream text-ink">
        <div className="mx-auto max-w-2xl px-6 pb-24 pt-24">
          <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-ink/60">Message sent</p>
          <h1 data-testid="contact-success-headline" className="mt-2 font-display text-4xl font-bold tracking-tight md:text-5xl">
            Thanks — we&apos;ll be in touch soon.
          </h1>
          <p className="mt-4 text-base leading-relaxed text-ink/70">
            Your enquiry landed in our inbox. We reply within one working day. If it&apos;s
            urgent, mention it in the message and we&apos;ll bump it up the queue.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="/services"
              data-testid="contact-services-cta"
              className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-medium text-cream hover:opacity-90"
            >
              Browse packages →
            </a>
            <a
              href="/book"
              data-testid="contact-book-cta"
              className="inline-flex items-center gap-2 rounded-full border border-ink/25 px-5 py-3 text-sm font-medium text-ink hover:border-ink"
            >
              Or lock in a date now
            </a>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-cream text-ink">
      <div className="mx-auto max-w-3xl px-6 pb-24 pt-24">
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-ink/60">Get in touch</p>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight md:text-5xl">
          Tell us about your shoot.
        </h1>
        <p className="mt-4 max-w-xl text-base leading-relaxed text-ink/70">
          Quick questions, custom packages, or something we haven&apos;t listed — drop us a
          note and we&apos;ll reply within one working day. Want to lock a date now instead?{" "}
          <a href="/book" className="underline underline-offset-4">Skip to booking →</a>
        </p>

        <form onSubmit={handleSubmit} className="mt-10 space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="c-name">Your name *</label>
              <input
                id="c-name"
                data-testid="contact-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="mt-2 w-full rounded-lg border border-ink/20 bg-cream px-4 py-3 text-sm focus:border-ink focus:outline-none"
              />
            </div>
            <div>
              <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="c-email">Email *</label>
              <input
                id="c-email"
                type="email"
                data-testid="contact-email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="mt-2 w-full rounded-lg border border-ink/20 bg-cream px-4 py-3 text-sm focus:border-ink focus:outline-none"
              />
            </div>
            <div>
              <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="c-package">Package interest</label>
              <select
                id="c-package"
                data-testid="contact-package"
                value={packageId}
                onChange={(e) => setPackageId(e.target.value)}
                className="mt-2 w-full rounded-lg border border-ink/20 bg-cream px-4 py-3 text-sm focus:border-ink focus:outline-none"
              >
                <option value="">Not sure yet</option>
                {BOOKABLE_PACKAGES.map((p) => (
                  <option key={p.id} value={p.id}>{p.title}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="c-date">Event date</label>
              <input
                id="c-date"
                type="date"
                data-testid="contact-event-date"
                value={eventDate}
                onChange={(e) => setEventDate(e.target.value)}
                min={new Date().toISOString().slice(0, 10)}
                className="mt-2 w-full rounded-lg border border-ink/20 bg-cream px-4 py-3 text-sm focus:border-ink focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="font-mono text-[11px] uppercase tracking-widest text-ink/70" htmlFor="c-message">Your message *</label>
            <textarea
              id="c-message"
              data-testid="contact-message"
              rows={6}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
              placeholder="Tell us a little about your event — venue, vibe, anything we should know."
              className="mt-2 w-full rounded-lg border border-ink/20 bg-cream px-4 py-3 text-sm focus:border-ink focus:outline-none"
            />
          </div>

          {state.error && (
            <p data-testid="contact-error" role="alert" className="rounded-lg bg-red-100 px-4 py-3 text-sm text-red-800">
              {state.error}
            </p>
          )}

          <div className="flex flex-col-reverse gap-3 border-t border-ink/10 pt-6 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs leading-relaxed text-ink/60">
              We&apos;ll only use your email to reply to this enquiry.{" "}
              <a className="underline" href="/privacy">Privacy Policy</a>.
            </p>
            <button
              type="submit"
              data-testid="contact-submit"
              disabled={submitting}
              className="inline-flex items-center justify-center gap-2 rounded-full bg-ink px-6 py-3 text-sm font-medium text-cream transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              {submitting ? "Sending…" : "Send enquiry →"}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}
