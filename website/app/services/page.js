import { packages, graduation, extras, bookingTerms } from "../../lib/pricing";

export const metadata = {
  title: "Services & Pricing",
  description:
    "Wedding videography from £250, birthday films, naming ceremony & gender reveal coverage, lifestyle shoots and graduation reels. Transparent GBP pricing, 50% deposit secures your date.",
};

const gbp = (n) => `£${n}`;

function TierCard({ tier, hoursOnly }) {
  return (
    <div
      data-testid={`tier-${tier.name.toLowerCase()}`}
      className={`relative flex flex-col rounded-lg border p-8 ${
        tier.popular ? "border-ink bg-dune" : "border-dune bg-sand"
      }`}
    >
      {tier.popular && (
        <span className="absolute -top-3 left-8 rounded-full bg-ink px-3 py-1 font-mono text-[10px] font-bold uppercase tracking-widest text-cream">
          Most popular
        </span>
      )}
      <h3 className="font-display text-xl font-bold">{tier.name}</h3>
      <p className="mt-4 font-mono text-4xl font-bold tracking-tight">{gbp(tier.price)}</p>
      <p className="mt-1 font-mono text-xs uppercase tracking-widest text-ink/60">{tier.coverage}</p>
      {!hoursOnly && (
        <div className="mt-6 border-t border-ink/10 pt-5">
          {tier.leadIn && <p className="mb-3 text-sm font-semibold">{tier.leadIn}</p>}
          <ul className="space-y-2.5 text-sm leading-relaxed text-ink/80">
            {tier.features.map((f) => (
              <li key={f} className="flex gap-2.5">
                <span aria-hidden className="mt-2 h-1 w-1 shrink-0 rounded-full bg-ink" />
                {f}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function ServicesPage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Service",
    name: "Flyboy Videography — Event Videography Services",
    provider: { "@type": "LocalBusiness", name: "Flyboy Videography" },
    areaServed: "GB",
    hasOfferCatalog: {
      "@type": "OfferCatalog",
      name: "Videography Packages",
      itemListElement: [
        ...packages.flatMap((p) =>
          p.tiers.map((t) => ({
            "@type": "Offer",
            name: `${p.title} — ${t.name}`,
            price: t.price,
            priceCurrency: "GBP",
            description: t.coverage,
          }))
        ),
        {
          "@type": "Offer",
          name: graduation.title,
          price: graduation.price,
          priceCurrency: "GBP",
          description: graduation.coverage,
        },
      ],
    },
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

      <section className="bg-coal text-cream">
        <div className="mx-auto max-w-6xl px-6 py-24 md:py-32">
          <p className="font-mono text-xs uppercase tracking-[0.35em] text-dune">Services &amp; Pricing</p>
          <h1 className="mt-6 max-w-3xl font-display text-4xl font-bold leading-tight tracking-tight md:text-6xl">
            Honest pricing. Cinematic results.
          </h1>
          <p className="mt-6 max-w-xl text-lg text-dune">
            Every package is shot and edited by Flyboy. Pick a tier, add extra reels if you need them — no hidden fees.
          </p>
        </div>
      </section>

      {packages.map((pkg) => (
        <section key={pkg.id} id={pkg.id} className="border-b border-dune">
          <div className="mx-auto max-w-6xl px-6 py-16 md:py-20">
            <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">{pkg.title}</h2>
            {pkg.hoursOnly && (
              <p className="mt-2 font-mono text-xs uppercase tracking-widest text-ink/50">
                Coverage &amp; pricing — get in touch to discuss your event
              </p>
            )}
            <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3">
              {pkg.tiers.map((tier) => (
                <TierCard key={tier.name} tier={tier} hoursOnly={pkg.hoursOnly} />
              ))}
            </div>
          </div>
        </section>
      ))}

      <section id="graduation" className="border-b border-dune">
        <div className="mx-auto max-w-6xl px-6 py-16 md:py-20">
          <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">{graduation.title}</h2>
          <div className="mt-10 max-w-md">
            <div data-testid="tier-graduation" className="rounded-lg border border-dune bg-sand p-8">
              <p className="font-mono text-4xl font-bold tracking-tight">{gbp(graduation.price)}</p>
              <p className="mt-1 font-mono text-xs uppercase tracking-widest text-ink/60">{graduation.coverage}</p>
              <ul className="mt-6 space-y-2.5 border-t border-ink/10 pt-5 text-sm text-ink/80">
                {graduation.features.map((f) => (
                  <li key={f} className="flex gap-2.5">
                    <span aria-hidden className="mt-2 h-1 w-1 shrink-0 rounded-full bg-ink" />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section id="extras" className="border-b border-dune bg-sand">
        <div className="mx-auto max-w-6xl px-6 py-16 md:py-20">
          <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">{extras.title}</h2>
          <p className="mt-2 font-mono text-xs uppercase tracking-widest text-ink/50">{extras.subtitle}</p>
          <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-3">
            {extras.items.map((item) => (
              <div
                key={item.label}
                data-testid={`extra-${item.price}`}
                className="flex items-center justify-between rounded-lg border border-dune bg-cream px-6 py-5"
              >
                <span className="text-sm font-medium">{item.label}</span>
                <span className="font-mono text-xl font-bold">{gbp(item.price)}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="booking-terms" className="bg-coal text-cream">
        <div className="mx-auto max-w-6xl px-6 py-16 md:py-20">
          <h2 className="font-display text-2xl font-bold tracking-tight md:text-3xl">Booking terms</h2>
          <p data-testid="booking-terms" className="mt-4 max-w-xl text-lg text-dune">{bookingTerms}</p>
          <a
            href="mailto:hello@flyboyvideography.com"
            data-testid="services-enquire-cta"
            className="mt-8 inline-block rounded-full bg-cream px-8 py-3 font-medium text-ink transition-opacity hover:opacity-85"
          >
            Enquire about your date
          </a>
        </div>
      </section>
    </>
  );
}
