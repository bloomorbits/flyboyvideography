import Link from "next/link";
import { packages as fallbackPackages, graduation as fallbackGraduation, extras as fallbackExtras, bookingTerms as fallbackBookingTerms } from "../../lib/pricing";
import HeroPlayer from "../components/HeroPlayer";
import Marquee from "../components/Marquee";
import Reveal from "../components/Reveal";
import { SERVICE_AREA } from "../components/SiteFooter";

export const metadata = {
  title: "Services & Pricing",
  description:
    "Wedding videography from £250, birthday films, naming ceremony & gender reveal coverage, lifestyle shoots and graduation reels. Transparent GBP pricing, 50% deposit secures your date.",
};

// Refresh the cached HTML at most every 60s. Publishing new pricing via
// the admin panel will show up within that window — a good tradeoff
// between "near-instant" and "don't hammer the backend on every request."
export const revalidate = 60;

// Backend URL for the pricing fetch. Missing = we hit the fallback path.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

async function fetchCatalog() {
  // Guardrail: if the backend is unreachable OR the API is missing on the
  // very first deploy, we serve the last-known-good `pricing.js` constants
  // and log the failure. The site NEVER shows a "pricing missing" error.
  if (!API_BASE) {
    return {
      packages: fallbackPackages,
      graduation: fallbackGraduation,
      extras: fallbackExtras,
      bookingTerms: fallbackBookingTerms,
    };
  }
  try {
    const res = await fetch(`${API_BASE}/api/pricing`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) throw new Error(`pricing HTTP ${res.status}`);
    const body = await res.json();
    const c = body?.content;
    if (!c || !Array.isArray(c.packages) || !c.graduation || !c.extras) {
      throw new Error("pricing content shape invalid");
    }
    return {
      packages: c.packages,
      graduation: c.graduation,
      extras: c.extras,
      bookingTerms: c.bookingTerms || fallbackBookingTerms,
    };
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn("[services] pricing fetch failed — using pricing.js fallback:", err?.message || err);
    return {
      packages: fallbackPackages,
      graduation: fallbackGraduation,
      extras: fallbackExtras,
      bookingTerms: fallbackBookingTerms,
    };
  }
}

const gbp = (n) => `£${n}`;
const CATEGORIES = ["Weddings", "Birthdays", "Naming Ceremonies", "Gender Reveals", "Lifestyle", "Graduations", "Extra Reels"];

function TierCard({ tier, hoursOnly, packageTitle, packageId }) {
  // Deep-link into /book pre-populating the tier the visitor tapped, so they
  // arrive on the booking flow with everything but the date already chosen.
  const bookHref = `/book?package=${encodeURIComponent(packageId)}&tier=${encodeURIComponent(tier.name)}`;
  return (
    <div
      data-testid={`tier-${tier.name.toLowerCase()}`}
      className={`glass-card relative flex flex-col rounded-lg p-8 ${tier.popular ? "!border-ink/40" : ""}`}
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
      <Link
        href={bookHref}
        data-testid={`tier-cta-${tier.name.toLowerCase()}`}
        data-package={packageTitle}
        data-tier={tier.name}
        className={`mt-8 inline-flex w-full items-center justify-between gap-2 rounded-full border px-5 py-3 text-sm font-medium transition-colors duration-200 ${
          tier.popular
            ? "border-transparent bg-ink text-cream hover:bg-ink/90"
            : "border-ink/20 bg-transparent text-ink hover:border-ink hover:bg-ink hover:text-cream"
        }`}
      >
        <span>Book {tier.name}</span>
        <span aria-hidden className="font-mono">→</span>
      </Link>
    </div>
  );
}

function SectionBackdrop() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute -right-24 top-8 h-72 w-72 rounded-full bg-dune opacity-60 blur-3xl" />
      <div className="absolute -left-24 bottom-0 h-64 w-64 rounded-full bg-sand opacity-80 blur-3xl" />
    </div>
  );
}

