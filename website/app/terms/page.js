import Link from "next/link";

export const metadata = {
  title: "Terms & Conditions",
  description:
    "Booking terms, deposit and delivery terms, cancellation policy, and usage rights for Flyboy Videography.",
  robots: { index: true, follow: true },
};

// SOLICITOR REVIEW PENDING — includes 14-day cooling-off clause (§7),
// which needs specific solicitor sign-off before this page ships to real
// customers. Keep LAST_UPDATED null until approved.
const LAST_UPDATED = null;

export default function TermsPage() {
  return (
    <div className="bg-cream">
      <div className="mx-auto max-w-3xl px-6 pb-20 pt-32 md:pt-40">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/70">Legal</p>
        <h1 className="mt-3 font-display text-4xl font-bold tracking-tight md:text-5xl">
          Booking Terms &amp; Conditions
        </h1>
        <p className="mt-3 font-mono text-xs uppercase tracking-widest text-ink/70">
          {LAST_UPDATED ? `Last updated ${LAST_UPDATED}` : "Not yet published — pending solicitor review"}
        </p>

        <div className="mt-10 space-y-8 text-ink/90 leading-relaxed">
          <p>
            These terms apply to every booking made through flyboyvideography.com. By checking the box at checkout, you&apos;re confirming you&apos;ve read and agree to them.
          </p>

          <section>
            <h2 className="font-display text-xl font-semibold">1. Deposits &amp; Payment</h2>
            <p className="mt-3">
              A 50% deposit is required to secure your date. The remaining balance is due 3–5 days before your event. If payment fails or isn&apos;t completed, your booking isn&apos;t confirmed and your date isn&apos;t held.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">2. Cancellations &amp; Refunds</h2>
            <ul className="mt-3 list-disc space-y-2 pl-6">
              <li>More than 7 days before your event: full refund of your deposit</li>
              <li>3–7 days before your event: 50% of your deposit refunded</li>
              <li>Within 48 hours of your event: no refund</li>
              <li>No-shows forfeit their deposit in full</li>
            </ul>
            <p className="mt-3">
              To cancel, contact us at <a className="underline" href="mailto:hello@flyboyvideography.com">hello@flyboyvideography.com</a> as early as possible.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">3. Rescheduling</h2>
            <p className="mt-3">
              If you need to move your date, contact us as soon as you can. We&apos;ll do our best to accommodate a new date subject to availability — rescheduling isn&apos;t guaranteed and may be treated as a cancellation and new booking if requested with less than 48 hours&apos; notice.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">4. Content Usage Rights</h2>
            <p className="mt-3">
              What we can and can&apos;t do with the footage and photos from your session is covered separately in our <Link className="underline" href="/model-release">Model &amp; Talent Release</Link> — please read that alongside these terms.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">5. Delivery Timeline</h2>
            <p className="mt-3">
              Delivery times vary by package and are stated on your service confirmation — typically 7 days for standard packages, up to 7–14 days for full-day coverage. Delays will always be communicated directly; they&apos;re not common, but travel, extreme weather, or exceptional circumstances can occasionally affect timing.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">6. Weather &amp; Outdoor Shoots</h2>
            <p className="mt-3">
              For sessions involving outdoor locations, weather beyond our control (e.g. severe storms, unsafe conditions) may require adjusting the shoot plan on the day, or in rare cases rescheduling. We&apos;re not liable for weather-related changes to the shoot, but we&apos;ll always work with you to find the best outcome.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">7. Your Right to Cancel (14-Day Cooling-Off)</h2>
            <p className="mt-3">
              UK law normally gives you 14 days to cancel an online booking. Because our services are typically booked for a specific date, once you&apos;ve agreed a date and time with us, you&apos;re agreeing that the service will be carried out before the 14-day period ends, and that your right to a full refund under this cooling-off period ends once the shoot has taken place. This doesn&apos;t affect your rights under our own cancellation policy above.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">8. Liability</h2>
            <p className="mt-3">
              We carry appropriate insurance for our work. We&apos;re not liable for indirect or consequential losses arising from your booking, except where required by law.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
