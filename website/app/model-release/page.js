import Link from "next/link";

export const metadata = {
  title: "Model & Talent Release",
  description:
    "How Flyboy Videography uses content from your booked session in our portfolio and marketing — including your right to opt out.",
  robots: { index: true, follow: true },
};

// SOLICITOR REVIEW PENDING — do not treat as final legal copy.
// Copy drafted for readability; final review by client's solicitor
// required before real-customer bookings are accepted.
const LAST_UPDATED = null; // becomes "Not yet published" until approved

export default function ModelReleasePage() {
  return (
    <div className="bg-cream">
      <div className="mx-auto max-w-3xl px-6 pb-20 pt-32 md:pt-40">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/50">Legal</p>
        <h1 className="mt-3 font-display text-4xl font-bold tracking-tight md:text-5xl">
          Model &amp; Talent Release
        </h1>
        <p className="mt-3 font-mono text-xs uppercase tracking-widest text-ink/50">
          {LAST_UPDATED ? `Last updated ${LAST_UPDATED}` : "Not yet published — pending solicitor review"}
        </p>

        <div className="mt-10 space-y-8 text-ink/90 leading-relaxed">
          <p className="italic text-ink/70">
            What this page covers: whether we can use content from your session in our portfolio and marketing.
          </p>

          <section>
            <h2 className="font-display text-xl font-semibold">What this covers</h2>
            <p className="mt-3">
              This applies to video footage, audio recordings, and still photographs captured during your booking with Flyboy Videography.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">How we might use it</h2>
            <p className="mt-3">
              With your permission, we may feature content from your session on our website, portfolio, and social media (Instagram, TikTok, and similar platforms) — including reasonable editing, cropping, and creative adaptation for these purposes.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">Your choice</h2>
            <p className="mt-3">
              By default, we assume you&apos;re happy for us to do this — it&apos;s how we build our portfolio and it&apos;s genuinely how most clients feel. If you&apos;d rather your session stay private, just uncheck the box at booking, or let us know anytime afterward at <a className="underline" href="mailto:hello@flyboyvideography.com">hello@flyboyvideography.com</a>. Opting out never affects your right to receive your own booked deliverables in full.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">What we&apos;ll never do</h2>
            <ul className="mt-3 list-disc space-y-2 pl-6">
              <li>Sell your content to third parties</li>
              <li>Use it to advertise anything unrelated to our own videography work</li>
              <li>Use it in any way that misrepresents you</li>
            </ul>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">Changing your mind</h2>
            <p className="mt-3">
              You can withdraw this permission in writing at any time. We&apos;ll stop using your content going forward within 14 days of your request — though we can&apos;t retroactively remove things already published before you asked.
            </p>
          </section>

          <section>
            <h2 className="font-display text-xl font-semibold">If minors are involved</h2>
            <p className="mt-3">
              If anyone under 18 appears in your session&apos;s content, this permission has to come from their parent or legal guardian — see our <Link className="underline" href="/safeguarding-consent">Children &amp; Safeguarding Consent</Link> page.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
