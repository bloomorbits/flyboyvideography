import Link from "next/link";

export const metadata = {
  title: "Terms & Conditions",
  description:
    "Booking terms, deposit and delivery terms, cancellation policy, and usage rights for Flyboy Videography.",
  robots: { index: true, follow: true },
};

const LAST_UPDATED = "8 February 2026";

// Solid starter T&Cs for a UK-based event videography studio.
// Deliberately plain-English and safe defaults; anything project-specific
// (advance-cancellation window, revision counts, usage rights) is written
// to match what the pricing packages and portal workflows already do.

export default function TermsPage() {
  return (
    <div className="bg-cream">
      <div className="mx-auto max-w-3xl px-6 pb-20 pt-32 md:pt-40">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/50">
          Legal
        </p>
        <h1 className="mt-3 font-display text-4xl font-bold tracking-tight md:text-5xl">
          Terms &amp; Conditions
        </h1>
        <p className="mt-3 font-mono text-xs uppercase tracking-widest text-ink/50">
          Last updated {LAST_UPDATED}
        </p>

        <div className="prose prose-neutral mt-10 max-w-none text-ink/85">
          <h2 className="font-display text-xl font-bold">1. Booking &amp; deposit</h2>
          <p>
            A booking is confirmed once a signed booking agreement is in place
            and the 50% deposit has cleared. The deposit secures your date and
            is non-refundable except where we cancel or where a statutory
            right of cancellation applies.
          </p>

          <h2 className="mt-8 font-display text-xl font-bold">2. Balance payment</h2>
          <p>
            The remaining 50% balance is due 3&ndash;5 days before your event.
            If the balance has not cleared by 24 hours before the event we
            reserve the right to withdraw coverage; in that case the deposit
            is retained to cover time already committed.
          </p>

          <h2 className="mt-8 font-display text-xl font-bold">3. Coverage on the day</h2>
          <p>
            Coverage hours are as stated in your chosen package. Additional
            time on the day can be added at our published rate, subject to
            availability, and is invoiced separately. Travel outside the
            stated service area is quoted in advance.
          </p>

          <h2 className="mt-8 font-display text-xl font-bold">4. Delivery timelines</h2>
          <p>
            Standard delivery windows are stated per package (typically
            7&ndash;14 days for wedding packages, faster for shorter shoots
            and reels). If a delay is unavoidable we will notify you in
            writing with a revised delivery date.
          </p>

          <h2 className="mt-8 font-display text-xl font-bold">5. Revisions</h2>
          <p>
            Each package includes a set number of revision rounds per
            deliverable. Additional revisions beyond the included allowance
            are flagged in the client portal and may be quoted separately;
            they are never applied silently.
          </p>

          <h2 className="mt-8 font-display text-xl font-bold">6. Cancellation</h2>
          <ul className="list-disc space-y-1 pl-6">
            <li>
              <strong>By you, more than 30 days before the event:</strong> the
              deposit is retained; no further payment is due.
            </li>
            <li>
              <strong>By you, within 30 days of the event:</strong> the deposit
              is retained and 50% of the remaining balance is payable to cover
              committed time and turned-away enquiries.
            </li>
            <li>
              <strong>By us:</strong> any payments received are refunded in
              full, and where possible we will help arrange an alternative
              videographer.
            </li>
            <li>
              <strong>Rescheduling:</strong> one free reschedule is available
              if requested more than 30 days before the event and subject to
              availability of the new date.
            </li>
          </ul>

          <h2 className="mt-8 font-display text-xl font-bold">7. Usage rights</h2>
          <p>
            You receive an unlimited personal-use licence to the delivered
            films and stills as soon as the final invoice is paid in full. We
            retain copyright and the right to use the delivered work in our
            own portfolio and marketing unless you specifically opt out in
            writing before delivery.
          </p>

          <h2 className="mt-8 font-display text-xl font-bold">8. Master footage</h2>
          <p>
            Master (unedited) footage is not delivered as part of any package.
            We retain masters for the period stated in your booking agreement,
            after which they are deleted from active storage.
          </p>

          <h2 className="mt-8 font-display text-xl font-bold">9. Liability</h2>
          <p>
            Our liability for any single booking is capped at the total
            invoice value of that booking. We are not liable for indirect or
            consequential loss, or for events outside our reasonable control
            (illness, equipment failure despite backups, weather forcing an
            event to be cancelled by the venue, etc.). Where equipment failure
            or illness prevents us from covering an event, our first remedy is
            to arrange a suitable substitute videographer; if that is not
            possible, all sums paid are refunded.
          </p>

          <h2 className="mt-8 font-display text-xl font-bold">10. Governing law</h2>
          <p>
            These terms are governed by the laws of England &amp; Wales. Any
            dispute is subject to the exclusive jurisdiction of the courts of
            England &amp; Wales.
          </p>

          <p className="mt-10 text-sm text-ink/60">
            See also our{" "}
            <Link href="/privacy" className="underline underline-offset-4">Privacy Policy</Link>.
          </p>
        </div>
      </div>
    </div>
  );
}
