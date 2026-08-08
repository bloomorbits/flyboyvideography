import Link from "next/link";

export const metadata = {
  title: "Privacy Policy",
  description:
    "How Flyboy Videography collects, uses and protects your personal information.",
  robots: { index: true, follow: true },
};

// Placeholder-but-real privacy policy. Written in plain English and
// covers what UK GDPR / DPA 2018 expects for a small event-videography
// studio: what is collected, why, retention, sharing, and rights.
//
// This is intentionally a solid starting draft, NOT bespoke legal
// advice. It is meant to be updated by (or reviewed with) legal
// counsel before high-volume traffic hits the site.

const LAST_UPDATED = "8 February 2026";

export default function PrivacyPage() {
  return (
    <div className="bg-cream">
      <div className="mx-auto max-w-3xl px-6 pb-20 pt-32 md:pt-40">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/50">
          Legal
        </p>
        <h1 className="mt-3 font-display text-4xl font-bold tracking-tight md:text-5xl">
          Privacy Policy
        </h1>
        <p className="mt-3 font-mono text-xs uppercase tracking-widest text-ink/50">
          Last updated {LAST_UPDATED}
        </p>

        <div className="prose prose-neutral mt-10 max-w-none text-ink/85">
          <h2 className="font-display text-xl font-bold">Who we are</h2>
          <p>
            Flyboy Videography (&ldquo;we&rdquo;, &ldquo;us&rdquo;) is a UK-based event
            videography studio. This policy explains how we handle personal
            information collected through this website and through our booking,
            delivery and client-portal workflows. For any privacy question,
            contact{" "}
            <a href="mailto:hello@flyboyvideography.com" className="underline underline-offset-4">
              hello@flyboyvideography.com
            </a>
            .
          </p>

          <h2 className="mt-8 font-display text-xl font-bold">What we collect</h2>
          <ul className="list-disc space-y-1 pl-6">
            <li>
              <strong>Enquiry details:</strong> name, email, phone (if
              provided), event date, location and any notes you share with an
              enquiry.
            </li>
            <li>
              <strong>Booking &amp; delivery data:</strong> once a booking is
              confirmed, we also store the event address, invoice-related
              details, and links to the finished films/photos in your client
              portal.
            </li>
            <li>
              <strong>Website usage:</strong> anonymised page-view and
              interaction data, only if you opt in to analytics cookies. No
              analytics scripts load before you consent.
            </li>
            <li>
              <strong>Communications:</strong> emails you send us, and our
              replies.
            </li>
          </ul>

          <h2 className="mt-8 font-display text-xl font-bold">Why we use it</h2>
          <ul className="list-disc space-y-1 pl-6">
            <li>To respond to enquiries and prepare quotes.</li>
            <li>
              To perform the videography contract you book — coverage on the
              day, editing, and delivery through the client portal.
            </li>
            <li>To issue invoices and keep required financial records.</li>
            <li>
              To improve this website (analytics), only where you have opted
              in.
            </li>
          </ul>

          <h2 className="mt-8 font-display text-xl font-bold">Legal bases</h2>
          <p>
            We rely on <em>contract</em> for booking, delivery and invoicing;
            <em> legitimate interests</em> for responding to enquiries and
            keeping our site secure; <em>legal obligation</em> for tax and
            accounting records; and <em>consent</em> for analytics cookies and
            for any promotional use of your footage.
          </p>

          <h2 className="mt-8 font-display text-xl font-bold">How long we keep it</h2>
          <ul className="list-disc space-y-1 pl-6">
            <li>Enquiries that don&rsquo;t convert: up to 12 months.</li>
            <li>
              Booking &amp; delivery records: for the duration of the
              engagement and for the period required by UK tax law (currently 6
              years for financial records).
            </li>
            <li>
              Website analytics: aggregated only, retained no longer than 26
              months.
            </li>
            <li>
              Master footage: archived after delivery for a fixed period agreed
              in your booking contract, then deleted from active storage.
            </li>
          </ul>

          <h2 className="mt-8 font-display text-xl font-bold">Who we share it with</h2>
          <p>We share personal information only where necessary, with:</p>
          <ul className="list-disc space-y-1 pl-6">
            <li>
              <strong>Supabase</strong> — hosts the client portal database and
              authentication.
            </li>
            <li>
              <strong>Vercel</strong> — hosts and serves this public website.
            </li>
            <li>
              <strong>Payment processor</strong> — once wired in, handles
              deposit and balance payments. We do not store card details.
            </li>
            <li>
              <strong>Email delivery provider</strong> — once wired in, sends
              transactional emails such as booking confirmations and delivery
              notices.
            </li>
            <li>UK tax and legal authorities where the law requires.</li>
          </ul>
          <p>
            We do not sell your data. We do not use it for cross-site
            advertising.
          </p>

          <h2 className="mt-8 font-display text-xl font-bold">Cookies</h2>
          <p>
            We use only cookies that are strictly necessary for the site to
            work, plus (with your explicit opt-in) anonymised analytics
            cookies. You can change your choice at any time by clearing the
            <code className="mx-1 rounded bg-ink/5 px-1.5 py-0.5 font-mono text-xs">flyboy_consent</code>
            key in your browser&rsquo;s site storage and reloading the page.
          </p>

          <h2 className="mt-8 font-display text-xl font-bold">Your rights</h2>
          <p>
            Under UK GDPR you have the right to access, correct, delete,
            restrict, port or object to our use of your personal data, and to
            withdraw consent where we rely on it. To exercise any right, email
            {" "}
            <a href="mailto:hello@flyboyvideography.com" className="underline underline-offset-4">
              hello@flyboyvideography.com
            </a>
            . You also have the right to complain to the ICO
            (<a href="https://ico.org.uk" target="_blank" rel="noreferrer" className="underline underline-offset-4">ico.org.uk</a>).
          </p>

          <h2 className="mt-8 font-display text-xl font-bold">Changes</h2>
          <p>
            We&rsquo;ll update this policy as our workflow evolves. The
            &ldquo;last updated&rdquo; date at the top will always reflect the
            most recent change.
          </p>

          <p className="mt-10 text-sm text-ink/60">
            See also our{" "}
            <Link href="/terms" className="underline underline-offset-4">Terms &amp; Conditions</Link>.
          </p>
        </div>
      </div>
    </div>
  );
}