export default async function ServicesPage() {
  const { packages, graduation, extras, bookingTerms } = await fetchCatalog();

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

      <HeroPlayer
        kicker="Services & Pricing"
        headline="Turning visuals into value"
        sub="Every package is shot and edited by Flyboy. Pick a tier, add extra reels if you need them — no hidden fees."
      />

      <Marquee items={CATEGORIES} />

      {/* Service area strip — one line, same convention on the Portfolio page. */}
      <div className="border-b border-dune bg-cream">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <p
            data-testid="services-service-area"
            className="font-mono text-[11px] uppercase tracking-[0.3em] text-ink/60"
          >
            Serving {SERVICE_AREA} · Travel elsewhere quoted in advance
          </p>
        </div>
      </div>

      {packages.map((pkg, idx) => (
        <section key={pkg.id} id={pkg.id} className="relative border-b border-dune">
          <SectionBackdrop />
          <div className="relative mx-auto max-w-6xl px-6 py-16 md:py-20">
            <Reveal>
              <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">{pkg.title}</h2>
              {pkg.hoursOnly && (
                <p className="mt-2 font-mono text-xs uppercase tracking-widest text-ink/70">
                  Coverage &amp; pricing — get in touch to discuss your event
                </p>
              )}
            </Reveal>
            <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3">
              {pkg.tiers.map((tier, i) => (
                <Reveal key={tier.name} delay={i * 100}>
                  <TierCard tier={tier} hoursOnly={pkg.hoursOnly} packageTitle={pkg.title} packageId={pkg.id} />
                </Reveal>
              ))}
            </div>

            {/* Package-level CTA — one per package section, distinct from
                the per-tier CTAs above. Pre-fills with just the package
                name so a visitor unsure which tier to pick can start the
                conversation. */}
            <Reveal delay={400}>
              <div className="mt-10 flex flex-col items-start justify-between gap-4 rounded-lg border border-ink/10 bg-cream/50 p-5 md:flex-row md:items-center">
                <p className="text-sm text-ink/70">
                  Not sure which tier fits? Start a conversation and we&rsquo;ll
                  recommend the right {pkg.title.toLowerCase()} package for your event.
                </p>
                <Link
                  href={`/contact?package=${encodeURIComponent(pkg.id)}`}
                  data-testid={`package-cta-${pkg.id}`}
                  data-package={pkg.title}
                  className="inline-flex flex-shrink-0 items-center gap-2 rounded-full bg-ink px-5 py-2.5 text-sm font-medium text-cream hover:bg-ink/90"
                >
                  Enquire about this package <span aria-hidden className="font-mono">→</span>
                </Link>
              </div>
            </Reveal>
          </div>
          {idx === 1 && (
            <div className="relative">
              <Marquee items={CATEGORIES} />
            </div>
          )}
        </section>
      ))}

      <section id="graduation" className="relative border-b border-dune">
        <SectionBackdrop />
        <div className="relative mx-auto max-w-6xl px-6 py-16 md:py-20">
          <Reveal>
            <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">{graduation.title}</h2>
          </Reveal>
          <Reveal delay={100}>
            <div className="mt-10 max-w-md">
              <div data-testid="tier-graduation" className="glass-card flex flex-col rounded-lg p-8">
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
                <Link
                  href="/book?package=graduation"
                  data-testid="tier-cta-graduation"
                  data-package={graduation.title}
                  className="mt-8 inline-flex w-full items-center justify-between gap-2 rounded-full bg-ink px-5 py-3 text-sm font-medium text-cream transition-colors duration-200 hover:bg-ink/90"
                >
                  <span>Book {graduation.title}</span>
                  <span aria-hidden className="font-mono">→</span>
                </Link>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <Marquee items={["Add-ons", "Extra Reels", "Any Package"]} />

      <section id="extras" className="relative border-b border-dune bg-sand">
        <div className="relative mx-auto max-w-6xl px-6 py-16 md:py-20">
          <Reveal>
            <h2 className="font-display text-3xl font-bold tracking-tight md:text-4xl">{extras.title}</h2>
            <p className="mt-2 font-mono text-xs uppercase tracking-widest text-ink/70">{extras.subtitle}</p>
          </Reveal>
          <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-3">
            {extras.items.map((item, i) => (
              <Reveal key={item.label} delay={i * 100}>
                <div
                  data-testid={`extra-${item.price}`}
                  className="glass-card flex items-center justify-between rounded-lg px-6 py-5"
                >
                  <span className="text-sm font-medium">{item.label}</span>
                  <span className="font-mono text-xl font-bold">{gbp(item.price)}</span>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section id="booking-terms" className="relative overflow-hidden bg-coal text-cream">
        <div aria-hidden className="pointer-events-none absolute inset-0">
          <div className="blob blob-2" />
          <div className="grain" />
        </div>
        <div className="relative z-10 mx-auto max-w-6xl px-6 py-16 md:py-20">
          <Reveal>
            <h2 className="font-display text-2xl font-bold tracking-tight md:text-3xl">Booking terms</h2>
            <p data-testid="booking-terms" className="mt-4 max-w-xl text-lg text-dune">{bookingTerms}</p>
            <Link
              href="/book"
              data-testid="services-enquire-cta"
              className="mt-8 inline-block rounded-full bg-cream px-8 py-3 font-medium text-ink transition-opacity hover:opacity-85"
            >
              Book your date
            </Link>
          </Reveal>
        </div>
      </section>
    </>
  );
}
