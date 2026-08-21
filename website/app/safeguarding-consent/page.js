import Link from "next/link";

export const metadata = {
  title: "Children & Safeguarding Consent",
  description:
    "Guardian consent, safeguarding rights, and how consent for minors is captured at booking with Flyboy Videography.",
  robots: { index: true, follow: true },
};

// SOLICITOR REVIEW PENDING — do not treat as final legal copy.
const LAST_UPDATED = null;

export default function SafeguardingConsentPage() {
  return (
    <div className="bg-cream">
      <div className="mx-auto max-w-3xl px-6 pb-20 pt-32 md:pt-40">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/70">Legal</p>
        <h1 className="mt-3 font-display text-4xl font-bold tracking-tight md:text-5xl">
          Children &amp; Safeguarding Consent
        </h1>
        <p className="mt-3 font-mono text-xs uppercase tracking-widest text-ink/70">
          {LAST_UPDATED ? `Last updated ${LAST_UPDATED}` : "Not yet published — pending solicitor review"}
        </p>

        <div className="mt-10 space-y-8 text-ink/90 leading-relaxed">
          <p className="italic text-ink/70">
            This applies whenever anyone under 18 will appear in the video, audio, or photos from your booking.
          </p>

          <section>
            <h2 className="font-display text-xl font-semibold">Who this is for</h2>
            <p className="mt-3">
              The parent or legal guardian of any child under 18 who&apos;ll appear in the content from your session.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">What you&apos;re agreeing to</h2>
            <ul className="mt-3 list-disc space-y-2 pl-6">
              <li>That your child may be filmed, photographed, and/or recorded during the booked session</li>
              <li>That the resulting content may be used as described in our <Link className="underline" href="/model-release">Model &amp; Talent Release</Link> — including portfolio and marketing use — unless you choose to opt out</li>
              <li>That you&apos;re the parent or legal guardian of the child(ren) involved, or have the explicit consent of their parent or legal guardian to give this consent on their behalf</li>
            </ul>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">Your rights</h2>
            <ul className="mt-3 list-disc space-y-2 pl-6">
              <li>You can ask that your child&apos;s content specifically be kept private, even if you&apos;re comfortable with other participants&apos; content being used</li>
              <li>You can withdraw this consent in writing at any time</li>
              <li>You can ask what data or content we hold about your child, and request it be deleted, subject to our standard data retention obligations</li>
            </ul>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">How this is captured</h2>
            <p className="mt-3">
              At booking, if you tell us anyone under 18 will be involved, we&apos;ll ask for the guardian&apos;s name and a confirmation that you&apos;re providing this consent — this is recorded against your booking, along with the date and time.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">Questions or concerns</h2>
            <p className="mt-3">
              Reach us anytime at <a className="underline" href="mailto:hello@flyboyvideography.com">hello@flyboyvideography.com</a> — safeguarding questions are always taken seriously and answered directly, not left to a form.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
