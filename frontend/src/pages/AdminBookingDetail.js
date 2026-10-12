import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { ArrowLeft, AlertTriangle, Check, X } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Card, StatusPill, fmtDate, fmtMoney } from "../components/ui";

function Field({ label, children, testId }) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-widest text-ink/70">{label}</p>
      <p className="mt-1 break-words text-sm text-ink" data-testid={testId}>{children ?? "—"}</p>
    </div>
  );
}

function Phone({ contact, testId }) {
  if (!contact?.phone) return <span data-testid={testId}>Not provided</span>;
  return (
    <span className="inline-flex flex-wrap items-center gap-2" data-testid={testId}>
      {contact.phone}
      {contact.phone_needs_check && (
        <span
          data-testid={`${testId}-check`}
          className="inline-flex items-center gap-1 rounded-full border border-[#B45309]/20 bg-[#B45309]/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[#B45309]"
        >
          <AlertTriangle size={11} /> check number
        </span>
      )}
    </span>
  );
}

function Bool({ value, testId }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm" data-testid={testId}>
      {value ? <Check size={14} className="text-[#15803D]" /> : <X size={14} className="text-ink/40" />}
      {value ? "Yes" : "No"}
    </span>
  );
}

export default function AdminBookingDetail() {
  const { profile } = useAuth();
  const { id } = useParams();
  const [b, setB] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const { data } = await api.get(`/admin/bookings/${id}`);
      setB(data);
    } catch (e) {
      setErr(e.response?.data?.detail || "Could not load this booking.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  if (profile && profile.role !== "admin") return <Navigate to="/" replace />;

  const venue = b?.venue_tbc ? "To be confirmed" : (b?.venue_name || "—");

  return (
    <div data-testid="admin-booking-detail-page">
      <Link to="/admin/calendar" data-testid="back-to-calendar" className="mb-6 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-ink/60 hover:text-ink">
        <ArrowLeft size={14} /> Back to calendar
      </Link>

      {loading ? (
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/50">Loading…</p>
      ) : err ? (
        <Card className="p-8"><p data-testid="admin-booking-detail-error" className="text-sm text-red-700">{err}</p></Card>
      ) : (
        <>
          <div className="rise mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="mb-2 font-mono text-[11px] font-bold uppercase tracking-[0.3em] text-accent">Admin · Booking</p>
              <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl" data-testid="admin-booking-detail-title">{b.title || "Shoot"}</h1>
            </div>
            <StatusPill status={b.status} testId="admin-booking-detail-status" />
          </div>

          <Card className="rise mb-6 p-6">
            <h2 className="mb-5 font-display text-xl font-semibold tracking-tight">Event</h2>
            <div className="grid grid-cols-2 gap-6 md:grid-cols-3">
              <Field label="Date" testId="admin-detail-event-date">{fmtDate(b.event_date)}</Field>
              <Field label="Start time" testId="admin-detail-start-time">{b.event_start_time}</Field>
              <Field label="Guests" testId="admin-detail-guest-count">{b.guest_count}</Field>
              <Field label="Venue" testId="admin-detail-venue">{venue}</Field>
              <Field label="Town / city" testId="admin-detail-city">{b.event_city}</Field>
              <Field label="Postcode" testId="admin-detail-postcode">{b.venue_tbc ? "—" : b.event_postcode}</Field>
              <Field label="Deposit paid" testId="admin-detail-deposit">{b.deposit_paid_at ? fmtDate(b.deposit_paid_at.slice(0, 10)) : "—"}</Field>
              <Field label="Budget" testId="admin-detail-budget">{b.budget ? fmtMoney(b.budget) : "—"}</Field>
            </div>
          </Card>

          <Card className="rise mb-6 p-6">
            <h2 className="mb-5 font-display text-xl font-semibold tracking-tight">Contact</h2>
            <div className="grid grid-cols-2 gap-6 md:grid-cols-3">
              <Field label="Name" testId="admin-detail-contact-name">{b.contact?.full_name}</Field>
              <Field label="Email" testId="admin-detail-contact-email">{b.contact?.email}</Field>
              <Field label="Phone" testId="admin-detail-contact-phone"><Phone contact={b.contact} testId="admin-detail-contact-phone-value" /></Field>
              <Field label="Secondary name" testId="admin-detail-secondary-name">{b.secondary_contact_name}</Field>
              <Field label="Secondary phone" testId="admin-detail-secondary-phone">{b.secondary_contact_phone}</Field>
            </div>
          </Card>

          <Card className="rise mb-6 p-6">
            <h2 className="mb-5 font-display text-xl font-semibold tracking-tight">Consent &amp; compliance</h2>
            <div className="grid grid-cols-2 gap-6 md:grid-cols-3">
              <Field label="T&amp;Cs accepted" testId="admin-detail-tc"><Bool value={!!b.tc_accepted_at} testId="admin-detail-tc-bool" /></Field>
              <Field label="Model release" testId="admin-detail-model-release"><Bool value={!!b.model_release_opted_in} testId="admin-detail-model-release-bool" /></Field>
              <Field label="Minors involved" testId="admin-detail-minors"><Bool value={!!b.minors_involved} testId="admin-detail-minors-bool" /></Field>
              {b.minors_involved && (
                <>
                  <Field label="Guardian" testId="admin-detail-guardian">{b.safeguarding_guardian_name}</Field>
                  <Field label="Safeguarding consent" testId="admin-detail-safeguarding"><Bool value={!!b.safeguarding_consent_accepted_at} testId="admin-detail-safeguarding-bool" /></Field>
                </>
              )}
            </div>
          </Card>

          <Card className="rise mb-6 p-6">
            <h2 className="mb-5 font-display text-xl font-semibold tracking-tight">References</h2>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              <Field label="Stripe session" testId="admin-detail-stripe-session">{b.stripe_session_id}</Field>
              <Field label="Booking intent id" testId="admin-detail-intent-id">{b.booking_intent_id}</Field>
              <Field label="Client id" testId="admin-detail-client-id">{b.client_id}</Field>
            </div>
          </Card>

          {b.notes && (
            <Card className="rise p-6">
              <h2 className="mb-3 font-display text-xl font-semibold tracking-tight">Notes</h2>
              <p className="whitespace-pre-wrap text-sm text-ink/70" data-testid="admin-detail-notes">{b.notes}</p>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
