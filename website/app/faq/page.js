import Link from "next/link";

export const metadata = {
  title: "FAQ",
  description:
    "Pricing structure, deposit terms, delivery timelines and cancellation policy for Flyboy Videography.",
};

const FAQ = [
  {
    q: "How is your pricing structured?",
    a: "Every event category has 2–3 flat-price tiers (Basic / Classic / Royale) with the exact deliverables listed on the Services page. There are no hidden fees — the tier price is the price you pay, plus optional extra reels if you want more social cuts. Travel outside the stated service area is quoted in advance.",
  },
  {
    q: "How much is the deposit, and when is the balance due?",
    a: "A 50% deposit secures your date. The remaining 50% is due 3–5 days before the event. The deposit is non-refundable except where we cancel or a statutory right of cancellation applies.",
  },
  {
    q: "What's your delivery timeline?",
    a: "Delivery windows are stated on each package. As a rough guide: 7 days for Basic wedding packages, 7–14 days for larger packages, and faster (typically 3–5 days) for social reels, lifestyle shoots and graduations. If an unavoidable delay comes up we'll notify you in writing with a revised delivery date.",
  },
  {
    q: "What's your cancellation policy?",
    a: "More than 30 days before the event: the deposit is retained; no further payment is due. Within 30 days: the deposit is retained and 50% of the remaining balance is payable to cover committed time. One free reschedule is available if requested more than 30 days out, subject to date availability. Full terms are on the Terms & Conditions page.",
  },
  {
    q: "What areas do you cover?",
    a: "We're based in West Yorkshire and cover Leeds, Sheffield and the wider region as standard. We do travel further — coverage outside the standard area is quoted in advance to cover travel and accommodation where needed.",
  },
  {
    q: "How many revision rounds do I get?",
    a: "Every package includes a set number of revision rounds per deliverable. If a request would exceed the included allowance we don't block it — we flag it in your client portal so you can decide whether to proceed. Additional revisions beyond the allowance may be quoted separately; they are never charged silently.",
  },
  {
    q: "Do I get the raw footage?",
    a: "Master (unedited) footage is not delivered as part of any package. We retain masters for the period stated in your booking agreement so we can re-edit or issue a re-encode if needed, then delete them from active storage.",
  },
  {
    q: "Can I use my delivered films on social media?",
    a: "Yes — you receive an unlimited personal-use licence to the delivered films and stills as soon as the final invoice is paid in full. Commercial use (e.g. a venue or brand using footage in their own marketing) requires a separate licence — get in touch and we'll sort it.",
  },
];

export default function FaqPage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQ.map(({ q, a }) => ({
      "@type": "Question",
      name: q,
      acceptedAnswer: { "@type": "Answer", text: a },
    })),
  };

  return (
    <div className="bg-cream">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <div className="mx-auto max-w-3xl px-6 pb-20 pt-32 md:pt-40">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-ink/70">
          Common questions
        </p>
        <h1 className="mt-3 font-display text-4xl font-bold tracking-tight md:text-5xl">
          Frequently asked questions
        </h1>
        <p className="mt-4 max-w-xl text-ink/70">
          Straight answers on pricing, deposits, timelines and cancellations.
          If your question isn&rsquo;t here, just{" "}
          <Link
            href="/contact"
            className="underline decoration-dotted underline-offset-4 hover:decoration-solid"
          >
            drop us a line
          </Link>
          .
        </p>

        <div className="mt-12 divide-y divide-ink/10 border-y border-ink/10">
          {FAQ.map(({ q, a }, i) => (
            <details
              key={q}
              data-testid={`faq-item-${i}`}
              className="group py-6"
              open={i === 0}
            >
              <summary className="flex cursor-pointer list-none items-start justify-between gap-6">
                <h2 className="font-display text-lg font-semibold tracking-tight md:text-xl">
                  {q}
                </h2>
                <span
                  aria-hidden
                  className="mt-1 flex h-8 w-8 flex-none items-center justify-center rounded-full border border-ink/15 font-mono text-sm text-ink/70 transition-transform group-open:rotate-45"
                >
                  +
                </span>
              </summary>
              <p className="mt-4 max-w-prose text-ink/80">{a}</p>
            </details>
          ))}
        </div>

        <div className="mt-16 rounded-lg border border-ink/10 bg-sand p-6">
          <p className="font-display text-lg font-semibold">
            Still not sure which package fits?
          </p>
          <p className="mt-2 text-ink/70">
            Send a quick note with your event date and location and we&rsquo;ll
            reply with a specific recommendation.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              href="/contact"
              data-testid="faq-enquire-cta"
              className="rounded-full bg-ink px-6 py-2.5 text-sm font-medium text-cream hover:bg-ink/90"
            >
              Enquire
            </Link>
            <Link
              href="/services"
              data-testid="faq-services-link"
              className="rounded-full border border-ink/20 px-6 py-2.5 text-sm font-medium text-ink hover:border-ink hover:bg-ink hover:text-cream"
            >
              See services &amp; pricing
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
