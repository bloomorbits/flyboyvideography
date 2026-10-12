import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import { Card, StatusPill, fmtDate, fmtMoney } from "../components/ui";

function Field({ label, children, testId }) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-widest text-ink/70">{label}</p>
      <p className="mt-1 text-sm text-ink" data-testid={testId}>{children ?? "—"}</p>
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

export default function BookingDetail() {
  const { id } = useParams();
  const [b, setB] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const { data } = await api.get(`/bookings/${id}`);
      setB(data);
    } catch (e) {
      setErr(e.response?.data?.detail || "Could not load this booking.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const venue = b?.venue_tbc ? "To be confirmed" : (b?.venue_name || "—");

  return (
    <div data-testid="booking-detail-page">
      <Link to="/bookings" data-testid="back-to-bookings" className="mb-6 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-ink/60 hover:text-ink">
        <ArrowLeft size={14} /> Back to bookings
      </Link>

      {loading ? (
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/50">Loading…</p>
      ) : err ? (
        <Card className="p-8"><p data-testid="booking-detail-error" className="text-sm text-red-700">{err}</p></Card>
      ) : (
        <>
          <div className="rise mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="mb-2 font-mono text-[11px] font-bold uppercase tracking-[0.3em] text-accent">Booking</p>
              <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl" data-testid="booking-detail-title">{b.title || "Shoot"}</h1>
            </div>
            <StatusPill status={b.status} testId="booking-detail-status" />
          </div>

          <Card className="rise mb-6 p-6">
            <h2 className="mb-5 font-display text-xl font-semibold tracking-tight">Event</h2>
            <div className="grid grid-cols-2 gap-6 md:grid-cols-3">
              <Field label="Date" testId="detail-event-date">{fmtDate(b.event_date)}</Field>
              <Field label="Start time" testId="detail-start-time">{b.event_start_time}</Field>
              <Field label="Guests" testId="detail-guest-count">{b.guest_count}</Field>
              <Field label="Venue" testId="detail-venue">{venue}</Field>
              <Field label="Town / city" testId="detail-city">{b.event_city}</Field>
              <Field label="Postcode" testId="detail-postcode">{b.venue_tbc ? "—" : b.event_postcode}</Field>
            </div>
          </Card>

          <Card className="rise mb-6 p-6">
            <h2 className="mb-5 font-display text-xl font-semibold tracking-tight">Contact</h2>
            <div className="grid grid-cols-2 gap-6 md:grid-cols-3">
              <Field label="Name" testId="detail-contact-name">{b.contact?.full_name}</Field>
              <Field label="Email" testId="detail-contact-email">{b.contact?.email}</Field>
              <Field label="Phone" testId="detail-contact-phone"><Phone contact={b.contact} testId="detail-contact-phone-value" /></Field>
              <Field label="Secondary name" testId="detail-secondary-name">{b.secondary_contact_name}</Field>
              <Field label="Secondary phone" testId="detail-secondary-phone">{b.secondary_contact_phone}</Field>
            </div>
          </Card>

          {b.notes && (
            <Card className="rise p-6">
              <h2 className="mb-3 font-display text-xl font-semibold tracking-tight">Notes</h2>
              <p className="whitespace-pre-wrap text-sm text-ink/70" data-testid="detail-notes">{b.notes}</p>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
